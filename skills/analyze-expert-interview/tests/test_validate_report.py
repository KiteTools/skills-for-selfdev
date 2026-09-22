import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from compute_metrics import compute_metrics  # noqa: E402
from validate_report import validate_report  # noqa: E402


def normalized_document():
    return {
        "metadata": {"duration_ms": 8_000, "source_format": "vtt"},
        "segments": [
            {
                "id": "seg_0001",
                "speaker": "HOST",
                "start_ms": 0,
                "end_ms": 1_000,
                "text": "What changed for you?",
            },
            {
                "id": "seg_0002",
                "speaker": "GUEST",
                "start_ms": 1_000,
                "end_ms": 4_000,
                "text": "First I noticed the difficult pattern",
            },
            {
                "id": "seg_0003",
                "speaker": "GUEST",
                "start_ms": 4_000,
                "end_ms": 7_000,
                "text": "and then chose a clearer direction.",
            },
            {
                "id": "seg_0004",
                "speaker": "HOST",
                "start_ms": 7_000,
                "end_ms": 8_000,
                "text": "Thank you.",
            },
        ],
    }


def valid_report(normalized=None):
    normalized = normalized or normalized_document()
    evidence = {
        "quote": "First I noticed the difficult pattern",
        "start_ms": 1_000,
    }
    return {
        "metadata": {"title": "Broadcast analysis"},
        "metrics": compute_metrics(normalized),
        "scores": {"structural_chaos": 4, "logical_soundness": 8.5},
        "diagnosis": {
            "title": "A clear progression",
            "paragraphs": ["The guest moves from observation to a decision."],
            "anchor_evidence": copy.deepcopy(evidence),
        },
        "topics": [
            {
                "id": "change",
                "label": "Change",
                "color": "#3355aa",
                "spans": [
                    {
                        "start_ms": 1_000,
                        "end_ms": 7_000,
                        "weight": "dominant",
                        "note": "The guest describes a change in direction.",
                    }
                ],
            }
        ],
        "structure": {
            "counts": [{"label": "guest turns", "value": 1}],
            "events": [
                {
                    "kind": "turning_point",
                    **copy.deepcopy(evidence),
                    "analysis": "The observation becomes an explicit choice.",
                }
            ],
        },
        "logic": {
            "defects": [
                {
                    "category": "qualification",
                    "count": 1,
                    "example": {
                        **copy.deepcopy(evidence),
                        "analysis": "The premise remains somewhat broad.",
                    },
                }
            ],
            "theses": [
                {
                    "thesis": "Recognition enables a clearer choice.",
                    "status": "supported",
                    "support": "The guest states the sequence directly.",
                    **copy.deepcopy(evidence),
                }
            ],
            "strong_moments": [
                {
                    "title": "Choice follows recognition",
                    **copy.deepcopy(evidence),
                    "analysis": "A compact causal progression.",
                }
            ],
        },
        "recommendations": [
            {
                "title": f"Recommendation {index}",
                "body": "A concrete revision.",
                "candidate_id": f"structure:recommendation-{index}",
                "source_ids": ["structure:event-1"],
                "basis": {
                    **copy.deepcopy(evidence),
                    "analysis": "The recommendation follows from the cited passage.",
                },
            }
            for index in range(1, 6)
        ],
        "method": "Scores describe polarity: more chaos is worse; more soundness is better.",
    }


