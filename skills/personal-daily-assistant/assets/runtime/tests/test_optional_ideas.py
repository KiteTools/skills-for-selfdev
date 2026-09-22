from datetime import datetime
import json
from unittest import mock
from zoneinfo import ZoneInfo
import unittest
import test_personal_daily_system as base

class OptionalIdeaTests(unittest.TestCase):
    setUp = base.PortablePersonalDailyRuntimeTests.setUp
    tearDown = base.PortablePersonalDailyRuntimeTests.tearDown
    def open_idea(self):
        now = datetime(2099, 1, 2, 22, tzinfo=ZoneInfo('UTC'))
        self.service.store.append_event({'type': 'idea', 'idempotency_key': 'synthetic-idea', 'occurred_at': now.isoformat(), 'source': {'channel': 'telegram'}, 'description': 'Идея: вымышленная заметка'})
        self.service.prepare('evening', now=now, report_text='Synthetic report')
        self.service.route_reply('Ничего больше', message_id='synthetic-gap', now=now)
        result = self.service.route_reply('Стало яснее', message_id='synthetic-answer', now=now)
        return now, result

    def test_idea_review_offers_a_choice_without_promoting_existing_evidence(self):
        original = self.context_path.read_bytes()
        with mock.patch.object(self.service, '_promote_idea') as promote:
            now, result = self.open_idea()
            self.assertEqual(result['next_stage'], 'awaiting_idea_choice')
            self.assertNotIn('15–30', result['text'])
            self.assertIn('пропустить', result['text'])
            result = self.service.route_reply('пропустить', message_id='synthetic-skip', now=now)
            self.assertEqual(result['status'], 'recorded')
            promote.assert_not_called()
        self.assertEqual(original, self.context_path.read_bytes())

    def test_discussion_saves_note_without_forcing_artifact_task_or_success(self):
        original = self.context_path.read_bytes()
        now, _ = self.open_idea()
        result = self.service.route_reply('обсудить', message_id='synthetic-discuss', now=now)
        self.assertEqual(result['next_stage'], 'awaiting_idea_result')
        result = self.service.route_reply('Пока просто интересно, хочу подумать.', message_id='synthetic-note', now=now)
        self.assertEqual(result['status'], 'recorded')
        self.assertNotIn('task', result)
        self.assertEqual(original, self.context_path.read_bytes())
        self.assertFalse(any(e['type'] == 'success' for e in self.service.store.load_materialized_events()))
