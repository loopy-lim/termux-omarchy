"""Real runtime filesystem checks for the immutable Quickshell path index."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'termux'))
import omarchy_resources as resources
sys.path.pop(0)


class QuickshellRebindTests(unittest.TestCase):
    def fixture(self, directory):
        root, prefix = Path(directory) / 'runtime', Path(directory) / 'prefix'
        root.mkdir(); prefix.mkdir()
        shell = 'c0240dfe8c8e8a421e1f8db23a03fc60'
        (root / 'quickshell/by-shell' / shell).mkdir(parents=True)
        link = root / 'quickshell/by-path' / shell
        link.parent.mkdir()
        target = '/run/user/1000/quickshell/by-shell/' + shell
        link.symlink_to(target)
        value = {'runtime': resources.row(root)[:3], 'display': ':20'}
        (root / 'owner.json').write_text('{}')
        resources.capture(root, prefix, value, [])
        return root, prefix, value, link, target

    def replace_link(self, link, target):
        replacement = link.with_name('replacement')
        replacement.symlink_to(target)
        replacement.replace(link)

    def test_owned_shell_can_recreate_its_fixed_path_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root, prefix, value, link, target = self.fixture(directory)
            before = resources.row(link)
            self.replace_link(link, target)
            self.assertNotEqual(before[1], resources.row(link)[1])
            resources.capture(root, prefix, value, [])
            self.assertEqual(value['resources']['runtime:' + str(link.relative_to(root))],
                             resources.row(link))
            resources.cleanup(root, prefix, value)
            self.assertFalse(os.path.lexists(link))

    def test_changed_target_is_refused_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root, prefix, value, link, _ = self.fixture(directory)
            preserved = Path(directory) / 'user-data'; preserved.write_text('preserve')
            self.replace_link(link, str(preserved))
            with self.assertRaises(resources.ResourceFailure):
                resources.capture(root, prefix, value, [])
            self.assertEqual(preserved.read_text(), 'preserve')
            self.assertTrue(link.is_symlink())

    def test_fixed_index_survives_the_short_lived_ipc_client(self):
        with tempfile.TemporaryDirectory() as directory:
            root, prefix, value, link, target = self.fixture(directory)
            self.replace_link(link, target)
            resources.capture(root, prefix, value, [])

    def test_replaced_target_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root, prefix, value, link, target = self.fixture(directory)
            native_target = root / target.removeprefix('/run/user/1000/')
            native_target.rename(native_target.with_name('preserved-original'))
            native_target.mkdir()
            self.replace_link(link, target)
            with self.assertRaises(resources.ResourceFailure):
                resources.capture(root, prefix, value, [])

    def test_other_quickshell_link_replacement_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root, prefix, value, _, target = self.fixture(directory)
            link = root / 'quickshell/by-path/unknown-index'
            link.symlink_to(target)
            resources.capture(root, prefix, value, [])
            self.replace_link(link, target)
            with self.assertRaises(resources.ResourceFailure):
                resources.capture(root, prefix, value, [])


if __name__ == '__main__': unittest.main()
