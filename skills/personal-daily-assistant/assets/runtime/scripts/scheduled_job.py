#!/usr/bin/env python3
"""Run one deterministic personal-assistant schedule entry."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(argv: list[str]) -> None:
    subprocess.run(argv, cwd=PROJECT_ROOT, check=True)


def run_job(job: str, *, dry_run: bool = False) -> None:
    python_bin = os.environ.get("PDS_PYTHON_BIN", sys.executable)
    timezone = os.environ.get("PDS_TIMEZONE", "UTC")
    target = os.environ.get("PDS_TELEGRAM_TARGET", "").strip()
    system_script = PROJECT_ROOT / "scripts" / "personal_daily_system.py"
    common = [python_bin, str(system_script), "--repo-root", str(PROJECT_ROOT)]

    if job == "preflight":
        _run([*common, "refresh-context"])
        _run([*common, "render"])
        _run([*common, "validate"])
        return

    if not target:
        raise RuntimeError("PDS_TELEGRAM_TARGET is required for dispatch jobs")

    if job == "ten":
        if os.environ.get("PDS_EVENING_TEN_ENABLED") != "1":
            raise RuntimeError("Evening Ten delivery is disabled")
        command = [python_bin, str(PROJECT_ROOT / "scripts" / "evening_ten.py"), "dispatch", "--target", target]
        if dry_run: command.append("--dry-run")
        _run(command)
        return

    dispatch = [*common, "dispatch", job, "--target", target]
    if job == "evening" and os.environ.get("PDS_INCLUDE_CODEX_ACTIVITY", "").strip() == "1":
        source_value = os.environ.get("PDS_CODEX_ACTIVITY_SOURCE_DIR", "").strip()
        source_root = Path(source_value).expanduser()
        if not source_value or not source_root.is_absolute():
            raise RuntimeError("PDS_CODEX_ACTIVITY_SOURCE_DIR must be an explicit absolute directory when activity is enabled")
        activity_path = PROJECT_ROOT / "context" / "codex_activity_latest.md"
        local_date = datetime.now(ZoneInfo(timezone)).date().isoformat()
        activity_script = PROJECT_ROOT / "scripts" / "build_codex_activity_context.py"
        _run(
            [
                python_bin,
                str(activity_script),
                "--codex-home",
                str(source_root),
                "--date",
                local_date,
                "--timezone",
                timezone,
                "--output",
                str(activity_path),
            ]
        )
        dispatch.extend(["--codex-activity", str(activity_path)])
    if dry_run:
        dispatch.append("--dry-run")
    _run(dispatch)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "job",
        choices=("preflight", "morning", "viability", "evening", "weekly", "ten"),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_job(args.job, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
