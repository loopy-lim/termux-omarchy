"""Bounded synthetic pointer for an owned native Wayland recovery fixture only."""
import os
from pathlib import Path
import socket
import stat
import struct
import time

UINT = struct.Struct('=I')


def click(path, x, y, width, height):
    path = Path(path)
    assert path.parent.parent == Path('/tmp') and path.parent.name.startswith('lhw-')
    info = path.lstat()
    assert stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid() == 501
    assert 0 <= x < width <= 1920 and 0 <= y < height <= 1200
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(2); sock.connect(str(path))
        _, uid, _ = struct.unpack('=iii', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        assert uid == os.getuid()
        buffer = bytearray(); globals = {}; callback = 2

        def send(obj, opcode, data=b''):
            sock.sendall(struct.pack('=II', obj, ((len(data) + 8) << 16) | opcode) + data)

        def sync():
            nonlocal callback
            callback += 1; send(1, 0, UINT.pack(callback))
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                while len(buffer) >= 8:
                    obj, word = struct.unpack_from('=II', buffer); size, opcode = word >> 16, word & 65535
                    assert 8 <= size <= 65536 and size % 4 == 0
                    if len(buffer) < size: break
                    body = bytes(buffer[8:size]); del buffer[:size]
                    assert (obj, opcode) != (1, 0), 'original compositor rejected virtual pointer protocol: ' + repr(body)
                    if obj == callback and opcode == 0: return
                    if (obj, opcode) == (2, 0):
                        name, length = struct.unpack_from('=II', body)
                        assert 1 <= length <= 256 and body[8 + length - 1] == 0
                        interface = body[8:8 + length - 1].decode('ascii')
                        version = UINT.unpack_from(body, 8 + ((length + 3) & ~3))[0]
                        globals[interface] = (name, version)
                chunk = sock.recv(16384)
                assert chunk and len(buffer) + len(chunk) <= 262144
                buffer.extend(chunk)
            raise TimeoutError('owned virtual pointer sync')

        send(1, 1, UINT.pack(2)); sync()
        interface = 'zwlr_virtual_pointer_manager_v1'
        name, version = globals[interface]; assert version >= 1
        value = interface.encode() + b'\0'
        encoded = UINT.pack(len(value)) + value + bytes(-len(value) % 4)
        send(2, 0, UINT.pack(name) + encoded + struct.pack('=II', 1, 4))
        send(4, 0, struct.pack('=II', 0, 5)); callback = 5; sync()
        now = int(time.monotonic() * 1000) & 0xffffffff
        send(5, 1, struct.pack('=IIIII', now, x, y, width, height)); send(5, 4); sync()
        send(5, 2, struct.pack('=III', now, 0x110, 1)); send(5, 4)
        send(5, 2, struct.pack('=III', now, 0x110, 0)); send(5, 4); sync()
