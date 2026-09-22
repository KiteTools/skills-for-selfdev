import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests"))

from render_report import render_report  # noqa: E402
from test_validate_report import normalized_document, valid_report  # noqa: E402
from validate_report import validate_report  # noqa: E402


class RenderReportTests(unittest.TestCase):
    def render(self, source_url=None):
        report = valid_report(normalized_document())
        if source_url is not None:
            report["metadata"]["source_url"] = source_url
        html = render_report(report)
        validate_report(report, normalized_document(), html)
        return html

    def test_renders_required_editorial_grammar(self):
        html = self.render()

        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn('class="wrap"', html)
        self.assertIn('class="tiles"', html)
        self.assertIn('class="scores"', html)
        self.assertIn('class="callout"', html)
        self.assertIn('class="scroll"', html)
        self.assertIn('class="tc"', html)
        self.assertEqual(html.count("1. Diagnosis"), 1)
        self.assertEqual(html.count("2. Logic"), 1)
        self.assertEqual(html.count("3. Five revisions"), 1)
        self.assertIn("Higher means more disorder.", html)
        self.assertIn("Higher means stronger reasoning.", html)
        self.assertIn('<svg role="img"', html)
        self.assertIn("<title>", html)
        self.assertIn("<details>", html)
        self.assertIn("Guest topic map", html)
        self.assertIn("Method", html)

    def test_renders_all_static_report_ui_in_english(self):
        html = self.render("https://www.youtube.com/watch?v=abc123")

        for label in (
            'lang="en"',
            "Expert interview analysis: guest only",
            "Structure and reasoning, based on the guest’s contribution to the recording.",
            ">Recording</a>",
            "Duration 0:08",
            "Roles: HOST / GUEST",
            "Transcript provenance: normalized speaker-labelled source",
            "Guest speaking time",
            "Guest speaking share",
            "Guest turns",
            "Longest guest turn",
            "Host-to-guest transitions",
            "Structural chaos",
            "Logical soundness",
            "Topic trajectory",
            "Structural account",
            "Representative moments",
            "Gaps",
            "Defended claims",
            "Strong reasoning moments",
            "Guest topic map",
            "Method",
            'aria-label="Guest topic trajectory"',
        ):
            self.assertIn(label, html)

        for old_label in ("Разбор экспертного эфира", "Траектория тем", "Пять правок", 'lang="ru"'):
            self.assertNotIn(old_label, html)

    def test_renders_diagnosis_title_once_in_the_diagnosis_section(self):
        report = valid_report(normalized_document())
        report["metadata"]["title"] = "Название эфира"
        report["diagnosis"]["title"] = "Переход от наблюдения к решению"

        html = render_report(report)

        self.assertIn('<h3 class="diagnosis-title">Переход от наблюдения к решению</h3>', html)
        self.assertEqual(html.count("Переход от наблюдения к решению"), 1)
        self.assertIn("<h1>Название эфира</h1>", html)

    def test_uses_safe_youtube_urls_for_recording_and_timestamps(self):
        for source_url, timestamp_href in (
            ("https://youtu.be/abc123", "https://youtu.be/abc123?t=1s"),
            ("https://youtube.com/watch?v=abc123", "https://youtube.com/watch?v=abc123&amp;t=1s"),
        ):
            with self.subTest(source_url=source_url):
                html = self.render(source_url)
                self.assertIn(f'href="{source_url}"', html)
                self.assertIn(f'href="{timestamp_href}"', html)

    def test_credentials_bearing_youtube_url_renders_no_links_and_validates(self):
        report = valid_report(normalized_document())
        report["metadata"]["source_url"] = "https://user:pass@youtube.com/watch?v=abc123"

        html = render_report(report)

        self.assertIn("Recording unavailable", html)
        self.assertNotIn("href=", html)
        validate_report(report, normalized_document(), html)

    def test_many_topics_keep_full_labels_and_constrain_trajectory_height(self):
        report = valid_report(normalized_document())
        long_label = "Очень длинная тема с полной формулировкой для подробной проверки отображения"
        report["topics"] = [
            {
                "id": f"topic-{index}",
                "label": long_label if index == 0 else f"Topic {index}",
                "color": "#3355aa",
                "spans": [{"start_ms": 1_000, "end_ms": 7_000, "weight": "dominant", "note": "Полная заметка."}],
            }
            for index in range(24)
        ]

        html = render_report(report)

        self.assertIn("max-height: 560px", html)
        self.assertIn("overflow-y: auto", html)
        self.assertIn(f"<title>{long_label}</title>", html)
        self.assertIn("Очень длинная тема с полной…", html)
        self.assertIn(long_label, html)
        validate_report(report, normalized_document(), html)

    def test_renders_all_recommendation_bases_without_machine_provenance(self):
        report = valid_report(normalized_document())
        report["metadata"]["source_url"] = "https://www.youtube.com/watch?v=abc123"
        bases = (
            ("First I noticed the difficult pattern", "Основание первой правки."),
            ("I noticed the difficult pattern and", "Основание второй правки."),
            ("noticed the difficult pattern and then", "Основание третьей правки."),
            ("the difficult pattern and then chose", "Основание четвёртой правки."),
            ("difficult pattern and then chose a clearer direction.", "Основание пятой правки."),
        )
        for recommendation, (quote, analysis) in zip(report["recommendations"], bases):
            recommendation["basis"] = {"quote": quote, "start_ms": 1_000, "analysis": analysis}

        linked = render_report(report)
        plain_report = copy.deepcopy(report)
        plain_report["metadata"].pop("source_url")
        plain = render_report(plain_report)

        self.assertEqual(linked.count('class="recommendation-basis"'), 5)
        self.assertEqual(linked.count('<p class="basis-label">Basis</p>'), 5)
        for quote, analysis in bases:
            self.assertIn(f"“{quote}”", linked)
            self.assertIn(analysis, linked)
        self.assertEqual(linked.count('href="https://www.youtube.com/watch?v=abc123&amp;t=1s"'), 10)
        self.assertNotIn("structure:recommendation-1", linked)
        self.assertNotIn("structure:event-1", linked)
        self.assertNotIn("href=", plain)
        self.assertEqual(plain.count('<span class="tc">00:01</span>'), 10)
        validate_report(report, normalized_document(), linked)
        validate_report(plain_report, normalized_document(), plain)

    def test_escapes_recommendation_basis_analysis(self):
        report = valid_report(normalized_document())
        report["recommendations"][0]["basis"]["analysis"] = '<img src=x onerror="alert(1)">'

        html = render_report(report)

        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", html)
        self.assertNotIn('<img src=x onerror=', html)
        validate_report(report, normalized_document(), html)

    def test_uses_clickable_youtube_timestamps_only_with_valid_youtube_url(self):
        linked = self.render("https://www.youtube.com/watch?v=abc123")
        unlinked = self.render()

        self.assertIn('href="https://www.youtube.com/watch?v=abc123&amp;t=1s"', linked)
        self.assertNotIn("href=", unlinked)
        self.assertIn('class="tc"', unlinked)

    def test_rejects_invalid_source_url_by_rendering_plain_timestamps(self):
        html = self.render("https://example.com/watch?v=abc123")

        self.assertNotIn("href=", html)
        self.assertIn("00:01", html)

    def test_escapes_report_content_and_cannot_create_markup_or_attributes(self):
        report = valid_report(normalized_document())
        payload = '<img src=x onerror="alert(1)"><style>@import "bad"</style>'
        report["metadata"]["title"] = payload
        report["diagnosis"]["title"] = payload
        report["diagnosis"]["paragraphs"] = [payload]
        report["recommendations"][0]["body"] = payload

        html = render_report(report)
        validate_report(report, normalized_document(), html)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", html)
        self.assertNotIn('<img src=x onerror=', html)
        self.assertNotIn("<style>@import", html)

    def test_topic_color_cannot_inject_css(self):
        report = valid_report(normalized_document())
        report["topics"][0]["color"] = "red; background: url(https://example.com/x)"

        html = render_report(report)
        self.assertNotIn("example.com", html)
        self.assertIn("background:#8a8985", html)

    def test_logic_tables_render_as_labelled_cards_on_mobile(self):
        html = self.render()

        self.assertIn('<table class="logic-table defects-table">', html)
        self.assertIn('<table class="logic-table theses-table">', html)
        for label in ("Category", "Count", "Evidence", "Claim", "Status", "Basis"):
            self.assertIn(f'data-label="{label}"', html)
        self.assertIn(".logic-scroll { overflow-x: visible; }", html)
        self.assertIn(".logic-table { min-width: 0; }", html)
        self.assertIn(".logic-table td { display: block; width: 100%;", html)
        self.assertIn(".logic-table td::before { display: block;", html)
        self.assertNotIn(".logic-table td { display: grid;", html)

    def test_maps_known_logic_enums_to_english_presentation_labels(self):
        report = valid_report(normalized_document())
        report["logic"]["defects"] = [
            {**copy.deepcopy(report["logic"]["defects"][0]), "category": category}
            for category in (
                "unsupported_claim",
                "contradiction",
                "non_sequitur",
                "undefined_term",
                "overgeneralisation",
                "missing_qualification",
                "abandoned_reasoning",
            )
        ]
        report["logic"]["theses"] = [
            {**copy.deepcopy(report["logic"]["theses"][0]), "status": status}
            for status in ("supported", "partially_supported", "unsupported")
        ]

        html = render_report(report)

        for label in (
            "unsupported claim",
            "contradiction",
            "overgeneralisation",
            "non sequitur",
            "undefined term",
            "missing qualification",
            "abandoned reasoning",
            "supported",
            "partially supported",
            "unsupported",
        ):
            self.assertIn(f">{label}</span>", html)
        self.assertNotIn(">unsupported_claim</span>", html)
        validate_report(report, normalized_document(), html)

    def test_unknown_logic_enums_are_preserved_and_escaped_under_english_labels(self):
        report = valid_report(normalized_document())
        payload = '<img src=x onerror="alert(1)">'
        report["logic"]["defects"][0]["category"] = payload
        report["logic"]["theses"][0]["status"] = payload

        html = render_report(report)

        self.assertIn("Other category: &lt;img", html)
        self.assertIn("Other status: &lt;img", html)
        self.assertNotIn('<img src=x onerror=', html)
        validate_report(report, normalized_document(), html)

    def test_topic_trajectory_has_timestamp_ruler_and_event_markers(self):
        report = valid_report(normalized_document())
        second_event = copy.deepcopy(report["structure"]["events"][0])
        second_event["start_ms"] = 2_000
        report["structure"]["events"].append(second_event)

        html = render_report(report)

        for label in ("00:00", "00:08"):
            self.assertIn(f'>{label}</text>', html)
        self.assertEqual(html.count('class="trajectory-grid"'), 2)
        self.assertEqual(html.count('class="event-marker"'), 2)
        self.assertIn("<title>0:01 — turning_point: First I noticed the difficult pattern</title>", html)
        self.assertIn("<title>0:02 — turning_point: First I noticed the difficult pattern</title>", html)
        validate_report(report, normalized_document(), html)

    def test_trajectory_event_marker_tooltips_escape_report_content(self):
        report = valid_report(normalized_document())
        report["structure"]["events"][0]["kind"] = '<img src=x onerror="alert(1)">'

        html = render_report(report)

        self.assertIn('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;', html)
        self.assertNotIn('<img src=x onerror=', html)
        self.assertNotIn('event-summary-navigation', html)
        validate_report(report, normalized_document(), html)

    def test_topic_trajectory_formats_hour_long_timestamp_ruler(self):
        report = valid_report(normalized_document())
        report["metrics"]["duration_ms"] = 5_962_000

        html = render_report(report)

        for label in (
            "00:00",
            "10:00",
            "20:00",
            "30:00",
            "40:00",
            "50:00",
            "01:00:00",
            "01:10:00",
            "01:20:00",
            "01:30:00",
            "01:39:22",
        ):
            self.assertIn(f'>{label}</text>', html)
        self.assertEqual(html.count('class="trajectory-grid"'), 11)
        self.assertEqual(html.count(">01:39:22</text>"), 1)

    def test_structure_event_summary_groups_known_event_kinds_before_evidence(self):
        report = valid_report(normalized_document())
        kinds = ("transition", "return", "digression", "nested_digression", "loop", "answer_directness")
        report["structure"]["events"] = [
            {**copy.deepcopy(report["structure"]["events"][0]), "kind": kind}
            for kind in kinds
        ]

        html = render_report(report)

        for group, label, count in (
            ("navigation", "Navigation", 2),
            ("branches", "Branches", 2),
            ("breaks", "Breaks", 1),
            ("direct-answers", "Direct answers", 1),
        ):
            self.assertIn(
                f'<li class="event-summary-item event-summary-{group}"><span>{label}</span><strong>{count}</strong></li>',
                html,
            )
        self.assertLess(html.index('class="event-summary"'), html.index('<ol class="evidence">'))
        validate_report(report, normalized_document(), html)

    def test_diagnosis_paragraphs_render_as_labelled_editorial_points(self):
        report = valid_report(normalized_document())
        report["diagnosis"]["paragraphs"] = [
            "Структурный ход.",
            "Логический ход.",
            "Ограничение вывода.",
            "Opportunities следующего шага.",
        ]

        html = render_report(report)

        self.assertIn('<div class="diagnosis-points">', html)
        self.assertEqual(html.count('class="diagnosis-point"'), 4)
        for label, paragraph in zip(
            ("Structure", "Logic", "Limitations", "Opportunities"),
            report["diagnosis"]["paragraphs"],
        ):
            self.assertIn(f'<p class="diagnosis-label">{label}</p>', html)
            self.assertIn(f'<p class="diagnosis-copy">{paragraph}</p>', html)
        self.assertIn(".diagnosis-points { display: grid;", html)
        validate_report(report, normalized_document(), html)

    def test_diagnosis_uses_generic_labels_after_four_editorial_points(self):
        report = valid_report(normalized_document())
        report["diagnosis"]["paragraphs"] = ["Один.", "Два.", "Три.", "Четыре.", "Пять."]

        html = render_report(report)

        self.assertIn('<p class="diagnosis-label">Point 5</p>', html)
        validate_report(report, normalized_document(), html)

    def test_masthead_uses_muted_kicker_and_thin_divider(self):
        html = self.render()

        self.assertIn("header { padding-bottom:", html)
        self.assertIn("border-bottom: 1px solid var(--line)", html)
        self.assertIn(".kicker { margin: 0 0 12px; color: var(--ink2);", html)

    def test_opening_cadence_tightens_tiles_scores_and_section_spacing(self):
        html = self.render()

        self.assertIn(".wrap { width: min(1040px, calc(100% - 48px)); margin: 0 auto; padding: 56px 0 104px; }", html)
        self.assertIn("header { padding-bottom: 28px; border-bottom: 1px solid var(--line); }", html)
        self.assertIn(".tiles { display: grid;", html)
        self.assertIn("margin-top: 32px;", html)
        self.assertIn(".scores { display: grid;", html)
        self.assertIn("margin-top: 14px;", html)
        self.assertIn("section { margin-top: 68px; }", html)

    def test_uses_audited_reference_palette_tokens_without_legacy_values(self):
        html = self.render()

        for token in (
            "--paper: #fcfcfb",
            "--tile: #f3f2ee",
            "--ink: #0b0b0b",
            "--ink2: #52514e",
            "--ink3: #8a8985",
            "--line: #e6e5e1",
            "--blue: #2a78d6",
            'fill="#8a8985"',
            'stroke="#e6e5e1"',
            'fill="#2a78d6"',
        ):
            self.assertIn(token, html)
        for legacy in ("#181817", "#686864", "#2868b8", "#deded9"):
            self.assertNotIn(legacy, html)

    def test_mobile_trajectory_keeps_wide_plot_inside_its_own_scroll_region(self):
        html = self.render()

        self.assertIn('class="trajectory-scroll"', html)
        self.assertIn("Diagram exceeds screen width → scroll horizontally", html)
        self.assertIn("Colored spans — topics", html)
        self.assertIn("Blue markers — structural events", html)
        self.assertIn('class="trajectory-key"', html)
        self.assertIn(".trajectory-scroll { overflow-x: auto;", html)
        self.assertIn(".trajectory-scroll svg { display: block; width: 760px; min-width: 760px; max-width: none;", html)
        self.assertIn(".trajectory-cue { display: none; }", html)
        self.assertIn(".trajectory-cue { display: block;", html)
        self.assertIn("html { background: var(--paper); overflow-x: clip; }", html)

    def test_output_is_deterministic(self):
        report = valid_report(normalized_document())
        self.assertEqual(render_report(report), render_report(copy.deepcopy(report)))

    def test_cli_validates_then_writes_self_contained_html(self):
        report = valid_report(normalized_document())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            normalized_path = root / "normalized.json"
            report_path = root / "report.json"
            output_path = root / "report.html"
            normalized_path.write_text(__import__("json").dumps(normalized_document()), encoding="utf-8")
            report_path.write_text(__import__("json").dumps(report), encoding="utf-8")

            from render_report import main
            self.assertEqual(main([str(report_path), str(output_path), "--normalized", str(normalized_path)]), 0)
            validate_report(report, normalized_document(), output_path.read_text(encoding="utf-8"))

    def test_has_mobile_layout_and_horizontal_table_scrolling(self):
        html = self.render()
        self.assertIn("@media (max-width: 760px)", html)
        self.assertIn("overflow-x: auto", html)
        self.assertIn("font-size: 30px", html)
        self.assertIn("--tile: #f3f2ee", html)


if __name__ == "__main__":
    unittest.main()
