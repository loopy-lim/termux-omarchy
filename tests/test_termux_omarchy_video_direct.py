"""Video-direct launcher installation against the actual guest rootfs boundary."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'termux/omarchy_video_direct_install.py'
SCRIPT = ROOT / 'termux/loopy-video-direct'
DESKTOP = ROOT / 'termux/loopy-video-direct.desktop'


def sha(data):
    return hashlib.sha256(data).hexdigest()


class VideoDirectTests(unittest.TestCase):
    def setUp(self):
        for path in (SOURCE, SCRIPT, DESKTOP):
            self.assertTrue(path.is_file(), path.name + ' missing')
        sys.path.insert(0, str(SOURCE.parent))
        self.addCleanup(sys.path.remove, str(SOURCE.parent))
        spec = importlib.util.spec_from_file_location('tested_video_direct', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name).resolve()
        self.home, self.prefix = self.folder / 'home', self.folder / 'prefix'
        self.home.mkdir(mode=0o700); self.prefix.mkdir(mode=0o700)
        self.root = self.home / '.local/share/loopy-omarchy'
        self.root.mkdir(parents=True, mode=0o700)
        self.rootfs = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy/rootfs'
        self.rootfs.mkdir(parents=True, mode=0o700)
        for target in ('install.lock', 'runtime-control.lock'): self.write(self.root / target, b'')
        backend = self.root / 'weston/x11-backend.so'
        backend.parent.mkdir(mode=0o700); self.write(backend, b'public backend')
        guard = self.root / 'proot-guard'; guard.mkdir(mode=0o700)
        guard_files = {'proot': b'public guard', 'loader': b'public loader',
                       'libandroid-shmem.so': b'public shmem'}
        for name, data in guard_files.items():
            self.write(guard / name, data, 0o600 if name.endswith('.so') else 0o700)
        guard_pins = {name: sha(data) for name, data in guard_files.items()}
        self.write_json(self.root / 'proot-guard.json', dict(schema=1, phase='INSTALLED',
            uid=os.getuid(), root=self.identity(self.root), directory=self.identity(guard), files=guard_pins))
        self.installed = {'schema': 1, 'phase': 'INSTALLED', 'uid': os.getuid(),
            'root': self.identity(self.root), 'home': str(self.home), 'prefix': str(self.prefix),
            'container': 'loopy-omarchy', 'bundle_sha256': self.m.base.OUTER_SHA,
            'container_identity': self.identity(self.rootfs.parent),
            'rootfs_identity': self.identity(self.rootfs),
            'managed_files': {'weston/x11-backend.so': sha(b'public backend')}}
        self.write_json(self.root / 'install.json', self.installed)
        for patch in (mock.patch.multiple(self.m.base, RUNTIME_SHA={},
                HOST_FILES={'weston/x11-backend.so': 'fixture'}, FILE_SHA={'fixture': sha(b'public backend')}),
                mock.patch.object(self.m.guard, 'FILES', guard_pins)):
            patch.start(); self.addCleanup(patch.stop)

    @staticmethod
    def identity(path):
        value = path.lstat(); return [value.st_dev, value.st_ino, value.st_uid]

    @staticmethod
    def write(path, data, mode=0o600):
        path.write_bytes(data); path.chmod(mode)

    def write_json(self, path, value):
        self.write(path, json.dumps(value, sort_keys=True).encode())

    def install(self):
        return self.m.install(self.home, self.prefix)

    def inventory(self):
        return {str(p.relative_to(self.rootfs)): (p.lstat().st_ino, p.lstat().st_mode,
                p.lstat().st_mtime_ns, os.readlink(p) if p.is_symlink() else p.read_bytes())
                for p in self.rootfs.rglob('*') if p.is_file() or p.is_symlink()}

    def test_fresh_install_publishes_both_entry_points_with_idempotent_rerun(self):
        result = self.install()
        self.assertEqual(result['phase'], 'INSTALLED')
        script = self.rootfs / 'usr/local/bin/loopy-video-direct'
        desktop = self.rootfs / 'home/omarchy/.local/share/applications/loopy-video-direct.desktop'
        self.assertEqual(script.read_bytes(), SCRIPT.read_bytes())
        self.assertEqual(desktop.read_bytes(), DESKTOP.read_bytes())
        self.assertEqual(script.stat().st_mode & 0o777, 0o755)
        self.assertEqual(desktop.stat().st_mode & 0o777, 0o644)
        self.assertEqual(json.loads((self.root / 'video-direct.json').read_bytes()), result)
        before = self.inventory(); row = self.install()
        self.assertEqual(row, result); self.assertEqual(self.inventory(), before)

    def test_existing_entry_point_is_preserved_and_refuses(self):
        target = self.rootfs / 'usr/local/bin/loopy-video-direct'
        target.parent.mkdir(parents=True, mode=0o700)
        self.write(target, SCRIPT.read_bytes(), 0o755)
        before = self.inventory()
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(self.inventory(), before)
        self.assertFalse((self.root / 'video-direct.json').exists())

    def test_tampered_installed_entry_point_refuses_idempotent_rerun(self):
        result = self.install()
        target = self.rootfs / 'usr/local/bin/loopy-video-direct'
        original = target.read_bytes()
        self.write(target, original + b'\n# tampered\n', 0o755)
        with self.assertRaises(ValueError): self.install()
        self.write(target, original, 0o755)
        before = self.inventory()
        row = self.install()
        self.assertEqual(row, result)
        self.assertEqual(self.inventory(), before)


if __name__ == '__main__':
    unittest.main()
