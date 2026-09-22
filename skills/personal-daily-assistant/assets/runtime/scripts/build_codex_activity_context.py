#!/usr/bin/env python3
"""Build a compact activity manifest from explicitly selected Codex exports.

Includes excerpts of user/assistant text and paths. Pattern filtering is not
a privacy guarantee; review input copies before enabling downstream delivery.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = os.environ.get("PDS_TIMEZONE", "UTC")
DEFAULT_MAX_CHARS = 6500
PROMPT_LIMIT = 240
RESULT_LIMIT = 480
MAX_TURNS_PER_SESSION = 2


@dataclass
class TurnActivity:
    timestamp: datetime
    request: str
    status: str
    result: str = ""
    reason: str = ""
    tools: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)


@dataclass
class SessionActivity:
    session_id: str
    title: str
    cwd: str
    turns: list[TurnActivity]


@dataclass
class ScanResult:
    sessions: list[SessionActivity]
    scanned_files: int = 0
    excluded_subagents: int = 0
    invalid_lines: int = 0


@dataclass
class _OpenTurn:
    timestamp: datetime
    request: str
    last_agent_message: str = ""
    tools: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)


SECRET_PATTERNS = (
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "sk-[REDACTED]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\bpostgres(?:ql)?://[^\s)\]>'\"]+"), "postgresql://[REDACTED]"),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|token|secret|password|authorization|cookie)\b"
            r"(\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
        ),
        r"\1\2[REDACTED]",
    ),
)

NOISY_BLOCK_PATTERN = re.compile(
    r"<(environment_context|recommended_plugins)>.*?</\1>", re.IGNORECASE | re.DOTALL
)
PATCH_PATH_PATTERN = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)
NESTED_TOOL_PATTERN = re.compile(r"\btools\.([A-Za-z][A-Za-z0-9_]*)\s*\(")
HEARTBEAT_ID_PATTERN = re.compile(
    r"<automation_id>\s*([^<]+?)\s*</automation_id>", re.IGNORECASE
)
HEARTBEAT_DECISION_PATTERN = re.compile(
    r"<decision>\s*([^<]+?)\s*</decision>", re.IGNORECASE
)
HEARTBEAT_MESSAGE_PATTERN = re.compile(
    r"<message>\s*(.*?)\s*</message>", re.IGNORECASE | re.DOTALL
)
REQUEST_MARKER = "## My request for Codex:"
TECHNICAL_SESSION_PREFIXES = (
    "conversation info (untrusted metadata):",
    "[cron:",
)


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed


def resolve_window(
    *,
    single_date: str | None,
    date_from: str | None,
    date_to: str | None,
    timezone_name: str,
) -> tuple[datetime, datetime]:
    timezone = ZoneInfo(timezone_name)
    if single_date and (date_from or date_to):
        raise ValueError("--date cannot be combined with --from/--to")
    if bool(date_from) != bool(date_to):
        raise ValueError("--from and --to must be provided together")

    if single_date:
        start_date = date.fromisoformat(single_date)
        end_date = start_date + timedelta(days=1)
    elif date_from and date_to:
        start_date = date.fromisoformat(date_from)
        end_date = date.fromisoformat(date_to)
        if end_date <= start_date:
            raise ValueError("--to must be later than --from")
    else:
        start_date = datetime.now(timezone).date()
        end_date = start_date + timedelta(days=1)

    return (
        datetime.combine(start_date, time.min, tzinfo=timezone),
        datetime.combine(end_date, time.min, tzinfo=timezone),
    )


def redact_text(text: str) -> str:
    redacted = text
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def compact_text(text: Any, limit: int) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = NOISY_BLOCK_PATTERN.sub(" ", text)
    cleaned = redact_text(" ".join(cleaned.split()))
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def normalize_user_message(text: Any) -> str:
    """Keep the user's intent while dropping recurring UI and automation wrappers."""
    if not isinstance(text, str):
        return ""
    if "<heartbeat" in text.lower():
        match = HEARTBEAT_ID_PATTERN.search(text)
        if match:
            return compact_text(f"Heartbeat: {match.group(1)}", PROMPT_LIMIT)
        return "Heartbeat automation run"
    if REQUEST_MARKER in text:
        text = text.split(REQUEST_MARKER, 1)[1]
    return compact_text(text, PROMPT_LIMIT)


def normalize_agent_message(text: Any) -> str:
    """Compact terminal output, including heartbeat XML envelopes."""
    if not isinstance(text, str):
        return ""
    if "<heartbeat" in text.lower():
        decision_match = HEARTBEAT_DECISION_PATTERN.search(text)
        message_match = HEARTBEAT_MESSAGE_PATTERN.search(text)
        decision = compact_text(decision_match.group(1), 40) if decision_match else ""
        message = compact_text(message_match.group(1), RESULT_LIMIT) if message_match else ""
        if decision and message:
            return compact_text(f"{decision}: {message}", RESULT_LIMIT)
        return message or decision or "Heartbeat result"
    return compact_text(text, RESULT_LIMIT)


