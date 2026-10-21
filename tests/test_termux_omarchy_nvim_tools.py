"""Real pinned archives/state; only Android pacman/GPG/PRoot are substituted."""
import fcntl
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
SOURCE = ROOT / 'termux/omarchy_nvim_tools_guest.py'
PACKAGES = ROOT / 'build/deliverables/Omarchy-Neovim-tools-packages-20261009-01'
EXPECTED = {'lazygit': '0.66.0-1', 'lua-luarocks': '3.13.0-5', 'lua51': '5.1.5-13',
            'luarocks': '3.13.0-5', 'tree-sitter-cli': '0.26.9-1', 'unzip': '6.0-23', 'zip': '3.0-14'}


class PayloadFixture:
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'separate Neovim package worker is missing')
        spec = importlib.util.spec_from_file_location('tested_nvim_guest', SOURCE)
        self.worker = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.worker)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.stage = self.root / 'payload'; self.stage.mkdir(mode=0o700)
        self.rows = json.loads((PACKAGES / 'nvim-tools-manifest.json').read_bytes())['packages']
        for name in ['nvim-tools-manifest.json', *[n for r in self.rows for n in (r['file'], r['file'] + '.sig')]]:
            shutil.copyfile(PACKAGES / name, self.stage / name); (self.stage / name).chmod(0o600)
        (self.stage / 'pacman.conf').write_bytes(self.worker.CONFIG)
        (self.stage / 'pacman.conf').chmod(0o600)
        self.commands = fixtures.PackageCommands(self.stage, self.rows)

    def execute(self, **kwargs):
        return self.worker.execute(self.stage, runner=self.commands, **kwargs)

    def install_reviewed(self, digest):
        with mock.patch.object(self.worker.os, 'getuid', return_value=0):
            return self.execute(install=True, before=digest)


