"""Pinned native payload boundaries; only the ELF version process is doubled."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'termux' / 'omarchy_host_install.py'


def digest(data):
    return hashlib.sha256(data).hexdigest()


class HostInstallTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'portable Weston installer missing')
        sys.path.insert(0, str(SOURCE.parent))
        self.addCleanup(sys.path.remove, str(SOURCE.parent))
        spec = importlib.util.spec_from_file_location('tested_host_install', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve() / 'home'
        self.prefix = Path(self.tmp.name).resolve() / 'prefix'
        self.home.mkdir(mode=0o700)
        self.prefix.mkdir(mode=0o700)
        self.root = self.home / '.local/share/loopy-omarchy'
        self.root.mkdir(parents=True, mode=0o700)
        self.host = self.root / 'weston-host'
        self.container = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy'
        self.container.mkdir(parents=True, mode=0o700)
        (self.container / 'rootfs').mkdir(mode=0o700)
        self.backend = b'public fixture backend'
        (self.root / 'weston').mkdir(mode=0o700)
        (self.root / 'weston/x11-backend.so').write_bytes(self.backend)
        (self.root / 'weston/x11-backend.so').chmod(0o600)
        base_patch = mock.patch.multiple(self.m.base,
            HOST_FILES={'weston/x11-backend.so': 'fixture-backend'},
            FILE_SHA={'fixture-backend': digest(self.backend)})
        base_patch.start()
        self.addCleanup(base_patch.stop)
        row = {'schema': 1, 'uid': os.getuid(), 'root': self.identity(self.root),
               'home': str(self.home), 'prefix': str(self.prefix),
               'container': 'loopy-omarchy', 'bundle_sha256': self.m.base.OUTER_SHA,
               'phase': 'INSTALLED', 'container_identity': self.identity(self.container),
               'rootfs_identity': self.identity(self.container / 'rootfs'),
               'managed_files': {'weston/x11-backend.so': digest(self.backend)}}
        self.base_journal = self.root / 'install.json'
        self.base_journal.write_text(json.dumps(row))
        self.base_journal.chmod(0o600)
        self.base_bytes = self.base_journal.read_bytes()
        self.files = {'bin/weston': (b'public fixture executable', 0o700),
                      'lib/libweston-14.so': (b'public fixture library', 0o600),
                      'lib/libweston-14/gl-renderer.so': (b'public fixture renderer', 0o600),
                      'lib/weston/kiosk-shell.so': (b'public fixture shell', 0o600)}
        self.payload, self.manifest = self.home / 'payload.tar', self.home / 'payload-manifest.json'
        self.write_inputs()
        self.pin_patch = mock.patch.multiple(self.m, PAYLOAD_SHA=digest(self.payload.read_bytes()),
            PAYLOAD_BYTES=self.payload.stat().st_size, MANIFEST_SHA=digest(self.manifest.read_bytes()),
            MANIFEST_BYTES=self.manifest.stat().st_size)
        self.pin_patch.start()
        self.addCleanup(self.pin_patch.stop)
        self.version_calls = []

    def identity(self, path):
        row = path.lstat()
        return [row.st_dev, row.st_ino, row.st_uid]

    def write_inputs(self, extra=None, omit=None):
        manifest = {'schema': 1, 'debSHA256': self.m.DEB_SHA, 'sourceURL': self.m.SOURCE_URL,
                    'files': {k: {'sha256': digest(v), 'mode': mode} for k, (v, mode) in self.files.items()}}
        self.manifest.write_text(json.dumps(manifest))
        self.manifest.chmod(0o600)
        with tarfile.open(self.payload, 'w:') as tar:
            directories = {'weston-host'}
            for name in self.files:
                directories.update(str(p) for p in Path('weston-host', name).parents if str(p) != '.')
            for name in sorted(directories):
                row = tarfile.TarInfo(name)
                row.type, row.mode = tarfile.DIRTYPE, 0o755
                tar.addfile(row)
            for name, (data, mode) in self.files.items():
                if name == omit:
                    continue
                row = tarfile.TarInfo('weston-host/' + name)
                row.size, row.mode = len(data), mode
                tar.addfile(row, io.BytesIO(data))
            if extra is not None:
                tar.addfile(extra, io.BytesIO(b'x' * extra.size) if extra.isfile() else None)
        self.payload.chmod(0o600)

    def repin(self):
        self.m.PAYLOAD_SHA = digest(self.payload.read_bytes())
        self.m.PAYLOAD_BYTES = self.payload.stat().st_size
        self.m.MANIFEST_SHA = digest(self.manifest.read_bytes())
        self.m.MANIFEST_BYTES = self.manifest.stat().st_size

    def version(self, args, **kwargs):
        self.version_calls.append(args)
        self.assertEqual(args[1:], ['--version'])
        self.assertFalse(kwargs.get('shell', False))
        path = Path(args[0])
        self.assertTrue(path.is_relative_to(self.root))
        self.assertEqual(path.read_bytes(), self.files['bin/weston'][0])
        self.assertEqual(kwargs['env']['LD_LIBRARY_PATH'],
                         f'{path.parent.parent}/lib/weston:{path.parent.parent}/lib:{self.prefix}/lib')
        return subprocess.CompletedProcess(args, 0, b'weston 14.0.2\n', b'')

    def run_install(self, runner=None):
        with mock.patch.object(self.m.subprocess, 'run', runner or self.version):
            return self.m.install(self.payload, self.manifest, self.home, self.prefix)

    def test_fresh_host_is_complete_private_and_callable_without_changing_base(self):
        result = self.run_install()
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(result['host'], self.identity(self.host))
        self.assertEqual(result['filesVerified'], 4)
        self.assertEqual(len(self.version_calls), 1)
        self.assertEqual(self.base_journal.read_bytes(), self.base_bytes)
        for name, (data, mode) in self.files.items():
            self.assertEqual((self.host / name).read_bytes(), data)
            self.assertEqual((self.host / name).stat().st_mode & 0o777, mode)
        self.assertEqual(self.host.stat().st_mode & 0o777, 0o700)
        self.assertEqual(json.loads((self.root / 'weston-install.json').read_bytes())['phase'], 'INSTALLED')

    def test_identical_reinstall_keeps_all_file_and_directory_inodes(self):
        self.run_install()
        before = {p: self.identity(p) for p in self.host.rglob('*')}
        root_before = self.identity(self.host)
        journal_before = (self.root / 'weston-install.json').read_bytes()
        self.run_install()
        self.assertEqual(before, {p: self.identity(p) for p in self.host.rglob('*')})
        self.assertEqual(root_before, self.identity(self.host))
        self.assertEqual((self.root / 'weston-install.json').read_bytes(), journal_before)

    def test_complete_legacy_host_is_adopted_without_overwriting_legacy_metadata(self):
        self.run_install()
        (self.root / 'weston-install.json').unlink()
        old = self.root / 'weston-host.json'
        old.write_bytes(b'public original metadata')
        old.chmod(0o600)
        before = self.identity(self.host / 'bin/weston')
        result = self.run_install()
        self.assertTrue(result['adoptedExisting'])
        self.assertEqual(old.read_bytes(), b'public original metadata')
        self.assertEqual(before, self.identity(self.host / 'bin/weston'))

    def test_changed_payload_or_manifest_refused_before_any_host_or_journal(self):
        for path in (self.payload, self.manifest):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b'x')
                with self.assertRaises(ValueError):
                    self.run_install()
                self.assertFalse(self.host.exists())
                self.assertFalse((self.root / 'weston-install.json').exists())
                path.write_bytes(original)
        self.assertEqual(self.version_calls, [])

    def test_symlink_and_world_writable_input_refused(self):
        original = self.payload.read_bytes()
        self.payload.unlink()
        other = self.home / 'other'
        other.write_bytes(original)
        self.payload.symlink_to(other)
        with self.assertRaises((ValueError, OSError)):
            self.run_install()
        self.payload.unlink()
        self.payload.write_bytes(original)
        self.payload.chmod(0o666)
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse(self.host.exists())

    def test_archive_unknown_traversal_duplicate_links_and_missing_files_refused(self):
        for name, kind in [('weston-host/extra', tarfile.REGTYPE), ('../escape', tarfile.REGTYPE),
                           ('/escape', tarfile.REGTYPE), ('weston-host/bin/weston', tarfile.REGTYPE),
                           ('weston-host/link', tarfile.SYMTYPE), ('weston-host/fifo', tarfile.FIFOTYPE)]:
            with self.subTest(name=name, kind=kind):
                row = tarfile.TarInfo(name)
                row.type, row.size, row.linkname = kind, 1 if kind == tarfile.REGTYPE else 0, '/tmp'
                self.write_inputs(extra=row)
                self.repin()
                with self.assertRaises(ValueError):
                    self.run_install()
                self.assertFalse(self.host.exists())
        self.write_inputs(omit='lib/libweston-14.so')
        self.repin()
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse(self.host.exists())

    def test_manifest_unsafe_paths_modes_and_file_hashes_refused(self):
        original = dict(self.files)
        for changed in ({'../escape': (b'x', 0o600)}, {'bin/weston': (b'x', 0o777)}):
            self.files = changed
            self.write_inputs()
            self.repin()
            with self.assertRaises(ValueError):
                self.run_install()
            self.assertFalse(self.host.exists())
        self.files = original
        self.write_inputs()
        value = json.loads(self.manifest.read_bytes())
        value['files']['bin/weston']['sha256'] = '0' * 64
        self.manifest.write_text(json.dumps(value))
        self.repin()
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse(self.host.exists())

    def test_changed_or_extra_existing_file_is_preserved(self):
        self.run_install()
        journal_before = (self.root / 'weston-install.json').read_bytes()
        target = self.host / 'bin/weston'
        target.write_bytes(b'public user edit')
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual(target.read_bytes(), b'public user edit')
        self.assertEqual((self.root / 'weston-install.json').read_bytes(), journal_before)
        target.write_bytes(self.files['bin/weston'][0])
        extra = self.host / 'user-file'
        extra.write_bytes(b'public user file')
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual(extra.read_bytes(), b'public user file')

    def test_existing_host_symlink_is_refused_without_following(self):
        other = self.home / 'other-host'
        other.mkdir(mode=0o700)
        self.host.symlink_to(other)
        with self.assertRaises((ValueError, OSError)):
            self.run_install()
        self.assertTrue(self.host.is_symlink())
        self.assertEqual(list(other.iterdir()), [])

    def test_missing_host_is_not_added_while_runtime_is_active(self):
        state = self.root / 'runtime-state.json'
        state.write_text(json.dumps({'phase': 'ready'}))
        state.chmod(0o600)
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse(self.host.exists())
        self.assertFalse((self.root / 'weston-install.json').exists())

    def test_confirmed_stopped_runtime_permits_first_host_install(self):
        state = self.root / 'runtime-state.json'
        state.write_text(json.dumps({'phase': 'stopped', 'terminationConfirmed': True}))
        state.chmod(0o600)
        self.assertEqual(self.run_install()['phase'], 'INSTALLED')

    def test_same_complete_host_can_be_adopted_during_running_session(self):
        self.run_install()
        (self.root / 'weston-install.json').unlink()
        state = self.root / 'runtime-state.json'
        state.write_text(json.dumps({'phase': 'ready'}))
        state.chmod(0o600)
        self.assertEqual(self.run_install()['phase'], 'INSTALLED')
        self.assertEqual(json.loads(state.read_bytes()), {'phase': 'ready'})

    def test_unknown_install_phase_is_retained_and_refused(self):
        journal = self.root / 'weston-install.json'
        journal.write_text(json.dumps({'schema': 1, 'uid': os.getuid(), 'root': self.identity(self.root),
            'payloadSHA256': self.m.PAYLOAD_SHA, 'manifestSHA256': self.m.MANIFEST_SHA,
            'phase': 'INSTALL_UNKNOWN'}))
        journal.chmod(0o600)
        before = journal.read_bytes()
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual(journal.read_bytes(), before)
        self.assertFalse(self.host.exists())

    def test_replaced_base_container_identity_refused_before_host(self):
        row = json.loads(self.base_journal.read_bytes())
        row['rootfs_identity'][1] += 1
        self.base_journal.write_text(json.dumps(row))
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse(self.host.exists())
        self.assertFalse((self.root / 'weston-install.json').exists())

    def test_version_failure_retains_private_stage_and_refuses_retries(self):
        def failed(args, **kwargs):
            return subprocess.CompletedProcess(args, 1, b'', b'public fixture loader error')
        with self.assertRaises(ValueError):
            self.run_install(failed)
        self.assertFalse(self.host.exists())
        journal = self.root / 'weston-install.json'
        row = json.loads(journal.read_bytes())
        self.assertEqual(row['phase'], 'INSTALL_UNKNOWN')
        self.assertTrue((self.root / row['stage']).is_dir())
        before = journal.read_bytes()
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual(journal.read_bytes(), before)

    def test_stage_changed_during_version_is_retained_and_never_published(self):
        def changed(args, **kwargs):
            result = self.version(args, **kwargs)
            Path(args[0]).write_bytes(b'public changed stage')
            return result
        with self.assertRaises(ValueError):
            self.run_install(changed)
        self.assertFalse(self.host.exists())
        row = json.loads((self.root / 'weston-install.json').read_bytes())
        self.assertEqual(row['phase'], 'INSTALL_UNKNOWN')
        self.assertEqual((self.root / row['stage'] / 'bin/weston').read_bytes(), b'public changed stage')

    def test_concurrent_user_journal_is_not_overwritten_during_legacy_adoption(self):
        self.run_install()
        (self.root / 'weston-install.json').unlink()
        def changed(args, **kwargs):
            result = self.version(args, **kwargs)
            (self.root / 'weston-install.json').write_bytes(b'public user metadata')
            return result
        with self.assertRaises(ValueError):
            self.run_install(changed)
        self.assertEqual((self.root / 'weston-install.json').read_bytes(), b'public user metadata')

    def test_directory_publication_never_replaces_concurrent_empty_directory(self):
        fd = self.m.base.directory(self.root)
        try:
            (self.root / 'prepared').mkdir(mode=0o700)
            (self.root / 'prepared/file').write_bytes(b'public prepared')
            (self.root / 'concurrent').mkdir(mode=0o700)
            before = self.identity(self.root / 'concurrent')
            with self.assertRaises(FileExistsError):
                self.m.publish_directory(fd, 'prepared', 'concurrent')
            self.assertEqual(self.identity(self.root / 'concurrent'), before)
            self.assertEqual((self.root / 'prepared/file').read_bytes(), b'public prepared')
            self.m.publish_directory(fd, 'prepared', 'published')
            self.assertFalse((self.root / 'prepared').exists())
            self.assertEqual((self.root / 'published/file').read_bytes(), b'public prepared')
        finally:
            os.close(fd)


if __name__ == '__main__':
    unittest.main()
