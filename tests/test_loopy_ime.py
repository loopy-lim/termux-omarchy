"""Atomic IMv2 and VK ordering witnessed by an independent Unix wire peer."""
import array
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
U32, HEADER = struct.Struct('=I'), struct.Struct('=II')


def frame(obj, opcode, body=b''):
    return HEADER.pack(obj, ((len(body) + 8) << 16) | opcode) + body


def string(value):
    data = value.encode('utf-8') + b'\0'
    return U32.pack(len(data)) + data + bytes((-len(data)) % 4)


def read_string(body):
    length = U32.unpack_from(body)[0]; end = 4 + ((length + 3) & ~3)
    assert length >= 1 and end <= len(body) and body[3 + length] == 0
    return body[4:3 + length].decode(), end


class ImePeer:
    def __init__(self, root, mode='gtk', initial='', fault=None, cursor=None):
        self.path = root / 'wayland-1'; (root / ('display-' + TOKEN)).write_text('wayland-1\n')
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(self.path)); self.listener.listen(1); self.listener.settimeout(2)
        self.mode, self.fault, self.text = mode, fault, initial
        self.cursor = len(initial.encode()) if cursor is None else cursor; self.serial = 0
        self.anchor = 0 if fault == 'selection' else self.cursor
        self.order, self.commits, self.deletions, self.keys, self.maps, self.ids, self.errors = [], [], [], [], [], [], []
        self.im_count = self.vk_count = 0; self.queued_context = False; self.request_serials = []
        self.app_queue = []; self.cached = initial, self.cursor, self.anchor
        self.stop, self.closed = threading.Event(), threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True); self.thread.start()

    def state(self, conn, active=None):
        data = b''
        if active is not None: data += frame(self.im, 0 if active else 1)
        if self.mode == 'gtk':
            text, cursor, actual_anchor = self.cached if self.fault == 'async-surrounding' else (self.text, self.cursor, self.anchor)
            raw = text.encode(); original_cursor = cursor
            # GTK's 4000-byte surrounding window follows a cursor at its end.
            prefix = raw[:cursor].decode(); suffix = raw[cursor:].decode()
            while len((prefix + suffix).encode()) > 4000: prefix = prefix[1:]
            raw = (prefix + suffix).encode(); cursor = len(prefix.encode())
            anchor = 1 if self.fault == 'badcursor' else actual_anchor - (original_cursor - cursor)
            data += frame(self.im, 2, string(raw.decode()) + struct.pack('=II', cursor, anchor))
        data += frame(self.im, 4, struct.pack('=II', 0, 13 if self.mode == 'foot' else 0))
        self.serial = (self.serial + 1) & 0xffffffff
        conn.sendall(data + frame(self.im, 5))

    def apply_app(self, text=None, key=None):
        raw = self.text.encode(); start, end = sorted((self.cursor, self.anchor))
        if text is not None:
            raw = raw[:start] + text.encode() + raw[end:]; self.cursor = start + len(text.encode())
        elif key in ('BackSpace', 'Delete'):
            if start == end:
                if key == 'BackSpace': start -= len(raw[:start].decode()[-1:].encode())
                else: end += len(raw[end:].decode()[:1].encode())
            raw = raw[:start] + raw[end:]; self.cursor = start
        self.anchor = self.cursor; self.text = raw.decode()

    def serve(self):
        fds = []
        try:
            conn, _ = self.listener.accept()
            with conn:
                conn.settimeout(2); buffer = b''; objects = {1: 'display'}; symbols = {}; held = set()
                pending_text, pending_delete = None, (0, 0)
                while not self.stop.is_set():
                    while len(buffer) < 8 or len(buffer) < (HEADER.unpack_from(buffer)[1] >> 16):
                        data, ancillary, _, _ = conn.recvmsg(8192, socket.CMSG_SPACE(32))
                        if not data: return
                        buffer += data
                        for level, kind, value in ancillary:
                            assert (level, kind) == (socket.SOL_SOCKET, socket.SCM_RIGHTS)
                            descriptors = array.array('i'); descriptors.frombytes(value); fds.extend(descriptors)
                    obj, word = HEADER.unpack_from(buffer); size, opcode = word >> 16, word & 65535
                    assert 8 <= size <= 16384 and size % 4 == 0
                    body, buffer = buffer[8:size], buffer[size:]; kind = objects[obj]
                    if kind == 'display' and opcode == 1:
                        registry = U32.unpack(body)[0]; objects[registry] = 'registry'; self.ids.append(registry)
                        conn.sendall(b''.join(frame(registry, 0, U32.pack(name) + string(interface) + U32.pack(1))
                            for name, interface in ((7, 'wl_seat'), (9, 'zwp_virtual_keyboard_manager_v1'), (11, 'zwp_input_method_manager_v2'))))
                    elif kind == 'display' and opcode == 0:
                        callback = U32.unpack(body)[0]; self.ids.append(callback)
                        if self.fault == 'stall' and self.commits: self.stop.wait(1); return
                        for operation in self.app_queue: self.apply_app(**operation)
                        self.app_queue.clear()
                        conn.sendall(frame(callback, 0, U32.pack(1)) + frame(1, 1, U32.pack(callback)))
                        if self.fault == 'queued-context' and len(self.commits) == 1 and not self.queued_context:
                            self.queued_context = True; self.state(conn)
                        if self.fault == 'queued-delete-context' and self.maps and not self.queued_context:
                            self.queued_context = True; self.text = 'abcd'; self.cursor = self.anchor = 4; self.state(conn)
                    elif kind == 'registry':
                        name = U32.unpack_from(body)[0]; interface, end = read_string(body[4:]); end += 4
                        version, value = struct.unpack_from('=II', body, end); assert version == 1
                        objects[value] = {7: 'seat', 9: 'vk-manager', 11: 'im-manager'}[name]; self.ids.append(value)
                        if name == 7: conn.sendall(frame(value, 0, U32.pack(3)))
                    elif kind == 'vk-manager':
                        seat, value = struct.unpack('=II', body); assert objects[seat] == 'seat'
                        objects[value] = 'vk'; self.vk_count += 1; self.ids.append(value)
                    elif kind == 'im-manager' and opcode == 0:
                        seat, self.im = struct.unpack('=II', body); assert objects[seat] == 'seat'
                        objects[self.im] = 'im'; self.im_count += 1; self.ids.append(self.im)
                        if self.fault == 'busy': conn.sendall(frame(self.im, 6))
                        elif self.fault == 'flood': conn.sendall(frame(self.im, 0) + frame(self.im, 5) * 4200)
                        elif self.mode != 'inactive': self.state(conn, True)
                    elif kind == 'im' and opcode == 0:
                        pending_text, end = read_string(body); assert end == len(body) and len(pending_text.encode()) <= 4000
                    elif kind == 'im' and opcode == 2:
                        pending_delete = struct.unpack('=II', body)
                    elif kind == 'im' and opcode == 3:
                        serial = U32.unpack(body)[0]
                        self.request_serials.append(serial)
                        if self.fault == 'stale': self.state(conn)
                        if serial == self.serial:
                            if self.fault == 'async-surrounding': self.cached = self.text, self.cursor, self.anchor
                            before, after = pending_delete
                            raw = self.text.encode(); start, end = sorted((self.cursor, self.anchor))
                            assert before <= start and after <= len(raw) - end
                            raw = raw[:start - before] + (pending_text or '').encode() + raw[end + after:]
                            self.cursor = start + len((pending_text or '').encode()) - before
                            self.anchor = self.cursor
                            if self.fault == 'async-surrounding':
                                assert (before, after) == (0, 0), 'cached surrounding must not determine deletion bytes'
                                self.text, self.cursor, self.anchor = self.cached
                                self.app_queue.append({'text': pending_text})
                            else: self.text = raw.decode()
                            if before or after: self.deletions.append((before, after)); self.order.append(('delete', before, after))
                            if pending_text is not None: self.commits.append(pending_text); self.order.append(('text', pending_text))
                            if self.fault == 'disconnect': return
                            if self.fault == 'delay': time.sleep(.08)
                            if self.fault != 'foot-no-done': self.state(conn, False if self.fault == 'deactivate' else None)
                        pending_text, pending_delete = None, (0, 0)
                    elif kind == 'im' and opcode == 6:
                        objects.pop(obj); conn.sendall(frame(1, 1, U32.pack(obj)))
                    elif kind == 'im-manager' and opcode == 1:
                        assert not body; objects.pop(obj); conn.sendall(frame(1, 1, U32.pack(obj)))
                    elif kind == 'vk' and opcode == 0:
                        fmt, length = struct.unpack('=II', body); assert fmt == 1 and fds and not held
                        fd = fds.pop(0)
                        try: raw = os.pread(fd, length, 0)
                        finally: os.close(fd)
                        self.maps.append(raw); codes = {name: int(code) - 8 for name, code in re.findall(r'<(K\d+)>\s*=\s*(\d+);', raw.decode())}
                        symbols = {codes[name]: symbol for name, symbol in re.findall(r'key\s*<(K\d+)>\s*\{[^}]*symbols\[Group1\]\s*=\s*\[([^]]+)\]', raw.decode())}
                        if self.fault == 'change-map':
                            self.text = 'abcd'; self.cursor = self.anchor = 4; self.state(conn)
                    elif kind == 'vk' and opcode == 1:
                        _, code, down = struct.unpack('=III', body); symbol = symbols[code]
                        if down: assert code not in held; held.add(code)
                        else: assert code in held; held.remove(code)
                        self.keys.append((symbol, down)); self.order.append(('key', symbol, down))
                        if down:
                            if self.fault == 'async-surrounding': self.app_queue.append({'key': symbol})
                            else: self.apply_app(key=symbol)
                        if self.fault == 'tab-context' and down and symbol == 'Tab':
                            self.state(conn, False); self.text = 'right'; self.cursor = self.anchor = 5; self.state(conn, True)
                        if self.fault in ('activate-vk', 'activate-foot') and len(self.keys) == 64: self.state(conn, True)
                    elif kind == 'vk' and opcode == 2: assert struct.unpack('=IIII', body) == (0, 0, 0, 0)
                    elif kind == 'vk' and opcode == 3:
                        assert not held; objects.pop(obj); conn.sendall(frame(1, 1, U32.pack(obj)))
                    else: raise AssertionError('unexpected request ' + str((kind, opcode)))
        except (BrokenPipeError, ConnectionResetError): pass
        except BaseException as error:
            if not self.stop.is_set(): self.errors.append(error)
        finally:
            for fd in fds: os.close(fd)
            self.closed.set()

    def close(self):
        self.stop.set(); self.listener.close(); self.thread.join(3)
        assert not self.thread.is_alive()


class LoopyImeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='loopy-ime-', dir='/tmp'); self.directory = Path(self.tmp.name).resolve()
        spec = importlib.util.spec_from_file_location('atomic_loopy_input', HELPER)
        self.helper = importlib.util.module_from_spec(spec)
        with patch.object(sys, 'path', [str(HELPER.parent)] + sys.path): spec.loader.exec_module(self.helper)
        self.env = patch.dict(os.environ, LOOPY_SESSION=TOKEN, XDG_RUNTIME_DIR=str(self.directory), WAYLAND_DISPLAY='wayland-1')
        self.root_patch = patch.object(self.helper, 'IPC_ROOT', self.directory)
        self.select_patch = patch.object(self.helper, 'ACTIVATE_TIMEOUT', .025)
        self.env.start(); self.root_patch.start(); self.select_patch.start(); self.peer = None

    def tearDown(self):
        try:
            self.helper.close()
            if self.peer: self.peer.close(); self.assertEqual(self.peer.errors, [])
        finally: self.select_patch.stop(); self.root_patch.stop(); self.env.stop(); self.tmp.cleanup()

    def start(self, **kwargs): self.peer = ImePeer(self.directory, **kwargs); return self.peer

    def test_long_unicode_is_atomic_and_scalar_bounded_without_key_per_character(self):
        peer = self.start(); text = '가' * 1364 + '😀'
        self.helper.inject(text); self.helper.inject('한글😀'); self.helper.inject(key='Return')
        self.assertEqual(''.join(peer.commits), text + '한글😀'); self.assertEqual(peer.im_count, 1)
        self.assertTrue(all(len(part.encode()) <= 4000 for part in peer.commits))
        self.assertEqual(peer.keys, [('Return', 1), ('Return', 0)])
        self.assertEqual(peer.order[-2:], [('key', 'Return', 1), ('key', 'Return', 0)])

    def test_async_application_cached_surrounding_does_not_block_exact_long_ime_queue(self):
        peer = self.start(fault='async-surrounding'); prefix = '한글😀'; body = '가' * 1400 + '😀'
        try:
            self.helper.inject(prefix, timeout=.12)
            self.helper.inject('가' * 1365, timeout=.12)
            self.helper.inject('가' * 35 + '😀x', timeout=.12)
            self.helper.inject(backspaces=1, timeout=.12); self.helper.inject(key='Return', timeout=.12)
        except TimeoutError: self.fail('fresh done with cached old surrounding was treated as a text delivery ACK')
        self.assertEqual(peer.text, prefix + body)
        self.assertEqual(peer.commits, [prefix, '가' * 1333, '가' * 32, '가' * 35 + '😀x'])
        self.assertEqual(peer.deletions, [])
        self.assertEqual(peer.keys, [('BackSpace', 1), ('BackSpace', 0), ('Return', 1), ('Return', 0)])
        self.assertEqual(peer.im_count, 1)

    def test_cached_gtk_context_deletion_uses_ordered_keys_without_waiting_for_done(self):
        peer = self.start(initial='😀한x', fault='async-surrounding', cursor=4)
        try: self.helper.inject('\x7f\b글', timeout=.12)
        except (OSError, ValueError): self.fail('cached context determined deletion bytes or waited for app confirmation')
        self.assertEqual(peer.text, '글x'); self.assertEqual(peer.deletions, [])
        self.assertEqual(peer.keys, [('Delete', 1), ('Delete', 0), ('BackSpace', 1), ('BackSpace', 0)])

    def test_queued_surrounding_done_is_drained_before_a_second_atomic_commit(self):
        peer = self.start(fault='queued-context'); text = '가' * 1365
        self.helper.inject(text)
        self.assertEqual(peer.commits, ['가' * 1333, '가' * 32])
        self.assertEqual(peer.text, text); self.assertEqual(peer.keys, [])

    def test_queued_context_does_not_determine_backspace_byte_lengths(self):
        peer = self.start(initial='😀', fault='queued-delete-context')
        try: self.helper.inject('한', backspaces=1, timeout=.12)
        except TimeoutError: self.fail('deletion used stale UTF-8 context or request serial')
        self.assertEqual(peer.deletions, []); self.assertEqual(peer.text, 'abc한')
        self.assertEqual(peer.keys, [('BackSpace', 1), ('BackSpace', 0)])

    def test_gtk_unicode_deletion_uses_native_balanced_keys_before_atomic_text(self):
        peer = self.start(initial='ab😀한'); self.helper.inject('글', backspaces=2)
        self.assertEqual(peer.deletions, []); self.assertEqual(peer.text, 'ab글')
        pairs = [('BackSpace', down) for _ in range(2) for down in (1, 0)]
        self.assertEqual(peer.keys, pairs)
        self.assertEqual(peer.order, [('key', key, down) for key, down in pairs] + [('text', '글')])

    def test_foot_unsupported_surrounding_uses_only_vk_deletion_and_atomic_text(self):
        peer = self.start(mode='foot'); self.helper.inject('한글😀\n', backspaces=2)
        self.assertEqual(peer.commits, ['한글😀']); self.assertEqual(peer.deletions, [])
        self.assertEqual(peer.keys, [(key, state) for key in ('BackSpace', 'BackSpace', 'Return') for state in (1, 0)])
        self.assertEqual(peer.order[4], ('text', '한글😀'))

    def test_foot_without_followup_done_keeps_atomic_text_and_semantic_order(self):
        peer = self.start(mode='foot', fault='foot-no-done')
        self.helper.inject('한' * 1365, timeout=.12); self.helper.inject(key='Return', timeout=.12)
        self.assertEqual(peer.text, '한' * 1365); self.assertEqual(peer.commits, ['한' * 1333, '한' * 32])
        self.assertEqual(peer.request_serials, [1, 1]); self.assertEqual(peer.keys, [('Return', 1), ('Return', 0)])

    def test_busy_owner_fails_without_text_key_or_clipboard_fallback(self):
        peer = self.start(fault='busy')
        with self.assertRaises(ValueError): self.helper.inject('private', backspaces=1)
        self.assertEqual(peer.commits, []); self.assertEqual(peer.keys, []); self.assertTrue(peer.closed.wait(.5))

    def test_deactivation_after_commit_never_replays_tail_in_another_backend(self):
        peer = self.start(fault='deactivate'); text = '가' * 1364
        with self.assertRaises(ValueError): self.helper.inject(text)
        self.assertEqual(len(peer.commits), 1); self.assertEqual(peer.keys, [])
        self.assertTrue(peer.closed.wait(.5))

    def test_disconnected_atomic_prefix_is_never_replayed(self):
        peer = self.start(fault='disconnect')
        with self.assertRaises(OSError): self.helper.inject('private ' * 500)
        self.assertEqual(len(peer.commits), 1); self.assertEqual(peer.keys, [])

    def test_semantic_keys_do_not_require_active_ime(self):
        peer = self.start(mode='inactive'); self.helper.inject(key='Tab'); self.helper.inject(key='Return')
        self.assertEqual(peer.im_count, 0); self.assertEqual(peer.keys, [(key, state) for key in ('Tab', 'Return') for state in (1, 0)])

    def test_invalid_text_does_not_damage_an_active_atomic_connection(self):
        peer = self.start(); self.helper.inject('a')
        for text in ('bad\0tail', 'bad\ud800tail', 'a' * 4097):
            with self.assertRaises(ValueError): self.helper.inject(text, backspaces=1)
        self.helper.inject('b'); self.assertEqual(peer.text, 'ab'); self.assertEqual(peer.im_count, 1)

    def test_public_guest_execute_uses_atomic_text_and_same_wire_return(self):
        peer = self.start(); spec = importlib.util.spec_from_file_location('atomic_actions', HELPER.with_name('desktop_actions.py'))
        actions = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'loopy_input': self.helper}), patch.object(sys, 'path', [str(HELPER.parent)] + sys.path): spec.loader.exec_module(actions)
        with patch.object(actions.subprocess, 'run', side_effect=AssertionError('unexpected external input process')):
            actions.execute({'action': 'input', 'text': '한😀', 'backspaces': 0})
            actions.execute({'action': 'ime-key', 'key': 'Return'})
        self.assertEqual(peer.commits, ['한😀']); self.assertEqual(peer.keys, [('Return', 1), ('Return', 0)])

    def test_done_serial_wraps_without_disabling_a_valid_active_context(self):
        state = self.helper.loopy_ime.State(); state.event(0, b'')
        state.serial = 0xffffffff; state.event(5, b'')
        self.assertEqual(state.serial, 0); self.assertTrue(state.ready)

    def test_fresh_done_with_old_surrounding_is_only_a_state_barrier(self):
        state = self.helper.loopy_ime.State(); state.event(0, b'')
        state.event(2, string('a') + struct.pack('=II', 1, 1)); state.event(5, b'')
        state.expect_done(); self.assertFalse(state.settled())
        state.event(2, string('a') + struct.pack('=II', 1, 1)); state.event(5, b'')
        self.assertTrue(state.settled())  # Old cached text cannot acknowledge an application edit.

    def test_clean_initial_inactive_editor_preselects_virtual_without_atomic_replay(self):
        peer = self.start(mode='inactive'); self.helper.inject('ab', backspaces=1)
        self.assertEqual(peer.im_count, 1); self.assertEqual(peer.commits, [])
        self.assertEqual(peer.keys, [(key, state) for key in ('BackSpace', 'U0061', 'U0062') for state in (1, 0)])

    def test_activation_mid_virtual_prefix_aborts_remaining_input(self):
        peer = self.start(mode='inactive', fault='activate-vk')
        with self.assertRaises(ValueError): self.helper.inject('a' * 64)
        self.assertEqual(len(peer.keys), 64); self.assertEqual(peer.commits, [])
        self.assertTrue(peer.closed.wait(.5))

    def test_malformed_surrounding_cursor_fails_before_any_edit(self):
        peer = self.start(initial='한', fault='badcursor')
        with self.assertRaises(ValueError): self.helper.inject('글', backspaces=1)
        self.assertEqual(peer.commits, []); self.assertEqual(peer.deletions, []); self.assertEqual(peer.keys, [])

    def test_native_backspace_keeps_application_selection_semantics(self):
        peer = self.start(initial='abc', fault='selection')
        self.helper.inject('글', backspaces=1); self.helper.inject('한')
        self.assertEqual(peer.text, '글한'); self.assertEqual(peer.im_count, 1); self.assertEqual(peer.deletions, [])
        self.assertEqual(peer.keys, [('BackSpace', 1), ('BackSpace', 0)])

    def test_stale_serial_silent_discard_has_no_app_ack_and_is_never_replayed(self):
        peer = self.start(fault='stale'); before = time.monotonic()
        self.helper.inject('not accepted', timeout=.12)
        self.assertLess(time.monotonic() - before, .5)
        self.assertEqual(peer.text, ''); self.assertEqual(peer.commits, []); self.assertEqual(peer.keys, [])
        self.assertEqual(len(peer.request_serials), 1)  # Only the app witness can establish missing delivery.

    def test_whole_deadline_is_not_renewed_across_commit_segments(self):
        peer = self.start(fault='delay'); before = time.monotonic()
        with self.assertRaises(TimeoutError): self.helper.inject('a' * 4001, timeout=.12)
        self.assertLess(time.monotonic() - before, .5)
        self.assertEqual(peer.commits, ['a' * 4000, 'a']); self.assertEqual(peer.keys, [])

    def test_selected_virtual_future_capacity_rejection_preserves_live_wire(self):
        peer = self.start(mode='inactive'); session = self.helper._Session(peer.path, TOKEN)
        session.prepare(['U' + format(cp, '04X') for cp in range(0x400, 0x13e9)])
        self.helper._SESSION = session
        with self.assertRaises(ValueError): self.helper.inject('😀', backspaces=1)
        self.assertEqual(peer.commits, []); self.assertEqual(peer.keys, [])
        self.helper.inject(chr(0x400)); self.assertEqual(peer.keys, [('U0400', 1), ('U0400', 0)])
        self.assertEqual(peer.im_count, 1)

    def test_surrounding_change_pending_is_not_current_until_done(self):
        state = self.helper.loopy_ime.State(); state.event(0, b'')
        state.event(2, string('😀한') + struct.pack('=II', 7, 7)); state.event(5, b'')
        self.assertEqual(state.surrounding, ('😀한'.encode(), 7, 7))
        state.event(2, string('ab') + struct.pack('=II', 2, 2))
        self.assertEqual(state.surrounding, ('😀한'.encode(), 7, 7))
        state.event(5, b''); self.assertEqual(state.surrounding, (b'ab', 2, 2))

    def test_activation_does_not_reset_done_serial_and_one_byte_overflow_never_sends(self):
        state = self.helper.loopy_ime.State(); state.event(0, b''); state.event(5, b'')
        state.event(1, b''); state.event(5, b''); state.event(0, b''); state.event(5, b'')
        self.assertEqual(state.serial, 3)
        with self.assertRaises(ValueError): self.helper.loopy_ime.string('a' * 4001)

    def test_native_backspace_ignores_previous_context_after_map_sync(self):
        peer = self.start(initial='😀', fault='change-map'); self.helper.inject('한', backspaces=1)
        self.assertEqual(peer.deletions, []); self.assertEqual(peer.text, 'abc한')
        self.assertEqual(peer.keys, [('BackSpace', 1), ('BackSpace', 0)])

    def test_foot_epoch_change_mid_deletion_aborts_the_second_batch(self):
        peer = self.start(mode='foot', fault='activate-foot')
        with self.assertRaises(ValueError): self.helper.inject('tail', backspaces=64)
        self.assertEqual(len(peer.keys), 64); self.assertEqual(peer.commits, [])

    def test_valid_protocol_string_padding_need_not_be_zero(self):
        body = bytearray(string('a')); body[-2:] = b'xy'
        raw, end = self.helper.loopy_ime.read_string(bytes(body))
        self.assertEqual(raw, b'a'); self.assertEqual(end, len(body))

    def test_unchanged_unsaturated_surrounding_does_not_assert_app_delivery(self):
        state = self.helper.loopy_ime.State(); state.event(0, b'')
        current = 'a' * 300
        state.event(2, string(current) + struct.pack('=II', 300, 300)); state.event(5, b'')
        state.expect_done(); self.assertFalse(state.settled())
        state.event(2, string(current) + struct.pack('=II', 300, 300)); state.event(5, b'')
        self.assertTrue(state.settled())

    def test_literal_backspace_before_text_does_not_wait_for_application_state(self):
        peer = self.start(initial='ab', fault='vk-edit-no-state')
        try: self.helper.inject('\bc', timeout=.12)
        except TimeoutError: self.fail('a queued VK deletion left the later commit using stale surrounding state')
        self.assertEqual(peer.text, 'ac'); self.assertEqual(peer.deletions, [])
        self.assertEqual(peer.keys, [('BackSpace', 1), ('BackSpace', 0)])

    def test_full_ascii_job_uses_two_atomic_commits_and_no_per_character_keys(self):
        peer = self.start(); self.helper.inject('a' * 4096)
        self.assertEqual(peer.commits, ['a' * 4000, 'a' * 96]); self.assertEqual(peer.keys, [])
        self.assertEqual(peer.text, 'a' * 4096)

    def test_atomic_unicode_does_not_consume_or_depend_on_virtual_symbol_capacity(self):
        peer = self.start(); session = self.helper._Session(peer.path, TOKEN)
        session.prepare(['U' + format(cp, '04X') for cp in range(0x400, 0x13e9)])
        self.helper._SESSION = session
        self.helper.inject('😀'); self.assertEqual(peer.commits, ['😀']); self.assertEqual(peer.keys, [])
        self.assertNotIn('U1F600', session.mapping)

    def test_saturated_repeated_window_is_a_state_barrier_without_delivery_ack(self):
        state = self.helper.loopy_ime.State(); state.event(0, b'')
        current = 'a' * 4000
        state.event(2, string(current) + struct.pack('=II', 4000, 4000)); state.event(5, b'')
        state.expect_done(); self.assertFalse(state.settled())
        # Insertion and unchanged text can produce identical bounded windows.
        state.event(2, string(current) + struct.pack('=II', 4000, 4000)); state.event(5, b'')
        self.assertTrue(state.settled())  # Exact DOM/PTY acceptance must be witnessed separately.

    def test_gtk_four_byte_edge_trimming_can_refill_a_3992_byte_window(self):
        state = self.helper.loopy_ime.State(); state.event(0, b'')
        current = '😀' * 998  # GTK trims one complete scalar at each 4000-byte window edge.
        state.event(2, string(current) + struct.pack('=II', 1996, 1996)); state.event(5, b'')
        state.expect_done()
        # Deleting one emoji recenters/refills from outside the represented window.
        state.event(2, string(current) + struct.pack('=II', 1996, 1996)); state.event(5, b'')
        self.assertTrue(state.settled())
        # This repeated-window barrier cannot distinguish an edit from unchanged text.

    def test_literal_forward_delete_uses_balanced_native_keys_and_keeps_insertion_order(self):
        peer = self.start(initial='😀한x', cursor=4); self.helper.inject('\x7fx')
        self.assertEqual(peer.deletions, []); self.assertEqual(peer.text, '😀xx')
        self.assertEqual(peer.keys, [('Delete', 1), ('Delete', 0)])

    def test_tab_focus_change_aborts_text_tail_instead_of_sending_to_new_field(self):
        peer = self.start(initial='left', fault='tab-context')
        with self.assertRaises(ValueError): self.helper.inject('a\tb')
        self.assertEqual(peer.commits, ['a']); self.assertEqual(peer.text, 'right')
        self.assertEqual(peer.keys, [('Tab', 1), ('Tab', 0)])

    def test_input_method_event_flood_respects_job_budget_without_legacy_fallback(self):
        peer = self.start(fault='flood')
        with self.assertRaises(ValueError): self.helper.inject('tail', backspaces=1)
        self.assertEqual(peer.keys, []); self.assertEqual(peer.commits, []); self.assertTrue(peer.closed.wait(.5))


if __name__ == '__main__': unittest.main()
