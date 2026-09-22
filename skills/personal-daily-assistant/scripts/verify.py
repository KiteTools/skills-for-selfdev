#!/usr/bin/env python3
"""Verify a portable personal daily assistant installation without secrets."""

from __future__ import annotations

import argparse
import json
import re
import stat
from pathlib import Path


MARKER = "REPLACE_WITH_YOUR_"
EXPECTED_KEYS = {
    "personal-daily-preflight-0300",
    "personal-daily-morning-0800",
    "personal-daily-viability-1200",
    "personal-daily-viability-1510",
    "personal-daily-viability-1800",
    "personal-daily-evening-2200",
    "personal-daily-weekly-sun-2000",
}
RUNTIME_BANNED = re.compile(
    r"clickup|content[ _-]?ledger|macwhisper|speech[ _-]?to[ _-]?text|"
    r"audio_as_voice|voice_send|voice_cache|refresh_voice|\.Transcript\b",
    flags=re.IGNORECASE,
)


def _inside(candidate: Path, parent: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def _contains_include(value: object) -> bool:
    if isinstance(value, dict):
        return "$include" in value or any(_contains_include(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_include(item) for item in value)
    return False


def verify_installation(
    *,
    project_root: Path,
    data_dir: Path,
    token_file: Path,
    openclaw_config: Path | None,
) -> dict:
    checks: list[dict] = []
    warnings: list[str] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(passed), "detail": detail})

    project = project_root.expanduser().resolve(strict=False)
    data = data_dir.expanduser().resolve(strict=False)
    token = token_file.expanduser().resolve(strict=False)
    required = [
        project / "AGENTS.md",
        project / "context" / "active_context.json",
        project / "context" / "active_context.md",
        project / "scripts" / "personal_daily_system.py",
        project / "scripts" / "scheduled_job.py",
        project / "scripts" / "build_codex_activity_context.py",
        project / "scripts" / "codex_thread_hygiene.py",
        project / "openclaw-plugins" / "personal-daily-transport" / "openclaw.plugin.json",
        project / "setup" / "openclaw-plugin-fragment.json",
        project / "setup" / "schedule-declarations.json",
        data / "events.jsonl",
        data / "state.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    check("required_files", not missing, "all present" if not missing else f"missing: {missing}")
    check(
        "private_data_outside_project",
        not _inside(data, project) and not _inside(project, data),
        str(data),
    )

    data_mode = stat.S_IMODE(data.stat().st_mode) if data.is_dir() else None
    check("private_data_permissions", data_mode == 0o700, f"mode={data_mode!r}")
    private_files = [data / "events.jsonl", data / "state.json"]
    modes = {
        path.name: stat.S_IMODE(path.stat().st_mode)
        for path in private_files
        if path.is_file()
    }
    check(
        "private_file_permissions",
        len(modes) == len(private_files) and all(mode == 0o600 for mode in modes.values()),
        json.dumps(modes, sort_keys=True),
    )

    token_mode = stat.S_IMODE(token.stat().st_mode) if token.is_file() else None
    check(
        "token_file_permissions",
        token.is_file() and token_mode is not None and not (token_mode & 0o077),
        f"exists={token.is_file()} mode={token_mode!r}",
    )

    context_path = project / "context" / "active_context.json"
    if context_path.is_file():
        context_text = context_path.read_text(encoding="utf-8")
        try:
            context = json.loads(context_text)
        except json.JSONDecodeError as error:
            check("context", False, str(error))
        else:
            check(
                "context",
                context.get("schema_version") == 1 and MARKER not in context_text,
                "schema=1 and personalized",
            )

    schedule_path = project / "setup" / "schedule-declarations.json"
    if schedule_path.is_file():
        declarations = json.loads(schedule_path.read_text(encoding="utf-8"))
        schedules = declarations.get("schedules") or []
        keys = [item.get("declaration_key") for item in schedules]
        check(
            "schedule_declarations",
            len(keys) == 7 and len(set(keys)) == 7 and set(keys) == EXPECTED_KEYS,
            f"keys={keys}",
        )

    runtime_root = project / "scripts"
    plugin_root = project / "openclaw-plugins" / "personal-daily-transport"
    violations: list[str] = []
    for root in (runtime_root, plugin_root):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".mjs", ".ts", ".json", ".md"}:
                continue
            match = RUNTIME_BANNED.search(path.read_text(encoding="utf-8"))
            if match:
                violations.append(f"{path.relative_to(project)}:{match.group(0)}")
    check("excluded_features_absent", not violations, str(violations))

    if openclaw_config is not None:
        config_path = openclaw_config.expanduser().resolve(strict=False)
        fragment_path = project / "setup" / "openclaw-plugin-fragment.json"
        try:
            # Deliberately accept strict JSON only. JSON5, includes and computed
            # release-specific configuration require the installed CLI's check.
            config = json.loads(config_path.read_text(encoding="utf-8"))
            fragment = json.loads(fragment_path.read_text(encoding="utf-8"))
            if not isinstance(config, dict) or not isinstance(fragment, dict):
                raise ValueError("configuration must be a JSON object")
            expected_owner = fragment["plugins"]["entries"]["personal-daily-transport"]["config"]["ownerTelegramId"]
            if not isinstance(expected_owner, str) or not expected_owner.isdigit():
                raise ValueError("installed owner ID is missing or invalid")
        except (OSError, UnicodeError, ValueError, KeyError, TypeError):
            check(
                "openclaw_config_parse",
                False,
                "unverified: readable strict JSON objects and an installed owner ID are required; JSON5/includes are not evaluated",
            )
        else:
            check("openclaw_config_parse", True, "strict JSON parsed; static inspection only")
            plugin_id = "personal-daily-transport"
            plugins = config.get("plugins")
            if not isinstance(plugins, dict):
                plugins = {}
            entries = plugins.get("entries")
            entry = entries.get(plugin_id) if isinstance(entries, dict) else None
            if not isinstance(entry, dict):
                entry = {}
            plugin_config = entry.get("config")
            if not isinstance(plugin_config, dict):
                plugin_config = {}
            global_enabled = plugins.get("enabled", True)
            allow = plugins.get("allow")
            deny = plugins.get("deny", [])
            allow_ok = allow is None or (
                isinstance(allow, list)
                and all(isinstance(item, str) for item in allow)
                and plugin_id in allow
            )
            deny_ok = (
                isinstance(deny, list)
                and all(isinstance(item, str) for item in deny)
                and plugin_id not in deny
            )
            check(
                "openclaw_plugin_enabled",
                global_enabled is True and entry.get("enabled") is True and allow_ok and deny_ok,
                "requires an enabled entry, plugins not globally disabled, and compatible allow/deny lists",
            )
            check(
                "openclaw_plugin_owner",
                plugin_config.get("ownerTelegramId") == expected_owner,
                "configured plugin owner must exactly match the installed owner",
            )
            gateway = config.get("gateway")
            bind = gateway.get("bind") if isinstance(gateway, dict) else None
            check(
                "gateway_loopback_configured",
                bind == "loopback",
                "requires explicit gateway.bind=loopback; absent, public and unknown modes are unverified",
            )
            if _contains_include(config):
                check("openclaw_includes", False, "unverified: included configuration is not evaluated")
        backups = list(config_path.parent.glob(f"{config_path.name}.backup-*"))
        check("openclaw_backup", bool(backups), f"backups={len(backups)}")
        warnings.append(
            "Static configuration only: active plugin loading, bound network interfaces, schedules and Telegram delivery require live readback."
        )
    else:
        warnings.append("OpenClaw configuration and runtime were not checked.")

    return {
        "ok": all(item["ok"] for item in checks),
        "scope": "static-files-and-configuration",
        "runtime_verified": False,
        "checks": checks,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--openclaw-config", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = verify_installation(
        project_root=args.project_root,
        data_dir=args.data_dir,
        token_file=args.token_file,
        openclaw_config=args.openclaw_config,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
