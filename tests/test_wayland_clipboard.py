"""Actual AF_UNIX / SCM_RIGHTS clipboard delivery without a child process."""
import importlib.util
import os
from pathlib import Path
import select
import sys
import tempfile
import time
import unittest
from tests.fixtures.wayland_clipboard_peer import Peer

ROOT = Path(__file__).resolve().parents[1]


class WaylandClipboardTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'android/assets/omarchy-bridge/wayland_clipboard.py'
        self.assertTrue(path.is_file(), 'Clipboard has no in-process Wayland data-control client')
        spec = importlib.util.spec_from_file_location('wire_clipboard_case', path)
        module = importlib.util.module_from_spec(spec)
        previous = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True; spec.loader.exec_module(module)
        finally: sys.dont_write_bytecode = previous
        self.temp = tempfile.TemporaryDirectory(dir='/tmp'); self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / 'wayland'; self.peer = Peer(path); self.addCleanup(self.peer.close)
        self.exports = []; self.client = module.Client(path, lambda state, data: self.exports.append((state, data)))
        self.addCleanup(self.client.close)

    def pump_until(self, predicate):
        end = time.monotonic() + 4
        while not predicate() and time.monotonic() < end:
            self.client.pump(); select.select(self.client.readers, self.client.writers, [], .01)
        self.assertTrue(predicate(), 'Wayland clipboard did not deliver the requested data')
        self.assertIsNone(self.peer.error)

    def test_android_source_uses_a_real_passed_descriptor_and_balanced_clear(self):
        data = 'Android 한글🙂'.encode()
        self.client.set_selection(data)
        self.pump_until(lambda: bool(self.peer.pending))
        received = bytearray(); fd = self.peer.pending[0]; os.set_blocking(fd, False)
        def complete():
            try:
                chunk = os.read(fd, 65537)
                if chunk: received.extend(chunk); return False
                return True
            except BlockingIOError: return False
        self.pump_until(complete)
        self.assertEqual(bytes(received), data)
        self.client.set_selection(b'')
        self.pump_until(lambda: self.peer.imports == [b''])

    def test_guest_unicode_and_equal_content_recurrence_are_distinct_events(self):
        self.exports.clear()
        for value in ['guest 한글🙂', 'B', 'guest 한글🙂']:
            before = len(self.exports); self.peer.offer(value.encode())
            self.pump_until(lambda: len(self.exports) > before)
            self.assertEqual(self.exports[-1], ('data', value.encode()))
        self.peer.send(self.peer.device, 1, (0).to_bytes(4, sys.byteorder))
        self.pump_until(lambda: self.exports[-1] == ('nil', b''))

    def test_binary_offers_do_not_export_as_text(self):
        self.exports.clear()
        obj = self.peer.offer(b'PNG', 'image/png')
        self.pump_until(lambda: obj in self.client.offers)
        for _ in range(3): self.client.pump(); time.sleep(.01)
        self.assertEqual(self.exports, [])

    def test_primary_selection_changes_never_replace_clipboard_or_exhaust_offers(self):
        self.peer.offer(b'explicit copy')
        self.pump_until(lambda: self.exports[-1] == ('data', b'explicit copy'))
        before = list(self.exports)
        for _ in range(260):
            obj = self.peer.offer(b'mouse selection', primary=True)
            self.pump_until(lambda: obj in self.peer.destroyed_offers)
        self.peer.send(self.peer.device, 3, (0).to_bytes(4, sys.byteorder))
        self.peer.offer(b'next explicit copy')
        self.pump_until(lambda: self.exports[-1] == ('data', b'next explicit copy'))
        self.assertEqual(self.exports, before + [('data', b'next explicit copy')])

    def test_invalid_utf8_nul_and_oversized_guest_offers_preserve_the_old_clipboard(self):
        self.exports.clear()
        for value in (b'\x80', b'private\0binary', b'x' * 65537):
            obj = self.peer.offer(value)
            self.pump_until(lambda: obj in self.peer.completed_offers and self.client.incoming is None)
            self.assertEqual(self.exports, [], 'invalid text replaced the Android clipboard')

    def test_sensitive_mime_is_not_exported(self):
        self.exports.clear()
        obj = self.peer.offer(b'sensitive', ['text/plain;charset=utf-8', 'x-kde-passwordManagerHint'])
        self.pump_until(lambda: obj in self.client.offers)
        self.assertIsNone(self.client.incoming)
        self.assertEqual(self.exports, [])


if __name__ == '__main__': unittest.main()