class ValidateReportShapeTests(unittest.TestCase):
    def test_accepts_minimal_valid_report(self):
        normalized = normalized_document()
        validate_report(valid_report(normalized), normalized)

    def test_rejects_missing_required_top_level_key(self):
        normalized = normalized_document()
        for key in (
            "metadata",
            "metrics",
            "scores",
            "diagnosis",
            "topics",
            "structure",
            "logic",
            "recommendations",
            "method",
        ):
            with self.subTest(key=key):
                report = valid_report(normalized)
                del report[key]
                with self.assertRaisesRegex(ValueError, "missing required"):
                    validate_report(report, normalized)

    def test_rejects_a_missing_required_collection(self):
        normalized = normalized_document()
        report = valid_report(normalized)
        del report["logic"]["strong_moments"]

        with self.assertRaisesRegex(ValueError, "strong_moments"):
            validate_report(report, normalized)

    def test_rejects_score_outside_zero_to_ten(self):
        normalized = normalized_document()
        report = valid_report(normalized)
        report["scores"]["structural_chaos"] = 11

        with self.assertRaisesRegex(ValueError, "structural_chaos"):
            validate_report(report, normalized)

    def test_rejects_bad_topic_span(self):
        normalized = normalized_document()
        invalid_spans = [
            {"start_ms": 7_000, "end_ms": 7_000, "weight": "dominant", "note": "x"},
            {"start_ms": 1_000, "end_ms": 9_000, "weight": "dominant", "note": "x"},
            {"start_ms": 1_000, "end_ms": 2_000, "weight": "minor", "note": "x"},
        ]
        for span in invalid_spans:
            with self.subTest(span=span):
                report = valid_report(normalized)
                report["topics"][0]["spans"] = [span]
                with self.assertRaisesRegex(ValueError, "span"):
                    validate_report(report, normalized)


class ValidateReportEvidenceTests(unittest.TestCase):
    def test_rejects_invented_quote(self):
        normalized = normalized_document()
        report = valid_report(normalized)
        report["diagnosis"]["anchor_evidence"]["quote"] = "This was never spoken at all"

        with self.assertRaisesRegex(ValueError, "quote not found"):
            validate_report(report, normalized)

    def test_rejects_timestamp_outside_quote_occurrence_or_guest_cue(self):
        normalized = normalized_document()
        invalid = [
            ("First I noticed the difficult pattern", 0),
            ("What changed for you?", 0),
            ("First I noticed the difficult pattern", 4_000),
        ]
        for quote, start_ms in invalid:
            with self.subTest(quote=quote, start_ms=start_ms):
                report = valid_report(normalized)
                report["diagnosis"]["anchor_evidence"] = {
                    "quote": quote,
                    "start_ms": start_ms,
                }
                pattern = "quote not found" if quote.startswith("What") else "start_ms"
                with self.assertRaisesRegex(ValueError, pattern):
                    validate_report(report, normalized)

    def test_accepts_unicode_case_whitespace_and_cross_segment_guest_quote(self):
        normalized = normalized_document()
        normalized["segments"][1]["text"] = "First I noticed “the difficult"
        normalized["segments"][2]["text"] = "pattern” — and chose a direction."
        report = valid_report(normalized)
        for evidence in self._evidence_items(report):
            evidence["quote"] = ' first   i NOTICED "the difficult pattern" - and chose '
            evidence["start_ms"] = 1_500

        validate_report(report, normalized)

    def test_repeated_quote_accepts_matching_occurrence_timestamp(self):
        normalized = normalized_document()
        normalized["segments"][1]["text"] = "This pattern gives a clearer direction"
        normalized["segments"][2]["text"] = "This pattern gives a clearer direction again"
        report = valid_report(normalized)
        for evidence in self._evidence_items(report):
            evidence["quote"] = "This pattern gives a clearer direction"
            evidence["start_ms"] = 4_500

        validate_report(report, normalized)

    def test_rejects_short_or_empty_quote(self):
        normalized = normalized_document()
        for quote in ("", "clearer direction now"):
            with self.subTest(quote=quote):
                report = valid_report(normalized)
                report["diagnosis"]["anchor_evidence"]["quote"] = quote
                with self.assertRaisesRegex(ValueError, "at least 4"):
                    validate_report(report, normalized)

    def test_rejects_invented_evidence_in_an_extension_collection(self):
        normalized = normalized_document()
        report = valid_report(normalized)
        report["extra_findings"] = [
            {"quote": "This quote was completely invented", "start_ms": 1_000}
        ]

        with self.assertRaisesRegex(ValueError, "quote not found"):
            validate_report(report, normalized)

    @staticmethod
    def _evidence_items(report):
        return [
            report["diagnosis"]["anchor_evidence"],
            report["structure"]["events"][0],
            report["logic"]["defects"][0]["example"],
            report["logic"]["theses"][0],
            report["logic"]["strong_moments"][0],
            *[item["basis"] for item in report["recommendations"]],
        ]


