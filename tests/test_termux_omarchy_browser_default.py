"""Browser-default routing against the actual guest rootfs boundary and journals."""
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
SOURCE = ROOT / 'termux/omarchy_browser_default_install.py'
ENTRY_SCRIPT = ROOT / 'termux/loopy-native-browser'
ENTRY_DESKTOP = ROOT / 'termux/loopy-native-browser.desktop'


def sha(data):
    return hashlib.sha256(data).hexdigest()


class BrowserDefaultTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file() and ENTRY_SCRIPT.is_file() and ENTRY_DESKTOP.is_file())
        sys.path.insert(0, str(SOURCE.parent))
        self.addCleanup(sys.path.remove, str(SOURCE.parent))
        spec = importlib.util.spec_from_file_location('tested_browser_default', SOURCE)
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
        script = self.rootfs / 'usr/local/bin/loopy-native-browser'
        script.parent.mkdir(parents=True, mode=0o700); self.write(script, ENTRY_SCRIPT.read_bytes(), 0o755)
        desktop = self.rootfs / 'home/omarchy/.local/share/applications/loopy-native-browser.desktop'
        desktop.parent.mkdir(parents=True, mode=0o700); self.write(desktop, ENTRY_DESKTOP.read_bytes(), 0o644)
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

    def restore(self):
        return self.m.restore(self.home, self.prefix)

    def mimeapps(self):
        return (self.rootfs / 'home/omarchy/.config/mimeapps.list').read_bytes()

    def inventory(self):
        return {str(p.relative_to(self.rootfs)): (p.lstat().st_ino, p.lstat().st_mode,
                p.lstat().st_mtime_ns, os.readlink(p) if p.is_symlink() else p.read_bytes())
                for p in self.rootfs.rglob('*') if p.is_file() or p.is_symlink()}

    def test_fresh_install_routes_three_keys_with_idempotent_rerun(self):
        result = self.install()
        self.assertEqual(result['phase'], 'INSTALLED')
        content = self.mimeapps()
        for key in self.m.DEFAULT_KEYS:
            self.assertIn(f'{key}=loopy-native-browser.desktop\n'.encode(), content)
        self.assertEqual(json.loads((self.root / 'browser-default.json').read_bytes()), result)
        self.assertEqual(sorted(p.name for p in (self.root / result['backupDirectory']).iterdir()), [])
        before = self.inventory(); row = self.install()
        self.assertEqual(row, result); self.assertEqual(self.inventory(), before)

    def test_existing_defaults_are_replaced_and_other_entries_preserved(self):
        previous = (b'# user mime cache\n[Default Applications]\n'
                    b'x-scheme-handler/http=chromium.desktop\ntext/html=chromium.desktop\n'
                    b'x-scheme-handler/mailto=mutt.desktop\n\n[Added Associations]\n'
                    b'x-scheme-handler/http=firefox.desktop\n')
        config = self.rootfs / 'home/omarchy/.config/mimeapps.list'
        config.parent.mkdir(parents=True, mode=0o700); self.write(config, previous)
        result = self.install()
        self.assertEqual(result['previous']['sha256'], sha(previous))
        content = self.mimeapps()
        self.assertIn(b'x-scheme-handler/http=loopy-native-browser.desktop\n', content)
        self.assertNotIn(b'x-scheme-handler/http=chromium.desktop', content)
        self.assertIn(b'x-scheme-handler/mailto=mutt.desktop\n', content)
        self.assertIn(b'x-scheme-handler/http=firefox.desktop\n', content)
        self.assertEqual(content.count(b'[Default Applications]'), 1)
        backup = self.root / result['backupDirectory'] / 'mimeapps.list'
        self.assertEqual(backup.read_bytes(), previous)
        self.restore()
        self.assertEqual(self.mimeapps(), previous)
        row = json.loads((self.root / 'browser-default.json').read_bytes())
        self.assertEqual(row['phase'], 'RESTORED')
        before = self.inventory(); row = self.install()
        self.assertEqual(row['phase'], 'INSTALLED')
        self.assertEqual(json.loads((self.root / 'browser-default.json').read_bytes()), row)
        self.assertIn(b'x-scheme-handler/http=loopy-native-browser.desktop\n', self.mimeapps())
        self.assertNotEqual(self.inventory(), before)  # rerouting after restore writes new defaults

    def test_missing_or_tampered_entry_point_refuses_without_writes(self):
        (self.rootfs / 'usr/local/bin/loopy-native-browser').unlink()
        with self.assertRaises(ValueError): self.install()
        self.assertFalse((self.root / 'browser-default.json').exists())
        self.write(self.rootfs / 'usr/local/bin/loopy-native-browser', ENTRY_SCRIPT.read_bytes(), 0o700)
        target = self.rootfs / 'home/omarchy/.local/share/applications/loopy-native-browser.desktop'
        original = target.read_bytes()
        self.write(target, original + b'# trailing comment\n', 0o644)
        before = self.inventory()
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(self.inventory(), before)

    def test_duplicate_default_key_is_refused_without_writes(self):
        config = self.rootfs / 'home/omarchy/.config/mimeapps.list'
        config.parent.mkdir(parents=True, mode=0o700)
        self.write(config, b'[Default Applications]\nx-scheme-handler/http=a\nx-scheme-handler/http=b\n')
        before = self.inventory()
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(self.inventory(), before)
        self.assertFalse((self.root / 'browser-default.json').exists())

    def test_missing_trailing_newline_is_not_corrupted_and_comment_header_stays_separate(self):
        config = self.rootfs / 'home/omarchy/.config/mimeapps.list'
        config.parent.mkdir(parents=True, mode=0o700)
        self.write(config, b'# managed by hand\n[Default Applications]\n'
                          b'x-scheme-handler/mailto=mutt.desktop')
        result = self.install()
        content = self.mimeapps()
        self.assertIn(b'x-scheme-handler/mailto=mutt.desktop\n', content)
        self.assertNotIn(b'mutt.desktopx-scheme-handler', content)
        self.assertNotIn(b'hand[Default Applications]', content)
        for key in self.m.DEFAULT_KEYS:
            self.assertIn(f'{key}=loopy-native-browser.desktop\n'.encode(), content)
        self.assertEqual((self.root / result['backupDirectory'] / 'mimeapps.list').read_bytes(),
                         b'# managed by hand\n[Default Applications]\nx-scheme-handler/mailto=mutt.desktop')

    def test_restore_requires_completed_journal_and_exact_state(self):
        with self.assertRaises(ValueError): self.restore()
        self.install()
        routed = self.mimeapps()
        config = self.rootfs / 'home/omarchy/.config/mimeapps.list'
        self.write(config, b'[Default Applications]\nx-scheme-handler/http=other.desktop\n')
        with self.assertRaises(ValueError): self.restore()  # drifted current state is not silently replaced
        self.assertEqual(self.mimeapps(), b'[Default Applications]\nx-scheme-handler/http=other.desktop\n')
        with self.assertRaises(ValueError): self.install()  # a drifted installed journal is terminal evidence
        self.assertEqual(self.mimeapps(), b'[Default Applications]\nx-scheme-handler/http=other.desktop\n')
        self.write(config, routed)  # exact journaled state restores cleanly
        self.assertEqual(self.restore()['phase'], 'RESTORED')
        self.assertEqual(json.loads((self.root / 'browser-default.json').read_bytes())['phase'], 'RESTORED')


if __name__ == '__main__':
    unittest.main()
