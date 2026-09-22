#!/usr/bin/env python3
"""Compute deterministic guest-only structural transcript metrics."""

import argparse
import json
import sys
from pathlib import Path


__all__ = ["compute_metrics"]

_ROLES = {"HOST", "GUEST"}


def _is_timestamp(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validated_segments(doc: dict) -> list[dict]:
    if not isinstance(doc, dict) or not doc:
        raise ValueError("Input must be a non-empty normalized document")
    segments = doc.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("segments must be a non-empty list")

    metadata = doc.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    previous_end = None
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValueError(f"segment {index + 1} must be an object")
        if segment.get("speaker") not in _ROLES:
            raise ValueError(f"segment {index + 1} has an invalid speaker role")

        start_ms = segment.get("start_ms")
        end_ms = segment.get("end_ms")
        if not _is_timestamp(start_ms) or start_ms < 0:
            raise ValueError(
                f"segment {index + 1} start_ms must be a nonnegative integer"
            )
        if end_ms is None:
            if index != len(segments) - 1:
                raise ValueError("end_ms may be null only on the final segment")
        else:
            if not _is_timestamp(end_ms) or end_ms < 0:
                raise ValueError(
                    f"segment {index + 1} end_ms must be a nonnegative integer"
                )
            if end_ms <= start_ms:
                raise ValueError(f"segment {index + 1} must have positive duration")
        if previous_end is not None and start_ms < previous_end:
            raise ValueError(f"segment {index + 1} overlaps the previous segment")
        previous_end = end_ms
    return segments


def _median_ms(values: list[int | float]) -> int | float:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    total = ordered[midpoint - 1] + ordered[midpoint]
    return total // 2 if total % 2 == 0 else total / 2


def compute_metrics(doc: dict) -> dict:
    """Return structural speaking metrics from a normalized transcript."""
    segments = _validated_segments(doc)
    turns: list[dict] = []

    for segment in segments:
        end_ms = segment["end_ms"]
        if (
            turns
            and turns[-1]["speaker"] == segment["speaker"]
            and turns[-1]["end_ms"] == segment["start_ms"]
        ):
            turns[-1]["end_ms"] = end_ms
            turns[-1]["partial"] = end_ms is None
        else:
            turns.append(
                {
                    "speaker": segment["speaker"],
                    "start_ms": segment["start_ms"],
                    "end_ms": end_ms,
                    "partial": end_ms is None,
                }
            )

    known_segments = [segment for segment in segments if segment["end_ms"] is not None]
    known_speaking_ms = sum(
        segment["end_ms"] - segment["start_ms"] for segment in known_segments
    )
    guest_speaking_ms = sum(
        segment["end_ms"] - segment["start_ms"]
        for segment in known_segments
        if segment["speaker"] == "GUEST"
    )
    unknown_duration_segment_count = len(segments) - len(known_segments)

    if guest_speaking_ms <= 0:
        raise ValueError("Transcript has no guest speech with known duration")

    guest_turns = [turn for turn in turns if turn["speaker"] == "GUEST"]
    guest_turn_durations = [
        turn["end_ms"] - turn["start_ms"]
        for turn in guest_turns
        if not turn["partial"]
    ]
    host_to_guest_transitions = sum(
        previous["speaker"] == "HOST" and current["speaker"] == "GUEST"
        for previous, current in zip(turns, turns[1:])
    )

    final_end = segments[-1]["end_ms"]
    duration_ms = None if final_end is None else final_end
    return {
        "duration_ms": duration_ms,
        "guest_speaking_ms": guest_speaking_ms,
        "guest_speaking_share": guest_speaking_ms / known_speaking_ms,
        "guest_turn_count": len(guest_turns),
        "guest_turn_median_ms": (
            _median_ms(guest_turn_durations) if guest_turn_durations else None
        ),
        "longest_guest_turn_ms": (
            max(guest_turn_durations) if guest_turn_durations else None
        ),
        "host_to_guest_transitions": host_to_guest_transitions,
        "duration_metrics_partial": unknown_duration_segment_count > 0,
        "unknown_duration_segment_count": unknown_duration_segment_count,
        "guest_turn_duration_count": len(guest_turn_durations),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute guest structural metrics from normalized JSON"
    )
    parser.add_argument("input_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args(argv)

    try:
        doc = json.loads(args.input_json.read_text(encoding="utf-8"))
        metrics = compute_metrics(doc)
        args.output_json.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
