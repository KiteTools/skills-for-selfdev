"""Fictional, offline checks of prepared Ten import and explicit feedback."""
import copy
import importlib.util
import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'evening_ten.py'

def load():
    spec = importlib.util.spec_from_file_location('portable_ten', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def fixture():
    return {
        'schema_version': 1, 'date': '2099-01-02', 'timezone': 'UTC',
        'source_manifest': {'evidence_ids': ['e1', 'e2', 'e3'], 'goal_ids': ['g1']},
        'day_threads': [{'id': f't{i}', 'title': f'Fictional thread {i}', 'substantive': True, 'evidence_ids': [f'e{i}']} for i in range(1, 4)],
        'day_summary': 'Three fictional activities; offline activity is unknown.', 'alignment': None,
        'candidates': [{'id': f'c{i}', 'text': f'Fictional opportunity {i}: try a small change for a clearer example.', 'goal_id': 'g1', 'evidence_ids': [f'e{(i-1)%3+1}'], 'thread_id': f't{(i-1)%3+1}', 'move_type': f'move-{i%4}', 'mechanism': 'A fictional useful connection.', 'exploratory': i <= 3} for i in range(1, 21)],
        'selected': [f'c{i}' for i in range(1, 11)],
        'checks': {'history_available': False, 'coverage_complete_for_supplied_input': True, 'preparation_reviewed': True},
    }

class EveningTenTests(unittest.TestCase):
    def setUp(self):
        self.module = load()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.module.TenStore(self.root, 'UTC')
        self.now = datetime(2099, 1, 2, 22, tzinfo=ZoneInfo('UTC'))

    def test_import_is_idempotent_and_numbering_cannot_be_replaced(self):
        self.assertEqual(self.store.ingest(fixture())['status'], 'saved')
        self.assertEqual(self.store.ingest(fixture())['status'], 'already_saved')
        changed = fixture(); changed['selected'].reverse()
        with self.assertRaisesRegex(ValueError, 'immutable'):
            self.store.ingest(changed)
        self.assertFalse((self.root / 'state.json').exists())
        self.assertFalse((self.root / 'events.jsonl').exists())

    def test_invalid_evidence_diversity_and_raw_data_are_rejected_without_writes(self):
        for mutation in ['evidence', 'count', 'diversity', 'coverage', 'private']:
            value = fixture()
            if mutation == 'evidence': value['candidates'][0]['evidence_ids'] = ['invented']
            if mutation == 'count': value['selected'].pop()
            if mutation == 'diversity':
                for c in value['candidates']: c['move_type'] = 'same'
            if mutation == 'coverage': value['day_threads'].pop()
            if mutation == 'private': value['raw_screenshots'] = ['private data']
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.store.ingest(value)
        self.assertFalse((self.root / 'evening-ten').exists())

    def test_delivery_dry_run_no_data_and_uncertain_transport_do_not_fake_success(self):
        calls = []
        send = lambda text: calls.append(text) or {'message_id': 'synthetic-1'}
        self.assertEqual(self.store.dispatch(self.now, send=send)['status'], 'no_data')
        self.store.ingest(fixture())
        self.assertEqual(self.store.dispatch(self.now, send=send, dry_run=True)['status'], 'preview')
        self.assertFalse(calls)
        self.assertEqual(self.store.dispatch(self.now, send=lambda text: {})['status'], 'delivery_uncertain')
        self.assertEqual(self.store.dispatch(self.now, send=send)['status'], 'delivery_uncertain')
        self.assertFalse(calls)

    def test_interest_choice_and_reported_completion_are_separate_and_do_not_touch_retro(self):
        state = self.root / 'state.json'; state.write_text('{"pending_interaction":"synthetic-retro"}')
        self.store.ingest(fixture())
        self.store.dispatch(self.now, send=lambda text: {'message_id': 'synthetic-1'})
        result = self.store.feedback('/ход 2,4', message_id='synthetic-in-1', now=self.now)
        self.assertEqual(result['action'], 'interested')
        self.store.feedback('/десятка 2099-01-02 выбран 2', message_id='synthetic-in-2', now=self.now)
        with self.assertRaises(ValueError): self.store.feedback('/десятка 2099-01-02 выполнено 2', message_id='synthetic-in-3', now=self.now)
        self.store.feedback('/десятка 2099-01-02 выполнено 2: Я сделал вымышленный пример.', message_id='synthetic-in-4', now=self.now)
        events = self.store.feedback_events()
        self.assertEqual([e['action'] for e in events], ['interested', 'chosen', 'completed'])
        self.assertEqual(events[-1]['evidence_kind'], 'explicit_self_report')
        self.assertEqual(self.store.feedback('/ход 2,4', message_id='synthetic-in-1', now=self.now), result)
        self.assertEqual(state.read_text(), '{"pending_interaction":"synthetic-retro"}')
        self.assertFalse((self.root / 'events.jsonl').exists())

    def test_bare_numbers_and_undelivered_or_old_implicit_selection_are_not_claimed(self):
        self.store.ingest(fixture())
        for text in ['2,4', '/ход 2']:
            with self.assertRaises(ValueError): self.store.feedback(text, message_id='synthetic-in', now=self.now)
        self.store.dispatch(self.now, send=lambda text: {'message_id': 'synthetic-1'})
        with self.assertRaises(ValueError): self.store.feedback('/ход 2', message_id='synthetic-in', now=self.now.replace(day=3))

    def test_actual_cli_feedback_preserves_pending_retro(self):
        import base64, os, subprocess, sys
        self.store.ingest(fixture())
        self.store.dispatch(self.now, send=lambda text: {'message_id': 'synthetic-delivery'})
        state = self.root / 'state.json'
        state.write_text('{"pending_interaction":"synthetic-retro"}')
        command = '/ход 2,4'
        script = PATH.with_name('personal_daily_system.py')
        result = subprocess.run([sys.executable, str(script), '--repo-root', str(self.root), '--data-dir', str(self.root), 'ten-feedback', '--text-base64', base64.b64encode(command.encode()).decode(), '--message-id', 'synthetic-cli-ten', '--at', self.now.isoformat()], text=True, capture_output=True, env={**os.environ, 'PDS_TIMEZONE': 'UTC', 'PDS_EVENING_TEN_ENABLED': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['action'], 'interested')
        self.assertEqual(state.read_text(), '{"pending_interaction":"synthetic-retro"}')
        self.assertFalse((self.root / 'events.jsonl').exists())

if __name__ == '__main__': unittest.main()