class ValidateReportMetricsAndExclusionsTests(unittest.TestCase):
    def test_rejects_missing_extra_mismatched_or_boolean_metrics(self):
        normalized = normalized_document()
        mutations = {}
        missing = valid_report(normalized)
        del missing["metrics"]["guest_turn_count"]
        mutations["missing"] = missing
        extra = valid_report(normalized)
        extra["metrics"]["invented"] = 1
        mutations["extra"] = extra
        mismatch = valid_report(normalized)
        mismatch["metrics"]["guest_turn_count"] = 99
        mutations["mismatch"] = mismatch
        boolean = valid_report(normalized)
        boolean["metrics"]["guest_turn_count"] = True
        mutations["boolean"] = boolean

        for label, report in mutations.items():
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "metrics"):
                validate_report(report, normalized)

    def test_rejects_non_finite_numeric_values(self):
        normalized = normalized_document()
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                report = valid_report(normalized)
                report["structure"]["counts"][0]["value"] = value
                with self.assertRaisesRegex(ValueError, "finite"):
                    validate_report(report, normalized)

    def test_handles_arbitrarily_large_json_integers_without_overflow(self):
        normalized = normalized_document()
        report = valid_report(normalized)
        report["structure"]["counts"][0]["value"] = 10**400
        validate_report(report, normalized)

        report["scores"]["structural_chaos"] = 10**400
        with self.assertRaisesRegex(ValueError, "between 0 and 10"):
            validate_report(report, normalized)


