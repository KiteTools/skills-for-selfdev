from datetime import datetime, timedelta
import unittest
from zoneinfo import ZoneInfo
import test_personal_daily_system as base

class ExplicitActivityTests(unittest.TestCase):
    setUp = base.PortablePersonalDailyRuntimeTests.setUp
    tearDown = base.PortablePersonalDailyRuntimeTests.tearDown

    def test_start_end_are_only_user_reports_not_task_completion(self):
        now = datetime(2099, 1, 2, 14, tzinfo=ZoneInfo('UTC'))
        original = self.context_path.read_bytes()
        fn = self.module.record_activity_command
        first = fn(self.service.store, '/занятие начало Вымышленное чтение', message_id='synthetic-start', now=now)
        self.assertEqual(first['action'], 'started')
        repeat = fn(self.service.store, '/занятие начало Вымышленное чтение', message_id='synthetic-start', now=now)
        self.assertEqual(first, repeat)
        finish = fn(self.service.store, '/занятие конец Прочитал один пример, вопрос остался.', message_id='synthetic-end', now=now + timedelta(minutes=12))
        self.assertEqual(finish['action'], 'finished')
        events = self.service.store.load_materialized_events()
        self.assertEqual([e['type'] for e in events], ['focus_started', 'focus_finished'])
        self.assertEqual(events[-1]['self_report']['evidence_kind'], 'explicit_self_report')
        self.assertEqual(original, self.context_path.read_bytes())
        self.assertFalse(self.service.state_path.exists())

    def test_postpone_skip_and_missing_start_are_not_completed_by_timer(self):
        fn = self.module.record_activity_command
        now = datetime(2099, 1, 2, 14, tzinfo=ZoneInfo('UTC'))
        with self.assertRaises(self.module.PersonalEventError): fn(self.service.store, '/занятие конец Готово', message_id='synthetic-invalid', now=now)
        fn(self.service.store, '/занятие начало Вымышленная практика', message_id='synthetic-1', now=now)
        with self.assertRaises(self.module.PersonalEventError): fn(self.service.store, '/занятие начало Другое', message_id='synthetic-2', now=now)
        result = fn(self.service.store, '/занятие отложить Вернусь позже', message_id='synthetic-3', now=now + timedelta(days=1))
        self.assertEqual(result['action'], 'postponed')
        fn(self.service.store, '/занятие начало Другой пример', message_id='synthetic-4', now=now + timedelta(days=1))
        self.assertEqual(fn(self.service.store, '/занятие пропустить Не подходит', message_id='synthetic-5', now=now + timedelta(days=1))['action'], 'skipped')
        self.assertFalse(any(e['type'] in {'success', 'focus_finished'} for e in self.service.store.load_materialized_events()))

    def test_actual_cli_routes_explicit_activity_without_pending_state(self):
        import base64, json, os, subprocess, sys
        result = subprocess.run([sys.executable, str(base.SCRIPT_PATH), '--repo-root', str(self.root), '--data-dir', str(self.data_dir), 'activity-command', '--text-base64', base64.b64encode('/занятие начало Синтетическая проверка'.encode()).decode(), '--message-id', 'synthetic-cli', '--at', '2099-01-02T14:00:00+00:00'], text=True, capture_output=True, env={**os.environ, 'PDS_TIMEZONE': 'UTC'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['action'], 'started')
        self.assertFalse(self.service.state_path.exists())
