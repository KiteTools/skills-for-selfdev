"""Morning interaction regressions using only synthetic context and temporary state."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from test_personal_daily_system import context_fixture, load_module


class MorningFreeformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.context_path = self.root / "context.json"
        self.context_path.write_text(json.dumps(context_fixture()), encoding="utf-8")
        self.context_before = self.context_path.read_bytes()
        self.module = load_module()
        self.service = self.module.PersonalDailyService(
            repo_root=self.root, data_dir=self.root / "private",
            context_path=self.context_path, timezone="UTC",
        )
        self.now = datetime.fromisoformat("2099-01-02T08:00:00+00:00")

    def tearDown(self):
        self.temp.cleanup()

    def morning_prompt(self):
        self.service.prepare("morning", now=self.now)
        self.service.route_reply("Focus on a useful prototype", message_id="m1", now=self.now)
        return self.service.route_reply("Notice my curiosity", message_id="m2", now=self.now)

    def intents(self):
        return [e for e in self.service.store.load_events() if e["type"] == "morning_intent"]

    def test_freeform_prompt_hides_catalog_and_offers_generic_button(self):
        response = self.morning_prompt()
        self.assertIn("Напиши своими словами", response["text"])
        self.assertNotIn("Prepare the first artifact", response["text"])
        self.assertEqual(["Показать задачи"], [b["text"] for b in response["buttons"]])

    def test_catalog_callback_is_read_only_and_then_allows_selection(self):
        response = self.morning_prompt()
        callback = response["buttons"][0]["callback_data"]
        catalog = self.service.route_callback(callback, now=self.now)
        self.assertEqual("shown", catalog["status"])
        self.assertIn("1. Prepare the first artifact", catalog["text"])
        self.assertEqual([], self.intents())
        self.assertEqual("awaiting_task_choice", self.service.pending_interaction(now=self.now)["stage"])
        result = self.service.route_reply("1", message_id="choice", now=self.now)
        self.assertEqual(["task-001"], result["event"]["links"]["choice_ids"])
        self.assertEqual("stale", self.service.route_callback(callback, now=self.now)["status"])

    def test_text_catalog_request_is_not_saved_as_intent(self):
        self.morning_prompt()
        result = self.service.route_reply("Показать задачи", message_id="catalog", now=self.now)
        self.assertEqual("shown", result["status"])
        self.assertEqual([], self.intents())
        self.assertEqual(result, self.service.route_reply("Показать задачи", message_id="catalog", now=self.now))

    def test_freeform_choice_preserves_words_and_does_not_mutate_context(self):
        self.morning_prompt()
        text = "Собрать 2 варианта простого прототипа"
        result = self.service.route_reply(text, message_id="choice", now=self.now)
        self.assertEqual("recorded", result["status"])
        self.assertEqual(text, result["event"]["description"])
        self.assertEqual("freeform", result["event"]["self_report"]["selection_mode"])
        self.assertEqual([], result["event"]["links"]["choice_ids"])
        self.assertIsNone(result["event"]["links"]["l2"])
        self.assertEqual(self.context_before, self.context_path.read_bytes())
        self.assertEqual(result, self.service.route_reply(text, message_id="choice", now=self.now))
        self.assertEqual(1, len(self.intents()))

    def test_retry_after_event_write_reuses_original_choice_and_result(self):
        self.morning_prompt()
        with self.service._state_transaction() as state:
            first = self.service._record_morning_choice(
                "task-001", source={"channel": "telegram", "message_id": "before-restart"},
                pending=state["pending_interaction"],
            )
        result = self.service.route_reply("Другая идея после перезапуска", message_id="retry", now=self.now)
        self.assertEqual(first["event"]["id"], result["event"]["id"])
        self.assertEqual(first["day_result"], result["day_result"])
        self.assertEqual(first["first_step"], result["first_step"])
        self.assertEqual(1, len(self.intents()))

    def test_legacy_multiple_numbers_remain_supported(self):
        self.morning_prompt()
        result = self.service.route_reply("1 и 2", message_id="choice", now=self.now)
        self.assertEqual([1, 2], result["event"]["links"]["choice_numbers"])

    def test_zero_means_no_focus(self):
        self.morning_prompt()
        result = self.service.route_reply("0", message_id="choice", now=self.now)
        self.assertTrue(result["event"]["self_report"]["no_focus"])

    def test_invalid_numeric_selection_does_not_become_freeform(self):
        self.morning_prompt()
        for index, text in enumerate(("-1", "0 и 2", "99")):
            with self.subTest(text=text):
                result = self.service.route_reply(text, message_id=f"invalid-{index}", now=self.now)
                self.assertEqual("invalid", result["status"])
        self.assertEqual([], self.intents())

    def test_legacy_task_id_callback_remains_idempotent(self):
        self.morning_prompt()
        with self.service._state_transaction() as state:
            pending = state["pending_interaction"]
            choice = copy.deepcopy(pending["payload"]["choices_snapshot"]["task-002"])
            state["callbacks"]["pd:m:20990102:task-002"] = {
                "workflow": "morning", "issued_at": self.now.isoformat(),
                "expires_at": (self.now + timedelta(minutes=30)).isoformat(),
                "metadata": {"interaction_id": pending["interaction_id"],
                             "choice_id": choice["id"], "choice_snapshot": choice,
                             "l1_snapshot": pending["payload"]["l1_snapshot"]},
            }
        callback = "pd:m:20990102:task-002"
        result = self.service.route_callback(callback, now=self.now)
        self.assertEqual("task-002", result["event"]["links"]["choice_id"])
        self.assertEqual(result, self.service.route_callback(callback, now=self.now))
        self.assertEqual(1, len(self.intents()))

    def test_compact_renewal_keeps_freeform_and_text_catalog_available(self):
        self.morning_prompt()
        renewed = self.service.prepare("morning", compact=True, now=self.now + timedelta(minutes=1))
        self.assertIn("Напиши своими словами", renewed["text"])
        self.assertNotIn("Prepare the first artifact", renewed["text"])
        catalog = self.service.route_reply("Показать задачи", message_id="renewed-catalog", now=self.now + timedelta(minutes=2))
        self.assertEqual("shown", catalog["status"])
        result = self.service.route_reply("Собрать небольшой пример", message_id="renewed-choice", now=self.now + timedelta(minutes=2))
        self.assertEqual("recorded", result["status"])

    def test_catalog_preserves_numbers_and_rejects_completed_tasks(self):
        self.service.context["task_choices"][0]["status"] = "completed"
        self.service.context["task_choices"][1]["number"] = 7
        response = self.morning_prompt()
        catalog = self.service.route_callback(response["buttons"][0]["callback_data"], now=self.now)
        self.assertIn("7. Send the artifact", catalog["text"])
        self.assertIn("1. ✅ Prepare the first artifact", catalog["text"])
        rejected = self.service.route_reply("1", message_id="completed", now=self.now)
        self.assertEqual("invalid", rejected["status"])
        chosen = self.service.route_reply("7", message_id="active", now=self.now)
        self.assertEqual([7], chosen["event"]["links"]["choice_numbers"])

    def test_catalog_uses_issued_snapshot_after_context_changes(self):
        response = self.morning_prompt()
        self.service.context["task_choices"][0]["label"] = "New unpublished task wording"
        catalog = self.service.route_callback(response["buttons"][0]["callback_data"], now=self.now)
        self.assertIn("Prepare the first artifact", catalog["text"])
        self.assertNotIn("New unpublished task wording", catalog["text"])


if __name__ == "__main__":
    unittest.main()
