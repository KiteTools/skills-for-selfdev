#!/usr/bin/env python3
"""Check package links, skill discovery, and obvious accidental data leaks.

This is a release guard, not proof that arbitrary text has been anonymized.
"""
from pathlib import Path
import json
import re
import sys
from urllib.parse import unquote
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", "__pycache__", ".venv", "node_modules"}


def check(root: Path = ROOT) -> list[str]:
    errors = []
    skills = sorted((root / "skills").glob("*/SKILL.md"))
    if not skills:
        errors.append("No discoverable skills")
    for skill in skills:
        text = skill.read_text()
        match = re.match(r"\A---\s*\n(.*?)\n---", text, re.S)
        if not match:
            errors.append(f"{skill.relative_to(root)}: missing frontmatter")
            continue
        name = re.search(r"^name:\s*[\"']?([a-z0-9-]+)[\"']?\s*$", match[1], re.M)
        if not name or name[1] != skill.parent.name:
            errors.append(f"{skill.relative_to(root)}: folder/name mismatch")
        if not re.search(r"^description:\s*\S", match[1], re.M):
            errors.append(f"{skill.relative_to(root)}: missing description")
        if not (root / "docs/skills" / f"{skill.parent.name}.md").is_file():
            errors.append(f"Missing visitor page for {skill.parent.name}")
    manifests = []
    for name in ["plugin.json", ".codex-plugin/plugin.json"]:
        try:
            manifests.append(json.loads((root / name).read_text()))
        except (OSError, ValueError) as exc:
            errors.append(f"{name}: {exc}")
    if len(manifests) == 2 and any(manifests[0].get(k) != manifests[1].get(k) for k in ["name", "version"]):
        errors.append("Plugin names/versions disagree")
    secret_patterns = [r"gh[pousr]_[A-Za-z0-9]{30,}", r"sk-(?:proj-)?[A-Za-z0-9_-]{32,}", r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"]
    for path in sorted(root.rglob("*")):
        if any(part in SKIP for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root)
        if path.is_symlink():
            errors.append(f"{rel}: symbolic link")
            continue
        if not path.is_file():
            continue
        if path.suffix == ".svg":
            try:
                ET.parse(path)
            except ET.ParseError as exc:
                errors.append(f"{rel}: invalid SVG: {exc}")
        if path.suffix not in {".md", ".py", ".json", ".yml", ".yaml", ".js", ".mjs", ".html", ".svg", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in secret_patterns:
            if re.search(pattern, text):
                errors.append(f"{rel}: credential-shaped text; inspect before publishing")
        if re.search(r"/(?:Users|home)/[a-zA-Z0-9_.-]+/", text):
            errors.append(f"{rel}: absolute personal home path")
        if path.suffix == ".md":
            body = re.sub(r"```.*?```", "", text, flags=re.S)
            for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", body):
                target = target.split(' "')[0].strip("<>")
                if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                target = unquote(target.split("#")[0])
                if target and not (path.parent / target).exists():
                    errors.append(f"{rel}: broken relative link {target}")
    return errors


if __name__ == "__main__":
    problems = check()
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    print(f"Package checks passed: {len(list((ROOT / 'skills').glob('*/SKILL.md')))} skills; relative links, manifests, SVG, and credential/path patterns.")
