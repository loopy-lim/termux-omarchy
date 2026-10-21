#!/usr/bin/python3
"""Bounded IMv2 text and virtual-keyboard-v1 key pairs; no replay fallback.

Wire contract: atx/wtype v0.4 protocol/virtual-keyboard-unstable-v1.xml and
wayland.freedesktop.org/docs/book/Protocol.html. Sync confirms compositor
processing, not application/DOM delivery; callers still need their own witness.
"""
import array
import atexit
import heapq
import math
import os
from pathlib import Path
import re
import socket
import stat
import struct
import tempfile
import time
import loopy_ime
import loopy_input_trace

IPC_ROOT = Path('/run/loopy')
# Linux UAPI input-event-codes.h: clients derive KeyboardEvent.code from evdev,
# independently of this virtual keyboard's keysym (KEY_CLEAR = 0x163).
RESERVED = {'Return': 28, 'BackSpace': 14, 'Delete': 111, 'Tab': 15, 'Escape': 1,
            'Up': 103, 'Down': 108, 'Left': 105, 'Right': 106, 'Home': 102,
            'End': 107, 'Prior': 104, 'Next': 109, 'Clear': 355}
KEYS = frozenset(RESERVED) - {'Clear'}
CONTROLS = {'\b': 'BackSpace', '\t': 'Tab', '\n': 'Return', '\v': 'Clear',
            '\r': 'Return', '\x1b': 'Escape', '\x7f': 'Delete'}
MAX_UNIQUE, MAX_KEYMAP = 4073, 4 * 1024 * 1024
# libxkbcommon 1.8.1 caps XKB codes at 4095: 14 reserved + 4073 symbols + 8.
MAX_FRAME, MAX_RECEIVED, MAX_EVENTS = 16384, 1048576, 4096
ACTIVATE_TIMEOUT = 2
HEADER, UINT = struct.Struct('=II'), struct.Struct('=I')


def _string(value):
    data = value.encode('ascii') + b'\0'
    return UINT.pack(len(data)) + data + bytes((-len(data)) % 4)


def _frame(obj, opcode, body=b''):
    return HEADER.pack(obj, ((8 + len(body)) << 16) | opcode) + body


def _symbols(text, backspaces, key):
    if type(text) is not str or '\0' in text or len(text.encode('utf-8')) > 4096:
        raise ValueError('Invalid bounded Unicode input')
    if type(backspaces) is not int or not 0 <= backspaces <= 64:
        raise ValueError('Invalid deletion count')
    if key is not None and (type(key) is not str or key not in KEYS):
        raise ValueError('Unsupported semantic input key')
    result = ['BackSpace'] * backspaces
    for char in text:
        cp = ord(char)
        # libxkbcommon 1.8.1 rejects C0/C1 Uxxxx names. Numeric Unicode keysyms
        # compile and round-trip these scalars without silently becoming NoSymbol.
        literal = '0x%08X' % (0x01000000 | cp) if cp < 0x20 or 0x7f <= cp < 0xa0 else 'U' + format(cp, '04X')
        result.append(CONTROLS.get(char, literal))
    if key is not None: result.append(key)
    return result


def _keymap(mapping):
    if len(mapping) > MAX_UNIQUE + len(RESERVED) or any(
            type(code) is not int or not 1 <= code <= MAX_UNIQUE + len(RESERVED) for code in mapping.values()) \
            or len(set(mapping.values())) != len(mapping):
        raise ValueError('Input symbol count exceeds its bound')
    lines = ['xkb_keymap {', 'xkb_keycodes "loopy" { minimum=8; maximum=4095;']
    lines += ['<K%03d> = %d;' % (code, code + 8) for code in mapping.values()]
    lines += ['};', 'xkb_types "loopy" { type "ONE_LEVEL" { modifiers=None; map[None]=Level1; }; };',
              'xkb_compatibility "loopy" {};', 'xkb_symbols "loopy" {']
    lines += ['key <K%03d> { type="ONE_LEVEL", symbols[Group1]=[%s] };' % (code, symbol)
              for symbol, code in mapping.items()]
    data = ('\n'.join(lines + ['};', '};']) + '\n\0').encode('ascii')
    if len(data) > MAX_KEYMAP: raise ValueError('Input keymap exceeds its bound')
    return data


