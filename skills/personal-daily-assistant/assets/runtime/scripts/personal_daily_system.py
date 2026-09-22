#!/usr/bin/env python3
"""Append-only personal event journal with a small JSON CLI."""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = os.environ.get("PDS_TIMEZONE", "UTC")
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXT_RELATIVE = Path("context") / "active_context.json"
DEFAULT_CODEX_ACTIVITY_RELATIVE = Path("context") / "codex_activity_latest.md"
DEFAULT_SESSION_SUMMARIES_RELATIVE = Path("summaries")
RUSSIAN_MONTHS_GENITIVE = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)
ACTIVITY_GAP_QUESTION = (
    "Было что-то ещё, что не вошло в activity context (исследования в ChatGPT, "
    "переписки, 1:1 значимые, CusDev)?"
)
VIABILITY_CONTEXT_QUESTION = (
    "Что произошло? Было ли что-то между тобой и живым процессом? "
    "«Ничего» — нормальный ответ."
)
VIABILITY_PROMPT_QUESTION = (
    "Что это событие сделало с желанием жить прямо сейчас? Выбери дельту."
)
VIABILITY_REFLECTION_START_DATE = date(2026, 7, 26)
VIABILITY_REFLECTION_START_SLOT = 1
VIABILITY_REFLECTION_SLOTS = {
    "1200": 0,
    "1510": 1,
    "1800": 2,
}
VIABILITY_AFFIRMATIONS = ("Set personal affirmations in active context.",)
VIABILITY_UNDERSTANDINGS = ("Set personal understandings in active context.",)
WEEKLY_FEELING_QUESTION = (
    "Каково твоё итоговое ощущение недели: где жить хотелось больше, где меньше, "
    "и что это меняет в гипотезах на следующую неделю?"
)
VIABILITY_MARK_VALUES = {
    "−−": -2,
    "--": -2,
    "−": -1,
    "-": -1,
    "=": 0,
    "+": 1,
    "++": 2,
}
VIABILITY_LINE_PATTERN = re.compile(
    r"^(?P<description>.+?)\s+"
    r"(?P<mark>\+\+|\+|=|−−|--|−|-)"
    r"(?:\s+\((?P<context>[^()]*)\))?\s*$"
)
CORRECTABLE_EVENT_FIELDS = {
    "self_report",
    "description",
    "mediator",
    "spheres",
    "links",
    "evidence",
    "agent_annotations",
    "status",
}

SUPPORTED_EVENT_TYPES = {
    "viability_checkin",
    "idea",
    "occasion",
    "success",
    "morning_intent",
    "evening_reflection",
    "weekly_reflection",
    "focus_started",
    "focus_finished",
    "decision",
    "strategy_change",
    "content_experience",
    "correction",
    "external_sync",
}

REQUIRED_FIELDS = {
    "id",
    "occurred_at",
    "type",
    "idempotency_key",
    "source",
    "self_report",
    "description",
    "mediator",
    "spheres",
    "links",
    "evidence",
    "agent_annotations",
    "status",
}

DEFAULT_FIELDS: dict[str, Any] = {
    "source": {},
    "self_report": {},
    "description": None,
    "mediator": None,
    "spheres": [],
    "links": {},
    "evidence": [],
    "agent_annotations": [],
    "status": "captured",
}


def _viability_prompt_text(
    local_now: datetime,
    *,
    affirmations: tuple[str, ...] | list[str] | None = None,
    understandings: tuple[str, ...] | list[str] | None = None,
) -> str:
    slot_index = VIABILITY_REFLECTION_SLOTS.get(local_now.strftime("%H%M"))
    if slot_index is None:
        return VIABILITY_PROMPT_QUESTION

    active_affirmations = tuple(affirmations or VIABILITY_AFFIRMATIONS)
    active_understandings = tuple(understandings or VIABILITY_UNDERSTANDINGS)
    position = (
        (local_now.date() - VIABILITY_REFLECTION_START_DATE).days * 3
        + slot_index
        - VIABILITY_REFLECTION_START_SLOT
    )
    reflections = active_affirmations + active_understandings
    reflection_index = position % len(reflections)
    reflection = reflections[reflection_index]
    if reflection_index < len(active_affirmations):
        label = f"Аффирмация {reflection_index + 1}/{len(active_affirmations)}"
    else:
        understanding_index = reflection_index - len(active_affirmations)
        label = (
            f"Новое понимание {understanding_index + 1}/"
            f"{len(active_understandings)}"
        )
    return f"{label}:\n{reflection}\n\n{VIABILITY_PROMPT_QUESTION}"


class PersonalEventError(ValueError):
    """Raised when an event or event log violates the journal contract."""


def resolve_data_dir(value: str | Path | None = None) -> Path:
    """Resolve the absolute directory for private runtime data."""

    configured = value
    if configured is None:
        configured = os.environ.get("PDS_DATA_DIR")
    if configured is None:
        configured = (
            Path.home()
            / "Library"
            / "Application Support"
            / "OpenClaw Personal Daily Assistant"
        )
    resolved = Path(configured).expanduser()
    if not resolved.is_absolute():
        raise PersonalEventError("personal runtime data directory must be absolute")
    return resolved


def _reject_json_constant(value: str) -> None:
    raise PersonalEventError(f"non-standard JSON constant is not allowed: {value}")


