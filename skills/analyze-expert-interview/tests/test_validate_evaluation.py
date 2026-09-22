"""Behavioural contract for the deterministic evaluation-artifact gate."""

import binascii
import copy
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

from test_validate_passes import logic as valid_logic  # noqa: E402
from test_validate_passes import normalized as valid_normalized  # noqa: E402
from test_validate_passes import report as valid_bundle_report  # noqa: E402
from test_validate_passes import structure as valid_structure  # noqa: E402
from compute_metrics import compute_metrics  # noqa: E402
from validate_evaluation import _validate_judges, validate_evaluation  # noqa: E402


def valid_evaluation() -> dict:
    judges = [
        {
            "id": f"blind-judge-{number}",
            "scores": {"S": 96, "E": 97, "V": 95, "T": 98},
            "notes": "Independent source-grounded assessment.",
        }
        for number in range(1, 4)
    ]
    medians = {"S": 96, "E": 97, "V": 95, "T": 98}
    return {
        "rubric_version": "1.0",
        "artifacts": {
            "normalized_json": "normalized.json",
            "structure_analysis_json": "structure-analysis.json",
            "logic_analysis_json": "logic-analysis.json",
            "synthesis_json": "synthesis.json",
            "report_html": "report.html",
            "screenshots": {
                "desktop": "screenshots/desktop-1440x1000.png",
                "mobile": "screenshots/mobile-390x844.png",
            },
        },
        "browser_checks": {
            "desktop": {"width": 1440, "height": 1000, "no_overflow": True},
            "mobile": {"width": 390, "height": 844, "no_overflow": True},
            "scripts": 0,
            "external_resources": 0,
            "details_count": 2,
            "timestamp_count": 3,
            "validator_pass": True,
        },
        "judges": judges,
        "aggregation": {
            "category_medians": medians,
            "weighted": 96.1,
        },
        "passed": True,
    }


def png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + chunk(b"IEND", b"")
    )


def jpeg_sof_stub(width: int, height: int) -> bytes:
    return (
        b"\xff\xd8\xff\xc0\x00\x0b\x08"
        + struct.pack(">HH", height, width)
        + b"\x01\x01\x11\x00\xff\xd9"
    )


def jpeg_empty_scan_stub(width: int, height: int) -> bytes:
    return jpeg_sof_stub(width, height)[:-2] + b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\xff\xd9"


def write_artifacts(directory: Path, *, report_html: str | None = None) -> None:
    (directory / "screenshots").mkdir()
    normalized = valid_normalized()
    structure = valid_structure(normalized)
    logic = valid_logic(normalized)
    synthesis = valid_bundle_report(normalized, structure, logic)
    synthesis["metrics"] = compute_metrics(normalized)
    (directory / "normalized.json").write_text(
        json.dumps(normalized), encoding="utf-8"
    )
    (directory / "synthesis.json").write_text(
        json.dumps(synthesis), encoding="utf-8"
    )
    (directory / "structure-analysis.json").write_text(
        json.dumps(structure), encoding="utf-8"
    )
    (directory / "logic-analysis.json").write_text(
        json.dumps(logic), encoding="utf-8"
    )
    (directory / "report.html").write_text(
        report_html
        or """<!doctype html><html><head><style>body { color: #111; }</style></head>
<body><a class=\"tc\">00:01</a><a class=\"tc\">00:02</a><span class=\"tc\">00:03</span>
<details><summary>Topics</summary></details><details><summary>Method</summary></details></body></html>""",
        encoding="utf-8",
    )
    (directory / "screenshots" / "desktop-1440x1000.png").write_bytes(png(1440, 1000))
    (directory / "screenshots" / "mobile-390x844.png").write_bytes(png(390, 844))


