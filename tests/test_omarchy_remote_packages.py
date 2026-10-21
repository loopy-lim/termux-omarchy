"""A remote extension must add clients without replacing the installed Arch transaction."""
import importlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OmarchyRemotePackagesTests(unittest.TestCase):
    def test_complete_remote_closure_preserves_all_installed_package_identities(self):
        self.assertTrue((ROOT / 'tools/prepare_omarchy_remote.py').is_file(), 'verified Omarchy remote extension is missing')
        tool = importlib.import_module('tools.prepare_omarchy_remote')
        plan = tool.plan(ROOT)
        self.assertEqual([p['name'] for p in plan['added_packages']], [
            'freerdp', 'libappindicator', 'libcbor', 'libfido2', 'libvncserver',
            'remmina', 'sdl3_ttf', 'vte-common', 'vte3'])
        self.assertEqual(len(plan['reused_packages']), 288)
        self.assertEqual(plan['base_package_count'], 921)
        self.assertEqual(plan['base_archive_sha256'], '7dcc1b5382007da2ef2a52d503ee646bdf863f00b45ad65098f8435d9689fd86')

    def test_incompatible_installed_identity_is_rejected_instead_of_upgraded(self):
        self.assertTrue((ROOT / 'tools/prepare_omarchy_remote.py').is_file(), 'verified Omarchy remote extension is missing')
        tool = importlib.import_module('tools.prepare_omarchy_remote')
        base = [{'name': 'lib', 'version': '1-1'}]
        candidate = [{'name': 'lib', 'version': '2-1'}, {'name': 'client', 'version': '1-1'}]
        with self.assertRaises(ValueError):
            tool.split_packages(candidate, base)

    def test_native_pacman_comparator_handles_pkgrel_epoch_and_numeric_versions(self):
        from tools.arch_vercmp import Comparator
        compare = Comparator(ROOT)
        self.addCleanup(compare.temporary.cleanup)
        self.assertEqual(compare('262-1', '262'), 0)
        self.assertEqual(compare('1.0-1', '1.0-1'), 0)
        self.assertGreater(compare('7.2-1', '4.10'), 0)
        self.assertGreater(compare('1:26.2.4-1', '17.0.1-2'), 0)
        self.assertLess(compare('2.38.0-1', '2.38.0-2'), 0)


if __name__ == '__main__':
    unittest.main()
