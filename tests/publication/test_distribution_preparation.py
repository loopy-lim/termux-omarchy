"""Assembly uses reviewed local inputs and preserves prior output and user files."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))


class DistributionPreparationTests(unittest.TestCase):
    def fixture(self, root):
        source = root / 'reviewed'
        source.write_bytes(b'reviewed')
        return {'input/file': source}, {'input/file': {
            'bytes': 8, 'sha256': hashlib.sha256(b'reviewed').hexdigest()}}

    def test_prepares_verified_closed_tree(self):
        from prepare_distribution import prepare
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs, expected = self.fixture(root)
            before = inputs['input/file'].stat()
            self.assertEqual(prepare(inputs, expected, root / 'output'), 1)
            self.assertEqual((root / 'output/input/file').read_bytes(), b'reviewed')
            self.assertEqual(inputs['input/file'].stat().st_mtime_ns, before.st_mtime_ns)

    def test_wrong_input_refused_before_output_creation(self):
        from prepare_distribution import prepare
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs, expected = self.fixture(root)
            inputs['input/file'].write_bytes(b'replaced')
            with self.assertRaisesRegex(ValueError, 'delivery-file-hash'):
                prepare(inputs, expected, root / 'output')
            self.assertFalse((root / 'output').exists())

    def test_existing_output_and_symlink_refused_unchanged(self):
        from prepare_distribution import prepare
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs, expected = self.fixture(root)
            output = root / 'output'
            output.mkdir()
            (output / 'private').write_bytes(b'preserve')
            with self.assertRaises(FileExistsError):
                prepare(inputs, expected, output)
            self.assertEqual((output / 'private').read_bytes(), b'preserve')
            alias = root / 'alias'
            alias.symlink_to(output)
            with self.assertRaises(FileExistsError):
                prepare(inputs, expected, alias)

    def test_missing_or_unlisted_input_refused(self):
        from prepare_distribution import prepare
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs, expected = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'delivery-input-members'):
                prepare({}, expected, root / 'output')
            with self.assertRaisesRegex(ValueError, 'delivery-input-members'):
                prepare(dict(inputs, unreviewed=root / 'other'), expected, root / 'output')

    def test_catalog_maps_to_real_builder_and_download_layouts(self):
        from prepare_distribution import input_paths
        args = SimpleNamespace(downloads=Path('/downloads'), payloads=Path('/payloads'),
                               guard=Path('/guard'), apk=Path('/apk'), apk_source=Path('/source'))
        names = ('omarchy-base.bundle.tar', 'proot-guard/proot', 'tools/tools-manifest.json',
                 'input/termux-x11.apk', 'sources/termux-x11-source.tar.gz')
        inputs = input_paths(args, dict.fromkeys(names))
        self.assertEqual(inputs['omarchy-base.bundle.tar'],
                         Path('/downloads/omarchy-android-aarch64-0.1.1.bundle.tar'))
        self.assertEqual(inputs['proot-guard/proot'], Path('/guard/arm64-v8a/proot'))
        import json
        catalog = json.loads((ROOT / 'manifests/downloads.json').read_text())['artifacts']
        filename = next(row['file'] for row in catalog.values() if row['file'].endswith('.pkg.tar.xz'))
        self.assertEqual(input_paths(args, {'tools/' + filename: {}})['tools/' + filename],
                         Path('/downloads') / filename)


if __name__ == '__main__':
    unittest.main()
