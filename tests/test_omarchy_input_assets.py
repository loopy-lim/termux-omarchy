"""Reject stale or redirected copies of the existing bounded Wayland input client."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('mac_commands.py', 'loopy_chords.py', 'loopy_input.py', 'loopy_ime.py', 'loopy_input_trace.py')


def validator():
    path = ROOT / 'tools/omarchy_input_inputs.py'
    if not path.is_file():
        raise AssertionError('Reusable native input assets have no build-time provenance guard')
    spec = importlib.util.spec_from_file_location('omarchy_input_inputs', path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result.checked_inputs


def fixture(root):
    assets = root / 'android/assets/omarchy-bridge'; assets.mkdir(parents=True)
    source = root / 'guest/desktop/usr/local/lib/loopy'; source.mkdir(parents=True)
    hashes = {}
    for name in NAMES:
        data = ('PUBLIC_FIXTURE_' + name).encode()
        (assets / name).write_bytes(data); (source / name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    (assets / 'input-sources.json').write_text(json.dumps({'schema': 1, 'files': hashes}))
    return assets, source


class OmarchyInputAssetTests(unittest.TestCase):
    def test_current_input_copies_are_verified_and_both_sources_and_assets_are_build_inputs(self):
        check = validator()
        with tempfile.TemporaryDirectory(prefix='loopy-input-assets-') as d:
            root = Path(d); assets, source = fixture(root)
            paths = check(root)
            self.assertTrue(all(assets / name in paths and source / name in paths for name in NAMES))
            self.assertIn(assets / 'input-sources.json', paths)

    def test_modified_asset_and_modified_source_both_require_regeneration(self):
        check = validator()
        with tempfile.TemporaryDirectory(prefix='loopy-input-assets-') as d:
            root = Path(d); assets, source = fixture(root)
            original = (assets / 'loopy_input.py').read_bytes()
            (assets / 'loopy_input.py').write_bytes(b'STALE_COPY')
            with self.assertRaises(ValueError): check(root)
            (assets / 'loopy_input.py').write_bytes(original)
            (source / 'loopy_input.py').write_bytes(b'NEW_SOURCE')
            with self.assertRaises(ValueError): check(root)

    def test_symlinked_input_cannot_be_accepted_or_modify_its_target(self):
        check = validator()
        with tempfile.TemporaryDirectory(prefix='loopy-input-assets-') as d:
            root = Path(d); assets, _ = fixture(root)
            outside = root / 'keep'; outside.write_bytes((assets / 'loopy_ime.py').read_bytes())
            (assets / 'loopy_ime.py').unlink(); (assets / 'loopy_ime.py').symlink_to(outside)
            with self.assertRaises(ValueError): check(root)
            self.assertTrue(outside.read_bytes().startswith(b'PUBLIC_FIXTURE_'))


if __name__ == '__main__': unittest.main()
