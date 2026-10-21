"""Actual input payload, target files, signed-package boundary and journals."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

import test_termux_omarchy_korean_packages as fixtures

SOURCE = fixtures.ROOT / 'termux/omarchy_input_install.py'
CONFIG = fixtures.ROOT / 'build/deliverables/Omarchy-Hangul-input-config-20261009-01'
BEFORE = fixtures.ROOT / 'build/diagnostics/termux-omarchy-input-readonly-device-20261009-03/receipt.json'
AUTOSTART = 'home/omarchy/.config/hypr/autostart.lua'


class KoreanInputTests(fixtures.KoreanInstallerFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(SOURCE.is_file(), 'Combined signed input packages and guarded configuration installer is missing')
        spec = importlib.util.spec_from_file_location('combined_input_install', SOURCE)
        self.input = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.input)
        patch = mock.patch.object(self.input.packages, 'run_bounded', side_effect=self.native_transport)
        patch.start(); self.addCleanup(patch.stop)
        self.payload = CONFIG / 'input-config-payload.tar'
        self.manifest = CONFIG / 'input-config-manifest.json'
        self.old = next(r['source'].encode() for r in json.loads(BEFORE.read_bytes())['inputConfigFiles']
                        if r['relative'] == '.config/hypr/autostart.lua')
        path = self.rootfs / AUTOSTART; path.parent.mkdir(parents=True, mode=0o700)
        path.write_bytes(self.old); path.chmod(0o644)
        self.already_installed = True

    def stopped(self):
        (self.managed / 'runtime-state.json').write_text(json.dumps({'phase': 'stopped', 'terminationConfirmed': True}))

    def install(self):
        return self.input.install(self.stage, self.payload, self.manifest, self.home, self.prefix)

    def test_active_desktop_refuses_config_and_packages_before_any_install_journal(self):
        with self.assertRaisesRegex(ValueError, 'guest-runtime-active'): self.install()
        self.assertEqual((self.rootfs / AUTOSTART).read_bytes(), self.old)
        self.assertFalse((self.managed / 'input-config-install.json').exists())
        self.assertFalse((self.managed / 'korean-input-install.json').exists())

    def test_existing_personal_gtk_file_is_preserved_before_package_staging(self):
        self.stopped(); path = self.rootfs / 'home/omarchy/.config/gtk-3.0/settings.ini'
        path.parent.mkdir(mode=0o700); path.write_bytes(b'[Settings]\ngtk-font-name=Personal 14\n'); path.chmod(0o644)
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'guest-user-file-changed'): self.install()
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.managed / 'korean-input-install.json').exists())

    def test_input_files_are_installed_with_exact_autostart_backup_and_base_preserved(self):
        self.stopped(); base_bytes = (self.managed / 'install.json').read_bytes()
        value = self.install()
        self.assertFalse(value['physicalKoreanInputVerified'])
        config = value['config']
        self.assertEqual(config['phase'], 'INSTALLED')
        self.assertEqual(config['filesVerified'], 5)
        change = next(r for r in config['changes'] if r['path'] == AUTOSTART)
        backup = self.managed / config['backupDirectory'] / change['backup']
        self.assertEqual(backup.read_bytes(), self.old)
        self.assertEqual((self.managed / 'install.json').read_bytes(), base_bytes)
        self.assertFalse((self.managed / 'guest-install.json').exists())
        self.assertFalse((self.managed / 'tools-install.json').exists())

    def test_repeated_install_preserves_first_backups_and_journals(self):
        self.stopped(); first = self.install()
        journal = (self.managed / 'input-config-install.json').read_bytes()
        second = self.install()
        self.assertEqual(first['config']['backupDirectory'], second['config']['backupDirectory'])
        self.assertEqual((self.managed / 'input-config-install.json').read_bytes(), journal)

    def test_reviewed_input_install_adds_only_seven_missing_packages(self):
        self.stopped(); self.already_installed = False
        result = self.install()
        self.assertTrue(result['packages']['packageWrites'])
        self.assertEqual(result['packages']['packages'], fixtures.EXPECTED)
        for commands in self.guest_commands.values():
            self.assertEqual(json.loads(commands.db.read_bytes()), {'original': '7-1', **fixtures.EXPECTED})
        self.assertEqual(result['config']['phase'], 'INSTALLED')


if __name__ == '__main__': unittest.main()
