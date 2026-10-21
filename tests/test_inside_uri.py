"""The same public serialized URI vectors are checked by Python and Java."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UriTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'android/assets/omarchy-bridge/inside_uri.py'
        spec = importlib.util.spec_from_file_location('inside_uri_test', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_shared_public_vectors_preserve_every_valid_original_byte(self):
        vectors = json.loads((ROOT / 'tests/fixtures/inside_browser_uri.json').read_text())
        for row in vectors:
            with self.subTest(case=row['id']):
                if row['valid']:
                    self.assertEqual(self.module.validate(row['uri']), row['uri'])
                else:
                    with self.assertRaisesRegex(ValueError, '^inside-uri$'):
                        self.module.validate(row['uri'])

    def test_byte_bound_and_type_are_checked_without_rewriting(self):
        prefix = 'https://example.test/'
        edge = prefix + 'a' * (2048 - len(prefix))
        self.assertEqual(self.module.validate(edge), edge)
        for value in (edge + 'a', None, True, b'https://example.test/', 1):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                self.module.validate(value)
        self.assertEqual(self.module.validate('https://example.test/%5B%5D?q=%25'),
                         'https://example.test/%5B%5D?q=%25')

    def test_fixed_browser_gate_does_not_authorize_generic_app_uri(self):
        target = dict(component=self.module.BROWSER, uid=10372)
        public = 'https://example.test/'
        self.assertEqual(self.module.initial(target, public), public)
        for component in ('notion.id/notion.local.id.MainActivity',
                          'com.android.chrome/com.google.android.apps.chrome.Main', ''):
            with self.subTest(case=component), self.assertRaisesRegex(ValueError, '^inside-uri-target$'):
                self.module.initial({**target, 'component': component}, public)


if __name__ == '__main__':
    unittest.main()
