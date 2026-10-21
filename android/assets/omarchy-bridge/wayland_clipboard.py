"""Bounded wlr-data-control client on the current compositor connection.

Implements the pinned Hyprland protocols/wlr-data-control-unstable-v1.xml.
All transfers use real SCM_RIGHTS descriptors and nonblocking pipes. The
existing session worker selects these descriptors; there are no child tools.
"""
import array
import collections
import heapq
import os
import select
import socket
import struct
import time

UINT = struct.Struct('=I')
LIMIT, MAX_OBJECTS, MAX_TRANSFERS = 65536, 256, 8
TEXT = ('text/plain;charset=utf-8', 'UTF8_STRING', 'text/plain')


class ProtocolError(OSError):
    pass


def string(value):
    data = value.encode('ascii') + b'\0'
    return UINT.pack(len(data)) + data + bytes(-len(data) % 4)


def parse_string(body, offset=0):
    if len(body) < offset + 4: raise ProtocolError('Missing clipboard protocol string')
    size = UINT.unpack_from(body, offset)[0]; end = offset + 4 + ((size + 3) & ~3)
    if not 1 <= size <= 256 or end > len(body) or body[offset + 3 + size] != 0:
        raise ProtocolError('Invalid clipboard protocol string')
    return body[offset + 4:offset + 3 + size].decode('ascii'), end


