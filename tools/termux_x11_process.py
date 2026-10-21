#!/usr/bin/env python3
"""Repair the pinned X11 input process or its synthetic language-switch mapping."""
import argparse
import copy
import hashlib
import io
import os
from pathlib import Path
import re
import stat
import struct
import zipfile

APK_SHA256 = '1370cdab3cbe96ba330cc7e430bbefcc163bca39fd1db8ffdce51eb8e290e713'
LANGUAGE_APK_SHA256 = 'd0443400bd9475b5e5275897ec88503877f6af01e85a4e0c38d93f6e960a1948'
NATIVE_SHA256 = 'f9d60f48c5af45971571783166437b25dfb84cf7a2233c0265c49f652a9fe851'
KEYMAP_SHA256 = 'baa3be71c3b73505d78f91e0c9acb1ef3e12fbb7ca5b589a2c523b03d6b51f91'
KEYMAP_OFFSET = 411744
NATIVE_LIBRARY = 'lib/arm64-v8a/libXlorie.so'
ANDROID = 'http://schemas.android.com/apk/res/android'
PACKAGE = 'com.termux.x11'
MAIN = PACKAGE + '.MainActivity'
KEYS = PACKAGE + '.utils.KeyInterceptor'
NONE = 0xffffffff


def require(value):
    if not value:
        raise ValueError('Unexpected shared-UID X11 manifest')


def chunks(data):
    require(isinstance(data, bytes) and 8 <= len(data) <= 1024**2)
    require(struct.unpack_from('<HHI', data) == (3, 8, len(data)))
    offset = 8
    result = []
    while offset < len(data):
        require(offset + 8 <= len(data))
        kind, header, size = struct.unpack_from('<HHI', data, offset)
        require(8 <= header <= size and size % 4 == 0 and offset + size <= len(data))
        result.append((kind, header, offset, size))
        offset += size
    return result


def strings(data, row):
    kind, header, offset, size = row
    require(kind == 1 and header == 28)
    count, styles, flags, start, style_start = struct.unpack_from('<IIIII', data, offset + 8)
    require(count <= 32768 and 28 + (count + styles) * 4 <= start < size)
    limit = style_start or size
    require(start < limit <= size)
    output = []
    for index in range(count):
        relative, = struct.unpack_from('<I', data, offset + 28 + index * 4)
        cursor = offset + start + relative
        end = offset + limit
        require(cursor < end)
        def length(unit):
            nonlocal cursor
            require(cursor + unit <= end)
            value = int.from_bytes(data[cursor:cursor + unit], 'little'); cursor += unit
            high = 0x80 if unit == 1 else 0x8000
            if value & high:
                require(cursor + unit <= end)
                value = ((value & (high - 1)) << (8 if unit == 1 else 16)) | int.from_bytes(data[cursor:cursor + unit], 'little')
                cursor += unit
            return value
        if flags & 0x100:
            length(1)
            size_bytes = length(1)
            require(cursor + size_bytes + 1 <= end and data[cursor + size_bytes] == 0)
            value = data[cursor:cursor + size_bytes].decode('utf-8')
        else:
            size_bytes = length(2) * 2
            require(cursor + size_bytes + 2 <= end and data[cursor + size_bytes:cursor + size_bytes + 2] == b'\0\0')
            value = data[cursor:cursor + size_bytes].decode('utf-16le')
        output.append(value)
    return output


def nodes(data):
    rows = chunks(data)
    pools = [row for row in rows if row[0] == 1]
    require(len(pools) == 1)
    pool = strings(data, pools[0])
    def text(index):
        require(index < len(pool))
        return pool[index]
    output = []
    for kind, header, offset, size in rows:
        if kind != 0x102:
            continue
        require(header == 16 and size >= 36)
        ext = offset + header
        _, name, attr_start, attr_size, count, id_index, class_index, style_index = struct.unpack_from('<IIHHHHHH', data, ext)
        require(attr_start == 20 and attr_size == 20 and count <= 512)
        require(ext + attr_start + count * attr_size == offset + size)
        attrs = {}
        for index in range(count):
            at = ext + attr_start + index * attr_size
            ns, key, raw, value_size, zero, value_type, value = struct.unpack_from('<IIIHBBI', data, at)
            require(value_size == 8 and zero == 0)
            identity = (None if ns == NONE else text(ns), text(key))
            require(identity not in attrs)
            decoded = text(raw) if raw != NONE else (text(value) if value_type == 3 else value)
            attrs[identity] = (decoded, data[at:at + 20])
        require(all(v <= count for v in (id_index, class_index, style_index)))
        output.append({'tag': text(name), 'attrs': attrs, 'offset': offset, 'size': size, 'count': count})
    return output


