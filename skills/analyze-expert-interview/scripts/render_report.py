#!/usr/bin/env python3
"""Render a validated expert-broadcast synthesis JSON as static HTML."""

import argparse
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from validate_report import validate_report


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "assets" / "report-template.html"
YOUTUBE_HOSTS = {"www.youtube.com", "youtube.com", "youtu.be"}
RULER_CADENCE_MS = 10 * 60 * 1000
EVENT_SUMMARY_GROUPS = (
    ("navigation", "Navigation", {"transition", "return"}),
    ("branches", "Branches", {"digression", "nested_digression"}),
    ("breaks", "Breaks", {"abandoned_thread", "loop"}),
    ("direct-answers", "Direct answers", {"answer_directness"}),
)
DEFECT_CATEGORY_LABELS = {
    "unsupported_claim": "unsupported claim",
    "contradiction": "contradiction",
    "non_sequitur": "non sequitur",
    "undefined_term": "undefined term",
    "overgeneralisation": "overgeneralisation",
    "missing_qualification": "missing qualification",
    "abandoned_reasoning": "abandoned reasoning",
}
THESIS_STATUS_LABELS = {
    "supported": "supported",
    "partially_supported": "partially supported",
    "unsupported": "unsupported",
}


def _text(value: object) -> str:
    return html.escape(str(value), quote=True)


def _seconds(milliseconds: int) -> int:
    return milliseconds // 1000


def _timestamp_label(milliseconds: int) -> str:
    seconds = _seconds(milliseconds)
    minutes, seconds_remainder = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds_remainder:02d}" if hours else f"{minutes:02d}:{seconds_remainder:02d}"


def _safe_youtube_url(value: object) -> str | None:
    """Return a safe canonical YouTube URL or ``None`` for any other input."""
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.hostname.casefold() not in YOUTUBE_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def timestamp(milliseconds: int, source_url: object) -> str:
    label = _timestamp_label(milliseconds)
    safe_source_url = _safe_youtube_url(source_url)
    if safe_source_url is None:
        return f'<span class="tc">{label}</span>'
    parsed = urlsplit(safe_source_url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "t"]
    query.append(("t", f"{_seconds(milliseconds)}s"))
    href = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))
    return f'<a class="tc" href="{_text(href)}">{label}</a>'


def _number(value: object) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


def _color(value: object) -> str:
    """Allow only simple hex colors from report data in SVG/CSS contexts."""
    if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", value):
        return value
    return "#8a8985"


def _presentation_label(value: str, labels: dict[str, str], fallback: str) -> str:
    """Translate known machine enums while retaining an unknown report value."""
    return labels.get(value, f"{fallback}: {value}")


def _defect_category_label(value: str) -> str:
    return _presentation_label(value, DEFECT_CATEGORY_LABELS, "Other category")


def _thesis_status_label(value: str) -> str:
    return _presentation_label(value, THESIS_STATUS_LABELS, "Other status")