class ValidateEvaluationTests(unittest.TestCase):
    def write_evaluation(self, directory: Path, evaluation: dict) -> Path:
        path = directory / "evaluation.json"
        path.write_text(json.dumps(evaluation), encoding="utf-8")
        return path

    def test_accepts_complete_passing_evaluation_and_recomputes_aggregation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_artifacts(directory)
            path = self.write_evaluation(directory, valid_evaluation())

            self.assertIsNone(validate_evaluation(path))

    def test_rejects_missing_or_invalid_semantic_pass_artifacts_before_report_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_artifacts(directory)
            evaluation = valid_evaluation()
            (directory / "structure-analysis.json").unlink()
            with self.assertRaisesRegex(ValueError, "structure_analysis_json"):
                validate_evaluation(self.write_evaluation(directory, evaluation))

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_artifacts(directory)
            evaluation = valid_evaluation()
            structure = json.loads((directory / "structure-analysis.json").read_text())
            structure["pass"] = "logic"
            (directory / "structure-analysis.json").write_text(json.dumps(structure))
            with self.assertRaisesRegex(ValueError, "structure schema_version or pass invalid"):
                validate_evaluation(self.write_evaluation(directory, evaluation))

    def test_rejects_non_images_and_wrong_screenshot_dimensions(self):
        for filename, contents, message in (
            ("desktop-1440x1000.png", b"not an image", "recognized image"),
            ("mobile-390x844.png", png(391, 844), "must be 390x844"),
        ):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                write_artifacts(directory)
                (directory / "screenshots" / filename).write_bytes(contents)
                with self.assertRaisesRegex(ValueError, message):
                    validate_evaluation(self.write_evaluation(directory, valid_evaluation()))

    def test_rejects_incomplete_png_and_jpeg_header_stubs(self):
        incomplete_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
            + struct.pack(">IIBBBBB", 1440, 1000, 8, 2, 0, 0, 0)
        )
        for filename, contents in (
            ("desktop-1440x1000.png", incomplete_png),
            ("mobile-390x844.png", jpeg_sof_stub(390, 844)),
        ):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                write_artifacts(directory)
                (directory / "screenshots" / filename).write_bytes(contents)
                with self.assertRaisesRegex(ValueError, "complete|recognized"):
                    validate_evaluation(self.write_evaluation(directory, valid_evaluation()))

    def test_rejects_empty_jpeg_scan_and_header_only_gif(self):
        for filename, contents in (
            ("mobile-390x844.png", jpeg_empty_scan_stub(390, 844)),
            ("mobile-390x844.png", b"GIF89a" + struct.pack("<HH", 390, 844)),
        ):
            with self.subTest(contents=contents[:6]), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                write_artifacts(directory)
                (directory / "screenshots" / filename).write_bytes(contents)
                with self.assertRaisesRegex(ValueError, "complete|recognized"):
                    validate_evaluation(self.write_evaluation(directory, valid_evaluation()))

    def test_normalizes_even_judge_scores_to_exact_decimal_medians(self):
        evaluation = valid_evaluation()
        evaluation["judges"] = [
            {
                "id": f"decimal-judge-{number}",
                "scores": scores,
                "notes": "Independent source-grounded assessment.",
            }
            for number, scores in enumerate(
                (
                    {"S": 95.2, "E": 95.3, "V": 94.4, "T": 97.1},
                    {"S": 96.4, "E": 96.5, "V": 95.6, "T": 98.3},
                    {"S": 97.6, "E": 97.7, "V": 96.8, "T": 99.5},
                    {"S": 98.8, "E": 98.9, "V": 98.0, "T": 100},
                ),
                start=1,
            )
        ]
        evaluation["aggregation"] = {
            "category_medians": {"S": 97.0, "E": 97.1, "V": 96.2, "T": 98.9},
            "weighted": 96.955,
        }

        medians = _validate_judges(evaluation)

        self.assertEqual(
            medians,
            {
                "S": Decimal("97.0"),
                "E": Decimal("97.1"),
                "V": Decimal("96.2"),
                "T": Decimal("98.9"),
            },
        )
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_artifacts(directory)
            self.assertIsNone(
                validate_evaluation(self.write_evaluation(directory, evaluation))
            )

    def test_rejects_meta_refresh_even_when_validator_pass_is_claimed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_artifacts(
                directory,
                report_html="""<!doctype html><html><head>
<meta http-equiv=\"refresh\" content=\"0;url=https://outside.example\">
<style>body { color: #111; }</style></head><body>
<a class=\"tc\">00:01</a><a class=\"tc\">00:02</a><span class=\"tc\">00:03</span>
<details><summary>Topics</summary></details><details><summary>Method</summary></details>
</body></html>""",
            )
            path = self.write_evaluation(directory, valid_evaluation())

            with self.assertRaisesRegex(ValueError, "forbidden external URL"):
                validate_evaluation(path)

    def test_rejects_css_escape_even_when_static_counts_are_zero(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_artifacts(
                directory,
                report_html=r"""<!doctype html><html><head><style>
body { background: u\72l(https://outside.example/pixel.png); }
</style></head><body><a class="tc">00:01</a><a class="tc">00:02</a>
<span class="tc">00:03</span><details><summary>Topics</summary></details>
<details><summary>Method</summary></details></body></html>""",
            )
            path = self.write_evaluation(directory, valid_evaluation())

            with self.assertRaisesRegex(ValueError, "CSS URL"):
                validate_evaluation(path)

    def test_rejects_forged_aggregate_even_when_the_gate_would_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_artifacts(directory)
            evaluation = valid_evaluation()
            evaluation["aggregation"]["weighted"] = 99
            path = self.write_evaluation(directory, evaluation)

            with self.assertRaisesRegex(ValueError, "aggregation.weighted"):
                validate_evaluation(path)

    def test_rejects_missing_or_mismatched_browser_artifact_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_artifacts(directory)
            evaluation = valid_evaluation()
            evaluation["browser_checks"]["details_count"] = 3
            path = self.write_evaluation(directory, evaluation)

            with self.assertRaisesRegex(ValueError, "details_count"):
                validate_evaluation(path)

    def test_rejects_under_threshold_scores_even_when_passed_is_truthful(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_artifacts(directory)
            evaluation = valid_evaluation()
            for judge in evaluation["judges"]:
                judge["scores"]["T"] = 84
            evaluation["aggregation"]["category_medians"]["T"] = 84
            evaluation["aggregation"]["weighted"] = 95.4
            evaluation["passed"] = False
            path = self.write_evaluation(directory, evaluation)

            with self.assertRaisesRegex(ValueError, "hard gate"):
                validate_evaluation(path)

    def test_rejects_path_escape_duplicate_judges_and_forged_passed_flag(self):
        cases = []
        escaped = valid_evaluation()
        escaped["artifacts"]["report_html"] = "../report.html"
        cases.append((escaped, "report_html"))

        duplicate = valid_evaluation()
        duplicate["judges"][2]["id"] = duplicate["judges"][1]["id"]
        cases.append((duplicate, "unique"))

        forged_passed = valid_evaluation()
        forged_passed["passed"] = False
        cases.append((forged_passed, "passed"))

        for evaluation, message in cases:
            with self.subTest(message=message):
                with tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    write_artifacts(directory)
                    path = self.write_evaluation(directory, evaluation)

                    with self.assertRaisesRegex(ValueError, message):
                        validate_evaluation(path)


class ValidateEvaluationCliTests(unittest.TestCase):
    def test_cli_reports_a_concise_error_and_exit_two(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            write_artifacts(directory)
            evaluation = valid_evaluation()
            evaluation["browser_checks"]["timestamp_count"] = 0
            path = directory / "evaluation.json"
            path.write_text(json.dumps(evaluation), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_evaluation.py"), str(path)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("error: "))
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
