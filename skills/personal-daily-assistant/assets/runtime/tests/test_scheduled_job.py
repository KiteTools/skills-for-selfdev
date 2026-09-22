"""Scheduling boundary tests: use mocked commands, never local history or Telegram."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import unittest
from unittest import mock

RUNTIME = Path(__file__).resolve().parents[1]


def load_scheduler():
    spec = importlib.util.spec_from_file_location('portable_schedule', RUNTIME / 'scripts' / 'scheduled_job.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ActivityOptInTests(unittest.TestCase):
    def setUp(self):
        self.module = load_scheduler()
        self.env = {'PDS_TELEGRAM_TARGET': '123', 'PDS_TIMEZONE': 'UTC'}

    def test_default_evening_does_not_scan_or_attach_activity(self):
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(self.module, '_run') as run:
            self.module.run_job('evening', dry_run=True)
        self.assertEqual(run.call_count, 1)
        command = run.call_args.args[0]
        self.assertIn('evening', command)
        self.assertIn('--dry-run', command)
        self.assertNotIn('--codex-activity', command)
        self.assertFalse(any('build_codex_activity_context' in arg for arg in command))

    def test_source_path_alone_does_not_enable_activity(self):
        self.env['PDS_CODEX_ACTIVITY_SOURCE_DIR'] = '/tmp/selected-fictional-exports'
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(self.module, '_run') as run:
            self.module.run_job('evening', dry_run=True)
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('--codex-activity', run.call_args.args[0])

    def test_opt_in_requires_explicit_absolute_source(self):
        self.env['PDS_INCLUDE_CODEX_ACTIVITY'] = '1'
        for source in ['', 'relative-exports']:
            self.env['PDS_CODEX_ACTIVITY_SOURCE_DIR'] = source
            with self.subTest(source=source), mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(self.module, '_run') as run:
                with self.assertRaisesRegex(RuntimeError, 'absolute.*PDS_CODEX_ACTIVITY_SOURCE_DIR|PDS_CODEX_ACTIVITY_SOURCE_DIR.*absolute'):
                    self.module.run_job('evening', dry_run=True)
                run.assert_not_called()

    def test_opt_in_scans_only_configured_source_and_attaches_output(self):
        self.env.update(PDS_INCLUDE_CODEX_ACTIVITY='1', PDS_CODEX_ACTIVITY_SOURCE_DIR='/tmp/selected-fictional-exports')
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(self.module, '_run') as run:
            self.module.run_job('evening', dry_run=True)
        self.assertEqual(run.call_count, 2)
        build, dispatch = [call.args[0] for call in run.call_args_list]
        self.assertIn('build_codex_activity_context.py', build[1])
        self.assertEqual(build[build.index('--codex-home') + 1], '/tmp/selected-fictional-exports')
        self.assertEqual(dispatch[dispatch.index('--codex-activity') + 1], build[build.index('--output') + 1])
        self.assertIn('--dry-run', dispatch)


if __name__ == '__main__': unittest.main()