class NeovimGuestTests(PayloadFixture, unittest.TestCase):
    def test_real_seven_archives_are_readonly_verified(self):
        before = self.commands.db.read_bytes()
        row = self.execute()
        self.assertEqual(row['missing'], EXPECTED)
        self.assertEqual(row['signaturesVerified'], 7)
        self.assertFalse(row['packageWrites'])
        self.assertEqual(self.commands.db.read_bytes(), before)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_install_adds_exact_seven_preserving_all_previous_versions(self):
        self.commands.db.write_text(json.dumps({'original': '7-1', 'fcitx5': '5.1.23-1', 'neovim': '0.11.4-1'}))
        prior = json.loads(self.commands.db.read_bytes())
        row = self.install_reviewed(self.execute()['beforeSHA256'])
        self.assertEqual(row['added'], EXPECTED)
        self.assertEqual(json.loads(self.commands.db.read_bytes()), dict(prior, **EXPECTED))
        self.assertEqual(json.loads((self.stage / 'transaction.json').read_bytes())['phase'], 'INSTALLED')

    def test_untrusted_or_revoked_signature_prevents_package_changes(self):
        original = self.commands; before = original.db.read_bytes()
        for status in ('TRUST_UNDEFINED', 'REVKEYSIG'):
            def commands(argv):
                result = original(argv)
                if argv[0] == '/usr/bin/gpg':
                    result.stdout = result.stdout.replace('TRUST_FULLY', status)
                return result
            self.commands = commands
            with self.assertRaisesRegex(ValueError, 'nvim-tools-signature-untrusted'): self.execute()
            self.assertEqual(original.db.read_bytes(), before)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_existing_different_version_is_refused_without_changes(self):
        self.commands.db.write_text(json.dumps({'original': '7-1', 'lazygit': '0.67.0-1'}))
        before = self.commands.db.read_bytes()
        with self.assertRaisesRegex(ValueError, 'nvim-tools-existing-version-different'): self.execute()
        self.assertEqual(self.commands.db.read_bytes(), before)

    def test_extra_dependency_plan_and_stale_review_are_refused(self):
        digest = self.execute()['beforeSHA256']; before = self.commands.db.read_bytes()
        self.commands.extra_plan = True
        with self.assertRaisesRegex(ValueError, 'nvim-tools-plan-different'): self.install_reviewed(digest)
        self.assertEqual(self.commands.db.read_bytes(), before)
        self.commands.extra_plan = False
        self.commands.db.write_text(json.dumps({'original': '8-1'})); before = self.commands.db.read_bytes()
        with self.assertRaisesRegex(ValueError, 'nvim-tools-package-review-changed'): self.install_reviewed(digest)
        self.assertEqual(self.commands.db.read_bytes(), before)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_tampered_archive_signature_or_manifest_is_refused(self):
        for name in (self.rows[0]['file'], self.rows[0]['file'] + '.sig', 'nvim-tools-manifest.json'):
            path = self.stage / name; before = path.read_bytes(); path.write_bytes(before + b'changed')
            with self.assertRaises(ValueError): self.execute()
            path.write_bytes(before)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_archive_symlink_is_refused(self):
        path = self.stage / self.rows[0]['file']; external = self.root / 'external'
        path.rename(external); path.symlink_to(external)
        with self.assertRaises((OSError, ValueError)): self.execute()
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_metadata_mismatch_is_refused(self):
        original = self.commands
        def commands(argv):
            result = original(argv)
            if argv[1] == '-Qp': result.stdout = 'wrong 9-1\n'
            return result
        self.commands = commands
        with self.assertRaisesRegex(ValueError, 'nvim-tools-package-metadata-different'): self.execute()
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_archive_change_during_plan_is_refused_before_transaction(self):
        digest = self.execute()['beforeSHA256']; original = self.commands; before = original.db.read_bytes()
        def commands(argv):
            result = original(argv)
            if '-Up' in argv:
                path = self.stage / self.rows[0]['file']; path.write_bytes(path.read_bytes() + b'changed')
            return result
        self.commands = commands
        with self.assertRaises(ValueError): self.install_reviewed(digest)
        self.assertEqual(original.db.read_bytes(), before)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_interrupted_transaction_is_preserved_even_if_packages_now_present(self):
        digest = self.execute()['beforeSHA256']; self.commands.fail_transaction = True
        with self.assertRaisesRegex(ValueError, 'nvim-tools-transaction-uncertain'): self.install_reviewed(digest)
        path = self.stage / 'transaction.json'; before = path.read_bytes()
        self.assertEqual(json.loads(before)['phase'], 'INSTALL_UNKNOWN')
        self.commands.db.write_text(json.dumps({'original': '7-1', **EXPECTED}))
        with self.assertRaisesRegex(ValueError, 'nvim-tools-transaction-uncertain'): self.execute()
        self.assertEqual(path.read_bytes(), before)

    def test_completed_install_is_readonly_idempotent(self):
        self.install_reviewed(self.execute()['beforeSHA256'])
        path = self.stage / 'transaction.json'; before = path.read_bytes(); timestamp = path.stat().st_mtime_ns
        row = self.execute()
        self.assertFalse(row['packageWrites']); self.assertFalse(row['missing'])
        self.assertEqual(path.read_bytes(), before); self.assertEqual(path.stat().st_mtime_ns, timestamp)

    def test_unexpected_previous_version_change_is_retained_as_uncertain(self):
        digest = self.execute()['beforeSHA256']; original = self.commands
        def commands(argv):
            result = original(argv)
            if '-U' in argv:
                values = json.loads(original.db.read_bytes()); values['original'] = '8-1'
                original.db.write_text(json.dumps(values))
            return result
        self.commands = commands
        with self.assertRaisesRegex(ValueError, 'nvim-tools-transaction-uncertain'): self.install_reviewed(digest)
        self.assertEqual(json.loads((self.stage / 'transaction.json').read_bytes())['phase'], 'INSTALL_UNKNOWN')
        self.assertEqual(json.loads(original.db.read_bytes())['original'], '8-1')


