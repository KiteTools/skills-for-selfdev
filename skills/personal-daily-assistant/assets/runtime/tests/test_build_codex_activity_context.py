import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

# Import the bundled runtime, independent of the caller's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zoneinfo import ZoneInfo

from scripts.build_codex_activity_context import (
    build_parser,
    _iter_transcript_paths,
    load_session_index,
    normalize_agent_message,
    normalize_user_message,
    render_manifest,
    resolve_window,
    scan_transcripts,
)


class ExplicitSourceTests(unittest.TestCase):
    def test_cli_requires_explicit_source_directory(self):
        from contextlib import redirect_stderr
        import io
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            build_parser().parse_args(["--date", "2099-01-02"])
        self.assertEqual(error.exception.code, 2)

    def test_selected_export_scope_does_not_follow_external_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = root / "selected"
            selected.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (outside / "private.jsonl").write_text("Synthetic data", encoding="utf-8")
            (selected / "sessions").symlink_to(outside, target_is_directory=True)
            (selected / "session_index.jsonl").symlink_to(outside / "private.jsonl")
            self.assertEqual(list(_iter_transcript_paths(selected)), [])
            self.assertEqual(load_session_index(selected), {})



def write_jsonl(path: Path, records: list[dict], *, corrupt_tail: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    if corrupt_tail:
        lines.append("{broken json")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def event(timestamp: str, event_type: str, **payload: object) -> dict:
    return {
        "timestamp": timestamp,
        "type": "event_msg",
        "payload": {"type": event_type, **payload},
    }


class CodexActivityContextTests(unittest.TestCase):
    def test_normalizes_heartbeat_and_files_wrapper(self) -> None:
        heartbeat = """<heartbeat>
        <automation_id>sample-daily-heartbeat</automation_id>
        <instructions>Long recurring automation instructions that should not enter the manifest.</instructions>
        </heartbeat>"""
        wrapped_request = """# Files mentioned by the user:

        - notes.md

        ## My request for Codex:
        Собери короткий дневной отчёт.
        """

        self.assertEqual(
            normalize_user_message(heartbeat),
            "Heartbeat: sample-daily-heartbeat",
        )
        self.assertEqual(
            normalize_user_message(wrapped_request),
            "Собери короткий дневной отчёт.",
        )
        self.assertEqual(
            normalize_agent_message(
                """<heartbeat><automation_id>sample-daily-heartbeat</automation_id>
                <decision>DONT_NOTIFY</decision><message>Новых сигналов нет.</message></heartbeat>"""
            ),
            "DONT_NOTIFY: Новых сигналов нет.",
        )

    def test_resolve_window_uses_lisbon_calendar_day(self) -> None:
        start, end = resolve_window(
            single_date="2026-07-18",
            date_from=None,
            date_to=None,
            timezone_name="Europe/Lisbon",
        )

        self.assertEqual(start, datetime(2026, 7, 18, tzinfo=ZoneInfo("Europe/Lisbon")))
        self.assertEqual(end, datetime(2026, 7, 19, tzinfo=ZoneInfo("Europe/Lisbon")))

    def test_scan_omits_transport_and_cron_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            sessions = {
                "transport": "Conversation info (untrusted metadata): Telegram",
                "cron": "[cron:fixture001] sample-daily-heartbeat",
                "meaningful": "Подготовь ролики по Debug",
            }
            for index, session_id in enumerate(sessions):
                write_jsonl(
                    codex_home / "sessions" / f"rollout-{session_id}.jsonl",
                    [
                        {
                            "timestamp": f"2026-07-18T{8 + index:02d}:00:00Z",
                            "type": "session_meta",
                            "payload": {
                                "id": session_id,
                                "cwd": "/repo",
                                "source": "cli",
                            },
                        },
                        event(
                            f"2026-07-18T{8 + index:02d}:01:00Z",
                            "user_message",
                            message=f"Запрос {session_id}",
                        ),
                        event(
                            f"2026-07-18T{8 + index:02d}:02:00Z",
                            "task_complete",
                            turn_id=f"turn-{session_id}",
                            last_agent_message=f"Результат {session_id}",
                        ),
                    ],
                )
            (codex_home / "session_index.jsonl").write_text(
                "\n".join(
                    json.dumps(
                        {"id": session_id, "thread_name": title},
                        ensure_ascii=False,
                    )
                    for session_id, title in sessions.items()
                )
                + "\n",
                encoding="utf-8",
            )
            start, end = resolve_window(
                single_date="2026-07-18",
                date_from=None,
                date_to=None,
                timezone_name="Europe/Lisbon",
            )

            result = scan_transcripts(codex_home, start, end)

            self.assertEqual(
                ["Подготовь ролики по Debug"],
                [session.title for session in result.sessions],
            )

    def test_scans_root_turns_filters_subagents_and_redacts_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            root_id = "019f-root-session"
            root_file = codex_home / "sessions/2026/07/17/rollout-root.jsonl"
            subagent_file = codex_home / "sessions/2026/07/18/rollout-subagent.jsonl"
            old_file = codex_home / "archived_sessions/rollout-old.jsonl"

            write_jsonl(
                root_file,
                [
                    {
                        "timestamp": "2026-07-17T22:45:00Z",
                        "type": "session_meta",
                        "payload": {
                            "id": root_id,
                            "cwd": "/repo",
                            "originator": "Codex Desktop",
                            "source": "vscode",
                        },
                    },
                    event(
                        "2026-07-17T22:50:00Z",
                        "user_message",
                        message="Собери отчёт token=supersecret sk-abcdefghijklmnopqrstuvwxyz",
                    ),
                    {
                        "timestamp": "2026-07-18T00:00:00Z",
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call",
                            "name": "exec",
                            "input": "await tools.exec_command({});\n*** Update File: reports/day.md",
                        },
                    },
                    event(
                        "2026-07-18T00:04:00Z",
                        "agent_message",
                        message="Промежуточное сообщение, которое не должно дублировать финал.",
                    ),
                    event(
                        "2026-07-18T00:05:00Z",
                        "task_complete",
                        turn_id="turn-1",
                        last_agent_message="Отчёт готов. password=hunter2",
                    ),
                    event(
                        "2026-07-18T08:00:00Z",
                        "user_message",
                        message="Проверь второй поток",
                    ),
                    {
                        "timestamp": "2026-07-18T08:00:30Z",
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call",
                            "name": "exec",
                            "input": "await tools.exec_command({});\n*** Update File: reports/day.md",
                        },
                    },
                    event(
                        "2026-07-18T08:01:00Z",
                        "turn_aborted",
                        turn_id="turn-2",
                        reason="interrupted",
                    ),
                    event(
                        "2026-07-18T09:00:00Z",
                        "user_message",
                        message="Незавершённая задача",
                    ),
                    event(
                        "2026-07-18T09:01:00Z",
                        "agent_message",
                        message="Начал исследование token=freshsecret",
                    ),
                ],
                corrupt_tail=True,
            )
            write_jsonl(
                subagent_file,
                [
                    {
                        "timestamp": "2026-07-18T08:00:00Z",
                        "type": "session_meta",
                        "payload": {
                            "id": "subagent-session",
                            "parent_thread_id": root_id,
                            "cwd": "/repo",
                            "source": {"subagent": {"other": "guardian"}},
                        },
                    },
                    event(
                        "2026-07-18T08:01:00Z",
                        "user_message",
                        message="Служебный subagent prompt",
                    ),
                    event(
                        "2026-07-18T08:02:00Z",
                        "task_complete",
                        turn_id="sub-turn",
                        last_agent_message="Служебный результат",
                    ),
                ],
            )
            write_jsonl(
                old_file,
                [
                    {
                        "timestamp": "2026-07-16T08:00:00Z",
                        "type": "session_meta",
                        "payload": {"id": "old", "cwd": "/repo", "source": "cli"},
                    },
                    event(
                        "2026-07-16T08:01:00Z",
                        "user_message",
                        message="Старая задача",
                    ),
                    event(
                        "2026-07-16T08:02:00Z",
                        "task_complete",
                        turn_id="old-turn",
                        last_agent_message="Старый результат",
                    ),
                ],
            )
            (codex_home / "session_index.jsonl").write_text(
                json.dumps(
                    {
                        "id": root_id,
                        "thread_name": "Дневной отчёт",
                        "updated_at": "2026-07-18T09:01:00Z",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            start, end = resolve_window(
                single_date="2026-07-18",
                date_from=None,
                date_to=None,
                timezone_name="Europe/Lisbon",
            )
            result = scan_transcripts(codex_home, start, end)
            manifest = render_manifest(
                result,
                start=start,
                end=end,
                timezone_name="Europe/Lisbon",
                max_chars=6500,
            )

            self.assertEqual(len(result.sessions), 1)
            self.assertEqual(result.excluded_subagents, 1)
            self.assertEqual(result.invalid_lines, 1)
            self.assertEqual([turn.status for turn in result.sessions[0].turns], [
                "in_progress",
                "aborted",
                "completed",
            ])
            self.assertIn("Дневной отчёт", manifest)
            self.assertIn("reports/day.md", manifest)
            self.assertIn("exec_command", manifest)
            self.assertIn("[REDACTED]", manifest)
            self.assertTrue(
                any("Отчёт готов" in turn.result for turn in result.sessions[0].turns)
            )
            self.assertNotIn("supersecret", manifest)
            self.assertNotIn("hunter2", manifest)
            self.assertNotIn("freshsecret", manifest)
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", manifest)
            self.assertNotIn("Служебный subagent prompt", manifest)
            self.assertNotIn("Старая задача", manifest)
            self.assertNotIn("Промежуточное сообщение", manifest)

    def test_manifest_has_global_character_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            records: list[dict] = [
                {
                    "timestamp": "2026-07-18T08:00:00Z",
                    "type": "session_meta",
                    "payload": {"id": "long", "cwd": "/repo", "source": "cli"},
                }
            ]
            for index in range(20):
                records.extend(
                    [
                        event(
                            f"2026-07-18T08:{index:02d}:00Z",
                            "user_message",
                            message=f"Запрос {index} " + "я" * 500,
                        ),
                        event(
                            f"2026-07-18T08:{index:02d}:30Z",
                            "task_complete",
                            turn_id=f"turn-{index}",
                            last_agent_message=f"Результат {index} " + "р" * 1000,
                        ),
                    ]
                )
            write_jsonl(codex_home / "sessions/rollout-long.jsonl", records)

            start, end = resolve_window(
                single_date="2026-07-18",
                date_from=None,
                date_to=None,
                timezone_name="Europe/Lisbon",
            )
            result = scan_transcripts(codex_home, start, end)
            manifest = render_manifest(
                result,
                start=start,
                end=end,
                timezone_name="Europe/Lisbon",
                max_chars=1200,
            )

            self.assertLessEqual(len(manifest), 1200)
            self.assertIn("Manifest truncated", manifest)

    def test_manifest_prefers_recent_activity_when_truncated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            write_jsonl(
                codex_home / "sessions/rollout-spanning-window.jsonl",
                [
                    {
                        "timestamp": "2026-07-01T08:00:00Z",
                        "type": "session_meta",
                        "payload": {"id": "spanning", "cwd": "/repo", "source": "cli"},
                    },
                    event(
                        "2026-07-01T08:01:00Z",
                        "user_message",
                        message="Старый запрос " + "с" * 400,
                    ),
                    event(
                        "2026-07-01T08:02:00Z",
                        "task_complete",
                        turn_id="old",
                        last_agent_message="Старый результат " + "р" * 700,
                    ),
                    event(
                        "2026-07-18T08:01:00Z",
                        "user_message",
                        message="Свежий запрос для дневного анализа",
                    ),
                    event(
                        "2026-07-18T08:02:00Z",
                        "task_complete",
                        turn_id="recent",
                        last_agent_message="Свежий результат",
                    ),
                ],
            )
            start, end = resolve_window(
                single_date=None,
                date_from="2026-07-01",
                date_to="2026-07-19",
                timezone_name="Europe/Lisbon",
            )
            result = scan_transcripts(codex_home, start, end)
            manifest = render_manifest(
                result,
                start=start,
                end=end,
                timezone_name="Europe/Lisbon",
                max_chars=900,
            )

            self.assertIn("Свежий запрос", manifest)
            self.assertIn("Manifest truncated", manifest)

    def test_manifest_limits_each_session_to_latest_two_turns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            records: list[dict] = [
                {
                    "timestamp": "2026-07-18T08:00:00Z",
                    "type": "session_meta",
                    "payload": {"id": "chatty", "cwd": "/repo", "source": "cli"},
                }
            ]
            for index in range(5):
                records.extend(
                    [
                        event(
                            f"2026-07-18T08:0{index}:00Z",
                            "user_message",
                            message=f"Ход {index}",
                        ),
                        event(
                            f"2026-07-18T08:0{index}:30Z",
                            "task_complete",
                            turn_id=f"turn-{index}",
                            last_agent_message=f"Итог {index}",
                        ),
                    ]
                )
            write_jsonl(codex_home / "sessions/rollout-chatty.jsonl", records)
            start, end = resolve_window(
                single_date="2026-07-18",
                date_from=None,
                date_to=None,
                timezone_name="Europe/Lisbon",
            )
            result = scan_transcripts(codex_home, start, end)
            manifest = render_manifest(
                result,
                start=start,
                end=end,
                timezone_name="Europe/Lisbon",
                max_chars=6500,
            )

            self.assertIn("Ход 4", manifest)
            self.assertIn("Ход 3", manifest)
            self.assertNotIn("Ход 2", manifest)
            self.assertIn("Older turns omitted: 3", manifest)


if __name__ == "__main__":
    unittest.main()
