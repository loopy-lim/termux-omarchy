"""Balanced editing chords using the same US evdev map as the physical keyboard.

GTK bindings re-query hardware keycodes. A one-symbol text keyboard is therefore
unsuitable for accelerators even when its GDK event carries the expected keysym.
Keep this keyboard separate from Unicode/IME input and never replay a failed job.
"""
import atexit
import math
import os
import struct
import time
import loopy_input as input_wire

LETTERS = dict(zip('abcdefghijklmnopqrstuvwxyz',
    (30, 48, 46, 32, 18, 33, 34, 35, 23, 36, 37, 38, 50, 49, 24, 25, 16, 19, 31, 20, 22, 47, 17, 45, 21, 44)))
CODES = dict(LETTERS, Home=102, End=107, Left=105, Right=106, BackSpace=14,
             plus=13, minus=12, **{'0': 11})
MODIFIERS = {'shift': 1, 'ctrl': 4}
KEYMAP = (b'xkb_keymap { xkb_keycodes { include "evdev+aliases(qwerty)" }; '
          b'xkb_types { include "complete" }; xkb_compatibility { include "complete" }; '
          b'xkb_symbols { include "pc+us+inet(evdev)" }; };\n\0')
_SESSION = None


def close():
    global _SESSION
    session, _SESSION = _SESSION, None
    if session is None: return
    wire = session[2]
    wire.deadline = time.monotonic() + .25
    try:
        if wire.keyboard:
            wire.send(input_wire._frame(wire.keyboard, 2, struct.pack('=IIII', 0, 0, 0, 0)))
        wire.finish()
    except (OSError, ValueError, struct.error):
        pass
    finally:
        wire.sock.close()  # wlroots releases modifiers and keys on disconnect.


def inject(sequence, timeout=3):
    """Validate the complete bounded sequence before changing any guest input."""
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 3:
        raise ValueError('Invalid chord deadline')
    if type(sequence) not in (list, tuple) or not 1 <= len(sequence) <= 4:
        raise ValueError('Invalid chord sequence')
    prepared = []
    for item in sequence:
        if type(item) not in (tuple, list) or len(item) != 2:
            raise ValueError('Invalid chord')
        key, modifiers = item
        if type(key) is not str or key not in CODES or type(modifiers) not in (tuple, list) \
                or len(modifiers) > 2 or any(type(mod) is not str or mod not in MODIFIERS for mod in modifiers):
            raise ValueError('Unsupported editing chord')
        mask = 1 if key == 'plus' else 0
        for modifier in modifiers: mask |= MODIFIERS[modifier]
        prepared.append((CODES[key], mask))
    path, token = input_wire._socket_path(), os.environ['LOOPY_SESSION']
    global _SESSION
    if _SESSION is not None and _SESSION[:2] != (path, token): close()
    deadline = time.monotonic() + timeout
    try:
        if _SESSION is None:
            wire = input_wire._Wire(path, deadline)
            _SESSION = (path, token, wire)
            wire.initialize()
            wire.input(KEYMAP, [])
        else:
            wire = _SESSION[2]
            wire.deadline = deadline
            wire.received = wire.events = 0
        for code, mask in prepared:
            wire.send(input_wire._frame(wire.keyboard, 2, struct.pack('=IIII', mask, 0, 0, 0)))
            wire.input(None, [code])
            wire.send(input_wire._frame(wire.keyboard, 2, struct.pack('=IIII', 0, 0, 0, 0)))
            wire.sync()
    except BaseException:
        close()
        raise


atexit.register(close)