class InstallerFixture(PayloadFixture):
    def setUp(self):
        super().setUp()
        source = SOURCE.with_name('omarchy_nvim_tools_install.py')
        self.assertTrue(source.is_file(), 'separate Neovim native installer is missing')
        sys.path.insert(0, str(SOURCE.parent)); self.addCleanup(sys.path.remove, str(SOURCE.parent))
        spec = importlib.util.spec_from_file_location('tested_nvim_install', source)
        self.host = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.host)
        self.home, self.prefix = self.root / 'home', self.root / 'prefix'
        self.home.mkdir(mode=0o700); self.prefix.mkdir(mode=0o700)
        self.managed = self.home / '.local/share/loopy-omarchy'; self.managed.mkdir(parents=True, mode=0o700)
        self.rootfs = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy/rootfs'
        self.rootfs.mkdir(parents=True, mode=0o700)
        patch = mock.patch.multiple(self.host.base, HOST_FILES={}, FILE_SHA={})
        patch.start(); self.addCleanup(patch.stop)
        identity = self.host.base.identity
        row = {'schema': 1, 'phase': 'INSTALLED', 'uid': os.getuid(), 'root': identity(self.managed.stat()),
               'home': str(self.home), 'prefix': str(self.prefix), 'container': 'loopy-omarchy',
               'bundle_sha256': self.host.base.OUTER_SHA, 'container_identity': identity(self.rootfs.parent.stat()),
               'rootfs_identity': identity(self.rootfs.stat()), 'managed_files': {}}
        self.write(self.managed / 'install.json', json.dumps(row).encode())
        self.preserved = []
        for name in ('etc/pacman.conf', 'var/lib/pacman/sync/core.db', 'var/lib/pacman/sync/extra.db',
                     'home/omarchy/.config/nvim/init.lua', 'home/omarchy/.local/share/nvim/lazy/personal.lua'):
            path = self.rootfs / name; self.write(path, b'personal existing bytes'); self.preserved.append(path)
        for name in ('tools-install.json', 'korean-input-install.json'):
            path = self.managed / name; self.write(path, b'{"existing":"unmodified"}'); self.preserved.append(path)
        self.state = {'schema': 1, 'uid': os.getuid(), 'root': identity(self.managed.stat()),
                      'phase': 'stopped', 'terminationConfirmed': True, 'prootExitKillRequested': True}
        self.write(self.managed / 'runtime-state.json', json.dumps(self.state).encode())
        source = ROOT / 'build/diagnostics/termux-omarchy-proot-private-runpath-build-20261009-01/arm64-v8a'
        target = self.managed / 'proot-guard'; target.mkdir(mode=0o700)
        for name, mode in self.host.guard.MODES.items():
            shutil.copyfile(source / name, target / name); (target / name).chmod(mode)
        self.write(self.managed / 'proot-guard.json', json.dumps({'schema': 1, 'phase': 'INSTALLED',
            'uid': os.getuid(), 'root': identity(self.managed.stat()), 'directory': identity(target.stat()),
            'files': self.host.guard.FILES}).encode())
        self.before = {str(p): (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns) for p in self.preserved}
        self.already_installed, self.interrupt = False, False
        self.guest_commands, self.calls = {}, []
        def transport(argv, **kwargs):
            self.calls.append((argv, kwargs['env']))
            self.assertEqual(argv[1:5], ['login', '--isolated', '--user', 'root'])
            split = argv.index('--'); self.assertEqual(argv[split - 1], 'loopy-omarchy')
            self.assertEqual(argv[split + 1:split + 3], ['/usr/bin/python3', '-c'])
            stage = self.rootfs / argv[split + 4].lstrip('/')
            commands = self.guest_commands.get(str(stage))
            if commands is None:
                commands = fixtures.PackageCommands(stage, self.rows); self.guest_commands[str(stage)] = commands
                if self.already_installed: commands.db.write_text(json.dumps({'original': '7-1', **EXPECTED}))
            commands.fail_transaction = self.interrupt
            with mock.patch.object(self.host.worker.os, 'getuid', return_value=0):
                return json.dumps(self.host.worker.execute(stage, runner=commands, install='--install' in argv,
                    before=argv[argv.index('--before') + 1] if '--before' in argv else None))
        patch = mock.patch.object(self.host, 'run_bounded', side_effect=transport)
        patch.start(); self.addCleanup(patch.stop)

    def write(self, path, data):
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        path.write_bytes(data); path.chmod(0o600)

    def install(self):
        return self.host.install(self.stage, self.home, self.prefix)

    def assert_preserved(self):
        after = {str(p): (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns) for p in self.preserved}
        self.assertEqual(after, self.before)


