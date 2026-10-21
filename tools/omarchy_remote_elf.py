"""Check ARM64 DT_NEEDED against the signed extension and fixed complete image."""
import struct


def needed(data):
    if not data.startswith(b'\x7fELF'):
        return None
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError('Remote client requires original ARM64 ELF64 inputs')
    offset = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    if size != 56 or not 0 < count < 256 or offset + size * count > len(data):
        raise ValueError('Invalid remote ELF program table')
    segments, dynamic = [], None
    for i in range(count):
        kind, _, start, address, _, length, _, _ = struct.unpack_from('<IIQQQQQQ', data, offset + i * size)
        if start + length > len(data): raise ValueError('Remote ELF segment exceeds its input')
        if kind == 1: segments.append((address, address + length, start))
        if kind == 2: dynamic = start, length
    if dynamic is None: return []
    required, strings = [], None
    for i in range(dynamic[0], sum(dynamic), 16):
        tag, value = struct.unpack_from('<QQ', data, i)
        if tag == 0: break
        if tag == 1: required.append(value)
        if tag == 5: strings = value
    if strings is None: raise ValueError('Remote ELF has no string table')
    for begin, end, start in segments:
        if begin <= strings < end:
            table = start + strings - begin
            break
    else: raise ValueError('Remote ELF string table is not file backed')
    names = []
    for relative in required:
        start = table + relative
        end = data.find(b'\0', start, start + 256)
        if start >= len(data) or end == -1: raise ValueError('Invalid remote ELF dependency string')
        name = data[start:end].decode('ascii')
        if '/' in name or not name: raise ValueError('Invalid remote native dependency name')
        names.append(name)
    return names


def resolve_library(name, extension, base):
    current = 'usr/lib/' + name
    seen = set()
    for _ in range(16):
        if current in seen: break
        seen.add(current)
        entry = extension.get(current, base.get(current))
        if entry is None: break
        if entry['kind'] == 'file': return current
        if entry['kind'] != 'symlink': break
        current = entry['target']
    raise ValueError('Remote client native dependency is unavailable: ' + name)
