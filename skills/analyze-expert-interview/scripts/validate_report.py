#!/usr/bin/env python3
"""Validate the synthesis report contract against its normalized transcript."""

import argparse
from html.parser import HTMLParser
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from compute_metrics import compute_metrics


__all__ = ["validate_report"]

_REQUIRED_TOP_LEVEL = {
    "metadata",
    "metrics",
    "scores",
    "diagnosis",
    "topics",
    "structure",
    "logic",
    "recommendations",
    "method",
}
_EXCLUDED_MODULE_NAMES = {
    "speech",
    "речь",
    "listener",
    "audience",
    "слушатель",
    "аудитория",
    "host evaluation",
    "ведущий",
    "montage",
    "editing sheet",
    "монтажный лист",
}
_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "′": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "″": '"',
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "―": "-",
        "−": "-",
        "…": "...",
        "\u00a0": " ",
    }
)
_MAX_REPORT_DEPTH = 256
_MAX_REPORT_NODES = 100_000


def _object(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _list(value: object, path: str, *, nonempty: bool = False) -> list:
    if not isinstance(value, list) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise ValueError(f"{path} must be a {qualifier}list")
    return value


def _string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _number(value: object, path: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} must be finite")
    return value


def _timestamp(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{path} must be a nonnegative integer")
    return value


def _normalized_text(value: str) -> str:
    return " ".join(value.translate(_PUNCTUATION_TRANSLATION).casefold().split())


def _module_name(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").replace("-", " ").split())


def _validate_excluded_modules(report: dict) -> None:
    for value, path in _iter_report_nodes(report):
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = _module_name(str(key))
                if normalized_key in _EXCLUDED_MODULE_NAMES:
                    raise ValueError(f"excluded module key at {path}.{key}")
                if normalized_key in {"title", "heading", "section title"} and isinstance(child, str):
                    if _module_name(child) in _EXCLUDED_MODULE_NAMES:
                        raise ValueError(f"excluded module heading at {path}.{key}")


def _iter_report_nodes(root: object):
    stack: list[tuple[object, str, int]] = [(root, "report", 0)]
    visited = 0
    while stack:
        value, path, depth = stack.pop()
        visited += 1
        if visited > _MAX_REPORT_NODES:
            raise ValueError("report exceeds maximum node count")
        if depth > _MAX_REPORT_DEPTH:
            raise ValueError("report exceeds maximum nesting depth")
        yield value, path
        if isinstance(value, dict):
            if visited + len(stack) + len(value) > _MAX_REPORT_NODES:
                raise ValueError("report exceeds maximum node count")
            children = [
                (child, f"{path}.{key}", depth + 1)
                for key, child in value.items()
            ]
            stack.extend(reversed(children))
        elif isinstance(value, list):
            if visited + len(stack) + len(value) > _MAX_REPORT_NODES:
                raise ValueError("report exceeds maximum node count")
            children = [
                (child, f"{path}[{index}]", depth + 1)
                for index, child in enumerate(value)
            ]
            stack.extend(reversed(children))


def _guest_runs(normalized: dict) -> list[list[dict]]:
    runs: list[list[dict]] = []
    for segment in normalized.get("segments", []):
        if segment.get("speaker") != "GUEST":
            continue
        if (
            runs
            and runs[-1][-1].get("end_ms") == segment.get("start_ms")
        ):
            runs[-1].append(segment)
        else:
            runs.append([segment])
    return runs


def _evidence_occurrences(quote: str, normalized: dict) -> list[dict]:
    needle = _normalized_text(quote)
    if len(re.findall(r"\w+", needle, flags=re.UNICODE)) < 4:
        raise ValueError("evidence quote must contain at least 4 normalized words")

    occurrences: list[dict] = []
    for run in _guest_runs(normalized):
        pieces = [_normalized_text(_string(segment.get("text"), "segment.text")) for segment in run]
        speech = ""
        starts: list[int] = []
        for piece in pieces:
            if speech:
                speech += " "
            starts.append(len(speech))
            speech += piece
        cursor = 0
        while True:
            found = speech.find(needle, cursor)
            if found < 0:
                break
            segment_index = max(
                index for index, start in enumerate(starts) if start <= found
            )
            occurrences.append(run[segment_index])
            cursor = found + 1
    return occurrences


def _validate_evidence(value: object, normalized: dict, path: str) -> None:
    evidence = _object(value, path)
    quote = evidence.get("quote")
    if not isinstance(quote, str):
        raise ValueError(f"{path}.quote must be a string with at least 4 normalized words")
    start_ms = _timestamp(evidence.get("start_ms"), f"{path}.start_ms")
    occurrences = _evidence_occurrences(quote, normalized)
    if not occurrences:
        raise ValueError(f"{path}: quote not found in GUEST transcript")
    if not any(
        segment["start_ms"] <= start_ms
        and (segment.get("end_ms") is None or start_ms < segment["end_ms"])
        for segment in occurrences
    ):
        raise ValueError(f"{path}.start_ms is outside the quote's starting GUEST cue")


def _validate_all_evidence(value: object, normalized: dict, path: str = "report") -> None:
    """Validate evidence in allowed extension fields as well as the core schema."""
    for child, child_path in _iter_report_nodes(value):
        if isinstance(child, dict) and "quote" in child:
            _validate_evidence(child, normalized, child_path)


def _require_fields(item: dict, fields: tuple[str, ...], path: str) -> None:
    missing = [field for field in fields if field not in item]
    if missing:
        raise ValueError(f"{path} missing required fields: {', '.join(missing)}")


def _validate_metrics(report_metrics: object, normalized: dict) -> None:
    actual = _object(report_metrics, "metrics")
    expected = compute_metrics(normalized)
    if set(actual) != set(expected):
        raise ValueError("metrics keys must exactly match compute_metrics output")
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if isinstance(expected_value, (int, float)) and not isinstance(expected_value, bool):
            if isinstance(actual_value, bool) or not isinstance(actual_value, (int, float)):
                raise ValueError(f"metrics.{key} has an invalid numeric type")
        elif type(actual_value) is not type(expected_value):
            raise ValueError(f"metrics.{key} has an invalid type")
        if actual_value != expected_value:
            raise ValueError(f"metrics.{key} does not match compute_metrics")


def _validate_shape_and_evidence(report: dict, normalized: dict) -> None:
    _object(report["metadata"], "metadata")
    scores = _object(report["scores"], "scores")
    for name in ("structural_chaos", "logical_soundness"):
        score = _number(scores.get(name), f"scores.{name}")
        if not 0 <= score <= 10:
            raise ValueError(f"scores.{name} must be between 0 and 10")

    diagnosis = _object(report["diagnosis"], "diagnosis")
    _require_fields(diagnosis, ("title", "paragraphs", "anchor_evidence"), "diagnosis")
    _string(diagnosis["title"], "diagnosis.title")
    for index, paragraph in enumerate(_list(diagnosis["paragraphs"], "diagnosis.paragraphs", nonempty=True)):
        _string(paragraph, f"diagnosis.paragraphs[{index}]")
    _validate_evidence(diagnosis["anchor_evidence"], normalized, "diagnosis.anchor_evidence")

    duration_ms = compute_metrics(normalized)["duration_ms"]
    topics = _list(report["topics"], "topics", nonempty=True)
    for topic_index, value in enumerate(topics):
        path = f"topics[{topic_index}]"
        topic = _object(value, path)
        _require_fields(topic, ("id", "label", "color", "spans"), path)
        for field in ("id", "label", "color"):
            _string(topic[field], f"{path}.{field}")
        for span_index, span_value in enumerate(_list(topic["spans"], f"{path}.spans", nonempty=True)):
            span_path = f"{path}.spans[{span_index}]"
            span = _object(span_value, span_path)
            _require_fields(span, ("start_ms", "end_ms", "weight", "note"), span_path)
            start_ms = _timestamp(span["start_ms"], f"{span_path}.start_ms")
            end_ms = _timestamp(span["end_ms"], f"{span_path}.end_ms")
            if start_ms >= end_ms or (
                isinstance(duration_ms, (int, float))
                and not isinstance(duration_ms, bool)
                and end_ms > duration_ms
            ):
                raise ValueError(f"{span_path}: span must have positive duration within transcript")
            if span["weight"] not in {"dominant", "touched"}:
                raise ValueError(f"{span_path}.weight: invalid topic span weight")
            _string(span["note"], f"{span_path}.note")

    structure = _object(report["structure"], "structure")
    _require_fields(structure, ("counts", "events"), "structure")
    for index, value in enumerate(_list(structure["counts"], "structure.counts")):
        item = _object(value, f"structure.counts[{index}]")
        _require_fields(item, ("label", "value"), f"structure.counts[{index}]")
        _string(item["label"], f"structure.counts[{index}].label")
        _number(item["value"], f"structure.counts[{index}].value")
    for index, value in enumerate(_list(structure["events"], "structure.events")):
        path = f"structure.events[{index}]"
        item = _object(value, path)
        _require_fields(item, ("kind", "quote", "start_ms", "analysis"), path)
        _string(item["kind"], f"{path}.kind")
        _string(item["analysis"], f"{path}.analysis")
        _validate_evidence(item, normalized, path)

    logic = _object(report["logic"], "logic")
    _require_fields(logic, ("defects", "theses", "strong_moments"), "logic")
    logic_specs = {
        "defects": ("category", "count", "example"),
        "theses": ("thesis", "status", "support", "quote", "start_ms"),
        "strong_moments": ("title", "quote", "start_ms", "analysis"),
    }
    for collection_name, required in logic_specs.items():
        items = _list(logic[collection_name], f"logic.{collection_name}")
        for index, value in enumerate(items):
            path = f"logic.{collection_name}[{index}]"
            item = _object(value, path)
            _require_fields(item, required, path)
            for field in required:
                if field not in {"count", "start_ms", "example"}:
                    _string(item[field], f"{path}.{field}")
            if collection_name == "defects":
                count = _number(item["count"], f"{path}.count")
                if count < 0:
                    raise ValueError(f"{path}.count must be nonnegative")
                example = _object(item["example"], f"{path}.example")
                _require_fields(example, ("quote", "start_ms", "analysis"), f"{path}.example")
                _string(example["analysis"], f"{path}.example.analysis")
                _validate_evidence(example, normalized, f"{path}.example")
            else:
                _validate_evidence(item, normalized, path)

    recommendations = _list(report["recommendations"], "recommendations")
    if len(recommendations) != 5:
        raise ValueError("recommendations must contain exactly 5 items")
    for index, value in enumerate(recommendations):
        path = f"recommendations[{index}]"
        item = _object(value, path)
        required_keys = {"title", "body", "candidate_id", "source_ids", "basis"}
        if set(item) != required_keys:
            raise ValueError(
                f"{path} must contain exactly title, body, candidate_id, source_ids, and basis"
            )
        _string(item["title"], f"{path}.title")
        _string(item["body"], f"{path}.body")
        candidate_id = _string(item["candidate_id"], f"{path}.candidate_id")
        identifier_pattern = r"^(structure|logic):[A-Za-z0-9._-]+$"
        candidate_match = re.fullmatch(identifier_pattern, candidate_id)
        if candidate_match is None:
            raise ValueError(
                f"{path}.candidate_id must be a qualified structure: or logic: identifier"
            )
        pass_prefix = candidate_match.group(1)
        source_ids = _list(item["source_ids"], f"{path}.source_ids", nonempty=True)
        seen_source_ids: set[str] = set()
        for source_index, source_id in enumerate(source_ids):
            source_path = f"{path}.source_ids[{source_index}]"
            canonical_source_id = _string(source_id, source_path)
            source_match = re.fullmatch(identifier_pattern, canonical_source_id)
            if source_match is None:
                raise ValueError(
                    f"{source_path} must be a qualified structure: or logic: identifier"
                )
            if source_match.group(1) != pass_prefix:
                raise ValueError(
                    f"{path}.source_ids must use the same pass prefix as candidate_id"
                )
            if canonical_source_id in seen_source_ids:
                raise ValueError(f"{path}.source_ids must contain unique strings")
            seen_source_ids.add(canonical_source_id)
        basis = _object(item["basis"], f"{path}.basis")
        if set(basis) != {"quote", "start_ms", "analysis"}:
            raise ValueError(
                f"{path}.basis must contain exactly quote, start_ms, and analysis"
            )
        _string(basis["analysis"], f"{path}.basis.analysis")
        _validate_evidence(basis, normalized, f"{path}.basis")
    _string(report["method"], "method")


class _ReportHTMLParser(HTMLParser):
    _VOID_ELEMENTS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
    _URL_ATTRIBUTES = {
        "action", "archive", "background", "cite", "codebase", "data",
        "formaction", "href", "icon", "longdesc", "manifest", "ping",
        "poster", "profile", "src", "srcset", "usemap", "xlink:href",
    }
    _ALLOWED_EXPLICIT_SELF_CLOSING = {"meta", "br", "hr", "img"}
    _FORBIDDEN_SMIL_ELEMENTS = {
        "set", "animate", "animatemotion", "animatetransform", "mpath"
    }
    _FORBIDDEN_RUNTIME_ELEMENTS = {
        "audio", "base", "embed", "iframe", "object", "source", "track",
        "video",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_count = 0
        self.head_count = 0
        self.body_count = 0
        self.style_count = 0
        self.errors: list[str] = []
        self._in_style = False
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self.headings: list[str] = []
        self._stack: list[str] = []
        self._phase = "before_html"
        self._doctype_seen = False
        self._head_closed = False
        self._body_closed = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._handle_start(tag, attrs, self_closing=tag in self._VOID_ELEMENTS)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self._ALLOWED_EXPLICIT_SELF_CLOSING:
            self.errors.append(f"forbidden self-closing non-void element <{tag}/>")
        self._handle_start(tag, attrs, self_closing=True)

    def _handle_start(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        *,
        self_closing: bool,
    ) -> None:
        names = [name.casefold() for name, _ in attrs]
        if len(names) != len(set(names)):
            self.errors.append(f"duplicate attribute on <{tag}>")
        attributes = dict(attrs)
        self._validate_attributes(tag, attributes)
        self._validate_start_order(tag, self_closing)
        if tag == "html":
            self.html_count += 1
        elif tag == "head":
            self.head_count += 1
        elif tag == "body":
            self.body_count += 1
        elif tag == "style":
            self.style_count += 1
            self._in_style = True
        elif tag == "link":
            self.errors.append("forbidden external link element")
        elif tag == "script":
            self.errors.append("forbidden script element")
        elif tag.casefold() in self._FORBIDDEN_RUNTIME_ELEMENTS:
            self.errors.append(f"forbidden runtime/media element <{tag}>")
        elif tag.casefold() in self._FORBIDDEN_SMIL_ELEMENTS:
            self.errors.append(f"forbidden SVG SMIL element <{tag}>")
        elif tag == "img" and attributes.get("src", "").strip() and not attributes["src"].strip().casefold().startswith("data:"):
            self.errors.append("forbidden external image")
        if tag == "meta" and (attributes.get("http-equiv") or "").casefold() == "refresh":
            self.errors.append("forbidden external meta refresh")
        if tag in {"h1", "h2", "h3"}:
            self._heading_tag = tag
            self._heading_parts = []
        style = attributes.get("style")
        if style:
            self._validate_css(style)

    def _validate_start_order(self, tag: str, self_closing: bool) -> None:
        if tag == "html":
            if self._phase != "before_html" or self._stack or self_closing:
                self.errors.append("HTML root is duplicated or misordered")
            self._phase = "in_html"
        elif self._phase != "in_html" or not self._stack:
            self.errors.append(f"HTML element <{tag}> is outside the html root")
        elif tag == "head":
            if self._stack != ["html"] or self.head_count or self.body_count or self_closing:
                self.errors.append("HTML head is duplicated or misordered")
        elif tag == "body":
            if self._stack != ["html"] or not self._head_closed or self.body_count or self_closing:
                self.errors.append("HTML body is duplicated or misordered")
        elif "head" not in self._stack and "body" not in self._stack:
            self.errors.append(f"HTML element <{tag}> must be inside head or body")
        if not self_closing:
            self._stack.append(tag)

    def _validate_attributes(self, tag: str, attributes: dict[str, str | None]) -> None:
        for name, raw_value in attributes.items():
            normalized_name = name.casefold()
            value = (raw_value or "").strip()
            compact = re.sub(r"[\x00-\x20]+", "", value).casefold()
            if normalized_name == "xml:base" and value:
                self.errors.append("forbidden xml:base attribute")
            if normalized_name.startswith("on"):
                self.errors.append("forbidden event-handler attribute")
            if re.search(r"(?:https?:|data:|javascript:|vbscript:|(?<!:)//)", compact):
                if not self._is_allowed_youtube_anchor(tag, normalized_name, value):
                    self.errors.append(f"forbidden external URL in {tag}.{name}")
            if normalized_name in self._URL_ATTRIBUTES and value:
                allowed_youtube = self._is_allowed_youtube_anchor(
                    tag, normalized_name, value
                )
                if not allowed_youtube:
                    self.errors.append(f"forbidden external resource in {tag}.{name}")
            attribute_css = self._normalize_css(value)
            for match in re.finditer(
                r"url\(\s*(['\"]?)(.*?)\1\s*\)",
                attribute_css,
                flags=re.IGNORECASE,
            ):
                if not re.fullmatch(r"#[A-Za-z_][\w:.-]*", match.group(2).strip()):
                    self.errors.append(f"forbidden url() in {tag}.{name}")

    @staticmethod
    def _is_allowed_youtube_anchor(tag: str, name: str, value: str) -> bool:
        if tag != "a" or name != "href":
            return False
        parsed = urlsplit(value)
        return (
            parsed.scheme.casefold() == "https"
            and parsed.hostname is not None
            and parsed.hostname.casefold()
            in {"www.youtube.com", "youtube.com", "youtu.be"}
            and parsed.username is None
            and parsed.password is None
        )

    def handle_decl(self, decl: str) -> None:
        if (
            self._doctype_seen
            or self._phase != "before_html"
            or decl.strip().casefold() != "doctype html"
        ):
            self.errors.append("HTML doctype is duplicated or misordered")
        self._doctype_seen = True

    def handle_endtag(self, tag: str) -> None:
        if not self._stack or self._stack[-1] != tag:
            self.errors.append(f"HTML closing tag </{tag}> is misordered")
        else:
            self._stack.pop()
            if tag == "head":
                self._head_closed = True
            elif tag == "body":
                self._body_closed = True
            elif tag == "html":
                if not self._head_closed or not self._body_closed:
                    self.errors.append("HTML root closed before head and body")
                self._phase = "after_html"
        if tag == "style":
            self._in_style = False
        if tag == self._heading_tag:
            self.headings.append("".join(self._heading_parts))
            self._heading_tag = None
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if data.strip() and (
            self._phase != "in_html"
            or not self._stack
            or self._stack == ["html"]
        ):
            self.errors.append("HTML has content outside head or body")
        if self._in_style:
            self._validate_css(data)
        if self._heading_tag:
            self._heading_parts.append(data)

    def handle_comment(self, data: str) -> None:
        if self._phase != "in_html":
            self.errors.append("HTML has a comment outside the root")

    def handle_pi(self, data: str) -> None:
        self.errors.append("HTML processing instructions are forbidden")

    def _validate_css(self, css: str) -> None:
        css = self._normalize_css(css)
        if re.search(r"@import\b", css, flags=re.IGNORECASE):
            self.errors.append("forbidden external CSS import")
        if re.search(
            r"@font-face\b|(?:-webkit-)?image-set\s*\(|cross-fade\s*\(",
            css,
            flags=re.IGNORECASE,
        ):
            self.errors.append("forbidden CSS resource function")
        for match in re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", css, flags=re.IGNORECASE):
            self.errors.append("forbidden external CSS URL")

    @staticmethod
    def _unescape_css(css: str) -> str:
        def replace_escape(match: re.Match) -> str:
            hexadecimal = match.group(1)
            if hexadecimal is not None:
                codepoint = int(hexadecimal, 16)
                if codepoint == 0 or codepoint > 0x10FFFF:
                    return "\ufffd"
                return chr(codepoint)
            return match.group(2)

        return re.sub(
            r"\\(?:([0-9a-fA-F]{1,6})\s?|([^\r\n]))",
            replace_escape,
            css,
        )

    @classmethod
    def _normalize_css(cls, css: str) -> str:
        return cls._unescape_css(cls._strip_css_comments(css))

    @staticmethod
    def _strip_css_comments(css: str) -> str:
        output: list[str] = []
        index = 0
        quote: str | None = None
        while index < len(css):
            character = css[index]
            if quote is not None:
                output.append(character)
                if character == "\\" and index + 1 < len(css):
                    index += 1
                    output.append(css[index])
                elif character == quote:
                    quote = None
                index += 1
                continue
            if character in {"'", '"'}:
                quote = character
                output.append(character)
                index += 1
                continue
            if css.startswith("/*", index):
                closing = css.find("*/", index + 2)
                if closing < 0:
                    raise ValueError("forbidden unterminated CSS comment")
                index = closing + 2
                continue
            output.append(character)
            index += 1
        return "".join(output)

    def validate_document(self) -> None:
        if self._stack:
            self.errors.append("HTML contains unclosed elements")
        if self._phase != "after_html":
            self.errors.append("HTML root was not closed")


def _validate_html(html_text: str) -> None:
    if not isinstance(html_text, str) or not html_text.strip():
        raise ValueError("HTML must be a non-empty document")
    parser = _ReportHTMLParser()
    parser.feed(html_text)
    parser.close()
    parser.validate_document()
    if parser.errors:
        raise ValueError(parser.errors[0])
    if parser.html_count != 1 or parser.head_count != 1 or parser.body_count != 1:
        raise ValueError("HTML must contain one html, head, and body")
    if parser.style_count < 1:
        raise ValueError("HTML requires an inline style element")
    for heading in parser.headings:
        if _module_name(heading) in _EXCLUDED_MODULE_NAMES:
            raise ValueError("HTML contains an excluded module heading")


def validate_report(report: dict, normalized: dict, html_text: str | None = None) -> None:
    """Raise ValueError when a report violates the synthesis contract."""
    report = _object(report, "report")
    normalized = _object(normalized, "normalized")
    missing = sorted(_REQUIRED_TOP_LEVEL - set(report))
    if missing:
        raise ValueError(f"report missing required top-level keys: {', '.join(missing)}")
    _validate_excluded_modules(report)
    _validate_metrics(report["metrics"], normalized)
    _validate_shape_and_evidence(report, normalized)
    _validate_all_evidence(report, normalized)
    if html_text is not None:
        _validate_html(html_text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a broadcast analysis report")
    parser.add_argument("normalized_json", type=Path)
    parser.add_argument("report_json", type=Path)
    parser.add_argument("html", type=Path, nargs="?")
    args = parser.parse_args(argv)
    try:
        normalized = json.loads(args.normalized_json.read_text(encoding="utf-8"))
        report = json.loads(args.report_json.read_text(encoding="utf-8"))
        html_text = args.html.read_text(encoding="utf-8") if args.html else None
        validate_report(report, normalized, html_text)
    except (OSError, json.JSONDecodeError, RecursionError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
