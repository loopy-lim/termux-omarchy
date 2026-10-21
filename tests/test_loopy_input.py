"""VK backend wire witnesses; public atomic IM routing has separate tests."""
import array
import ctypes
import ctypes.util
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'guest/desktop/usr/local/lib/loopy/loopy_input.py'
TOKEN = '11111111-2222-3333-4444-555555555555'
U32 = struct.Struct('=I')
HEADER = struct.Struct('=II')


def frame(obj, opcode, body=b''):
    return HEADER.pack(obj, ((8 + len(body)) << 16) | opcode) + body


def string(value):
    data = value.encode() + b'\0'
    return U32.pack(len(data)) + data + bytes((-len(data)) % 4)


class WaylandPeer:
    """Compositor boundary: parses real client requests and mmaps received keymaps."""
    def __init__(self, root, fault=None, fragment=False, native_chords=False):
        self.path = root / 'wayland-1'
        (root / ('display-' + TOKEN)).write_text('wayland-1\n')
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(self.path)); self.listener.listen(1); self.listener.settimeout(2)
        self.fault, self.fragment = fault, fragment
        self.native_chords = native_chords
        self.errors, self.keys, self.maps, self.batches, self.ids, self.modifiers = [], [], [], [], [], []
        self.destroyed, self.connected, self.keymap_fds = False, False, []
        self.creations, self.raw_keys, self.disconnected = 0, [], threading.Event()
        self.received_fd_count, self.key_times = 0, []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True); self.thread.start()

    def send(self, conn, data):
        if self.fragment:
            for start in range(0, len(data), 3): conn.sendall(data[start:start + 3])
        else: conn.sendall(data)

    def serve(self):
        descriptors = []
        try:
            conn, _ = self.listener.accept(); self.connected = True
            with conn:
                conn.settimeout(2); buffer = b''; symbols = {}; held = set(); since_sync = 0; modifier_ready = False
                registry = seat = keyboard = manager = None
                while not self.stop.is_set():
                    while len(buffer) < 8 or len(buffer) < (HEADER.unpack(buffer[:8])[1] >> 16):
                        data, ancillary, _, _ = conn.recvmsg(8192, socket.CMSG_SPACE(32))
                        if not data: return
                        buffer += data
                        for level, kind, value in ancillary:
                            assert (level, kind) == (socket.SOL_SOCKET, socket.SCM_RIGHTS)
                            incoming = array.array('i'); incoming.frombytes(value); descriptors.extend(incoming)
                            self.received_fd_count += len(incoming)
                    obj, word = HEADER.unpack(buffer[:8]); size, opcode = word >> 16, word & 65535
                    assert 8 <= size <= 16384 and size % 4 == 0
                    body, buffer = buffer[8:size], buffer[size:]
                    if obj == 1 and opcode == 1:
                        registry = U32.unpack(body)[0]; self.ids.append(registry)
                        if self.fault == 'frame':
                            conn.sendall(HEADER.pack(1, (6 << 16))); return
                        globals = frame(registry, 0, U32.pack(7) + string('wl_seat') + U32.pack(7))
                        if self.fault != 'missing-manager':
                            globals += frame(registry, 0, U32.pack(9) + string('zwp_virtual_keyboard_manager_v1') + U32.pack(1))
                        if self.fault == 'registry-flood':
                            globals += b''.join(frame(registry, 0, U32.pack(20 + i) + string('unneeded') + U32.pack(1)) for i in range(300))
                        self.send(conn, globals)
                    elif obj == 1 and opcode == 0:
                        callback = U32.unpack(body)[0]; self.ids.append(callback)
                        self.batches.append(since_sync); since_sync = 0
                        if self.fault == 'slow-sync': time.sleep(.05)
                        if self.fault == 'stall' and self.keys:
                            self.stop.wait(1); return
                        if self.fault == 'eof' and self.keys: return
                        if self.fault == 'unexpected-fd':
                            with tempfile.TemporaryFile() as file:
                                conn.sendmsg([frame(callback, 0, U32.pack(1))],
                                    [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [file.fileno()]))])
                            return
                        self.send(conn, frame(callback, 0, U32.pack(1)) +
                                  (b'' if self.fault == 'no-delete' else frame(1, 1, U32.pack(callback))))
                    elif obj == registry and opcode == 0:
                        name, length = struct.unpack_from('=II', body)
                        interface = body[8:8 + length - 1].decode()
                        version, new_id = struct.unpack_from('=II', body, 8 + ((length + 3) & ~3))
                        self.ids.append(new_id)
                        if interface == 'wl_seat':
                            assert (name, version) == (7, 1); seat = new_id
                            self.send(conn, frame(seat, 0, U32.pack(3)))
                        else:
                            assert (name, interface, version) == (9, 'zwp_virtual_keyboard_manager_v1', 1)
                            manager = new_id
                    elif obj == manager and opcode == 0:
                        actual_seat, keyboard = struct.unpack('=II', body)
                        assert actual_seat == seat; self.ids.append(keyboard); self.creations += 1
                    elif obj == keyboard and opcode == 0:
                        fmt, length = struct.unpack('=II', body)  # FD occupies zero payload bytes.
                        assert fmt == 1 and 0 < length <= 4 * 1024 * 1024 and descriptors and not held
                        fd = descriptors.pop(0); self.keymap_fds.append(fd)
                        try: raw = os.pread(fd, length, 0)
                        finally: os.close(fd)
                        assert len(raw) == length and raw.endswith(b'\0')
                        self.maps.append(raw)
                        modifier_ready = False
                        codes = {name: int(code) - 8 for name, code in re.findall(r'<(K\d+)>\s*=\s*(\d+);', raw.decode())}
                        entries = re.findall(r'key\s*<(K\d+)>\s*\{[^}]*symbols\[Group1\]\s*=\s*\[([^]]+)\]', raw.decode())
                        symbols = {codes[name]: symbol for name, symbol in entries}
                        assert len(symbols) == len(codes) and all(1 <= code <= 4087 for code in symbols)
                        if self.native_chords:
                            assert b'pc+us+inet(evdev)' in raw and b'evdev+aliases(qwerty)' in raw
                            symbols = {46: 'c', 47: 'v', 44: 'z', 13: 'plus', 102: 'Home', 14: 'BackSpace'}
                        if self.fault == 'error':
                            self.send(conn, frame(1, 0, struct.pack('=II', keyboard, 0) + string('rejected')))
                        if self.fault == 'invalid-delete':
                            self.send(conn, frame(1, 1, U32.pack(keyboard)))
                    elif obj == keyboard and opcode == 1:
                        stamp, code, state = struct.unpack('=III', body); assert code in symbols and state in (0, 1) and modifier_ready
                        if state: assert code not in held; held.add(code)
                        else: assert code in held; held.remove(code)
                        self.keys.append((symbols[code], state)); self.raw_keys.append((code, state))
                        self.key_times.append(stamp); since_sync += 1
                    elif obj == keyboard and opcode == 2:
                        values = struct.unpack('=IIII', body)
                        assert values[1:] == (0, 0, 0) and (values[0] in (0, 1, 4, 5) if self.native_chords else values[0] == 0)
                        self.modifiers.append(values); modifier_ready = True
                    elif obj == keyboard and opcode == 3:
                        assert not body and not held; self.destroyed = True
                    else: raise AssertionError('unexpected wire request: ' + str((obj, opcode)))
        except (BrokenPipeError, ConnectionResetError): pass
        except BaseException as error:
            if not self.stop.is_set(): self.errors.append(error)
        finally:
            for fd in descriptors: os.close(fd)
            self.disconnected.set()

    def close(self):
        self.stop.set(); self.listener.close(); self.thread.join(3)
        if self.thread.is_alive(): raise AssertionError('fake compositor did not terminate')


class LoopyInputTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HELPER.is_file(), 'bounded bulk Wayland input helper is missing')
        spec = importlib.util.spec_from_file_location('tested_loopy_input', HELPER)
        self.helper = importlib.util.module_from_spec(spec)
        with patch.object(sys, 'path', [str(HELPER.parent)] + sys.path): spec.loader.exec_module(self.helper)
        self.helper.inject = self.helper.inject_virtual  # Explicit VK transport, not an atomic IM claim.
        self.tmp = tempfile.TemporaryDirectory(prefix='loopy-wire-', dir='/tmp')
        self.directory = Path(self.tmp.name).resolve()
        self.env = {'LOOPY_SESSION': TOKEN, 'XDG_RUNTIME_DIR': str(self.directory), 'WAYLAND_DISPLAY': 'wayland-1'}
        self.patches = [patch.object(self.helper, 'IPC_ROOT', self.directory), patch.dict(os.environ, self.env)]
        for p in self.patches: p.start()
        self.peer = None

    def tearDown(self):
        if not hasattr(self, 'tmp'): return
        try:
            if hasattr(self.helper, 'close'): self.helper.close()
            if self.peer: self.peer.close(); self.assertEqual(self.peer.errors, [])
        finally:
            for p in reversed(self.patches): p.stop()
            self.tmp.cleanup()

    def start(self, **kwargs): self.peer = WaylandPeer(self.directory, **kwargs); return self.peer

    def test_unicode_pairs_use_real_fd_keymaps_and_at_most_64_events_per_barrier(self):
        peer = self.start(fragment=True)
        self.helper.inject('한글😀' + '가' * 1360 + '😀', backspaces=2)
        self.helper.close()
        wanted = ['BackSpace', 'BackSpace', 'UD55C', 'UAE00', 'U1F600'] + ['UAC00'] * 1360 + ['U1F600']
        self.assertEqual(peer.keys, [(sym, state) for sym in wanted for state in (1, 0)])
        self.assertTrue(peer.destroyed)
        self.assertLessEqual(max(peer.batches), 64); self.assertLess(len(peer.batches), 50)
        self.assertEqual(sorted(set(peer.ids)), list(range(2, max(peer.ids) + 1)))
        self.assertEqual(len(peer.maps), 1)
        self.assertEqual(peer.modifiers, [(0, 0, 0, 0)])

    def test_more_than_247_unique_unicode_symbols_use_one_stable_map_without_dropping_text(self):
        peer = self.start(); text = ''.join(chr(cp) for cp in range(0x400, 0x400 + 300))
        self.helper.inject(text)
        self.assertEqual(peer.keys, [('U' + format(ord(char), '04X'), state) for char in text for state in (1, 0)])
        self.assertEqual(len(peer.maps), 1)

    def test_bulk_ascii_completes_without_per_transition_sleep(self):
        peer = self.start(); before = time.monotonic()
        try: self.helper.inject('a' * 4096, timeout=2)
        except TimeoutError: self.fail('bounded ASCII job retained per-transition pacing')
        self.assertLess(time.monotonic() - before, 2)
        self.assertEqual(peer.keys, [('U0061', state) for _ in range(4096) for state in (1, 0)])
        self.assertLessEqual(max(peer.batches), 64)

    def test_ordered_jobs_keep_one_keyboard_and_deferred_keycodes_keep_their_meaning(self):
        self.assertTrue(hasattr(self.helper, 'close'), 'persistent input session is missing')
        peer = self.start()
        for text in ('한글😀가', '한가😀x'): self.helper.inject(text)
        self.helper.inject(key='BackSpace'); self.helper.inject(key='Return')
        self.assertEqual(peer.creations, 1); self.assertFalse(peer.destroyed)
        # GTK3 bindings re-query the current map by hardware code after queueing.
        final = self.compile_map(peer.maps[-1])
        try:
            for (code, state), (symbol, _) in zip(peer.raw_keys, peer.keys):
                if state:
                    got = final[0].xkb_state_key_get_one_sym(final[3], code + 8)
                    expected = final[0].xkb_keysym_from_name(symbol.encode(), 0)
                    self.assertEqual(got, expected, 'a later job reassigned a queued keycode')
        finally: self.free_map(final)
        self.assertEqual(len(peer.maps), 2, 'semantic keys rebuilt the map')
        self.helper.close(); self.assertTrue(peer.destroyed)

    def test_callback_ids_reuse_only_acknowledged_deletions_past_8192_jobs(self):
        self.assertTrue(hasattr(self.helper, 'close'), 'persistent input session is missing')
        peer = self.start()
        for _ in range(8200): self.helper.inject(key='Return', timeout=2)
        self.assertEqual(peer.creations, 1); self.assertEqual(len(peer.maps), 1)
        self.assertEqual(len(peer.keys), 16400)
        self.assertLessEqual(max(peer.ids), 8, 'callback objects accumulated across jobs')

    def test_callback_done_without_delete_ack_does_not_permit_id_reuse(self):
        peer = self.start(fault='no-delete')
        for _ in range(20): self.helper.inject(key='Return')
        self.assertEqual(len(peer.ids), len(set(peer.ids)), 'callback.done was mistaken for delete_id')

    def test_invalid_paste_keeps_active_connection_and_later_input_usable(self):
        peer = self.start(); self.helper.inject('a')
        for text in ('invalid\0tail', 'invalid\ud800tail', 'x' * 4097):
            with self.assertRaises(ValueError): self.helper.inject(text, backspaces=2)
        self.helper.inject('가')
        self.assertEqual(peer.keys, [(sym, state) for sym in ('U0061', 'UAC00') for state in (1, 0)])
        self.assertEqual(peer.creations, 1); self.assertFalse(peer.destroyed)

    def test_failed_connection_retains_codes_but_never_replays_partial_input(self):
        peer = self.start(fault='eof')
        with self.assertRaises(OSError): self.helper.inject('a' * 64)
        old_code = peer.raw_keys[0][0]
        self.assertTrue(peer.disconnected.wait(.5)); peer.close(); self.peer = None; self.path_cleanup()
        peer = self.start(); self.helper.inject('b')
        self.assertEqual(peer.keys, [('U0062', 1), ('U0062', 0)])
        self.assertNotEqual(peer.raw_keys[0][0], old_code)
        values = self.compile_map(peer.maps[0])
        try:
            self.assertEqual(values[0].xkb_state_key_get_one_sym(values[3], old_code + 8),
                             values[0].xkb_keysym_from_name(b'U0061', 0))
        finally: self.free_map(values)

    def test_deleting_a_live_keyboard_without_destroy_is_rejected(self):
        peer = self.start(fault='invalid-delete')
        with self.assertRaises(ValueError): self.helper.inject('a')
        self.assertTrue(peer.disconnected.wait(.5)); self.assertEqual(peer.keys, [])

    def test_maximum_session_map_carries_real_fd_and_xkb_keycode_beyond_255(self):
        self.assertTrue(hasattr(self.helper, '_Session'), 'stable symbol allocator is missing')
        peer = self.start(); session = self.helper._Session(peer.path, TOKEN)
        symbols = ['U' + format(cp, '04X') for cp in range(0x400, 0x13e9)]
        session.prepare(symbols); self.helper._SESSION = session
        self.helper.inject(chr(0x13e8))
        self.assertLessEqual(len(peer.maps[0]), 4 * 1024 * 1024)
        self.assertEqual(peer.raw_keys, [(4087, 1), (4087, 0)])
        values = self.compile_map(peer.maps[0])
        try:
            buffer = ctypes.create_string_buffer(16)
            count = values[0].xkb_state_key_get_utf8(values[3], 4095, buffer, 16)
            self.assertEqual(buffer.raw[:count].decode(), chr(0x13e8))
        finally: self.free_map(values)

    def test_exhausted_future_map_is_rejected_before_deletion_or_socket_open(self):
        self.assertTrue(hasattr(self.helper, '_Session'), 'stable symbol allocator is missing')
        peer = self.start(); session = self.helper._Session(peer.path, TOKEN)
        symbols = ['U' + format(cp, '04X') for cp in range(0x400, 0x13e9)]
        session.prepare(symbols)
        with self.assertRaises(ValueError): session.prepare(symbols + ['U1F600'])
        self.helper._SESSION = session
        with self.assertRaises(ValueError): self.helper.inject('😀', backspaces=1)
        self.assertFalse(peer.connected); self.assertEqual(peer.keys, [])
        self.helper.inject(chr(0x13e8))
        with self.assertRaises(ValueError): self.helper.inject('😀', backspaces=1)
        self.helper.inject(chr(0x400))
        self.assertEqual(peer.raw_keys, [(4087, 1), (4087, 0), (2, 1), (2, 0)])
        self.assertEqual(peer.creations, 1); self.assertEqual(len(peer.maps), 1)

    def test_future_fd_byte_budget_is_checked_before_any_deletion_or_connection(self):
        peer = self.start()
        with patch.object(self.helper, 'MAX_KEYMAP', 512, create=True), self.assertRaises(ValueError):
            self.helper.inject('한글😀', backspaces=2)
        self.assertFalse(peer.connected); self.assertEqual(peer.keys, [])

    def test_text_control_characters_and_semantic_keys_have_exact_symbols(self):
        peer = self.start(); self.helper.inject('a\n\t\x1b\b\r\v\x7f', key='Delete')
        self.assertEqual(peer.keys, [(sym, state) for sym in ('U0061', 'Return', 'Tab', 'Escape', 'BackSpace', 'Return', 'Clear', 'Delete', 'Delete') for state in (1, 0)])

    def test_invalid_unicode_and_counts_are_rejected_before_any_deletion_or_connection(self):
        peer = self.start()
        for args in ({'text': 'bad\0text'}, {'text': '\ud800'}, {'text': 'x' * 4097},
                     {'text': 'ok', 'backspaces': -1}, {'text': 'ok', 'backspaces': True},
                     {'text': 'ok', 'backspaces': 65}, {'text': 'ok', 'key': 'Return; exec unsafe'}):
            with self.subTest(args=repr(args)), self.assertRaises(ValueError): self.helper.inject(**args)
        self.assertFalse(peer.connected); self.assertEqual(peer.keys, [])

    def test_current_session_display_marker_and_socket_path_escape_are_enforced(self):
        peer = self.start()
        for display in ('../wayland-1', '/tmp/wayland-1', 'wayland-0', '.', ''):
            with self.subTest(display=display), patch.dict(os.environ, {'WAYLAND_DISPLAY': display}), self.assertRaises(ValueError):
                self.helper.inject('a', backspaces=1)
        self.assertFalse(peer.connected)

    def test_malformed_frames_and_missing_protocol_fail_without_input(self):
        for fault in ('frame', 'missing-manager', 'unexpected-fd', 'registry-flood'):
            with self.subTest(fault=fault):
                peer = self.start(fault=fault)
                with self.assertRaises((ValueError, OSError)): self.helper.inject('a')
                peer.close(); self.assertEqual(peer.keys, []); self.assertEqual(peer.errors, [])
                self.peer = None; self.path_cleanup()

    def path_cleanup(self): (self.directory / 'wayland-1').unlink()

    def test_compositor_error_after_keymap_is_explicit_failure_without_replay(self):
        peer = self.start(fault='error')
        with self.assertRaises(ValueError): self.helper.inject('secret input')
        self.assertEqual(peer.keys, [])

    def test_timeout_is_total_job_deadline_and_ends_owned_connection(self):
        peer = self.start(fault='stall'); before = time.monotonic()
        with self.assertRaises(TimeoutError): self.helper.inject('x' * 64, timeout=.12)
        self.assertLess(time.monotonic() - before, .5)
        self.assertLessEqual(len(peer.keys), 64)

    def test_deadline_is_not_renewed_for_each_compositor_sync(self):
        peer = self.start(fault='slow-sync'); before = time.monotonic()
        with self.assertRaises(TimeoutError): self.helper.inject('x' * 32, timeout=.12)
        self.assertLess(time.monotonic() - before, .5)

    def test_short_fd_sendmsg_transfers_ancillary_once_and_completes_frames(self):
        peer = self.start(); real_socket = socket.socket
        class ShortSocket:
            def __init__(self, *args, **kwargs): self.socket = real_socket(*args, **kwargs)
            def __getattr__(self, name): return getattr(self.socket, name)
            def __enter__(self): return self
            def __exit__(self, *args): self.socket.close()
            def send(self, data): return self.socket.send(data[:7])
            def sendmsg(self, buffers, ancillary): return self.socket.sendmsg([b''.join(buffers)[:5]], ancillary)
        with patch.object(socket, 'socket', ShortSocket): self.helper.inject('한😀')
        self.assertEqual(peer.keys, [(sym, state) for sym in ('UD55C', 'U1F600') for state in (1, 0)])
        self.assertEqual(len(peer.keymap_fds), 1)
        self.assertEqual(peer.received_fd_count, 1, 'short sendmsg repeated SCM_RIGHTS')

    def test_unexpected_inbound_descriptor_is_closed_before_rejection(self):
        self.start(fault='unexpected-fd'); closed = []; original = os.close
        def close(fd): closed.append(fd); original(fd)
        with patch.object(os, 'close', side_effect=close), self.assertRaises(ValueError): self.helper.inject('a')
        self.assertEqual(len(closed), 1)
        with self.assertRaises(OSError): os.fstat(closed[0])

    def test_keymap_fd_compiles_with_actual_xkb_and_preserves_utf8(self):
        peer = self.start(); self.helper.inject('한글😀a\x01\x85\ud7ff\ue000\U0010ffff')
        values = self.compile_map(peer.maps[0]); xkb, context, keymap, state = values
        try:
            pressed = [code + 8 for code, down in peer.raw_keys if down]
            for code, expected in zip(pressed, ('한', '글', '😀', 'a', '\x01', '\x85', '\ud7ff', '\ue000', '\U0010ffff')):
                buffer = ctypes.create_string_buffer(16); count = xkb.xkb_state_key_get_utf8(state, code, buffer, 16)
                self.assertEqual(buffer.raw[:count].decode(), expected)
        finally: self.free_map(values)

    def compile_map(self, data):
        library = ROOT / 'build/host-xkb/out/libxkbcommon.0.dylib'
        name = str(library) if library.is_file() else ctypes.util.find_library('xkbcommon')
        if not name: self.skipTest('host libxkbcommon is unavailable; wire tests still run')
        xkb = ctypes.CDLL(name)
        signatures = {'xkb_context_new': (ctypes.c_void_p, [ctypes.c_int]),
                      'xkb_keymap_new_from_string': (ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]),
                      'xkb_state_new': (ctypes.c_void_p, [ctypes.c_void_p]),
                      'xkb_state_key_get_utf8': (ctypes.c_int, [ctypes.c_void_p, ctypes.c_uint, ctypes.c_char_p, ctypes.c_size_t]),
                      'xkb_state_key_get_one_sym': (ctypes.c_uint, [ctypes.c_void_p, ctypes.c_uint]),
                      'xkb_keysym_from_name': (ctypes.c_uint, [ctypes.c_char_p, ctypes.c_int]),
                      'xkb_context_unref': (None, [ctypes.c_void_p]), 'xkb_keymap_unref': (None, [ctypes.c_void_p]),
                      'xkb_state_unref': (None, [ctypes.c_void_p])}
        for fn, (restype, argtypes) in signatures.items():
            getattr(xkb, fn).restype = restype; getattr(xkb, fn).argtypes = argtypes
        context = xkb.xkb_context_new(1); self.assertTrue(context); keymap = state = None
        try:
            keymap = xkb.xkb_keymap_new_from_string(context, data, 1, 0)
            self.assertTrue(keymap, 'wire FD carries an invalid XKB map'); state = xkb.xkb_state_new(keymap)
            self.assertTrue(state); return xkb, context, keymap, state
        except BaseException:
            if state: xkb.xkb_state_unref(state)
            if keymap: xkb.xkb_keymap_unref(keymap)
            xkb.xkb_context_unref(context)
            raise

    @staticmethod
    def free_map(values):
        xkb, context, keymap, state = values
        xkb.xkb_state_unref(state); xkb.xkb_keymap_unref(keymap); xkb.xkb_context_unref(context)

    def actions(self):
        path = HELPER.with_name('desktop_actions.py')
        spec = importlib.util.spec_from_file_location('wire_actions', path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'loopy_input': self.helper}): spec.loader.exec_module(module)
        return module

    def test_all_semantic_keys_use_balanced_virtual_keyboard_pairs(self):
        peer = self.start()
        for key in ('Return', 'BackSpace', 'Delete', 'Tab', 'Escape', 'Up', 'Down', 'Left', 'Right', 'Home', 'End', 'Prior', 'Next'):
            with self.subTest(key=key):
                self.helper.inject(key=key)
                self.assertEqual(peer.keys[-2:], [(key, 1), (key, 0)])
        self.assertEqual(peer.creations, 1); self.assertEqual(len(peer.maps), 1)

    def test_guest_execute_uses_exact_unicode_transport_without_starting_wtype(self):
        actions = self.actions(); peer = self.start()
        with patch.object(actions.subprocess, 'run', side_effect=AssertionError('obsolete per-character wtype invoked')):
            actions.execute({'action': 'input', 'text': '한😀', 'backspaces': 2})
        self.assertEqual(peer.keys, [(sym, state) for sym in ('BackSpace', 'BackSpace', 'UD55C', 'U1F600') for state in (1, 0)])
        with patch.object(actions.subprocess, 'run', side_effect=AssertionError('obsolete semantic wtype invoked')):
            actions.execute({'action': 'ime-key', 'key': 'Return'})
        self.assertEqual(peer.keys[-2:], [('Return', 1), ('Return', 0)]); self.assertEqual(peer.creations, 1)

    def test_worker_records_partial_transport_failure_without_replay_or_text_leak(self):
        actions = self.actions(); peer = self.start(fault='eof')
        job = self.directory / ('command-' + TOKEN + '-0000000000000001.json')
        job.write_text(json.dumps({'action': 'input', 'text': 'private text ' * 20, 'backspaces': 0}))
        with patch.object(actions.subprocess, 'run', side_effect=AssertionError('partial input replayed through wtype')):
            actions.consume(self.directory, TOKEN)
        self.assertFalse(job.exists()); self.assertEqual(len(peer.keys), 64)
        error = (self.directory / ('error-' + TOKEN + '.log')).read_text()
        self.assertEqual(error, 'Desktop command failed: OSError\n'); self.assertNotIn('private text', error)


if __name__ == '__main__': unittest.main()
