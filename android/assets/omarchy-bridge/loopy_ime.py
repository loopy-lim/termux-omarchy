"""IMv2 state/UTF-8 codec; no keyboard grab, clipboard access, or replay.

Pinned protocol: wlroots0.18.2 input-method-unstable-v2.xml. done serials
count modulo UINT32 across activations; stale commits have no error/ACK.
"""
import struct

UINT = struct.Struct('=I')
MAX_TEXT = 4000


def string(text):
    data = text.encode('utf-8')
    if b'\0' in data or len(data) > MAX_TEXT:
        raise ValueError('Invalid bounded input-method string')
    data += b'\0'
    return UINT.pack(len(data)) + data + bytes((-len(data)) % 4)


def read_string(body):
    if len(body) < 4: raise ValueError('Invalid input-method string frame')
    length = UINT.unpack_from(body)[0]; end = 4 + ((length + 3) & ~3)
    if not 1 <= length <= MAX_TEXT + 1 or end > len(body):
        raise ValueError('Input-method string exceeds its bound')
    raw = body[4:4 + length]
    if raw[-1:] != b'\0' or b'\0' in raw[:-1]:
        raise ValueError('Invalid input-method string termination')
    try: raw[:-1].decode('utf-8')
    except UnicodeError: raise ValueError('Invalid input-method UTF-8') from None
    return raw[:-1], end


def operations(text, controls):
    """Precompute scalar-safe strings and explicit legacy control keys."""
    result, chars, size = [], [], 0
    for char in text:
        if char in controls:
            if chars: result.append(('text', ''.join(chars))); chars, size = [], 0
            result.append(('key', controls[char])); continue
        length = len(char.encode('utf-8'))
        if size + length > MAX_TEXT:
            result.append(('text', ''.join(chars))); chars, size = [], 0
        chars.append(char); size += length
    if chars: result.append(('text', ''.join(chars)))
    # Validate every string before the first deletion or input request.
    for kind, value in result:
        if kind == 'text': string(value)
    return result


class State:
    def __init__(self):
        self.active = self.pending_active = False
        self.transition, self.epoch, self.serial, self.seen_done = False, 0, 0, False
        self.surrounding = self.pending_surrounding = None
        self.purpose = self.pending_purpose = 0
        self.expected = None

    @property
    def ready(self): return self.active and not self.transition and self.seen_done

    def event(self, opcode, body):
        if opcode in (0, 1):
            if body: raise ValueError('Invalid input-method activation event')
            self.epoch += 1; self.transition = True; self.pending_active = opcode == 0
            self.pending_surrounding = None; self.pending_purpose = 0
            self.expected = None
        elif opcode == 2:
            raw, end = read_string(body)
            if end + 8 != len(body): raise ValueError('Invalid input-method surrounding event')
            cursor, anchor = struct.unpack_from('=II', body, end)
            if cursor > len(raw) or anchor > len(raw): raise ValueError('Invalid surrounding cursor')
            try: raw[:cursor].decode(); raw[:anchor].decode()
            except UnicodeError: raise ValueError('Surrounding cursor splits UTF-8') from None
            self.pending_surrounding = raw, cursor, anchor
        elif opcode == 3:
            if len(body) != 4 or UINT.unpack(body)[0] > 1: raise ValueError('Invalid input-method change cause')
        elif opcode == 4:
            if len(body) != 8: raise ValueError('Invalid input-method content type')
            hint, purpose = struct.unpack('=II', body)
            if hint & ~1023 or purpose > 13: raise ValueError('Invalid input-method content type')
            self.pending_purpose = purpose
        elif opcode == 5:
            if body: raise ValueError('Invalid input-method done event')
            self.serial = (self.serial + 1) & 0xffffffff
            self.seen_done = True
            self.active, self.surrounding, self.purpose = self.pending_active, self.pending_surrounding, self.pending_purpose
            self.transition = False; self.pending_surrounding = None
        elif opcode == 6:
            raise ValueError('Input method is unavailable')
        else: raise ValueError('Unexpected input-method event')

    def expect_done(self):
        # GTK may report cached old surrounding before WebKit's asynchronous
        # application edit. Foot has no surrounding and need not emit a new done.
        self.expected = (self.serial, self.epoch) if self.surrounding is not None else None

    def settled(self):
        """Fresh client state/focus barrier only, never application delivery ACK."""
        if self.expected is None: return True
        serial, epoch = self.expected
        if self.epoch != epoch or not self.ready: raise ValueError('Input focus changed during commit')
        if self.serial == serial: return False
        self.expected = None; return True