def _duration(milliseconds: object) -> str:
    if not isinstance(milliseconds, int):
        return "duration partly unknown"
    hours, rem = divmod(milliseconds // 1000, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def _display_topic_label(label: str, limit: int = 30) -> str:
    if len(label) <= limit:
        return label
    return f"{label[:limit - 1].rsplit(' ', 1)[0]}…"


def _evidence(item: dict, source_url: object, analysis_key: str = "analysis") -> str:
    return (
        '<li><blockquote>“' + _text(item["quote"]) + '”</blockquote>'
        + timestamp(item["start_ms"], source_url)
        + (f'<p>{_text(item[analysis_key])}</p>' if item.get(analysis_key) else "")
        + "</li>"
    )


def _ruler_ticks(duration_ms: int) -> list[int]:
    ticks = list(range(0, duration_ms, RULER_CADENCE_MS))
    if not ticks or ticks[-1] != duration_ms:
        ticks.append(duration_ms)
    return ticks


def _event_summary(events: list[dict]) -> str:
    items = []
    for group, label, kinds in EVENT_SUMMARY_GROUPS:
        count = sum(1 for event in events if event.get("kind") in kinds)
        if count:
            items.append(
                f'<li class="event-summary-item event-summary-{group}"><span>{label}</span><strong>{count}</strong></li>'
            )
    return f'<ul class="event-summary" aria-label="Structural event summary">{"".join(items)}</ul>' if items else ""


def _topic_svg(topics: list[dict], duration_ms: object, events: list[dict]) -> str:
    duration = duration_ms if isinstance(duration_ms, int) and duration_ms > 0 else max(
        span["end_ms"] for topic in topics for span in topic["spans"]
    )
    plot_x = 150
    plot_width = 830
    rows_y = 42
    event_y = rows_y + len(topics) * 36 + 10
    height = max(98, event_y + 28)
    groups = []
    legend = []
    ticks = _ruler_ticks(duration)
    for index, tick_ms in enumerate(ticks):
        ratio = tick_ms / duration
        x = plot_x + ratio * plot_width
        anchor = "start" if index == 0 else "end" if index == len(ticks) - 1 else "middle"
        groups.append(
            f'<text x="{x:.2f}" y="13" fill="#8a8985" font-size="11" text-anchor="{anchor}">{_timestamp_label(tick_ms)}</text>'
        )
        groups.append(
            f'<line class="trajectory-grid" x1="{x:.2f}" y1="19" x2="{x:.2f}" y2="{event_y - 7}" stroke="#e6e5e1" stroke-width="1"></line>'
        )
    for row, topic in enumerate(topics):
        y = rows_y + row * 36
        color = _color(topic["color"])
        label = _text(topic["label"])
        display_label = _text(_display_topic_label(topic["label"]))
        legend.append(f'<span><i style="background:{color}"></i>{label}</span>')
        groups.append(f'<text x="0" y="{y + 12}" fill="#8a8985" font-size="12"><title>{label}</title>{display_label}</text>')
        for span in topic["spans"]:
            x = plot_x + (span["start_ms"] / duration) * plot_width
            width = max(3, ((span["end_ms"] - span["start_ms"]) / duration) * plot_width)
            opacity = "0.9" if span["weight"] == "dominant" else "0.38"
            note = _text(f'{topic["label"]}: {span["note"]}')
            groups.append(
                f'<g><title>{note}</title><rect x="{x:.2f}" y="{y}" width="{width:.2f}" height="18" rx="3" fill="{color}" fill-opacity="{opacity}"></rect></g>'
            )
    groups.append(f'<text x="0" y="{event_y + 5}" fill="#8a8985" font-size="11">Events</text>')
    groups.append(
        f'<line x1="{plot_x}" y1="{event_y}" x2="{plot_x + plot_width}" y2="{event_y}" stroke="#8a8985" stroke-width="1"></line>'
    )
    for index, event in enumerate(events):
        x = plot_x + (event["start_ms"] / duration) * plot_width
        marker_y = event_y - 5 - (index % 2) * 6
        note = _text(f'{_duration(event["start_ms"])} — {event["kind"]}: {event["quote"]}')
        groups.append(
            f'<g class="event-marker"><title>{note}</title><line x1="{x:.2f}" y1="{event_y}" x2="{x:.2f}" y2="{marker_y}" stroke="#2a78d6" stroke-width="1.5"></line><circle cx="{x:.2f}" cy="{marker_y}" r="3" fill="#2a78d6"></circle></g>'
        )
    svg = '<svg role="img" aria-label="Guest topic trajectory" viewBox="0 0 1000 ' + str(height) + '">' + "".join(groups) + "</svg>"
    return (
        '<div class="trajectory"><p class="trajectory-key"><span><i class="topic-key"></i>Colored spans — topics</span><span><i class="event-key"></i>Blue markers — structural events</span></p>'
        '<p class="trajectory-cue">Diagram exceeds screen width → scroll horizontally</p>'
        f'<div class="trajectory-scroll">{svg}</div><div class="legend">{"".join(legend)}</div></div>'
    )


def _diagnosis_points(paragraphs: list[object]) -> str:
    labels = ("Structure", "Logic", "Limitations", "Opportunities")
    points = "".join(
        f'<div class="diagnosis-point"><p class="diagnosis-label">{labels[index] if index < len(labels) else f"Point {index + 1}"}</p><p class="diagnosis-copy">{_text(paragraph)}</p></div>'
        for index, paragraph in enumerate(paragraphs)
    )
    return f'<div class="diagnosis-points">{points}</div>'


def render_report(report: dict) -> str:
    """Return deterministic, escaped, standalone HTML for an already-valid report."""
    metadata = report["metadata"]
    source_url = metadata.get("source_url")
    metrics = report["metrics"]
    scores = report["scores"]
    diagnosis = report["diagnosis"]
    structure = report["structure"]
    logic = report["logic"]
    safe_source_url = _safe_youtube_url(source_url)
    source_link = (
        f'<a href="{_text(safe_source_url)}">Recording</a>'
        if safe_source_url is not None
        else "Recording unavailable"
    )
    tile_data = [
        ("Guest speaking time", _duration(metrics.get("guest_speaking_ms"))),
        ("Guest speaking share", f'{metrics.get("guest_speaking_share", 0) * 100:.0f}%'),
        ("Guest turns", _number(metrics.get("guest_turn_count", 0))),
        ("Longest guest turn", _duration(metrics.get("longest_guest_turn_ms"))),
        ("Host-to-guest transitions", _number(metrics.get("host_to_guest_transitions", 0))),
    ]
    tiles = "".join(f'<div class="tile"><div class="tile-label">{_text(label)}</div><span class="tile-value">{_text(value)}</span></div>' for label, value in tile_data)
    score_cards = "".join(
        f'<div class="score"><div class="score-label">{_text(label)}</div><div class="score-value">{_number(value)} <small>/ 10</small></div><div class="meter"><span style="width:{float(value) * 10:.1f}%"></span></div><p class="polarity">{polarity}</p></div>'
        for label, value, polarity in (
            ("Structural chaos", scores["structural_chaos"], "Higher means more disorder."),
            ("Logical soundness", scores["logical_soundness"], "Higher means stronger reasoning."),
        )
    )
    counts = "".join(f'<tr><td>{_text(item["label"])}</td><td>{_text(_number(item["value"]))}</td></tr>' for item in structure["counts"])
    defects = "".join(
        f'<tr><td data-label="Category"><span class="logic-enum">{_text(_defect_category_label(item["category"]))}</span></td><td data-label="Count">{_text(_number(item["count"]))}</td><td data-label="Evidence">“{_text(item["example"]["quote"])}”<br>{timestamp(item["example"]["start_ms"], source_url)}<br>{_text(item["example"]["analysis"])}</td></tr>'
        for item in logic["defects"]
    )
    theses = "".join(
        f'<tr><td data-label="Claim">{_text(item["thesis"])}</td><td data-label="Status"><span class="logic-enum">{_text(_thesis_status_label(item["status"]))}</span></td><td data-label="Basis">{_text(item["support"])}<br>“{_text(item["quote"])}” {timestamp(item["start_ms"], source_url)}</td></tr>'
        for item in logic["theses"]
    )
    events = "".join(_evidence(item, source_url) for item in structure["events"])
    event_summary = _event_summary(structure["events"])
    strong = "".join(
        f'<li><blockquote>“{_text(item["quote"])}”</blockquote>{timestamp(item["start_ms"], source_url)}<p><strong>{_text(item["title"])}.</strong> {_text(item["analysis"])}</p></li>'
        for item in logic["strong_moments"]
    )
    recommendations = "".join(
        f'<li><strong>{_text(item["title"])}</strong>'
        f'<p class="recommendation-body">{_text(item["body"])}</p>'
        f'<div class="recommendation-basis"><p class="basis-label">Basis</p>'
        f'<blockquote>“{_text(item["basis"]["quote"])}”</blockquote>'
        f'{timestamp(item["basis"]["start_ms"], source_url)}'
        f'<p class="basis-analysis">{_text(item["basis"]["analysis"])}</p></div></li>'
        for item in report["recommendations"]
    )
    topic_row_parts = []
    for topic in report["topics"]:
        span_labels = []
        for span in topic["spans"]:
            label = (
                f'{_duration(span["start_ms"])}–{_duration(span["end_ms"])} '
                f'({span["weight"]}): {span["note"]}'
            )
            span_labels.append(_text(label))
        span_text = "; ".join(span_labels)
        topic_row_parts.append(
            f'<tr><td>{_text(topic["label"])}</td><td>{span_text}</td></tr>'
        )
    topic_rows = "".join(topic_row_parts)
    paragraphs = _diagnosis_points(diagnosis["paragraphs"])
    body = f'''<header><p class="kicker">Expert interview analysis: guest only</p><h1>{_text(metadata.get("title", "Interview analysis"))}</h1><p class="lede">Structure and reasoning, based on the guest’s contribution to the recording.</p><div class="meta"><span>{source_link}</span><span>Duration {_text(_duration(metrics.get("duration_ms")))}</span><span>Roles: HOST / GUEST</span><span>Transcript provenance: normalized speaker-labelled source</span></div></header><div class="tiles">{tiles}</div><div class="scores">{score_cards}</div><section><h2>1. Diagnosis</h2><h3 class="diagnosis-title">{_text(diagnosis["title"])}</h3>{paragraphs}<aside class="callout"><p class="quote">“{_text(diagnosis["anchor_evidence"]["quote"])}”</p>{timestamp(diagnosis["anchor_evidence"]["start_ms"], source_url)}</aside></section><section><h2>Topic trajectory</h2>{_topic_svg(report["topics"], metrics.get("duration_ms"), structure["events"])}</section><section><h2>Structural account</h2><div class="scroll"><table><thead><tr><th>Structural measure — guest only</th><th>Value</th></tr></thead><tbody>{counts}</tbody></table></div><h3>Representative moments</h3>{event_summary}<ol class="evidence">{events}</ol></section><section><h2>2. Logic</h2><h3>Gaps</h3><div class="scroll logic-scroll"><table class="logic-table defects-table"><thead><tr><th>Category</th><th>Count</th><th>Evidence</th></tr></thead><tbody>{defects}</tbody></table></div><h3>Defended claims</h3><div class="scroll logic-scroll"><table class="logic-table theses-table"><thead><tr><th>Claim</th><th>Status</th><th>Basis</th></tr></thead><tbody>{theses}</tbody></table></div><h3>Strong reasoning moments</h3><ol class="evidence">{strong}</ol></section><section><h2>3. Five revisions</h2><ol class="recommendations">{recommendations}</ol></section><section><details><summary>Guest topic map</summary><div class="scroll"><table><thead><tr><th>Topic</th><th>Guest trajectory</th></tr></thead><tbody>{topic_rows}</tbody></table></div></details><details><summary>Method</summary><p>{_text(report["method"])}</p></details></section>'''
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace("__PAGE_TITLE__", _text(metadata.get("title", "Interview analysis"))).replace("__BODY__", body)


def _normalized_path(report_path: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    return report_path.with_name("normalized.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a validated expert broadcast report")
    parser.add_argument("report_json", type=Path)
    parser.add_argument("output_html", type=Path)
    parser.add_argument("--normalized", type=Path, help="normalized transcript JSON (defaults to normalized.json beside report)")
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report_json.read_text(encoding="utf-8"))
        normalized = json.loads(_normalized_path(args.report_json, args.normalized).read_text(encoding="utf-8"))
        validate_report(report, normalized)
        document = render_report(report)
        validate_report(report, normalized, document)
        args.output_html.write_text(document, encoding="utf-8")
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
