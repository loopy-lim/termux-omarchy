"""Pinned Code patch and its real-fs provider regression seam."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'build/diagnostics/termux-omarchy-vscode-empty-write-source-20261009-01/sharedProcessMain.before.js'
MODULE = ROOT / 'termux/vscode_write_compat.py'
FIXTURE = ROOT / 'tests/fixtures/vscode_write_compat_regression.cjs'


class CodeWriteCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), 'bounded Code empty-write patch is missing')
        spec = importlib.util.spec_from_file_location('vscode_write_compat', MODULE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.original = SOURCE.read_bytes()

    def test_patch_executes_actual_provider_method_with_real_files(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is needed to execute the real-fs regression')
        with tempfile.TemporaryDirectory() as name:
            source = Path(name) / 'sharedProcessMain.js'
            source.write_bytes(self.m.patch_bytes(self.original))
            result = subprocess.run([node, str(FIXTURE), str(source), name],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            row = json.loads(result.stdout)
            self.assertEqual(row['phase'], 'PASS')
            self.assertEqual(row['cases'], 9)
            self.assertEqual(row['writesMocked'], False)

    def test_changed_release_refuses_before_creating_outputs(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / 'source.js'
            source.write_bytes(self.original + b' ')
            with self.assertRaises(ValueError):
                self.m.build(source, root / 'candidate')
            self.assertFalse((root / 'candidate').exists())
            self.assertEqual(source.read_bytes(), self.original + b' ')

    def test_candidate_is_exclusive_and_original_is_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            source, out = Path(name) / 'source.js', Path(name) / 'candidate'
            source.write_bytes(self.original)
            before = (source.stat().st_ino, source.stat().st_mtime_ns)
            row = self.m.build(source, out)
            candidate = out / 'sharedProcessMain.js'
            self.assertEqual(row['beforeSha256'], hashlib.sha256(self.original).hexdigest())
            self.assertEqual(row['afterSha256'], hashlib.sha256(candidate.read_bytes()).hexdigest())
            self.assertEqual(json.loads((out / 'manifest.json').read_text()), row)
            self.assertEqual(source.read_bytes(), self.original)
            self.assertEqual((source.stat().st_ino, source.stat().st_mtime_ns), before)
            outputs = {p.name: (p.read_bytes(), p.stat().st_ino) for p in out.iterdir()}
            with self.assertRaises(FileExistsError):
                self.m.build(source, out)
            self.assertEqual({p.name: (p.read_bytes(), p.stat().st_ino) for p in out.iterdir()}, outputs)

    def test_symlink_source_is_refused_without_outputs(self):
        with tempfile.TemporaryDirectory() as name:
            source = Path(name) / 'source.js'
            source.symlink_to(SOURCE)
            with self.assertRaises(ValueError):
                self.m.build(source, Path(name) / 'candidate')
            self.assertFalse((Path(name) / 'candidate').exists())

    def test_already_patched_or_same_size_tampering_is_refused(self):
        for data in (self.original[:-1] + bytes([self.original[-1] ^ 1]),
                     self.m.patch_bytes(self.original)):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                self.m.patch_bytes(data)


if __name__ == '__main__':
    unittest.main()
