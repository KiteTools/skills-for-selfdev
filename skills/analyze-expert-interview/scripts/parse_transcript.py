#!/usr/bin/env python3
"""Normalize diarized VTT, SRT, and labelled TXT transcripts.

Start-only TXT cues use the next cue's start as their inferred end.  Because
there is no following boundary for the final cue, its ``end_ms`` and the
document ``duration_ms`` are ``None`` rather than an invented duration.
"""

import argparse
import html
import json
import re
from pathlib import Path


__all__ = ["parse_timestamp", "parse_text", "parse_file"]

_TIMESTAMP_RE = re.compile(r"^(?:(\d{2,}):)?([0-5]\d):([0-5]\d)(?:[.,](\d{3}))?$")
_TIMING_RE = re.compile(r"^(.+?)\s+-->\s+([^ ]+)(?:\s+.*)?$")
_VOICE_RE = re.compile(r"^<v\s+([^>]+)>(.*)$", re.DOTALL)
_PREFIX_RE = re.compile(r"^([A-Za-z]+):\s*(.*)$", re.DOTALL)
_TXT_INTERVAL_RE = re.compile(r"^\[([^]]+?)\s+-->\s+([^]]+)]\s*(.*)$")
_TXT_START_RE = re.compile(r"^\[([^]]+)]\s*(.*)$")
_TXT_START_TIMESTAMP_RE = re.compile(r"^(\d{2,}):([0-5]\d)$")
_VTT_INLINE_TAG_RE = re.compile(
    r"</?(?:i|b|u)(?:\s+[^>]*)?>"
    r"|</?c(?:\.[^>\s]+)*(?:\s+[^>]*)?>"
    r"|</?lang(?:\s+[^>]*)?>"
    r"|<(?:\d{2,}:)?[0-5]\d:[0-5]\d\.\d{3}>",
    re.IGNORECASE,
)
_SRT_PRESENTATION_TAG_RE = re.compile(
    r"</?(?:i|b|u|font)(?:\s+[^>]*)?>",
    re.IGNORECASE,
)
_ROLES = {"HOST", "GUEST"}
_FULL_TIMESTAMP_RE = {
    "vtt": re.compile(r"^(?:\d{2,}:)?[0-5]\d:[0-5]\d\.\d{3}$"),
    "srt": re.compile(r"^\d{2}:[0-5]\d:[0-5]\d,\d{3}$"),
    "txt": re.compile(r"^\d{2}:[0-5]\d:[0-5]\d\.\d{3}$"),
}


def parse_timestamp(value: str) -> int:
    """Return a strict full timestamp, or a ``MM:SS`` TXT timestamp, in ms."""
    match = _TIMESTAMP_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Malformed timestamp: {value!r}")
    hours, minutes, seconds, milliseconds = match.groups()
    if hours is not None and milliseconds is None:
        raise ValueError(f"Malformed timestamp: {value!r}")
    return (
        int(hours or 0) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1_000
        + int(milliseconds or 0)
    )