class ValidateReportRecommendationsTests(unittest.TestCase):
    def test_rejects_old_title_body_only_recommendations(self):
        report = valid_report()
        for recommendation in report["recommendations"]:
            del recommendation["source_ids"]
            del recommendation["basis"]

        with self.assertRaisesRegex(ValueError, "recommendations"):
            validate_report(report, normalized_document())

    def test_rejects_extra_recommendation_or_basis_keys(self):
        variants = []
        extra_recommendation = valid_report()
        extra_recommendation["recommendations"][0]["extra"] = True
        variants.append(extra_recommendation)
        extra_basis = valid_report()
        extra_basis["recommendations"][0]["basis"]["extra"] = True
        variants.append(extra_basis)

        for report in variants:
            with self.subTest(report=report), self.assertRaisesRegex(ValueError, "exactly"):
                validate_report(report, normalized_document())

    def test_rejects_empty_duplicate_or_invalid_source_ids(self):
        invalid_values = [
            [],
            [""],
            ["   "],
            ["structure:event-1", "structure:event-1"],
            ["structure:event-1", " structure:event-1 "],
            ["structure:event-1", 2],
            ["seg_0002"],
            ["logic:thesis-1"],
        ]
        for source_ids in invalid_values:
            with self.subTest(source_ids=source_ids):
                report = valid_report()
                report["recommendations"][0]["source_ids"] = source_ids
                with self.assertRaisesRegex(ValueError, "source_ids"):
                    validate_report(report, normalized_document())

    def test_rejects_invalid_candidate_id_or_source_prefix(self):
        invalid_candidate_ids = [
            "",
            "candidate-1",
            "topics:candidate-1",
            "structure:",
            "logic:bad id",
            1,
        ]
        for candidate_id in invalid_candidate_ids:
            with self.subTest(candidate_id=candidate_id):
                report = valid_report()
                report["recommendations"][0]["candidate_id"] = candidate_id
                with self.assertRaisesRegex(ValueError, "candidate_id"):
                    validate_report(report, normalized_document())

        report = valid_report()
        report["recommendations"][0]["candidate_id"] = "logic:thesis-1"
        report["recommendations"][0]["source_ids"] = ["structure:event-1"]
        with self.assertRaisesRegex(ValueError, "same pass prefix"):
            validate_report(report, normalized_document())

    def test_rejects_invalid_recommendation_basis(self):
        invalid_bases = [
            {
                "quote": "This recommendation basis was never spoken",
                "start_ms": 1_000,
                "analysis": "Invented.",
            },
            {
                "quote": "What changed for you?",
                "start_ms": 0,
                "analysis": "Host-only.",
            },
            {"quote": "clearer direction now", "start_ms": 1_000, "analysis": "Short."},
            {
                "quote": "First I noticed the difficult pattern",
                "start_ms": 1_000,
            },
            {
                "quote": "First I noticed the difficult pattern",
                "start_ms": 1_000,
                "analysis": "   ",
            },
        ]
        for basis in invalid_bases:
            with self.subTest(basis=basis):
                report = valid_report()
                report["recommendations"][0]["basis"] = basis
                with self.assertRaises(ValueError):
                    validate_report(report, normalized_document())

    def test_rejects_excluded_module_key_or_heading(self):
        normalized = normalized_document()
        reports = []
        by_key = valid_report(normalized)
        by_key["speech"] = {"notes": []}
        reports.append(by_key)
        by_heading = valid_report(normalized)
        by_heading["diagnosis"]["title"] = "Host evaluation"
        reports.append(by_heading)
        by_russian_heading = valid_report(normalized)
        by_russian_heading["recommendations"][0]["title"] = "Монтажный лист"
        reports.append(by_russian_heading)

        for report in reports:
            with self.subTest(report=report), self.assertRaisesRegex(ValueError, "excluded module"):
                validate_report(report, normalized)

    def test_rejects_case_and_separator_variants_of_title_like_keys(self):
        normalized = normalized_document()
        for key in ("Title", "section-title"):
            with self.subTest(key=key):
                report = valid_report(normalized)
                report["extra"] = {key: "Speech"}
                with self.assertRaisesRegex(ValueError, "excluded module"):
                    validate_report(report, normalized)

    def test_does_not_reject_ordinary_prose_mentioning_host_or_speech(self):
        normalized = normalized_document()
        report = valid_report(normalized)
        report["diagnosis"]["paragraphs"] = [
            "The host question helps the guest's speech reach the central idea."
        ]

        validate_report(report, normalized)