def load_session_index(codex_home: Path) -> dict[str, str]:
    index_path = codex_home / "session_index.jsonl"
    titles: dict[str, str] = {}
    if not index_path.is_file() or not index_path.resolve().is_relative_to(codex_home.resolve()):
        return titles
    for raw_line in index_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        session_id = record.get("id")
        title = record.get("thread_name")
        if isinstance(session_id, str) and isinstance(title, str) and title.strip():
            titles[session_id] = compact_text(title, 120)
    return titles


def is_technical_session_title(title: str) -> bool:
    normalized = " ".join(title.casefold().split())
    return normalized.startswith(TECHNICAL_SESSION_PREFIXES)


def _iter_transcript_paths(codex_home: Path) -> Iterable[Path]:
    seen: set[Path] = set()
    selected_root = codex_home.resolve()
    for relative_root in ("sessions", "archived_sessions"):
        root = codex_home / relative_root
        if not root.is_dir() or not root.resolve().is_relative_to(selected_root):
            continue
        for path in root.rglob("*.jsonl"):
            resolved = path.resolve()
            if resolved.is_relative_to(selected_root) and resolved not in seen:
                seen.add(resolved)
                yield path


def _load_records(path: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    invalid_lines = 0
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return records, 1
    for raw_line in raw_lines:
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            invalid_lines += 1
            continue
        if isinstance(record, dict):
            records.append(record)
        else:
            invalid_lines += 1
    return records, invalid_lines


def _session_meta(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in records:
        if record.get("type") == "session_meta" and isinstance(record.get("payload"), dict):
            return record["payload"]
    return None


def _is_subagent(meta: dict[str, Any]) -> bool:
    if meta.get("parent_thread_id"):
        return True
    source = meta.get("source")
    return isinstance(source, dict) and source.get("subagent") is not None


def _tool_metadata(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    direct_name = payload.get("name") or payload.get("tool_name")
    raw_input = payload.get("input", payload.get("arguments", ""))
    if isinstance(raw_input, str):
        input_text = raw_input
    else:
        input_text = json.dumps(raw_input, ensure_ascii=False, default=str)

    nested_names = NESTED_TOOL_PATTERN.findall(input_text)
    names = nested_names or ([str(direct_name)] if direct_name else [])
    paths = [compact_text(path, 240) for path in PATCH_PATH_PATTERN.findall(input_text)]
    return names, paths


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _turn_is_in_window(turn: _OpenTurn, terminal_time: datetime | None, start: datetime, end: datetime) -> bool:
    request_time = turn.timestamp.astimezone(start.tzinfo)
    if start <= request_time < end:
        return True
    if terminal_time is None:
        return False
    local_terminal = terminal_time.astimezone(start.tzinfo)
    return start <= local_terminal < end


def _collect_session(
    records: list[dict[str, Any]],
    *,
    session_id: str,
    title: str,
    cwd: str,
    start: datetime,
    end: datetime,
) -> SessionActivity | None:
    turns: list[TurnActivity] = []
    current: _OpenTurn | None = None

    def finish_open_turn(status: str, terminal_time: datetime | None, result: str = "", reason: str = "") -> None:
        nonlocal current
        if current is None:
            return
        if _turn_is_in_window(current, terminal_time, start, end):
            turns.append(
                TurnActivity(
                    timestamp=terminal_time or current.timestamp,
                    request=current.request,
                    status=status,
                    result=result,
                    reason=reason,
                    tools=_unique(current.tools),
                    paths=_unique(current.paths),
                )
            )
        current = None

    for record in records:
        timestamp = parse_timestamp(record.get("timestamp"))
        payload = record.get("payload")
        if timestamp is None or not isinstance(payload, dict):
            continue

        record_type = record.get("type")
        payload_type = payload.get("type")
        if record_type == "event_msg" and payload_type == "user_message":
            if current is not None:
                finish_open_turn("in_progress", None, current.last_agent_message)
            current = _OpenTurn(
                timestamp=timestamp,
                request=normalize_user_message(payload.get("message", "")),
            )
        elif current is not None and record_type == "event_msg" and payload_type == "agent_message":
            current.last_agent_message = normalize_agent_message(payload.get("message", ""))
        elif current is not None and record_type == "response_item" and payload_type in {
            "custom_tool_call",
            "function_call",
        }:
            names, paths = _tool_metadata(payload)
            current.tools.extend(names)
            current.paths.extend(paths)
        elif current is not None and record_type == "event_msg" and payload_type == "task_complete":
            finish_open_turn(
                "completed",
                timestamp,
                normalize_agent_message(payload.get("last_agent_message", "")),
            )
        elif current is not None and record_type == "event_msg" and payload_type == "turn_aborted":
            finish_open_turn(
                "aborted",
                timestamp,
                current.last_agent_message,
                compact_text(payload.get("reason", ""), 160),
            )

    if current is not None:
        finish_open_turn("in_progress", None, current.last_agent_message)

    if not turns:
        return None
    turns.sort(key=lambda turn: turn.timestamp, reverse=True)
    return SessionActivity(session_id=session_id, title=title, cwd=cwd, turns=turns)


def scan_transcripts(codex_home: Path, start: datetime, end: datetime) -> ScanResult:
    titles = load_session_index(codex_home)
    result = ScanResult(sessions=[])

    for path in _iter_transcript_paths(codex_home):
        result.scanned_files += 1
        records, invalid_lines = _load_records(path)
        result.invalid_lines += invalid_lines
        meta = _session_meta(records)
        if not meta:
            continue
        if _is_subagent(meta):
            result.excluded_subagents += 1
            continue
        session_id = str(meta.get("id") or meta.get("session_id") or path.stem)
        title = titles.get(session_id, f"Session {session_id[:8]}")
        if is_technical_session_title(title):
            continue
        session = _collect_session(
            records,
            session_id=session_id,
            title=title,
            cwd=str(meta.get("cwd") or "unknown"),
            start=start,
            end=end,
        )
        if session:
            result.sessions.append(session)

    result.sessions.sort(key=lambda session: session.turns[0].timestamp, reverse=True)
    return result


def _truncate_manifest(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    suffix = "\n\n> Manifest truncated to the configured character budget.\n"
    available = max(1, max_chars - len(suffix))
    clipped = text[:available]
    if "\n" in clipped:
        clipped = clipped.rsplit("\n", 1)[0]
    return clipped.rstrip() + suffix


def render_manifest(
    result: ScanResult,
    *,
    start: datetime,
    end: datetime,
    timezone_name: str,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    timezone = ZoneInfo(timezone_name)
    generated = datetime.now(timezone).isoformat(timespec="seconds")
    lines = [
        "# Codex Activity Manifest",
        "",
        f"- Generated: {generated}",
        f"- Range: {start.isoformat()} -> {end.isoformat()} (end exclusive)",
        f"- Root sessions with activity: {len(result.sessions)}",
        f"- Transcript files scanned: {result.scanned_files}",
        f"- Subagent transcripts excluded: {result.excluded_subagents}",
        f"- Invalid JSONL lines skipped: {result.invalid_lines}",
        "",
        "## Dialogues and turns",
        "",
    ]

    if not result.sessions:
        lines.append("- No root Codex activity found in this window.")
    for session in result.sessions:
        lines.extend(
            [
                f"### {compact_text(session.title, 120)}",
                "",
                f"- Session: `{session.session_id[:12]}`",
                f"- Workspace: `{compact_text(session.cwd, 240)}`",
                "",
            ]
        )
        visible_turns = session.turns[:MAX_TURNS_PER_SESSION]
        for turn in visible_turns:
            local_time = turn.timestamp.astimezone(timezone).strftime("%Y-%m-%d %H:%M")
            lines.append(f"- **{local_time} [{turn.status}]** {compact_text(turn.request, PROMPT_LIMIT) or '(request unavailable)'}")
            outcome = turn.result or turn.reason
            if outcome:
                lines.append(f"  - Outcome: {compact_text(outcome, RESULT_LIMIT)}")
            if turn.reason and turn.result:
                lines.append(f"  - Stop reason: {compact_text(turn.reason, 160)}")
            if turn.tools:
                lines.append(f"  - Tools: `{', '.join(_unique(turn.tools))}`")
            if turn.paths:
                lines.append(f"  - Logged patch paths: {', '.join(f'`{path}`' for path in _unique(turn.paths))}")
        omitted_turns = len(session.turns) - len(visible_turns)
        if omitted_turns:
            lines.append(f"- Older turns omitted: {omitted_turns}")
        lines.append("")

    lines.extend(
        [
            "## Interpretation rules",
            "",
            "- Codex outcomes are chat signals, not proof that work is done.",
            "- Git commits, file changes, tests, and external readback outrank transcript claims.",
            "- Reasoning and tool outputs are intentionally excluded.",
            "- Raw transcripts are not copied into the repository.",
        ]
    )
    return _truncate_manifest("\n".join(lines).rstrip() + "\n", max_chars)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    window = parser.add_mutually_exclusive_group()
    window.add_argument("--date", dest="single_date", help="Local calendar day (YYYY-MM-DD)")
    window.add_argument("--from", dest="date_from", help="Inclusive local start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="Exclusive local end date (YYYY-MM-DD)")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument(
        "--codex-home",
        type=Path,
        required=True,
        help="Explicit selected export root; reads sessions/, archived_sessions/, and optional session_index.jsonl",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        start, end = resolve_window(
            single_date=args.single_date,
            date_from=args.date_from,
            date_to=args.date_to,
            timezone_name=args.timezone,
        )
    except (ValueError, KeyError) as error:
        parser.error(str(error))

    if args.max_chars < 500:
        parser.error("--max-chars must be at least 500")

    result = scan_transcripts(args.codex_home.expanduser(), start, end)
    manifest = render_manifest(
        result,
        start=start,
        end=end,
        timezone_name=args.timezone,
        max_chars=args.max_chars,
    )
    if args.output:
        output_path = args.output.expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(manifest, encoding="utf-8")
        print(output_path)
    else:
        print(manifest, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
