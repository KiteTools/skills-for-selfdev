import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from parse_transcript import parse_file, parse_text, parse_timestamp  # noqa: E402


class ParseTimestampTests(unittest.TestCase):
    def test_parses_hour_and_minute_timestamps(self):
        self.assertEqual(parse_timestamp("01:02:03.456"), 3_723_456)
        self.assertEqual(parse_timestamp("02:03,004"), 123_004)

    def test_rejects_malformed_timestamps(self):
        for value in ("1:02:03.456", "00:61.000", "00:00:03", "nonsense"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_timestamp(value)


class ParseTextTests(unittest.TestCase):
    def test_parses_webvtt_voice_spans_and_ignores_note_blocks(self):
        result = parse_text(
            """WEBVTT

NOTE speaker mapping
this line is part of the note

00:00:01.000 --> 00:00:02.000
<v HOST>  Hello   there </v>

00:00:02.000 --> 00:00:03.500
<v GUEST>General
Kenobi</v>
""",
            ".vtt",
        )

        self.assertEqual(result["metadata"]["source_format"], "vtt")
        self.assertEqual(result["metadata"]["duration_ms"], 3_500)
        self.assertEqual(
            result["segments"],
            [
                {
                    "id": "seg_0001",
                    "speaker": "HOST",
                    "start_ms": 1_000,
                    "end_ms": 2_000,
                    "text": "Hello there",
                },
                {
                    "id": "seg_0002",
                    "speaker": "GUEST",
                    "start_ms": 2_000,
                    "end_ms": 3_500,
                    "text": "General Kenobi",
                },
            ],
        )

    def test_parses_webvtt_voice_spans_without_closing_tags(self):
        result = parse_text(
            """WEBVTT

00:00:01.000 --> 00:00:02.000
<v HOST>Hello

00:00:02.000 --> 00:00:03.000
<v GUEST>There
""",
            ".vtt",
        )

        self.assertEqual(
            [segment["text"] for segment in result["segments"]],
            ["Hello", "There"],
        )

    def test_parses_srt_speaker_prefixes(self):
        result = parse_text(
            """1
00:00:01,000 --> 00:00:02,000
HOST: Welcome

2
00:00:02,000 --> 00:00:04,000
GUEST: Thank you
""",
            ".srt",
        )

        self.assertEqual([s["speaker"] for s in result["segments"]], ["HOST", "GUEST"])
        self.assertEqual(result["segments"][1]["text"], "Thank you")

    def test_cleans_only_srt_presentation_tags_and_html_entities(self):
        result = parse_text(
            """1
00:00:01,000 --> 00:00:02,000
HOST: <i>Hello &amp;</i> <foo>kept</foo>

2
00:00:02,000 --> 00:00:03,000
GUEST: <font color="red"><b>Hi</b></font> <u>there</u>
""",
            ".srt",
        )

        self.assertEqual(
            [segment["text"] for segment in result["segments"]],
            ["Hello & <foo>kept</foo>", "Hi there"],
        )

    def test_parses_full_interval_labelled_txt(self):
        result = parse_text(
            """[00:00:01.000 --> 00:00:02.000] HOST: First
[00:00:02.000 --> 00:00:03.000] GUEST: Second
""",
            ".txt",
        )

        self.assertEqual(result["metadata"]["duration_ms"], 3_000)
        self.assertEqual(result["segments"][0]["end_ms"], 2_000)

    def test_infers_txt_end_from_next_start_but_leaves_final_end_unknown(self):
        result = parse_text(
            """[00:01] HOST: First
[00:03] GUEST: Second
""",
            ".txt",
        )

        self.assertEqual(result["segments"][0]["end_ms"], 3_000)
        self.assertIsNone(result["segments"][1]["end_ms"])
        self.assertIsNone(result["metadata"]["duration_ms"])

    def test_start_only_txt_allows_unbounded_two_digit_minutes(self):
        result = parse_text(
            """[60:00] HOST: First
[99:59] GUEST: Second
""",
            ".txt",
        )

        self.assertEqual(result["segments"][0]["start_ms"], 3_600_000)
        self.assertEqual(result["segments"][0]["end_ms"], 5_999_000)
        self.assertEqual(result["segments"][1]["start_ms"], 5_999_000)

    def test_start_only_txt_service_cue_remains_a_timing_boundary(self):
        result = parse_text(
            """[00:01] HOST: First
[00:02] HOST: Search in video
[00:03] GUEST: Second
""",
            ".txt",
        )

        self.assertEqual(len(result["segments"]), 2)
        self.assertEqual(result["segments"][0]["end_ms"], 2_000)
        self.assertEqual(result["segments"][1]["start_ms"], 3_000)
        self.assertIsNone(result["segments"][1]["end_ms"])

    def test_keeps_adjacent_same_speaker_cues_separate(self):
        result = parse_text(
            """[00:01] HOST: One
[00:02] HOST: Two
[00:03] GUEST: Three
""",
            ".txt",
        )

        self.assertEqual(len(result["segments"]), 3)

    def test_rejects_invalid_documents(self):
        cases = {
            "unknown role": ("[00:01] MODERATOR: Hi\n[00:02] GUEST: There", ".txt"),
            "missing role": (
                "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n\n"
                "00:00:02.000 --> 00:00:03.000\n<v GUEST>There</v>",
                ".vtt",
            ),
            "empty text": ("[00:01] HOST:   \n[00:02] GUEST: There", ".txt"),
            "overlap": (
                "[00:00:01.000 --> 00:00:03.000] HOST: Hi\n"
                "[00:00:02.000 --> 00:00:04.000] GUEST: There",
                ".txt",
            ),
            "non-monotonic": (
                "[00:03] HOST: Hi\n[00:02] GUEST: There",
                ".txt",
            ),
            "only one role": ("[00:01] HOST: Hi\n[00:02] HOST: Again", ".txt"),
        }
        for label, (text, suffix) in cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                parse_text(text, suffix)

    def test_rejects_unsupported_suffix(self):
        with self.assertRaises(ValueError):
            parse_text("anything", ".md")

    def test_rejects_non_strict_interval_timestamp_formats(self):
        cases = {
            "short TXT interval": (
                "[00:01 --> 00:02] HOST: Hi\n"
                "[00:02:00.000 --> 00:02:01.000] GUEST: There",
                ".txt",
            ),
            "VTT missing milliseconds": (
                "WEBVTT\n\n00:00:01 --> 00:00:02\n<v HOST>Hi\n\n"
                "00:00:02.000 --> 00:00:03.000\n<v GUEST>There",
                ".vtt",
            ),
            "VTT invalid fractional width": (
                "WEBVTT\n\n00:00:01.00 --> 00:00:02.000\n<v HOST>Hi\n\n"
                "00:00:02.000 --> 00:00:03.000\n<v GUEST>There",
                ".vtt",
            ),
            "VTT comma mismatch": (
                "WEBVTT\n\n00:00:01,000 --> 00:00:02,000\n<v HOST>Hi\n\n"
                "00:00:02.000 --> 00:00:03.000\n<v GUEST>There",
                ".vtt",
            ),
            "SRT dot mismatch": (
                "1\n00:00:01.000 --> 00:00:02.000\nHOST: Hi\n\n"
                "2\n00:00:02,000 --> 00:00:03,000\nGUEST: There",
                ".srt",
            ),
            "TXT comma mismatch": (
                "[00:00:01,000 --> 00:00:02,000] HOST: Hi\n"
                "[00:00:02.000 --> 00:00:03.000] GUEST: There",
                ".txt",
            ),
        }
        for label, (text, suffix) in cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                parse_text(text, suffix)

    def test_rejects_non_strict_start_only_txt_timestamps(self):
        invalid_starts = (
            "00:01.000",
            "00:01,000",
            "00:00:01.000",
            "0:01",
            "00",
        )
        for value in invalid_starts:
            text = f"[{value}] HOST: Hi\n[00:02] GUEST: There"
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_text(text, ".txt")

    def test_parses_standard_webvtt_timestamps_blocks_settings_and_inline_tags(self):
        result = parse_text(
            """WEBVTT

STYLE
::cue { color: lime; }

REGION
id:fred
width:40%

host-cue
00:01.000 --> 00:02.000 align:start position:10%
<v HOST><i>Hello &amp; <b>friends</b></i>

guest-cue
00:02.000 --> 00:03.500 line:90%
<v GUEST><c.green><lang en>Welcome</lang> <00:02.500>back</c>
""",
            ".vtt",
        )

        self.assertEqual(
            [segment["text"] for segment in result["segments"]],
            ["Hello & friends", "Welcome back"],
        )
        self.assertEqual(result["metadata"]["duration_ms"], 3_500)

    def test_webvtt_accepts_hour_fields_longer_than_two_digits(self):
        result = parse_text(
            """WEBVTT

100:00:01.000 --> 100:00:02.000
<v HOST>Hello

100:00:02.000 --> 100:00:03.000
<v GUEST>There
""",
            ".vtt",
        )

        self.assertEqual(result["segments"][0]["start_ms"], 360_001_000)
        self.assertEqual(result["metadata"]["duration_ms"], 360_003_000)

    def test_skips_exact_search_service_text_across_formats(self):
        documents = {
            ".vtt": """WEBVTT

00:00:01.000 --> 00:00:02.000
<v HOST>Intro

00:00:02.000 --> 00:00:03.000
 Search   in video

00:00:03.000 --> 00:00:04.000
<v GUEST>Hi
""",
            ".srt": """1
00:00:01,000 --> 00:00:02,000
HOST: Intro

2
00:00:02,000 --> 00:00:03,000
 Search   in video

3
00:00:03,000 --> 00:00:04,000
GUEST: Hi
""",
            ".txt": """[00:00:01.000 --> 00:00:02.000] HOST: Intro
[00:00:02.000 --> 00:00:03.000] Search   in video
[00:00:03.000 --> 00:00:04.000] GUEST: Hi
""",
        }
        for suffix, text in documents.items():
            with self.subTest(suffix=suffix):
                result = parse_text(text, suffix)
                self.assertEqual(
                    [segment["text"] for segment in result["segments"]],
                    ["Intro", "Hi"],
                )

    def test_rejects_generic_unlabelled_timed_cues_across_formats(self):
        documents = {
            ".vtt": """WEBVTT

00:00:01.000 --> 00:00:02.000
<v HOST>Intro

00:00:02.000 --> 00:00:03.000
Chapter One

00:00:03.000 --> 00:00:04.000
<v GUEST>Hi
""",
            ".srt": """1
00:00:01,000 --> 00:00:02,000
HOST: Intro

2
00:00:02,000 --> 00:00:03,000
Chapter One

3
00:00:03,000 --> 00:00:04,000
GUEST: Hi
""",
            ".txt": """[00:00:01.000 --> 00:00:02.000] HOST: Intro
[00:00:02.000 --> 00:00:03.000] Chapter One
[00:00:03.000 --> 00:00:04.000] GUEST: Hi
""",
        }
        for suffix, text in documents.items():
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                parse_text(text, suffix)

    def test_does_not_guess_that_labelled_short_speech_is_metadata(self):
        result = parse_text(
            """[00:01] HOST: Intro
[00:02] GUEST: Q&A
""",
            ".txt",
        )

        self.assertEqual(
            [segment["text"] for segment in result["segments"]],
            ["Intro", "Q&A"],
        )


class ParseFileAndCliTests(unittest.TestCase):
    CONTENT = "[00:01] HOST: Hello\n[00:02] GUEST: Hi"

    def test_parse_file_adds_title_and_source_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "my-talk.txt"
            path.write_text(self.CONTENT, encoding="utf-8")
            result = parse_file(path, "https://example.test/talk")

        self.assertEqual(result["metadata"]["title"], "my-talk")
        self.assertEqual(result["metadata"]["source_url"], "https://example.test/talk")

    def test_cli_writes_utf8_json_and_accepts_title_override(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "talk.txt"
            output_path = Path(directory) / "out.json"
            input_path.write_text(self.CONTENT, encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "parse_transcript.py"),
                    str(input_path),
                    str(output_path),
                    "--source-url",
                    "https://example.test",
                    "--title",
                    "Разговор",
                ],
                check=True,
            )
            raw = output_path.read_text(encoding="utf-8")
            result = json.loads(raw)

        self.assertIn("Разговор", raw)
        self.assertEqual(result["metadata"]["title"], "Разговор")

    def test_cli_reports_expected_input_errors_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "bad.txt"
            output_path = Path(directory) / "out.json"
            input_path.write_text("[00:01] MODERATOR: Nope", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "parse_transcript.py"),
                    str(input_path),
                    str(output_path),
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertTrue(completed.stderr.startswith("error: "))
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(completed.stdout, "")


if __name__ == "__main__":
    unittest.main()