def _strict_json_dumps(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PersonalEventError(f"value is not valid strict JSON: {exc}") from exc


def build_openclaw_send_command(
    response: dict[str, Any],
    *,
    target: str,
    dry_run: bool = False,
    openclaw_bin: str = "openclaw",
) -> list[str]:
    """Translate one deterministic response into an OpenClaw Telegram send."""

    _nonempty_string(target, "telegram target")
    _nonempty_string(openclaw_bin, "openclaw executable")
    text = response.get("text")
    _nonempty_string(text, "response text")
    command = [
        openclaw_bin,
        "message",
        "send",
        "--channel",
        "telegram",
        "--target",
        target,
        "--message",
        text,
        "--json",
    ]
    buttons = response.get("buttons")
    if buttons is not None:
        if not isinstance(buttons, list) or not buttons:
            raise PersonalEventError("response buttons must be a nonempty array")
        presentation_buttons: list[dict[str, str]] = []
        for index, button in enumerate(buttons):
            if not isinstance(button, dict):
                raise PersonalEventError(f"response button {index} must be an object")
            label = button.get("text")
            callback_data = button.get("callback_data")
            _nonempty_string(label, f"response button {index}.text")
            _nonempty_string(
                callback_data,
                f"response button {index}.callback_data",
            )
            if len(callback_data.encode("utf-8")) >= 64:
                raise PersonalEventError(
                    f"callback data is too long: {callback_data}"
                )
            presentation_buttons.append(
                {"label": label, "value": callback_data}
            )
        presentation = {
            "blocks": [
                {
                    "type": "buttons",
                    "buttons": presentation_buttons,
                }
            ]
        }
        command.extend(["--presentation", _strict_json_dumps(presentation)])
    if dry_run:
        command.append("--dry-run")
    return command


def _run_openclaw_send(command: list[str]) -> tuple[bool, Any, str]:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    raw_output = result.stdout.strip()
    transport: Any = raw_output
    if raw_output:
        try:
            transport = json.loads(
                raw_output,
                parse_constant=_reject_json_constant,
            )
        except json.JSONDecodeError:
            pass
    error = result.stderr.strip() or raw_output or "unknown error"
    return result.returncode == 0, transport, error


def send_openclaw_response(
    response: dict[str, Any],
    *,
    target: str,
    dry_run: bool = False,
    openclaw_bin: str = "openclaw",
) -> dict[str, Any]:
    command = build_openclaw_send_command(
        response,
        target=target,
        dry_run=dry_run,
        openclaw_bin=openclaw_bin,
    )
    succeeded, transport, error = _run_openclaw_send(command)
    if not succeeded:
        raise PersonalEventError(f"OpenClaw send failed: {error}")
    return {
        "sent": not dry_run,
        "dry_run": dry_run,
        "mode": "text",
        "transport": transport,
    }


def _parse_aware_datetime(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise PersonalEventError("occurred_at must be a nonempty ISO date-time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PersonalEventError(f"occurred_at is not valid ISO date-time: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PersonalEventError("occurred_at must include a timezone offset")
    return parsed


def _instant_precedes(left: datetime, right: datetime) -> bool:
    return left.astimezone(timezone.utc) < right.astimezone(timezone.utc)


def _nonempty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PersonalEventError(f"{field} must be a nonempty string")


def _report_date(
    value: date | datetime | str | None,
    timezone: ZoneInfo,
) -> date:
    if value is None:
        return datetime.now(timezone).date()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise PersonalEventError("report datetime must include a timezone offset")
        return value.astimezone(timezone).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise PersonalEventError(
                f"report date is not valid ISO date: {value}"
            ) from exc
    raise PersonalEventError("report date must be YYYY-MM-DD")


def _iso_week_label(value: date) -> str:
    iso_year, iso_week, _ = value.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _iso_week_date(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-W\d{2}", value):
        raise PersonalEventError(
            "weekly_reflection self_report.week_label must be a valid ISO week "
            "(YYYY-Www)"
        )
    year = int(value[:4])
    week = int(value[-2:])
    try:
        return date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise PersonalEventError(
            "weekly_reflection self_report.week_label must be a valid ISO week "
            "(YYYY-Www)"
        ) from exc


def _report_timezone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except KeyError as exc:
        raise PersonalEventError(f"unknown timezone: {timezone}") from exc


def resolve_day_window(
    target_date: date | datetime | str | None = None,
    *,
    timezone: str = DEFAULT_TIMEZONE,
) -> tuple[datetime, datetime]:
    local_timezone = _report_timezone(timezone)
    local_date = _report_date(target_date, local_timezone)
    return (
        datetime.combine(local_date, time.min, tzinfo=local_timezone),
        datetime.combine(
            local_date + timedelta(days=1),
            time.min,
            tzinfo=local_timezone,
        ),
    )


def resolve_iso_week_window(
    target_date: date | datetime | str | None = None,
    *,
    timezone: str = DEFAULT_TIMEZONE,
) -> tuple[datetime, datetime]:
    local_timezone = _report_timezone(timezone)
    local_date = _report_date(target_date, local_timezone)
    week_start = local_date - timedelta(days=local_date.weekday())
    return (
        datetime.combine(week_start, time.min, tzinfo=local_timezone),
        datetime.combine(
            week_start + timedelta(days=7),
            time.min,
            tzinfo=local_timezone,
        ),
    )


EPISODE_MERGE_WINDOW_SECONDS = 120


def _normalized_episode_description(event: dict[str, Any]) -> str:
    description = event.get("description")
    if not isinstance(description, str):
        return ""
    return " ".join(description.casefold().split()).strip(" .,:;!—–-")


def _event_source_channel(event: dict[str, Any]) -> str | None:
    source = event.get("source")
    if not isinstance(source, dict):
        return None
    channel = source.get("channel")
    return channel if isinstance(channel, str) and channel else None


def _same_report_episode(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    left_at = _parse_aware_datetime(left["occurred_at"])
    right_at = _parse_aware_datetime(right["occurred_at"])
    if (
        abs((right_at - left_at).total_seconds())
        > EPISODE_MERGE_WINDOW_SECONDS
    ):
        return False

    left_description = _normalized_episode_description(left)
    right_description = _normalized_episode_description(right)
    if left_description and left_description == right_description:
        return True

    if left.get("type") != "viability_checkin" or right.get(
        "type"
    ) != "viability_checkin":
        return False
    if left.get("self_report", {}).get("delta") != right.get(
        "self_report", {}
    ).get("delta"):
        return False

    left_channel = _event_source_channel(left)
    right_channel = _event_source_channel(right)
    if not left_channel or not right_channel or left_channel == right_channel:
        return False

    left_spheres = {
        item for item in left.get("spheres", []) if isinstance(item, str)
    }
    right_spheres = {
        item for item in right.get("spheres", []) if isinstance(item, str)
    }
    return bool(left_spheres.intersection(right_spheres))


def _report_event_score(event: dict[str, Any]) -> tuple[int, int, int]:
    self_report = event.get("self_report", {})
    has_delta = int(
        event.get("type") == "viability_checkin"
        and isinstance(self_report.get("delta"), int)
    )
    has_context = int(self_report.get("context_status") == "provided")
    description = event.get("description")
    description_length = len(description) if isinstance(description, str) else 0
    return has_delta, has_context, description_length


def _deduplicate_report_episodes(
    events: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    for event in sorted(events, key=lambda item: item["occurred_at"]):
        matching_group = next(
            (
                group
                for group in groups
                if any(_same_report_episode(event, member) for member in group)
            ),
            None,
        )
        if matching_group is None:
            groups.append([event])
        else:
            matching_group.append(event)
    representatives = [
        max(group, key=_report_event_score)
        for group in groups
    ]
    return sorted(representatives, key=lambda item: item["occurred_at"])


def _viability_total_reaction(total: int) -> str | None:
    if total >= 10:
        return (
            "Сильный итог: это уже не один удачный момент, а целая серия "
            "эпизодов, в которых жить хотелось больше."
        )
    if total >= 5:
        return (
            "Заметно живой день: положительная дельта сложилась из нескольких "
            "эпизодов, а не одного всплеска."
        )
    if total > 0:
        return "День завершился в плюсе: живого в нём прибавилось."
    return None


def _task_is_completed(choice: dict[str, Any]) -> bool:
    return choice.get("status", "active") == "completed"


def _ordered_task_choices(
    choices: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        choices,
        key=lambda choice: (_task_is_completed(choice), choice["number"]),
    )


def _parse_morning_choice_numbers(text: str) -> list[int] | None:
    normalized = text.casefold().strip()
    numbers = [int(match.group(0)) for match in re.finditer(r"\d+", normalized)]
    if not numbers:
        return None
    remainder = re.sub(r"\d+", " ", normalized)
    remainder = re.sub(
        r"\b(?:и|номер|номера|номером|задача|задачи|задачу|выбираю)\b",
        " ",
        remainder,
    )
    if remainder.strip(" \t\r\n,;.:+") != "":
        return None
    return list(dict.fromkeys(numbers))


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        temp_fd = os.open(temp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def _summary_section(
    markdown: str,
    names: tuple[str, ...],
    *,
    level: int,
) -> str:
    lines = markdown.splitlines()
    wanted = {name.casefold() for name in names}
    start: int | None = None
    for index, line in enumerate(lines):
        match = re.fullmatch(r"(#{1,6})\s+(.+?)\s*", line)
        if match is None:
            continue
        heading_level = len(match.group(1))
        heading = match.group(2).strip().casefold()
        if start is None:
            if heading_level == level and heading in wanted:
                start = index + 1
            continue
        if heading_level <= level:
            return "\n".join(lines[start:index]).strip()
    if start is None:
        return ""
    return "\n".join(lines[start:]).strip()


def _plain_summary_text(value: str) -> str:
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
    cleaned = cleaned.replace("`", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _summary_list_items(section: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        match = re.match(r"^(?:\d+\.\s+|-\s+)(.+)$", line)
        if match is not None:
            if current:
                items.append(_plain_summary_text(" ".join(current)))
            current = [match.group(1)]
            continue
        if current and line and not line.startswith("#"):
            current.append(line)
    if current:
        items.append(_plain_summary_text(" ".join(current)))
    return [item for item in items if item]


def _summary_questions(section: str) -> dict[str, str]:
    questions: dict[str, str] = {}
    for raw_line in section.splitlines():
        line = raw_line.strip()
        match = re.match(
            r"^(?:-\s*)?\*\*(?:На\s+)?(утро|вечер):\*\*\s*(.+)$",
            line,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        key = "morning" if match.group(1).casefold() == "утро" else "evening"
        questions[key] = _plain_summary_text(match.group(2))
    return questions


def _latest_summary_path(repo_root: Path) -> tuple[date, Path] | None:
    configured = os.environ.get("PDS_SUMMARIES_DIR", "").strip()
    summaries_root = Path(configured).expanduser() if configured else repo_root / DEFAULT_SESSION_SUMMARIES_RELATIVE
    if configured and not summaries_root.is_absolute():
        raise ValueError("PDS_SUMMARIES_DIR must be an absolute directory")
    candidates: list[tuple[date, int, str, Path]] = []
    for path in summaries_root.glob("*саммари*.md"):
        match = re.match(r"^(\d{4}-\d{2}-\d{2})\s+саммари", path.name)
        if match is None:
            continue
        try:
            summary_date = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        candidates.append(
            (summary_date, path.stat().st_mtime_ns, path.name, path)
        )
    if not candidates:
        return None
    summary_date, _, _, path = max(candidates)
    return summary_date, path


def _refresh_context_markdown(
    path: Path,
    *,
    summary_date: date,
    active_understanding: str,
    questions: dict[str, str],
    warning_patterns: list[str],
) -> None:
    if not path.exists():
        return
    markdown = path.read_text(encoding="utf-8")
    source_line = f"Источник саммари: **{summary_date.isoformat()}**."
    if re.search(r"^Источник саммари: .+$", markdown, flags=re.MULTILINE):
        markdown = re.sub(
            r"^Источник саммари: .+$",
            source_line,
            markdown,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        markdown = re.sub(
            r"(Статус капсулы:.*?\n)",
            rf"\1\n{source_line}\n",
            markdown,
            count=1,
        )
    markdown = re.sub(
        r"(## Главный критерий\n\n).*?(\n\nL1:)",
        rf"\1{active_understanding}\2",
        markdown,
        count=1,
        flags=re.DOTALL,
    )
    markdown = re.sub(
        r"(## Вопросы 1:1\n\n).*?(?=\n## Контрольная грабля)",
        (
            rf"\1Утро: {questions['morning']}\n\n"
            rf"Вечер: {questions['evening']}\n"
        ),
        markdown,
        count=1,
        flags=re.DOTALL,
    )
    pattern_lines = "\n".join(f"- {item}" for item in warning_patterns)
    markdown = re.sub(
        r"(## Контрольная грабля\n\n).*?(?=\n## Утверждённый фокус)",
        rf"\1{pattern_lines}\n",
        markdown,
        count=1,
        flags=re.DOTALL,
    )
    _atomic_write_text(path, markdown.rstrip() + "\n")


def refresh_active_context_from_latest_summary(
    *,
    repo_root: str | Path | None = None,
    context_path: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else DEFAULT_REPO_ROOT
    resolved_context_path = (
        Path(context_path)
        if context_path is not None
        else root / DEFAULT_CONTEXT_RELATIVE
    )
    latest = _latest_summary_path(root)
    if latest is None:
        return {"status": "unchanged", "reason": "no_summary"}
    summary_date, summary_path = latest
    raw_summary = summary_path.read_text(encoding="utf-8")
    summary_sha256 = hashlib.sha256(raw_summary.encode("utf-8")).hexdigest()
    context = json.loads(
        resolved_context_path.read_text(encoding="utf-8"),
        parse_constant=_reject_json_constant,
    )
    existing_source = context.get("source_summary")
    if (
        isinstance(existing_source, dict)
        and existing_source.get("sha256") == summary_sha256
    ):
        return {
            "status": "unchanged",
            "summary_date": summary_date.isoformat(),
            "summary_path": str(summary_path),
        }

    understandings_section = _summary_section(
        raw_summary,
        ("Новые понимания",),
        level=2,
    )
    facts_section = _summary_section(
        understandings_section,
        ("Факты",),
        level=3,
    )
    mechanisms_section = _summary_section(
        understandings_section,
        ("Механизмы",),
        level=3,
    )
    affirmations_section = _summary_section(
        raw_summary,
        ("Аффирмации", "10 аффирмаций"),
        level=2,
    )
    questions_section = _summary_section(
        raw_summary,
        ("Вопросы", "Вопросы на день"),
        level=2,
    )
    patterns_section = _summary_section(
        raw_summary,
        ("Повторяющиеся неконструктивные паттерны",),
        level=2,
    )
    affirmations = _summary_list_items(affirmations_section)
    understandings = [
        *_summary_list_items(facts_section),
        *_summary_list_items(mechanisms_section),
    ]
    questions = _summary_questions(questions_section)
    warning_patterns = _summary_list_items(patterns_section)
    bold_facts = [
        _plain_summary_text(item)
        for item in re.findall(r"\*\*(.+?)\*\*", facts_section, flags=re.DOTALL)
        if _plain_summary_text(item)
    ]
    active_understanding = (
        bold_facts[-1]
        if bold_facts
        else (understandings[0] if understandings else "")
    )
    missing = [
        name
        for name, value in (
            ("active_understanding", active_understanding),
            ("affirmations", affirmations),
            ("understandings", understandings),
            ("morning_question", questions.get("morning")),
            ("evening_question", questions.get("evening")),
            ("warning_patterns", warning_patterns),
        )
        if not value
    ]
    if missing:
        return {
            "status": "ignored",
            "summary_date": summary_date.isoformat(),
            "summary_path": str(summary_path),
            "reason": "missing_sections",
            "missing": missing,
        }

    applied_at = now or datetime.now(ZoneInfo(DEFAULT_TIMEZONE))
    if applied_at.tzinfo is None or applied_at.utcoffset() is None:
        raise PersonalEventError("summary refresh time must include timezone")
    try:
        relative_summary_path = summary_path.relative_to(root)
    except ValueError:
        relative_summary_path = summary_path
    context["active_understanding"] = active_understanding
    context["questions"] = questions
    context["warning_patterns"] = warning_patterns
    context["viability_reflections"] = {
        "affirmations": affirmations,
        "understandings": understandings,
    }
    context["source_summary"] = {
        "date": summary_date.isoformat(),
        "path": str(relative_summary_path),
        "sha256": summary_sha256,
        "applied_at": applied_at.astimezone(
            ZoneInfo(DEFAULT_TIMEZONE)
        ).isoformat(timespec="seconds"),
    }
    _atomic_write_text(
        resolved_context_path,
        _strict_json_dumps(context) + "\n",
    )
    _refresh_context_markdown(
        resolved_context_path.with_suffix(".md"),
        summary_date=summary_date,
        active_understanding=active_understanding,
        questions=questions,
        warning_patterns=warning_patterns,
    )
    return {
        "status": "updated",
        "summary_date": summary_date.isoformat(),
        "summary_path": str(summary_path),
        "affirmations": len(affirmations),
        "understandings": len(understandings),
        "warning_patterns": len(warning_patterns),
    }


def _refresh_summary_for_dispatch(
    workflow: str,
    *,
    phase: str,
    dry_run: bool,
    repo_root: Path,
    context_path: Path,
    now: datetime,
) -> dict[str, Any] | None:
    if dry_run:
        return None
    should_refresh = (
        workflow == "morning" and phase == "before"
    ) or (
        workflow == "evening" and phase == "after_prepare"
    )
    if not should_refresh:
        return None
    return refresh_active_context_from_latest_summary(
        repo_root=repo_root,
        context_path=context_path,
        now=now,
    )


class PersonalEventStore:
    """Read, validate, and append personal events without rewriting history."""

    def __init__(
        self,
        repo_root: str | Path | None = None,
        events_path: str | Path | None = None,
        *,
        data_dir: str | Path | None = None,
        timezone: str = DEFAULT_TIMEZONE,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root is not None else DEFAULT_REPO_ROOT
        self.data_dir = (
            Path(events_path).expanduser().parent
            if data_dir is None
            and os.environ.get("PDS_DATA_DIR") is None
            and events_path is not None
            else resolve_data_dir(data_dir)
        )
        self.events_path = (
            Path(events_path).expanduser()
            if events_path is not None
            else self.data_dir / "events.jsonl"
        )
        self.lock_path = self.events_path.parent / ".events.lock"
        try:
            self.timezone = ZoneInfo(timezone)
        except KeyError as exc:
            raise PersonalEventError(f"unknown timezone: {timezone}") from exc

    def _read_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []

        events: list[dict[str, Any]] = []
        with self.events_path.open("r", encoding="utf-8") as handle:
            for line_number, raw in enumerate(handle, start=1):
                if not raw.strip():
                    continue
                try:
                    value = json.loads(raw, parse_constant=_reject_json_constant)
                except PersonalEventError as exc:
                    raise PersonalEventError(
                        f"Invalid JSON at {self.events_path}:{line_number}: {exc}"
                    ) from exc
                except json.JSONDecodeError as exc:
                    raise PersonalEventError(
                        f"Invalid JSON at {self.events_path}:{line_number}: {exc.msg}"
                    ) from exc
                if not isinstance(value, dict):
                    raise PersonalEventError(
                        f"Event at {self.events_path}:{line_number} must be an object"
                    )
                events.append(value)
        return events

    def load_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []

        lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_fd, "a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_SH)
            try:
                events = self._read_events()
                self._validate_events(events)
                return events
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _validate_weekly_idempotency_key(
        self,
        event: dict[str, Any],
    ) -> None:
        idempotency_key = event.get("idempotency_key")
        if event.get("type") != "weekly_reflection":
            if isinstance(idempotency_key, str) and idempotency_key.startswith(
                "weekly_reflection:"
            ):
                raise PersonalEventError(
                    "weekly_reflection:* idempotency keys are reserved for "
                    "weekly_reflection events"
                )
            return
        self_report = event.get("self_report")
        if not isinstance(self_report, dict):
            raise PersonalEventError(
                "weekly_reflection self_report must be an object"
            )
        week_label = self_report.get("week_label")
        _iso_week_date(week_label)
        expected_key = f"weekly_reflection:{week_label}"
        if idempotency_key != expected_key:
            raise PersonalEventError(
                "weekly_reflection idempotency_key must be "
                f"{expected_key}"
            )

    def _validate_type_specific(self, event: dict[str, Any]) -> None:
        self._validate_weekly_idempotency_key(event)
        if event["type"] == "viability_checkin":
            delta = event["self_report"].get("delta")
            if type(delta) is not int or not -2 <= delta <= 2:
                raise PersonalEventError(
                    "viability_checkin self_report.delta must be an integer "
                    "from -2 to 2"
                )
        if event["type"] == "weekly_reflection":
            _nonempty_string(
                event["self_report"].get("final_feeling"),
                "weekly_reflection self_report.final_feeling",
            )

    def validate_event(
        self,
        event: dict[str, Any],
        existing_events: Iterable[dict[str, Any]] = (),
    ) -> None:
        if not isinstance(event, dict):
            raise PersonalEventError("event must be an object")

        missing = REQUIRED_FIELDS - set(event)
        if missing:
            raise PersonalEventError(f"event missing fields: {sorted(missing)}")

        _nonempty_string(event["id"], "id")
        _parse_aware_datetime(event["occurred_at"])
        _nonempty_string(event["type"], "type")
        _nonempty_string(event["idempotency_key"], "idempotency_key")
        _nonempty_string(event["status"], "status")

        if event["type"] not in SUPPORTED_EVENT_TYPES:
            raise PersonalEventError(f"unsupported event type: {event['type']}")
        if not isinstance(event["source"], dict):
            raise PersonalEventError("source must be an object")
        if not isinstance(event["self_report"], dict):
            raise PersonalEventError("self_report must be an object")
        if event["description"] is not None and not isinstance(event["description"], str):
            raise PersonalEventError("description must be a string or null")
        if event["mediator"] is not None and not isinstance(
            event["mediator"], (str, dict)
        ):
            raise PersonalEventError("mediator must be a string, object, or null")
        if not isinstance(event["spheres"], list):
            raise PersonalEventError("spheres must be an array")
        if not all(isinstance(sphere, str) for sphere in event["spheres"]):
            raise PersonalEventError("spheres items must be strings")
        if not isinstance(event["links"], dict):
            raise PersonalEventError("links must be an object")
        if not isinstance(event["evidence"], list):
            raise PersonalEventError("evidence must be an array")
        if not isinstance(event["agent_annotations"], list):
            raise PersonalEventError("agent_annotations must be an array")

        self._validate_type_specific(event)
        existing = list(existing_events)
        existing_ids = {item.get("id") for item in existing}
        if event["id"] in existing_ids:
            raise PersonalEventError(f"duplicate event id: {event['id']}")

        if event["type"] == "correction":
            target = event.get("supersedes_event_id")
            if not isinstance(target, str) or target not in existing_ids:
                raise PersonalEventError(
                    "correction supersedes_event_id must refer to an existing event"
                )
            corrected_fields = event.get("corrected_fields")
            if (
                not isinstance(corrected_fields, list)
                or not corrected_fields
                or not all(
                    isinstance(field, str)
                    and field in CORRECTABLE_EVENT_FIELDS
                    for field in corrected_fields
                )
            ):
                raise PersonalEventError(
                    "correction corrected_fields must name corrected event fields"
                )
            missing_values = [
                field for field in corrected_fields if field not in event
            ]
            if missing_values:
                raise PersonalEventError(
                    "correction corrected fields must be present in the event: "
                    f"{missing_values}"
                )
            self._materialize_validated_events([*existing, event])

    def _materialize_validated_events(
        self,
        raw_events: Iterable[dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        materialized: dict[str, dict[str, Any]] = {}
        roots: dict[str, str] = {}
        order: list[str] = []
        for event in raw_events:
            if event["type"] != "correction":
                root_id = event["id"]
                roots[root_id] = root_id
                materialized[root_id] = copy.deepcopy(event)
                order.append(root_id)
                continue

            target_id = event["supersedes_event_id"]
            root_id = roots.get(target_id)
            if root_id is None or root_id not in materialized:
                raise PersonalEventError(
                    f"correction target is not materializable: {target_id}"
                )
            current = materialized[root_id]
            for field in event["corrected_fields"]:
                if field not in event:
                    raise PersonalEventError(
                        "correction corrected fields must be present in the event: "
                        f"{field}"
                    )
                current[field] = copy.deepcopy(event[field])
            current["last_correction_id"] = event["id"]
            history = current.setdefault("correction_history", [])
            history.append(event["id"])
            roots[event["id"]] = root_id
        for root_id in order:
            self._validate_type_specific(materialized[root_id])
        return materialized, order

    def _validate_events(self, events: Iterable[dict[str, Any]]) -> None:
        accepted: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for index, event in enumerate(events, start=1):
            try:
                self.validate_event(event, accepted)
            except PersonalEventError as exc:
                raise PersonalEventError(
                    f"Invalid event at {self.events_path}:{index}: {exc}"
                ) from exc
            key = event["idempotency_key"]
            if key in seen_keys:
                raise PersonalEventError(
                    f"Invalid event at {self.events_path}:{index}: "
                    f"duplicate idempotency_key: {key}"
                )
            seen_keys.add(key)
            accepted.append(event)

    def validate_log(self) -> int:
        return len(self.load_events())

    def load_materialized_events(self) -> list[dict[str, Any]]:
        raw_events = self.load_events()
        materialized, order = self._materialize_validated_events(raw_events)
        return [copy.deepcopy(materialized[root_id]) for root_id in order]

    def _new_event_id(self, occurred_at: datetime) -> str:
        local_time = occurred_at.astimezone(self.timezone)
        timestamp = local_time.strftime("%Y%m%dT%H%M%S%f")
        return f"evt_{timestamp}_{uuid.uuid4().hex[:8]}"

    def _normalize_event(self, event: dict[str, Any]) -> dict[str, Any]:
        if event.get("type") == "correction":
            supplied_fields = event.get("corrected_fields")
            if isinstance(supplied_fields, list):
                missing_values = [
                    field for field in supplied_fields if field not in event
                ]
                if missing_values:
                    raise PersonalEventError(
                        "correction corrected fields must be present in the event: "
                        f"{missing_values}"
                    )
        normalized = copy.deepcopy(DEFAULT_FIELDS)
        normalized.update(copy.deepcopy(event))
        if event.get("type") == "correction":
            corrected_fields = event.get("corrected_fields")
            if corrected_fields is None:
                corrected_fields = sorted(
                    field
                    for field in CORRECTABLE_EVENT_FIELDS
                    if field in event
                )
            normalized["corrected_fields"] = copy.deepcopy(corrected_fields)

        occurred_at = normalized.get("occurred_at")
        if occurred_at is None:
            now = datetime.now(self.timezone)
            normalized["occurred_at"] = now.isoformat(timespec="seconds")
        else:
            now = _parse_aware_datetime(occurred_at)

        if not normalized.get("id"):
            normalized["id"] = self._new_event_id(now)
        return normalized

    def append_event(self, event: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(event, dict):
            raise PersonalEventError("event must be an object")
        idempotency_key = event.get("idempotency_key")
        _nonempty_string(idempotency_key, "idempotency_key")
        self._validate_weekly_idempotency_key(event)

        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_fd, "a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                existing = self._read_events()
                self._validate_events(existing)
                for stored in existing:
                    if stored["idempotency_key"] == idempotency_key:
                        return copy.deepcopy(stored)

                normalized = self._normalize_event(event)
                self.validate_event(normalized, existing)
                serialized = _strict_json_dumps(normalized) + "\n"
                creating_events_file = not self.events_path.exists()
                event_fd = os.open(
                    self.events_path,
                    os.O_CREAT | os.O_APPEND | os.O_WRONLY,
                    0o600,
                )
                with os.fdopen(event_fd, "a", encoding="utf-8") as event_handle:
                    event_handle.write(serialized)
                    event_handle.flush()
                    os.fsync(event_handle.fileno())
                if creating_events_file:
                    directory_fd = os.open(self.events_path.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                return copy.deepcopy(normalized)
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


class PersonalReportService:
    """Render deterministic reports from one Lisbon calendar window."""

    def __init__(
        self,
        repo_root: str | Path | None = None,
        events_path: str | Path | None = None,
        *,
        data_dir: str | Path | None = None,
        reports_root: str | Path | None = None,
        timezone: str = DEFAULT_TIMEZONE,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root is not None else DEFAULT_REPO_ROOT
        self.store = PersonalEventStore(
            repo_root=self.repo_root,
            events_path=events_path,
            data_dir=data_dir,
            timezone=timezone,
        )
        self.timezone = self.store.timezone
        self.timezone_name = timezone
        self.reports_root = (
            Path(reports_root)
            if reports_root is not None
            else self.store.data_dir / "reports"
        )

    def _events_in_window(
        self,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for event in self.store.load_materialized_events():
            occurred_at = _parse_aware_datetime(event["occurred_at"]).astimezone(
                self.timezone
            )
            if start <= occurred_at < end:
                events.append(event)
        return events

    def _activity_lines(
        self,
        codex_activity_path: str | Path | None,
        start: datetime,
        end: datetime,
    ) -> list[str]:
        if codex_activity_path is None:
            return []
        path = Path(codex_activity_path)
        try:
            manifest = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return ["- activity context недоступен; отчёт собран fail-soft."]

        signals: list[str] = []
        pattern = re.compile(
            r"^- \*\*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) "
            r"\[[^\]]+\]\*\* (.+)$"
        )
        for line in manifest.splitlines():
            match = pattern.match(line.strip())
            if match is None:
                continue
            try:
                local_time = datetime.strptime(
                    match.group(1),
                    "%Y-%m-%d %H:%M",
                ).replace(tzinfo=self.timezone)
            except ValueError:
                continue
            if start <= local_time < end:
                signals.append(line.strip()[2:].strip())
            if len(signals) == 3:
                break
        return [
            f"- {signal} — не подтверждение результата."
            for signal in signals
        ]

    @staticmethod
    def _mediator_label(mediator: Any) -> str | None:
        if isinstance(mediator, str):
            return mediator if mediator.strip() else None
        if isinstance(mediator, dict) and mediator:
            return json.dumps(
                mediator,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        return None

    @staticmethod
    def _episodes(count: int) -> str:
        if count % 10 == 1 and count % 100 != 11:
            return f"{count} эпизод"
        if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
            return f"{count} эпизода"
        return f"{count} эпизодов"

    @staticmethod
    def _times(count: int) -> str:
        if count % 10 == 1 and count % 100 != 11:
            return f"{count} раз"
        if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
            return f"{count} раза"
        return f"{count} раз"

    def _event_fact(
        self,
        event: dict[str, Any],
        *,
        time_only: bool = False,
    ) -> str:
        occurred_at = _parse_aware_datetime(event["occurred_at"]).astimezone(
            self.timezone
        )
        description = event.get("description")
        normalized_description = (
            " ".join(description.split())
            if isinstance(description, str) and description.strip()
            else None
        )
        if time_only:
            label = normalized_description or event["type"]
        else:
            label = event["type"]
            if normalized_description is not None:
                label += f": {normalized_description}"
        if event["type"] == "viability_checkin":
            label += f" ({event['self_report']['delta']:+d})"
        timestamp_format = "%H:%M" if time_only else "%Y-%m-%d %H:%M"
        return f"- {occurred_at.strftime(timestamp_format)} — {label}."

    @staticmethod
    def _is_context_bearing(event: dict[str, Any]) -> bool:
        return (
            event.get("type") == "viability_checkin"
            and event.get("self_report", {}).get("context_status")
            in {"provided", "none"}
        )

    def _context_fact(self, event: dict[str, Any]) -> str:
        occurred_at = _parse_aware_datetime(event["occurred_at"]).astimezone(
            self.timezone
        )
        self_report = event.get("self_report", {})
        context_status = self_report.get("context_status")
        context = self_report.get("context")
        description = event.get("description")
        if (
            context_status == "provided"
            and isinstance(context, str)
            and context.strip()
        ):
            detail = " ".join(context.split())
        elif context_status == "none":
            detail = "ничего (контекст явно отмечен)"
        elif isinstance(description, str) and description.strip():
            detail = " ".join(description.split())
        else:
            detail = "описание контекста не записано"
        mediator = self._mediator_label(event.get("mediator"))
        mediator_suffix = (
            f"; посредник: «{mediator}»" if mediator is not None else ""
        )
        return (
            f"- {occurred_at.strftime('%Y-%m-%d %H:%M')} — "
            f"сырьё о контексте: {detail}{mediator_suffix}; "
            f"дельта {self_report['delta']:+d}."
        )

    @staticmethod
    def _viability_distribution(
        events: Iterable[dict[str, Any]],
    ) -> dict[int, int]:
        distribution = {delta: 0 for delta in range(-2, 3)}
        for event in events:
            if event["type"] == "viability_checkin":
                distribution[event["self_report"]["delta"]] += 1
        return distribution

    def _report_header(
        self,
        *,
        title: str,
        start: datetime,
        end: datetime,
        events: list[dict[str, Any]],
        codex_activity_path: str | Path | None,
    ) -> list[str]:
        distribution = self._viability_distribution(events)
        distribution_text = "; ".join(
            f"{delta}: {distribution[delta]}" for delta in range(-2, 3)
        )
        lines = [
            f"# {title}",
            "",
            (
                f"- Окно {self.timezone_name}: {start.isoformat()} → "
                f"{end.isoformat()} (конец не включён)."
            ),
            f"- Распределение самооценки жизнеспособности: {distribution_text}.",
        ]
        if not any(distribution.values()):
            lines.append("- самооценка не записана.")
        activity_lines = self._activity_lines(
            codex_activity_path,
            start,
            end,
        )
        if activity_lines:
            lines.extend(
                [
                    "",
                    "### Codex activity: дополнительные сигналы",
                    "",
                    *activity_lines,
                ]
            )
        return lines

    @staticmethod
    def _append_section(
        lines: list[str],
        heading: str,
        items: Iterable[str],
        *,
        empty: str = "Недостаточно данных",
    ) -> None:
        values = list(items)
        lines.extend(["", heading, ""])
        lines.extend(values or [empty])

    def _render_evening(
        self,
        *,
        title: str,
        start: datetime,
        end: datetime,
        events: list[dict[str, Any]],
        codex_activity_path: str | Path | None,
    ) -> str:
        del start, end, codex_activity_path
        lines = [title]
        events = _deduplicate_report_episodes(events)
        facts = [
            self._event_fact(event, time_only=True)
            for event in events
            if event["type"] not in {"weekly_reflection", "external_sync"}
        ]
        lines.extend(["", *(facts or ["Подтверждённых событий пока нет."])])
        text = "\n".join(lines).rstrip().replace(
            ACTIVITY_GAP_QUESTION,
            "[повтор вопроса activity context опущен]",
        )
        return f"{text}\n\n{ACTIVITY_GAP_QUESTION}\n"

    def _weekly_reflection(
        self,
        week_label: str,
    ) -> dict[str, Any] | None:
        for event in reversed(self.store.load_materialized_events()):
            if (
                event.get("type") == "weekly_reflection"
                and event.get("self_report", {}).get("week_label")
                == week_label
            ):
                return event
        return None

    def _weekly_patterns(
        self,
        events: Iterable[dict[str, Any]],
    ) -> tuple[
        dict[tuple[str, str], int],
        dict[tuple[str, str], set[date]],
    ]:
        counts: dict[tuple[str, str], int] = {}
        dates: dict[tuple[str, str], set[date]] = {}
        for event in events:
            if event.get("type") != "viability_checkin":
                continue
            candidates: list[tuple[str, str]] = []
            mediator = self._mediator_label(event.get("mediator"))
            if mediator is not None:
                candidates.append(("Посредник", " ".join(mediator.split())))
            self_report = event.get("self_report", {})
            context = self_report.get("context")
            if (
                self_report.get("context_status") == "provided"
                and isinstance(context, str)
                and context.strip()
            ):
                candidates.append(("Контекст", " ".join(context.split())))
            for value in (event.get("description"), context):
                if not isinstance(value, str) or not value.strip():
                    continue
                for match in re.finditer(
                    r"\b(?:поставил(?:а|и)?|ставил(?:а|и)?|поставлено)\s+"
                    r"(?P<label>[^.!?;\n]{1,120}?)\s+перед\s+духом\b",
                    value,
                    flags=re.IGNORECASE,
                ):
                    label = " ".join(match.group("label").split()).strip(
                        " «»\"'()[]—–-,:"
                    )
                    if label:
                        candidates.append(("Посредник", label))
            local_date = _parse_aware_datetime(
                event["occurred_at"]
            ).astimezone(self.timezone).date()
            for candidate in dict.fromkeys(candidates):
                counts[candidate] = counts.get(candidate, 0) + 1
                dates.setdefault(candidate, set()).add(local_date)
        return counts, dates

    def _render_weekly(
        self,
        *,
        title: str,
        start: datetime,
        end: datetime,
        events: list[dict[str, Any]],
        codex_activity_path: str | Path | None,
        reflection: dict[str, Any] | None,
    ) -> str:
        del start, end, codex_activity_path, reflection
        viability_sum = sum(
            event["self_report"]["delta"]
            for event in events
            if event["type"] == "viability_checkin"
        )
        viability_sum_text = f"{viability_sum:+d}" if viability_sum else "0"

        def normalized_description(event: dict[str, Any]) -> str | None:
            description = event.get("description")
            if not isinstance(description, str) or not description.strip():
                return None
            normalized = " ".join(description.split()).rstrip(".")
            return re.sub(
                r"^успех\s*:\s*",
                "",
                normalized,
                flags=re.IGNORECASE,
            )

        positive_description_keys = {
            description.casefold()
            for event in events
            if event.get("type") == "viability_checkin"
            and event.get("self_report", {}).get("delta", 0) > 0
            and (description := normalized_description(event)) is not None
        }
        successes: list[str] = []
        explicit_success_keys: set[str] = set()
        for event in events:
            description = normalized_description(event)
            if event.get("type") == "viability_checkin":
                delta = event.get("self_report", {}).get("delta", 0)
                if delta <= 0:
                    continue
                label = description or "Положительный срез ЖС"
                successes.append(f"{label} ({'++' if delta == 2 else '+'})")
                continue
            if event.get("type") not in {"success", "focus_finished"}:
                continue
            if description is None:
                continue
            key = description.casefold()
            if key in positive_description_keys or key in explicit_success_keys:
                continue
            explicit_success_keys.add(key)
            successes.append(description)
        if successes:
            successes_text = "; ".join(successes) + "."
        else:
            successes_text = "явных записей об успехах пока нет."

        pattern_counts, _ = self._weekly_patterns(events)
        placements = [
            (label, count)
            for (kind, label), count in pattern_counts.items()
            if kind == "Посредник"
        ]
        if placements:
            placements_text = "; ".join(
                f"«{label}» — {self._times(count)}"
                for label, count in placements
            )
            placements_text += "."
        else:
            placements_text = "явных записей пока нет."
        patterns = sorted(
            (
                (label, count)
                for (kind, label), count in pattern_counts.items()
                if kind == "Посредник" and count >= 2
            ),
            key=lambda item: (-item[1], item[0].casefold()),
        )
        if patterns:
            patterns_text = "; ".join(
                f"«{label}» — {self._times(count)}"
                for label, count in patterns
            )
            patterns_text += "."
        else:
            patterns_text = "повторяющихся посредников пока не видно."

        return (
            f"{title}\n\n"
            f"Σ ЖС: {viability_sum_text}\n\n"
            f"Успехи: {successes_text}\n\n"
            f"Что ставил перед Духом: {placements_text}\n\n"
            f"Паттерны перед Духом: {patterns_text}\n"
        )

    def _write_report(self, path: Path, text: str) -> dict[str, Any]:
        _atomic_write_text(path, text)
        return {"valid": True, "path": path, "text": text}

    def write_evening_report(
        self,
        target_date: date | datetime | str | None = None,
        *,
        codex_activity_path: str | Path | None = None,
    ) -> dict[str, Any]:
        local_date = _report_date(target_date, self.timezone)
        start, end = resolve_day_window(
            local_date,
            timezone=self.timezone_name,
        )
        text = self._render_evening(
            title=f"Вечерний отчёт — {local_date.isoformat()}",
            start=start,
            end=end,
            events=self._events_in_window(start, end),
            codex_activity_path=codex_activity_path,
        )
        path = self.reports_root / "daily" / f"{local_date.isoformat()}.md"
        return self._write_report(path, text)

    def write_weekly_report(
        self,
        target_date: date | datetime | str | None = None,
        *,
        codex_activity_path: str | Path | None = None,
    ) -> dict[str, Any]:
        local_date = _report_date(target_date, self.timezone)
        start, end = resolve_iso_week_window(
            local_date,
            timezone=self.timezone_name,
        )
        week_label = _iso_week_label(local_date)
        text = self._render_weekly(
            title=f"Недельный отчёт — {week_label}",
            start=start,
            end=end,
            events=self._events_in_window(start, end),
            codex_activity_path=codex_activity_path,
            reflection=self._weekly_reflection(week_label),
        )
        path = self.reports_root / "weekly" / f"{week_label}.md"
        return self._write_report(path, text)


def render_reading_views(
    data_dir: Path,
    events: list[dict[str, Any]],
) -> dict[str, str]:
    views_root = data_dir / "views"
    specifications: dict[str, tuple[str, str, str | None]] = {
        "journal": ("Дневник.md", "Дневник", None),
        "ideas": ("Идеи.md", "Идеи", "idea"),
        "successes": ("Успехи.md", "Успехи", "success"),
        "content": ("Контент.md", "Контент", "content_experience"),
    }
    paths: dict[str, str] = {}
    for key, (filename, title, event_type) in specifications.items():
        selected = [
            event
            for event in events
            if event_type is None or event["type"] == event_type
        ]
        lines = [f"# {title}", ""]
        if selected:
            for event in selected:
                description = event.get("description")
                summary = (
                    " ".join(description.split())
                    if isinstance(description, str) and description.strip()
                    else "(без описания)"
                )
                suffix = ""
                if event.get("type") == "idea":
                    status_label = {
                        "captured": "сохранена",
                        "developing": "в работе",
                        "implemented": "реализована",
                        "deferred": "отложена",
                        "rejected": "отклонена",
                    }.get(event.get("status"))
                    if status_label is not None:
                        suffix += f" · {status_label}"
                    links = event.get("links")
                    task_number = (
                        links.get("focus_task_number")
                        if isinstance(links, dict)
                        else None
                    )
                    if isinstance(task_number, int):
                        suffix += f" · задача {task_number}"
                lines.append(
                    f"- {event['occurred_at']} · {event['type']} · {summary}{suffix}"
                )
        else:
            lines.append("Пока записей нет.")
        path = views_root / filename
        _atomic_write_text(path, "\n".join(lines).rstrip() + "\n")
        paths[key] = str(path)
    return paths


class PersonalDailyService:
    """Deterministic local state machine for the short daily dialogue."""

    def __init__(
        self,
        repo_root: str | Path | None = None,
        events_path: str | Path | None = None,
        state_path: str | Path | None = None,
        context_path: str | Path | None = None,
        *,
        data_dir: str | Path | None = None,
        timezone: str = DEFAULT_TIMEZONE,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root is not None else DEFAULT_REPO_ROOT
        self.store = PersonalEventStore(
            repo_root=self.repo_root,
            events_path=events_path,
            data_dir=data_dir,
            timezone=timezone,
        )
        self.timezone = self.store.timezone
        self.state_path = (
            Path(state_path)
            if state_path is not None
            else self.store.data_dir / "state.json"
        )
        self.state_lock_path = self.state_path.parent / ".state.lock"
        self.context_path = (
            Path(context_path)
            if context_path is not None
            else self.repo_root / DEFAULT_CONTEXT_RELATIVE
        )
        self.context = self._load_context()

    def _local_now(self, now: datetime | None = None) -> datetime:
        value = now if now is not None else datetime.now(self.timezone)
        if value.tzinfo is None or value.utcoffset() is None:
            raise PersonalEventError("interaction time must include a timezone offset")
        return value.astimezone(self.timezone)

    def _load_context(self) -> dict[str, Any]:
        try:
            raw = self.context_path.read_text(encoding="utf-8")
            value = json.loads(raw, parse_constant=_reject_json_constant)
        except FileNotFoundError as exc:
            raise PersonalEventError(
                f"active context does not exist: {self.context_path}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise PersonalEventError(
                f"active context is invalid JSON: {self.context_path}: {exc.msg}"
            ) from exc
        if not isinstance(value, dict):
            raise PersonalEventError("active context must be an object")
        self._validate_context(value)
        return value

    def _validate_context(self, context: dict[str, Any]) -> None:
        _nonempty_string(context.get("status"), "active context status")
        focus_until = context.get("focus_until")
        _nonempty_string(focus_until, "active context focus_until")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", focus_until):
            raise PersonalEventError(
                "active context focus_until must be an ISO date (YYYY-MM-DD)"
            )
        try:
            date.fromisoformat(focus_until)
        except ValueError as exc:
            raise PersonalEventError(
                "active context focus_until must be a valid ISO date"
            ) from exc
        _nonempty_string(context.get("active_understanding"), "active_understanding")
        l1 = context.get("l1")
        if not isinstance(l1, dict):
            raise PersonalEventError("active context l1 must be an object")
        _nonempty_string(l1.get("text"), "active context l1.text")
        questions = context.get("questions")
        if not isinstance(questions, dict):
            raise PersonalEventError("active context questions must be an object")
        _nonempty_string(questions.get("morning"), "active context questions.morning")
        _nonempty_string(questions.get("evening"), "active context questions.evening")
        patterns = context.get("warning_patterns")
        if not isinstance(patterns, list) or not all(
            isinstance(item, str) and item.strip() for item in patterns
        ):
            raise PersonalEventError(
                "active context warning_patterns must be an array of strings"
            )
        reflections = context.get("viability_reflections")
        if reflections is not None:
            if not isinstance(reflections, dict):
                raise PersonalEventError(
                    "active context viability_reflections must be an object"
                )
            for field in ("affirmations", "understandings"):
                values = reflections.get(field)
                if not isinstance(values, list) or not values or not all(
                    isinstance(item, str) and item.strip() for item in values
                ):
                    raise PersonalEventError(
                        "active context viability_reflections."
                        f"{field} must be a nonempty array of strings"
                    )
        groups = context.get("focus_groups")
        if not isinstance(groups, list) or not groups:
            raise PersonalEventError(
                "active context focus_groups must be a nonempty array"
            )
        groups_by_id: dict[str, dict[str, Any]] = {}
        for index, group in enumerate(groups):
            if not isinstance(group, dict):
                raise PersonalEventError(
                    f"active context focus_groups[{index}] must be an object"
                )
            for field in ("id", "label", "l2", "period_focus"):
                _nonempty_string(
                    group.get(field),
                    f"active context focus_groups[{index}].{field}",
                )
            group_id = group["id"]
            if group_id in groups_by_id:
                raise PersonalEventError(
                    f"active context contains duplicate focus group id: {group_id}"
                )
            groups_by_id[group_id] = group
        choices = context.get("task_choices")
        if not isinstance(choices, list) or not choices:
            raise PersonalEventError(
                "active context task_choices must be a nonempty array"
            )
        seen_ids: set[str] = set()
        seen_numbers: set[int] = set()
        required = (
            "id",
            "group_id",
            "label",
            "l2",
            "period_focus",
            "day_result",
            "first_step",
        )
        for index, choice in enumerate(choices):
            if not isinstance(choice, dict):
                raise PersonalEventError(
                    f"active context task_choices[{index}] must be an object"
                )
            for field in required:
                _nonempty_string(
                    choice.get(field),
                    f"active context task_choices[{index}].{field}",
                )
            choice_id = choice["id"]
            if choice_id in seen_ids:
                raise PersonalEventError(
                    f"active context contains duplicate task id: {choice_id}"
                )
            seen_ids.add(choice_id)
            number = choice.get("number")
            if (
                isinstance(number, bool)
                or not isinstance(number, int)
                or number < 1
            ):
                raise PersonalEventError(
                    f"active context task_choices[{index}].number must be a "
                    "positive integer"
                )
            if number in seen_numbers:
                raise PersonalEventError(
                    f"active context contains duplicate task number: {number}"
                )
            seen_numbers.add(number)
            group_id = choice["group_id"]
            group = groups_by_id.get(group_id)
            if group is None:
                raise PersonalEventError(
                    f"active context task {choice_id} has unknown group: {group_id}"
                )
            if (
                choice["l2"] != group["l2"]
                or choice["period_focus"] != group["period_focus"]
            ):
                raise PersonalEventError(
                    f"active context task {choice_id} has stale focus snapshot"
                )
            duration = choice.get("duration_minutes")
            if (
                duration is not None
                and (
                    isinstance(duration, bool)
                    or not isinstance(duration, int)
                    or duration <= 0
                )
            ):
                raise PersonalEventError(
                    f"active context task_choices[{index}].duration_minutes "
                    "must be a positive integer or null"
                )
            status = choice.get("status", "active")
            if status not in {"active", "completed"}:
                raise PersonalEventError(
                    f"active context task_choices[{index}].status must be "
                    "active or completed"
                )
            if status == "completed":
                _nonempty_string(
                    choice.get("completed_at"),
                    f"active context task_choices[{index}].completed_at",
                )
                completion_evidence = choice.get("completion_evidence")
                if not isinstance(completion_evidence, list) or not all(
                    isinstance(item, str) and item.strip()
                    for item in completion_evidence
                ):
                    raise PersonalEventError(
                        "active context completed task "
                        f"{choice_id} must have completion_evidence"
                    )
        numbers = [choice["number"] for choice in choices]
        if numbers != list(range(1, len(choices) + 1)):
            raise PersonalEventError(
                "active context task numbers must be contiguous from 1 "
                "in task order"
            )

    def _empty_state(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "pending_interaction": None,
            "callbacks": {},
            "replies": {},
            "pulses": {},
            "completed_interactions": {},
        }

    def _validate_state(self, state: dict[str, Any]) -> None:
        if not isinstance(state, dict):
            raise PersonalEventError("interaction state must be an object")
        for field in (
            "callbacks",
            "replies",
            "pulses",
            "completed_interactions",
        ):
            if not isinstance(state.get(field), dict):
                raise PersonalEventError(
                    f"interaction state {field} must be an object"
                )
        pending = state.get("pending_interaction")
        if pending is not None:
            if not isinstance(pending, dict):
                raise PersonalEventError(
                    "interaction state pending_interaction must be an object or null"
                )
            for field in ("workflow", "interaction_id", "stage"):
                _nonempty_string(
                    pending.get(field),
                    f"interaction state pending_interaction.{field}",
                )
            for field in ("opened_at", "expires_at"):
                try:
                    _parse_aware_datetime(pending.get(field))
                except PersonalEventError as exc:
                    raise PersonalEventError(
                        f"interaction state pending_interaction.{field}: {exc}"
                    ) from exc
            if not isinstance(pending.get("payload"), dict):
                raise PersonalEventError(
                    "interaction state pending_interaction.payload must be an object"
                )
        for value, callback in state["callbacks"].items():
            _nonempty_string(value, "interaction state callback key")
            if not isinstance(callback, dict):
                raise PersonalEventError(
                    f"interaction state callback {value} must be an object"
                )
            _nonempty_string(
                callback.get("workflow"),
                f"interaction state callback {value}.workflow",
            )
            _parse_aware_datetime(callback.get("expires_at"))
            if not isinstance(callback.get("metadata", {}), dict):
                raise PersonalEventError(
                    f"interaction state callback {value}.metadata must be an object"
                )
            if callback.get("result") is not None and not isinstance(
                callback["result"], dict
            ):
                raise PersonalEventError(
                    f"interaction state callback {value}.result must be an object"
                )
        for message_id, reply in state["replies"].items():
            _nonempty_string(message_id, "interaction state reply key")
            if not isinstance(reply, dict) or not isinstance(
                reply.get("result"), dict
            ):
                raise PersonalEventError(
                    f"interaction state reply {message_id} must contain result"
                )
        for pulse_id, pulse in state["pulses"].items():
            _nonempty_string(pulse_id, "interaction state pulse key")
            if not isinstance(pulse, dict):
                raise PersonalEventError(
                    f"interaction state pulse {pulse_id} must be an object"
                )
            if pulse.get("result") is not None and not isinstance(
                pulse["result"], dict
            ):
                raise PersonalEventError(
                    f"interaction state pulse {pulse_id}.result must be an object"
                )
        for interaction_id, completion in state["completed_interactions"].items():
            _nonempty_string(
                interaction_id,
                "interaction state completed interaction key",
            )
            if not isinstance(completion, dict) or not isinstance(
                completion.get("result"), dict
            ):
                raise PersonalEventError(
                    "interaction state completed interaction "
                    f"{interaction_id} must contain result"
                )

    def _load_state_unlocked(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._empty_state()
        try:
            value = json.loads(
                self.state_path.read_text(encoding="utf-8"),
                parse_constant=_reject_json_constant,
            )
        except json.JSONDecodeError as exc:
            raise PersonalEventError(
                f"interaction state is invalid JSON: {self.state_path}: {exc.msg}"
            ) from exc
        if not isinstance(value, dict):
            raise PersonalEventError("interaction state must be an object")
        state = self._empty_state()
        state.update(value)
        self._validate_state(state)
        return state

    def _write_state_unlocked(self, state: dict[str, Any]) -> None:
        self._validate_state(state)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = _strict_json_dumps(state) + "\n"
        temp_path = self.state_path.parent / (
            f".{self.state_path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            temp_fd = os.open(temp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.state_path)
            directory_fd = os.open(self.state_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass

    @contextmanager
    def _state_transaction(self) -> Iterable[dict[str, Any]]:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(self.state_lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_fd, "a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                state = self._load_state_unlocked()
                yield state
                self._write_state_unlocked(state)
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _relative_expiry(self, now: datetime, seconds: int) -> datetime:
        return (
            now.astimezone(timezone.utc) + timedelta(seconds=seconds)
        ).astimezone(self.timezone)

    def _expires_at(self, now: datetime, seconds: int) -> str:
        return self._relative_expiry(now, seconds).isoformat(timespec="seconds")

    def _new_pending(
        self,
        workflow: str,
        interaction_id: str,
        stage: str,
        *,
        now: datetime,
        expires_in_seconds: int | None = None,
        expires_at: datetime | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if (expires_in_seconds is None) == (expires_at is None):
            raise PersonalEventError(
                "pending interaction requires exactly one expiry"
            )
        if expires_at is None:
            assert expires_in_seconds is not None
            expiry = self._relative_expiry(now, expires_in_seconds)
        else:
            expiry = self._local_now(expires_at)
        return {
            "workflow": workflow,
            "interaction_id": interaction_id,
            "stage": stage,
            "opened_at": now.isoformat(timespec="seconds"),
            "expires_at": expiry.isoformat(timespec="seconds"),
            "payload": copy.deepcopy(payload or {}),
        }

    def _morning_deadline(self, now: datetime) -> datetime:
        return datetime.combine(
            now.date(),
            time(hour=10),
            tzinfo=self.timezone,
        )

    def _skipped_morning_response(self) -> dict[str, Any]:
        return {
            "workflow": "morning",
            "status": "skipped",
            "reason": "morning_deadline_passed",
            "text": "Утреннее окно завершилось в 10:00.",
        }

    def open_interaction(
        self,
        workflow: str,
        interaction_id: str,
        stage: str,
        *,
        now: datetime | None = None,
        expires_in_seconds: int = 12 * 60 * 60,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        local_now = self._local_now(now)
        pending = self._new_pending(
            workflow,
            interaction_id,
            stage,
            now=local_now,
            expires_in_seconds=expires_in_seconds,
            payload=payload,
        )
        with self._state_transaction() as state:
            state["pending_interaction"] = pending
        return copy.deepcopy(pending)

    def _add_callbacks(
        self,
        state: dict[str, Any],
        callback_data: Iterable[str],
        *,
        workflow: str,
        now: datetime,
        expires_in_seconds: int,
        metadata: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        expires_at = self._expires_at(now, expires_in_seconds)
        callbacks = state.setdefault("callbacks", {})
        for value in callback_data:
            if len(value.encode("utf-8")) >= 64:
                raise PersonalEventError(f"callback data is too long: {value}")
            callbacks.setdefault(
                value,
                {
                    "workflow": workflow,
                    "issued_at": now.isoformat(timespec="seconds"),
                    "expires_at": expires_at,
                    "metadata": copy.deepcopy((metadata or {}).get(value, {})),
                },
            )

    def _button(self, text: str, value: str, callback_data: str) -> dict[str, str]:
        return {
            "text": text,
            "value": value,
            "callback_data": callback_data,
        }

    def _morning_initial_response(self) -> dict[str, Any]:
        understanding = self.context["active_understanding"]
        question = self.context["questions"]["morning"]
        return {
            "workflow": "morning",
            "text": f"Активное понимание: {understanding}\n\n{question}",
            "next_stage": "awaiting_morning_answer",
        }

    def _morning_control_response(self) -> dict[str, Any]:
        return {
            "workflow": "morning",
            "next_stage": "awaiting_control_answer",
            "text": (
                "Как сегодня заметишь, что продолжаешь цель только из-за "
                "уже вложенных сил, хотя она перестала греть?"
            ),
        }

    def _same_active_interaction(
        self,
        pending: Any,
        workflow: str,
        interaction_id: str,
        now: datetime,
    ) -> bool:
        if not isinstance(pending, dict):
            return False
        if (
            pending.get("workflow") != workflow
            or pending.get("interaction_id") != interaction_id
        ):
            return False
        expires_at = _parse_aware_datetime(pending.get("expires_at"))
        return _instant_precedes(now, expires_at)

    def _event_by_idempotency_key(
        self,
        idempotency_key: str,
        *,
        expected_type: str,
        week_label: str | None = None,
    ) -> dict[str, Any] | None:
        for event in self.store.load_events():
            if event.get("idempotency_key") == idempotency_key:
                return self._require_expected_event(
                    event,
                    idempotency_key=idempotency_key,
                    expected_type=expected_type,
                    week_label=week_label,
                )
        return None

    @staticmethod
    def _normalize_episode_description(value: str) -> str:
        return " ".join(value.casefold().split()).strip(" .,:;!—–-")

    def _parse_activity_gap_lines(self, text: str) -> list[dict[str, Any]]:
        parsed = []
        for line_number, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            match = VIABILITY_LINE_PATTERN.fullmatch(line)
            if match is None:
                continue
            parsed.append(
                {
                    "line_number": line_number,
                    "description": match.group("description").strip(),
                    "delta": VIABILITY_MARK_VALUES[match.group("mark")],
                    "context": (
                        match.group("context").strip()
                        if match.group("context")
                        else None
                    ),
                }
            )
        return parsed

    def _daily_viability_total(self, now: datetime) -> int:
        local_day = now.astimezone(self.timezone).date()
        daily_events = [
            event
            for event in self.store.load_materialized_events()
            if _parse_aware_datetime(event["occurred_at"])
            .astimezone(self.timezone)
            .date()
            == local_day
        ]
        return sum(
            event["self_report"]["delta"]
            for event in _deduplicate_report_episodes(daily_events)
            if event["type"] == "viability_checkin"
        )

    def _record_activity_gap_checkins(
        self,
        *,
        interaction_id: str,
        text: str,
        message_id: str,
        now: datetime,
    ) -> list[dict[str, Any]]:
        local_day = now.astimezone(self.timezone).date()
        existing_by_description: dict[str, dict[str, Any]] = {}
        for event in self.store.load_materialized_events():
            description = event.get("description")
            if (
                event.get("type") != "viability_checkin"
                or not isinstance(description, str)
                or _parse_aware_datetime(event["occurred_at"])
                .astimezone(self.timezone)
                .date()
                != local_day
            ):
                continue
            existing_by_description[
                self._normalize_episode_description(description)
            ] = event

        recorded: list[dict[str, Any]] = []
        for item in self._parse_activity_gap_lines(text):
            description_key = self._normalize_episode_description(
                item["description"]
            )
            existing = existing_by_description.get(description_key)
            idempotency_key = (
                f"evening_gap:{interaction_id}:{item['line_number']}"
            )
            if existing is not None:
                if existing["self_report"]["delta"] == item["delta"]:
                    continue
                corrected_report = copy.deepcopy(existing["self_report"])
                corrected_report["delta"] = item["delta"]
                if item["context"]:
                    corrected_report.update(
                        {
                            "context_status": "provided",
                            "context": item["context"],
                        }
                    )
                correction = self.store.append_event(
                    {
                        "type": "correction",
                        "idempotency_key": idempotency_key,
                        "occurred_at": now.isoformat(timespec="seconds"),
                        "source": {
                            "channel": "telegram",
                            "message_id": message_id,
                            "line_number": item["line_number"],
                        },
                        "supersedes_event_id": existing["id"],
                        "corrected_fields": [
                            "self_report",
                            "description",
                        ],
                        "self_report": corrected_report,
                        "description": item["description"],
                    }
                )
                recorded.append(correction)
                existing_by_description[description_key] = {
                    **existing,
                    "self_report": corrected_report,
                    "description": item["description"],
                }
                continue

            event = self.store.append_event(
                {
                    "type": "viability_checkin",
                    "idempotency_key": idempotency_key,
                    "occurred_at": now.isoformat(timespec="seconds"),
                    "source": {
                        "channel": "telegram",
                        "message_id": message_id,
                        "line_number": item["line_number"],
                    },
                    "self_report": {
                        "delta": item["delta"],
                        "context_status": (
                            "provided" if item["context"] else "missing"
                        ),
                        "context": item["context"],
                    },
                    "description": item["description"],
                }
            )
            recorded.append(event)
            existing_by_description[description_key] = event
        return recorded

    def _require_expected_event(
        self,
        event: dict[str, Any],
        *,
        idempotency_key: str,
        expected_type: str,
        week_label: str | None = None,
    ) -> dict[str, Any]:
        if event.get("idempotency_key") != idempotency_key:
            raise PersonalEventError(
                f"expected idempotency_key {idempotency_key}"
            )
        if event.get("type") != expected_type:
            raise PersonalEventError(
                f"idempotency_key {idempotency_key} belongs to "
                f"{event.get('type')}, expected {expected_type}"
            )
        if week_label is not None:
            self_report = event.get("self_report")
            stored_week = (
                self_report.get("week_label")
                if isinstance(self_report, dict)
                else None
            )
            if stored_week != week_label:
                raise PersonalEventError(
                    f"idempotency_key {idempotency_key} belongs to week "
                    f"{stored_week}, expected {week_label}"
                )
        return event

    def _viability_context_callbacks(
        self,
        state: dict[str, Any],
        *,
        pulse_id: str,
        checkin_event_id: str,
    ) -> list[dict[str, str]]:
        day, slot = pulse_id.split(":", maxsplit=1)
        actions = (
            ("Добавить контекст", "add", "a"),
            ("Ничего", "none", "n"),
        )
        buttons = [
            self._button(label, value, f"pd:vc:{day}:{slot}:{code}")
            for label, value, code in actions
        ]
        pulse = state["pulses"].get(pulse_id)
        if not isinstance(pulse, dict):
            raise PersonalEventError(
                f"viability context has no pulse: {pulse_id}"
            )
        callbacks = state.setdefault("callbacks", {})
        for button in buttons:
            callback_data = button["callback_data"]
            if len(callback_data.encode("utf-8")) >= 64:
                raise PersonalEventError(
                    f"callback data is too long: {callback_data}"
                )
            callbacks.setdefault(
                callback_data,
                {
                    "workflow": "viability_context",
                    "issued_at": pulse["issued_at"],
                    "expires_at": pulse["expires_at"],
                    "metadata": {
                        "action": button["value"],
                        "pulse_id": pulse_id,
                        "checkin_event_id": checkin_event_id,
                    },
                },
            )
        return buttons

    def _viability_delta_response(
        self,
        state: dict[str, Any],
        *,
        event: dict[str, Any],
        pulse_id: str,
        status: str,
    ) -> dict[str, Any]:
        stored_delta = event["self_report"]["delta"]
        if status == "recorded":
            saved_text = f"Срез сохранён: {stored_delta:+d}."
        else:
            saved_text = f"Этот срез уже сохранён: {stored_delta:+d}."
        return {
            "status": status,
            "event": event,
            "text": f"{saved_text}\n\n{VIABILITY_CONTEXT_QUESTION}",
            "buttons": self._viability_context_callbacks(
                state,
                pulse_id=pulse_id,
                checkin_event_id=event["id"],
            ),
        }

    def _viability_context_result(
        self,
        event: dict[str, Any],
        *,
        status: str,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "event": event,
            "text": (
                "Контекст сохранён."
                if status == "recorded"
                else "Контекст этого среза уже сохранён."
            ),
        }

    def _record_viability_context(
        self,
        *,
        pulse_id: str,
        checkin_event_id: str,
        context_status: str,
        context: str | None,
        description: str,
        source: dict[str, Any],
    ) -> dict[str, Any]:
        idempotency_key = f"viability_context:{pulse_id}"
        existing = self._event_by_idempotency_key(
            idempotency_key,
            expected_type="correction",
        )
        if existing is not None:
            return self._viability_context_result(
                existing,
                status="already_recorded",
            )
        checkin = self._event_by_idempotency_key(
            f"viability:{pulse_id}",
            expected_type="viability_checkin",
        )
        if (
            checkin is None
            or checkin.get("id") != checkin_event_id
            or checkin.get("type") != "viability_checkin"
        ):
            return {
                "status": "stale",
                "text": "Исходный срез больше недоступен.",
            }
        event = self.store.append_event(
            {
                "type": "correction",
                "idempotency_key": idempotency_key,
                "source": source,
                "supersedes_event_id": checkin["id"],
                "corrected_fields": ["self_report", "description"],
                "self_report": {
                    "delta": checkin["self_report"]["delta"],
                    "context_status": context_status,
                    "context": context,
                },
                "description": description,
            }
        )
        return self._viability_context_result(event, status="recorded")

    def _matching_viability_context_pending(
        self,
        pending: Any,
        pulse_id: str,
    ) -> bool:
        return (
            isinstance(pending, dict)
            and pending.get("workflow") == "viability_context"
            and pending.get("interaction_id") == pulse_id
            and pending.get("stage") == "awaiting_viability_context"
        )

    def _pending_is_active(
        self,
        pending: Any,
        now: datetime,
    ) -> bool:
        if not isinstance(pending, dict):
            return False
        expires_at = _parse_aware_datetime(pending.get("expires_at"))
        return _instant_precedes(now, expires_at)

    def _route_viability_context_callback(
        self,
        state: dict[str, Any],
        callback_data: str,
        callback: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        metadata = callback.get("metadata", {})
        pulse_id = metadata.get("pulse_id")
        checkin_event_id = metadata.get("checkin_event_id")
        action = metadata.get("action")
        if not isinstance(pulse_id, str) or not isinstance(
            checkin_event_id, str
        ):
            return {
                "status": "stale",
                "text": "Контекст этого среза больше недоступен.",
            }

        pending = state.get("pending_interaction")
        matching_pending = self._matching_viability_context_pending(
            pending,
            pulse_id,
        )
        existing = self._event_by_idempotency_key(
            f"viability_context:{pulse_id}",
            expected_type="correction",
        )
        if existing is not None:
            if matching_pending:
                state["pending_interaction"] = None
            return self._viability_context_result(
                existing,
                status="already_recorded",
            )

        if self._pending_is_active(pending, now) and not matching_pending:
            return {
                "status": "stale",
                "text": "Сейчас ожидается ответ на более новое взаимодействие.",
            }

        if action == "add":
            if matching_pending and self._pending_is_active(pending, now):
                return {
                    "status": "waiting",
                    "next_stage": "awaiting_viability_context",
                    "text": "Напиши или надиктуй, что произошло.",
                }
            state["pending_interaction"] = self._new_pending(
                "viability_context",
                pulse_id,
                "awaiting_viability_context",
                now=now,
                expires_in_seconds=30 * 60,
                payload={
                    "pulse_id": pulse_id,
                    "checkin_event_id": checkin_event_id,
                },
            )
            return {
                "status": "waiting",
                "next_stage": "awaiting_viability_context",
                "text": "Напиши или надиктуй, что произошло.",
            }

        if action == "none":
            result = self._record_viability_context(
                pulse_id=pulse_id,
                checkin_event_id=checkin_event_id,
                context_status="none",
                context=None,
                description="Ничего",
                source={
                    "channel": "telegram",
                    "callback_data": callback_data,
                },
            )
            if matching_pending and result.get("status") in {
                "recorded",
                "already_recorded",
            }:
                state["pending_interaction"] = None
            return result

        return {
            "status": "stale",
            "text": "Неизвестное действие для контекста.",
        }

    def _morning_completion(
        self,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        links = event.get("links", {})
        day_result = links.get("day_result")
        first_step = links.get("first_step")
        return {
            "status": "completed",
            "event": event,
            "day_result": day_result,
            "first_step": first_step,
            "text": (
                f"Утренний выбор уже сохранён.\nРезультат дня: {day_result}"
                + (f"\nПервый шаг: {first_step}" if first_step else "")
            ),
        }

    def _mark_completed(
        self,
        state: dict[str, Any],
        interaction_id: str,
        result: dict[str, Any],
    ) -> None:
        state["completed_interactions"][interaction_id] = {
            "result": copy.deepcopy(result)
        }

    def _renew_morning_choice(
        self,
        state: dict[str, Any],
        pending: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        stored = pending["payload"].get("choice_response")
        if not isinstance(stored, dict):
            raise PersonalEventError(
                "morning interaction is missing choice_response"
            )
        stored = copy.deepcopy(stored)
        stored.pop("buttons", None)
        expires_at = self._expires_at(now, 30 * 60)
        pending["expires_at"] = expires_at
        pending["payload"]["compact"] = True
        pending["payload"]["choice_response"] = copy.deepcopy(stored)
        state["pending_interaction"] = pending
        callbacks = state.setdefault("callbacks", {})
        for callback_data, callback in list(callbacks.items()):
            if (
                isinstance(callback, dict)
                and callback.get("workflow") == "morning"
                and callback.get("metadata", {}).get("interaction_id")
                == pending["interaction_id"]
            ):
                callbacks.pop(callback_data, None)
        return copy.deepcopy(stored)

    @staticmethod
    def _idea_title(idea: dict[str, Any]) -> str:
        description = idea.get("description")
        if not isinstance(description, str) or not description.strip():
            return "Оформить идею"
        title = re.sub(
            r"^\s*идея(?:\s*[:—–-]|\.)\s*",
            "",
            description.strip(),
            flags=re.IGNORECASE,
        )
        title = " ".join(title.split())
        title = re.split(r"(?<=[.!?])\s+", title, maxsplit=1)[0]
        if len(title) > 100:
            title = title[:97].rstrip(" ,.;:—–-") + "…"
        return title[:1].upper() + title[1:] if title else "Оформить идею"

    def _ideas_for_evening(self, now: datetime) -> list[dict[str, Any]]:
        local_now = self._local_now(now)
        pending: list[dict[str, Any]] = []
        for event in self.store.load_materialized_events():
            if event.get("type") != "idea":
                continue
            links = event.get("links")
            if isinstance(links, dict) and isinstance(
                links.get("focus_task_id"), str
            ):
                continue
            pending.append(event)
        pending.sort(key=lambda event: event["occurred_at"])
        today = [
            event
            for event in pending
            if _parse_aware_datetime(event["occurred_at"])
            .astimezone(self.timezone)
            .date()
            == local_now.date()
        ]
        backlog = [event for event in pending if event not in today]
        return [*today, *backlog[:1]]

    def _idea_followthrough_prompt(self, idea: dict[str, Any]) -> str:
        title = self._idea_title(idea)
        return (
            f"Идея: «{title}»\n"
            "Первый шаг на 15–30 минут: зафиксируй короткую заметку — "
            "какой результат хочешь получить и что сделаешь следующим.\n"
            "Что получилось?"
        )

    @staticmethod
    def _idea_match_tokens(text: str) -> set[str]:
        stopwords = {
            "идея",
            "собрать",
            "сделать",
            "создать",
            "оформить",
            "этот",
            "эта",
            "это",
            "для",
            "чтобы",
            "как",
            "про",
            "свой",
            "свои",
            "мой",
            "мои",
        }
        return {
            token
            for token in re.findall(r"[0-9a-zа-яё]+", text.casefold())
            if len(token) >= 4 and token not in stopwords
        }

    def _idea_existing_evidence(
        self,
        idea: dict[str, Any],
        *,
        now: datetime,
    ) -> str | None:
        for item in reversed(idea.get("evidence", [])):
            if isinstance(item, str) and self._idea_result_has_artifact(item):
                return " ".join(item.split())

        title_tokens = self._idea_match_tokens(self._idea_title(idea))
        if not title_tokens:
            return None
        idea_time = _parse_aware_datetime(idea["occurred_at"])
        best: tuple[int, str] | None = None
        for event in self.store.load_materialized_events():
            if event.get("id") == idea.get("id") or event.get("type") not in {
                "success",
                "focus_finished",
                "viability_checkin",
                "evening_reflection",
            }:
                continue
            event_time = _parse_aware_datetime(event["occurred_at"])
            if _instant_precedes(event_time, idea_time) or _instant_precedes(
                now,
                event_time,
            ):
                continue
            description = event.get("description")
            if not isinstance(description, str) or not self._idea_result_has_artifact(
                description
            ):
                continue
            overlap = title_tokens & self._idea_match_tokens(description)
            minimum_overlap = 1 if len(title_tokens) == 1 else 2
            if len(overlap) < minimum_overlap:
                continue
            evidence = " ".join(description.split())
            score = len(overlap)
            if best is None or score > best[0]:
                best = (score, evidence)
        return best[1] if best is not None else None

    def _idea_by_id(self, idea_id: str) -> dict[str, Any] | None:
        return next(
            (
                event
                for event in self.store.load_materialized_events()
                if event.get("type") == "idea" and event.get("id") == idea_id
            ),
            None,
        )

    @staticmethod
    def _idea_completion_text(count: int) -> str:
        if count == 1:
            return "Идея оформлена и добавлена в текущие задачи."
        if count == 2:
            return "Две идеи оформлены и добавлены в текущие задачи."
        if count == 3:
            return "Три идеи оформлены и добавлены в текущие задачи."
        return f"{count} идей оформлены и добавлены в текущие задачи."

    def _idea_focus_group(self, title: str) -> dict[str, Any]:
        groups = {
            group["id"]: group for group in self.context["focus_groups"]
        }
        lowered = title.casefold()
        candidates = (
            (
                "bsz_tools",
                (
                    "бсз",
                    "бз",
                    "лекц",
                    "конспект",
                    "скилл",
                    "skill",
                    "harness",
                    "каталог",
                    "генограмм",
                    "инструмент",
                ),
            ),
            (
                "distribution",
                (
                    "telegram",
                    "телеграм",
                    "канал",
                    "linkedin",
                    "рассыл",
                    "лид",
                    "интенсив",
                    "артефакт",
                    "сайт",
                    "стать",
                    "видео",
                    "ролик",
                    "пост",
                    "отправ",
                ),
            ),
            (
                "truth",
                ("quantum", "истин", "comparison", "сравнен"),
            ),
        )
        for group_id, markers in candidates:
            if group_id in groups and any(
                marker in lowered for marker in markers
            ):
                return groups[group_id]
        return groups.get(
            "vitality_system",
            self.context["focus_groups"][0],
        )

    @staticmethod
    def _idea_result_is_complete(text: str) -> bool:
        return bool(
            re.search(
                r"\b(?:полностью\s+реализовал|реализовал|реализована|"
                r"завершил|завершена|пров(?:е|ё)л|"
                r"провед(?:е|ё)н(?:а|о|ы)?|готово|выполнено|опубликовал|"
                r"запустил)\b",
                text,
                flags=re.IGNORECASE,
            )
            or re.search(
                r"\b\d+\s+(?:лекци|заняти|встреч|сесси|урок)\w*\b",
                text,
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _idea_result_has_artifact(text: str) -> bool:
        stripped = " ".join(text.split())
        if not stripped or re.search(
            r"\b(?:не\s+сделал|не\s+успел|ничего|не\s+начал)\b",
            stripped,
            flags=re.IGNORECASE,
        ):
            return False
        return bool(
            re.search(
                r"(?:https?://|/Users/|\b(?:заметк|тз|план|черновик|файл|"
                r"документ|схем|прототип|список|таблиц|написал|создал|"
                r"собрал|оформил|реализовал|завершил|готово|выполнено|"
                r"опубликовал|запустил|пров(?:е|ё)л|"
                r"провед(?:е|ё)н)\w*|"
                r"\b\d+\s+(?:лекци|заняти|встреч|сесси|урок)\w*\b)",
                stripped,
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _idea_task_id(idea_id: str) -> str:
        digest = hashlib.sha256(idea_id.encode("utf-8")).hexdigest()[:10]
        return f"idea-{digest}"

    @staticmethod
    def _task_for_idea(
        context: dict[str, Any],
        idea_id: str,
    ) -> dict[str, Any] | None:
        for task in context.get("task_choices", []):
            source = task.get("source")
            if (
                isinstance(source, dict)
                and source.get("idea_event_id") == idea_id
            ):
                return task
        return None

    def _promote_idea(
        self,
        idea: dict[str, Any],
        *,
        result_text: str,
        source: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        existing_context = self._load_context()
        existing_task = self._task_for_idea(existing_context, idea["id"])
        if existing_task is not None:
            existing_correction = self._event_by_idempotency_key(
                f"idea_followthrough:{idea['id']}",
                expected_type="correction",
            )
            if existing_correction is not None:
                materialized_idea = next(
                    (
                        event
                        for event in self.store.load_materialized_events()
                        if event["id"] == idea["id"]
                    ),
                    idea,
                )
                stored_evidence = materialized_idea.get("evidence", [])
                return {
                    "title": self._idea_title(materialized_idea),
                    "task": copy.deepcopy(existing_task),
                    "event": existing_correction,
                    "evidence": (
                        stored_evidence[-1] if stored_evidence else ""
                    ),
                    "task_storage": "local",
                }
        evidence = " ".join(result_text.split())
        if not self._idea_result_has_artifact(evidence):
            raise PersonalEventError(
                "idea result must contain a material note, plan, file, or result"
            )
        local_now = self._local_now(now)
        title = self._idea_title(idea)
        completed = self._idea_result_is_complete(evidence)
        task_created = False
        context_lock = self.store.data_dir / ".active-context.lock"
        context_lock.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(context_lock, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_fd, "a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                context = self._load_context()
                task = self._task_for_idea(context, idea["id"])
                if task is None:
                    group = self._idea_focus_group(title)
                    number = max(
                        (
                            item["number"]
                            for item in context["task_choices"]
                        ),
                        default=0,
                    ) + 1
                    task = {
                        "number": number,
                        "id": self._idea_task_id(idea["id"]),
                        "group_id": group["id"],
                        "status": "completed" if completed else "active",
                        "label": title,
                        "l2": group["l2"],
                        "period_focus": group["period_focus"],
                        "day_result": (
                            f"Получен законченный результат по идее «{title}»"
                        ),
                        "first_step": (
                            "Открыть первичный материал и выполнить следующий "
                            f"конкретный шаг к завершению идеи «{title}»"
                        ),
                        "duration_minutes": 30,
                        "source": {
                            "kind": "personal_idea",
                            "idea_event_id": idea["id"],
                        },
                    }
                    if completed:
                        task["completed_at"] = local_now.date().isoformat()
                        task["completion_evidence"] = [evidence]
                    context["task_choices"].append(task)
                    self._validate_context(context)
                    _atomic_write_text(
                        self.context_path,
                        json.dumps(
                            context,
                            ensure_ascii=False,
                            indent=2,
                            allow_nan=False,
                        )
                        + "\n",
                    )
                    task_created = True
                self.context = context
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

        current_idea = next(
            (
                event
                for event in self.store.load_materialized_events()
                if event["id"] == idea["id"]
            ),
            idea,
        )
        links = copy.deepcopy(current_idea.get("links", {}))
        links.update(
            {
                "focus_task_id": task["id"],
                "focus_task_number": task["number"],
                "active_context": str(self.context_path),
            }
        )
        idea_evidence = list(current_idea.get("evidence", []))
        if evidence not in idea_evidence:
            idea_evidence.append(evidence)
        annotations = list(current_idea.get("agent_annotations", []))
        annotation = {
            "kind": "idea_shape",
            "title": title,
            "group_id": task["group_id"],
            "day_result": task["day_result"],
            "first_step": task["first_step"],
        }
        if annotation not in annotations:
            annotations.append(annotation)
        correction = self.store.append_event(
            {
                "type": "correction",
                "idempotency_key": f"idea_followthrough:{idea['id']}",
                "occurred_at": local_now.isoformat(timespec="seconds"),
                "source": source,
                "supersedes_event_id": idea["id"],
                "corrected_fields": [
                    "status",
                    "links",
                    "evidence",
                    "agent_annotations",
                ],
                "status": "implemented" if completed else "developing",
                "links": links,
                "evidence": idea_evidence,
                "agent_annotations": annotations,
            }
        )
        render_reading_views(
            self.store.data_dir,
            self.store.load_materialized_events(),
        )
        return {
            "title": title,
            "task": copy.deepcopy(task),
            "event": correction,
            "evidence": evidence,
            "task_storage": "local",
        }

    def _weekly_report(
        self,
        *,
        report_date: date | str,
        codex_activity_path: str | Path | None,
    ) -> dict[str, Any]:
        reporter = PersonalReportService(
            repo_root=self.store.repo_root,
            events_path=self.store.events_path,
            data_dir=self.store.data_dir,
        )
        return reporter.write_weekly_report(
            report_date,
            codex_activity_path=codex_activity_path,
        )

    @staticmethod
    def _weekly_question_response(
        report_text: str,
        interaction_id: str,
    ) -> dict[str, Any]:
        text = report_text.replace(
            WEEKLY_FEELING_QUESTION,
            "[повтор вопроса об итоговом ощущении опущен]",
        ).rstrip()
        return {
            "workflow": "weekly",
            "status": "waiting",
            "interaction_id": interaction_id,
            "next_stage": "awaiting_weekly_feeling",
            "text": f"{text}\n\n{WEEKLY_FEELING_QUESTION}",
        }

    @staticmethod
    def _busy_response(
        workflow: str,
        pending: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "workflow": workflow,
            "status": "busy",
            "reason": "another_interaction_is_active",
            "text": (
                "Сначала заверши активное взаимодействие "
                f"«{pending['workflow']}»."
            ),
        }

    def _active_unrelated_pending(
        self,
        pending: Any,
        *,
        workflow: str,
        interaction_id: str,
        now: datetime,
    ) -> bool:
        if (
            workflow in {"evening", "weekly"}
            and isinstance(pending, dict)
            and pending.get("workflow") == "morning"
        ):
            return False
        return (
            self._pending_is_active(pending, now)
            and (
                pending.get("workflow") != workflow
                or pending.get("interaction_id") != interaction_id
            )
        )

    def mark_weekly_delivered(self, interaction_id: str) -> bool:
        return self.mark_interaction_delivered(
            "weekly",
            interaction_id,
        )

    def begin_delivery_attempt(
        self,
        workflow: str,
        interaction_id: str,
    ) -> str | None:
        _nonempty_string(workflow, "workflow")
        _nonempty_string(interaction_id, "interaction_id")
        with self._state_transaction() as state:
            pending = state.get("pending_interaction")
            if (
                not isinstance(pending, dict)
                or pending.get("workflow") != workflow
                or pending.get("interaction_id") != interaction_id
            ):
                return None
            payload = pending["payload"]
            payload["delivery_managed"] = True
            payload.setdefault("delivered", False)
            return pending["interaction_id"]

    def mark_interaction_delivered(
        self,
        workflow: str,
        interaction_id: str,
    ) -> bool:
        _nonempty_string(workflow, "workflow")
        _nonempty_string(interaction_id, "interaction_id")
        with self._state_transaction() as state:
            pending = state.get("pending_interaction")
            if (
                not isinstance(pending, dict)
                or pending.get("workflow") != workflow
                or pending.get("interaction_id") != interaction_id
            ):
                return False
            pending["payload"]["delivery_managed"] = True
            pending["payload"]["delivered"] = True
            return True

    def discard_undelivered_weekly(self, interaction_id: str) -> bool:
        return self.discard_undelivered_interaction(
            "weekly",
            interaction_id,
        )

    def discard_undelivered_interaction(
        self,
        workflow: str,
        interaction_id: str,
    ) -> bool:
        _nonempty_string(workflow, "workflow")
        _nonempty_string(interaction_id, "interaction_id")
        with self._state_transaction() as state:
            pending = state.get("pending_interaction")
            if (
                not isinstance(pending, dict)
                or pending.get("workflow") != workflow
                or pending.get("interaction_id") != interaction_id
                or pending.get("payload", {}).get("delivered") is True
            ):
                return False
            state["pending_interaction"] = None
            return True

    def prepare(
        self,
        workflow: str,
        *,
        now: datetime | None = None,
        report_text: str | None = None,
        codex_activity_path: str | Path | None = None,
        compact: bool = False,
    ) -> dict[str, Any]:
        if compact and workflow != "morning":
            raise PersonalEventError("--compact is only valid for morning")
        local_now = self._local_now(now)
        day = local_now.strftime("%Y%m%d")

        if workflow == "morning":
            interaction_id = f"{local_now.date().isoformat()}:08"
            deadline = self._morning_deadline(local_now)
            with self._state_transaction() as state:
                pending = state.get("pending_interaction")
                if self._active_unrelated_pending(
                    pending,
                    workflow="morning",
                    interaction_id=interaction_id,
                    now=local_now,
                ):
                    return self._busy_response("morning", pending)
                if not compact and local_now >= deadline:
                    if (
                        isinstance(pending, dict)
                        and pending.get("workflow") == "morning"
                        and pending.get("interaction_id") == interaction_id
                        and not pending.get("payload", {}).get("compact")
                    ):
                        state["pending_interaction"] = None
                    return self._skipped_morning_response()
                completed = state["completed_interactions"].get(interaction_id)
                if isinstance(completed, dict):
                    result = copy.deepcopy(completed["result"])
                    result["status"] = "completed"
                    return result
                existing_event = self._event_by_idempotency_key(
                    f"morning_intent:{interaction_id}",
                    expected_type="morning_intent",
                )
                if existing_event is not None:
                    result = self._morning_completion(existing_event)
                    self._mark_completed(state, interaction_id, result)
                    state["pending_interaction"] = None
                    return result
                if compact:
                    if (
                        self._same_active_interaction(
                            pending,
                            "morning",
                            interaction_id,
                            local_now,
                        )
                        and pending["stage"] == "awaiting_task_choice"
                    ):
                        return self._renew_morning_choice(
                            state,
                            pending,
                            local_now,
                        )
                    pending = self._new_pending(
                        "morning",
                        interaction_id,
                        "awaiting_task_choice",
                        now=local_now,
                        expires_in_seconds=30 * 60,
                        payload={"compact": True},
                    )
                    state["pending_interaction"] = pending
                    return self._morning_choices_response(
                        state,
                        pending,
                        local_now,
                    )

                if self._same_active_interaction(
                    pending, "morning", interaction_id, local_now
                ):
                    stage = pending["stage"]
                    if stage == "awaiting_morning_answer":
                        return self._morning_initial_response()
                    if stage == "awaiting_control_answer":
                        return self._morning_control_response()
                    if stage == "awaiting_task_choice":
                        stored = pending["payload"].get("choice_response")
                        if not isinstance(stored, dict):
                            raise PersonalEventError(
                                "morning interaction is missing choice_response"
                            )
                        return copy.deepcopy(stored)
                    raise PersonalEventError(
                        f"unsupported morning interaction stage: {stage}"
                    )
                state["pending_interaction"] = self._new_pending(
                    "morning",
                    interaction_id,
                    "awaiting_morning_answer",
                    now=local_now,
                    expires_at=deadline,
                )
                return self._morning_initial_response()

        if workflow == "viability":
            slot = local_now.strftime("%H%M")
            pulse_id = f"{day}:{slot}"
            codes = [
                ("−−", "-2", "m2"),
                ("−", "-1", "m1"),
                ("=", "0", "z"),
                ("+", "1", "p1"),
                ("++", "2", "p2"),
            ]
            buttons = [
                self._button(label, value, f"pd:v:{day}:{slot}:{code}")
                for label, value, code in codes
            ]
            metadata = {
                button["callback_data"]: {
                    "delta": int(button["value"]),
                    "slot": slot,
                    "pulse_id": pulse_id,
                }
                for button in buttons
            }
            context_reflections = (
                self.context.get("viability_reflections") or {}
            )
            text = _viability_prompt_text(
                local_now,
                affirmations=context_reflections.get("affirmations"),
                understandings=context_reflections.get("understandings"),
            )
            with self._state_transaction() as state:
                self._add_callbacks(
                    state,
                    [button["callback_data"] for button in buttons],
                    workflow="viability",
                    now=local_now,
                    expires_in_seconds=4 * 60 * 60,
                    metadata=metadata,
                )
                state["pulses"].setdefault(
                    pulse_id,
                    {
                        "issued_at": local_now.isoformat(timespec="seconds"),
                        "expires_at": self._expires_at(
                            local_now, 4 * 60 * 60
                        ),
                        "result": None,
                    },
                )
                return {
                    "workflow": "viability",
                    "text": text,
                    "buttons": buttons,
                }

        if workflow == "evening":
            if report_text is not None:
                _nonempty_string(report_text, "evening report text")
            callback = f"pd:e:{day}:addsuccess"
            interaction_id = f"{local_now.date().isoformat()}:22"
            with self._state_transaction() as state:
                pending = state.get("pending_interaction")
                if self._active_unrelated_pending(
                    pending,
                    workflow="evening",
                    interaction_id=interaction_id,
                    now=local_now,
                ):
                    return self._busy_response("evening", pending)
                completed = state["completed_interactions"].get(interaction_id)
                if isinstance(completed, dict):
                    result = copy.deepcopy(completed["result"])
                    result["status"] = "completed"
                    return result
                existing_success = self._event_by_idempotency_key(
                    f"evening_success:{interaction_id}",
                    expected_type="success",
                )
                if existing_success is not None:
                    result = {
                        "status": "completed",
                        "event": existing_success,
                        "text": "Вечернее ретро и успех уже сохранены.",
                    }
                    self._mark_completed(state, interaction_id, result)
                    state["pending_interaction"] = None
                    return result
                if self._same_active_interaction(
                    pending, "evening", interaction_id, local_now
                ):
                    stage = pending["stage"]
                    if stage == "awaiting_activity_gap":
                        stored_report = pending["payload"].get("report_text")
                        if not isinstance(stored_report, str) or not stored_report:
                            raise PersonalEventError(
                                "evening interaction is missing report_text"
                            )
                        return {
                            "workflow": "evening",
                            "text": stored_report,
                            "next_stage": "awaiting_activity_gap",
                        }
                    if stage == "awaiting_evening_answer":
                        return {
                            "workflow": "evening",
                            "text": self.context["questions"]["evening"],
                            "next_stage": "awaiting_evening_answer",
                        }
                    stored = pending["payload"].get("last_response")
                    if isinstance(stored, dict):
                        return copy.deepcopy(stored)
                    raise PersonalEventError(
                        f"evening interaction has no response for stage: {stage}"
                    )
                stage = (
                    "awaiting_activity_gap"
                    if report_text is not None
                    else "awaiting_evening_answer"
                )
                payload = {"success_callback": callback}
                if report_text is not None:
                    payload["report_text"] = report_text
                state["pending_interaction"] = self._new_pending(
                    "evening",
                    interaction_id,
                    stage,
                    now=local_now,
                    expires_in_seconds=6 * 60 * 60,
                    payload=payload,
                )
                if report_text is not None:
                    return {
                        "workflow": "evening",
                        "text": report_text,
                        "next_stage": "awaiting_activity_gap",
                    }
                return {
                    "workflow": "evening",
                    "text": self.context["questions"]["evening"],
                    "next_stage": "awaiting_evening_answer",
                }

        if workflow == "weekly":
            week_label = _iso_week_label(local_now.date())
            interaction_id = f"weekly:{week_label}"
            idempotency_key = f"weekly_reflection:{week_label}"
            with self._state_transaction() as state:
                pending = state.get("pending_interaction")
                if self._active_unrelated_pending(
                    pending,
                    workflow="weekly",
                    interaction_id=interaction_id,
                    now=local_now,
                ):
                    return self._busy_response("weekly", pending)
                existing = self._event_by_idempotency_key(
                    idempotency_key,
                    expected_type="weekly_reflection",
                    week_label=week_label,
                )
                if existing is not None:
                    report = self._weekly_report(
                        report_date=_iso_week_date(week_label),
                        codex_activity_path=codex_activity_path,
                    )
                    result = {
                        "workflow": "weekly",
                        "status": "completed",
                        "interaction_id": interaction_id,
                        "event": existing,
                        "text": report["text"],
                    }
                    self._mark_completed(state, interaction_id, result)
                    pending = state.get("pending_interaction")
                    if (
                        isinstance(pending, dict)
                        and pending.get("interaction_id") == interaction_id
                    ):
                        state["pending_interaction"] = None
                    return result

                _nonempty_string(report_text, "weekly report text")
                if self._same_active_interaction(
                    pending,
                    "weekly",
                    interaction_id,
                    local_now,
                ):
                    stored = pending["payload"].get("last_response")
                    if not isinstance(stored, dict):
                        raise PersonalEventError(
                            "weekly interaction is missing last_response"
                        )
                    return copy.deepcopy(stored)

                response = self._weekly_question_response(
                    report_text,
                    interaction_id,
                )
                payload: dict[str, Any] = {
                    "week_label": week_label,
                    "report_date": local_now.date().isoformat(),
                    "report_text": report_text,
                    "delivered": False,
                    "last_response": copy.deepcopy(response),
                }
                if codex_activity_path is not None:
                    payload["codex_activity_path"] = str(codex_activity_path)
                state["pending_interaction"] = self._new_pending(
                    "weekly",
                    interaction_id,
                    "awaiting_weekly_feeling",
                    now=local_now,
                    expires_in_seconds=6 * 60 * 60,
                    payload=payload,
                )
                return response

        raise PersonalEventError(f"unsupported workflow: {workflow}")

    def _pending_or_status(
        self,
        state: dict[str, Any],
        now: datetime,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        pending = state.get("pending_interaction")
        if not isinstance(pending, dict):
            return None, {"status": "stale", "text": "Нет ожидаемого ответа."}
        expires_at = _parse_aware_datetime(pending.get("expires_at"))
        if not _instant_precedes(now, expires_at):
            state["pending_interaction"] = None
            return None, {
                "status": "expired",
                "text": "Это окно ответа уже завершилось.",
            }
        payload = pending.get("payload", {})
        if (
            (
                pending.get("workflow") == "weekly"
                or payload.get("delivery_managed") is True
            )
            and payload.get("delivered") is not True
        ):
            return None, {
                "status": "stale",
                "text": "Недельный вопрос ещё не был доставлен.",
            }
        return pending, None

    def pending_interaction(
        self,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        local_now = self._local_now(now)
        with self._state_transaction() as state:
            pending, terminal = self._pending_or_status(state, local_now)
            if pending is None:
                return {
                    "pending": False,
                    "status": terminal["status"] if terminal else "none",
                }
            if pending["stage"] == "awaiting_success_action":
                return {
                    "pending": False,
                    "status": "optional_action",
                }
            return {
                "pending": True,
                "workflow": pending["workflow"],
                "stage": pending["stage"],
                "interaction_id": pending["interaction_id"],
                "expires_at": pending["expires_at"],
            }

    def _morning_choices_response(
        self,
        state: dict[str, Any],
        pending: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        choices = _ordered_task_choices(
            copy.deepcopy(self.context["task_choices"]),
        )
        groups = copy.deepcopy(self.context["focus_groups"])
        focus_until = date.fromisoformat(self.context["focus_until"])
        focus_until_human = (
            f"{focus_until.day} "
            f"{RUSSIAN_MONTHS_GENITIVE[focus_until.month]}"
        )
        l1_snapshot = self.context["l1"]["text"]
        blocks = [f"L1 → {l1_snapshot}"]
        for group in groups:
            blocks.append(
                "\n".join(
                    [
                        group["label"],
                        f"L2 → {group['l2']}",
                        (
                            f"Фокус до {focus_until_human} → "
                            f"{group['period_focus']}"
                        ),
                    ]
                )
            )
        blocks.append(
            "Задачи:\n"
            + "\n".join(
                (
                    f"{choice['number']}. "
                    f"{'✅ ' if _task_is_completed(choice) else ''}"
                    f"{choice['label']}"
                )
                for choice in choices
            )
        )
        pending["stage"] = "awaiting_task_choice"
        pending["payload"]["choices_snapshot"] = {
            choice["id"]: copy.deepcopy(choice) for choice in choices
        }
        pending["payload"]["choice_order"] = [
            choice["id"] for choice in choices if not _task_is_completed(choice)
        ]
        pending["payload"]["l1_snapshot"] = l1_snapshot
        state["pending_interaction"] = pending
        response = {
            "workflow": "morning",
            "next_stage": "awaiting_task_choice",
            "text": "\n\n".join(blocks)
            + (
                "\n\nЧто выбираешь сегодня? Ответь одним или несколькими "
                "номерами либо 0."
            ),
        }
        pending["payload"]["choice_response"] = copy.deepcopy(response)
        return response

    def _record_morning_choice(
        self,
        choice_id: str,
        *,
        source: dict[str, Any],
        pending: dict[str, Any] | None,
        choice_snapshot: dict[str, Any] | None = None,
        l1_snapshot: str | None = None,
    ) -> dict[str, Any]:
        return self._record_morning_choices(
            [choice_id],
            source=source,
            pending=pending,
            choice_snapshots=(
                None
                if choice_snapshot is None
                else {choice_id: choice_snapshot}
            ),
            l1_snapshot=l1_snapshot,
        )

    def _record_morning_choices(
        self,
        choice_ids: list[str],
        *,
        source: dict[str, Any],
        pending: dict[str, Any] | None,
        choice_snapshots: dict[str, dict[str, Any]] | None = None,
        l1_snapshot: str | None = None,
    ) -> dict[str, Any]:
        if not choice_ids or ("t0" in choice_ids and choice_ids != ["t0"]):
            return {
                "status": "invalid",
                "text": "Выбери задачи или только 0.",
            }
        no_focus = choice_ids == ["t0"]
        payload = pending.get("payload", {}) if isinstance(pending, dict) else {}
        available_snapshots = payload.get("choices_snapshot", {})
        selected_choices: list[dict[str, Any]] = []
        if not no_focus:
            for choice_id in choice_ids:
                candidate = (
                    (choice_snapshots or {}).get(choice_id)
                    if isinstance(choice_snapshots, dict)
                    else None
                )
                if candidate is None and isinstance(
                    available_snapshots, dict
                ):
                    candidate = available_snapshots.get(choice_id)
                if not isinstance(candidate, dict):
                    return {
                        "status": "stale",
                        "text": "Снимок этой задачи больше недоступен.",
                    }
                if _task_is_completed(candidate):
                    return {
                        "status": "invalid",
                        "text": (
                            f"Задача {candidate['number']} уже выполнена; "
                            "выбери открытую."
                        ),
                    }
                selected_choices.append(copy.deepcopy(candidate))

        shown_l1 = l1_snapshot or payload.get("l1_snapshot")
        if not isinstance(shown_l1, str) or not shown_l1:
            return {
                "status": "stale",
                "text": "Снимок лестницы больше недоступен.",
            }
        if not isinstance(pending, dict):
            return {
                "status": "stale",
                "text": "Утреннее взаимодействие больше не активно.",
            }
        interaction_id = pending["interaction_id"]
        day_results = (
            ["Прожить день без обязательной фокус-задачи"]
            if no_focus
            else [choice["day_result"] for choice in selected_choices]
        )
        first_steps = (
            []
            if no_focus
            else [choice["first_step"] for choice in selected_choices]
        )
        if no_focus:
            day_result = day_results[0]
            first_step = None
        elif len(selected_choices) == 1:
            day_result = day_results[0]
            first_step = first_steps[0]
        else:
            day_result = "\n".join(
                f"{choice['number']}. {result}"
                for choice, result in zip(selected_choices, day_results)
            )
            first_step = "\n".join(
                f"{choice['number']}. {step}"
                for choice, step in zip(selected_choices, first_steps)
            )
        choice_numbers = [
            choice["number"] for choice in selected_choices
        ]
        descriptions = [
            choice["label"] for choice in selected_choices
        ]
        unique_l2 = list(
            dict.fromkeys(choice["l2"] for choice in selected_choices)
        )
        unique_period_focus = list(
            dict.fromkeys(
                choice["period_focus"] for choice in selected_choices
            )
        )
        event = self.store.append_event(
            {
                "type": "morning_intent",
                "idempotency_key": f"morning_intent:{interaction_id}",
                "source": source,
                "self_report": {
                    "no_focus": no_focus,
                    "morning_answer": payload.get("morning_answer"),
                    "control_answer": payload.get("control_answer"),
                },
                "description": (
                    "Сегодня без фокус-задачи"
                    if no_focus
                    else "; ".join(descriptions)
                ),
                "links": {
                    "active_context": str(self.context_path),
                    "choice_id": choice_ids[0],
                    "choice_ids": choice_ids,
                    "choice_numbers": choice_numbers,
                    "l1": shown_l1,
                    "l2": None if no_focus else " / ".join(unique_l2),
                    "period_focus": (
                        None
                        if no_focus
                        else " / ".join(unique_period_focus)
                    ),
                    "day_result": day_result,
                    "day_results": day_results,
                    "first_step": first_step,
                    "first_steps": first_steps,
                },
            }
        )
        stored_links = event.get("links", {})
        stored_choice_ids = stored_links.get("choice_ids")
        if not isinstance(stored_choice_ids, list):
            stored_choice_ids = [stored_links.get("choice_id")]
        stored_day_result = stored_links.get("day_result")
        stored_first_step = stored_links.get("first_step")
        status = (
            "recorded"
            if stored_choice_ids == choice_ids
            else "already_recorded"
        )
        if not no_focus and len(selected_choices) > 1:
            text = (
                "Выбрано:\n"
                + "\n".join(
                    f"{choice['number']}. {choice['label']}"
                    for choice in selected_choices
                )
                + "\n\nРезультаты дня:\n"
                + day_result
                + "\n\nПервые шаги:\n"
                + (first_step or "")
            )
        else:
            text = (
                f"Результат дня: {stored_day_result}"
                + (
                    f"\nПервый шаг: {stored_first_step}"
                    if stored_first_step
                    else ""
                )
            )
        return {
            "status": status,
            "event": event,
            "day_result": stored_day_result,
            "day_results": stored_links.get("day_results", [stored_day_result]),
            "first_step": stored_first_step,
            "first_steps": stored_links.get(
                "first_steps",
                [] if stored_first_step is None else [stored_first_step],
            ),
            "text": text,
        }

    def _remember_reply(
        self,
        state: dict[str, Any],
        message_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        state["replies"][message_id] = {"result": copy.deepcopy(result)}
        return result

    def route_reply(
        self,
        text: str,
        *,
        message_id: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        _nonempty_string(text, "reply")
        _nonempty_string(message_id, "message_id")
        local_now = self._local_now(now)
        with self._state_transaction() as state:
            cached = state["replies"].get(message_id)
            if isinstance(cached, dict) and isinstance(cached.get("result"), dict):
                return copy.deepcopy(cached["result"])

            pending, terminal = self._pending_or_status(state, local_now)
            if terminal is not None:
                return terminal
            assert pending is not None
            stage = pending["stage"]
            payload = pending["payload"]

            if stage == "awaiting_weekly_feeling":
                week_label = payload.get("week_label")
                report_date = payload.get("report_date")
                _iso_week_date(week_label)
                if not isinstance(report_date, str):
                    raise PersonalEventError(
                        "weekly interaction is missing report_date"
                    )
                idempotency_key = f"weekly_reflection:{week_label}"
                existing = self._event_by_idempotency_key(
                    idempotency_key,
                    expected_type="weekly_reflection",
                    week_label=week_label,
                )
                event = self.store.append_event(
                    {
                        "type": "weekly_reflection",
                        "idempotency_key": idempotency_key,
                        "occurred_at": local_now.isoformat(timespec="seconds"),
                        "source": {
                            "channel": "telegram",
                            "message_id": message_id,
                        },
                        "self_report": {
                            "week_label": week_label,
                            "final_feeling": text.strip(),
                        },
                        "description": text.strip(),
                    }
                )
                event = self._require_expected_event(
                    event,
                    idempotency_key=idempotency_key,
                    expected_type="weekly_reflection",
                    week_label=week_label,
                )
                result = {
                    "workflow": "weekly",
                    "status": (
                        "already_recorded"
                        if existing is not None
                        else "recorded"
                    ),
                    "event": event,
                    "text": "Итоговое ощущение недели сохранено.",
                }
                self._mark_completed(
                    state,
                    pending["interaction_id"],
                    result,
                )
                state["pending_interaction"] = None
                return self._remember_reply(state, message_id, result)

            if stage == "awaiting_activity_gap":
                interaction_id = pending["interaction_id"]
                payload["activity_gap_answer"] = text.strip()
                self._record_activity_gap_checkins(
                    interaction_id=interaction_id,
                    text=text,
                    message_id=message_id,
                    now=local_now,
                )
                total = self._daily_viability_total(local_now)
                signed_total = f"{total:+d}" if total else "0"
                reaction = _viability_total_reaction(total)
                response_parts = [f"Сумма ЖС за день: {signed_total}."]
                if reaction is not None:
                    response_parts.append(reaction)
                response_parts.append(self.context["questions"]["evening"])
                pending["stage"] = "awaiting_evening_answer"
                result = {
                    "workflow": "evening",
                    "text": "\n\n".join(response_parts),
                    "next_stage": "awaiting_evening_answer",
                }
                return self._remember_reply(state, message_id, result)

            if stage == "awaiting_morning_answer":
                payload["morning_answer"] = text.strip()
                pending["stage"] = "awaiting_control_answer"
                result = self._morning_control_response()
                return self._remember_reply(state, message_id, result)

            if stage == "awaiting_control_answer":
                payload["control_answer"] = text.strip()
                result = self._morning_choices_response(
                    state, pending, local_now
                )
                return self._remember_reply(state, message_id, result)

            if stage == "awaiting_viability_context":
                pulse_id = payload.get("pulse_id")
                checkin_event_id = payload.get("checkin_event_id")
                if not isinstance(pulse_id, str) or not isinstance(
                    checkin_event_id, str
                ):
                    return {
                        "status": "stale",
                        "text": "Исходный срез больше недоступен.",
                    }
                stripped = text.strip()
                result = self._record_viability_context(
                    pulse_id=pulse_id,
                    checkin_event_id=checkin_event_id,
                    context_status="provided",
                    context=stripped,
                    description=stripped,
                    source={
                        "channel": "telegram",
                        "message_id": message_id,
                    },
                )
                if result.get("status") in {
                    "recorded",
                    "already_recorded",
                }:
                    state["pending_interaction"] = None
                    return self._remember_reply(state, message_id, result)
                return result

            if stage == "awaiting_task_choice":
                numbers = _parse_morning_choice_numbers(text)
                if numbers is None or (0 in numbers and numbers != [0]):
                    return {
                        "status": "invalid",
                        "text": (
                            "Ответь одним или несколькими номерами задач "
                            "либо только 0."
                        ),
                    }
                snapshots = payload.get("choices_snapshot", {})
                if not isinstance(snapshots, dict):
                    return {
                        "status": "stale",
                        "text": "Снимок задач больше недоступен.",
                    }
                choices_by_number = {
                    choice.get("number"): choice_id
                    for choice_id, choice in snapshots.items()
                    if isinstance(choice, dict)
                }
                if numbers == [0]:
                    choice_ids = ["t0"]
                else:
                    unknown = [
                        number
                        for number in numbers
                        if number not in choices_by_number
                    ]
                    if unknown:
                        return {
                            "status": "invalid",
                            "text": (
                                "Нет задач с номерами: "
                                + ", ".join(str(number) for number in unknown)
                                + "."
                            ),
                        }
                    completed = [
                        number
                        for number in numbers
                        if _task_is_completed(
                            snapshots[choices_by_number[number]]
                        )
                    ]
                    if completed:
                        noun = "Задача" if len(completed) == 1 else "Задачи"
                        verb = "уже выполнена" if len(completed) == 1 else "уже выполнены"
                        return {
                            "status": "invalid",
                            "text": (
                                f"{noun} "
                                + ", ".join(str(number) for number in completed)
                                + f" {verb}; выбери открытые."
                            ),
                        }
                    choice_ids = [
                        choices_by_number[number] for number in numbers
                    ]
                result = self._record_morning_choices(
                    choice_ids,
                    source={"channel": "telegram", "message_id": message_id},
                    pending=pending,
                )
                if result.get("status") in {"recorded", "already_recorded"}:
                    completion = self._morning_completion(result["event"])
                    self._mark_completed(
                        state,
                        pending["interaction_id"],
                        completion,
                    )
                    state["pending_interaction"] = None
                    self._remember_reply(state, message_id, result)
                return result

            if stage == "awaiting_evening_answer":
                interaction_id = pending["interaction_id"]
                event = self.store.append_event(
                    {
                        "type": "evening_reflection",
                        "idempotency_key": (
                            f"evening_reflection:{interaction_id}"
                        ),
                        "source": {
                            "channel": "telegram",
                            "message_id": message_id,
                        },
                        "self_report": {
                            "activity_gap_answer": payload.get(
                                "activity_gap_answer"
                            )
                        },
                        "description": text.strip(),
                    }
                )
                callback_data = payload.get("success_callback")
                if not isinstance(callback_data, str):
                    raise PersonalEventError(
                        "evening interaction is missing success_callback"
                    )
                pending["stage"] = "awaiting_success_action"
                self._add_callbacks(
                    state,
                    [callback_data],
                    workflow="evening",
                    now=local_now,
                    expires_in_seconds=6 * 60 * 60,
                    metadata={
                        callback_data: {
                            "interaction_id": interaction_id
                        }
                    },
                )
                success_text = (
                    "Ретро сохранено. Не обесценивай пройденное: если "
                    "хочется, добавь один сегодняшний успех."
                )
                candidates = self._ideas_for_evening(local_now)
                ideas = []
                for idea in candidates:
                    existing_evidence = self._idea_existing_evidence(
                        idea,
                        now=local_now,
                    )
                    if existing_evidence is None:
                        ideas.append(idea)
                        continue
                    self._promote_idea(
                        idea,
                        result_text=existing_evidence,
                        source={
                            "channel": "agent",
                            "operation": "evening_idea_preflight",
                        },
                        now=local_now,
                    )
                if ideas:
                    pending["stage"] = "awaiting_idea_result"
                    payload["idea_queue"] = [idea["id"] for idea in ideas]
                    payload["idea_index"] = 0
                    payload["ideas_completed"] = 0
                    idea_prompt = self._idea_followthrough_prompt(ideas[0])
                    result = {
                        "status": "recorded",
                        "event": event,
                        "next_stage": "awaiting_idea_result",
                        "text": f"{success_text}\n\n{idea_prompt}",
                        "buttons": [
                            self._button(
                                "Добавить успех",
                                "add_success",
                                callback_data,
                            )
                        ],
                    }
                else:
                    pending["stage"] = "awaiting_success_action"
                    result = {
                        "status": "recorded",
                        "event": event,
                        "next_stage": "awaiting_success_action",
                        "text": success_text,
                        "buttons": [
                            self._button(
                                "Добавить успех",
                                "add_success",
                                callback_data,
                            )
                        ],
                    }
                payload["last_response"] = copy.deepcopy(result)
                return self._remember_reply(state, message_id, result)

            if stage == "awaiting_success_reply":
                interaction_id = pending["interaction_id"]
                event = self.store.append_event(
                    {
                        "type": "success",
                        "idempotency_key": (
                            f"evening_success:{interaction_id}"
                        ),
                        "source": {
                            "channel": "telegram",
                            "message_id": message_id,
                        },
                        "description": text.strip(),
                    }
                )
                success_text = (
                    "Успех сохранён. Это не мелочь — это часть твоего пути."
                )
                if payload.pop("resume_stage", None) == "awaiting_idea_result":
                    queue = payload.get("idea_queue", [])
                    index = payload.get("idea_index", 0)
                    idea = (
                        self._idea_by_id(queue[index])
                        if isinstance(queue, list)
                        and isinstance(index, int)
                        and 0 <= index < len(queue)
                        else None
                    )
                    if idea is None:
                        raise PersonalEventError(
                            "evening idea queue lost its current idea"
                        )
                    pending["stage"] = "awaiting_idea_result"
                    result = {
                        "status": "recorded",
                        "event": event,
                        "next_stage": "awaiting_idea_result",
                        "text": (
                            f"{success_text}\n\n"
                            f"{self._idea_followthrough_prompt(idea)}"
                        ),
                    }
                else:
                    result = {
                        "status": "recorded",
                        "event": event,
                        "text": success_text,
                    }
                callback_data = payload.get("success_callback")
                if isinstance(callback_data, str):
                    callback = state["callbacks"].get(callback_data)
                    if isinstance(callback, dict):
                        callback["result"] = copy.deepcopy(result)
                if pending["stage"] != "awaiting_idea_result":
                    self._mark_completed(
                        state,
                        interaction_id,
                        result,
                    )
                    state["pending_interaction"] = None
                return self._remember_reply(state, message_id, result)

            if stage == "awaiting_idea_result":
                queue = payload.get("idea_queue")
                index = payload.get("idea_index")
                if (
                    not isinstance(queue, list)
                    or not isinstance(index, int)
                    or not 0 <= index < len(queue)
                ):
                    raise PersonalEventError(
                        "evening interaction has an invalid idea queue"
                    )
                idea = self._idea_by_id(queue[index])
                if idea is None:
                    raise PersonalEventError(
                        "evening idea queue lost its current idea"
                    )
                if not self._idea_result_has_artifact(text):
                    result = {
                        "status": "waiting",
                        "next_stage": "awaiting_idea_result",
                        "text": (
                            "Пока не вижу материального первого следа. "
                            "Сделай один маленький результат сейчас.\n\n"
                            f"{self._idea_followthrough_prompt(idea)}"
                        ),
                    }
                    payload["last_response"] = copy.deepcopy(result)
                    return self._remember_reply(state, message_id, result)
                promoted = self._promote_idea(
                    idea,
                    result_text=text,
                    source={
                        "channel": "telegram",
                        "message_id": message_id,
                    },
                    now=local_now,
                )
                payload["ideas_completed"] = int(
                    payload.get("ideas_completed", 0)
                ) + 1
                payload["idea_index"] = index + 1
                if payload["idea_index"] < len(queue):
                    next_idea = self._idea_by_id(queue[payload["idea_index"]])
                    if next_idea is None:
                        raise PersonalEventError(
                            "evening idea queue lost its next idea"
                        )
                    if promoted["task"].get("status") == "completed":
                        idea_result_text = (
                            "Результат идеи зафиксирован; задача "
                            f"{promoted['task']['number']} отмечена "
                            "выполненной."
                        )
                    else:
                        idea_result_text = (
                            "Первичный шаг зафиксирован; задача "
                            f"{promoted['task']['number']} добавлена."
                        )
                    result = {
                        "status": "recorded",
                        "task": promoted["task"],
                        "next_stage": "awaiting_idea_result",
                        "text": (
                            f"{idea_result_text}\n\n"
                            f"{self._idea_followthrough_prompt(next_idea)}"
                        ),
                    }
                    payload["last_response"] = copy.deepcopy(result)
                    return self._remember_reply(state, message_id, result)
                result = {
                    "status": "recorded",
                    "task": promoted["task"],
                    "text": (
                        "Идея уже реализована: результат сохранён, "
                        "задача отмечена выполненной."
                        if promoted["task"].get("status") == "completed"
                        else self._idea_completion_text(
                            payload["ideas_completed"]
                        )
                    ),
                }
                self._mark_completed(
                    state,
                    pending["interaction_id"],
                    result,
                )
                state["pending_interaction"] = None
                return self._remember_reply(state, message_id, result)

            if stage == "awaiting_success_action":
                return {
                    "status": "waiting",
                    "text": "Нажми «Добавить успех», если хочешь его записать.",
                }

            return {
                "status": "stale",
                "text": "Этот ответ больше не ожидается.",
            }

    def route_callback(
        self,
        callback_data: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        _nonempty_string(callback_data, "callback_data")
        local_now = self._local_now(now)
        with self._state_transaction() as state:
            callback = state.get("callbacks", {}).get(callback_data)
            if not isinstance(callback, dict):
                return {
                    "status": "stale",
                    "text": "Эта кнопка больше не активна.",
                }
            workflow = callback.get("workflow")
            if (
                workflow != "viability_context"
                and isinstance(callback.get("result"), dict)
            ):
                return copy.deepcopy(callback["result"])
            expires_at = _parse_aware_datetime(callback.get("expires_at"))
            if not _instant_precedes(local_now, expires_at):
                return {
                    "status": "expired",
                    "text": "Срок действия этой кнопки истёк.",
                }

            metadata = callback.get("metadata", {})
            pending = state.get("pending_interaction")
            if workflow == "viability":
                pulse_id = metadata.get("pulse_id")
                pulse = state["pulses"].get(pulse_id)
                if not isinstance(pulse, dict):
                    raise PersonalEventError(
                        f"viability callback has no pulse: {pulse_id}"
                )
                if isinstance(pulse.get("result"), dict):
                    existing = copy.deepcopy(pulse["result"])
                    result = self._viability_delta_response(
                        state,
                        event=existing["event"],
                        pulse_id=pulse_id,
                        status="already_recorded",
                    )
                else:
                    requested_delta = metadata.get("delta")
                    event = self.store.append_event(
                        {
                            "type": "viability_checkin",
                            "idempotency_key": f"viability:{pulse_id}",
                            "source": {
                                "channel": "telegram",
                                "callback_data": callback_data,
                            },
                            "self_report": {"delta": requested_delta},
                            "description": "Дневной срез жизнеспособности",
                            "links": {"slot": metadata.get("slot")},
                        }
                    )
                    stored_delta = event["self_report"]["delta"]
                    status = (
                        "recorded"
                        if stored_delta == requested_delta
                        else "already_recorded"
                    )
                    result = self._viability_delta_response(
                        state,
                        event=event,
                        pulse_id=pulse_id,
                        status=status,
                    )
                    pulse["result"] = copy.deepcopy(result)
            elif workflow == "viability_context":
                return self._route_viability_context_callback(
                    state,
                    callback_data,
                    callback,
                    local_now,
                )
            elif workflow == "morning":
                expected_interaction_id = metadata.get("interaction_id")
                if (
                    not isinstance(pending, dict)
                    or pending.get("workflow") != "morning"
                    or pending.get("stage") != "awaiting_task_choice"
                    or pending.get("interaction_id")
                    != expected_interaction_id
                ):
                    return {
                        "status": "stale",
                        "text": "Этот утренний выбор больше не активен.",
                    }
                result = self._record_morning_choice(
                    metadata.get("choice_id"),
                    source={
                        "channel": "telegram",
                        "callback_data": callback_data,
                    },
                    pending=pending,
                    choice_snapshot=metadata.get("choice_snapshot"),
                    l1_snapshot=metadata.get("l1_snapshot"),
                )
                if result.get("status") in {"recorded", "already_recorded"}:
                    completion = self._morning_completion(result["event"])
                    self._mark_completed(
                        state,
                        pending["interaction_id"],
                        completion,
                    )
                    state["pending_interaction"] = None
            elif workflow == "evening":
                expected_interaction_id = metadata.get("interaction_id")
                if (
                    not isinstance(pending, dict)
                    or pending.get("workflow") != "evening"
                    or pending.get("interaction_id")
                    != expected_interaction_id
                    or pending.get("stage")
                    not in {
                        "awaiting_success_action",
                        "awaiting_idea_result",
                    }
                    or not _instant_precedes(
                        local_now,
                        _parse_aware_datetime(pending.get("expires_at")),
                    )
                ):
                    return {
                        "status": "stale",
                        "text": "Эта вечерняя кнопка больше не активна.",
                    }
                if pending["stage"] == "awaiting_idea_result":
                    pending["payload"]["resume_stage"] = (
                        "awaiting_idea_result"
                    )
                pending["stage"] = "awaiting_success_reply"
                pending["payload"]["success_callback"] = callback_data
                result = {
                    "status": "waiting",
                    "next_stage": "awaiting_success_reply",
                    "text": "Какой сегодняшний успех ты хочешь признать?",
                }
                pending["payload"]["last_response"] = copy.deepcopy(result)
            else:
                return {
                    "status": "stale",
                    "text": "Неизвестный тип кнопки.",
                }

            callback["result"] = copy.deepcopy(result)
            state["callbacks"][callback_data] = callback
            return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--events-path", type=Path)
    parser.add_argument("--state-path", type=Path)
    parser.add_argument("--context-path", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)

    append_parser = commands.add_parser("append", help="Append one JSON event")
    append_parser.add_argument(
        "--event-json",
        required=True,
        help="Event object encoded as JSON",
    )
    capture_parser = commands.add_parser(
        "capture",
        help="Capture one Telegram idea, success, or occasion",
    )
    capture_parser.add_argument(
        "--type",
        dest="event_type",
        required=True,
        choices=("idea", "success", "occasion"),
    )
    capture_text = capture_parser.add_mutually_exclusive_group(required=True)
    capture_text.add_argument("--text")
    capture_text.add_argument("--text-base64")
    capture_parser.add_argument("--message-id", required=True)

    prepare_parser = commands.add_parser(
        "prepare",
        help="Prepare a deterministic Telegram workflow response",
    )
    prepare_parser.add_argument(
        "workflow",
        choices=("morning", "viability", "evening"),
    )
    prepare_parser.add_argument("--at", help="Aware ISO date-time for testing")
    prepare_parser.add_argument(
        "--compact",
        action="store_true",
        help="Jump directly to the morning task choices",
    )

    route_reply_parser = commands.add_parser(
        "route-reply",
        help="Route text to the currently pending personal interaction",
    )
    route_text = route_reply_parser.add_mutually_exclusive_group(required=True)
    route_text.add_argument("--text")
    route_text.add_argument("--text-base64")
    route_reply_parser.add_argument("--message-id", required=True)
    route_reply_parser.add_argument("--at", help="Aware ISO date-time for testing")

    route_callback_parser = commands.add_parser(
        "route-callback",
        help="Route one pd:* Telegram callback",
    )
    route_callback_parser.add_argument("--data", required=True)
    route_callback_parser.add_argument(
        "--at",
        help="Aware ISO date-time for testing",
    )

    pending_parser = commands.add_parser(
        "pending",
        help="Report whether a personal interaction is waiting for a reply",
    )
    pending_parser.add_argument("--at", help="Aware ISO date-time for testing")

    dispatch_parser = commands.add_parser(
        "dispatch",
        help="Prepare and send one scheduled OpenClaw Telegram message",
    )
    dispatch_parser.add_argument(
        "workflow",
        choices=("morning", "viability", "evening", "weekly"),
    )
    dispatch_parser.add_argument("--target")
    dispatch_parser.add_argument("--at", help="Aware ISO date-time for testing")
    dispatch_parser.add_argument("--codex-activity", type=Path)
    dispatch_parser.add_argument("--openclaw-bin", default="openclaw")
    dispatch_parser.add_argument("--dry-run", action="store_true")

    context_parser = commands.add_parser(
        "context",
        help="Build a morning, evening, or weekly context",
    )
    context_parser.add_argument(
        "context_kind",
        choices=("morning", "evening", "weekly"),
    )
    context_parser.add_argument(
        "--date",
        dest="report_date",
        help="Local calendar date (YYYY-MM-DD)",
    )
    context_parser.add_argument("--codex-activity", type=Path)
    refresh_parser = commands.add_parser(
        "refresh-context",
        help="Apply the latest 1:1 summary to the daily context",
    )
    refresh_parser.add_argument(
        "--at",
        help="Aware ISO date-time for testing",
    )
    commands.add_parser(
        "render",
        help="Materialize private Markdown reading views",
    )
    commands.add_parser("validate", help="Validate the complete event log")
    return parser


def _interaction_time(value: str | None, timezone: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    parsed = _parse_aware_datetime(value)
    return parsed.astimezone(timezone)


def _command_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        text = args.text
    else:
        try:
            raw = base64.b64decode(args.text_base64, validate=True)
            text = raw.decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
            raise PersonalEventError(
                "--text-base64 must be valid Base64-encoded UTF-8"
            ) from exc
    _nonempty_string(text, "text")
    return text


def _print_json(value: Any, *, file: Any = sys.stdout) -> None:
    print(_strict_json_dumps(value), file=file)


@contextmanager
def _dispatch_lock(lock_path: Path) -> Iterable[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    os.fchmod(lock_fd, 0o600)
    with os.fdopen(lock_fd, "a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _dispatch_lifecycle(
    args: argparse.Namespace,
    store: PersonalEventStore,
    *,
    target: str,
    state_path: Path | None,
    context_path: Path,
    reports_root: Path | None = None,
) -> dict[str, Any]:
    dispatch_timezone = ZoneInfo(DEFAULT_TIMEZONE)
    requested_now = _interaction_time(args.at, dispatch_timezone)
    dispatch_now = requested_now or datetime.now(dispatch_timezone)
    service = PersonalDailyService(
        repo_root=store.repo_root,
        events_path=store.events_path,
        state_path=state_path,
        context_path=context_path,
        data_dir=store.data_dir,
    )
    local_now = service._local_now(dispatch_now)
    # Attaching activity is explicit; do not reuse a stale manifest after opt-out.
    activity_path = args.codex_activity
    if args.workflow == "evening":
        reporter = PersonalReportService(
            repo_root=store.repo_root,
            events_path=store.events_path,
            data_dir=store.data_dir,
            reports_root=reports_root,
        )
        report = reporter.write_evening_report(
            local_now.date(),
            codex_activity_path=activity_path,
        )
        response = service.prepare(
            "evening",
            now=local_now,
            report_text=report["text"],
        )
    elif args.workflow == "weekly":
        reporter = PersonalReportService(
            repo_root=store.repo_root,
            events_path=store.events_path,
            data_dir=store.data_dir,
            reports_root=reports_root,
        )
        report = reporter.write_weekly_report(
            local_now.date(),
            codex_activity_path=activity_path,
        )
        response = service.prepare(
            "weekly",
            now=local_now,
            report_text=report["text"],
            codex_activity_path=activity_path,
        )
    else:
        response = service.prepare(args.workflow, now=local_now)
    if response.get("status") in {"skipped", "busy"}:
        result = {
            "valid": True,
            "workflow": args.workflow,
            "response": response,
            "delivery": {
                "status": "skipped",
                "reason": response.get("reason"),
            },
        }
        return result
    expected_interaction_id = response.get("interaction_id")
    if not isinstance(expected_interaction_id, str):
        daily_slot = {
            "morning": "08",
            "evening": "22",
        }.get(args.workflow)
        if daily_slot is not None:
            expected_interaction_id = (
                f"{local_now.date().isoformat()}:{daily_slot}"
            )
    interaction_id = (
        service.begin_delivery_attempt(
            args.workflow,
            expected_interaction_id,
        )
        if isinstance(expected_interaction_id, str)
        else None
    )
    try:
        delivery = send_openclaw_response(
            response,
            target=target,
            dry_run=args.dry_run,
            openclaw_bin=args.openclaw_bin,
        )
    except (PersonalEventError, OSError):
        if isinstance(interaction_id, str):
            service.discard_undelivered_interaction(
                args.workflow,
                interaction_id,
            )
        raise
    if isinstance(interaction_id, str):
        service.mark_interaction_delivered(
            args.workflow,
            interaction_id,
        )
    result = {
        "valid": True,
        "workflow": args.workflow,
        "response": response,
        "delivery": delivery,
    }
    return result


def _dispatch_command(
    args: argparse.Namespace,
    store: PersonalEventStore,
    *,
    state_path: Path | None,
    context_path: Path,
    reports_root: Path | None = None,
) -> dict[str, Any]:
    target = args.target or os.environ.get("PDS_TELEGRAM_TARGET")
    _nonempty_string(target, "telegram target")
    resolved_state_path = (
        Path(state_path)
        if state_path is not None
        else store.data_dir / "state.json"
    )
    with _dispatch_lock(resolved_state_path.parent / ".dispatch.lock"):
        return _dispatch_lifecycle(
            args,
            store,
            target=target,
            state_path=state_path,
            context_path=context_path,
            reports_root=reports_root,
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = PersonalEventStore(
            repo_root=args.repo_root,
            events_path=args.events_path,
            data_dir=args.data_dir,
        )
        if args.command == "append":
            try:
                event = json.loads(
                    args.event_json,
                    parse_constant=_reject_json_constant,
                )
            except json.JSONDecodeError as exc:
                raise PersonalEventError(f"--event-json is invalid JSON: {exc.msg}") from exc
            if not isinstance(event, dict):
                raise PersonalEventError("--event-json must encode an object")
            _print_json(store.append_event(event))
            return 0

        if args.command == "capture":
            captured_text = _command_text(args)
            _nonempty_string(args.message_id, "message_id")
            event = store.append_event(
                {
                    "type": args.event_type,
                    "idempotency_key": (
                        f"telegram:{args.message_id}:{args.event_type}"
                    ),
                    "source": {
                        "channel": "telegram",
                        "message_id": args.message_id,
                    },
                    "description": captured_text.strip(),
                }
            )
            render_reading_views(
                store.data_dir,
                store.load_materialized_events(),
            )
            _print_json(
                {
                    **event,
                    "status": "recorded",
                    "event": event,
                    "text": (
                        "Идея сохранена."
                        if args.event_type == "idea"
                        else "Успех сохранён."
                        if args.event_type == "success"
                        else "Повод сохранён."
                    ),
                }
            )
            return 0

        if args.command == "refresh-context":
            context_path = (
                args.context_path
                if args.context_path is not None
                else store.repo_root / DEFAULT_CONTEXT_RELATIVE
            )
            refresh_now = _interaction_time(
                args.at,
                ZoneInfo(DEFAULT_TIMEZONE),
            )
            context_result = refresh_active_context_from_latest_summary(
                repo_root=store.repo_root,
                context_path=context_path,
                now=refresh_now,
            )
            _print_json(context_result)
            return 0

        if args.command in {
            "prepare",
            "route-reply",
            "route-callback",
            "pending",
            "dispatch",
        }:
            if args.command == "dispatch":
                context_path = (
                    args.context_path
                    if args.context_path is not None
                    else store.repo_root / DEFAULT_CONTEXT_RELATIVE
                )
                if args.dry_run:
                    with tempfile.TemporaryDirectory(
                        prefix="personal-daily-preview-"
                    ) as preview:
                        preview_root = Path(preview)
                        preview_events_path = preview_root / "events.jsonl"
                        if store.events_path.exists():
                            preview_events_path.write_bytes(
                                store.events_path.read_bytes()
                            )
                        preview_store = PersonalEventStore(
                            repo_root=store.repo_root,
                            events_path=preview_events_path,
                            data_dir=preview_root,
                        )
                        result = _dispatch_command(
                            args,
                            preview_store,
                            state_path=preview_root / "state.json",
                            context_path=context_path,
                            reports_root=preview_root / "reports",
                        )
                else:
                    result = _dispatch_command(
                        args,
                        store,
                        state_path=args.state_path,
                        context_path=context_path,
                    )
                _print_json(result)
                return 0

            service = PersonalDailyService(
                repo_root=args.repo_root,
                events_path=args.events_path,
                state_path=args.state_path,
                context_path=args.context_path,
                data_dir=args.data_dir,
            )
            now = _interaction_time(args.at, service.timezone)

            if args.command == "prepare":
                _print_json(
                    service.prepare(
                        args.workflow,
                        now=now,
                        compact=args.compact,
                    )
                )
                return 0
            if args.command == "route-reply":
                reply_text = _command_text(args)
                _print_json(
                    service.route_reply(
                        reply_text,
                        message_id=args.message_id,
                        now=now,
                    )
                )
                return 0
            if args.command == "route-callback":
                _print_json(service.route_callback(args.data, now=now))
                return 0
            if args.command == "pending":
                _print_json(service.pending_interaction(now=now))
                return 0

        if args.command == "validate":
            _print_json({"valid": True, "event_count": store.validate_log()})
            return 0

        if args.command == "render":
            materialized = store.load_materialized_events()
            paths = render_reading_views(store.data_dir, materialized)
            _print_json(
                {
                    "valid": True,
                    "materialized_event_count": len(materialized),
                    "paths": paths,
                }
            )
            return 0

        if args.command == "context":
            if args.context_kind == "morning":
                service = PersonalDailyService(
                    repo_root=args.repo_root,
                    events_path=args.events_path,
                    state_path=args.state_path,
                    context_path=args.context_path,
                    data_dir=args.data_dir,
                )
                now = None
                if args.report_date is not None:
                    local_date = _report_date(args.report_date, service.timezone)
                    now = datetime.combine(
                        local_date,
                        time(hour=8),
                        tzinfo=service.timezone,
                    )
                _print_json(service.prepare("morning", now=now))
                return 0

            reporter = PersonalReportService(
                repo_root=args.repo_root,
                events_path=args.events_path,
                data_dir=args.data_dir,
            )
            if args.context_kind == "evening":
                result = reporter.write_evening_report(
                    args.report_date,
                    codex_activity_path=args.codex_activity,
                )
            else:
                result = reporter.write_weekly_report(
                    args.report_date,
                    codex_activity_path=args.codex_activity,
                )
            _print_json(
                {
                    "valid": True,
                    "path": str(result["path"]),
                    "text": result["text"],
                }
            )
            return 0
    except (PersonalEventError, OSError, UnicodeError) as exc:
        _print_json({"valid": False, "error": str(exc)}, file=sys.stderr)
        return 1

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
