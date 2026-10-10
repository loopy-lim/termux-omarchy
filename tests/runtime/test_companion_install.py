#!/usr/bin/env python3
"""Preservation and package-boundary checks for the pinned X11 companion."""
import hashlib
import gzip
import importlib.util
import io
import lzma
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'installer'))
MODULE = ROOT / 'installer/companion.py'
spec_loader = importlib.util.spec_from_file_location('companion_under_test', MODULE)
companion = importlib.util.module_from_spec(spec_loader)
spec_loader.loader.exec_module(companion)

PACKAGE = 'termux-x11-nightly'
VERSION = '1.03.01-test-0'
PREFIX = 'data/data/com.termux/files/usr/'
PAYLOAD = {'bin/termux-x11': (b'launch wrapper\n', 0o755),
           'bin/termux-x11-preference': (b'preference wrapper\n', 0o755),
           'libexec/termux-x11/loader.apk': (b'fresh source-built loader\n', 0o400)}
POSTINST = (b'#!/data/data/com.termux/files/usr/bin/sh\n'
            b'chmod 400 /data/data/com.termux/files/usr/libexec/termux-x11/loader.apk\n')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def tar_blob(entries, compression):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:') as archive:
        for name, data, mode in entries:
            row = tarfile.TarInfo(name)
            row.mode = mode
            row.size = len(data)
            archive.addfile(row, io.BytesIO(data))
    # Match the Java source builder, which retains file-type bits in tar modes.
    data = bytearray(output.getvalue())
    position = 0
    for name, contents, mode in entries:
        data[position + 100:position + 108] = f'{mode | stat.S_IFREG:07o}\0'.encode()
        data[position + 148:position + 156] = b' ' * 8
        checksum = sum(data[position:position + 512])
        data[position + 148:position + 156] = f'{checksum:06o}\0 '.encode()
        position += 512 + ((len(contents) + 511) // 512) * 512
    return gzip.compress(data, mtime=0) if compression == 'gz' else lzma.compress(data)


def ar_blob(entries):
    output = bytearray(b'!<arch>\n')
    for name, data in entries:
        output.extend((f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(data):<10}`\n').encode())
        output.extend(data)
        if len(data) % 2:
            output.extend(b'\n')
    return bytes(output)


def deb_blob(*, script=POSTINST, extra_control=None, extra_data=None):
    control = (f'Package: {PACKAGE}\nArchitecture: all\nMaintainer: Termux Omarchy contributors\n'
               f'Version: {VERSION}\nHomepage: https://github.com/loopy-lim/termux-omarchy\n'
               'Depends: xkeyboard-config\nDescription: Termux Omarchy input source alpha companion (Termux:X11 fork)\n').encode()
    control_entries = [('./control', control, 0o644), ('./postinst', script, 0o755)]
    if extra_control:
        control_entries.append(extra_control)
    data_entries = [('./' + PREFIX + name, data, 0o644 if mode == 0o400 else mode)
                    for name, (data, mode) in PAYLOAD.items()]
    if extra_data:
        data_entries.append(extra_data)
    return ar_blob([('debian-binary', b'2.0\n'),
                    ('control.tar.gz', tar_blob(control_entries, 'gz')),
                    ('data.tar.xz', tar_blob(data_entries, 'xz'))])


def manifest(deb):
    return {'schema': 1, 'package': PACKAGE, 'version': VERSION,
            'files': {name: {'bytes': len(data), 'sha256': digest(data), 'mode': mode}
                      for name, (data, mode) in PAYLOAD.items()},
            'deb': {'bytes': len(deb), 'sha256': digest(deb)}}


class CompanionInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='companion-tests-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.prefix = self.root / 'prefix'
        self.prefix.mkdir()
        self.directory = self.root / 'kit'
        (self.directory / 'input').mkdir(parents=True)
        self.deb = deb_blob()
        self.spec = manifest(self.deb)
        self.deb_path = self.directory / 'input/termux-x11-companion.deb'
        self.deb_path.write_bytes(self.deb)
        self.deb_path.chmod(0o600)
        self.installed = {'xkeyboard-config': '2.46-1', 'python': '3.13.9'}

    def write_targets(self):
        for name, (data, mode) in PAYLOAD.items():
            target = self.prefix / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(mode)

    def test_absent_preflight_does_not_create_files(self):
        result = companion.preflight(self.prefix, self.installed, self.spec)
        self.assertEqual(result['status'], 'companion-absent')
        self.assertFalse(result['packageWrites'])
        self.assertEqual(list(self.prefix.iterdir()), [])

    def test_absent_partial_targets_are_preserved(self):
        target = self.prefix / 'bin/termux-x11'
        target.parent.mkdir()
        target.write_bytes(b'old unrelated nightly')
        with self.assertRaisesRegex(ValueError, 'companion-target-exists'):
            companion.preflight(self.prefix, self.installed, self.spec)
        self.assertEqual(target.read_bytes(), b'old unrelated nightly')

    def test_mismatched_installed_version_is_preserved(self):
        self.write_targets()
        before = (self.prefix / 'bin/termux-x11').read_bytes()
        with self.assertRaisesRegex(ValueError, 'companion-version-mismatch'):
            companion.preflight(self.prefix, {PACKAGE: 'arbitrary-nightly'}, self.spec)
        self.assertEqual((self.prefix / 'bin/termux-x11').read_bytes(), before)

    def test_exact_version_and_files_are_accepted(self):
        self.write_targets()
        result = companion.preflight(self.prefix, {PACKAGE: VERSION}, self.spec)
        self.assertEqual(result['status'], 'companion-verified')
        self.assertEqual(result['filesVerified'], 3)

    def test_same_version_changed_bytes_are_preserved(self):
        self.write_targets()
        target = self.prefix / 'bin/termux-x11'
        target.write_bytes(b'changed locally')
        with self.assertRaisesRegex(ValueError, 'companion-file-mismatch'):
            companion.preflight(self.prefix, {PACKAGE: VERSION}, self.spec)
        self.assertEqual(target.read_bytes(), b'changed locally')

    def test_same_version_wrong_final_loader_mode_is_refused(self):
        self.write_targets()
        target = self.prefix / 'libexec/termux-x11/loader.apk'
        target.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'companion-file-mismatch'):
            companion.preflight(self.prefix, {PACKAGE: VERSION}, self.spec)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def test_linked_parent_is_refused_without_touching_destination(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'termux-x11').write_bytes(b'protected')
        (self.prefix / 'bin').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'companion-filesystem'):
            companion.preflight(self.prefix, self.installed, self.spec)
        self.assertEqual((outside / 'termux-x11').read_bytes(), b'protected')

    def test_linked_final_target_is_refused_and_preserved(self):
        outside = self.root / 'protected'
        outside.write_bytes(b'protected')
        (self.prefix / 'bin').mkdir()
        target = self.prefix / 'bin/termux-x11'
        target.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'companion-target-exists'):
            companion.preflight(self.prefix, self.installed, self.spec)
        self.assertTrue(target.is_symlink())
        self.assertEqual(outside.read_bytes(), b'protected')

    def test_unknown_manifest_target_is_refused(self):
        self.spec['files']['../outside'] = self.spec['files'].pop('bin/termux-x11')
        with self.assertRaisesRegex(ValueError, 'companion-spec'):
            companion.preflight(self.prefix, self.installed, self.spec)

    def write_db_status(self, status, version=VERSION):
        path = self.prefix / 'var/lib/dpkg/status'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'Package: {PACKAGE}\nStatus: {status}\nVersion: {version}\n\n')
        path.chmod(0o600)

    def test_removed_and_half_configured_package_states_are_preserved(self):
        for status in ('deinstall ok config-files', 'install ok half-installed',
                       'install ok unpacked', 'install ok half-configured',
                       'install ok triggers-awaited', 'install ok triggers-pending'):
            with self.subTest(status=status):
                self.write_db_status(status)
                before = (self.prefix / 'var/lib/dpkg/status').read_bytes()
                with self.assertRaisesRegex(ValueError, 'companion-package-state-pending'):
                    companion.preflight(self.prefix, self.installed, self.spec)
                self.assertEqual((self.prefix / 'var/lib/dpkg/status').read_bytes(), before)

    def test_leftover_dpkg_maintainer_script_is_preserved(self):
        info = self.prefix / 'var/lib/dpkg/info'
        info.mkdir(parents=True)
        script = info / (PACKAGE + '.postrm')
        script.write_bytes(b'old package cleanup script')
        with self.assertRaisesRegex(ValueError, 'companion-package-metadata-exists'):
            companion.preflight(self.prefix, self.installed, self.spec)
        self.assertEqual(script.read_bytes(), b'old package cleanup script')

    def test_package_database_and_passed_inventory_must_agree(self):
        self.write_db_status('install ok installed')
        with self.assertRaisesRegex(ValueError, 'companion-package-state-changed'):
            companion.preflight(self.prefix, self.installed, self.spec)

    def test_exact_installed_package_database_is_accepted(self):
        self.write_targets()
        self.write_db_status('install ok installed')
        info = self.prefix / 'var/lib/dpkg/info'
        info.mkdir()
        (info / (PACKAGE + '.list')).write_text('installed package files\n')
        result = companion.preflight(self.prefix, {PACKAGE: VERSION}, self.spec)
        self.assertEqual(result['status'], 'companion-verified')

    def test_apply_installs_only_verified_local_deb_then_rechecks(self):
        after = {**self.installed, PACKAGE: VERSION}
        def install(command, **options):
            self.assertEqual(command, [str(self.prefix / 'bin/dpkg'), '--no-triggers', '-i', str(self.deb_path)])
            self.assertEqual(options, {'capture': False, 'timeout': 120})
            self.write_targets()
            return ''
        with patch.object(companion.native, 'installed_packages', side_effect=[self.installed, after]), \
             patch.object(companion.native, 'run', side_effect=install) as run:
            result = companion.apply(self.directory, self.prefix, self.installed, self.spec)
        self.assertEqual(result['status'], 'companion-installed')
        self.assertTrue(result['packageWrites'])
        self.assertEqual(run.call_count, 1)
        companion.preflight(self.prefix, after, self.spec)

    def test_changed_deb_is_refused_before_native_write(self):
        self.deb_path.write_bytes(b'changed archive')
        with patch.object(companion.native, 'run') as run, \
             patch.object(companion.native, 'installed_packages') as query:
            with self.assertRaisesRegex(ValueError, 'companion-deb-mismatch'):
                companion.apply(self.directory, self.prefix, self.installed, self.spec)
        run.assert_not_called()
        query.assert_not_called()
        self.assertEqual(list(self.prefix.iterdir()), [])

    def test_manifest_matching_deb_with_unreviewed_script_is_refused(self):
        data = deb_blob(script=POSTINST + b'touch /private/file\n')
        self.deb_path.write_bytes(data)
        self.spec = manifest(data)
        with patch.object(companion.native, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'companion-deb-control'):
                companion.apply(self.directory, self.prefix, self.installed, self.spec)
        run.assert_not_called()

    def test_extra_package_target_is_refused(self):
        data = deb_blob(extra_data=('./' + PREFIX + 'bin/unreviewed', b'extra', 0o755))
        self.deb_path.write_bytes(data)
        self.spec = manifest(data)
        with patch.object(companion.native, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'companion-deb-data'):
                companion.apply(self.directory, self.prefix, self.installed, self.spec)
        run.assert_not_called()

    def test_extra_maintainer_script_is_refused(self):
        data = deb_blob(extra_control=('./preinst', b'#!/bin/sh\n', 0o755))
        self.deb_path.write_bytes(data)
        self.spec = manifest(data)
        with patch.object(companion.native, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'companion-deb-control'):
                companion.apply(self.directory, self.prefix, self.installed, self.spec)
        run.assert_not_called()

    def test_exact_existing_install_never_runs_dpkg(self):
        self.write_targets()
        with patch.object(companion.native, 'run') as run, \
             patch.object(companion.native, 'installed_packages') as query:
            result = companion.apply(self.directory, self.prefix, {PACKAGE: VERSION}, self.spec)
        self.assertEqual(result['status'], 'companion-verified')
        self.assertFalse(result['packageWrites'])
        run.assert_not_called()
        query.assert_not_called()

    def test_changed_package_state_is_refused_before_dpkg(self):
        with patch.object(companion.native, 'installed_packages', return_value={PACKAGE: 'other'}), \
             patch.object(companion.native, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'companion-package-state-changed'):
                companion.apply(self.directory, self.prefix, self.installed, self.spec)
        run.assert_not_called()

    def test_missing_dependency_is_refused_before_dpkg(self):
        with patch.object(companion.native, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'companion-dependency-missing'):
                companion.apply(self.directory, self.prefix, {}, self.spec)
        run.assert_not_called()

    def test_partial_install_result_is_reported_and_preserved(self):
        def partial_install(*args, **kwargs):
            (self.prefix / 'bin').mkdir()
            (self.prefix / 'bin/termux-x11').write_bytes(PAYLOAD['bin/termux-x11'][0])
            (self.prefix / 'bin/termux-x11').chmod(0o755)
            return ''
        with patch.object(companion.native, 'installed_packages', side_effect=[self.installed,
                {**self.installed, PACKAGE: VERSION}]), \
             patch.object(companion.native, 'run', side_effect=partial_install):
            with self.assertRaisesRegex(ValueError, 'companion-file-missing'):
                companion.apply(self.directory, self.prefix, self.installed, self.spec)
        self.assertEqual((self.prefix / 'bin/termux-x11').read_bytes(), PAYLOAD['bin/termux-x11'][0])


if __name__ == '__main__':
    unittest.main()
