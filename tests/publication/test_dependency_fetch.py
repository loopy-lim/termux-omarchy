"""Exercise download integrity and existing-file preservation on a real filesystem."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from tools import fetch_dependencies as fetch
except ImportError:
    fetch = None


class Response(io.BytesIO):
    def geturl(self):
        return 'https://release-assets.githubusercontent.com/test'


class DependencyFetchTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(fetch, 'pinned dependency acquisition is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = b'reviewed upstream bytes\n'
        self.row = {'file': 'fixture.tar', 'url': 'https://github.com/example/repo/releases/download/v1/fixture.tar',
                    'bytes': len(self.data), 'sha256': hashlib.sha256(self.data).hexdigest(),
                    'purpose': 'fixture', 'licenseNote': 'fixture'}

    def transfer(self, data):
        with patch.object(fetch, 'open_response', return_value=Response(data)):
            return fetch.acquire(self.root, self.row)

    def test_verified_bytes_are_published_once_and_cached_without_network(self):
        result = self.transfer(self.data)
        self.assertEqual(result['status'], 'downloaded')
        target = self.root / self.row['file']
        self.assertEqual(target.read_bytes(), self.data)
        inode = target.stat().st_ino
        with patch.object(fetch, 'open_response', side_effect=AssertionError('network')):
            self.assertEqual(fetch.acquire(self.root, self.row)['status'], 'cached')
        self.assertEqual(target.stat().st_ino, inode)

    def test_wrong_existing_file_is_preserved(self):
        target = self.root / self.row['file']
        target.write_bytes(b'user data')
        with self.assertRaisesRegex(ValueError, 'download-existing-mismatch'):
            self.transfer(self.data)
        self.assertEqual(target.read_bytes(), b'user data')

    def test_wrong_hash_truncated_and_oversized_downloads_leave_no_output(self):
        for data in (b'x' * len(self.data), self.data[:-1], self.data + b'x'):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, 'download-integrity'):
                self.transfer(data)
            self.assertEqual(list(self.root.iterdir()), [])

    def test_symlink_output_cannot_replace_or_write_target(self):
        victim = self.root / 'victim'
        victim.write_bytes(b'keep')
        (self.root / self.row['file']).symlink_to(victim)
        with self.assertRaises((ValueError, OSError)):
            self.transfer(self.data)
        self.assertEqual(victim.read_bytes(), b'keep')

    def test_unsafe_directory_is_refused_before_network(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with patch.object(fetch, 'open_response', side_effect=AssertionError('network')):
            with self.assertRaises((ValueError, OSError)):
                fetch.acquire(alias, self.row)

    def test_redirects_cannot_downgrade_or_change_to_an_unreviewed_host(self):
        handler = fetch.PinnedRedirect()
        for url in ('http://github.com/a', 'https://example.org/file',
                    'https://user@github.com/file', 'https://github.com:8443/file'):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'download-url'):
                handler.redirect_request(None, None, 302, '', {}, url)

    def test_manifest_rejects_paths_unknown_fields_and_mutable_urls(self):
        path = self.root / 'catalog.json'
        for updates in ({'file': '../victim'}, {'sha256': 'bad'}, {'bytes': True},
                        {'url': 'https://github.com/a/b/releases/latest/download/file'},
                        {'extra': 'ignored'}):
            with self.subTest(updates=updates):
                row = dict(self.row, **updates)
                path.write_text(json.dumps({'schema': 1, 'artifacts': {'fixture': row}}))
                with self.assertRaisesRegex(ValueError, 'download-catalog'):
                    fetch.catalog(path)

    def test_pinned_arch_package_with_epoch_uses_https_and_retains_hash(self):
        path = self.root / 'catalog.json'
        row = dict(self.row, file='libgit2-1:1.9.7-1-aarch64.pkg.tar.xz',
                   url='https://ca.us.mirror.archlinuxarm.org/aarch64/extra/libgit2-1:1.9.7-1-aarch64.pkg.tar.xz')
        path.write_text(json.dumps({'schema': 1, 'artifacts': {'fixture': row}}))
        self.assertEqual(fetch.catalog(path)['fixture']['sha256'], self.row['sha256'])


if __name__ == '__main__':
    unittest.main()
