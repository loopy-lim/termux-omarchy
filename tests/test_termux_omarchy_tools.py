"""Real payload/state files; pacman/GPG boundary is replaced on the macOS host."""
import hashlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'termux/omarchy_tools_guest.py'


class PackageCommands:
    """Only the documented operations; a transaction changes a real fixture DB."""
    def __init__(self, stage, rows):
        self.stage, self.rows = stage, rows
        self.db = stage / 'fixture-package-db.json'
        self.db.write_text(json.dumps({'original': '7-1'}))
        self.trusted, self.extra_plan, self.fail_transaction = True, False, False

    def __call__(self, argv):
        if argv[0] == '/usr/bin/gpg':
            output = '[GNUPG:] VALIDSIG ' + 'A' * 40 + ' 2026-10-09 1 0 4 0 1 8 00\n'
            output += '[GNUPG:] TRUST_FULLY 0 pgp\n' if self.trusted else '[GNUPG:] TRUST_UNDEFINED 0 pgp\n'
        elif argv[0] == '/usr/bin/pacman' and argv[1] == '-Q':
            output = ''.join(n + ' ' + v + '\n' for n, v in sorted(json.loads(self.db.read_text()).items()))
        elif argv[0] == '/usr/bin/pacman' and argv[1] == '-Qp':
            row = next(r for r in self.rows if r['file'] == Path(argv[2]).name)
            output = row['name'] + ' ' + row['version'] + '\n'
        elif argv[0] == '/usr/bin/pacman' and '-Up' in argv:
            targets = [r for r in self.rows if str(self.stage / r['file']) in argv]
            output = ''.join(r['name'] + ' ' + r['version'] + '\n' for r in targets)
            if self.extra_plan: output += 'unreviewed 99-1\n'
        elif argv[0] == '/usr/bin/pacman' and '-U' in argv:
            if self.fail_transaction: raise TimeoutError('public interrupted transaction')
            current = json.loads(self.db.read_text())
            current.update({r['name']: r['version'] for r in self.rows if str(self.stage / r['file']) in argv})
            self.db.write_text(json.dumps(current))
            output = 'public installation log\n'
        else:
            raise AssertionError('unexpected package operation')
        return subprocess.CompletedProcess(argv, 0, output, '')


class PayloadFixture:
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'portable signed package worker is missing')
        spec = importlib.util.spec_from_file_location('tested_tools_guest', SOURCE)
        self.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.stage = Path(self.tmp.name).resolve()
        self.rows = []
        for name in ('editor', 'remote'):
            package, signature = (name + ' public package').encode(), (name + ' public signature').encode()
            filename = name + '-1-1-aarch64.pkg.tar.xz'
            row = {'name': name, 'version': '1-1', 'file': filename, 'bytes': len(package),
                   'sha256': hashlib.sha256(package).hexdigest(), 'signatureBytes': len(signature),
                   'signatureSHA256': hashlib.sha256(signature).hexdigest()}
            self.rows.append(row)
            for filename, data in ((filename, package), (filename + '.sig', signature)):
                (self.stage / filename).write_bytes(data); (self.stage / filename).chmod(0o600)
        raw = (json.dumps({'schema': 1, 'component': 'guest-developer-tools', 'packages': self.rows}) + '\n').encode()
        (self.stage / 'tools-manifest.json').write_bytes(raw); (self.stage / 'tools-manifest.json').chmod(0o600)
        self.pin = mock.patch.multiple(self.m, MANIFEST_SHA=hashlib.sha256(raw).hexdigest(), MANIFEST_BYTES=len(raw))
        self.pin.start(); self.addCleanup(self.pin.stop)
        (self.stage / 'pacman.conf').write_bytes(self.m.CONFIG)
        (self.stage / 'pacman.conf').chmod(0o600)
        self.commands = PackageCommands(self.stage, self.rows)

