#!/usr/bin/env python3
"""Build a deterministic ZIP while excluding runtime state and caches."""

from __future__ import annotations

import argparse
import stat
import zipfile
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = SKILL_ROOT
FORBIDDEN_NAMES = {
    ".DS_Store",
    "events.jsonl",
    "state.json",
    "nightly.jsonl",
}


def build_archive(source: Path, output: Path) -> int:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve(strict=False)
    if not source.is_dir():
        raise ValueError(f"source directory does not exist: {source}")
    try:
        output.relative_to(source)
    except ValueError:
        pass
    else:
        raise ValueError("archive output must be outside the source directory")
    output.parent.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlinks are not allowed: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if path.name in FORBIDDEN_NAMES or "__pycache__" in relative.parts:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        files.append(path)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files, key=lambda item: item.as_posix()):
            relative = Path(source.name) / path.relative_to(source)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(2026, 8, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = stat.S_IMODE(path.stat().st_mode)
            info.external_attr = (mode & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())
    return len(files)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    count = build_archive(args.source, args.output)
    print(f"{args.output.expanduser().resolve(strict=False)}\t{count} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
