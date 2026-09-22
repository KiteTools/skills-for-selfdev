import importlib.util
import json
from pathlib import Path
import unittest
import test_install_safety as safety

ROOT = Path(__file__).resolve().parents[1]

class UpgradeAndTenTests(unittest.TestCase):
    setUp = safety.InstallationSafetyTests.setUp

    def test_ten_is_opt_in_and_retro_moves_to_2210_only_when_enabled(self):
        install = safety.install
        default = install.build_plan(self.options)
        self.assertEqual(len(default['schedules']), 7)
        options = self.options._replace(evening_ten_enabled=True)
        enabled = install.build_plan(options)
        schedules = {s['declaration_key']: s for s in enabled['schedules']}
        self.assertNotIn('personal-daily-evening-2200', schedules)
        self.assertEqual(schedules['personal-daily-ten-2200']['cron'], '0 22 * * *')
        self.assertEqual(schedules['personal-daily-evening-2210']['cron'], '10 22 * * *')
        self.assertTrue(enabled['plugin']['config']['eveningTenEnabled'])

    def test_upgrade_uses_fresh_destination_and_preserves_context_and_all_existing_data(self):
        safety.install.apply_install(self.options)
        marker = self.options.data_dir / 'events.jsonl'
        marker.write_text('synthetic-existing-journal\n')
        state = self.options.data_dir / 'state.json'; state.write_text('{"synthetic":"pending"}\n')
        old_context = (self.options.project_root / 'context/active_context.json').read_bytes()
        spec = importlib.util.spec_from_file_location('portable_upgrade', ROOT / 'scripts/upgrade.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        plan = module.upgrade(self.options.project_root, self.root / 'assistant-v02', self.config, apply=False, evening_ten_enabled=True)
        self.assertFalse((self.root / 'assistant-v02').exists())
        module.upgrade(self.options.project_root, self.root / 'assistant-v02', self.config, apply=True, evening_ten_enabled=True)
        self.assertEqual(marker.read_text(), 'synthetic-existing-journal\n')
        self.assertEqual(state.read_text(), '{"synthetic":"pending"}\n')
        self.assertEqual((self.root / 'assistant-v02/context/active_context.json').read_bytes(), old_context)
        self.assertEqual((self.options.project_root / 'context/active_context.json').read_bytes(), old_context)
        with self.assertRaises(ValueError): module.upgrade(self.options.project_root, self.root / 'assistant-v02', self.config, apply=True)

    def test_data_symlink_is_rejected_before_creating_new_workspace_or_changing_target(self):
        self.options.data_dir.mkdir()
        target = self.root / 'outside-state'
        link = self.options.data_dir / 'events.jsonl'
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            safety.install.apply_install(self.options)
        self.assertFalse(self.options.project_root.exists())
        self.assertFalse(target.exists())
        link.unlink(); target.write_text('synthetic'); target.chmod(0o644)
        (self.options.data_dir / 'state.json').symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            safety.install.apply_install(self.options)
        self.assertEqual(target.stat().st_mode & 0o777, 0o644)