def _socket_path():
    token, display = os.environ.get('LOOPY_SESSION', ''), os.environ.get('WAYLAND_DISPLAY', '')
    if not re.fullmatch(r'[A-Za-z0-9-]{1,64}', token) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', display) \
            or display in ('.', '..') or Path(os.environ.get('XDG_RUNTIME_DIR', '')) != IPC_ROOT:
        raise ValueError('Input must use the current session display')
    marker = IPC_ROOT / ('display-' + token)
    fd = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Invalid session display record')
        data = source.read(66)
    if len(data) > 65 or data != (display + '\n').encode('ascii'):
        raise ValueError('Input display does not match the session')
    path = IPC_ROOT / display
    info = path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError('Input display is not an owned socket')
    return path


class _Wire:
    def __init__(self, path, deadline):
        self.deadline, self.next_id = deadline, 2
        self.live, self.available, self.completed, self.destroy_pending = {1: 'display'}, [], set(), set()
        self.map_version = 0
        self.registry = self.seat = self.manager = self.keyboard = 0
        self.im_manager = self.im = 0
        self.ime, self.guard_epoch = None, None
        self.trace = None
        self.globals, self.global_names = {}, set()
        self.buffer, self.received, self.events = bytearray(), 0, 0
        self.possible_pressed = set()
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self._timeout(); self.sock.connect(str(path))
            if hasattr(socket, 'SO_PEERCRED'):
                _, uid, _ = struct.unpack('=iii', self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if uid != os.getuid(): raise ValueError('Input peer UID differs from the session')
        except BaseException:
            self.sock.close(); raise

    def _timeout(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0: raise TimeoutError('Wayland input deadline exceeded')
        self.sock.settimeout(remaining)

    def _id(self, kind):
        if self.available: value = heapq.heappop(self.available)
        else:
            if self.next_id > 8192: raise ValueError('Input object count exceeds its bound')
            value = self.next_id; self.next_id += 1
        self.live[value] = kind
        return value

    def send(self, data, fd=None):
        offset = 0
        while offset < len(data):
            self._timeout()
            if fd is not None:
                sent = self.sock.sendmsg([data[offset:]], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))])
                if sent > 0: fd = None  # SCM_RIGHTS must accompany only the first successful write.
            else: sent = self.sock.send(data[offset:])
            if sent <= 0: raise OSError('Input connection ended while sending')
            offset += sent

    def _event(self):
        while True:
            if len(self.buffer) >= 8:
                obj, word = HEADER.unpack_from(self.buffer)
                size, opcode = word >> 16, word & 65535
                if not 8 <= size <= MAX_FRAME or size % 4:
                    raise ValueError('Invalid Wayland input event frame')
                if len(self.buffer) >= size:
                    body = bytes(self.buffer[8:size]); del self.buffer[:size]
                    self.events += 1
                    if self.events > MAX_EVENTS: raise ValueError('Input event count exceeds its bound')
                    return obj, opcode, body
            self._timeout()
            data, ancillary, flags, _ = self.sock.recvmsg(4096, socket.CMSG_SPACE(16))
            for level, kind, value in ancillary:
                if (level, kind) == (socket.SOL_SOCKET, socket.SCM_RIGHTS):
                    descriptors = array.array('i'); descriptors.frombytes(value[:len(value) // descriptors.itemsize * descriptors.itemsize])
                    for fd in descriptors: os.close(fd)
            if ancillary or flags & socket.MSG_CTRUNC: raise ValueError('Unexpected input event descriptor')
            if not data: raise OSError('Wayland input connection ended')
            self.received += len(data)
            if self.received > MAX_RECEIVED: raise ValueError('Input receive budget exceeded')
            self.buffer.extend(data)

    def _global(self, body):
        if len(body) < 16: raise ValueError('Invalid input registry event')
        name, length = struct.unpack_from('=II', body)
        end = 8 + ((length + 3) & ~3)
        if not 1 <= length <= 128 or end + 4 != len(body) or body[8 + length - 1] != 0:
            raise ValueError('Invalid input registry interface')
        interface = body[8:8 + length - 1].decode('ascii')
        version = UINT.unpack_from(body, end)[0]
        if not name or name in self.global_names or len(self.global_names) >= 256:
            raise ValueError('Input registry exceeds its bound')
        self.global_names.add(name)
        if interface in ('wl_seat', 'zwp_virtual_keyboard_manager_v1', 'zwp_input_method_manager_v2') and version:
            self.globals.setdefault(interface, name)

    def sync(self):
        callback = self._id('callback'); self.send(_frame(1, 0, UINT.pack(callback)))
        while True:
            obj, opcode, body = self._event()
            if obj not in self.live: raise ValueError('Input event uses an unknown object')
            if obj == callback and opcode == 0 and len(body) == 4 and obj not in self.completed:
                self.completed.add(obj); return
            self.dispatch(obj, opcode, body)

    def dispatch(self, obj, opcode, body):
        if obj not in self.live: raise ValueError('Input event uses an unknown object')
        if self.live[obj] == 'input-method':
            self.ime.event(opcode, body)
            if self.trace: self.trace.note('im-event', self.ime, opcode=opcode)
            return
        if obj == 1 and opcode == 0: raise ValueError('Compositor rejected virtual input')
        if obj == 1 and opcode == 1 and len(body) == 4:
            removed = UINT.unpack(body)[0]
            if removed not in self.completed and removed not in self.destroy_pending:
                raise ValueError('Invalid input object deletion')
            if removed not in self.live: raise ValueError('Invalid input object deletion')
            self.completed.discard(removed); self.destroy_pending.discard(removed)
            del self.live[removed]; heapq.heappush(self.available, removed)
        elif obj == self.registry and opcode == 0: self._global(body)
        elif obj == self.registry and opcode == 1 and len(body) == 4:
            if UINT.unpack(body)[0] in self.globals.values(): raise ValueError('Input registry capability disappeared')
        elif obj == self.seat and opcode == 0 and len(body) == 4: pass
        else: raise ValueError('Unexpected Wayland input event')

    def select_ime(self):
        interface = 'zwp_input_method_manager_v2'
        if interface not in self.globals:
            if self.trace: self.trace.selected('virtual', 'manager_missing', self.ime)
            return False
        if not self.im:
            self.im_manager = self._id('im-manager')
            self.send(_frame(self.registry, 0, UINT.pack(self.globals[interface]) + _string(interface) + struct.pack('=II', 1, self.im_manager)))
            self.im = self._id('input-method'); self.ime = loopy_ime.State()
            self.send(_frame(self.im_manager, 0, struct.pack('=II', self.seat, self.im)))
        self.sync()
        if self.ime.ready:
            if self.trace: self.trace.selected('atomic', 'active', self.ime)
            return True
        epoch, deadline = self.ime.epoch, self.deadline
        self.deadline = min(deadline, time.monotonic() + ACTIVATE_TIMEOUT)
        try:
            while not self.ime.ready: self.dispatch(*self._event())
            if self.trace: self.trace.selected('atomic', 'active', self.ime)
            return True
        except TimeoutError:
            if time.monotonic() >= deadline: raise
            if self.buffer or self.ime.epoch != epoch or self.ime.transition:
                raise ValueError('Input focus changed while selecting backend') from None
            if self.trace: self.trace.selected('virtual', 'inactive_timeout', self.ime)
            return False  # Clean initial no-active field: select VK before any input.
        finally: self.deadline = deadline

    def settle_ime(self, epoch):
        while True:
            if not self.ime.ready or self.ime.epoch != epoch:
                raise ValueError('Input focus changed during atomic input')
            if self.ime.settled(): return
            self.dispatch(*self._event())

    def atomic_input(self, operations, backspaces, mapping, data):
        epoch = self.ime.epoch
        self.guard_epoch = epoch
        self.settle_ime(epoch)
        self.input(data, [])  # All keymap validation precedes editing.
        self.sync(); self.settle_ime(epoch)
        # Client surrounding may lag application edits: never derive deletion
        # byte lengths from it. Native keys keep application selection semantics.
        self.input(None, [mapping['BackSpace']] * backspaces)
        for kind, value in operations:
            self.sync(); self.settle_ime(epoch)  # Drain queued client-state done before choosing request serial.
            if kind == 'key':
                self.input(None, [mapping[value]])
            else:
                self.ime.expect_done()
                if self.trace: self.trace.note('im-text', self.ime, bytes=len(value.encode()), request_serial=self.ime.serial)
                self.send(_frame(self.im, 0, loopy_ime.string(value)) + _frame(self.im, 3, UINT.pack(self.ime.serial)))
                self.sync(); self.settle_ime(epoch)

    def initialize(self):
        self.registry = self._id('registry'); self.send(_frame(1, 1, UINT.pack(self.registry))); self.sync()
        for interface, attr in (('wl_seat', 'seat'), ('zwp_virtual_keyboard_manager_v1', 'manager')):
            if interface not in self.globals: raise ValueError('Compositor lacks virtual input capability')
            value = self._id(attr); setattr(self, attr, value)
            self.send(_frame(self.registry, 0, UINT.pack(self.globals[interface]) + _string(interface) + struct.pack('=II', 1, value)))
        self.keyboard = self._id('keyboard')
        self.send(_frame(self.manager, 0, struct.pack('=II', self.seat, self.keyboard)))

    def input(self, data, codes):
        if data is not None:
            with tempfile.TemporaryFile(dir='/tmp') as file:
                file.write(data); file.flush()
                self.send(_frame(self.keyboard, 0, struct.pack('=II', 1, len(data))), file.fileno())
                self.send(_frame(self.keyboard, 2, struct.pack('=IIII', 0, 0, 0, 0)))
                self.sync()  # All previous keys were released before extending the map.
                self.check_focus()
        for start in range(0, len(codes), 32):
            batch = codes[start:start + 32]; self.possible_pressed = set(batch)
            stamp = int(time.monotonic() * 1000) & 0xffffffff
            events = b''.join(_frame(self.keyboard, 1, struct.pack('=III', stamp, code, state))
                              for code in batch for state in (1, 0))
            self.check_focus(); self.send(events); self.sync(); self.possible_pressed.clear(); self.check_focus()
            if self.trace: self.trace.note('vk-pairs', self.ime, pairs=len(batch))

    def check_focus(self):
        if self.guard_epoch is not None and self.ime.epoch != self.guard_epoch:
            raise ValueError('Input focus changed during virtual input')

    def finish(self):
        if not self.keyboard: return
        stamp = int(time.monotonic() * 1000) & 0xffffffff
        for code in self.possible_pressed:
            self.send(_frame(self.keyboard, 1, struct.pack('=III', stamp, code, 0)))
        self.possible_pressed.clear()
        self.send(_frame(self.keyboard, 3)); self.destroy_pending.add(self.keyboard); self.keyboard = 0
        if self.im:
            self.send(_frame(self.im, 6)); self.destroy_pending.add(self.im); self.im = 0
            self.send(_frame(self.im_manager, 1)); self.destroy_pending.add(self.im_manager); self.im_manager = 0
        self.sync()


class _Session:
    def __init__(self, path, token):
        self.path, self.token, self.wire = path, token, None
        self.mapping = dict(RESERVED)
        self.data, self.version = None, 0
        self.ledger = loopy_input_trace.Ledger(path.parent, token)

    def prepare(self, symbols):
        future = dict(self.mapping)
        occupied = set(future.values())
        free = (code for code in range(1, MAX_UNIQUE + len(RESERVED) + 1) if code not in occupied)
        for symbol in symbols:
            if symbol not in future:
                if len(future) - len(RESERVED) >= MAX_UNIQUE:
                    raise ValueError('Input session symbol capacity exceeded')
                future[symbol] = next(free)
        data = _keymap(future) if self.data is None or future != self.mapping else self.data
        if len(data) > MAX_KEYMAP: raise ValueError('Input keymap exceeds its bound')
        if self.data != data: self.version += 1
        self.mapping, self.data = future, data
        return [future[symbol] for symbol in symbols]

    def run(self, codes, deadline, trace=None):
        try:
            self.begin(deadline, trace)
            self.wire.input(self.data if self.wire.map_version != self.version else None, codes)
            self.wire.map_version = self.version
        except BaseException:
            self.abort(); raise

    def begin(self, deadline, trace=None):
        if self.wire is None:
            self.wire = _Wire(self.path, deadline); self.wire.trace = trace; self.wire.initialize()
        else:
            self.wire.trace = trace
            self.wire.deadline = deadline
            self.wire.received = self.wire.events = 0  # Per-job, never per-sync, budgets.

    def run_text(self, text, backspaces, key, symbols, deadline, trace=None):
        operations = loopy_ime.operations(text, CONTROLS)
        if key is not None: operations.append(('key', key))
        try:
            self.begin(deadline, trace); atomic = self.wire.select_ime()
            if atomic: self.wire.settle_ime(self.wire.ime.epoch)
        except BaseException:
            self.abort(); raise
        # Selected-backend future budgets are validated before editing;
        # a rejected job keeps the previous connection and assignments intact.
        codes = self.prepare([value for kind, value in operations if kind == 'key'] if atomic else symbols)
        try:
            if atomic:
                self.wire.atomic_input(operations, backspaces, self.mapping, self.data if self.wire.map_version != self.version else None)
            else:
                self.wire.guard_epoch = self.wire.ime.epoch if self.wire.ime else None
                self.wire.input(self.data if self.wire.map_version != self.version else None, codes)
            self.wire.map_version = self.version
        except BaseException:
            self.abort(); raise
        finally:
            if self.wire: self.wire.guard_epoch = None

    def abort(self):
        wire, self.wire = self.wire, None
        if wire is None: return
        if wire.trace: wire.trace.note('abort', wire.ime)
        try: wire.finish()
        except (OSError, ValueError, struct.error): pass
        finally: wire.sock.close()  # wlroots releases this keyboard's held keys on disconnect.


_SESSION = None


def close():
    global _SESSION
    session, _SESSION = _SESSION, None
    if session is not None:
        if session.wire is not None: session.wire.deadline = time.monotonic() + .25
        session.abort()


def inject_virtual(text='', backspaces=0, key=None, timeout=15):
    """Prevalidate the whole job, then complete balanced batches or report failure.

    Keycodes never change meaning during the session, including after failure.
    A failure can leave an application-visible prefix; never replay it.
    """
    deadline = time.monotonic() + timeout if type(timeout) in (int, float) else 0
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 15:
        raise ValueError('Invalid input deadline')
    symbols = _symbols(text, backspaces, key)  # Unicode encoding is checked before any deletion.
    if not symbols: return
    global _SESSION
    path, token = _socket_path(), os.environ['LOOPY_SESSION']
    if _SESSION is not None and (_SESSION.path != path or _SESSION.token != token): close()
    if _SESSION is None: _SESSION = _Session(path, token)
    codes = _SESSION.prepare(symbols)  # Future symbol/FD budgets before sends or deletions.
    try:
        with _SESSION.ledger.job(_SESSION, text, backspaces, key) as trace:
            trace.selected('virtual', 'semantic' if key is not None and not text and not backspaces else 'explicit', None)
            _SESSION.run(codes, deadline, trace)
    except (struct.error, UnicodeError):
        raise ValueError('Malformed Wayland input data') from None


def inject(text='', backspaces=0, key=None, timeout=15):
    """Select atomic IM for active editors, clean initial VK for legacy fields."""
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 15:
        raise ValueError('Invalid input deadline')
    deadline = time.monotonic() + timeout
    symbols = _symbols(text, backspaces, key)
    if not text and not backspaces:
        return inject_virtual(key=key, timeout=timeout) if key is not None else None
    global _SESSION
    path, token = _socket_path(), os.environ['LOOPY_SESSION']
    if _SESSION is not None and (_SESSION.path != path or _SESSION.token != token): close()
    if _SESSION is None: _SESSION = _Session(path, token)
    try:
        with _SESSION.ledger.job(_SESSION, text, backspaces, key) as trace:
            _SESSION.run_text(text, backspaces, key, symbols, deadline, trace)
    except (struct.error, UnicodeError): raise ValueError('Malformed Wayland input data') from None


atexit.register(close)
