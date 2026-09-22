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
from parse_transcript import parse_file  # noqa: E402


def document(*segments, duration_ms=None, source_format="vtt"):
    if duration_ms is None and segments and segments[-1][2] is not None:
        duration_ms = segments[-1][2]
    return {
        "metadata": {
            "duration_ms": duration_ms,
            "source_format": source_format,
        },
        "segments": [
            {
                "id": f"seg_{index:04d}",
                "speaker": speaker,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": "spoken text",
            }
            for index, (speaker, start_ms, end_ms) in enumerate(segments, start=1)
        ],
    }


class ComputeMetricsTests(unittest.TestCase):
    def test_merges_only_contiguous_guest_cues_into_one_turn(self):
        result = compute_metrics(
            document(
                ("HOST", 0, 1_000),
                ("GUEST", 1_000, 5_000),
                ("GUEST", 5_000, 7_000),
                ("HOST", 7_000, 8_000),
            )
        )

        self.assertEqual(
            result,
            {
                "duration_ms": 8_000,
                "guest_speaking_ms": 6_000,
                "guest_speaking_share": 0.75,
                "guest_turn_count": 1,
                "guest_turn_median_ms": 6_000,
                "longest_guest_turn_ms": 6_000,
                "host_to_guest_transitions": 1,
                "duration_metrics_partial": False,
                "unknown_duration_segment_count": 0,
                "guest_turn_duration_count": 1,
            },
        )

    def test_gap_breaks_same_speaker_turn(self):
        result = compute_metrics(
            document(
                ("HOST", 0, 1_000),
                ("GUEST", 1_000, 2_000),
                ("GUEST", 3_000, 5_000),
            )
        )

        self.assertEqual(result["guest_turn_count"], 2)
        self.assertEqual(result["guest_turn_median_ms"], 1_500)
        self.assertEqual(result["longest_guest_turn_ms"], 2_000)
        self.assertEqual(result["host_to_guest_transitions"], 1)
        self.assertEqual(result["guest_speaking_share"], 0.75)

    def test_counts_host_to_guest_transitions_at_role_turn_boundaries(self):
        result = compute_metrics(
            document(
                ("HOST", 0, 1_000),
                ("HOST", 1_000, 2_000),
                ("GUEST", 2_000, 3_000),
                ("HOST", 3_000, 4_000),
                ("GUEST", 4_000, 5_000),
            )
        )

        self.assertEqual(result["guest_turn_count"], 2)
        self.assertEqual(result["host_to_guest_transitions"], 2)

    def test_even_median_uses_float_only_for_an_exact_half_millisecond(self):
        whole = compute_metrics(
            document(("GUEST", 0, 1_000), ("GUEST", 2_000, 3_002))
        )
        half = compute_metrics(
            document(("GUEST", 0, 1_001), ("GUEST", 2_000, 3_002))
        )

        self.assertEqual(whole["guest_turn_median_ms"], 1_001)
        self.assertIsInstance(whole["guest_turn_median_ms"], int)
        self.assertEqual(half["guest_turn_median_ms"], 1_001.5)
        self.assertIsInstance(half["guest_turn_median_ms"], float)

    def test_contiguous_unknown_guest_merges_and_makes_turn_duration_partial(self):
        doc = document(
            ("HOST", 0, 1_000),
            ("GUEST", 1_000, 2_000),
            ("GUEST", 2_000, None),
            duration_ms=None,
        )
        del doc["metadata"]["source_format"]

        result = compute_metrics(doc)

        self.assertIsNone(result["duration_ms"])
        self.assertEqual(result["guest_speaking_ms"], 1_000)
        self.assertEqual(result["guest_turn_count"], 1)
        self.assertEqual(result["guest_turn_duration_count"], 0)
        self.assertIsNone(result["guest_turn_median_ms"])
        self.assertIsNone(result["longest_guest_turn_ms"])
        self.assertTrue(result["duration_metrics_partial"])
        self.assertEqual(result["unknown_duration_segment_count"], 1)

    def test_unknown_guest_after_gap_starts_a_new_partial_turn(self):
        result = compute_metrics(
            document(
                ("GUEST", 0, 1_000),
                ("GUEST", 2_000, None),
                duration_ms=None,
            )
        )

        self.assertEqual(result["guest_turn_count"], 2)
        self.assertEqual(result["guest_turn_duration_count"], 1)
        self.assertEqual(result["guest_turn_median_ms"], 1_000)
        self.assertEqual(result["longest_guest_turn_ms"], 1_000)
        self.assertTrue(result["duration_metrics_partial"])

    def test_final_unknown_guest_participates_in_turn_topology(self):
        result = compute_metrics(
            document(
                ("HOST", 0, 1_000),
                ("GUEST", 1_000, 2_000),
                ("HOST", 2_000, 3_000),
                ("GUEST", 3_000, None),
                duration_ms=None,
            )
        )

        self.assertEqual(result["guest_turn_count"], 2)
        self.assertEqual(result["guest_turn_duration_count"], 1)
        self.assertEqual(result["host_to_guest_transitions"], 2)
        self.assertEqual(result["guest_speaking_ms"], 1_000)
        self.assertEqual(result["guest_speaking_share"], 1 / 3)

    def test_share_uses_known_speech_not_wall_clock_and_handles_zero_host(self):
        with_host_gap = compute_metrics(
            document(("HOST", 0, 1_000), ("GUEST", 9_000, 10_000))
        )
        guest_only = compute_metrics(document(("GUEST", 0, 2_000)))

        self.assertEqual(with_host_gap["guest_speaking_share"], 0.5)
        self.assertEqual(guest_only["guest_speaking_share"], 1.0)

    def test_rejects_invalid_normalized_documents(self):
        invalid = {
            "empty doc": {},
            "segments not list": {"metadata": {}, "segments": {}},
            "no segments": {"metadata": {}, "segments": []},
            "unknown role": document(("AUDIENCE", 0, 1_000)),
            "boolean start": document(("GUEST", True, 1_000)),
            "nan start": document(("GUEST", float("nan"), 1_000)),
            "infinite end": document(("GUEST", 0, float("inf"))),
            "fractional start": document(("GUEST", 0.5, 1_000)),
            "fractional end": document(("GUEST", 0, 1_000.5)),
            "negative start": document(("GUEST", -1, 1_000)),
            "negative duration": document(("GUEST", 2_000, 1_000)),
            "zero duration": document(("GUEST", 1_000, 1_000)),
            "overlap": document(("HOST", 0, 2_000), ("GUEST", 1_000, 3_000)),
            "null non-final": document(
                ("HOST", 0, None),
                ("GUEST", 1_000, 2_000),
                source_format="txt",
            ),
            "no known guest speech": document(
                ("HOST", 0, 1_000),
                ("GUEST", 1_000, None),
                source_format="txt",
            ),
        }
        for label, value in invalid.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                compute_metrics(value)

    def test_returns_no_forbidden_language_quality_metrics(self):
        result = compute_metrics(document(("GUEST", 0, 1_000)))
        forbidden = {
            "wpm",
            "fillers",
            "pauses",
            "restarts",
            "phrase_quality",
        }

        self.assertTrue(forbidden.isdisjoint(result))
        self.assertEqual(
            set(result),
            {
                "duration_ms",
                "guest_speaking_ms",
                "guest_speaking_share",
                "guest_turn_count",
                "guest_turn_median_ms",
                "longest_guest_turn_ms",
                "host_to_guest_transitions",
                "duration_metrics_partial",
                "unknown_duration_segment_count",
                "guest_turn_duration_count",
            },
        )



class ComputeMetricsCliTests(unittest.TestCase):
    def test_cli_writes_utf8_indented_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "вход.json"
            output_path = Path(temp_dir) / "метрики.json"
            input_path.write_text(
                json.dumps(document(("HOST", 0, 1_000), ("GUEST", 1_000, 3_000))),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "compute_metrics.py"), str(input_path), str(output_path)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["guest_speaking_ms"], 2_000)
            self.assertFalse(
                json.loads(output_path.read_text(encoding="utf-8"))[
                    "duration_metrics_partial"
                ]
            )
            self.assertIn('\n  "duration_ms"', output_path.read_text(encoding="utf-8"))

    def test_cli_reports_concise_validation_error_with_exit_two(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.json"
            output_path = Path(temp_dir) / "metrics.json"
            input_path.write_text("{}", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "compute_metrics.py"), str(input_path), str(output_path)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("error:", result.stderr.lower())
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
