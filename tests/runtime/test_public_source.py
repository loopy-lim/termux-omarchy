"""Source publication must fail closed before an unavailable installer can mutate HOME."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PublicSourceTests(unittest.TestCase):
    def run_tool(self, name, *args, root=ROOT, env=None):
        return subprocess.run([sys.executable, '-B', str(root / 'installer' / name), *args],
                              capture_output=True, text=True, timeout=10, env=env)

    def copied_tree(self, target):
        for name in ('runtime', 'profiles', 'installer', 'tests/runtime'):
            shutil.copytree(ROOT / name, target / name)
        (target / 'manifests').mkdir()
        for name in ('runtime-sources.json', 'runtime-prerequisites.json'):
            shutil.copyfile(ROOT / 'manifests' / name, target / 'manifests' / name)

    def test_complete_source_tree_verifies_without_binary_payloads(self):
        result = self.run_tool('verify.py')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)['status'], 'source-verified')

    def test_changed_runtime_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.copied_tree(root)
            with (root / 'runtime/omarchy_resources.py').open('a') as output:
                output.write('\n# unexpected source replacement\n')
            result = self.run_tool('verify.py', root=root)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['reason'], 'source-hash')

    def test_symlink_source_is_rejected_even_with_identical_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.copied_tree(root)
            source = root / 'runtime/omarchy_resources.py'
            held = root / 'same-source'
            source.rename(held)
            source.symlink_to(held)
            result = self.run_tool('verify.py', root=root)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['reason'], 'source-filesystem')

    def test_missing_manifest_is_a_bounded_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.copied_tree(root)
            (root / 'manifests/runtime-sources.json').unlink()
            result = self.run_tool('verify.py', root=root)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['reason'], 'source-filesystem')
            self.assertNotIn('Traceback', result.stderr)

    def test_install_check_honestly_reports_missing_binary_closure(self):
        result = self.run_tool('install.py', '--check')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        row = json.loads(result.stdout)
        self.assertEqual(row['status'], 'source-only-developer-alpha')
        self.assertFalse(row['automaticInstallEnabled'])
        self.assertFalse(row['binaryClosureComplete'])

    def test_apply_refuses_before_home_changes_or_untrusted_payload_access(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            (home / 'preserve').write_bytes(b'unchanged')
            env = dict(os.environ, HOME=str(home), PREFIX=str(home / 'not-created'))
            result = self.run_tool('install.py', '--apply', '--bundle', str(home / 'absent'), env=env)
            self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
            row = json.loads(result.stdout)
            self.assertEqual(row['reason'], 'binary-closure-unavailable')
            self.assertFalse(row['deviceChangesRequested'])
            self.assertEqual([path.name for path in home.iterdir()], ['preserve'])
            self.assertEqual((home / 'preserve').read_bytes(), b'unchanged')


if __name__ == '__main__':
    unittest.main()
