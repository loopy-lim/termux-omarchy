"""Delivery acquisition preserves source, user files and failed attempts."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

try:
    import acquire_distribution as delivery
except ImportError:
    delivery = None


def identity(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


class Response(io.BytesIO):
    def geturl(self):
        return 'https://release-assets.githubusercontent.com/reviewed-fixture'


class DistributionAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(delivery, 'distribution acquisition is not implemented')
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name).resolve()
        self.source = self.folder / 'source'
        self.source.mkdir(mode=0o700)
        (self.source / 'runtime').mkdir()
        (self.source / 'manifests/packages').mkdir(parents=True)
        pins = {}
        for number in range(11):
            name = 'fixture_' + str(number) + '.py'
            data = ('# Integrity fixture ' + str(number) + '\n').encode()
            (self.source / 'runtime' / name).write_bytes(data)
            pins[name] = identity(data)['sha256']
        for name in ('omarchy_install.py', 'omarchy_terminal.py'):
            (self.source / 'runtime' / name).write_text('RUNTIME_SHA = ' + repr(pins) + '\n')
        terminal = (self.source / 'runtime/omarchy_terminal.py').read_bytes()
        (self.source / 'runtime/omarchy_terminal_install.py').write_text(
            'SOURCE_SHA = ' + repr(identity(terminal)['sha256']) + '\n')
        self.write('manifests/runtime-prerequisites.json', {
            'schema': 1, 'binaryClosureComplete': False, 'automaticInstallEnabled': False,
            'missing': [], 'upstreamBundle': {}})
        self.write('manifests/companion.json', {})
        self.contents = {
            'input/termux-x11.apk': b'reviewed unsigned fixture identity\n',
            'sources/termux-x11-source.tar.gz': b'reviewed corresponding source fixture\n',
            'tools/tool.pkg.tar.xz': b'reviewed upstream package fixture\n',
            'tools/tools-manifest.json': b'{"fixture":"tools"}\n',
            'korean-input/ime-manifest.json': b'{"fixture":"ime"}\n'}
        self.entries = {name: identity(data) for name, data in self.contents.items()}
        self.write('manifests/distribution.json', {
            'schema': 1, 'status': 'build-closure-prepared',
            'fullFreshInstallVerified': False, 'files': self.entries})
        self.downloads, self.responses = {}, {}
        for number, (name, data) in enumerate(self.contents.items()):
            if name.endswith('-manifest.json'):
                (self.source / 'manifests/packages' / Path(name).name).write_bytes(data)
                continue
            filename = 'original-' + str(number) + '.bin'
            url = 'https://github.com/example/reviewed/releases/download/v1/' + filename
            self.downloads['fixture-' + str(number)] = dict(identity(data), file=filename,
                url=url, purpose='integrity fixture', licenseNote='test fixture')
            self.responses[url] = data
        self.write('manifests/downloads.json', {'schema': 1, 'artifacts': self.downloads})
        files = {path.relative_to(self.source).as_posix(): identity(path.read_bytes())
                 for path in (self.source / 'runtime').iterdir()}
        for name in ('runtime-prerequisites.json', 'distribution.json', 'companion.json'):
            files['manifests/' + name] = identity((self.source / 'manifests' / name).read_bytes())
        self.write('manifests/runtime-sources.json', {
            'schema': 1, 'sourceOnly': True, 'fullFreshInstallVerified': False, 'files': files})
        self.output = self.folder / 'assets'

    def write(self, name, data):
        (self.source / name).write_text(json.dumps(data, sort_keys=True) + '\n')

    def response(self, url):
        return Response(self.responses[url])

    def test_plan_validates_complete_mapping_without_network_or_writes(self):
        home = self.folder / 'home'
        home.mkdir()
        (home / 'preserve').write_bytes(b'private user data')
        before = {p: (p.stat().st_mtime_ns, p.read_bytes())
                  for p in self.source.rglob('*') if p.is_file()}
        with patch.dict(os.environ, {'HOME': str(home)}), \
             patch.object(delivery.fetch, 'open_response', side_effect=AssertionError('network')):
            entries, downloads, local = delivery.plan(self.source)
        self.assertEqual(entries, self.entries)
        self.assertEqual(set(downloads), set(self.entries) - set(delivery.LOCAL))
        self.assertEqual(set(local), set(delivery.LOCAL))
        self.assertFalse(self.output.exists())
        self.assertEqual((home / 'preserve').read_bytes(), b'private user data')
        self.assertEqual(before, {p: (p.stat().st_mtime_ns, p.read_bytes())
                                 for p in self.source.rglob('*') if p.is_file()})

    def test_acquisition_publishes_exact_tree_using_original_urls_and_pins(self):
        with patch.object(delivery.fetch, 'open_response', side_effect=self.response) as network:
            count = delivery.acquire(self.source, self.output)
        self.assertEqual(count, len(self.entries))
        self.assertEqual(network.call_count, len(self.responses))
        self.assertEqual({call.args[0] for call in network.call_args_list}, set(self.responses))
        for name, data in self.contents.items():
            self.assertEqual((self.output / name).read_bytes(), data)
        for directory in [self.output, *(p for p in self.output.rglob('*') if p.is_dir())]:
            self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(delivery.assets.verify_tree(self.output, self.entries), len(self.entries))
        self.assertEqual(delivery.fetch.catalog(self.source / 'manifests/downloads.json'), self.downloads)

    def test_wrong_source_or_local_manifest_is_refused_before_output_creation(self):
        for relative in ('runtime/fixture_0.py', 'manifests/packages/tools-manifest.json'):
            path = self.source / relative
            original = path.read_bytes()
            path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            with self.subTest(relative=relative), \
                 patch.object(delivery.fetch, 'open_response', side_effect=AssertionError('network')), \
                 self.assertRaises(ValueError):
                delivery.acquire(self.source, self.output)
            self.assertFalse(self.output.exists())
            path.write_bytes(original)

    def test_local_manifest_symlink_is_refused_before_output_creation(self):
        path = self.source / 'manifests/packages/tools-manifest.json'
        retained = self.folder / 'retained-manifest.json'
        path.rename(retained)
        path.symlink_to(retained)
        with patch.object(delivery.fetch, 'open_response', side_effect=AssertionError('network')), \
             self.assertRaises(OSError):
            delivery.acquire(self.source, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(retained.read_bytes(), self.contents['tools/tools-manifest.json'])

    def test_missing_and_ambiguous_download_map_is_refused_before_output_creation(self):
        first = next(iter(self.downloads))
        cases = [dict(list(self.downloads.items())[1:]), dict(self.downloads, duplicate=dict(
            self.downloads[first], file='duplicate.bin',
            url='https://github.com/example/reviewed/releases/download/v1/duplicate.bin'))]
        for catalog in cases:
            self.write('manifests/downloads.json', {'schema': 1, 'artifacts': catalog})
            with self.subTest(catalog=list(catalog)), \
                 patch.object(delivery.fetch, 'open_response', side_effect=AssertionError('network')), \
                 self.assertRaisesRegex(ValueError, 'delivery-download-map'):
                delivery.acquire(self.source, self.output)
            self.assertFalse(self.output.exists())

    def test_existing_directory_and_symlink_are_preserved_without_network(self):
        self.output.mkdir()
        sentinel = self.output / 'preserve'
        sentinel.write_bytes(b'keep existing output')
        alias = self.folder / 'alias'
        alias.symlink_to(self.output, target_is_directory=True)
        with patch.object(delivery.fetch, 'open_response', side_effect=AssertionError('network')):
            for output in (self.output, alias):
                with self.subTest(output=output.name), self.assertRaises(FileExistsError):
                    delivery.acquire(self.source, output)
        self.assertEqual(sentinel.read_bytes(), b'keep existing output')
        self.assertTrue(alias.is_symlink())

    def test_failed_download_preserves_partial_output_and_refuses_retry(self):
        calls = []
        def interrupted(url):
            calls.append(url)
            return self.response(url) if len(calls) == 1 else Response(b'invalid download')
        with patch.object(delivery.fetch, 'open_response', side_effect=interrupted), \
             self.assertRaisesRegex(ValueError, 'download-integrity'):
            delivery.acquire(self.source, self.output)
        first = self.output / 'input/termux-x11.apk'
        self.assertEqual(first.read_bytes(), self.contents['input/termux-x11.apk'])
        self.assertFalse(any(p.name.startswith('.download-') for p in self.output.rglob('*')))
        before = {p: p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
        with patch.object(delivery.fetch, 'open_response', side_effect=AssertionError('network')), \
             self.assertRaises(FileExistsError):
            delivery.acquire(self.source, self.output)
        self.assertEqual(before, {p: p.read_bytes() for p in self.output.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
