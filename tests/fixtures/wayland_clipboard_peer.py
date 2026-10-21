"""Owned Unix peer for wlr-data-control v1 wire/FD contract tests."""
import array
from pathlib import Path
import socket
import struct
import threading

U = struct.Struct('=I')


def string(value):
    data = value.encode() + b'\0'
    return U.pack(len(data)) + data + bytes(-len(data) % 4)


def frame(obj, opcode, body=b''):
    return struct.pack('=II', obj, (len(body) + 8) << 16 | opcode) + body


class Peer:
    def __init__(self, path):
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(path)); self.server.listen(1); self.server.settimeout(4)
        self.connection = None; self.lock = threading.Lock(); self.closed = False
        self.error = None; self.device = None; self.next_offer = 0xff000000
        self.offers, self.imports, self.pending = {}, [], []
        self.completed_offers = set()
        self.destroyed_offers = set()
        self.requested = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True); self.thread.start()

    def send(self, obj, opcode, body=b'', fd=None):
        with self.lock:
            data = frame(obj, opcode, body)
            if fd is None: self.connection.sendall(data)
            else: self.connection.sendmsg([data], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))])

    def offer(self, data, mime='text/plain;charset=utf-8', primary=False):
        obj = self.next_offer; self.next_offer += 1
        self.offers[obj] = data
        self.send(self.device, 0, U.pack(obj))
        for name in ([mime] if isinstance(mime, str) else mime): self.send(obj, 0, string(name))
        self.send(self.device, 3 if primary else 1, U.pack(obj))
        return obj

    def run(self):
        import os
        buffer, fds, kinds = bytearray(), [], {1: 'display'}
        try:
            self.connection = self.server.accept()[0]; self.connection.settimeout(4)
            while not self.closed:
                data, ancillary, flags, _ = self.connection.recvmsg(16384, socket.CMSG_SPACE(64))
                if not data: return
                for _, _, values in ancillary:
                    group = array.array('i'); group.frombytes(values[:len(values) // group.itemsize * group.itemsize]); fds.extend(group)
                buffer.extend(data)
                while len(buffer) >= 8:
                    obj, word = struct.unpack_from('=II', buffer); size, op = word >> 16, word & 65535
                    if len(buffer) < size: break
                    body = bytes(buffer[8:size]); del buffer[:size]
                    kind = kinds.get(obj)
                    if obj == 1 and op == 1:
                        registry = U.unpack(body)[0]; kinds[registry] = 'registry'
                        self.send(registry, 0, U.pack(10) + string('wl_seat') + U.pack(1))
                        self.send(registry, 0, U.pack(11) + string('zwlr_data_control_manager_v1') + U.pack(2))
                    elif obj == 1 and op == 0:
                        callback = U.unpack(body)[0]; self.send(callback, 0, U.pack(0)); self.send(1, 1, U.pack(callback))
                    elif kind == 'registry':
                        name = U.unpack_from(body)[0]; child = U.unpack_from(body, len(body) - 4)[0]
                        kinds[child] = 'seat' if name == 10 else 'manager'
                        if name == 10: self.send(child, 0, U.pack(3))
                    elif kind == 'manager' and op == 1:
                        self.device = U.unpack_from(body)[0]; kinds[self.device] = 'device'
                        self.send(self.device, 1, U.pack(0))
                        # Pinned Hyprland sends both initial selections, even
                        # when this client binds data control version 1.
                        self.send(self.device, 3, U.pack(0))
                    elif kind == 'manager' and op == 0:
                        kinds[U.unpack(body)[0]] = 'source'
                    elif kind == 'device' and op == 0:
                        source = U.unpack(body)[0]
                        if source:
                            read, write = os.pipe(); self.pending.append(read)
                            self.send(source, 0, string('text/plain;charset=utf-8'), write); os.close(write)
                            self.requested.set()
                        else: self.imports.append(b'')
                    elif kind == 'source' and op == 1:
                        self.send(1, 1, U.pack(obj))
                    elif obj in self.offers and op == 0:
                        fd = fds.pop(0)
                        try:
                            value = self.offers[obj]
                            while value:
                                count = os.write(fd, value); value = value[count:]
                        except BrokenPipeError:
                            pass
                        finally: os.close(fd); self.completed_offers.add(obj)
                    elif obj in self.offers and op == 1:
                        del self.offers[obj]
                        self.destroyed_offers.add(obj)
        except (OSError, ValueError, IndexError) as error:
            if not self.closed: self.error = error
        finally:
            for fd in fds: os.close(fd)

    def close(self):
        import os
        self.closed = True
        if self.connection is not None:
            try: self.connection.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            self.connection.close()
        self.server.close(); self.thread.join(4)
        for fd in self.pending:
            try: os.close(fd)
            except OSError: pass
