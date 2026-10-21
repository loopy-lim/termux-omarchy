"""Private VS Code installation: real archives, filesystem boundaries and preservation."""
import fcntl
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TERMUX = ROOT / 'termux'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    row = path.lstat()
    return [row.st_dev, row.st_ino, row.st_uid]


def snapshot(root):
    result = {}
    for p in [root, *sorted(root.rglob('*'))]:
        s = p.lstat()
        value = os.readlink(p) if p.is_symlink() else sha(p.read_bytes()) if p.is_file() else None
        result[str(p.relative_to(root))] = (s.st_ino, s.st_mode, s.st_mtime_ns, value)
    return result


class VSCodeTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((TERMUX / 'omarchy_vscode_install.py').is_file(), 'private VS Code installer missing')
        self.assertTrue((TERMUX / 'omarchy_vscode_archive.py').is_file(), 'bounded VS Code reader missing')
        sys.path.insert(0, str(TERMUX)); self.addCleanup(sys.path.remove, str(TERMUX))
        self.m = importlib.import_module('omarchy_vscode_install')
        self.a = self.m.archive
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name).resolve()
        self.home, self.prefix = self.folder / 'home', self.folder / 'prefix'
        self.home.mkdir(mode=0o700); self.prefix.mkdir(mode=0o700)
        self.root = self.home / '.local/share/loopy-omarchy'
        self.root.mkdir(parents=True, mode=0o700)
        self.container = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy'
        self.rootfs = self.container / 'rootfs'; self.rootfs.mkdir(parents=True, mode=0o700)
        backend = self.root / 'weston/x11-backend.so'; backend.parent.mkdir(mode=0o700)
        backend.write_bytes(b'public backend'); backend.chmod(0o600)
        patch = mock.patch.multiple(self.m.base, HOST_FILES={'weston/x11-backend.so': 'fixture'},
                                    FILE_SHA={'fixture': sha(backend.read_bytes())})
        patch.start(); self.addCleanup(patch.stop)
        self.record = dict(schema=1, phase='INSTALLED', uid=os.getuid(), root=identity(self.root),
            home=str(self.home), prefix=str(self.prefix), container='loopy-omarchy',
            bundle_sha256=self.m.base.OUTER_SHA, container_identity=identity(self.container),
            rootfs_identity=identity(self.rootfs), managed_files={'weston/x11-backend.so': sha(backend.read_bytes())})
        self.write_json(self.root / 'install.json', self.record)
        guard = self.root / 'proot-guard'; guard.mkdir(mode=0o700)
        artifacts = ROOT / 'build/diagnostics/termux-omarchy-proot-private-runpath-build-20261009-01/arm64-v8a'
        for name, mode in self.m.guard.MODES.items():
            shutil.copyfile(artifacts / name, guard / name); (guard / name).chmod(mode)
        self.write_json(self.root / 'proot-guard.json', dict(schema=1, phase='INSTALLED', uid=os.getuid(),
            root=identity(self.root), directory=identity(guard), files=self.m.guard.FILES))
        self.state = dict(schema=1, uid=os.getuid(), root=identity(self.root), phase='ready',
                          session='public-active-session', prootExitKillRequested=True)
        self.write_json(self.root / 'runtime-state.json', self.state)
        for name in ('install.lock', 'runtime-control.lock'):
            (self.root / name).write_bytes(b''); (self.root / name).chmod(0o600)
        for name in ('opt', 'usr/local/bin', 'usr/share/applications', 'home/omarchy/.config', 'var/lib/pacman/local'):
            (self.rootfs / name).mkdir(parents=True, mode=0o700)
        (self.home / '.zshrc').write_bytes(b'public user profile')
        (self.rootfs / 'home/omarchy/.config/user-settings').write_bytes(b'public user settings')
        (self.rootfs / 'var/lib/pacman/local/fixture').write_bytes(b'public installed packages')
        self.tar = self.folder / 'official-fixture.tar.gz'
        self.release = self.rootfs / 'opt/loopy-vscode/1.141.0'
        self.journal = self.root / self.m.JOURNAL
        self.entries = self.minimum_entries()
        self.make_archive()

    def write_json(self, path, value):
        path.write_text(json.dumps(value)); path.chmod(0o600)

    def minimum_entries(self):
        elf = b'\x7fELF\x02\x01\x01' + bytes(11) + b'\xb7\x00' + bytes(44)
        return [('code', elf, 0o755), ('bin/code', b'#!/bin/sh\nexit 0\n', 0o755),
            ('resources/app/package.json', json.dumps({'version': self.a.VERSION}).encode(), 0o664),
            ('resources/app/product.json', json.dumps({'version': self.a.VERSION, 'commit': self.a.COMMIT}).encode(), 0o664),
            ('resources/app/resources/linux/code.png', b'public image fixture', 0o664)]

    def make_archive(self, extra=()):
        with tarfile.open(self.tar, 'w:gz') as out:
            root = tarfile.TarInfo(self.a.TOP); root.type = tarfile.DIRTYPE; root.mode = 0o775; out.addfile(root)
            dirs = sorted({str(p) for name, _, _ in self.entries for p in Path(name).parents if str(p) != '.'}, key=lambda x: (x.count('/'), x))
            for name in dirs:
                row = tarfile.TarInfo(self.a.TOP + '/' + name); row.type = tarfile.DIRTYPE; row.mode = 0o775; out.addfile(row)
            for name, data, mode in self.entries:
                row = tarfile.TarInfo(self.a.TOP + '/' + name); row.size = len(data); row.mode = mode
                out.addfile(row, io.BytesIO(data))
            for row, data in extra:
                out.addfile(row, io.BytesIO(data) if data is not None else None)
        self.tar.chmod(0o600)
        for name, value in [('SHA256', sha(self.tar.read_bytes())), ('BYTES', self.tar.stat().st_size)]:
            p = mock.patch.object(self.a, name, value); p.start(); self.addCleanup(p.stop)

    def install(self):
        return self.m.install(self.tar, self.home, self.prefix)

    def reject_unchanged(self):
        before = snapshot(self.home), snapshot(self.prefix)
        with self.assertRaises((ValueError, OSError, tarfile.TarError)):
            self.install()
        self.assertEqual((snapshot(self.home), snapshot(self.prefix)), before)

    def test_first_install_preserves_active_session_profiles_packages_and_base(self):
        originals = {p: snapshot(p) for p in [self.rootfs / 'home', self.rootfs / 'var/lib/pacman', self.home / '.local/share/loopy-omarchy/weston']}
        state, base = (self.root / 'runtime-state.json').read_bytes(), (self.root / 'install.json').read_bytes()
        row = self.install()
        self.assertEqual(row['phase'], 'INSTALLED'); self.assertEqual(row['version'], '1.141.0')
        self.assertEqual(row, json.loads(self.journal.read_bytes()))
        for p, expected in originals.items(): self.assertEqual(snapshot(p), expected)
        self.assertEqual((self.root / 'runtime-state.json').read_bytes(), state)
        self.assertEqual((self.root / 'install.json').read_bytes(), base)
        self.assertEqual((self.release / 'resources/app/package.json').read_bytes(), self.entries[2][1])
        self.assertFalse((self.release / 'data/tmp').exists(), 'official CLI overrides TMPDIR when this exists')
        self.assertEqual(stat.S_IMODE((self.release / 'code').stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.release / 'resources/app/package.json').stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.journal.stat().st_mode), 0o600)
        self.assertTrue((self.rootfs / 'usr/local/bin/loopy-vscode').is_file())
        self.assertFalse((self.rootfs / 'usr/bin/code').exists())

    def test_repeat_preserves_mutable_portable_data_and_all_mtimes(self):
        row = self.install()
        (self.release / 'data/user-data/public-settings').write_bytes(b'public changed app settings')
        before = snapshot(self.home), snapshot(self.prefix)
        self.assertEqual(self.install(), row)
        self.assertEqual((snapshot(self.home), snapshot(self.prefix)), before)

    def test_wrong_hash_size_and_source_link_are_rejected_before_writes(self):
        with mock.patch.object(self.a, 'SHA256', '0' * 64): self.reject_unchanged()
        with mock.patch.object(self.a, 'BYTES', self.tar.stat().st_size + 1): self.reject_unchanged()
        other = self.tar.with_suffix('.real'); self.tar.rename(other); self.tar.symlink_to(other)
        self.reject_unchanged()

    def test_unsafe_paths_duplicate_specials_and_hardlinks_rejected(self):
        for name, kind, target in [('VSCode-linux-arm64/../outside', tarfile.REGTYPE, ''),
             ('/absolute', tarfile.REGTYPE, ''), ('other/code', tarfile.REGTYPE, ''),
             ('VSCode-linux-arm64/code', tarfile.REGTYPE, ''),
             ('VSCode-linux-arm64/fifo', tarfile.FIFOTYPE, ''),
             ('VSCode-linux-arm64/hard', tarfile.LNKTYPE, 'VSCode-linux-arm64/code')]:
            with self.subTest(name=name):
                row = tarfile.TarInfo(name); row.type = kind; row.linkname = target
                self.make_archive([(row, b'' if row.isfile() else None)]); self.reject_unchanged()

    def test_symlink_escape_cycle_dangling_and_parent_traversal_rejected(self):
        for name, target in [('outside', '../../outside'), ('absolute', '/etc/passwd'),
                             ('cycle', 'cycle'), ('missing', 'missing-target'), ('bin', '.')]:
            with self.subTest(target=target):
                row = tarfile.TarInfo(self.a.TOP + '/' + name); row.type = tarfile.SYMTYPE; row.linkname = target
                self.make_archive([(row, None)]); self.reject_unchanged()

    def test_internal_symlink_is_preserved_and_checked_without_following(self):
        row = tarfile.TarInfo(self.a.TOP + '/code-link'); row.type = tarfile.SYMTYPE; row.linkname = 'code'
        self.make_archive([(row, None)]); self.install()
        self.assertEqual(os.readlink(self.release / 'code-link'), 'code')
        (self.release / 'code-link').unlink(); (self.release / 'code-link').symlink_to('/etc/passwd')
        self.reject_unchanged()

    def test_archive_budgets_and_wrong_architecture_version_are_rejected(self):
        for key, value in [('MAX_MEMBERS', 2), ('MAX_FILE', 3), ('MAX_EXPANDED', 64)]:
            with mock.patch.object(self.a, key, value): self.reject_unchanged()
        self.entries[0] = ('code', b'wrong architecture', 0o755); self.make_archive(); self.reject_unchanged()
        self.entries = self.minimum_entries(); self.entries[2] = ('resources/app/package.json', b'{"version":"0"}', 0o664)
        self.make_archive(); self.reject_unchanged()

    def test_unknown_version_parent_or_stage_is_preserved(self):
        for leaf in ['1.141.0', '.stage-public', 'other-version']:
            p = self.rootfs / 'opt/loopy-vscode' / leaf; p.mkdir(parents=True, mode=0o700)
            (p / 'public-file').write_bytes(b'keep'); self.reject_unchanged(); shutil.rmtree(p)
        (self.rootfs / 'opt/loopy-vscode').rmdir()

    def test_existing_launcher_and_desktop_are_never_replaced(self):
        for name in ['usr/local/bin/loopy-vscode', 'usr/share/applications/loopy-vscode.desktop']:
            p = self.rootfs / name; p.write_bytes(b'public existing'); self.reject_unchanged(); p.unlink()

    def test_symlink_parent_never_writes_outside(self):
        outside = self.folder / 'outside'; outside.mkdir(mode=0o700)
        (self.rootfs / 'opt/loopy-vscode').symlink_to(outside)
        self.reject_unchanged(); self.assertEqual(list(outside.iterdir()), [])

    def test_missing_guard_wrong_uid_root_and_base_are_rejected(self):
        for key, value in [('uid', os.getuid() + 1), ('root', [0, 0, 0]), ('phase', 'NEW')]:
            self.write_json(self.root / 'install.json', dict(self.record, **{key: value})); self.reject_unchanged()
        self.write_json(self.root / 'install.json', self.record)
        shutil.rmtree(self.root / 'proot-guard'); (self.root / 'proot-guard.json').unlink()
        self.reject_unchanged()

    def test_either_lock_rejects_without_any_file_changes(self):
        for name in ['install.lock', 'runtime-control.lock']:
            with (self.root / name).open('r+b') as fd:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); self.reject_unchanged()

    def test_changed_installed_file_mode_extra_and_journal_refuse_adoption(self):
        self.install()
        binary = self.release / 'code'; old = binary.read_bytes(); binary.write_bytes(b'changed'); self.reject_unchanged()
        binary.write_bytes(old); binary.chmod(0o755); self.reject_unchanged(); binary.chmod(0o700)
        extra = self.release / 'unexpected'; extra.write_bytes(b'keep'); self.reject_unchanged(); extra.unlink()
        value = json.loads(self.journal.read_bytes()); value['root'] = [0, 0, 0]; self.write_json(self.journal, value); self.reject_unchanged()

    def test_partial_failure_is_preserved_and_retry_refused(self):
        with mock.patch.object(self.m.host, 'publish_directory', side_effect=OSError('public publish failure')):
            with self.assertRaises(OSError): self.install()
        self.assertTrue(any((self.rootfs / 'opt/loopy-vscode').iterdir()))
        self.reject_unchanged()

    def test_private_data_symlink_and_support_mutation_are_rejected(self):
        self.install()
        data = self.release / 'data'; data.rename(self.release / 'data-original'); data.symlink_to(self.folder)
        self.reject_unchanged()

    def test_wrapper_preserves_arguments_exit_and_private_environment(self):
        code = self.folder / 'code'; code.write_text('#!/bin/sh\npython3 -c \'import json,os,sys; print(json.dumps({"args":sys.argv[1:],"pulse":os.environ["PULSE_SERVER"],"tmp":os.environ["TMPDIR"]}))\' "$@"\nexit 17\n'); code.chmod(0o700)
        wrapper = self.folder / 'launch'; text = (TERMUX / 'loopy-vscode').read_text()
        text = text.replace('/opt/loopy-vscode/1.141.0/bin/code', str(code)); wrapper.write_text(text); wrapper.chmod(0o700)
        args = ['file with spaces', ';touch public-marker', '']
        result = subprocess.run([str(wrapper), *args], text=True, capture_output=True)
        self.assertEqual(result.returncode, 17, result.stderr)
        got = json.loads(result.stdout); self.assertEqual(got['args'][-3:], args)
        self.assertIn('--no-sandbox', got['args']); self.assertIn('--ozone-platform=wayland', got['args'])
        self.assertEqual(got['pulse'], 'unix:/run/user/1000/pulse/native')
        self.assertEqual(got['tmp'], '/run/user/1000')


if __name__ == '__main__': unittest.main()