class ToolsTests(PayloadFixture, unittest.TestCase):
    def test_missing_tools_are_reported_without_changing_package_db(self):
        prior = self.commands.db.read_bytes()
        result = self.m.execute(self.stage, runner=self.commands)
        self.assertEqual(result['missing'], {'editor': '1-1', 'remote': '1-1'})
        self.assertEqual(result['signaturesVerified'], 2)
        self.assertEqual(self.commands.db.read_bytes(), prior)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_reviewed_transaction_adds_only_tools_and_preserves_existing_version(self):
        audit = self.m.execute(self.stage, runner=self.commands)
        with mock.patch.object(self.m.os, 'getuid', return_value=0):
            value = self.m.execute(self.stage, install=True, before=audit['beforeSHA256'], runner=self.commands)
        self.assertEqual(json.loads(self.commands.db.read_text()), {'original': '7-1', 'editor': '1-1', 'remote': '1-1'})
        self.assertEqual(value['added'], {'editor': '1-1', 'remote': '1-1'})
        self.assertEqual(value['missing'], {})
        self.assertEqual(json.loads((self.stage / 'transaction.json').read_text())['phase'], 'INSTALLED')

    def test_untrusted_signature_prevents_package_writes(self):
        self.commands.trusted = False; prior = self.commands.db.read_bytes()
        with self.assertRaises(ValueError): self.m.execute(self.stage, runner=self.commands)
        self.assertEqual(self.commands.db.read_bytes(), prior)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_existing_different_version_is_preserved_and_refused(self):
        self.commands.db.write_text(json.dumps({'original': '7-1', 'editor': '9-9'})); prior = self.commands.db.read_bytes()
        with self.assertRaises(ValueError): self.m.execute(self.stage, runner=self.commands)
        self.assertEqual(self.commands.db.read_bytes(), prior)

    def test_extra_dependency_in_plan_prevents_all_package_changes(self):
        audit = self.m.execute(self.stage, runner=self.commands); self.commands.extra_plan = True
        prior = self.commands.db.read_bytes()
        with mock.patch.object(self.m.os, 'getuid', return_value=0), self.assertRaises(ValueError):
            self.m.execute(self.stage, install=True, before=audit['beforeSHA256'], runner=self.commands)
        self.assertEqual(self.commands.db.read_bytes(), prior)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_package_db_change_since_review_is_refused(self):
        audit = self.m.execute(self.stage, runner=self.commands)
        self.commands.db.write_text(json.dumps({'original': '8-1'})); prior = self.commands.db.read_bytes()
        with mock.patch.object(self.m.os, 'getuid', return_value=0), self.assertRaises(ValueError):
            self.m.execute(self.stage, install=True, before=audit['beforeSHA256'], runner=self.commands)
        self.assertEqual(self.commands.db.read_bytes(), prior)

    def test_changed_archive_or_signature_is_refused_before_keyring_commands(self):
        for name in (self.rows[0]['file'], self.rows[1]['file'] + '.sig'):
            target = self.stage / name; old = target.read_bytes(); target.write_bytes(old + b'public change')
            with self.assertRaises(ValueError): self.m.execute(self.stage, runner=self.commands)
            target.write_bytes(old)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_signature_symlink_is_never_followed(self):
        name = self.rows[0]['file'] + '.sig'; target = self.stage / name
        outside = self.stage / 'outside'; target.rename(outside); target.symlink_to(outside)
        with self.assertRaises((ValueError, OSError)): self.m.execute(self.stage, runner=self.commands)
        self.assertFalse((self.stage / 'transaction.json').exists())

    def test_interrupted_transaction_keeps_unknown_journal_and_refuses_retry(self):
        audit = self.m.execute(self.stage, runner=self.commands); self.commands.fail_transaction = True
        with mock.patch.object(self.m.os, 'getuid', return_value=0), self.assertRaises(ValueError):
            self.m.execute(self.stage, install=True, before=audit['beforeSHA256'], runner=self.commands)
        path = self.stage / 'transaction.json'; before = path.read_bytes()
        self.assertEqual(json.loads(before)['phase'], 'INSTALL_UNKNOWN')
        with mock.patch.object(self.m.os, 'getuid', return_value=0), self.assertRaises(ValueError):
            self.m.execute(self.stage, install=True, before=audit['beforeSHA256'], runner=self.commands)
        self.assertEqual(path.read_bytes(), before)