class Client:
    def __init__(self, path, export):
        self.export = export
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(2)
        self.buffer, self.fds = bytearray(), collections.deque()
        self.objects, self.pending_delete, self.free = {1: 'display'}, set(), []
        self.next_id, self.registry, self.device, self.manager = 2, None, None, None
        self.globals, self.offers, self.sources = {}, {}, {}
        self.selection, self.incoming, self.outgoing = None, None, {}
        try:
            self.sock.connect(str(path))
            if hasattr(socket, 'SO_PEERCRED'):
                _, uid, _ = struct.unpack('=iii', self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if uid != os.getuid(): raise ProtocolError('Clipboard compositor UID differs')
            self.registry = self.new('registry'); self.send(1, 1, UINT.pack(self.registry)); self.sync()
            seat = self.bind('wl_seat', 'seat')
            self.manager = self.bind('zwlr_data_control_manager_v1', 'manager', 2)
            self.device = self.new('device'); self.send(self.manager, 1, struct.pack('=II', self.device, seat)); self.sync()
        except BaseException:
            self.close(); raise

    def new(self, kind):
        if len(self.objects) >= MAX_OBJECTS: raise ProtocolError('Clipboard object bound exceeded')
        value = heapq.heappop(self.free) if self.free else self.next_id
        if value == self.next_id: self.next_id += 1
        if value >= 0xff000000: raise ProtocolError('Clipboard client ID exhausted')
        self.objects[value] = kind
        return value

    def send(self, obj, opcode, body=b'', fd=None):
        data = struct.pack('=II', obj, ((len(body) + 8) << 16) | opcode) + body
        while data:
            if fd is None: count = self.sock.send(data)
            else:
                count = self.sock.sendmsg([data], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))])
                if count: fd = None
            if not count: raise OSError('Clipboard compositor disconnected')
            data = data[count:]

    def sync(self):
        callback = self.new('callback'); self.send(1, 0, UINT.pack(callback))
        deadline = time.monotonic() + 5
        while callback in self.objects and callback not in self.pending_delete:
            self.pump()
            if time.monotonic() >= deadline: raise TimeoutError('Clipboard initialization timed out')
            select.select(self.readers, self.writers, [], .01)

    def bind(self, interface, kind, maximum_version=1):
        if interface not in self.globals: raise ProtocolError('Wayland clipboard capability unavailable')
        obj = self.new(kind)
        name, version = self.globals[interface]
        self.send(self.registry, 0, UINT.pack(name) + string(interface) + struct.pack('=II', min(version, maximum_version), obj))
        return obj

    @property
    def readers(self):
        return [self.sock] + ([self.incoming[0]] if self.incoming is not None else [])

    @property
    def writers(self):
        return list(self.outgoing)

    def set_selection(self, data):
        if len(data) > LIMIT or b'\0' in data: raise ProtocolError('Unsupported clipboard bytes')
        data.decode('utf-8')
        if len(self.sources) >= MAX_TRANSFERS: return False
        source = 0
        if data:
            source = self.new('source'); self.sources[source] = bytes(data)
            self.send(self.manager, 0, UINT.pack(source))
            for mime in TEXT: self.send(source, 0, string(mime))
        self.send(self.device, 0, UINT.pack(source))
        return True

    def pump(self):
        # Read only ready data. A bounded batch yields back to keyboard jobs.
        if select.select([self.sock], [], [], 0)[0]:
            data, ancillary, flags, _ = self.sock.recvmsg(16384, socket.CMSG_SPACE(64))
            for level, kind, values in ancillary:
                if (level, kind) != (socket.SOL_SOCKET, socket.SCM_RIGHTS):
                    raise ProtocolError('Unexpected clipboard ancillary data')
                descriptors = array.array('i')
                descriptors.frombytes(values[:len(values) // descriptors.itemsize * descriptors.itemsize])
                self.fds.extend(descriptors)
                for fd in descriptors: os.set_inheritable(fd, False)
            if flags & socket.MSG_CTRUNC or len(self.fds) > MAX_TRANSFERS:
                raise ProtocolError('Clipboard descriptor bound exceeded')
            if not data: raise OSError('Clipboard compositor disconnected')
            self.buffer.extend(data)
            if len(self.buffer) > 262144: raise ProtocolError('Clipboard event budget exceeded')
        for _ in range(256):
            if len(self.buffer) < 8: break
            obj, word = struct.unpack_from('=II', self.buffer); size, opcode = word >> 16, word & 65535
            if not 8 <= size <= 16384 or size % 4: raise ProtocolError('Malformed clipboard event')
            if len(self.buffer) < size: break
            body = bytes(self.buffer[8:size]); del self.buffer[:size]
            self.event(obj, opcode, body)
        self.transfer()

    def event(self, obj, opcode, body):
        kind = self.objects.get(obj)
        if obj == 1 and opcode == 0: raise ProtocolError('Compositor rejected clipboard protocol')
        if obj == 1 and opcode == 1 and len(body) == 4:
            removed = UINT.unpack(body)[0]
            if removed not in self.pending_delete: raise ProtocolError('Unexpected clipboard object deletion')
            self.pending_delete.remove(removed); self.objects.pop(removed); heapq.heappush(self.free, removed)
        elif kind == 'callback' and opcode == 0 and len(body) == 4:
            self.pending_delete.add(obj)
        elif kind == 'registry' and opcode == 0:
            interface, end = parse_string(body, 4)
            if end + 4 != len(body): raise ProtocolError('Invalid clipboard registry global')
            name, version = UINT.unpack_from(body)[0], UINT.unpack_from(body, end)[0]
            if interface in ('wl_seat', 'zwlr_data_control_manager_v1') and version:
                self.globals.setdefault(interface, (name, version))
        elif kind == 'registry' and opcode == 1 and len(body) == 4:
            if UINT.unpack(body)[0] in (item[0] for item in self.globals.values()): raise OSError('Clipboard seat disappeared')
        elif kind == 'seat' and opcode == 0 and len(body) == 4: pass
        elif kind == 'device' and opcode == 0 and len(body) == 4:
            offer = UINT.unpack(body)[0]
            if offer < 0xff000000 or offer in self.objects or len(self.objects) >= MAX_OBJECTS:
                raise ProtocolError('Invalid clipboard offer ID')
            self.objects[offer] = 'offer'; self.offers[offer] = set()
        elif kind == 'offer' and opcode == 0:
            mime, end = parse_string(body)
            if end != len(body) or len(self.offers[obj]) >= 64: raise ProtocolError('Clipboard MIME bound exceeded')
            self.offers[obj].add(mime)
        elif kind == 'device' and opcode == 1 and len(body) == 4:
            self.select_offer(UINT.unpack(body)[0])
        elif kind == 'device' and opcode == 3 and len(body) == 4:
            # Mouse selection is independent from explicit copy. Hyprland also
            # sends this since-v2 event to v1 bindings; release its offers without
            # reading/exporting them or clearing the Android clipboard.
            offer = UINT.unpack(body)[0]
            if offer:
                if offer not in self.offers or offer == self.selection:
                    raise ProtocolError('Invalid primary selection offer')
                self.send(offer, 1); self.objects.pop(offer); self.offers.pop(offer)
        elif kind == 'device' and opcode == 2: raise OSError('Clipboard data control finished')
        elif kind == 'source' and opcode == 0:
            mime, end = parse_string(body)
            if end != len(body) or not self.fds: raise ProtocolError('Clipboard source send descriptor missing')
            fd = self.fds.popleft()
            if mime not in TEXT or len(self.outgoing) >= MAX_TRANSFERS:
                os.close(fd); return
            os.set_blocking(fd, False)
            self.outgoing[fd] = (self.sources[obj], time.monotonic() + 3)
        elif kind == 'source' and opcode == 1 and not body:
            self.send(obj, 1); self.pending_delete.add(obj); self.sources.pop(obj)
        else: raise ProtocolError('Unexpected clipboard event')

    def select_offer(self, offer):
        if offer and offer not in self.offers: raise ProtocolError('Unknown clipboard selection')
        if self.incoming is not None:
            os.close(self.incoming[0]); self.incoming = None
        if self.selection:
            self.send(self.selection, 1); self.objects.pop(self.selection); self.offers.pop(self.selection)
        self.selection = offer
        if not offer:
            self.export('nil', b''); return
        mimes = self.offers[offer]
        if 'x-kde-passwordManagerHint' in mimes:
            return  # wl-clipboard also treats this offer as sensitive.
        mime = next((name for name in TEXT if name in mimes), None)
        if mime is None: return
        read, write = os.pipe(); os.set_blocking(read, False)
        try:
            self.send(offer, 0, string(mime), write)
            self.incoming = (read, bytearray(), time.monotonic() + 3)
        except BaseException:
            os.close(read); raise
        finally: os.close(write)

    def transfer(self):
        now = time.monotonic()
        for fd, (data, deadline) in list(self.outgoing.items()):
            try:
                if now >= deadline: raise BrokenPipeError()
                count = os.write(fd, data)
                if count < len(data): self.outgoing[fd] = (data[count:], deadline); continue
            except BlockingIOError: continue
            except BrokenPipeError: pass
            os.close(fd); del self.outgoing[fd]
        if self.incoming is None: return
        fd, data, deadline = self.incoming
        try:
            if now >= deadline:
                os.close(fd); self.incoming = None; return
            chunk = os.read(fd, min(4096, LIMIT + 1 - len(data)))
            data.extend(chunk)
            if len(data) > LIMIT:
                os.close(fd); self.incoming = None; return
            if chunk: return
            os.close(fd); self.incoming = None
            if b'\0' in data: return
            try: data.decode('utf-8')
            except UnicodeDecodeError: return
            self.export('data', bytes(data))
        except BlockingIOError: pass
        except BaseException:
            if self.incoming is not None: os.close(fd); self.incoming = None
            raise

    def close(self):
        for fd in list(self.outgoing) + list(self.fds) + ([self.incoming[0]] if self.incoming else []):
            os.close(fd)
        self.outgoing.clear(); self.fds.clear(); self.incoming = None
        self.sock.close()
