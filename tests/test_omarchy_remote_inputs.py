"""APK build inputs must retain signed package provenance and the source helper copies."""
from pathlib import Path
import json
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OmarchyRemoteInputsTests(unittest.TestCase):
    def test_actual_cache_sources_and_producer_are_verified_before_packaging(self):
        receipt = json.loads((ROOT / 'android/assets/omarchy-remote-client.provenance.json').read_text())
        self.assertTrue('trusted_icons' in receipt, 'signed public raw icon caches are missing')
        self.assertEqual(set(receipt['trusted_icons']['themes']), {'Adwaita', 'hicolor'})
        from tools.omarchy_remote_inputs import checked_inputs
        paths = checked_inputs(ROOT)
        self.assertIn(ROOT / 'tools/omarchy_remote_icons.py', paths)

    def test_actual_remote_assets_are_verified_and_included_as_build_inputs(self):
        self.assertTrue((ROOT / 'tools/omarchy_remote_inputs.py').is_file(), 'remote client build verification is missing')
        from tools.omarchy_remote_inputs import checked_inputs
        paths = checked_inputs(ROOT)
        self.assertIn(ROOT / 'android/assets/omarchy-remote-client.tar.gz', paths)
        self.assertIn(ROOT / 'guest/desktop/usr/local/lib/loopy/remote_connections.py', paths)
        self.assertIn(ROOT / 'third_party/omarchy-remote-signing-key.asc', paths)

    def test_stale_derived_helper_is_rejected_before_packaging(self):
        self.assertTrue((ROOT / 'tools/omarchy_remote_inputs.py').is_file(), 'remote client build verification is missing')
        from tools.omarchy_remote_inputs import checked_sources
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for directory in ('android/assets/omarchy-bridge', 'guest/desktop/usr/local/lib/loopy'):
                (root / directory).mkdir(parents=True)
                for name in ('remote_connections.py', 'remote_desktop.py'):
                    shutil.copyfile(ROOT / 'guest/desktop/usr/local/lib/loopy' / name, root / directory / name)
            path = root / 'android/assets/omarchy-bridge/remote_connections.py'
            original = path.read_bytes(); path.write_bytes(original + b'\n# stale\n')
            with self.assertRaises(ValueError): checked_sources(root)
            self.assertEqual(path.read_bytes(), original + b'\n# stale\n')

    def test_native_library_resolution_rejects_missing_or_cyclic_inputs(self):
        from tools.omarchy_remote_elf import resolve_library
        base = {'usr/lib/libc.so.6': {'kind': 'file'}}
        self.assertEqual(resolve_library('libc.so.6', {}, base), 'usr/lib/libc.so.6')
        with self.assertRaises(ValueError): resolve_library('libvncclient.so.1', {}, base)
        cycle = {'usr/lib/libvncclient.so.1': {'kind': 'symlink', 'target': 'usr/lib/libvncclient.so.1'}}
        with self.assertRaises(ValueError): resolve_library('libvncclient.so.1', cycle, base)


if __name__ == '__main__':
    unittest.main()
