#!/usr/bin/env python3
"""Copy selected skills without executing them or changing agent settings."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def available(root: Path = ROOT) -> dict[str, Path]:
    return {p.name: p for p in sorted((root / "skills").iterdir())
            if p.is_dir() and not p.is_symlink() and (p / "SKILL.md").is_file()}


def install(names: list[str], destination: Path, root: Path = ROOT) -> list[Path]:
    skills = available(root)
    if not names or len(names) != len(set(names)):
        raise ValueError("Choose at least one skill; do not repeat names.")
    for name in names:
        if name not in skills:
            raise ValueError(f"Unknown skill: {name}")
        if any(p.is_symlink() for p in skills[name].rglob("*")):
            raise ValueError(f"Refusing symbolic links in skill: {name}")
    destination = destination.expanduser().absolute()
    if destination.is_symlink():
        raise ValueError("Refusing a destination directory that is a symbolic link.")
    # Honor the selected parent location, including macOS /var -> /private/var.
    destination = destination.resolve()
    for name in names:
        if os.path.lexists(destination / name):
            raise ValueError(f"Already exists: {destination / name}. Move it aside before updating.")
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    # Stage all copies before publishing any destination.
    with tempfile.TemporaryDirectory(prefix=".selfdev-install-", dir=destination) as tmp:
        staged = Path(tmp)
        for name in names:
            shutil.copytree(skills[name], staged / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        for name in names:
            target = destination / name
            # mkdir reserves the name without overwriting an existing installation.
            target.mkdir()
            try:
                for child in (staged / name).iterdir():
                    child.rename(target / child.name)
            except Exception:
                shutil.rmtree(target)
                raise
            copied.append(target)
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skills", nargs="*", help="Skill directory names")
    parser.add_argument("--list", action="store_true", help="List available skill names")
    parser.add_argument("--all", action="store_true", help="Copy all skills; do not run them")
    parser.add_argument("--dest", type=Path, default=Path.home() / ".agents" / "skills")
    args = parser.parse_args()
    if args.list:
        print("\n".join(available()))
        return
    if args.all and args.skills:
        parser.error("Choose explicit names or --all, not both.")
    names = list(available()) if args.all else args.skills
    try:
        for path in install(names, args.dest):
            print(f"Copied: {path}")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Installation stopped: {exc}\n")
    print("No services started, accounts connected, or schedules changed.")


if __name__ == "__main__":
    main()
