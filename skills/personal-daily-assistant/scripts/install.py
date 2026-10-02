#!/usr/bin/env python3
"""Prepare or install the portable OpenClaw personal daily assistant."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = SKILL_ROOT / "assets" / "runtime"
MARKER = "REPLACE_WITH_YOUR_"


class InstallOptions(NamedTuple):
    project_root: Path
    data_dir: Path
    context_json: Path
    summaries_dir: Path
    timezone: str
    owner_telegram_id: str
    telegram_target: str
    openclaw_config: Path
    openclaw_sessions_dir: Path
    token_file: Path
    thread_cleanup_cutoff: str
    python_bin: str = "python3"
    evening_ten_enabled: bool = False


def _absolute(path: Path, label: str) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    return expanded.resolve(strict=False)


def _inside(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True


def ensure_data_outside_project(project_root: Path, data_dir: Path) -> None:
    project = _absolute(project_root, "project root")
    data = _absolute(data_dir, "private data directory")
    if _inside(data, project) or _inside(project, data):
        raise ValueError("private data directory must be outside the project root")


def _require_private_file(path: Path, label: str) -> Path:
    resolved = _absolute(path, label)
    if not resolved.is_file():
        raise ValueError(f"{label} does not exist: {resolved}")
    mode = stat.S_IMODE(resolved.stat().st_mode)
    if mode & 0o077:
        raise ValueError(f"{label} must have owner-only permissions (0600)")
    return resolved


def validate_context(context: dict) -> None:
    serialized = json.dumps(context, ensure_ascii=False)
    if MARKER in serialized:
        raise ValueError(f"context still contains {MARKER} markers")
    if context.get("schema_version") != 1:
        raise ValueError("context schema_version must be 1")
    if not str(context.get("active_understanding", "")).strip():
        raise ValueError("active_understanding is required")
    l1 = context.get("l1") or {}
    if not str(l1.get("text", "")).strip():
        raise ValueError("l1.text is required")
    questions = context.get("questions") or {}
    if not all(str(questions.get(key, "")).strip() for key in ("morning", "evening")):
        raise ValueError("morning and evening questions are required")
    reflections = context.get("viability_reflections") or {}
    if not reflections.get("affirmations") or not reflections.get("understandings"):
        raise ValueError("at least one affirmation and one understanding are required")
    groups = context.get("focus_groups") or []
    group_ids = {str(group.get("id")) for group in groups if group.get("id")}
    if not group_ids:
        raise ValueError("at least one focus group is required")
    tasks = context.get("task_choices") or []
    numbers = [task.get("number") for task in tasks]
    if not tasks or any(not isinstance(number, int) or number < 1 for number in numbers):
        raise ValueError("task choices require positive integer numbers")
    if len(set(numbers)) != len(numbers):
        raise ValueError("task choice numbers must be unique")
    if any(str(task.get("group_id")) not in group_ids for task in tasks):
        raise ValueError("every task must reference a known focus group")


def _reject_data_symlinks(root: Path) -> None:
    root = root.expanduser()
    if root.is_symlink():
        raise ValueError("private data root must not be a symlink")
    if root.exists():
        if not root.is_dir(): raise ValueError("private data root must be a directory")
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in dirs + files:
                if (Path(directory) / name).is_symlink():
                    raise ValueError("private data descendants must not be symlinks")


def _load_and_validate(options: InstallOptions) -> dict:
    _reject_data_symlinks(options.data_dir)
    ZoneInfo(options.timezone)
    if not options.owner_telegram_id.isdigit() or not options.telegram_target.isdigit():
        raise ValueError("Telegram owner ID and target must be numeric")
    if options.owner_telegram_id != options.telegram_target:
        raise ValueError("Telegram scheduled target must match the configured owner ID")
    destination = options.project_root.expanduser()
    _absolute(destination, "project root")
    if destination.exists() or destination.is_symlink():
        raise ValueError("project root must be a fresh, nonexisting destination")
    ensure_data_outside_project(options.project_root, options.data_dir)
    _require_private_file(options.token_file, "Telegram token file")
    context_path = _absolute(options.context_json, "context JSON")
    if not context_path.is_file():
        raise ValueError(f"context JSON does not exist: {context_path}")
    context = json.loads(context_path.read_text(encoding="utf-8"))
    validate_context(context)
    return context


def _schedule(
    options: InstallOptions,
    key: str,
    cron: str,
    job: str,
) -> dict:
    project = _absolute(options.project_root, "project root")
    return {
        "declaration_key": key,
        "cron": cron,
        "timezone": options.timezone,
        "exact": True,
        "cwd": str(project),
        "argv": [
            options.python_bin,
            str(project / "scripts" / "scheduled_job.py"),
            job,
        ],
        "env": {
            "PDS_DATA_DIR": str(_absolute(options.data_dir, "private data directory")),
            "PDS_TIMEZONE": options.timezone,
            "PDS_SUMMARIES_DIR": str(_absolute(options.summaries_dir, "summaries directory")),
            "PDS_TELEGRAM_TARGET": options.telegram_target,
            "PDS_PYTHON_BIN": options.python_bin,
        },
    }


def build_plan(options: InstallOptions) -> dict:
    _load_and_validate(options)
    project = _absolute(options.project_root, "project root")
    data = _absolute(options.data_dir, "private data directory")
    summaries = _absolute(options.summaries_dir, "summaries directory")
    sessions = _absolute(options.openclaw_sessions_dir, "OpenClaw sessions directory")
    config = _absolute(options.openclaw_config, "OpenClaw config")
    token = _absolute(options.token_file, "Telegram token file")
    schedules = [
        _schedule(options, "personal-daily-preflight-0300", "0 3 * * *", "preflight"),
        _schedule(options, "personal-daily-morning-0800", "0 8 * * *", "morning"),
        _schedule(options, "personal-daily-viability-1200", "0 12 * * *", "viability"),
        _schedule(options, "personal-daily-viability-1510", "10 15 * * *", "viability"),
        _schedule(options, "personal-daily-viability-1800", "0 18 * * *", "viability"),
        _schedule(options, "personal-daily-evening-2200", "0 22 * * *", "evening"),
        _schedule(options, "personal-daily-weekly-sun-2000", "0 20 * * 0", "weekly"),
    ]
    if options.evening_ten_enabled:
        schedules = [item for item in schedules if item["declaration_key"] != "personal-daily-evening-2200"]
        schedules.extend([
            _schedule(options, "personal-daily-ten-2200", "0 22 * * *", "ten"),
            _schedule(options, "personal-daily-evening-2210", "10 22 * * *", "evening"),
        ])
        for item in schedules:
            item["env"]["PDS_EVENING_TEN_ENABLED"] = "1"
    return {
        "schema_version": 1,
        "package_version": "0.3.0",
        "features": {"evening_ten": options.evening_ten_enabled},
        "mode": "dry-run",
        "project_root": str(project),
        "private_data_dir": str(data),
        "summaries_dir": str(summaries),
        "openclaw_config": str(config),
        "token_file": str(token),
        "plugin": {
            "id": "personal-daily-transport",
            "source": str(project / "openclaw-plugins" / "personal-daily-transport"),
            "config": {
                "ownerTelegramId": options.owner_telegram_id,
                "technicalCleanupEnabled": False,
                "eveningTenEnabled": options.evening_ten_enabled,
                "repoRoot": str(project),
                "dataDir": str(data),
                "timezone": options.timezone,
                "summariesDir": str(summaries),
                "openclawSessionsDir": str(sessions),
                "threadCleanupCutoff": options.thread_cleanup_cutoff,
                "pythonBin": options.python_bin,
            },
        },
        "telegram_guardrails": {
            "owner_id": options.owner_telegram_id,
            "groups": "disabled",
            "gateway_bind": "loopback",
            "token_file_reference": str(token),
        },
        "schedules": schedules,
        "next_step": "Merge the generated OpenClaw fragment using the installed release schema, register the declarations idempotently, then run verify.py.",
    }


def _render_context_markdown(context: dict) -> str:
    questions = context["questions"]
    lines = [
        "# Активный контекст",
        "",
        "## Главный критерий",
        "",
        str(context["active_understanding"]),
        "",
        f"L1: {context['l1']['text']}",
        "",
        "## Вопросы 1:1",
        "",
        f"- Утро: {questions['morning']}",
        f"- Вечер: {questions['evening']}",
        "",
        "## Контрольная грабля",
        "",
    ]
    lines.extend(f"- {item}" for item in context.get("warning_patterns", []))
    lines.extend(["", "## Утверждённый фокус", ""])
    for group in context["focus_groups"]:
        lines.extend(
            [
                f"### {group['label']}",
                "",
                f"L2: {group['l2']}",
                f"Фокус периода: {group['period_focus']}",
                "",
            ]
        )
    lines.extend(["## Задачи", ""])
    for task in sorted(context["task_choices"], key=lambda item: item["number"]):
        marker = "✅ " if task.get("status") == "completed" else ""
        lines.extend(
            [
                f"{task['number']}. {marker}{task['label']}",
                f"   - Результат дня: {task.get('day_result', '')}",
                f"   - Первый шаг: {task.get('first_step', '')}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _write_private(path: Path, content: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)


def _private_existing(path: Path, *, directory: bool = False) -> None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if directory: flags |= getattr(os, "O_DIRECTORY", 0)
    fd = os.open(path, flags)
    try:
        if not directory and not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError("Private state must be a regular file")
        os.fchmod(fd, 0o700 if directory else 0o600)
    finally: os.close(fd)


def apply_install(options: InstallOptions, plan: dict | None = None) -> dict:
    context = _load_and_validate(options)
    current_plan = build_plan(options)
    if plan is not None and plan != current_plan:
        raise ValueError("installation plan does not match the current validated options")
    plan = current_plan
    project = Path(plan["project_root"])
    data = Path(plan["private_data_dir"])
    summaries = Path(plan["summaries_dir"])

    # Reserve the fresh destination before any private-data or runtime writes.
    # exist_ok=False also refuses a destination created after the validation.
    project.mkdir(parents=True, exist_ok=False, mode=0o700)
    project.chmod(0o700)
    for directory in (project / "context", project / "setup", data, data / "reports", data / "views", summaries):
        directory.mkdir(parents=True, exist_ok=True)
    _private_existing(data, directory=True)
    _private_existing(data / "reports", directory=True)
    _private_existing(data / "views", directory=True)

    shutil.copytree(RUNTIME_ROOT / "scripts", project / "scripts")
    shutil.copytree(RUNTIME_ROOT / "tests", project / "tests")
    shutil.copytree(
        RUNTIME_ROOT / "openclaw-plugins",
        project / "openclaw-plugins",
    )
    shutil.copy2(SKILL_ROOT / "references" / "operator-rules.md", project / "AGENTS.md")
    (project / "context" / "active_context.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (project / "context" / "active_context.md").write_text(
        _render_context_markdown(context), encoding="utf-8"
    )
    for private_context in (project / "context").iterdir():
        private_context.chmod(0o600)
    for path, content in (
        (data / "events.jsonl", ""),
        (data / "state.json", "{}\n"),
    ):
        if not path.exists():
            _write_private(path, content)
        else:
            _private_existing(path)

    plugin_fragment = {
        "plugins": {
            "entries": {
                "personal-daily-transport": {
                    "enabled": True,
                    "config": plan["plugin"]["config"],
                }
            }
        },
        "telegram_guardrails": plan["telegram_guardrails"],
    }
    (project / "setup" / "openclaw-plugin-fragment.json").write_text(
        json.dumps(plugin_fragment, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (project / "setup" / "schedule-declarations.json").write_text(
        json.dumps(
            {"schema_version": 1, "features": plan["features"], "schedules": plan["schedules"]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    applied = dict(plan)
    applied["mode"] = "applied-local-files"
    return applied


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--context-json", type=Path, required=True)
    parser.add_argument("--summaries-dir", type=Path, required=True)
    parser.add_argument("--timezone", required=True)
    parser.add_argument("--owner-telegram-id", required=True)
    parser.add_argument("--telegram-target", required=True)
    parser.add_argument("--openclaw-config", type=Path, required=True)
    parser.add_argument("--openclaw-sessions-dir", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--thread-cleanup-cutoff", required=True)
    parser.add_argument("--python-bin", default="python3")
    parser.add_argument("--enable-evening-ten", action="store_true")
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    options = InstallOptions(
        project_root=args.project_root,
        data_dir=args.data_dir,
        context_json=args.context_json,
        summaries_dir=args.summaries_dir,
        timezone=args.timezone,
        owner_telegram_id=args.owner_telegram_id,
        telegram_target=args.telegram_target,
        openclaw_config=args.openclaw_config,
        openclaw_sessions_dir=args.openclaw_sessions_dir,
        token_file=args.token_file,
        thread_cleanup_cutoff=args.thread_cleanup_cutoff,
        python_bin=args.python_bin,
        evening_ten_enabled=args.enable_evening_ten,
    )
    plan = build_plan(options)
    result = apply_install(options, plan) if args.apply else plan
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
