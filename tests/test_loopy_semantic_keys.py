"""Semantic hardware codes and Unicode allocation on the real VK Unix wire."""
import ctypes
import re
import unittest
import test_loopy_input as protocol


# Linux v6.12 include/uapi/linux/input-event-codes.h, independent of the helper.
CANONICAL = [('Return', 28), ('BackSpace', 14), ('Delete', 111), ('Tab', 15),
             ('Escape', 1), ('Up', 103), ('Down', 108), ('Left', 105),
             ('Right', 106), ('Home', 102), ('End', 107), ('Prior', 104),
             ('Next', 109), ('Clear', 355)]


class SemanticKeyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = protocol.LoopyInputTests()
        self.fixture.setUp()
        self.helper = self.fixture.helper

    def tearDown(self):
        self.fixture.tearDown()

    def test_semantic_pairs_send_canonical_evdev_codes_and_matching_real_xkb(self):
        peer = self.fixture.start(fragment=True)
        for symbol, _ in CANONICAL[:-1]:
            self.helper.inject(key=symbol)
        self.helper.inject('\v')  # Clear is a text control, not an exposed IME key.
        self.assertEqual(peer.raw_keys, [(code, state) for _, code in CANONICAL for state in (1, 0)])
        self.assertEqual(peer.keys, [(symbol, state) for symbol, _ in CANONICAL for state in (1, 0)])
        values = self.fixture.compile_map(peer.maps[0])
        try:
            for symbol, code in CANONICAL:
                self.assertEqual(values[0].xkb_state_key_get_one_sym(values[3], code + 8),
                                 values[0].xkb_keysym_from_name(symbol.encode(), 0))
        finally:
            self.fixture.free_map(values)
        self.assertEqual(peer.creations, 1)
        self.assertEqual(len(peer.maps), 1)

    def test_unicode_extensions_skip_fixed_keys_and_keep_queued_code_meaning(self):
        peer = self.fixture.start()
        text = ''.join(chr(cp) for cp in range(0x400, 0x400 + 360))
        self.helper.inject(text[:80]); self.helper.inject(key='Return')
        self.helper.inject(text[80:]); self.helper.inject(key='BackSpace')
        unicode_codes = {code for (code, down), (symbol, _) in zip(peer.raw_keys, peer.keys)
                         if down and symbol.startswith('U')}
        self.assertTrue(unicode_codes.isdisjoint({code for _, code in CANONICAL}),
                        'Unicode keymap extension overwrote a semantic hardware slot')
        self.assertEqual(len(unicode_codes), 360)
        self.assertEqual(peer.raw_keys[:4], [(2, 1), (2, 0), (3, 1), (3, 0)])
        values = self.fixture.compile_map(peer.maps[-1])
        try:
            for (code, down), (symbol, _) in zip(peer.raw_keys, peer.keys):
                if down:
                    self.assertEqual(values[0].xkb_state_key_get_one_sym(values[3], code + 8),
                                     values[0].xkb_keysym_from_name(symbol.encode(), 0))
        finally:
            self.fixture.free_map(values)
        self.assertEqual(peer.creations, 1)

    def test_full_4073_unicode_capacity_preserves_reserved_codes_and_xkb4095(self):
        peer = self.fixture.start()
        session = self.helper._Session(peer.path, protocol.TOKEN)
        symbols = ['U' + format(cp, '04X') for cp in range(0x400, 0x13e9)]
        session.prepare(symbols); self.helper._SESSION = session
        self.helper.inject(chr(0x13e8)); self.helper.inject(key='Return')
        self.assertEqual(peer.raw_keys, [(4087, 1), (4087, 0), (28, 1), (28, 0)])
        # Parse the FD's keycodes/symbols independently; the entire finite space is used.
        codes = [int(code) - 8 for code in re.findall(r'<K\d+>\s*=\s*(\d+);', peer.maps[0].decode())]
        self.assertEqual(len(codes), 4087)
        self.assertEqual(set(codes), set(range(1, 4088)))
        self.assertEqual({key: session.mapping[key] for key, _ in CANONICAL}, dict(CANONICAL))
        values = self.fixture.compile_map(peer.maps[0])
        try:
            buffer = ctypes.create_string_buffer(16)
            count = values[0].xkb_state_key_get_utf8(values[3], 4095, buffer, 16)
            self.assertEqual(buffer.raw[:count].decode(), chr(0x13e8))
        finally:
            self.fixture.free_map(values)
        before = dict(session.mapping)
        with self.assertRaises(ValueError):
            self.helper.inject('😀', backspaces=1)
        self.assertEqual(session.mapping, before)
        self.helper.inject(key='BackSpace')
        self.assertEqual(peer.raw_keys[-2:], [(14, 1), (14, 0)])
        self.assertEqual(peer.creations, 1)
        self.assertEqual(len(peer.maps), 1)

    def test_duplicate_keycodes_are_rejected_before_a_keymap_can_alias_symbols(self):
        with self.assertRaises(ValueError):
            self.helper._keymap({'Return': 28, 'U0061': 28})


if __name__ == '__main__':
    unittest.main()
