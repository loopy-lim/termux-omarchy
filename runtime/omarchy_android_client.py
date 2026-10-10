#!/usr/bin/python3
"""Private session protocol shared by the native service and PRoot settings CLI."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import time
import uuid

LIMIT = 4096
ACTIONS = {'ping', 'wifi', 'bluetooth', 'desktop'}
BASE = Path('/run/user/1000/android')


def identifier(value):
    if not isinstance(value, str) or len(value) != 36 or str(uuid.UUID(value)) != value:
        raise ValueError('android-request-invalid')
    return value


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('android-packet-duplicate')
        result[key] = value
    return result


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def encode(value, key):
    if len(key) != 32 or 'mac' in value:
        raise ValueError('android-key-invalid')
    packet = canonical(dict(value, mac=hmac.new(key, canonical(value), hashlib.sha256).hexdigest()))
    if len(packet) > LIMIT:
        raise ValueError('android-packet-bounds')
    return packet


def decode(packet, key, token):
    if not packet or len(packet) > LIMIT or len(key) != 32:
        raise ValueError('android-packet-bounds')
    value = json.loads(packet, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError('android-packet-invalid')
    mac = value.pop('mac', None)
    if not isinstance(mac, str) or len(mac) != 64 \
            or not hmac.compare_digest(mac, hmac.new(key, canonical(value), hashlib.sha256).hexdigest()):
        raise ValueError('android-packet-authentication')
    if type(value.get('schema')) is not int or value['schema'] != 1 \
            or identifier(value.get('token')) != token:
        raise ValueError('android-session-changed')
    identifier(value.get('nonce'))
    return value


def receive(connection, timeout=10):
    data = bytearray()
    until = time.monotonic() + timeout
    while True:
        remaining = until - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('android-packet-timeout')
        connection.settimeout(remaining)
        part = connection.recv(min(1024, LIMIT + 1 - len(data)))
        if not part:
            break
        data.extend(part)
        if len(data) > LIMIT:
            raise ValueError('android-packet-bounds')
    if not data:
        raise ValueError('android-packet-empty')
    return bytes(data)


def private_file(base, name, maximum):
    descriptor = os.open(base / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 \
                or info.st_nlink != 1 or info.st_size > maximum:
            raise ValueError('android-private-file')
        return os.read(descriptor, maximum + 1)
    finally:
        os.close(descriptor)


def credentials(base):
    info = Path(base).lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('android-private-directory')
    key = private_file(base, 'cookie', 32)
    lease = json.loads(private_file(base, 'lease.json', LIMIT), object_pairs_hook=unique)
    if len(key) != 32 or not isinstance(lease, dict) or lease.get('schema') != 1 \
            or type(lease.get('uid')) is not int or type(lease.get('serverPid')) is not int \
            or lease['serverPid'] < 2:
        raise ValueError('android-lease-invalid')
    identifier(lease.get('token'))
    return key, lease


def validate_reply(reply, request):
    if set(reply) != {*request, 'status', 'reason'} \
            or any(reply.get(key) != value for key, value in request.items()) \
            or (reply.get('status'), reply.get('reason')) not in (
                ('ready', 'android-service-ready'), ('accepted', 'android-launch-requested'),
                ('unavailable', 'android-launch-unavailable')):
        raise ValueError('android-reply-invalid')
    return reply


def call(action, base=BASE):
    if not isinstance(action, str) or action not in ACTIONS:
        raise ValueError('android-action-invalid')
    base = Path(base)
    key, lease = credentials(base)
    request = {'schema': 1, 'token': lease['token'], 'nonce': str(uuid.uuid4()), 'action': action}
    path = base / 'native'
    before = path.lstat()
    if not stat.S_ISSOCK(before.st_mode) or len(os.fsencode(path)) >= 108:
        raise ValueError('android-socket-invalid')
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(10)
        connection.connect(str(path))
        pid, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        # PRoot's fake guest UID is not the kernel UID; use the native lease.
        if pid != lease['serverPid'] or uid != lease['uid']:
            raise ValueError('android-peer-changed')
        connection.sendall(encode(request, key))
        connection.shutdown(socket.SHUT_WR)
        reply = validate_reply(decode(receive(connection), key, lease['token']), request)
    after = path.lstat()
    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino) \
            or credentials(base) != (key, lease):
        raise ValueError('android-session-changed')
    return reply


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError('android-argument-count')
        value = call(sys.argv[1])
    except (OSError, ValueError):
        print('android-settings-unavailable', file=sys.stderr)
        return 1
    print(json.dumps(value, separators=(',', ':')), flush=True)
    return 0 if value['status'] in ('ready', 'accepted') else 1


if __name__ == '__main__':
    sys.exit(main())
