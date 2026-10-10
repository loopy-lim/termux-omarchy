"""Delivery preparation must refuse incomplete, replaced or extra binary inputs."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'installer'))


class DeliveryAssetTests(unittest.TestCase):
    def expected(self, name='input/file'):
        return {name: {'bytes': 8, 'sha256': hashlib.sha256(b'reviewed').hexdigest()}}

    def test_closed_tree_passes_without_modification(self):
        from assets import verify_tree
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'input').mkdir()
            file = root / 'input/file'
            file.write_bytes(b'reviewed')
            before = file.stat()
            self.assertEqual(verify_tree(root, self.expected()), 1)
            self.assertEqual((file.stat().st_ino, file.stat().st_mtime_ns),
                             (before.st_ino, before.st_mtime_ns))

    def test_wrong_bytes_or_extra_file_refused(self):
        from assets import verify_tree
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'input').mkdir()
            file = root / 'input/file'
            file.write_bytes(b'replaced')
            with self.assertRaisesRegex(ValueError, 'delivery-file-hash'):
                verify_tree(root, self.expected())
            file.write_bytes(b'reviewed')
            (root / 'private-data').write_bytes(b'preserve')
            with self.assertRaisesRegex(ValueError, 'delivery-members'):
                verify_tree(root, self.expected())
            self.assertEqual((root / 'private-data').read_bytes(), b'preserve')

    def test_symlink_file_and_parent_refused(self):
        from assets import verify_tree
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            root = parent / 'assets'
            root.mkdir()
            (root / 'input').mkdir()
            other = parent / 'reviewed'
            other.write_bytes(b'reviewed')
            (root / 'input/file').symlink_to(other)
            with self.assertRaises((ValueError, OSError)):
                verify_tree(root, self.expected())
            (root / 'input/file').unlink()
            (root / 'input').rmdir()
            (root / 'input').symlink_to(parent)
            with self.assertRaises((ValueError, OSError)):
                verify_tree(root, self.expected())

    def test_untrusted_paths_and_invalid_hashes_refused(self):
        from assets import validate_entries
        for name in ('../outside', '/outside', 'input/../outside', 'input//file', '.', ''):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_entries(self.expected(name))
        for row in ({'bytes': True, 'sha256': '0' * 64},
                    {'bytes': 8, 'sha256': 'bad'},
                    {'bytes': 8, 'sha256': '0' * 64, 'trust': True}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                validate_entries({'input/file': row})

    def test_package_manager_accepts_only_one_base_apk(self):
        from install import installed_apk_path
        self.assertEqual(str(installed_apk_path('package:/data/app/~~public/app-123/base.apk\n')),
                         '/data/app/~~public/app-123/base.apk')
        for value in ('package:/private/file', 'package:/data/app/../app/base.apk',
                      'package:/data/app/app/base.apk\npackage:/data/app/app/split.apk',
                      'package:/data/app/app/base.apk\nextra'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                installed_apk_path(value)

    def test_platform_apk_hardlinks_require_explicit_exception(self):
        import os
        from assets import verify_file
        with tempfile.TemporaryDirectory() as folder:
            source, link = Path(folder) / 'base.apk', Path(folder) / 'platform-link'
            source.write_bytes(b'reviewed')
            os.link(source, link)
            with self.assertRaisesRegex(ValueError, 'delivery-file-boundary'):
                verify_file(source, self.expected()['input/file'])
            verify_file(source, self.expected()['input/file'], owned=False, platform_links=True)

    def test_only_supported_android_gpu_environment_is_admitted(self):
        from install import check_android_sdk
        check_android_sdk('28\n')
        check_android_sdk('35')
        for value in ('27', '24', 'unknown', '28\n35', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                check_android_sdk(value)

    def test_existing_runtime_is_preserved_before_companion_package_writes(self):
        import install
        import companion
        sys.path.insert(0, str(ROOT / 'runtime'))
        with tempfile.TemporaryDirectory() as folder:
            home, prefix = Path(folder) / 'home', Path(folder) / 'usr'
            home.mkdir()
            prefix.mkdir()
            runtime = home / '.local/share/loopy-omarchy'
            runtime.mkdir(parents=True)
            marker = runtime / 'user-data'
            marker.write_bytes(b'preserve')
            with mock.patch.object(install, 'native_ready', return_value=(home, prefix, {})), \
                    mock.patch.object(companion, 'apply') as apply:
                with self.assertRaisesRegex(ValueError, 'delivery-existing-runtime-preserved'):
                    install.apply_assets(Path(folder), {})
                apply.assert_not_called()
            self.assertEqual(marker.read_bytes(), b'preserve')

    def test_existing_launcher_is_preserved_before_companion_package_writes(self):
        import install
        import companion
        with tempfile.TemporaryDirectory() as folder:
            home, prefix = Path(folder) / 'home', Path(folder) / 'usr'
            home.mkdir()
            (prefix / 'bin').mkdir(parents=True)
            launcher = prefix / 'bin/loopy-omarchy'
            launcher.write_bytes(b'user command')
            with mock.patch.object(install, 'native_ready', return_value=(home, prefix, {})), \
                    mock.patch.object(companion, 'apply') as apply:
                with self.assertRaisesRegex(ValueError, 'delivery-existing-launcher-preserved'):
                    install.apply_assets(Path(folder), {})
                apply.assert_not_called()
            self.assertEqual(launcher.read_bytes(), b'user command')


if __name__ == '__main__':
    unittest.main()