class ToolsInstallerTests(PayloadFixture, unittest.TestCase):
    """Actual installer records and files; only the PRoot process is replaced."""
    def setUp(self):
        super().setUp()
        path = SOURCE.with_name('omarchy_tools_install.py')
        self.assertTrue(path.is_file(), 'portable signed package installer is missing')
        sys.path.insert(0, str(path.parent)); self.addCleanup(sys.path.remove, str(path.parent))
        spec = importlib.util.spec_from_file_location('tested_tools_install', path)
        self.host = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.host)
        self.host_pin = mock.patch.multiple(self.host.worker, MANIFEST_SHA=self.m.MANIFEST_SHA,
                                           MANIFEST_BYTES=self.m.MANIFEST_BYTES)
        self.host_pin.start(); self.addCleanup(self.host_pin.stop)
        self.home, self.prefix = self.stage / 'home', self.stage / 'prefix'
        self.home.mkdir(mode=0o700); self.prefix.mkdir(mode=0o700)
        self.managed = self.home / '.local/share/loopy-omarchy'; self.managed.mkdir(parents=True, mode=0o700)
        self.rootfs = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy/rootfs'
        self.rootfs.mkdir(parents=True, mode=0o700)
        self.base_patch = mock.patch.multiple(self.host.base, HOST_FILES={}, FILE_SHA={})
        self.base_patch.start(); self.addCleanup(self.base_patch.stop)
        identity = self.host.base.identity
        record = {'schema': 1, 'phase': 'INSTALLED', 'uid': os.getuid(), 'root': identity(self.managed.stat()),
                  'home': str(self.home), 'prefix': str(self.prefix), 'container': 'loopy-omarchy',
                  'bundle_sha256': self.host.base.OUTER_SHA, 'container_identity': identity(self.rootfs.parent.stat()),
                  'rootfs_identity': identity(self.rootfs.stat()), 'managed_files': {}}
        (self.managed / 'install.json').write_text(json.dumps(record)); (self.managed / 'install.json').chmod(0o600)
        self.base_bytes = (self.managed / 'install.json').read_bytes()
        for name in ('etc/pacman.conf', 'var/lib/pacman/sync/core.db', 'var/lib/pacman/sync/extra.db'):
            path = self.rootfs / name; path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_bytes(b'public existing config or database'); path.chmod(0o600)
        (self.managed / 'runtime-state.json').write_text(json.dumps({'phase': 'ready'}))
        (self.managed / 'runtime-state.json').chmod(0o600)
        self.missing = False
        def transport(argv, **kwargs):
            self.assertEqual(argv[1:7], ['login', '--isolated', '--user', 'root', 'loopy-omarchy', '--'])
            guest_stage = self.rootfs / argv[10].lstrip('/')
            commands = PackageCommands(guest_stage, self.rows)
            if not self.missing: commands.db.write_text(json.dumps({'original': '7-1', 'editor': '1-1', 'remote': '1-1'}))
            with mock.patch.object(self.host.worker.os, 'getuid', return_value=0):
                return json.dumps(self.host.worker.execute(guest_stage, runner=commands))
        self.transport = mock.patch.object(self.host, 'run_bounded', side_effect=transport)
        self.transport.start(); self.addCleanup(self.transport.stop)

    def test_complete_tools_are_adopted_without_rewriting_existing_installation(self):
        result = self.host.install(self.stage, self.home, self.prefix)
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertFalse(result['packageWrites'])
        self.assertEqual((self.managed / 'install.json').read_bytes(), self.base_bytes)
        journal = (self.managed / 'tools-install.json').read_bytes()
        self.host.install(self.stage, self.home, self.prefix)
        self.assertEqual((self.managed / 'tools-install.json').read_bytes(), journal)

    def test_running_desktop_prevents_missing_package_transaction(self):
        self.missing = True
        with self.assertRaisesRegex(ValueError, 'tools-runtime-active'):
            self.host.install(self.stage, self.home, self.prefix)
        row = json.loads((self.managed / 'tools-install.json').read_bytes())
        self.assertEqual(row['phase'], 'STAGED')
        self.assertFalse((self.rootfs / row['stage'] / 'transaction.json').exists())
        self.assertEqual((self.managed / 'install.json').read_bytes(), self.base_bytes)

    def test_changed_payload_is_refused_before_installer_record_is_created(self):
        target = self.stage / self.rows[0]['file']; target.write_bytes(b'public changed archive')
        with self.assertRaises(ValueError): self.host.install(self.stage, self.home, self.prefix)
        self.assertFalse((self.managed / 'tools-install.json').exists())

    def test_busy_runtime_control_releases_the_install_lock_after_refusal(self):
        with (self.managed / 'runtime-control.lock').open('wb') as lock:
            os.fchmod(lock.fileno(), 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): self.host.install(self.stage, self.home, self.prefix)
        self.assertFalse((self.managed / 'tools-install.json').exists())
        self.assertEqual(self.host.install(self.stage, self.home, self.prefix)['phase'], 'INSTALLED')


if __name__ == '__main__': unittest.main()
