"""Fail-closed source identity and whole-transaction preparation boundaries."""
import hashlib
import base64
import json
import io
from pathlib import Path
import tempfile
import tarfile
import unittest

from tests.test_omarchy_packages import database, record

try:
    from tools import prepare_omarchy as prepare
except ImportError:
    prepare = None


class PrepareOmarchyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(prepare, 'Omarchy preparation CLI is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name)
        source = b'app\nmissing\n'
        (self.cache / 'omarchy-packages.txt').write_bytes(source)
        data = database([('app-1/desc', record('app', DEPENDS=['libfoo.so=14-64'])),
                         ('foo-1/desc', record('foo', PROVIDES=['libfoo.so=14-64']))])
        (self.cache / 'core.db').write_bytes(data)
        self.lock = {'schema_version': 1, 'architecture': 'aarch64',
                     'package_list': {'file': 'omarchy-packages.txt', 'sha256': hashlib.sha256(source).hexdigest()},
                     'scope_counts': {'package_requests': 2}, 'requested': ['app', 'missing'],
                     'profiles': {'full': ['app', 'missing'], 'graphics': ['app']},
                     'provider_preferences': {},
                     'repositories': [{'name': 'core', 'database_file': 'core.db',
                                       'database_sha256': hashlib.sha256(data).hexdigest(),
                                       'database_bytes': len(data),
                                       'database_url': 'https://example.org/core.db',
                                       'package_base_url': 'https://example.org/core'}]}
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w:gz') as writer:
            member = tarfile.TarInfo('omarchy-' + '0' * 40 + '/install/omarchy-base.packages')
            member.size = len(source); writer.addfile(member, io.BytesIO(source))
        data = archive.getvalue(); filename = 'source.tar.gz'
        (self.cache / filename).write_bytes(data)
        self.lock['omarchy_source'] = {'repo': 'omacom/omarchy', 'commit': '0' * 40,
            'archive_file': filename, 'archive_bytes': len(data),
            'archive_sha256': hashlib.sha256(data).hexdigest(),
            'archive_url': 'https://codeload.github.com/omacom/omarchy/tar.gz/' + '0' * 40}

    def test_full_audit_retains_missing_root_and_does_not_report_partial_success(self):
        result = prepare.audit(self.lock, self.cache, compare=lambda a, b: 0)
        self.assertEqual(result['status'], 'unresolved')
        self.assertEqual(result['requested'], ['app', 'missing'])
        self.assertEqual(result['unresolved'], ['missing'])
        self.assertFalse(result['ready_to_fetch'])

    def test_graphics_profile_is_explicitly_separate_from_full_support(self):
        result = prepare.audit(self.lock, self.cache, profile='graphics', compare=lambda a, b: 0)
        self.assertEqual(result['status'], 'transaction-resolved')
        self.assertEqual(result['profile'], 'graphics')
        self.assertFalse(result['omarchy_support_complete'])
        self.assertEqual({p['name'] for p in result['packages']}, {'app', 'foo'})

    def test_full_additions_audit_keeps_every_request_and_downloads_only_missing_packages(self):
        installed = [{'name': 'foo', 'version': '1-1', 'provides': ['libfoo.so=14-64'], 'conflicts': []},
                     {'name': 'missing', 'version': '1-1', 'provides': [], 'conflicts': []}]
        try:
            result = prepare.audit(self.lock, self.cache, installed=installed, compare=lambda a, b: 0)
        except TypeError as error:
            self.fail('Preparation cannot preserve current packages: ' + str(error))
        self.assertEqual(result['requested'], ['app', 'missing'])
        self.assertEqual(result['status'], 'transaction-resolved')
        self.assertEqual([p['name'] for p in result['packages']], ['app'])
        self.assertTrue(result['preserves_installed_versions'])
        self.assertFalse(result['omarchy_support_complete'])

    def test_installed_snapshot_load_rejects_stale_version_and_provider_hashes(self):
        self.assertTrue(hasattr(prepare, 'load_installed'), 'Installed snapshot input is missing')
        rows = [{'name': 'foo', 'version': '1-1', 'provides': ['libfoo.so=14-64'], 'conflicts': []}]
        canonical = json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()
        value = {'schema_version': 1, 'architecture': 'aarch64', 'packages': rows,
                 'package_list_sha256': hashlib.sha256(b'foo 1-1\n').hexdigest(),
                 'metadata_sha256': hashlib.sha256(canonical).hexdigest()}
        path = self.cache / 'installed.json'; path.write_text(json.dumps(value))
        self.assertEqual(prepare.load_installed(path), value)
        for key, changed in [('version', '2-1'), ('provides', ['libfoo.so=15-64'])]:
            edited = json.loads(json.dumps(value)); edited['packages'][0][key] = changed
            path.write_text(json.dumps(edited))
            with self.assertRaises(ValueError): prepare.load_installed(path)
        value['packages'].append(dict(rows[0])); path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): prepare.load_installed(path)

    def test_tampered_source_or_repository_fails_before_dependency_resolution(self):
        (self.cache / 'core.db').write_bytes(b'tampered')
        with self.assertRaises(ValueError): prepare.audit(self.lock, self.cache, compare=lambda a, b: 0)
        (self.cache / 'omarchy-packages.txt').write_bytes(b'app\n')
        with self.assertRaises(ValueError): prepare.audit(self.lock, self.cache, compare=lambda a, b: 0)

    def test_lock_rejects_scope_loss_and_path_escape(self):
        path = self.cache / 'lock.json'
        for field, value in [('requested', ['app']), ('architecture', 'x86_64')]:
            lock = dict(self.lock); lock[field] = value
            path.write_text(json.dumps(lock))
            with self.assertRaises(ValueError): prepare.load_lock(path)
        self.lock['package_list']['file'] = '../elsewhere'
        path.write_text(json.dumps(self.lock))
        with self.assertRaises(ValueError): prepare.load_lock(path)

    def test_original_package_list_can_be_restored_only_from_verified_source_archive(self):
        path = self.cache / self.lock['package_list']['file']
        path.unlink()
        self.assertTrue(hasattr(prepare, 'ensure_inputs'), 'Verified source recovery is missing')
        prepare.ensure_inputs(self.lock, self.cache)
        self.assertEqual(path.read_bytes(), b'app\nmissing\n')
        (self.cache / 'source.tar.gz').write_bytes(b'tampered')
        with self.assertRaises(ValueError): prepare.ensure_inputs(self.lock, self.cache)

    def test_unresolved_transaction_can_never_be_fetched(self):
        with self.assertRaises(ValueError):
            prepare.fetch_transaction({'status': 'unresolved', 'packages': []}, self.cache)

    def test_tampered_cached_package_is_rejected_without_network_or_signature_execution(self):
        folder = self.cache / 'packages'; folder.mkdir()
        (folder / 'app.pkg.tar.zst').write_bytes(b'tampered')
        transaction = {'status': 'transaction-resolved', 'packages': [
            {'filename': 'app.pkg.tar.zst', 'sha256': hashlib.sha256(b'good').hexdigest(),
             'size_bytes': 4, 'url': 'https://example.org/app.pkg.tar.zst'}]}
        with self.assertRaises(ValueError): prepare.fetch_transaction(transaction, self.cache)

    def test_invalid_signature_can_never_be_promoted_to_verified_package(self):
        folder = self.cache / 'packages'; folder.mkdir()
        payload = b'known fixture payload'
        (folder / 'app.pkg.tar.zst').write_bytes(payload)
        verifier = self.cache / 'reject-signature'
        verifier.write_text('#!/bin/sh\nexit 9\n'); verifier.chmod(0o700)
        transaction = {'status': 'transaction-resolved', 'packages': [
            {'filename': 'app.pkg.tar.zst', 'sha256': hashlib.sha256(payload).hexdigest(),
             'size_bytes': len(payload), 'url': 'https://example.org/app.pkg.tar.zst',
             'signature': [base64.b64encode(b'invalid signature').decode()]}]}
        with self.assertRaises(ValueError):
            prepare.fetch_transaction(transaction, self.cache, pacman_key=str(verifier))


if __name__ == '__main__':
    unittest.main()
