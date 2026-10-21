"""The native browser bridge accepts web navigation, never command-line options."""
import sys
from pathlib import Path
import unittest
import socket
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'termux'))
from omarchy_android_client import browser_fields
from omarchy_android import browser_profile_available

class BrowserBoundaryTests(unittest.TestCase):
    def test_stale_lock_can_be_recovered_without_deleting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            lock = profile / 'SingletonLock'
            lock.symlink_to(socket.gethostname() + '-12345')
            self.assertTrue(browser_profile_available(profile, {}, lambda pid: None))
            self.assertTrue(lock.is_symlink())
            self.assertFalse(browser_profile_available(profile, {}, lambda pid: {'pid': pid}))
            self.assertFalse(browser_profile_available(profile, {1: {'command': ['chrome', '--user-data-dir=' + directory]}}, lambda pid: None))
            lock.unlink()
            lock.symlink_to('another-host-12345')
            self.assertFalse(browser_profile_available(profile, {}, lambda pid: None))

    def test_http_navigation_preserves_literal_query(self):
        value={'url':'http://127.0.0.1:8765/?folder=%2Fhome%2Fomarchy','display':':0'}
        self.assertEqual(browser_fields(value),value)

    def test_rejects_command_paths_credentials_control_chars_and_extra_fields(self):
        for url in ('--no-sandbox','file:///etc/passwd','javascript:alert(1)',
                    'https://user:password@example.com','https://example.com/\n--foo',
                    'https://example.com:bad','https://example.com/'+'x'*2048):
            with self.subTest(url=url[:50]),self.assertRaises(ValueError):
                browser_fields({'url':url,'display':':0'})
        for fields in ({'url':'https://example.com','display':':21'},
                       {'url':'https://example.com','display':':0','argv':['--foo']},
                       {'url':'https://example.com','display':'localhost:0'},None):
            with self.assertRaises(ValueError):browser_fields(fields)
