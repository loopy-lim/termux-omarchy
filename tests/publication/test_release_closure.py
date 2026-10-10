"""Check real release cross-pins and complete acquisition mapping without network."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))


class ReleaseClosureTests(unittest.TestCase):
    def test_all_release_files_have_unique_pinned_origins(self):
        from acquire_distribution import plan
        entries, downloads, local = plan(ROOT)
        self.assertEqual(len(entries), 90)
        self.assertEqual(len(downloads), 88)
        self.assertEqual(len(local), 2)
        own = {name: row for name, row in downloads.items()
               if '/loopy-lim/termux-omarchy/releases/' in row['url']}
        self.assertEqual(len(own), 15)
        self.assertTrue(all('/v0.1.0-alpha.2/' in row['url'] for row in own.values()))
        self.assertTrue({'input/termux-x11.apk', 'input/termux-x11-companion.deb',
                         'sources/termux-x11-source.tar.gz',
                         'sources/proot-guard-source.tar.gz'} <= set(own))

    def test_apk_companion_and_runtime_payloads_match_delivery_catalog(self):
        from assets import catalog
        from companion import validate_spec
        entries = catalog(ROOT)
        companion = json.loads((ROOT / 'manifests/companion.json').read_text())
        validate_spec(companion)
        self.assertEqual(entries['input/termux-x11-companion.deb'], companion['deb'])
        source = json.loads((ROOT / 'manifests/input-sources.json').read_text())
        signed = source['freshSourceBuild']['signedAPK']
        self.assertEqual(entries['input/termux-x11.apk'],
                         {key: signed[key] for key in ('bytes', 'sha256')})
        build = json.loads((ROOT / 'manifests/runtime-build.json').read_text())
        for component in build['components'].values():
            for filename, expected in component['artifacts'].items():
                self.assertEqual(entries[filename], expected)
        self.assertFalse(build['fullFreshInstallVerified'])
        self.assertFalse(source['freshSourceBuild']['physicalCandidateAcceptance'])


if __name__ == '__main__':
    unittest.main()
