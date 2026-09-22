from __future__ import annotations

import copy
import json
import stat
import tempfile
import unittest
from pathlib import Path

from test_install_and_verify import install, personalized_context, verify


class InstallationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.token = self.root / 'telegram.token'
        self.token.write_text('synthetic-fixture-token\n')
        self.token.chmod(stat.S_IRUSR | stat.S_IWUSR)
        self.context = self.root / 'context.json'
        self.context.write_text(json.dumps(personalized_context()))
        self.config = self.root / 'openclaw.json'
        self.options = install.InstallOptions(
            project_root=self.root / 'assistant', data_dir=self.root / 'private',
            context_json=self.context, summaries_dir=self.root / 'summaries',
            timezone='Etc/UTC', owner_telegram_id='10001', telegram_target='10001',
            openclaw_config=self.config, openclaw_sessions_dir=self.root / 'sessions',
            token_file=self.token, thread_cleanup_cutoff='2099-01-01T00:00:00Z',
        )

    def _installed(self):
        install.apply_install(self.options)
        (self.root / 'openclaw.json.backup-fixture').write_text('{}')
        return {
            'plugins': {'enabled': True, 'entries': {'personal-daily-transport': {
                'enabled': True, 'config': {'ownerTelegramId': '10001'},
            }}},
            'gateway': {'bind': 'loopback'},
        }

    def _verify(self, config):
        self.config.write_text(config if isinstance(config, str) else json.dumps(config))
        return verify.verify_installation(
            project_root=self.options.project_root, data_dir=self.options.data_dir,
            token_file=self.token, openclaw_config=self.config,
        )

    def test_existing_workspace_remains_untouched_even_after_prior_dry_run(self):
        plan = install.build_plan(self.options)
        self.options.project_root.mkdir()
        agents = self.options.project_root / 'AGENTS.md'
        agents.write_text('My existing user instructions\n')
        with self.assertRaisesRegex(ValueError, 'exist|fresh'):
            install.apply_install(self.options, plan)
        self.assertEqual(agents.read_text(), 'My existing user instructions\n')
        self.assertEqual(list(self.options.project_root.iterdir()), [agents])
        self.assertFalse(self.options.data_dir.exists())
        self.assertFalse(self.options.summaries_dir.exists())

    def test_empty_existing_directory_is_not_a_fresh_target(self):
        self.options.project_root.mkdir()
        with self.assertRaisesRegex(ValueError, 'exist|fresh'):
            install.build_plan(self.options)
        self.assertFalse(self.options.data_dir.exists())

    def test_dangling_destination_symlink_is_not_followed(self):
        other = self.root / 'other'
        self.options.project_root.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'exist|fresh|symlink'):
            install.apply_install(self.options)
        self.assertFalse(other.exists())
        self.assertFalse(self.options.data_dir.exists())

    def test_scheduled_messages_must_target_configured_owner(self):
        options = self.options._replace(telegram_target='10002')
        with self.assertRaisesRegex(ValueError, 'owner|match|same'):
            install.build_plan(options)
        self.assertFalse(options.project_root.exists())

    def test_valid_config_is_static_evidence_only(self):
        report = self._verify(self._installed())
        self.assertTrue(report['ok'], report)
        self.assertFalse(report['runtime_verified'])
        self.assertEqual(report['scope'], 'static-files-and-configuration')

    def test_disabled_or_blocked_plugin_cannot_pass_by_string_presence(self):
        good = self._installed()
        variants = []
        for mutation in ['entry_disabled', 'global_disabled', 'global_unknown', 'wrong_owner', 'denied', 'not_allowed']:
            config = copy.deepcopy(good)
            plugin = config['plugins']['entries']['personal-daily-transport']
            if mutation == 'entry_disabled': plugin['enabled'] = False
            elif mutation == 'global_disabled': config['plugins']['enabled'] = False
            elif mutation == 'global_unknown': config['plugins']['enabled'] = 'true'
            elif mutation == 'wrong_owner':
                plugin['config']['ownerTelegramId'] = '10002'
                config['unrelated_note'] = '10001'
            elif mutation == 'denied': config['plugins']['deny'] = ['personal-daily-transport']
            elif mutation == 'not_allowed': config['plugins']['allow'] = ['some-other-plugin']
            variants.append((mutation, config))
        for name, config in variants:
            with self.subTest(name=name):
                self.assertFalse(self._verify(config)['ok'])

    def test_public_unknown_or_missing_gateway_bind_cannot_pass(self):
        good = self._installed()
        for bind in ['::', '[::]', 'lan', 'auto', 'custom', '0.0.0.0', None]:
            config = copy.deepcopy(good)
            config['gateway'] = {} if bind is None else {'bind': bind}
            config['unrelated_note'] = 'loopback'
            with self.subTest(bind=bind):
                self.assertFalse(self._verify(config)['ok'])

    def test_json5_or_wrong_shape_config_is_unverified_not_success(self):
        self._installed()
        variants = [
            '// comment\n{"plugins": "personal-daily-transport 10001", "gateway": "loopback"}',
            '{invalid json',
            '[]',
            '{"plugins": [], "gateway": {"bind": "loopback"}}',
        ]
        for config in variants:
            with self.subTest(config=config):
                report = self._verify(config)
                self.assertFalse(report['ok'])
                self.assertFalse(report['runtime_verified'])

    def test_included_configuration_is_unverified_at_any_depth(self):
        good = self._installed()
        for nested in [False, True]:
            config = copy.deepcopy(good)
            target = config['plugins'] if nested else config
            target['$include'] = 'unread-config.json'
            with self.subTest(nested=nested):
                self.assertFalse(self._verify(config)['ok'])


if __name__ == '__main__':
    unittest.main()