class ValidateReportHtmlTests(unittest.TestCase):
    VALID_HTML = """<!doctype html><html><head><style>body { color: #222 }</style></head>
    <body><h1>Analysis</h1><a href="https://youtube.com/watch?v=x">source</a></body></html>"""

    def test_accepts_self_contained_single_html_document(self):
        normalized = normalized_document()
        validate_report(valid_report(normalized), normalized, self.VALID_HTML)

    def test_rejects_external_html_dependencies(self):
        fragments = [
            '<link rel="stylesheet" href="style.css">',
            '<script src="app.js"></script>',
            '<iframe src="page.html"></iframe>',
            '<img src="https://example.com/image.png">',
            '<style>@import "theme.css";</style>',
            '<style>body { background: url(image.png) }</style>',
            '<video src="movie.mp4"></video>',
            '<audio src="sound.mp3"></audio>',
            '<source src="movie.webm">',
            '<img src="data:image/png;base64,AA" srcset="image-2x.png 2x">',
            '<img srcset="data:image/png;base64,AA 1x, https://example.com/x.png 2x">',
            '<object data="widget.html"></object>',
            '<embed src="widget.html">',
            '<svg><image href="https://example.com/image.svg"></image></svg>',
            '<meta http-equiv="refresh" content="0; url=https://example.com">',
            '<script>fetch("https://example.com/data.json")</script>',
            '<script>document.body.dataset.ready = "yes"</script>',
            '<div onclick="navigator.sendBeacon(\'https://example.com\')">x</div>',
        ]
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                html = f"<!doctype html><html><head><style>x{{color:black}}</style>{fragment}</head><body></body></html>"
                with self.assertRaisesRegex(ValueError, "external|forbidden"):
                    validate_report(valid_report(), normalized_document(), html)

    def test_rejects_external_or_runtime_urls_in_any_resource_attribute(self):
        fragments = [
            '<svg><feImage xlink:href="https://example.com/a.svg"/></svg>',
            '<svg><use href="//example.com/icons.svg#x"/></svg>',
            '<input src="field.png">',
            '<body background="paper.png">',
            '<video poster="poster.jpg"></video>',
            '<button formaction="/submit">go</button>',
            '<form action="javascript:alert(1)"></form>',
            '<a ping="https://tracker.example/p" href="https://youtu.be/x?t=2">video</a>',
            '<div data-note="vbscript:msgbox(1)">x</div>',
            '<div title="//example.com/runtime">x</div>',
        ]
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                html = f"<!doctype html><html><head><style>x{{}}</style></head><body>{fragment}</body></html>"
                with self.assertRaisesRegex(ValueError, "external|forbidden"):
                    validate_report(valid_report(), normalized_document(), html)

    def test_rejects_duplicate_attributes_before_case_insensitive_collapse(self):
        html_values = [
            '<!doctype html><html><head><style>x{}</style></head><body><a href="https://youtu.be/x?t=2" HREF="https://evil.example/x">video</a></body></html>',
            '<!doctype html><html><head><style>x{}</style></head><body><div class="a" CLASS="b">x</div></body></html>',
        ]
        for html in html_values:
            with self.subTest(html=html), self.assertRaisesRegex(ValueError, "duplicate attribute"):
                validate_report(valid_report(), normalized_document(), html)

    def test_rejects_all_data_urls_and_object_embed_elements(self):
        fragments = [
            '<img src="data:image/png;base64,AA">',
            '<div title="data:text/html,hello">x</div>',
            '<style>body { background: url(data:image/png;base64,AA) }</style>',
            '<object></object>',
            '<embed>',
        ]
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                html = f"<!doctype html><html><head><style>x{{}}</style></head><body>{fragment}</body></html>"
                with self.assertRaisesRegex(ValueError, "data|forbidden"):
                    validate_report(valid_report(), normalized_document(), html)

    def test_rejects_empty_media_and_runtime_elements_without_urls(self):
        fragments = [
            "<video></video>",
            "<AUDIO></AUDIO>",
            "<source>",
            "<TRACK>",
            "<object></object>",
            "<EMBED>",
            "<iframe></iframe>",
        ]
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                html = f"<!doctype html><html><head><style>x{{}}</style></head><body>{fragment}</body></html>"
                with self.assertRaisesRegex(ValueError, "media|runtime|forbidden"):
                    validate_report(valid_report(), normalized_document(), html)

        validate_report(valid_report(), normalized_document(), self.VALID_HTML)

    def test_rejects_self_closing_non_void_elements(self):
        for fragment in ("<style/>", "<div/>", "<svg/>"):
            with self.subTest(fragment=fragment):
                html = f"<!doctype html><html><head><style>x{{}}</style></head><body>{fragment}</body></html>"
                with self.assertRaisesRegex(ValueError, "self-closing"):
                    validate_report(valid_report(), normalized_document(), html)

        html = "<!doctype html><html><head><style>x{}</style><meta charset='utf-8'></head><body><br/><hr/><img/></body></html>"
        validate_report(valid_report(), normalized_document(), html)

    def test_attribute_url_functions_allow_only_safe_same_document_fragment(self):
        invalid = [
            '<svg><rect fill="url(https://example.com/a.svg#x)"/></svg>',
            '<svg><g filter="url(filters.svg#x)"></g></svg>',
            '<svg><g clip-path="url(data:image/svg+xml,x)"></g></svg>',
            '<svg><g mask="url(javascript:alert(1))"></g></svg>',
            '<svg><path marker-start="url(#bad id)"></path></svg>',
        ]
        for fragment in invalid:
            with self.subTest(fragment=fragment):
                html = f"<!doctype html><html><head><style>x{{}}</style></head><body>{fragment}</body></html>"
                with self.assertRaisesRegex(ValueError, "url|URL|forbidden"):
                    validate_report(valid_report(), normalized_document(), html)

        html = '<!doctype html><html><head><style>x{}</style></head><body><svg><g filter="url(#safe-id)"></g></svg></body></html>'
        validate_report(valid_report(), normalized_document(), html)

    def test_rejects_base_elements_and_xml_base_before_fragment_urls(self):
        fragments = [
            '<svg xml:base="evil.svg"><g filter="url(#safe)"></g></svg>',
            '<svg XML:BASE="evil.svg"><g filter="url(#safe)"></g></svg>',
            '<base>',
        ]
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                html = f"<!doctype html><html><head><style>x{{}}</style></head><body>{fragment}</body></html>"
                with self.assertRaisesRegex(ValueError, "base|forbidden"):
                    validate_report(valid_report(), normalized_document(), html)

    def test_rejects_svg_smil_animation_and_indirect_url_elements(self):
        fragments = [
            '<svg><set attributeName="href" to="evil.svg"></set></svg>',
            '<svg><animate attributeName="href" values="#safe;evil.svg"></animate></svg>',
            '<svg><animateMotion to="100,100"></animateMotion></svg>',
            '<svg><animateTransform to="90 10 10"></animateTransform></svg>',
            '<svg><mpath path="evil.svg#x"></mpath></svg>',
            '<svg><ANIMATEMOTION values="safe;evil"></ANIMATEMOTION></svg>',
        ]
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                html = f"<!doctype html><html><head><style>x{{}}</style></head><body>{fragment}</body></html>"
                with self.assertRaisesRegex(ValueError, "SMIL|forbidden"):
                    validate_report(valid_report(), normalized_document(), html)

    def test_allows_only_whitelisted_youtube_anchor_urls(self):
        normalized = normalized_document()
        for url in (
            "https://www.youtube.com/watch?v=abc&t=12s",
            "https://youtube.com/watch?v=abc&t=12s",
            "https://youtu.be/abc?t=12",
        ):
            with self.subTest(url=url):
                html = f'<!doctype html><html><head><style>x{{}}</style></head><body><a href="{url}">video</a></body></html>'
                validate_report(valid_report(normalized), normalized, html)

        for url in (
            "http://youtube.com/watch?v=abc&t=12s",
            "https://youtube.com.evil.test/watch?v=abc&t=12s",
            "https://example.com/video",
            "#local",
        ):
            with self.subTest(url=url):
                html = f'<!doctype html><html><head><style>x{{}}</style></head><body><a href="{url}">video</a></body></html>'
                with self.assertRaises(ValueError):
                    validate_report(valid_report(normalized), normalized, html)

    def test_rejects_css_escape_bypasses_but_allows_media_rules(self):
        invalid_css = [
            '@im\\port "theme.css";',
            '@\\69mport "theme.css";',
            'body { background: u\\72l(image.png) }',
            'body { background: url(h\\74tps://example.com/a.png) }',
        ]
        for css in invalid_css:
            with self.subTest(css=css):
                html = f"<!doctype html><html><head><style>{css}</style></head><body></body></html>"
                with self.assertRaisesRegex(ValueError, "CSS"):
                    validate_report(valid_report(), normalized_document(), html)

        html = "<!doctype html><html><head><style>@media (max-width: 40rem) { body { color: red } }</style></head><body></body></html>"
        validate_report(valid_report(), normalized_document(), html)

    def test_rejects_css_resource_functions_and_font_faces(self):
        css_values = [
            'body { background: image-set("a.png" 1x) }',
            'body { background: -webkit-image-set("a.png" 1x) }',
            'body { background: cross-fade("a.png", "b.png", 50%) }',
            '@font-face { font-family: x; src: local(x) }',
            'body { background: i\\6d age-set("a.png" 1x) }',
        ]
        for css in css_values:
            with self.subTest(css=css):
                html = f"<!doctype html><html><head><style>{css}</style></head><body></body></html>"
                with self.assertRaisesRegex(ValueError, "CSS"):
                    validate_report(valid_report(), normalized_document(), html)

    def test_strips_css_comments_before_resource_detection_and_fails_closed(self):
        css_values = [
            "body { background: u/**/rl(asset.png) }",
            "body { background: url/**/(asset.png) }",
            "body { background: u\\72/**/l(asset.png) }",
            '@im/**/port "theme.css";',
            "body { color: red; /* unterminated",
        ]
        for css in css_values:
            with self.subTest(css=css):
                html = f"<!doctype html><html><head><style>{css}</style></head><body></body></html>"
                with self.assertRaisesRegex(ValueError, "CSS"):
                    validate_report(valid_report(), normalized_document(), html)

        valid_css = '/* legal */ @media (max-width: 40rem) { body::before { content: "/* text */"; color: red } }'
        html = f"<!doctype html><html><head><style>{valid_css}</style></head><body></body></html>"
        validate_report(valid_report(), normalized_document(), html)

    def test_rejects_overdeep_extension_with_value_error_not_recursion_error(self):
        report = valid_report()
        cursor = report
        for _ in range(1_200):
            cursor["extension"] = {}
            cursor = cursor["extension"]

        with self.assertRaisesRegex(ValueError, "maximum nesting depth"):
            validate_report(report, normalized_document())

    def test_rejects_unclosed_misordered_or_outside_document_content(self):
        html_values = [
            "<head><style>x{}</style></head><html><body></body></html>",
            "<html><head><style>x{}</style></head><body></body>",
            "<html><head><style>x{}</style></head><body>",
            "<html><head><style>x{}</style><body></body></html>",
            "before<html><head><style>x{}</style></head><body></body></html>",
            "<html><head><style>x{}</style></head><body></body></html>after",
            "<html><head><style>x{}</style></head><body></body></html><html><head><style>x{}</style></head><body></body></html>",
        ]
        for html in html_values:
            with self.subTest(html=html), self.assertRaisesRegex(ValueError, "HTML"):
                validate_report(valid_report(), normalized_document(), html)

    def test_accepts_partial_transcript_with_unknown_final_duration(self):
        normalized = normalized_document()
        normalized["segments"][-1]["end_ms"] = None
        normalized["metadata"]["duration_ms"] = None

        validate_report(valid_report(normalized), normalized, self.VALID_HTML)

    def test_rejects_multiple_documents_missing_style_and_excluded_heading(self):
        html_values = [
            "<html><head><style>x{}</style></head><body></body></html><html></html>",
            "<html><head></head><body></body></html>",
            "<html><head><style>x{}</style></head><body><h2>Audience</h2></body></html>",
        ]
        for html in html_values:
            with self.subTest(html=html), self.assertRaises(ValueError):
                validate_report(valid_report(), normalized_document(), html)


class ValidateReportCliTests(unittest.TestCase):
    def test_cli_returns_two_with_concise_error(self):
        normalized = normalized_document()
        report = valid_report(normalized)
        report["scores"]["logical_soundness"] = 11
        with tempfile.TemporaryDirectory() as directory:
            normalized_path = Path(directory) / "normalized.json"
            report_path = Path(directory) / "report.json"
            normalized_path.write_text(json.dumps(normalized), encoding="utf-8")
            report_path.write_text(json.dumps(report), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_report.py"), str(normalized_path), str(report_path)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)
        self.assertLessEqual(len(result.stderr.splitlines()), 2)

    def test_cli_converts_overdeep_json_recursion_to_concise_exit_two(self):
        normalized = normalized_document()
        deep_json = '{"extension":' * 1_200 + "{}" + "}" * 1_200
        with tempfile.TemporaryDirectory() as directory:
            normalized_path = Path(directory) / "normalized.json"
            report_path = Path(directory) / "report.json"
            normalized_path.write_text(json.dumps(normalized), encoding="utf-8")
            report_path.write_text(deep_json, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_report.py"), str(normalized_path), str(report_path)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertLessEqual(len(result.stderr.splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
