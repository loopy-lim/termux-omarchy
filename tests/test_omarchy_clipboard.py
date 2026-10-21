"""Real record boundaries for Android and the native Omarchy clipboard relay."""
import importlib.util
import os
import sys
from pathlib import Path
import tempfile
import subprocess
from unittest.mock import patch
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = '2efb2c42-10e2-427b-9918-23fbd9d5de01'


class ClipboardRecordTests(unittest.TestCase):
    def setUp(self):
        before = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        self.addCleanup(setattr, sys, "dont_write_bytecode", before)
        path = ROOT / 'android/assets/omarchy-bridge/omarchy_clipboard.py'
        self.assertTrue(path.is_file(), 'Omarchy has no Android clipboard relay')
        sys.path.insert(0, str(path.parent)); self.addCleanup(sys.path.remove, str(path.parent))
        spec = importlib.util.spec_from_file_location('omarchy_clipboard_case', path)
        self.module = importlib.util.module_from_spec(spec)
        previous = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(self.module)
        finally:
            sys.dont_write_bytecode = previous
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.records = self.module.Records(self.root, TOKEN); self.addCleanup(self.records.close)
        self.android = self.root / ('clip-android-' + TOKEN)
        self.guest = self.root / ('clip-guest-' + TOKEN)

    def test_actual_revisions_preserve_equal_content_round_trips(self):
        self.assertEqual(self.records.read_android(), (None, None))
        self.android.write_bytes('한글🙂'.encode())
        data, revision = self.records.read_android()
        self.assertEqual(data, '한글🙂'.encode())
        self.assertEqual(self.records.read_android(), (data, revision))
        temporary = self.root / 'new'; temporary.write_bytes(data); temporary.replace(self.android)
        self.assertNotEqual(self.records.read_android()[1], revision)
        self.records.publish_guest(b'A')
        with self.guest.open('rb') as previous:
            self.records.publish_guest(b'A')
            self.assertNotEqual(os.fstat(previous.fileno()).st_ino, self.guest.stat().st_ino)
        self.assertEqual(self.guest.read_bytes(), b'A')
        self.assertEqual(self.guest.stat().st_mode & 0o777, 0o600)

    def test_initial_nil_sensitive_and_explicit_clear_have_distinct_effects(self):
        self.records.export('nil', b'')
        self.assertFalse(self.guest.exists())
        self.records.export('data', b'public')
        self.records.export('sensitive', b'should-not-publish')
        self.assertEqual(self.guest.read_bytes(), b'public')
        self.records.export('clear', b'')
        self.assertEqual(self.guest.read_bytes(), b'')
        self.records.export('data', b'again')
        self.records.export('nil', b'')
        self.assertEqual(self.guest.read_bytes(), b'')

    def test_unsupported_data_does_not_overwrite_a_valid_clipboard(self):
        self.records.publish_guest(b'keep')
        for data in (b'\x80', b'nul\0text', b'a' * 65537):
            with self.subTest(data_kind=len(data)), self.assertRaises(ValueError):
                self.records.publish_guest(data)
            self.assertEqual(self.guest.read_bytes(), b'keep')
            self.android.write_bytes(data)
            with self.assertRaises(ValueError): self.records.read_android()
        self.records.publish_guest(b'a' * 65536)
        self.assertEqual(self.guest.stat().st_size, 65536)

    def test_symlink_and_fifo_never_read_or_replace_unrelated_data(self):
        keep = self.root / 'keep'; keep.write_bytes(b'KEEP')
        self.android.symlink_to(keep)
        with self.assertRaises(OSError): self.records.read_android()
        self.android.unlink(); os.mkfifo(self.android)
        with self.assertRaises(ValueError): self.records.read_android()
        self.guest.symlink_to(keep)
        with self.assertRaises(ValueError): self.records.publish_guest(b'new')
        self.assertTrue(self.guest.is_symlink()); self.assertEqual(keep.read_bytes(), b'KEEP')

    def test_record_paths_cannot_cross_sessions_or_follow_a_directory_link(self):
        for token in ('../other', '', 'owned', TOKEN + '/other'):
            with self.assertRaises(ValueError): self.module.Records(self.root, token)
        alias = self.root / 'alias'; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError): self.module.Records(alias, TOKEN)

    def test_relay_never_adds_android_phantom_processes(self):
        # The real Android default-limit failure makes this a product requirement.
        # A disconnected compositor may fail, but cannot fall back to child tools.
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('clipboard created an Android phantom process')):
            try:
                relay = self.module.Relay(self.root, TOKEN)
            except (OSError, ValueError):
                return
            else:
                relay.close()



if __name__ == "__main__": unittest.main()
