from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from types import SimpleNamespace
from zoneinfo import ZoneInfo


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = RUNTIME_ROOT / "scripts" / "personal_daily_system.py"


def load_module():
    spec = importlib.util.spec_from_file_location("portable_personal_daily", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context_fixture() -> dict:
    return {
        "schema_version": 1,
        "status": "approved",
        "focus_until": "2099-12-31",
        "active_understanding": "Act from what feels alive.",
        "l1": {"status": "approved", "text": "Live and create freely."},
        "questions": {
            "morning": "What matters today?",
            "evening": "What became clearer today?",
        },
        "warning_patterns": ["Continuing only because effort was invested."],
        "viability_reflections": {
            "affirmations": ["I notice what makes me more alive."],
            "understandings": ["Goals are hypotheses, not obligations."],
        },
        "focus_groups": [
            {
                "id": "primary",
                "label": "Primary direction",
                "l2": "Create a useful result.",
                "period_focus": "Finish one meaningful iteration.",
            }
        ],
        "task_choices": [
            {
                "number": 1,
                "id": "task-001",
                "group_id": "primary",
                "status": "active",
                "label": "Prepare the first artifact",
                "l2": "Create a useful result.",
                "period_focus": "Finish one meaningful iteration.",
                "day_result": "One artifact is ready.",
                "first_step": "Open the draft.",
                "duration_minutes": 30,
            },
            {
                "number": 2,
                "id": "task-002",
                "group_id": "primary",
                "status": "active",
                "label": "Send the artifact",
                "l2": "Create a useful result.",
                "period_focus": "Finish one meaningful iteration.",
                "day_result": "The artifact is delivered.",
                "first_step": "Choose the recipient.",
                "duration_minutes": 30,
            },
        ],
    }


class PortablePersonalDailyRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "private"
        self.context_path = self.root / "context" / "active_context.json"
        self.context_path.parent.mkdir(parents=True)
        self.context_path.write_text(
            json.dumps(context_fixture(), ensure_ascii=False),
            encoding="utf-8",
        )
        self.service = self.module.PersonalDailyService(
            repo_root=self.root,
            data_dir=self.data_dir,
            context_path=self.context_path,
            timezone="UTC",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_text_send_command_never_adds_media_arguments(self) -> None:
        command = self.module.build_openclaw_send_command(
            {"text": "Hello"}, target="123", dry_run=True
        )
        self.assertNotIn("--media", command)
        self.assertEqual(command[-1], "--dry-run")

    def test_morning_accepts_multiple_task_numbers_in_free_text(self) -> None:
        now = datetime(2099, 1, 2, 8, 0, tzinfo=ZoneInfo("UTC"))
        self.service.prepare("morning", now=now)
        self.service.route_reply("Morning answer", message_id="m1", now=now)
        choices = self.service.route_reply("Control answer", message_id="m2", now=now)
        self.assertIn("1.", choices["text"])
        result = self.service.route_reply("1 и 2", message_id="m3", now=now)
        self.assertIn("Prepare the first artifact", result["text"])
        self.assertIn("Send the artifact", result["text"])
        events = self.service.store.load_materialized_events()
        intents = [event for event in events if event["type"] == "morning_intent"]
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0]["links"]["choice_numbers"], [1, 2])

    def test_viability_uses_context_reflection_and_text_buttons(self) -> None:
        response = self.service.prepare(
            "viability",
            now=datetime(2099, 1, 2, 12, 0, tzinfo=ZoneInfo("UTC")),
        )
        self.assertTrue(
            "I notice what makes me more alive." in response["text"]
            or "Goals are hypotheses, not obligations." in response["text"]
        )
        self.assertEqual([button["text"] for button in response["buttons"]], ["−−", "−", "=", "+", "++"])
        self.assertEqual(set(response), {"workflow", "text", "buttons"})

    def test_idea_capture_is_idempotent_and_renders_view(self) -> None:
        event = self.service.store.append_event(
            {
                "type": "idea",
                "idempotency_key": "telegram:42:idea",
                "source": {"channel": "telegram", "message_id": "42"},
                "description": "Idea: create a small prototype",
            }
        )
        repeated = self.service.store.append_event(
            {
                "type": "idea",
                "idempotency_key": "telegram:42:idea",
                "source": {"channel": "telegram", "message_id": "42"},
                "description": "Idea: create a small prototype",
            }
        )
        self.assertEqual(event["id"], repeated["id"])
        paths = self.module.render_reading_views(
            self.data_dir,
            self.service.store.load_materialized_events(),
        )
        self.assertIn("create a small prototype", Path(paths["ideas"]).read_text(encoding="utf-8"))

    def test_dispatch_without_activity_argument_does_not_read_default_manifest(self) -> None:
        args = SimpleNamespace(at="2099-01-02T22:00:00+00:00", codex_activity=None, workflow="evening")
        store = SimpleNamespace(repo_root=self.root, events_path=self.data_dir / "events.jsonl", data_dir=self.data_dir)
        with mock.patch.object(self.module, "PersonalDailyService") as service, mock.patch.object(self.module, "PersonalReportService") as reporter:
            service.return_value._local_now.return_value = datetime(2099, 1, 2, 22, tzinfo=ZoneInfo("UTC"))
            service.return_value.prepare.return_value = {"status": "skipped"}
            reporter.return_value.write_evening_report.return_value = {"text": "Synthetic report"}
            self.module._dispatch_lifecycle(args, store, target="123", state_path=None, context_path=self.context_path)
        self.assertIsNone(reporter.return_value.write_evening_report.call_args.kwargs["codex_activity_path"])

    def test_configured_summaries_directory_precedes_project_default(self) -> None:
        configured = self.root / "selected-summaries"
        configured.mkdir()
        wanted = configured / "2099-01-02 саммари.md"
        wanted.write_text("Fictional selected summary", encoding="utf-8")
        fallback = self.root / "summaries"
        fallback.mkdir()
        (fallback / "2099-01-03 саммари.md").write_text("Unselected summary", encoding="utf-8")
        with mock.patch.dict(os.environ, {"PDS_SUMMARIES_DIR": str(configured)}):
            result = self.module._latest_summary_path(self.root)
        self.assertEqual(result[1], wanted)

    def test_empty_configured_summaries_directory_does_not_fall_back(self) -> None:
        configured = self.root / "selected-summaries"
        configured.mkdir()
        fallback = self.root / "summaries"
        fallback.mkdir()
        (fallback / "2099-01-03 саммари.md").write_text("Unselected summary", encoding="utf-8")
        with mock.patch.dict(os.environ, {"PDS_SUMMARIES_DIR": str(configured)}):
            self.assertIsNone(self.module._latest_summary_path(self.root))

    def test_summary_refresh_reads_generic_summaries_folder(self) -> None:
        summaries = self.root / "summaries"
        summaries.mkdir()
        (summaries / "2099-01-02 саммари.md").write_text(
            """# Саммари

## Новые понимания

### Факты

1. **Свежее понимание.**

### Механизмы

1. Полезный механизм.

## Аффирмации

1. Личная аффирмация.

## Вопросы

- **Утро:** Новый утренний вопрос?
- **Вечер:** Новый вечерний вопрос?

## Повторяющиеся неконструктивные паттерны

1. Паттерн для наблюдения.
""",
            encoding="utf-8",
        )
        with mock.patch.object(
            self.module,
            "_summary_section",
            wraps=self.module._summary_section,
        ):
            result = self.module.refresh_active_context_from_latest_summary(
                repo_root=self.root,
                context_path=self.context_path,
                now=datetime(2099, 1, 3, tzinfo=ZoneInfo("UTC")),
            )
        self.assertEqual(result["status"], "updated")


if __name__ == "__main__":
    unittest.main()
