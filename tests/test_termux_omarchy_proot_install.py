"""Private PRoot installation uses real files, locks, publication and receipts."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'termux/omarchy_proot_install.py'
ARTIFACTS = ROOT / 'build/diagnostics/termux-omarchy-proot-private-runpath-build-20261009-01/arm64-v8a'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    row = path.lstat()
    return [row.st_dev, row.st_ino, row.st_uid]


def snapshot(root):
    result = {}
    for path in [root, *sorted(root.rglob('*'))]:
        row = path.lstat()
        content = os.readlink(path) if path.is_symlink() else (
            digest(path.read_bytes()) if path.is_file() else None)
        result[str(path.relative_to(root))] = (
            row.st_dev, row.st_ino, row.st_mode, row.st_uid, row.st_mtime_ns, content)
    return result


class ProotInstallTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'private PRoot installer missing')
        sys.path.insert(0, str(SOURCE.parent))
        self.addCleanup(sys.path.remove, str(SOURCE.parent))
        spec = importlib.util.spec_from_file_location('tested_proot_install', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name).resolve()
        self.home, self.prefix = self.directory / 'home', self.directory / 'prefix'
        self.home.mkdir(mode=0o700)
        self.prefix.mkdir(mode=0o700)
        self.root = self.home / '.local/share/loopy-omarchy'
        self.root.mkdir(parents=True, mode=0o700)
        self.container = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy'
        self.rootfs = self.container / 'rootfs'
        self.rootfs.mkdir(parents=True, mode=0o700)
        backend = self.root / 'weston/x11-backend.so'
        backend.parent.mkdir(mode=0o700)
        backend.write_bytes(b'public fixture backend')
        backend.chmod(0o600)
        patch = mock.patch.multiple(self.m.base, HOST_FILES={'weston/x11-backend.so': 'fixture'},
                                   FILE_SHA={'fixture': digest(backend.read_bytes())})
        patch.start()
        self.addCleanup(patch.stop)
        self.base_record = dict(schema=1, phase='INSTALLED', uid=os.getuid(), root=identity(self.root),
            home=str(self.home), prefix=str(self.prefix), container='loopy-omarchy',
            bundle_sha256=self.m.base.OUTER_SHA, container_identity=identity(self.container),
            rootfs_identity=identity(self.rootfs), managed_files={'weston/x11-backend.so': digest(backend.read_bytes())})
        self.base_journal = self.root / 'install.json'
        self.write_json(self.base_journal, self.base_record)
        self.source = self.directory / 'source'
        self.source.mkdir(mode=0o700)
        for name in ('proot', 'loader', 'libandroid-shmem.so'):
            shutil.copyfile(ARTIFACTS / name, self.source / name)
            (self.source / name).chmod(0o700)
        self.guard = self.root / 'proot-guard'
        self.journal = self.root / 'proot-guard.json'
        # Existing global binaries and user settings must never become installation targets.
        (self.prefix / 'bin').mkdir(mode=0o700)
        (self.prefix / 'bin/proot').write_bytes(b'public global proot')
        (self.home / '.zshrc').write_bytes(b'public user shell config')
        (self.rootfs / 'pacman.conf').write_bytes(b'public pacman config')

    def write_json(self, path, value):
        path.write_text(json.dumps(value))
        path.chmod(0o600)

    def install(self):
        return self.m.install(self.source, self.home, self.prefix)

    def assert_rejected_without_writes(self):
        before = snapshot(self.home), snapshot(self.prefix)
        with self.assertRaises((ValueError, OSError)):
            self.install()
        self.assertEqual((snapshot(self.home), snapshot(self.prefix)), before)

    def prepare_locks(self):
        for name in ('install.lock', 'runtime-control.lock'):
            path = self.root / name
            path.write_bytes(b'')
            path.chmod(0o600)

    def test_installs_pinned_files_with_private_modes_and_exact_bound_receipt(self):
        before_prefix = snapshot(self.prefix)
        before_base = self.base_journal.read_bytes()
        result = self.install()
        self.assertEqual(result, dict(schema=1, phase='INSTALLED', uid=os.getuid(),
            root=identity(self.root), directory=identity(self.guard), files=self.m.guard.FILES))
        self.assertEqual(json.loads(self.journal.read_bytes()), result)
        self.assertEqual(set(p.name for p in self.guard.iterdir()), {'proot', 'loader', 'libandroid-shmem.so'})
        for name, mode in {'proot': 0o700, 'loader': 0o700, 'libandroid-shmem.so': 0o600}.items():
            self.assertEqual((self.guard / name).read_bytes(), (self.source / name).read_bytes())
            self.assertEqual(stat.S_IMODE((self.guard / name).stat().st_mode), mode)
        self.assertEqual(stat.S_IMODE(self.guard.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.journal.stat().st_mode), 0o600)
        self.assertEqual(self.m.guard.selection(self.root), self.guard)
        self.assertEqual(snapshot(self.prefix), before_prefix)
        self.assertEqual(self.base_journal.read_bytes(), before_base)
        self.assertEqual((self.home / '.zshrc').read_bytes(), b'public user shell config')

    def test_valid_repeat_does_not_rewrite_files_directories_or_receipts(self):
        first = self.install()
        before = snapshot(self.home), snapshot(self.prefix)
        self.assertEqual(self.install(), first)
        self.assertEqual((snapshot(self.home), snapshot(self.prefix)), before)

    def test_all_source_hashes_are_verified_before_managed_state_is_touched(self):
        (self.source / 'libandroid-shmem.so').write_bytes(b'public corrupt library')
        self.assert_rejected_without_writes()

    def test_source_links_and_extra_members_are_refused(self):
        library = self.source / 'loader'
        original = library.read_bytes()
        library.unlink()
        library.symlink_to(ARTIFACTS / 'loader')
        self.assert_rejected_without_writes()
        library.unlink()
        library.write_bytes(original)
        library.chmod(0o700)
        (self.source / 'unexpected').write_bytes(b'public extra')
        self.assert_rejected_without_writes()

    def test_source_hardlink_is_refused(self):
        os.link(self.source / 'proot', self.directory / 'linked-proot')
        self.assert_rejected_without_writes()

    def test_bad_base_identity_is_refused_without_publishing(self):
        self.prepare_locks()
        self.base_record['rootfs_identity'][1] += 1
        self.write_json(self.base_journal, self.base_record)
        self.assert_rejected_without_writes()

    def test_active_and_unconfirmed_stopped_sessions_are_refused(self):
        self.prepare_locks()
        for state in ({'phase': 'ready'}, {'phase': 'stopped'},
                      {'phase': 'stopped', 'terminationConfirmed': False}):
            self.write_json(self.root / 'runtime-state.json', state)
            self.assert_rejected_without_writes()

    def test_confirmed_stopped_session_permits_installation(self):
        self.write_json(self.root / 'runtime-state.json', {'phase': 'stopped', 'terminationConfirmed': True})
        self.assertEqual(self.install()['phase'], 'INSTALLED')

    def test_valid_existing_guard_is_not_adopted_during_an_active_session(self):
        self.install()
        self.write_json(self.root / 'runtime-state.json', {'phase': 'ready'})
        self.assert_rejected_without_writes()

    def test_disappearing_runtime_state_during_read_never_becomes_absent_state(self):
        self.prepare_locks()
        self.write_json(self.root / 'runtime-state.json', {'phase': 'stopped', 'terminationConfirmed': True})
        original = self.m.os.stat
        def disappear(path, *args, **kwargs):
            if path == 'runtime-state.json':
                os.unlink(path, dir_fd=kwargs['dir_fd'])
            return original(path, *args, **kwargs)
        with mock.patch.object(self.m.os, 'stat', side_effect=disappear):
            with self.assertRaises((ValueError, OSError)):
                self.install()
        self.assertFalse(self.guard.exists())
        self.assertFalse(self.journal.exists())

    def test_each_runtime_or_install_lock_blocks_publication(self):
        self.prepare_locks()
        for name in ('install.lock', 'runtime-control.lock'):
            with (self.root / name).open('r+b') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assert_rejected_without_writes()

    def test_unknown_guard_directory_is_preserved_without_adoption(self):
        self.prepare_locks()
        self.guard.mkdir(mode=0o700)
        (self.guard / 'user-file').write_bytes(b'public user file')
        self.assert_rejected_without_writes()

    def test_old_partial_stage_is_preserved_and_blocks_retry(self):
        self.prepare_locks()
        stage = self.root / '.proot-guard-stage-1234567890abcdef1234567890abcdef'
        stage.mkdir(mode=0o700)
        (stage / 'loader').write_bytes(b'public partial loader')
        self.assert_rejected_without_writes()

    def test_unknown_receipt_is_preserved(self):
        self.prepare_locks()
        self.write_json(self.journal, {'schema': 1, 'phase': 'INSTALL_UNKNOWN'})
        self.assert_rejected_without_writes()

    def test_changed_installed_payload_is_preserved(self):
        self.install()
        (self.guard / 'proot').write_bytes(b'public user modification')
        self.assert_rejected_without_writes()

    def test_installed_mode_change_is_not_repaired_without_user_review(self):
        self.install()
        (self.guard / 'loader').chmod(0o755)
        self.assert_rejected_without_writes()

    def test_guard_symlink_never_targets_external_directory(self):
        self.prepare_locks()
        outside = self.directory / 'outside'
        outside.mkdir(mode=0o700)
        self.guard.symlink_to(outside)
        self.assert_rejected_without_writes()
        self.assertEqual(list(outside.iterdir()), [])

    def test_failed_publication_retains_stage_and_refuses_later_retry(self):
        with mock.patch.object(self.m.host, 'publish_directory', side_effect=OSError('public fixture rename failure')):
            with self.assertRaises((ValueError, OSError)):
                self.install()
        stages = list(self.root.glob('.proot-guard-stage-*'))
        self.assertEqual(len(stages), 1)
        self.assertEqual(set(p.name for p in stages[0].iterdir()), {'proot', 'loader', 'libandroid-shmem.so'})
        self.assertFalse(self.guard.exists())
        self.assertFalse(self.journal.exists())
        self.assert_rejected_without_writes()

    def test_failed_receipt_publication_retains_guard_and_refuses_adoption(self):
        original = self.m.base.publish
        def fail_receipt(fd, temporary, name):
            if name == 'proot-guard.json':
                raise OSError('public fixture journal publication failure')
            return original(fd, temporary, name)
        with mock.patch.object(self.m.base, 'publish', side_effect=fail_receipt):
            with self.assertRaises((ValueError, OSError)):
                self.install()
        self.assertTrue(self.guard.is_dir())
        self.assertFalse(self.journal.exists())
        self.assert_rejected_without_writes()

    def test_concurrent_guard_directory_is_not_replaced(self):
        original = self.m.host.publish_directory
        def add_other(fd, stage, name):
            self.guard.mkdir(mode=0o700)
            (self.guard / 'user-file').write_bytes(b'public concurrent directory')
            return original(fd, stage, name)
        with mock.patch.object(self.m.host, 'publish_directory', side_effect=add_other):
            with self.assertRaises((ValueError, OSError)):
                self.install()
        self.assertEqual((self.guard / 'user-file').read_bytes(), b'public concurrent directory')
        self.assertFalse(self.journal.exists())


if __name__ == '__main__':
    unittest.main()
