"""Read the guest ARM glibc wrapper's loader contract without executing it."""
import struct

INTERPRETER = '/lib/ld-linux-aarch64.so.1'


def inspect(data):
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01' \
            or struct.unpack_from('<HH', data, 16) != (3, 183):
        raise ValueError('ARM64 ELF64 little-endian PIE watchdog required')
    phoff = struct.unpack_from('<Q', data, 32)[0]
    phsize, phcount = struct.unpack_from('<HH', data, 54)
    if phsize != 56 or not 0 < phcount < 256 or phoff + phsize * phcount > len(data):
        raise ValueError('Invalid watchdog program headers')
    loads, dynamic, interpreter = [], None, None
    relro, nx = False, False
    for i in range(phcount):
        kind, flags, start, address, _, length, _, _ = struct.unpack_from('<IIQQQQQQ', data, phoff + i * phsize)
        if start + length > len(data): raise ValueError('Watchdog segment exceeds input')
        if kind == 1: loads.append((address, length, start))
        if kind == 2:
            if dynamic is not None or length % 16: raise ValueError('Invalid watchdog dynamic segment')
            dynamic = start, length
        if kind == 3:
            if interpreter is not None or not 1 < length < 256 or data[start + length - 1] != 0:
                raise ValueError('Invalid watchdog interpreter')
            interpreter = data[start:start + length - 1].decode('ascii')
        if kind == 0x6474e552: relro = length > 0
        if kind == 0x6474e551:
            if flags & 1: raise ValueError('Executable watchdog stack rejected')
            nx = True
    if interpreter != INTERPRETER or dynamic is None:
        raise ValueError('Pinned ARM glibc interpreter required')
    tags, required, ended = {}, [], False
    for offset in range(dynamic[0], sum(dynamic), 16):
        tag, value = struct.unpack_from('<QQ', data, offset)
        if tag == 0: ended = True; break
        if tag in (15, 29): raise ValueError('Watchdog RPATH/RUNPATH rejected')
        if tag == 1: required.append(value)
        else: tags[tag] = value
    if not ended or 5 not in tags or not 0 < tags.get(10, 0) < 4 * 1024**2:
        raise ValueError('Invalid watchdog dynamic string table')
    strings = None
    for address, length, start in loads:
        if address <= tags[5] and tags[5] + tags[10] <= address + length:
            strings = data[start + tags[5] - address:start + tags[5] - address + tags[10]]
            break
    if strings is None: raise ValueError('Watchdog strings must be file backed')

    def name(table, offset, maximum=256):
        end = table.find(b'\0', offset, offset + maximum)
        if offset >= len(table) or end == -1: raise ValueError('Invalid watchdog ELF string')
        return table[offset:end].decode('ascii')

    dependencies = [name(strings, offset) for offset in required]
    if any(not value or '/' in value for value in dependencies):
        raise ValueError('Invalid watchdog library name')
    shoff = struct.unpack_from('<Q', data, 40)[0]
    shsize, shcount = struct.unpack_from('<HH', data, 58)
    if shsize != 64 or not 0 < shcount < 4096 or shoff + shsize * shcount > len(data):
        raise ValueError('Watchdog dynamic symbols required')
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, shoff + i * shsize) for i in range(shcount)]
    canary = False
    for section in sections:
        if section[1] != 11: continue
        start, length, link, stride = section[4], section[5], section[6], section[9]
        if stride != 24 or length % stride or length > 24 * 65536 or start + length > len(data) or link >= shcount:
            raise ValueError('Invalid watchdog dynamic symbol table')
        table = sections[link]
        if table[1] != 3 or table[4] + table[5] > len(data):
            raise ValueError('Invalid watchdog symbol strings')
        text = data[table[4]:table[4] + table[5]]
        for offset in range(start, start + length, stride):
            named, _, _, index, _, _ = struct.unpack_from('<IBBHQQ', data, offset)
            if name(text, named, 65536) == '__stack_chk_fail' and index == 0: canary = True
    hardening = {'relro': relro, 'bind_now': 24 in tags or bool(tags.get(30, 0) & 8)
                 or bool(tags.get(0x6ffffffb, 0) & 1), 'nx_stack': nx, 'stack_canary': canary}
    if not all(hardening.values()): raise ValueError('Stock watchdog hardening required')
    return {'machine': 'aarch64', 'elf_type': 3, 'interpreter': interpreter,
            'hardening': hardening, 'needed': dependencies}