def component_processes(data):
    elements = nodes(data)
    manifests = [row for row in elements if row['tag'] == 'manifest']
    applications = [row for row in elements if row['tag'] == 'application']
    require(len(manifests) == 1 and len(applications) == 1)
    def attr(row, name, namespace=ANDROID, default=None):
        return row['attrs'].get((namespace, name), (default,))[0]
    require(attr(manifests[0], 'package', None) == PACKAGE)
    require(attr(manifests[0], 'sharedUserId') == 'com.termux')
    application = attr(applications[0], 'process', default=PACKAGE)
    result = {}
    for row in elements:
        if row['tag'] not in ('activity', 'service', 'receiver', 'provider', 'activity-alias'):
            continue
        name = attr(row, 'name')
        require(isinstance(name, str) and name not in result)
        value = attr(row, 'process', default=application)
        require(isinstance(value, str))
        result[name] = PACKAGE + value if value.startswith(':') else value
    require(MAIN in result and KEYS in result and result[MAIN] == 'com.termux')
    return result


def patch(data):
    before = component_processes(data)
    if before[KEYS] == before[MAIN]:
        return data
    elements = nodes(data)
    def component(name):
        matches = [row for row in elements if row['attrs'].get((ANDROID, 'name'), (None,))[0] == name]
        require(len(matches) == 1)
        return matches[0]
    main, keys = component(MAIN), component(KEYS)
    require((ANDROID, 'process') in main['attrs'] and (ANDROID, 'process') not in keys['attrs'])
    attribute = main['attrs'][(ANDROID, 'process')][1]
    offset, size = keys['offset'], keys['size']
    updated = bytearray(data[:offset + size] + attribute + data[offset + size:])
    struct.pack_into('<I', updated, 4, len(updated))
    struct.pack_into('<I', updated, offset + 4, size + 20)
    struct.pack_into('<H', updated, offset + 16 + 12, keys['count'] + 1)
    result = bytes(updated)
    require(component_processes(result) == {**before, KEYS: before[MAIN]})
    return result


def patch_language_switch(data):
    """Match the complete inspected ELF before changing Android 204 to KEY_HANGEUL.

    This is a pinned binary repair, not a native source rebuild. The full table
    was matched to upstream commit 6d3c688 and the actual installed APK. JNI
    continues to prefer a nonzero physical scancode over this fallback table.
    """
    require(isinstance(data, bytes) and hashlib.sha256(data).hexdigest() == NATIVE_SHA256)
    require(data[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', data, 18)[0] == 183)
    table = data[KEYMAP_OFFSET:KEYMAP_OFFSET + 304 * 4]
    require(hashlib.sha256(table).hexdigest() == KEYMAP_SHA256)
    offset = KEYMAP_OFFSET + 204 * 4
    require(struct.unpack_from('<I', data, offset)[0] == 0)
    result = bytearray(data)
    struct.pack_into('<I', result, offset, 122)  # Linux KEY_HANGEUL; XKB code 130.
    return bytes(result)


def rewrite_apk(source, destination, *, expected_sha256=None, language_switch=False):
    require(type(language_switch) is bool)
    if expected_sha256 is None:
        expected_sha256 = LANGUAGE_APK_SHA256 if language_switch else APK_SHA256
    require(isinstance(expected_sha256, str) and re.fullmatch('[a-f0-9]{64}', expected_sha256))
    fd = os.open(source, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= 64 * 1024**2)
        data = stream.read(64 * 1024**2 + 1)
    require(hashlib.sha256(data).hexdigest() == expected_sha256)
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as original, zipfile.ZipFile(output, 'w') as candidate:
        entries = original.infolist()
        require(len(entries) <= 8192 and len({e.filename for e in entries}) == len(entries))
        require(sum(e.file_size for e in entries) <= 256 * 1024**2)
        require('AndroidManifest.xml' in original.namelist())
        if language_switch:
            require(NATIVE_LIBRARY in original.namelist())
        for entry in entries:
            name = entry.filename
            if re.fullmatch(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC))', name, re.IGNORECASE):
                continue
            payload = original.read(entry)
            if name == 'AndroidManifest.xml':
                payload = patch(payload)
            elif language_switch and name == NATIVE_LIBRARY:
                payload = patch_language_switch(payload)
            candidate.writestr(copy.copy(entry), payload)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(output.getvalue()); stream.flush(); os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('unsigned_destination', type=Path)
    parser.add_argument('--language-switch', action='store_true',
                        help='Repair KeyBridge language_switch in the exact installed process-fix APK')
    arguments = parser.parse_args()
    rewrite_apk(arguments.source, arguments.unsigned_destination,
                language_switch=arguments.language_switch)


if __name__ == '__main__':
    main()
