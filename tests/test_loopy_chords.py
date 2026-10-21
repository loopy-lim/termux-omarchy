"""Real socket/SCM_RIGHTS witnesses for native editing chords and failure cleanup.

GTK action acceptance is tested by fixtures/tablet_clipboard_witness.py on Sway.
This peer proves wire delivery and lifetime, not application clipboard ownership.
"""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_loopy_input import WaylandPeer, TOKEN

LIB = Path(__file__).resolve().parents[1] / 'guest/desktop/usr/local/lib/loopy'
sys.path.insert(0, str(LIB))
import loopy_input


class ChordTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('tested_chords', LIB / 'loopy_chords.py')
        self.chords = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.chords)
        self.temp = tempfile.TemporaryDirectory(dir='/tmp')
        self.directory = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {'LOOPY_SESSION': TOKEN, 'XDG_RUNTIME_DIR': str(self.directory), 'WAYLAND_DISPLAY': 'wayland-1'})
        self.root = patch.object(loopy_input, 'IPC_ROOT', self.directory)
        self.env.start(); self.root.start(); self.peer = None

    def tearDown(self):
        try:
            self.chords.close()
            if self.peer: self.peer.close(); self.assertEqual(self.peer.errors, [])
        finally:
            self.root.stop(); self.env.stop(); self.temp.cleanup()

    def start(self, **kw):
        self.peer = WaylandPeer(self.directory, native_chords=True, **kw)
        return self.peer

    def test_copy_paste_redo_keep_native_codes_and_one_keyboard(self):
        peer = self.start(fragment=True)
        for key, mods in [('c', ('ctrl',)), ('v', ('ctrl', 'shift')), ('z', ('ctrl', 'shift'))]:
            self.chords.inject([(key, mods)])
        self.assertEqual(peer.raw_keys, [(code, state) for code in (46, 47, 44) for state in (1, 0)])
        self.assertEqual([m[0] for m in peer.modifiers], [0, 4, 0, 5, 0, 5, 0])
        self.assertEqual(len(peer.maps), 1); self.assertEqual(peer.creations, 1)
        self.assertFalse(peer.destroyed)
        self.chords.close(); self.assertTrue(peer.destroyed)

    def test_zoom_and_selected_line_delete_balance_modifiers(self):
        peer = self.start()
        self.chords.inject([('plus', ('ctrl',)), ('Home', ('shift',)), ('BackSpace', ())])
        self.assertEqual([m[0] for m in peer.modifiers], [0, 5, 0, 1, 0, 0, 0])
        self.assertEqual(peer.keys, [(key, s) for key in ('plus', 'Home', 'BackSpace') for s in (1, 0)])

    def test_invalid_later_chord_cannot_edit_or_disconnect_live_session(self):
        peer = self.start(); self.chords.inject([('c', ('ctrl',))]); before = list(peer.keys)
        for sequence in ([('v', ('ctrl',)), ('Escape;kill', ())], [('c', ('logo',))], [('c', ('ctrl',))] * 5):
            with self.assertRaises(ValueError): self.chords.inject(sequence)
        self.assertEqual(peer.keys, before); self.assertFalse(peer.destroyed)
        self.chords.inject([('v', ('ctrl',))]); self.assertEqual(peer.creations, 1)

    def test_transport_failure_disconnects_without_replaying_input(self):
        peer = self.start(fault='eof')
        with self.assertRaises(OSError): self.chords.inject([('c', ('ctrl',)), ('v', ('ctrl',))])
        self.assertTrue(peer.disconnected.wait(.5))
        self.assertEqual(peer.keys, [('c', 1), ('c', 0)])
        self.assertIsNone(self.chords._SESSION)
