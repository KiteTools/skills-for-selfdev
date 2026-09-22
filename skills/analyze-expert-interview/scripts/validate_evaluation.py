#!/usr/bin/env python3
"""Validate one deterministic expert-broadcast evaluation artifact."""

import argparse
import binascii
import json
import math
import re
import sys
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import validate_passes
from validate_report import validate_report


RUBRIC_VERSION = "1.0"
_CATEGORY_KEYS = ("S", "E", "V", "T")
_VIEWPORTS = {"desktop": (1440, 1000), "mobile": (390, 844)}
_ROOT_KEYS = {
    "rubric_version",
    "artifacts",
    "browser_checks",
    "judges",
    "aggregation",
    "passed",
}
_RESOURCE_TAGS = {
    "audio",
    "embed",
    "iframe",
    "img",
    "link",
    "object",
    "source",
    "track",
    "video",
}

_JPEG_SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}


def _object(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _exact_keys(value: dict, expected: set[str], path: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{path} must contain exactly {', '.join(sorted(expected))}")


def _string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _integer(value: object, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{path} must be an integer")
    return value


def _number(value: object, path: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{path} must be a finite number")
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    else:
        if not math.isfinite(value):
            raise ValueError(f"{path} must be a finite number")
        number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError(f"{path} must be a finite number")
    return number


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{path} must be a boolean")
    return value


def _artifact_path(root: Path, value: object, path: str) -> Path:
    relative = Path(_string(value, path))
    if relative.is_absolute():
        raise ValueError(f"{path} must be a relative path inside the evaluation directory")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{path} must stay inside the evaluation directory") from error
    if not resolved.is_file() or resolved.stat().st_size == 0:
        raise ValueError(f"{path} must reference a non-empty file")
    return resolved


class _StaticReportCounter(HTMLParser):
    """Count only static report features recorded by browser QA."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.details_count = 0
        self.timestamp_count = 0
        self.scripts = 0
        self.external_resources = 0
        self._in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        attributes = {name.casefold(): value or "" for name, value in attrs}
        if tag == "details":
            self.details_count += 1
        if "tc" in attributes.get("class", "").split():
            self.timestamp_count += 1
        if tag == "script":
            self.scripts += 1
        if tag in _RESOURCE_TAGS:
            self.external_resources += 1
        elif tag != "a" and any(
            attributes.get(name, "") for name in ("src", "href", "srcset")
        ):
            self.external_resources += 1
        self._in_style = tag == "style"

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self.external_resources += len(
                re.findall(r"@import\b|\burl\s*\(", data, flags=re.IGNORECASE)
            )


def _static_report_counts(report_path: Path) -> _StaticReportCounter:
    counter = _StaticReportCounter()
    counter.feed(report_path.read_text(encoding="utf-8"))
    counter.close()
    return counter


def _image_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        position = 8
        dimensions = None
        has_idat = False
        while position + 12 <= len(data):
            length = int.from_bytes(data[position:position + 4], "big")
            kind_start = position + 4
            payload_start = position + 8
            end = payload_start + length
            if end + 4 > len(data):
                break
            kind = data[kind_start:payload_start]
            payload = data[payload_start:end]
            declared_crc = int.from_bytes(data[end:end + 4], "big")
            if binascii.crc32(kind + payload) & 0xFFFFFFFF != declared_crc:
                raise ValueError(f"{path.name} has an invalid PNG checksum")
            if kind == b"IHDR" and dimensions is None and length == 13:
                dimensions = (
                    int.from_bytes(data[payload_start:payload_start + 4], "big"),
                    int.from_bytes(data[payload_start + 4:payload_start + 8], "big"),
                )
            elif kind == b"IDAT":
                has_idat = True
            elif kind == b"IEND" and length == 0:
                if dimensions and all(dimensions) and has_idat and end + 4 == len(data):
                    return dimensions
                break
            position = end + 4
        if dimensions is None:
            raise ValueError(f"{path.name} is not a recognized image")
        raise ValueError(f"{path.name} is not a complete PNG image")
    if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        raise ValueError(f"{path.name} is not a recognized image")
    position = 2
    dimensions = None
    while position < len(data):
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(data):
            break
        length = int.from_bytes(data[position:position + 2], "big")
        if length < 2 or position + length > len(data):
            break
        if marker in _JPEG_SOF_MARKERS:
            if length < 7:
                break
            dimensions = (
                int.from_bytes(data[position + 5:position + 7], "big"),
                int.from_bytes(data[position + 3:position + 5], "big"),
            )
        if marker == 0xDA:
            scan_start = position + length
            if dimensions and all(dimensions) and scan_start < len(data) - 2:
                return dimensions
        position += length
    raise ValueError(f"{path.name} is not a recognized image")


def _validate_screenshot(path: Path, name: str, expected: tuple[int, int]) -> None:
    dimensions = _image_dimensions(path)
    if dimensions != expected:
        raise ValueError(
            f"artifacts.screenshots.{name} must be {expected[0]}x{expected[1]}"
        )


def _validate_artifacts(document: dict, root: Path) -> tuple[Path, Path, Path, Path, Path]:
    artifacts = _object(document["artifacts"], "artifacts")
    _exact_keys(
        artifacts,
        {
            "normalized_json",
            "structure_analysis_json",
            "logic_analysis_json",
            "synthesis_json",
            "report_html",
            "screenshots",
        },
        "artifacts",
    )
    normalized_path = _artifact_path(
        root, artifacts["normalized_json"], "artifacts.normalized_json"
    )
    structure_path = _artifact_path(
        root, artifacts["structure_analysis_json"], "artifacts.structure_analysis_json"
    )
    logic_path = _artifact_path(
        root, artifacts["logic_analysis_json"], "artifacts.logic_analysis_json"
    )
    synthesis_path = _artifact_path(
        root, artifacts["synthesis_json"], "artifacts.synthesis_json"
    )
    report_path = _artifact_path(root, artifacts["report_html"], "artifacts.report_html")
    screenshots = _object(artifacts["screenshots"], "artifacts.screenshots")
    _exact_keys(screenshots, {"desktop", "mobile"}, "artifacts.screenshots")
    desktop_path = _artifact_path(root, screenshots["desktop"], "artifacts.screenshots.desktop")
    mobile_path = _artifact_path(root, screenshots["mobile"], "artifacts.screenshots.mobile")
    _validate_screenshot(desktop_path, "desktop", _VIEWPORTS["desktop"])
    _validate_screenshot(mobile_path, "mobile", _VIEWPORTS["mobile"])
    return normalized_path, structure_path, logic_path, synthesis_path, report_path


def _validate_primary_report_artifacts(
    normalized_path: Path, synthesis_path: Path, report_path: Path
) -> None:
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    synthesis = json.loads(synthesis_path.read_text(encoding="utf-8"))
    validate_report(synthesis, normalized, report_path.read_text(encoding="utf-8"))


def _validate_pass_artifacts(normalized_path: Path, structure_path: Path, logic_path: Path, synthesis_path: Path) -> None:
    validate_passes.validate_bundle(
        json.loads(normalized_path.read_text(encoding="utf-8")),
        json.loads(structure_path.read_text(encoding="utf-8")),
        json.loads(logic_path.read_text(encoding="utf-8")),
        json.loads(synthesis_path.read_text(encoding="utf-8")),
    )


def _validate_browser_checks(document: dict, report_path: Path) -> None:
    checks = _object(document["browser_checks"], "browser_checks")
    expected = {
        "desktop",
        "mobile",
        "scripts",
        "external_resources",
        "details_count",
        "timestamp_count",
        "validator_pass",
    }
    _exact_keys(checks, expected, "browser_checks")
    for name, (width, height) in _VIEWPORTS.items():
        viewport = _object(checks[name], f"browser_checks.{name}")
        _exact_keys(viewport, {"width", "height", "no_overflow"}, f"browser_checks.{name}")
        if _integer(viewport["width"], f"browser_checks.{name}.width") != width:
            raise ValueError(f"browser_checks.{name}.width must be {width}")
        if _integer(viewport["height"], f"browser_checks.{name}.height") != height:
            raise ValueError(f"browser_checks.{name}.height must be {height}")
        if not _boolean(viewport["no_overflow"], f"browser_checks.{name}.no_overflow"):
            raise ValueError(f"browser_checks.{name}.no_overflow must be true")

    if not _boolean(checks["validator_pass"], "browser_checks.validator_pass"):
        raise ValueError("browser_checks.validator_pass must be true")
    counter = _static_report_counts(report_path)
    recorded = {
        "scripts": counter.scripts,
        "external_resources": counter.external_resources,
        "details_count": counter.details_count,
        "timestamp_count": counter.timestamp_count,
    }
    for name, actual in recorded.items():
        declared = _integer(checks[name], f"browser_checks.{name}")
        if declared != actual:
            raise ValueError(f"browser_checks.{name} does not match report.html")
    if checks["scripts"] != 0:
        raise ValueError("browser_checks.scripts must be 0")
    if checks["external_resources"] != 0:
        raise ValueError("browser_checks.external_resources must be 0")


def _decimal_median(scores: list[Decimal]) -> Decimal:
    ordered = sorted(scores)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _validate_judges(document: dict) -> dict[str, Decimal]:
    judges = document["judges"]
    if not isinstance(judges, list) or len(judges) < 3:
        raise ValueError("judges must be an array with at least 3 entries")
    values = {category: [] for category in _CATEGORY_KEYS}
    seen_ids: set[str] = set()
    for index, value in enumerate(judges):
        path = f"judges[{index}]"
        judge = _object(value, path)
        _exact_keys(judge, {"id", "scores", "notes"}, path)
        judge_id = _string(judge["id"], f"{path}.id")
        if judge_id in seen_ids:
            raise ValueError("judges ids must be unique")
        seen_ids.add(judge_id)
        _string(judge["notes"], f"{path}.notes")
        scores = _object(judge["scores"], f"{path}.scores")
        _exact_keys(scores, set(_CATEGORY_KEYS), f"{path}.scores")
        for category in _CATEGORY_KEYS:
            score = _number(scores[category], f"{path}.scores.{category}")
            if not 0 <= score <= 100:
                raise ValueError(f"{path}.scores.{category} must be between 0 and 100")
            values[category].append(score)
    return {category: _decimal_median(scores) for category, scores in values.items()}


def _validate_aggregation(document: dict, medians: dict[str, Decimal]) -> None:
    aggregation = _object(document["aggregation"], "aggregation")
    _exact_keys(aggregation, {"category_medians", "weighted"}, "aggregation")
    declared_medians = _object(aggregation["category_medians"], "aggregation.category_medians")
    _exact_keys(declared_medians, set(_CATEGORY_KEYS), "aggregation.category_medians")
    for category in _CATEGORY_KEYS:
        declared = _number(declared_medians[category], f"aggregation.category_medians.{category}")
        if declared != medians[category]:
            raise ValueError(f"aggregation.category_medians.{category} is not the judge median")

    weighted = (
        Decimal("0.55") * medians["S"]
        + Decimal("0.20") * medians["E"]
        + Decimal("0.20") * medians["V"]
        + Decimal("0.05") * medians["T"]
    )
    if _number(aggregation["weighted"], "aggregation.weighted") != weighted:
        raise ValueError("aggregation.weighted is not the required weighted score")

    expected_passed = all(medians[category] >= 85 for category in _CATEGORY_KEYS) and weighted >= 95
    if _boolean(document["passed"], "passed") != expected_passed:
        raise ValueError("passed does not match the hard-gate result")
    if not expected_passed:
        raise ValueError("hard gate not met: every median must be at least 85 and weighted at least 95")


def validate_evaluation(evaluation_path: Path | str) -> None:
    """Validate a passing evaluation JSON and its local report artifacts."""
    path = Path(evaluation_path).resolve()
    document = _object(
        json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal),
        "evaluation",
    )
    _exact_keys(document, _ROOT_KEYS, "evaluation")
    if document["rubric_version"] != RUBRIC_VERSION:
        raise ValueError(f"rubric_version must be {RUBRIC_VERSION}")
    normalized_path, structure_path, logic_path, synthesis_path, report_path = _validate_artifacts(document, path.parent)
    _validate_pass_artifacts(normalized_path, structure_path, logic_path, synthesis_path)
    _validate_browser_checks(document, report_path)
    _validate_primary_report_artifacts(normalized_path, synthesis_path, report_path)
    medians = _validate_judges(document)
    _validate_aggregation(document, medians)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluation_json", type=Path)
    args = parser.parse_args(argv)
    try:
        validate_evaluation(args.evaluation_json)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
