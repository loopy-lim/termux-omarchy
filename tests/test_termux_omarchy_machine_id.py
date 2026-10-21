"""D-Bus identity repair preserves real files, symlinks, locks and history."""
import fcntl
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / 'termux/omarchy_machine_id.py'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    row = path.lstat()
    return [row.st_dev, row.st_ino, row.st_uid]


def snapshot(root):
    return {str(p.relative_to(root)): (p.lstat().st_ino, p.lstat().st_mode,
            p.lstat().st_mtime_ns, os.readlink(p) if p.is_symlink() else
            (p.read_bytes() if p.is_file() else None))
            for p in [root, *sorted(root.rglob('*'))]}


class MachineIDTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'machine-id installer missing')
        sys.path.insert(0, str(SOURCE.parent))
        self.addCleanup(sys.path.remove, str(SOURCE.parent))
        spec = importlib.util.spec_from_file_location('tested_machine_id', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name).resolve()
        self.home, self.prefix = self.path / 'home', self.path / 'prefix'
        self.home.mkdir(mode=0o700); self.prefix.mkdir(mode=0o700)
        self.root = self.home / '.local/share/loopy-omarchy'
        self.root.mkdir(parents=True, mode=0o700)
        self.container = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy'
        self.rootfs = self.container / 'rootfs'
        self.rootfs.mkdir(parents=True, mode=0o700)
        self.etc, self.dbus = self.rootfs / 'etc/machine-id', self.rootfs / 'var/lib/dbus/machine-id'
        for p in (self.etc, self.dbus):
            p.parent.mkdir(parents=True, mode=0o755)
            p.write_bytes(b''); p.chmod(0o444)
        backend = self.root / 'weston/x11-backend.so'
        backend.parent.mkdir(mode=0o700); backend.write_bytes(b'public backend'); backend.chmod(0o600)
        patch = mock.patch.multiple(self.m.base, HOST_FILES={'weston/x11-backend.so': 'fixture'},
                                    FILE_SHA={'fixture': sha(backend.read_bytes())})
        patch.start(); self.addCleanup(patch.stop)
        self.base = dict(schema=1, phase='INSTALLED', uid=os.getuid(), root=identity(self.root),
            home=str(self.home), prefix=str(self.prefix), container='loopy-omarchy',
            bundle_sha256=self.m.base.OUTER_SHA, container_identity=identity(self.container),
            rootfs_identity=identity(self.rootfs), managed_files={'weston/x11-backend.so': sha(backend.read_bytes())})
        self.write_json(self.root / 'install.json', self.base)
        for name in ('install.lock', 'runtime-control.lock'):
            (self.root / name).write_bytes(b''); (self.root / name).chmod(0o600)
        self.write_json(self.root / 'runtime-state.json', {'phase': 'ready', 'token': 'public-live-session'})
        (self.home / '.zshrc').write_bytes(b'public user config')
        self.journal = self.root / 'machine-id-install.json'

    def write_json(self, path, row):
        path.write_text(json.dumps(row)); path.chmod(0o600)

    def write_id(self, path, data):
        path.chmod(0o600); path.write_bytes(data); path.chmod(0o444)

    def install(self):
        return self.m.install(self.home, self.prefix)

    def rejected(self):
        before = snapshot(self.home), snapshot(self.prefix)
        with self.assertRaises((ValueError, OSError)):
            self.install()
        self.assertEqual((snapshot(self.home), snapshot(self.prefix)), before)

    def test_two_empty_regular_files_get_same_id_backups_and_live_session_is_unchanged(self):
        base = (self.root / 'install.json').read_bytes()
        runtime = (self.root / 'runtime-state.json').read_bytes()
        original = [identity(self.etc), identity(self.dbus)]
        result = self.install()
        self.assertRegex(self.etc.read_bytes(), rb'^[0-9a-f]{32}\n$')
        self.assertEqual(self.dbus.read_bytes(), self.etc.read_bytes())
        self.assertEqual(stat.S_IMODE(self.etc.stat().st_mode), 0o444)
        self.assertEqual(stat.S_IMODE(self.dbus.stat().st_mode), 0o444)
        self.assertEqual(result['phase'], 'INSTALLED')
        row = json.loads(self.journal.read_bytes())
        self.assertEqual(row, result)
        backup = self.root / row['backupDirectory']
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o700)
        for index, name in enumerate(('etc/machine-id', 'var/lib/dbus/machine-id')):
            self.assertEqual((backup / ('original-' + str(index))).read_bytes(), b'')
            self.assertEqual(row['before'][name]['fingerprint'][:3], original[index])
            self.assertEqual(row['before'][name]['mode'], 0o444)
        self.assertNotIn(self.etc.read_text().strip(), self.journal.read_text())
        self.assertEqual((self.root / 'install.json').read_bytes(), base)
        self.assertEqual((self.root / 'runtime-state.json').read_bytes(), runtime)

    def test_empty_etc_with_standard_absolute_guest_symlink_preserves_link_inode(self):
        self.dbus.unlink(); self.dbus.symlink_to('/etc/machine-id')
        before = self.dbus.lstat()
        result = self.install()
        self.assertRegex(self.etc.read_bytes(), rb'^[0-9a-f]{32}\n$')
        self.assertEqual(self.dbus.lstat(), before)
        self.assertEqual(os.readlink(self.dbus), '/etc/machine-id')
        self.assertEqual(result['before']['var/lib/dbus/machine-id']['kind'], 'symlink')

    def test_existing_matching_valid_ids_are_no_write_without_journal(self):
        self.write_id(self.etc, b'1234567890abcdef1234567890abcdef\n')
        self.write_id(self.dbus, b'1234567890abcdef1234567890abcdef')
        before = snapshot(self.path)
        result = self.install()
        self.assertEqual(result['status'], 'existing-valid')
        self.assertEqual(snapshot(self.path), before)

    def test_existing_valid_id_with_standard_symlink_is_no_write(self):
        self.write_id(self.etc, b'abcdef1234567890abcdef1234567890\n')
        self.dbus.unlink(); self.dbus.symlink_to('/etc/machine-id')
        before = snapshot(self.path)
        self.assertEqual(self.install()['status'], 'existing-valid')
        self.assertEqual(snapshot(self.path), before)

    def test_completed_repeat_preserves_files_backups_and_journal(self):
        first = self.install(); before = snapshot(self.path)
        self.assertEqual(self.install(), first)
        self.assertEqual(snapshot(self.path), before)

    def test_invalid_nonempty_partial_and_mismatched_ids_are_refused(self):
        for a, b in [(b'x', b''), (b'0'*32+b'\n', b''), (b'A'*32, b'A'*32),
                     (b'a'*32, b'b'*32), (b'a'*32+b'\n\n', b'a'*32)]:
            with self.subTest(a=a,b=b):
                self.write_id(self.etc, a); self.write_id(self.dbus, b)
                self.rejected()

    def test_arbitrary_relative_and_target_symlinks_are_refused(self):
        for target in ('../../../etc/machine-id', '/tmp/machine-id', '/etc/other'):
            self.dbus.unlink(); self.dbus.symlink_to(target)
            self.rejected()
        self.dbus.unlink(); self.dbus.write_bytes(b''); self.dbus.chmod(0o444)
        self.etc.unlink(); self.etc.symlink_to('/etc/machine-id')
        self.rejected()

    def test_missing_hardlinked_or_writable_files_are_refused(self):
        self.etc.chmod(0o666); self.rejected(); self.etc.chmod(0o444)
        self.etc.chmod(0o755); self.rejected(); self.etc.chmod(0o444)
        link = self.rootfs / 'linked'; os.link(self.etc, link)
        self.rejected(); link.unlink()
        self.etc.unlink(); self.rejected()

    def test_replaced_rootfs_and_bad_base_identity_are_refused(self):
        for field, value in [('uid', os.getuid()+1), ('rootfs_identity', [0,0,0]), ('phase','INSTALLING')]:
            self.write_json(self.root/'install.json', dict(self.base, **{field:value}))
            self.rejected()
        self.write_json(self.root/'install.json', self.base)
        self.root.chmod(0o755); self.rejected()

    def test_each_existing_lock_blocks_before_any_mutation(self):
        for name in ('install.lock', 'runtime-control.lock'):
            with (self.root/name).open('r+') as lock:
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                self.rejected()
        (self.root/'runtime-control.lock').unlink(); self.rejected()

    def test_partial_or_unknown_journal_and_orphan_backup_are_refused(self):
        for row in (None, {}, {'phase':'INSTALLING'}):
            self.write_json(self.journal,row); self.rejected()
        self.journal.unlink()
        (self.root/'.machine-id-backup-orphan').mkdir(mode=0o700); self.rejected()

    def test_replaced_installed_id_with_identical_bytes_is_refused(self):
        self.install()
        data=self.etc.read_bytes(); self.etc.unlink(); self.etc.write_bytes(data); self.etc.chmod(0o444)
        self.rejected()

    def test_second_target_failure_preserves_backup_and_unknown_journal(self):
        original=self.m.replace_file
        def fail_second(rootfs,name,*args):
            if name=='var/lib/dbus/machine-id': raise OSError('public injected failure')
            return original(rootfs,name,*args)
        with mock.patch.object(self.m,'replace_file',side_effect=fail_second):
            with self.assertRaises(OSError): self.install()
        row=json.loads(self.journal.read_bytes())
        self.assertEqual(row['phase'],'INSTALL_UNKNOWN')
        self.assertEqual(self.dbus.read_bytes(),b'')
        self.assertEqual((self.root/row['backupDirectory']/'original-0').read_bytes(),b'')
        self.rejected()

    def test_concurrent_target_replacement_is_preserved(self):
        original=self.m.replace_file
        def replace(rootfs,name,*args):
            self.etc.unlink(); self.etc.write_bytes(b'public other owner data'); self.etc.chmod(0o444)
            return original(rootfs,name,*args)
        with mock.patch.object(self.m,'replace_file',side_effect=replace):
            with self.assertRaises(ValueError): self.install()
        self.assertEqual(self.etc.read_bytes(),b'public other owner data')
        self.assertEqual(json.loads(self.journal.read_bytes())['phase'],'INSTALL_UNKNOWN')

    def test_final_journal_failure_preserves_valid_bytes_but_refuses_adoption(self):
        save = self.m.guest.save_record
        def fail(fd, row, *args, **kwargs):
            if row['phase'] == 'INSTALLED': raise OSError('public journal failure')
            return save(fd, row, *args, **kwargs)
        with mock.patch.object(self.m.guest, 'save_record', side_effect=fail):
            with self.assertRaises(OSError): self.install()
        self.assertEqual(self.etc.read_bytes(), self.dbus.read_bytes())
        self.assertEqual(json.loads(self.journal.read_bytes())['phase'], 'INSTALL_UNKNOWN')
        self.rejected()

    def test_cli_result_exposes_only_hash_and_keeps_live_state(self):
        output = io.StringIO()
        with mock.patch.dict(os.environ, HOME=str(self.home), PREFIX=str(self.prefix)):
            with contextlib.redirect_stdout(output): self.assertEqual(self.m.main(), 0)
        row = json.loads(output.getvalue())
        self.assertNotIn(self.etc.read_text().strip(), output.getvalue())
        self.assertEqual(row['machineIDSHA256'], sha(self.etc.read_bytes().rstrip(b'\n')))
        self.assertEqual(json.loads((self.root/'runtime-state.json').read_bytes())['phase'], 'ready')

    def test_changed_preserved_symlink_is_rejected_on_completed_install(self):
        self.dbus.unlink(); self.dbus.symlink_to('/etc/machine-id')
        self.install()
        self.dbus.unlink(); self.dbus.symlink_to('/etc/machine-id')
        self.rejected()


if __name__ == '__main__': unittest.main()