class NeovimInstallerTests(InstallerFixture, unittest.TestCase):
    def test_install_uses_separate_journal_and_preserves_personal_and_component_files(self):
        row = self.install()
        self.assertEqual(row['phase'], 'INSTALLED'); self.assertEqual(row['packages'], EXPECTED)
        self.assertTrue(row['packageWrites']); self.assertTrue(row['stage'].startswith('opt/loopy-nvim-tools-'))
        self.assert_preserved()
        self.assertEqual((self.managed / 'nvim-tools-install.json').stat().st_mode & 0o777, 0o600)
        before = (self.managed / 'nvim-tools-install.json').stat().st_mtime_ns
        count = len(self.calls)
        self.install()
        self.assertEqual((self.managed / 'nvim-tools-install.json').stat().st_mtime_ns, before)
        self.assertEqual(len(self.calls), count + 1)
        self.assertNotIn('--install', self.calls[-1][0]); self.assert_preserved()

    def test_running_guest_prevents_package_changes(self):
        self.write(self.managed / 'runtime-state.json', json.dumps(dict(self.state, phase='ready')).encode())
        with self.assertRaisesRegex(ValueError, 'nvim-tools-runtime-active'): self.install()
        self.assertFalse((self.managed / 'nvim-tools-install.json').exists())
        self.assertFalse(self.calls); self.assert_preserved()

    def test_existing_exact_packages_are_adopted_readonly(self):
        self.already_installed = True
        row = self.install()
        self.assertFalse(row['packageWrites']); self.assertEqual(row['phase'], 'INSTALLED')
        self.assert_preserved()

    def test_interrupted_transaction_is_preserved_and_retry_refused(self):
        self.interrupt = True
        with self.assertRaisesRegex(ValueError, 'nvim-tools-install-uncertain'): self.install()
        path = self.managed / 'nvim-tools-install.json'; before = path.read_bytes()
        self.assertEqual(json.loads(before)['phase'], 'INSTALL_UNKNOWN')
        calls = len(self.calls)
        with self.assertRaisesRegex(ValueError, 'nvim-tools-install-uncertain'): self.install()
        self.assertEqual(path.read_bytes(), before); self.assertEqual(len(self.calls), calls)
        self.assert_preserved()

    def test_changed_source_rejected_before_journal_or_guest(self):
        path = self.stage / self.rows[0]['file']; path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaises(ValueError): self.install()
        self.assertFalse((self.managed / 'nvim-tools-install.json').exists()); self.assertFalse(self.calls)
        self.assert_preserved()

    def test_busy_runtime_lock_releases_install_lock(self):
        lock = self.managed / 'runtime-control.lock'; self.write(lock, b'')
        with lock.open('rb') as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises((BlockingIOError, ValueError)): self.install()
            with (self.managed / 'install.lock').open('rb') as released:
                fcntl.flock(released, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertFalse(self.calls); self.assertFalse((self.managed / 'nvim-tools-install.json').exists())

    def test_partial_guard_is_refused_before_stage_or_guest(self):
        (self.managed / 'proot-guard.json').unlink()
        with self.assertRaisesRegex(ValueError, 'proot-guard-integrity'): self.install()
        self.assertFalse(self.calls); self.assertFalse((self.managed / 'nvim-tools-install.json').exists())

    def test_verified_guard_and_isolated_tmpdir_are_forwarded(self):
        target = self.managed / 'proot-guard'
        self.install()
        for args, env in self.calls:
            self.assertEqual(env['PD_PROOT_BIN'], str(target / 'proot'))
            self.assertIn('PROOT_LOADER=' + str(target / 'loader'), args)
            self.assertIn('PROOT_EXITKILL=1', args); self.assertIn('TMPDIR=/tmp', args)
            self.assertEqual(env['TMPDIR'], str(self.prefix / 'tmp'))
        self.assert_preserved()

    def test_wrong_root_identity_is_refused_before_staging(self):
        path = self.managed / 'install.json'; row = json.loads(path.read_bytes()); row['root'][1] += 1
        self.write(path, json.dumps(row).encode())
        with self.assertRaises(ValueError): self.install()
        self.assertFalse(self.calls); self.assertFalse((self.managed / 'nvim-tools-install.json').exists())
        self.assert_preserved()

    def test_unknown_native_journal_bytes_are_preserved(self):
        path = self.managed / 'nvim-tools-install.json'; self.write(path, b'{"phase":"INSTALL_UNKNOWN"}')
        before = path.read_bytes()
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(path.read_bytes(), before); self.assertFalse(self.calls); self.assert_preserved()

    def test_completed_stage_replacement_is_refused(self):
        row = self.install(); stage = self.rootfs / row['stage']; stage.rename(stage.with_name(stage.name + '-kept'))
        stage.mkdir(mode=0o700); calls = len(self.calls)
        before = (self.managed / 'nvim-tools-install.json').read_bytes()
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(len(self.calls), calls)
        self.assertEqual((self.managed / 'nvim-tools-install.json').read_bytes(), before); self.assert_preserved()

    def test_missing_runtime_state_is_refused_before_staging(self):
        (self.managed / 'runtime-state.json').unlink()
        with self.assertRaisesRegex(ValueError, 'nvim-tools-runtime-state'): self.install()
        self.assertFalse(self.calls); self.assertFalse((self.managed / 'nvim-tools-install.json').exists())

    def test_wrong_schema_uid_root_or_guard_state_is_refused(self):
        for values in ({'schema': 2}, {'uid': os.getuid() + 1}, {'root': [0, 0, 0]},
                       {'terminationConfirmed': False}, {'prootExitKillRequested': False}):
            with self.subTest(values=values):
                self.write(self.managed / 'runtime-state.json', json.dumps(dict(self.state, **values)).encode())
                with self.assertRaises(ValueError): self.install()
                self.assertFalse(self.calls); self.assertFalse((self.managed / 'nvim-tools-install.json').exists())
        self.assert_preserved()

    def test_missing_guard_never_falls_back_to_global_proot(self):
        (self.managed / 'proot-guard').rename(self.managed / 'proot-guard-kept')
        (self.managed / 'proot-guard.json').rename(self.managed / 'proot-guard-kept.json')
        with self.assertRaisesRegex(ValueError, 'nvim-tools-proot-required'): self.install()
        self.assertFalse(self.calls); self.assertFalse((self.managed / 'nvim-tools-install.json').exists())

    def test_installed_component_refuses_guard_removal(self):
        self.install(); calls = len(self.calls)
        path = self.managed / 'nvim-tools-install.json'; before = path.read_bytes()
        (self.managed / 'proot-guard').rename(self.managed / 'proot-guard-kept')
        (self.managed / 'proot-guard.json').rename(self.managed / 'proot-guard-kept.json')
        with self.assertRaisesRegex(ValueError, 'nvim-tools-proot-required'): self.install()
        self.assertEqual(len(self.calls), calls); self.assertEqual(path.read_bytes(), before)

    def test_runtime_changed_after_preflight_prevents_transaction(self):
        original = self.host.run_bounded.side_effect
        def transport(argv, **kwargs):
            result = original(argv, **kwargs)
            self.write(self.managed / 'runtime-state.json', json.dumps(dict(self.state, phase='ready')).encode())
            return result
        self.host.run_bounded.side_effect = transport
        with self.assertRaisesRegex(ValueError, 'nvim-tools-runtime-active'): self.install()
        row = json.loads((self.managed / 'nvim-tools-install.json').read_bytes())
        self.assertEqual(row['phase'], 'STAGED')
        self.assertFalse((self.rootfs / row['stage'] / 'transaction.json').exists())
        self.assertEqual(len(self.calls), 1); self.assertNotIn('--install', self.calls[0][0])

    def test_guard_removed_after_preflight_prevents_transaction(self):
        original = self.host.run_bounded.side_effect
        def transport(argv, **kwargs):
            result = original(argv, **kwargs)
            (self.managed / 'proot-guard').rename(self.managed / 'proot-guard-kept')
            (self.managed / 'proot-guard.json').rename(self.managed / 'proot-guard-kept.json')
            return result
        self.host.run_bounded.side_effect = transport
        with self.assertRaisesRegex(ValueError, 'nvim-tools-proot-required'): self.install()
        row = json.loads((self.managed / 'nvim-tools-install.json').read_bytes())
        self.assertEqual(row['phase'], 'STAGED')
        self.assertFalse((self.rootfs / row['stage'] / 'transaction.json').exists())
        self.assertEqual(len(self.calls), 1)


if __name__ == '__main__': unittest.main()
