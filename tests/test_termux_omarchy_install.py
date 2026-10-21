"""Real archive/file/journal boundaries; only the external PRoot install is doubled.

ROOT owns execution. The tiny trusted fixture replaces immutable release pins in
memory for these tests; the production CLI must not accept caller supplied pins.
"""
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

SOURCE = Path(__file__).resolve().parents[1] / 'termux' / 'omarchy_install.py'
RUNTIME_FILES = ('omarchy.py', 'processes.py', 'omarchy_runtime.py', 'omarchy_resources.py',
                 'omarchy_boot.py', 'omarchy_input.py', 'omarchy_audio.py',
                 'omarchy_android.py', 'omarchy_android_client.py', 'omarchy_commands.py', 'omarchy_proot.py')


def digest(data):
    return hashlib.sha256(data).hexdigest()


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'declarative Omarchy install feature missing')
        spec = importlib.util.spec_from_file_location('tested_omarchy_install', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.home, self.prefix = self.base / 'home', self.base / 'prefix'
        self.home.mkdir(mode=0o700)
        self.prefix.mkdir(mode=0o700)
        (self.prefix / 'bin').mkdir()
        for name in ('proot-distro', 'dpkg-query'):
            tool = self.prefix / 'bin' / name
            tool.write_text('#!/bin/sh\nexit 0\n')
            tool.chmod(0o700)
        self.root = self.home / '.local/share/loopy-omarchy'
        self.container = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy'
        self.packages = b'aquamarine 0.14.0-2\nchromium 151.0.7922.137-1\nhyprland 0.56.1-3\nmesa 1:26.2.1-1\nquickshell 0.3.1-1\n'
        inner = io.BytesIO()
        with tarfile.open(fileobj=inner, mode='w:xz') as archive:
            link = tarfile.TarInfo('bin')
            link.type, link.linkname = tarfile.SYMTYPE, '/usr/bin'
            archive.addfile(link)
        self.files = {
            'rootfs.tar.xz': inner.getvalue(),
            'manifest/packages-aarch64-0.1.1.lock': self.packages,
            'host/opt/weston/lib/libweston-14/x11-backend.so': b'public fixed backend',
            'host/bin/omarchy-process-guard': b'unexecuted upstream guard',
            'host/bin/omarchy-x11-keyboard': b'unexecuted upstream keyboard',
            'host/share/licenses/omarchy-android/LICENSE': b'public license A',
            'host/share/licenses/weston/COPYING': b'public license B',
        }
        self.fields = {
            'format': '1', 'version': '0.1.1', 'architecture': 'aarch64',
            'rootfs': 'rootfs.tar.xz', 'components_lock_sha256': '4' * 64,
            'patches_lock_sha256': '5' * 64, 'artifacts_lock_sha256': '6' * 64,
            'packages_lock_sha256': digest(self.packages),
            'host_artifact_sha256': '7' * 64, 'host_source_bundle_sha256': '8' * 64,
        }
        self.files['BUNDLE-MANIFEST'] = ''.join(k + '=' + v + '\n' for k, v in self.fields.items()).encode()
        self.pins = {name: digest(data) for name, data in self.files.items()}
        self.files['SHA256SUMS'] = ''.join(value + '  ./' + name + '\n' for name, value in self.pins.items()).encode()
        self.archive = self.make_archive('bundle.tar', self.files)
        self.patch = mock.patch.multiple(self.m, OUTER_SHA=digest(self.archive.read_bytes()),
                                        OUTER_BYTES=self.archive.stat().st_size,
                                        FILE_SHA=self.pins, MANIFEST_FIELDS=self.fields)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.calls = []

    def make_archive(self, name, files, extra=None):
        path = self.base / name
        with tarfile.open(path, 'w:') as archive:
            for key, data in files.items():
                row = tarfile.TarInfo('./' + key)
                row.size, row.mode = len(data), 0o600
                archive.addfile(row, io.BytesIO(data))
            if extra is not None:
                archive.addfile(extra)
        path.chmod(0o600)
        return path

    def use_archive(self, path):
        self.m.OUTER_SHA, self.m.OUTER_BYTES = digest(path.read_bytes()), path.stat().st_size

    def proot(self, args, **kwargs):
        self.calls.append(args)
        self.assertFalse(kwargs.get('shell', False))
        if len(args) == 2 and args[1] == '--version':
            self.fail('PRoot-Distro has no --version operation; query the installed package')
        if args[0] == str(self.prefix / 'bin/dpkg-query'):
            self.assertEqual(args[1:], ['-W', '-f=${Version}', 'proot-distro'])
            return subprocess.CompletedProcess(args, 0, '5.8.0\n', '')
        self.assertEqual(args[0], str(self.prefix / 'bin/proot-distro'))
        self.assertEqual(args[1:6], ['install', '--name', 'loopy-omarchy', '--architecture', 'aarch64'])
        self.assertEqual(Path(args[6]), self.root / 'bundle/rootfs.tar.xz')
        self.assertEqual(kwargs['env']['TERMUX__PREFIX'], str(self.prefix))
        self.container.mkdir(parents=True, mode=0o700)
        (self.container / 'rootfs').mkdir(mode=0o700)
        return subprocess.CompletedProcess(args, 0)

    def run_install(self, runner=None):
        with mock.patch.object(self.m.subprocess, 'run', runner or self.proot):
            return self.m.install(self.archive, self.home, self.prefix)

    def test_runtime_publication_never_replaces_a_concurrent_file_or_symlink(self):
        source, target = self.base / 'reviewed', self.base / 'concurrent'
        source.write_bytes(b'reviewed native source')
        target.write_bytes(b'concurrent user file')
        fd = self.m.directory(self.base)
        try:
            with self.assertRaises(FileExistsError):
                self.m.publish(fd, source.name, target.name)
            self.assertEqual(target.read_bytes(), b'concurrent user file')
            target.unlink()
            target.symlink_to(source)
            with self.assertRaises(FileExistsError):
                self.m.publish(fd, source.name, target.name)
            self.assertTrue(target.is_symlink())
            self.assertEqual(source.read_bytes(), b'reviewed native source')
        finally:
            os.close(fd)

    def test_valid_bundle_creates_only_named_container_and_backend(self):
        user = self.home / 'user-profile.txt'
        user.write_bytes(b'user data')
        other = self.prefix / 'var/lib/proot-distro/containers/user-container'
        other.mkdir(parents=True)
        result = self.run_install()
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(user.read_bytes(), b'user data')
        self.assertTrue(other.is_dir())
        self.assertEqual((self.root / 'weston/x11-backend.so').read_bytes(), self.files['host/opt/weston/lib/libweston-14/x11-backend.so'])
        self.assertFalse((self.root / 'bin').exists())
        self.assertFalse((self.root / 'bundle/bin').exists(), 'guest absolute symlink must never be host extracted')
        self.assertTrue(result['browser_linux_sandbox_disabled_in_bundle'])
        self.assertFalse(result['browser_launched'])

    def test_changed_outer_bytes_refused_before_targets(self):
        with self.archive.open('ab') as out:
            out.write(b'x')
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertFalse(self.root.exists())
        self.assertEqual(self.calls, [])

    def test_outer_traversal_absolute_and_link_members_refused(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/escape', tarfile.REGTYPE),
                           ('host/link', tarfile.SYMTYPE), ('host/link', tarfile.LNKTYPE)]:
            with self.subTest(name=name, kind=kind):
                row = tarfile.TarInfo(name)
                row.type, row.linkname = kind, '/user-profile.txt'
                bad = self.make_archive('bad.tar', self.files, row)
                self.use_archive(bad)
                with self.assertRaises(ValueError):
                    self.m.install(bad, self.home, self.prefix)
                self.assertFalse(self.root.exists())

    def test_package_closure_or_checksum_change_refused(self):
        for changed in [dict(self.files, **{'manifest/packages-aarch64-0.1.1.lock': b'hyprland wrong\n'}),
                        dict(self.files, SHA256SUMS=b'0' * 64 + b'  ./rootfs.tar.xz\n')]:
            bad = self.make_archive('bad.tar', changed)
            self.use_archive(bad)
            with self.assertRaises(ValueError):
                self.m.install(bad, self.home, self.prefix)
            self.assertFalse(self.root.exists())

    def test_existing_unowned_container_or_managed_root_never_adopted(self):
        self.container.mkdir(parents=True)
        marker = self.container / 'user'
        marker.write_bytes(b'keep')
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual(marker.read_bytes(), b'keep')
        self.assertEqual(self.calls, [])
        self.container.rename(self.container.with_name('user-container'))
        self.root.mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual(self.calls, [])

    def test_unknown_install_keeps_new_targets_and_refuses_retry(self):
        def partial(args, **kwargs):
            if args[0] == str(self.prefix / 'bin/dpkg-query'):
                return self.proot(args, **kwargs)
            self.proot(args, **kwargs)
            raise subprocess.TimeoutExpired(args, 1)
        with self.assertRaises(ValueError):
            self.run_install(partial)
        saved = json.loads((self.root / 'install.json').read_text())
        self.assertEqual(saved['phase'], 'INSTALL_UNKNOWN')
        self.assertTrue(self.container.is_dir())
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual(json.loads((self.root / 'install.json').read_text())['phase'], 'INSTALL_UNKNOWN')

    def test_install_log_is_owned_closed_and_bound_by_receipt(self):
        note = b'fixed public extraction result\n'
        saved = []
        def logging(args, **kwargs):
            if args[0] == str(self.prefix / 'bin/dpkg-query'):
                return self.proot(args, **kwargs)
            out = kwargs.get('stdout')
            self.assertTrue(hasattr(out, 'fileno'), 'owned install log missing')
            self.assertIs(kwargs['stderr'], out)
            self.assertEqual(os.fstat(out.fileno()).st_uid, os.getuid())
            self.assertEqual(os.fstat(out.fileno()).st_mode & 0o777, 0o600)
            out.write(note)
            saved.append(out)
            return self.proot(args, **kwargs)
        result = self.run_install(logging)
        self.assertTrue(saved[0].closed)
        path = self.root / 'proot-install.log'
        self.assertEqual(path.read_bytes(), note)
        self.assertEqual(result['install_exit_code'], 0)
        self.assertEqual(result['install_log_sha256'], digest(note))
        self.assertEqual(result['install_log_size'], len(note))

    def test_completed_install_idempotent_but_modified_backend_refused(self):
        self.run_install()
        count = len(self.calls)
        self.assertEqual(self.run_install()['phase'], 'INSTALLED')
        self.assertEqual(len(self.calls), count)
        (self.root / 'weston/x11-backend.so').write_bytes(b'user modification')
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual((self.root / 'weston/x11-backend.so').read_bytes(), b'user modification')

    def test_parent_symlink_refused_without_touching_target(self):
        external = self.base / 'external'
        external.mkdir()
        (self.home / '.local').symlink_to(external, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.run_install()
        self.assertEqual(list(external.iterdir()), [])

    def sources(self):
        target = self.base / 'sources'
        target.mkdir(mode=0o700)
        for name in RUNTIME_FILES:
            (target / name).write_bytes((SOURCE.parent / name).read_bytes())
            (target / name).chmod(0o600)
        return target

    def with_sources(self, sources):
        self.assertTrue(hasattr(self.m, 'RuntimeSources'), 'runtime source deployment is missing')
        with mock.patch.object(self.m.subprocess, 'run', self.proot):
            return self.m.install(self.archive, self.home, self.prefix, sources=sources)

    def test_fresh_install_has_a_callable_native_runtime_dependency_closure(self):
        result = self.run_install()
        self.assertTrue((self.root / 'omarchy.py').is_file(), 'installed bundle has no native launcher')
        child = subprocess.run([sys.executable, '-I', '-c',
                                'import sys;sys.path.insert(0,sys.argv[1]);'
                                'import omarchy,omarchy_runtime,omarchy_input;'
                                'print("Y900_INSTALLED_RUNTIME_IMPORT_OK")', str(self.root)],
                               capture_output=True, text=True, timeout=5)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(child.stdout.strip(), 'Y900_INSTALLED_RUNTIME_IMPORT_OK')
        self.assertEqual(set(result['runtime_files']), set(RUNTIME_FILES))

    def test_missing_source_is_rejected_before_any_bundle_install(self):
        sources = self.sources(); (sources / 'omarchy_audio.py').unlink()
        self.assertTrue(hasattr(self.m, 'RuntimeSources'), 'runtime source deployment is missing')
        with self.assertRaises(ValueError): self.with_sources(sources)
        self.assertFalse(self.root.exists())
        self.assertEqual(self.calls, [])

    def test_changed_or_symlinked_source_is_rejected_before_targets(self):
        sources = self.sources(); target = sources / 'omarchy_android.py'
        target.write_bytes(b'public user modification')
        self.assertTrue(hasattr(self.m, 'RuntimeSources'), 'runtime source deployment is missing')
        with self.assertRaises(ValueError): self.with_sources(sources)
        self.assertFalse(self.root.exists())
        target.unlink(); target.symlink_to(SOURCE.parent / 'omarchy_android.py')
        with self.assertRaises(ValueError): self.with_sources(sources)
        self.assertFalse(self.root.exists())

    def test_existing_modified_runtime_is_preserved_and_other_sources_are_not_added(self):
        self.run_install()
        target = self.root / 'omarchy.py'
        target.write_bytes(b'public modified launcher')
        missing = self.root / 'omarchy_audio.py'
        if missing.exists(): missing.unlink()
        self.assertTrue(hasattr(self.m, 'RuntimeSources'), 'runtime source deployment is missing')
        with self.assertRaises(ValueError): self.with_sources(self.sources())
        self.assertEqual(target.read_bytes(), b'public modified launcher')
        self.assertFalse(missing.exists())

    def test_identical_runtime_sources_do_not_change_inodes_on_reinstall(self):
        self.run_install()
        self.assertTrue((self.root / 'omarchy.py').is_file(), 'native launcher missing')
        before = {name: (self.root / name).stat().st_ino for name in RUNTIME_FILES}
        self.run_install()
        self.assertEqual(before, {name: (self.root / name).stat().st_ino for name in RUNTIME_FILES})

    def test_missing_runtime_source_is_not_added_to_a_running_session(self):
        self.run_install()
        missing = self.root / 'omarchy_input.py'; missing.unlink()
        (self.root / 'runtime-state.json').write_text(json.dumps({'phase': 'ready',
                                                                'terminationConfirmed': False}))
        with self.assertRaises(ValueError): self.with_sources(self.sources())
        self.assertFalse(missing.exists())

    def test_missing_runtime_source_can_be_added_after_confirmed_stop(self):
        self.run_install()
        missing = self.root / 'omarchy_input.py'; missing.unlink()
        (self.root / 'runtime-state.json').write_text(json.dumps({'phase': 'stopped',
                                                                'terminationConfirmed': True}))
        before = (self.root / 'omarchy.py').stat().st_ino
        self.with_sources(self.sources())
        self.assertEqual(missing.read_bytes(), (SOURCE.parent / 'omarchy_input.py').read_bytes())
        self.assertEqual((self.root / 'omarchy.py').stat().st_ino, before)


if __name__ == '__main__':
    unittest.main()
