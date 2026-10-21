"""Pinned real IME archives; external pacman/GPG are replaced on macOS."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import test_termux_omarchy_tools as fixtures

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / 'build/deliverables/Omarchy-Hangul-input-packages-20261009-01'
EXPECTED = {'fcitx5': '5.1.23-1', 'fcitx5-gtk': '5.1.7-1',
            'fcitx5-hangul': '5.1.11-1', 'fcitx5-qt': '5.1.16-1',
            'libhangul': '0.2.0-1', 'xcb-imdkit': '1.0.9-1', 'yoga': '3.2.1-1'}


class KoreanPackageFixture:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.stage = self.root / 'packages'; self.stage.mkdir(mode=0o700)
        self.rows = json.loads((PACKAGES / 'ime-manifest.json').read_bytes())['packages']
        for name in ['ime-manifest.json', *[n for r in self.rows for n in (r['file'], r['file'] + '.sig')]]:
            shutil.copyfile(PACKAGES / name, self.stage / name); (self.stage / name).chmod(0o600)
        spec = importlib.util.spec_from_file_location('korean_package_worker', fixtures.SOURCE)
        self.worker = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.worker)
        (self.stage / 'pacman.conf').write_bytes(self.worker.CONFIG)
        (self.stage / 'pacman.conf').chmod(0o600)
        self.commands = fixtures.PackageCommands(self.stage, self.rows)

    def execute_input(self, **kwargs):
        try:
            return self.worker.execute(self.stage, korean_input=True, runner=self.commands, **kwargs)
        except TypeError as error:
            if "unexpected keyword argument 'korean_input'" in str(error):
                self.fail('The pinned Korean input package transaction is unavailable')
            raise


class KoreanPackageTests(KoreanPackageFixture, unittest.TestCase):
    def test_real_korean_packages_are_verified_without_any_package_writes(self):
        before = self.commands.db.read_bytes()
        result = self.execute_input()
        self.assertEqual(result['missing'], EXPECTED)
        self.assertEqual(result['signaturesVerified'], 7)
        self.assertFalse(result['packageWrites'])
        self.assertEqual(self.commands.db.read_bytes(), before)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_korean_payload_cannot_be_substituted_for_developer_tools(self):
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.worker.execute(self.stage, runner=self.commands)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_reviewed_input_transaction_preserves_all_prior_package_versions(self):
        audit = self.execute_input()
        with mock.patch.object(self.worker.os, 'getuid', return_value=0):
            result = self.execute_input(install=True, before=audit['beforeSHA256'])
        self.assertEqual(result['added'], EXPECTED)
        self.assertEqual(json.loads(self.commands.db.read_bytes()), {'original': '7-1', **EXPECTED})
        self.assertEqual(json.loads((self.stage / 'transaction.json').read_bytes())['phase'], 'INSTALLED')

    def test_input_signature_without_trust_prevents_transaction(self):
        self.commands.trusted = False; before = self.commands.db.read_bytes()
        with self.assertRaisesRegex(ValueError, 'tools-signature-untrusted'):
            self.execute_input()
        self.assertEqual(self.commands.db.read_bytes(), before)
        self.assertFalse((self.stage / 'transaction.json').exists())


class KoreanInstallerFixture(KoreanPackageFixture):
    def setUp(self):
        super().setUp()
        sys.path.insert(0, str(fixtures.SOURCE.parent)); self.addCleanup(sys.path.remove, str(fixtures.SOURCE.parent))
        spec = importlib.util.spec_from_file_location('korean_package_host', fixtures.SOURCE.with_name('omarchy_tools_install.py'))
        self.host = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.host)
        self.home, self.prefix = self.root / 'home', self.root / 'prefix'
        self.home.mkdir(mode=0o700); self.prefix.mkdir(mode=0o700)
        self.managed = self.home / '.local/share/loopy-omarchy'; self.managed.mkdir(parents=True, mode=0o700)
        self.rootfs = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy/rootfs'
        self.rootfs.mkdir(parents=True, mode=0o700)
        patch = mock.patch.multiple(self.host.base, HOST_FILES={}, FILE_SHA={})
        patch.start(); self.addCleanup(patch.stop)
        identity = self.host.base.identity
        record = {'schema': 1, 'phase': 'INSTALLED', 'uid': os.getuid(), 'root': identity(self.managed.stat()),
                  'home': str(self.home), 'prefix': str(self.prefix), 'container': 'loopy-omarchy',
                  'bundle_sha256': self.host.base.OUTER_SHA, 'container_identity': identity(self.rootfs.parent.stat()),
                  'rootfs_identity': identity(self.rootfs.stat()), 'managed_files': {}}
        (self.managed / 'install.json').write_text(json.dumps(record)); (self.managed / 'install.json').chmod(0o600)
        for name in ('etc/pacman.conf', 'var/lib/pacman/sync/core.db', 'var/lib/pacman/sync/extra.db'):
            path = self.rootfs / name; path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_bytes(b'public existing package database'); path.chmod(0o600)
        (self.managed / 'runtime-state.json').write_text(json.dumps({'phase': 'ready'}))
        (self.managed / 'runtime-state.json').chmod(0o600)
        self.already_installed = False
        self.guest_commands = {}
        def transport(argv, **kwargs):
            self.assertEqual(argv[1:7], ['login', '--isolated', '--user', 'root', 'loopy-omarchy', '--'])
            guest_stage = self.rootfs / argv[10].lstrip('/')
            commands = self.guest_commands.get(str(guest_stage))
            if commands is None:
                commands = fixtures.PackageCommands(guest_stage, self.rows)
                self.guest_commands[str(guest_stage)] = commands
                if self.already_installed: commands.db.write_text(json.dumps({'original': '7-1', **EXPECTED}))
            with mock.patch.object(self.host.worker.os, 'getuid', return_value=0):
                return json.dumps(self.host.worker.execute(guest_stage,
                    korean_input='--korean-input' in argv, install='--install' in argv,
                    before=argv[argv.index('--before') + 1] if '--before' in argv else None,
                    runner=commands))
        patch = mock.patch.object(self.host, 'run_bounded', side_effect=transport)
        patch.start(); self.addCleanup(patch.stop)
        self.native_transport = transport

    def install_input(self):
        try:
            return self.host.install(self.stage, self.home, self.prefix, korean_input=True)
        except TypeError as error:
            if "unexpected keyword argument 'korean_input'" in str(error):
                self.fail('The managed Korean input package installer is unavailable')
            raise


class KoreanInstallerTests(KoreanInstallerFixture, unittest.TestCase):
    def test_active_desktop_prevents_input_package_changes_in_separate_journal(self):
        with self.assertRaisesRegex(ValueError, 'tools-runtime-active'):
            self.install_input()
        row = json.loads((self.managed / 'korean-input-install.json').read_bytes())
        self.assertEqual(row['phase'], 'STAGED')
        self.assertFalse((self.managed / 'tools-install.json').exists())
        self.assertFalse((self.rootfs / row['stage'] / 'transaction.json').exists())

    def test_existing_input_packages_are_adopted_without_developer_journal_changes(self):
        self.already_installed = True
        result = self.install_input()
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertFalse(result['packageWrites'])
        self.assertEqual(result['packages'], EXPECTED)
        self.assertFalse((self.managed / 'tools-install.json').exists())
        before = (self.managed / 'korean-input-install.json').read_bytes()
        self.install_input()
        self.assertEqual((self.managed / 'korean-input-install.json').read_bytes(), before)


if __name__ == '__main__': unittest.main()
