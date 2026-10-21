"""Real guest files/backups/journal; no guest apps or user data are executed."""
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'termux/omarchy_guest_install.py'


def digest(data):
    return hashlib.sha256(data).hexdigest()


class GuestInstallTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'portable guest adapter installer missing')
        sys.path.insert(0, str(SOURCE.parent))
        self.addCleanup(sys.path.remove, str(SOURCE.parent))
        spec = importlib.util.spec_from_file_location('tested_guest_install', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.home, self.prefix = root / 'home', root / 'prefix'
        self.home.mkdir(mode=0o700)
        self.prefix.mkdir(mode=0o700)
        self.root = self.home / '.local/share/loopy-omarchy'
        self.root.mkdir(parents=True, mode=0o700)
        self.container = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy'
        self.rootfs = self.container / 'rootfs'
        self.rootfs.mkdir(parents=True, mode=0o700)
        self.old = {'usr/share/omarchy/panel.qml': b'public original panel',
                    'home/omarchy/config.lua': b'public original config'}
        self.new = {'usr/local/bin/settings': (b'public settings entry', 0o700),
                    'usr/local/lib/guest.py': (b'VALUE = 1\n', 0o600),
                    'usr/share/omarchy/panel.qml': (b'public patched panel', 0o644),
                    'home/omarchy/config.lua': (b'public patched config', 0o644)}
        for name, data in self.old.items():
            target = self.rootfs / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            target.write_bytes(data)
            target.chmod(0o644)
        backend = self.root / 'weston/x11-backend.so'
        backend.parent.mkdir(mode=0o700)
        backend.write_bytes(b'public backend')
        backend.chmod(0o600)
        self.base_patch = mock.patch.multiple(self.m.base,
            HOST_FILES={'weston/x11-backend.so': 'fixture'}, FILE_SHA={'fixture': digest(backend.read_bytes())})
        self.base_patch.start()
        self.addCleanup(self.base_patch.stop)
        row = {'schema': 1, 'phase': 'INSTALLED', 'uid': os.getuid(), 'root': self.identity(self.root),
               'home': str(self.home), 'prefix': str(self.prefix), 'container': self.m.base.CONTAINER,
               'bundle_sha256': self.m.base.OUTER_SHA, 'container_identity': self.identity(self.container),
               'rootfs_identity': self.identity(self.rootfs), 'managed_files': {'weston/x11-backend.so': digest(backend.read_bytes())}}
        self.base_journal = self.root / 'install.json'
        self.base_journal.write_text(json.dumps(row))
        self.base_journal.chmod(0o600)
        self.base_bytes = self.base_journal.read_bytes()
        self.payload, self.manifest = root / 'guest.tar', root / 'guest.json'
        self.write_inputs()
        self.pin_patch = mock.patch.multiple(self.m, PAYLOAD_SHA=digest(self.payload.read_bytes()),
            PAYLOAD_BYTES=self.payload.stat().st_size, MANIFEST_SHA=digest(self.manifest.read_bytes()),
            MANIFEST_BYTES=self.manifest.stat().st_size)
        self.pin_patch.start()
        self.addCleanup(self.pin_patch.stop)

    def identity(self, path):
        row = path.lstat()
        return [row.st_dev, row.st_ino, row.st_uid]

    def write_inputs(self, extra=None):
        descriptor = {'schema': 1, 'component': 'guest-audio-android-settings', 'files': {
            name: {'sha256': digest(data), 'mode': mode, 'before': digest(self.old[name]) if name in self.old else None}
            for name, (data, mode) in self.new.items()}}
        self.manifest.write_text(json.dumps(descriptor))
        self.manifest.chmod(0o600)
        with tarfile.open(self.payload, 'w:') as tar:
            for name, (data, _) in self.new.items():
                row = tarfile.TarInfo('guest/' + name)
                row.size, row.mode = len(data), 0o600
                tar.addfile(row, io.BytesIO(data))
            if extra is not None:
                tar.addfile(extra, io.BytesIO(b'x' * extra.size) if extra.isfile() else None)
        self.payload.chmod(0o600)

    def repin(self):
        self.m.PAYLOAD_SHA, self.m.PAYLOAD_BYTES = digest(self.payload.read_bytes()), self.payload.stat().st_size
        self.m.MANIFEST_SHA, self.m.MANIFEST_BYTES = digest(self.manifest.read_bytes()), self.manifest.stat().st_size

    def run_install(self):
        return self.m.install(self.payload, self.manifest, self.home, self.prefix)

    def workflow_inputs(self):
        self.assertTrue(hasattr(self.m, 'Component'), 'independent pinned guest components are unavailable')
        files = {'home/omarchy/.zshrc': (b'source public-profile\n', 0o600),
                 'usr/local/bin/remote': (b'#!/bin/sh\nexit 0\n', 0o755)}
        payload, manifest = self.home / 'workflow.tar', self.home / 'workflow.json'
        manifest.write_text(json.dumps({'schema': 1, 'component': 'guest-personal-workflow', 'files': {
            name: {'sha256': digest(data), 'mode': mode, 'before': None}
            for name, (data, mode) in files.items()}}))
        manifest.chmod(0o600)
        with tarfile.open(payload, 'w:') as archive:
            for name, (data, _) in files.items():
                row = tarfile.TarInfo('guest/' + name)
                row.size, row.mode = len(data), 0o600
                archive.addfile(row, io.BytesIO(data))
        payload.chmod(0o600)
        component = self.m.Component(digest(payload.read_bytes()), payload.stat().st_size,
            digest(manifest.read_bytes()), manifest.stat().st_size, 'guest-personal-workflow', 'workflow-install.json')
        return payload, manifest, component

    def original_mode_component(self):
        # Reproduce the real bundle: public originals are 0644/0755, output is 0600/0700.
        self.assertIn('original_modes', self.m.Component._fields,
                      'installer cannot distinguish original permissions from installed permissions')
        self.new['home/omarchy/config.lua'] = (b'public patched config', 0o600)
        name = 'usr/local/bin/launch'
        self.old[name] = b'#!/bin/sh\n# public original launcher\n'
        self.new[name] = (b'#!/bin/sh\n# public managed launcher\n', 0o700)
        target = self.rootfs / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.write_bytes(self.old[name]); target.chmod(0o755)
        self.write_inputs(); self.repin()
        return self.m.definition()._replace(original_modes=(
            ('home/omarchy/config.lua', 0o644), (name, 0o755)))

    def test_bundle_original_modes_are_backed_up_and_restricted_on_installation(self):
        # Catches rejecting fresh bundle configs because their pre-install mode differs.
        component = self.original_mode_component()
        value = self.m.install(self.payload, self.manifest, self.home, self.prefix, component=component)
        self.assertEqual(value['phase'], 'INSTALLED')
        self.assertEqual((self.rootfs / 'home/omarchy/config.lua').stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.rootfs / 'usr/local/bin/launch').stat().st_mode & 0o777, 0o700)
        originals = {entry['path']: entry for entry in value['changes'] if entry['backup'] is not None}
        for name, mode in component.original_modes:
            self.assertEqual(originals[name]['original']['mode'], mode)
            backup = self.root / value['backupDirectory'] / originals[name]['backup']
            self.assertEqual(backup.read_bytes(), self.old[name])
        journal = (self.root / 'guest-install.json').read_bytes()
        inode = (self.rootfs / 'home/omarchy/config.lua').stat().st_ino
        self.m.install(self.payload, self.manifest, self.home, self.prefix, component=component)
        self.assertEqual((self.root / 'guest-install.json').read_bytes(), journal)
        self.assertEqual((self.rootfs / 'home/omarchy/config.lua').stat().st_ino, inode)

    def test_user_changed_original_permissions_preserve_the_entire_plan(self):
        # Catches weakening the original-mode boundary to accept any safe-looking mode.
        component = self.original_mode_component()
        target = self.rootfs / 'home/omarchy/config.lua'
        target.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'guest-user-file-changed'):
            self.m.install(self.payload, self.manifest, self.home, self.prefix, component=component)
        self.assertEqual(target.read_bytes(), self.old['home/omarchy/config.lua'])
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.rootfs / 'usr/local/bin/settings').exists())
        self.assertFalse((self.root / 'guest-install.json').exists())
        self.assertFalse(any(self.root.glob('.guest-backup-*')))

    def test_original_mode_policy_cannot_describe_a_new_file(self):
        component = self.original_mode_component()._replace(original_modes=(('usr/local/bin/settings', 0o755),))
        with self.assertRaisesRegex(ValueError, 'guest-original-mode-boundary'):
            self.m.install(self.payload, self.manifest, self.home, self.prefix, component=component)
        self.assertFalse((self.rootfs / 'usr/local/bin/settings').exists())
        self.assertFalse((self.root / 'guest-install.json').exists())

    def test_workflow_files_use_a_separate_journal_and_keep_adapter_installation(self):
        # Catches a second component overwriting the audio/settings ownership record.
        self.run_install()
        original = (self.root / 'guest-install.json').read_bytes()
        payload, manifest, component = self.workflow_inputs()
        value = self.m.install(payload, manifest, self.home, self.prefix, component=component)
        self.assertEqual(value['phase'], 'INSTALLED')
        self.assertEqual(value['filesVerified'], 2)
        self.assertEqual((self.rootfs / 'home/omarchy/.zshrc').read_bytes(), b'source public-profile\n')
        self.assertEqual((self.rootfs / 'usr/local/bin/remote').stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.root / 'guest-install.json').read_bytes(), original)
        self.assertEqual(json.loads((self.root / 'workflow-install.json').read_bytes()), value)

    def test_workflow_reinstall_keeps_existing_files_and_both_journals(self):
        self.run_install()
        payload, manifest, component = self.workflow_inputs()
        self.m.install(payload, manifest, self.home, self.prefix, component=component)
        before = {name: (self.root / name).read_bytes() for name in ('guest-install.json', 'workflow-install.json')}
        target = self.rootfs / 'home/omarchy/.zshrc'
        inode = target.stat().st_ino
        self.m.install(payload, manifest, self.home, self.prefix, component=component)
        self.assertEqual(target.stat().st_ino, inode)
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in before})

    def test_component_journal_path_cannot_escape_managed_root(self):
        payload, manifest, component = self.workflow_inputs()
        component = component._replace(journal='../outside.json')
        with self.assertRaises(ValueError):
            self.m.install(payload, manifest, self.home, self.prefix, component=component)
        self.assertFalse((self.root.parent / 'outside.json').exists())
        self.assertFalse((self.rootfs / 'home/omarchy/.zshrc').exists())

    def test_new_adapters_and_original_patches_are_installed_with_exact_backups(self):
        result = self.run_install()
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(result['filesVerified'], 4)
        self.assertEqual(self.base_journal.read_bytes(), self.base_bytes)
        for name, (data, mode) in self.new.items():
            self.assertEqual((self.rootfs / name).read_bytes(), data)
            self.assertEqual((self.rootfs / name).stat().st_mode & 0o777, mode)
        backups = self.root / result['backupDirectory']
        for entry in result['changes']:
            if entry['backup'] is not None:
                self.assertEqual((backups / entry['backup']).read_bytes(), self.old[entry['path']])

    def test_reinstall_preserves_every_target_inode_and_journal_bytes(self):
        self.run_install()
        before = {name: self.identity(self.rootfs / name) for name in self.new}
        journal = (self.root / 'guest-install.json').read_bytes()
        self.run_install()
        self.assertEqual(before, {name: self.identity(self.rootfs / name) for name in self.new})
        self.assertEqual((self.root / 'guest-install.json').read_bytes(), journal)

    def test_complete_legacy_adapters_can_be_adopted_while_runtime_is_ready(self):
        self.run_install()
        (self.root / 'guest-install.json').unlink()
        state = self.root / 'runtime-state.json'
        state.write_text(json.dumps({'phase': 'ready'}))
        state.chmod(0o600)
        before = {name: self.identity(self.rootfs / name) for name in self.new}
        result = self.run_install()
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(result['changes'], [])
        self.assertEqual(before, {name: self.identity(self.rootfs / name) for name in self.new})
        self.assertEqual(json.loads(state.read_bytes()), {'phase': 'ready'})

    def test_running_runtime_prevents_all_guest_changes_and_backups(self):
        state = self.root / 'runtime-state.json'
        state.write_text(json.dumps({'phase': 'ready'}))
        state.chmod(0o600)
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse((self.root / 'guest-install.json').exists())
        self.assertFalse((self.rootfs / 'usr/local/bin/settings').exists())
        self.assertEqual((self.rootfs / 'home/omarchy/config.lua').read_bytes(), self.old['home/omarchy/config.lua'])

    def test_user_modified_original_refuses_whole_plan_before_any_guest_write(self):
        target = self.rootfs / 'home/omarchy/config.lua'
        target.write_bytes(b'public user change')
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual(target.read_bytes(), b'public user change')
        self.assertFalse((self.rootfs / 'usr/local/bin/settings').exists())
        self.assertEqual((self.rootfs / 'usr/share/omarchy/panel.qml').read_bytes(), self.old['usr/share/omarchy/panel.qml'])
        self.assertFalse((self.root / 'guest-install.json').exists())

    def test_missing_required_original_is_not_recreated(self):
        target = self.rootfs / 'home/omarchy/config.lua'
        target.unlink()
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse(target.exists())
        self.assertFalse((self.rootfs / 'usr/local/bin/settings').exists())

    def test_target_symlink_and_symlink_parent_are_never_followed(self):
        original = self.rootfs / 'home/omarchy/config.lua'
        other = self.home / 'other'
        other.write_bytes(self.old['home/omarchy/config.lua'])
        original.unlink()
        original.symlink_to(other)
        with self.assertRaises((ValueError, OSError)):
            self.run_install()
        self.assertEqual(other.read_bytes(), self.old['home/omarchy/config.lua'])
        original.unlink()
        original.write_bytes(self.old['home/omarchy/config.lua'])
        original.chmod(0o644)
        external = self.home / 'external'
        external.mkdir(mode=0o700)
        (self.rootfs / 'usr/local').parent.mkdir(parents=True, exist_ok=True)
        (self.rootfs / 'usr/local').symlink_to(external)
        with self.assertRaises((ValueError, OSError)):
            self.run_install()
        self.assertEqual(list(external.iterdir()), [])

    def test_changed_source_inputs_are_refused_before_journal(self):
        for path in (self.payload, self.manifest):
            original = path.read_bytes()
            path.write_bytes(original + b'x')
            with self.assertRaises(ValueError):
                self.run_install()
            self.assertFalse((self.root / 'guest-install.json').exists())
            self.assertFalse((self.rootfs / 'usr/local/bin/settings').exists())
            path.write_bytes(original)

    def test_archive_unknown_traversal_duplicate_symlink_and_fifo_refused(self):
        for name, kind in [('guest/extra', tarfile.REGTYPE), ('../escape', tarfile.REGTYPE),
                           ('guest/usr/local/bin/settings', tarfile.REGTYPE), ('guest/link', tarfile.SYMTYPE),
                           ('guest/fifo', tarfile.FIFOTYPE)]:
            with self.subTest(name=name, kind=kind):
                row = tarfile.TarInfo(name)
                row.type, row.size, row.linkname = kind, 1 if kind == tarfile.REGTYPE else 0, '/tmp'
                self.write_inputs(extra=row)
                self.repin()
                with self.assertRaises(ValueError):
                    self.run_install()
                self.assertFalse((self.root / 'guest-install.json').exists())

    def test_replaced_rootfs_identity_refuses_before_any_changes(self):
        value = json.loads(self.base_journal.read_bytes())
        value['rootfs_identity'][1] += 1
        self.base_journal.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse((self.root / 'guest-install.json').exists())

    def test_unknown_phase_is_retained_and_never_retried(self):
        journal = self.root / 'guest-install.json'
        value = {'schema': 1, 'uid': os.getuid(), 'root': self.identity(self.root),
                 'rootfs': self.identity(self.rootfs), 'payloadSHA256': self.m.PAYLOAD_SHA,
                 'manifestSHA256': self.m.MANIFEST_SHA, 'filesVerified': 4, 'phase': 'INSTALL_UNKNOWN'}
        journal.write_text(json.dumps(value))
        journal.chmod(0o600)
        before = journal.read_bytes()
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual(journal.read_bytes(), before)
        self.assertFalse((self.rootfs / 'usr/local/bin/settings').exists())

    def test_user_changes_after_install_are_preserved_and_not_overwritten(self):
        self.run_install()
        target = self.rootfs / 'usr/local/bin/settings'
        target.write_bytes(b'public new user adapter')
        journal = (self.root / 'guest-install.json').read_bytes()
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual(target.read_bytes(), b'public new user adapter')
        self.assertEqual((self.root / 'guest-install.json').read_bytes(), journal)

    def test_runtime_control_lock_blocks_installer_before_journal(self):
        fd = os.open(self.root / 'runtime-control.lock', os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(ValueError):
                self.run_install()
            self.assertFalse((self.root / 'guest-install.json').exists())
            self.assertFalse((self.rootfs / 'usr/local/bin/settings').exists())
        finally:
            os.close(fd)

    def test_mid_install_error_keeps_exact_backups_and_uncertain_journal(self):
        original = self.m.write_target
        count = 0
        def interrupted(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('public interruption')
            return original(*args, **kwargs)
        with mock.patch.object(self.m, 'write_target', interrupted):
            with self.assertRaises(ValueError):
                self.run_install()
        row = json.loads((self.root / 'guest-install.json').read_bytes())
        self.assertEqual(row['phase'], 'INSTALL_UNKNOWN')
        for entry in row['changes']:
            if entry['backup']:
                self.assertEqual((self.root / row['backupDirectory'] / entry['backup']).read_bytes(), self.old[entry['path']])
        with self.assertRaises(ValueError):
            self.run_install()


if __name__ == '__main__':
    unittest.main()
