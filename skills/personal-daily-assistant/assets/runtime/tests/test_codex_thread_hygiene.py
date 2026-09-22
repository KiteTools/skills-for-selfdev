import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Import the bundled runtime, independent of the caller's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.codex_thread_hygiene as hygiene
from scripts.codex_thread_hygiene import (
    latest_trajectory_thread_id,
    select_archive_candidates,
)


class CodexThreadHygieneTests(unittest.TestCase):
    def test_selects_only_terminal_future_technical_threads(self):
        cutoff = int(
            datetime(2026, 7, 25, 23, tzinfo=timezone.utc).timestamp()
        )
        threads = [
            {
                "id": "safe",
                "name": "Conversation info (untrusted metadata): transport",
                "preview": "",
                "createdAt": cutoff + 1,
                "status": {"type": "idle"},
            },
            {
                "id": "current",
                "name": "[cron:heartbeat]",
                "preview": "",
                "createdAt": cutoff + 1,
                "status": {"type": "idle"},
            },
            {
                "id": "daily-system",
                "name": "[personal-daily:transport] daily system",
                "preview": "",
                "createdAt": cutoff + 1,
                "status": {"type": "idle"},
            },
            {
                "id": "morning-content",
                "name": "[personal-daily:transport] morning reminder",
                "preview": "",
                "createdAt": cutoff + 1,
                "status": {"type": "idle"},
            },
            {
                "id": "meaningful",
                "name": "Draft a learning note",
                "preview": "Собери статью",
                "createdAt": cutoff + 1,
                "status": {"type": "idle"},
            },
            {
                "id": "old",
                "name": "[cron:old]",
                "preview": "",
                "createdAt": cutoff - 1,
                "status": {"type": "idle"},
            },
            {
                "id": "active",
                "name": "[cron:running]",
                "preview": "",
                "createdAt": cutoff + 1,
                "status": {"type": "active", "activeFlags": []},
            },
            {
                "id": "technical-without-receipt",
                "name": "[cron:no receipt needed]",
                "preview": "",
                "createdAt": cutoff + 1,
                "status": {"type": "idle"},
            },
        ]
        self.assertEqual(
            [
                "safe",
                "daily-system",
                "morning-content",
                "technical-without-receipt",
            ],
            [
                thread["id"]
                for thread in select_archive_candidates(
                    threads,
                    delivered_ids={
                        "safe",
                        "current",
                        "daily-system",
                        "morning-content",
                        "meaningful",
                        "old",
                        "active",
                    },
                    protected_ids={"current"},
                    cutoff_epoch=cutoff,
                )
            ],
        )

    def test_latest_trajectory_thread_id_uses_last_session_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.trajectory.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "session.started",
                                "data": {"threadId": "first"},
                            }
                        ),
                        "{bad json",
                        json.dumps(
                            {
                                "type": "session.started",
                                "data": {"threadId": "latest"},
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual("latest", latest_trajectory_thread_id(path))

    def test_uses_isolated_app_server_for_shared_session_store(self):
        self.assertTrue(hasattr(hygiene, "codex_app_server_command"))
        self.assertEqual(
            ["codex", "app-server", "--stdio"],
            hygiene.codex_app_server_command(
                Path("/tmp/codex-control.sock")
            ),
        )