def _normalize_text(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("Transcript segment text must not be empty")
    return normalized


def _optional_label(value: str) -> tuple[str, str] | None:
    match = _PREFIX_RE.fullmatch(value.strip())
    if not match:
        return None
    speaker, text = match.groups()
    if speaker not in _ROLES:
        raise ValueError(f"Unknown speaker role: {speaker}")
    return speaker, _normalize_text(text)


def _is_search_service_text(value: str) -> bool:
    return " ".join(value.split()) == "Search in video"


def _clean_vtt_text(value: str) -> str:
    if value.endswith("</v>"):
        value = value[:-4]
    return html.unescape(_VTT_INLINE_TAG_RE.sub("", value))


def _clean_srt_text(value: str) -> str:
    return html.unescape(_SRT_PRESENTATION_TAG_RE.sub("", value))


def _parse_txt_start_timestamp(value: str) -> int:
    match = _TXT_START_TIMESTAMP_RE.fullmatch(value)
    if not match:
        raise ValueError(f"Malformed start-only TXT timestamp: {value!r}")
    minutes, seconds = match.groups()
    return int(minutes) * 60_000 + int(seconds) * 1_000


def _parse_full_timestamp(value: str, source_format: str) -> int:
    value = value.strip()
    if not _FULL_TIMESTAMP_RE[source_format].fullmatch(value):
        raise ValueError(
            f"Malformed {source_format.upper()} interval timestamp: {value!r}"
        )
    return parse_timestamp(value)


def _parse_timing(value: str, source_format: str) -> tuple[int, int]:
    match = _TIMING_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Malformed cue timing: {value!r}")
    start_ms = _parse_full_timestamp(match.group(1), source_format)
    end_ms = _parse_full_timestamp(match.group(2), source_format)
    return start_ms, end_ms


def _parse_vtt(text: str) -> list[dict]:
    clean = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if not clean.startswith("WEBVTT"):
        raise ValueError("WebVTT input must start with WEBVTT")
    blocks = re.split(r"\n[ \t]*\n", clean)
    segments = []
    for index, block in enumerate(blocks):
        lines = block.splitlines()
        if not lines:
            continue
        first = lines[0].strip()
        if index == 0 and first.startswith("WEBVTT"):
            continue
        if (
            first == "NOTE"
            or first.startswith("NOTE ")
            or first == "STYLE"
            or first == "REGION"
        ):
            continue
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            raise ValueError(f"WebVTT cue is missing a timestamp: {first!r}")
        start_ms, end_ms = _parse_timing(lines[timing_index], "vtt")
        payload = "\n".join(lines[timing_index + 1 :]).strip()
        voice = _VOICE_RE.fullmatch(payload)
        if not voice:
            # Deterministic metadata boundary: only explicit VTT metadata blocks
            # and the exact service string are skipped.  Other unlabelled timed
            # cues are errors; we do not guess from length or wording.
            if _is_search_service_text(_clean_vtt_text(payload)):
                continue
            raise ValueError(
                "WebVTT cue is missing a <v HOST> or <v GUEST> voice span"
            )
        speaker = voice.group(1).strip()
        if speaker not in _ROLES:
            raise ValueError(f"Unknown speaker role: {speaker}")
        payload = _clean_vtt_text(voice.group(2))
        if _is_search_service_text(payload):
            continue
        segments.append(_segment(speaker, start_ms, end_ms, payload))
    return segments


def _parse_srt(text: str) -> list[dict]:
    clean = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    segments = []
    for block in re.split(r"\n[ \t]*\n", clean.strip()):
        lines = block.splitlines()
        if not lines:
            continue
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            raise ValueError(f"SRT cue is missing a timestamp: {lines[0]!r}")
        start_ms, end_ms = _parse_timing(lines[timing_index], "srt")
        raw_payload = _clean_srt_text("\n".join(lines[timing_index + 1 :]))
        if _is_search_service_text(raw_payload):
            continue
        labelled = _optional_label(raw_payload)
        if labelled is None:
            raise ValueError("SRT cue is missing a HOST or GUEST role")
        speaker, payload = labelled
        if _is_search_service_text(payload):
            continue
        segments.append(_segment(speaker, start_ms, end_ms, payload))
    return segments


def _parse_txt(text: str) -> list[dict]:
    segments = []
    interval_modes = set()
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        interval = _TXT_INTERVAL_RE.fullmatch(line)
        if interval:
            start_ms = _parse_full_timestamp(interval.group(1), "txt")
            end_ms = _parse_full_timestamp(interval.group(2), "txt")
            labelled = interval.group(3)
            interval_mode = "full"
        else:
            start = _TXT_START_RE.fullmatch(line)
            if not start:
                raise ValueError(f"Malformed labelled TXT line: {raw_line!r}")
            start_ms = _parse_txt_start_timestamp(start.group(1))
            end_ms = None
            labelled = start.group(2)
            interval_mode = "start-only"
            # Every start-only cue is a timeline boundary, including a service
            # cue that will be filtered from the normalized spoken segments.
            if segments and segments[-1]["end_ms"] is None:
                segments[-1]["end_ms"] = start_ms
        if _is_search_service_text(labelled):
            continue
        parsed_label = _optional_label(labelled)
        if parsed_label is None:
            raise ValueError("TXT cue is missing a HOST or GUEST role")
        speaker, payload = parsed_label
        if _is_search_service_text(payload):
            continue
        interval_modes.add(interval_mode)
        segments.append(_segment(speaker, start_ms, end_ms, payload))
    if len(interval_modes) > 1:
        raise ValueError("Cannot mix full-interval and start-only TXT cues")
    return segments


def _segment(speaker: str, start_ms: int, end_ms: int | None, text: str) -> dict:
    return {
        "speaker": speaker,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "text": _normalize_text(text),
    }


def _validate(segments: list[dict]) -> None:
    if not segments:
        raise ValueError("Transcript has no segments")
    previous_start = None
    previous_end = None
    for segment in segments:
        start_ms = segment["start_ms"]
        end_ms = segment["end_ms"]
        if previous_start is not None and start_ms <= previous_start:
            raise ValueError("Cue starts must be strictly increasing")
        if end_ms is not None and end_ms <= start_ms:
            raise ValueError("Cue end must be later than its start")
        if previous_end is not None and start_ms < previous_end:
            raise ValueError("Transcript cues must not overlap")
        previous_start = start_ms
        previous_end = end_ms
    roles = {segment["speaker"] for segment in segments}
    if roles != _ROLES:
        missing = ", ".join(sorted(_ROLES - roles))
        raise ValueError(f"Transcript must contain both HOST and GUEST; missing: {missing}")


def parse_text(text: str, suffix: str) -> dict:
    """Parse transcript text into the canonical normalized dictionary shape."""
    source_format = suffix.lower().lstrip(".")
    parsers = {"vtt": _parse_vtt, "srt": _parse_srt, "txt": _parse_txt}
    if source_format not in parsers:
        raise ValueError(f"Unsupported transcript suffix: {suffix}")
    segments = parsers[source_format](text)
    _validate(segments)
    for number, segment in enumerate(segments, start=1):
        segment["id"] = f"seg_{number:04d}"
        segment_order = ("id", "speaker", "start_ms", "end_ms", "text")
        segment.update({key: segment.pop(key) for key in segment_order})
    duration_ms = None if any(s["end_ms"] is None for s in segments) else segments[-1]["end_ms"]
    return {
        "metadata": {
            "title": None,
            "source_url": None,
            "duration_ms": duration_ms,
            "source_format": source_format,
        },
        "segments": segments,
    }


def parse_file(path: Path, source_url: str | None = None) -> dict:
    """Read and normalize a transcript file, using its stem as the title."""
    path = Path(path)
    result = parse_text(path.read_text(encoding="utf-8"), path.suffix)
    result["metadata"]["title"] = path.stem
    result["metadata"]["source_url"] = source_url
    return result


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-url")
    parser.add_argument("--title")
    args = parser.parse_args()

    try:
        result = parse_file(args.input, args.source_url)
        if args.title is not None:
            result["metadata"]["title"] = args.title
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    _main()
