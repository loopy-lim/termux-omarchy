"""Owned Unix-only bridge for fixed Android settings intents; no extra grants."""
from collections import deque
import os
from pathlib import Path
import re
import signal
import socket
import stat
import struct
import subprocess
import sys
import threading
import time

from processes import atomic_json, identity, read_json, run_bounded, same_identity
from omarchy_resources import StartupLog, live_peer
from omarchy_android_client import ACTIONS, call, decode, encode, identifier, private_file, receive


class AndroidFailure(ValueError):
    pass


class Nonces:
    """Reject replay in a bounded recent window without exhausting the service."""
    def __init__(self):
        self.values, self.seen = deque(), set()

    def accept(self, nonce):
        if nonce in self.seen:
            raise AndroidFailure('android-request-repeated')
        if len(self.values) == 4096:
            self.seen.remove(self.values.popleft())
        self.values.append(nonce)
        self.seen.add(nonce)


def service_arguments(args):
    if len(args) != 5 or args[0] != '_serve' or not re.fullmatch(r':[2-9][0-9]', args[2]) \
            or not re.fullmatch(r'[0-9]{1,10}', args[3]) or int(args[3]) < 2 \
            or not re.fullmatch(r'[0-9]{1,32}', args[4]):
        raise AndroidFailure('android-service-arguments')
    return identifier(args[1]), args[2], int(args[3]), args[4]


def handle(request, prefix, env, runner=run_bounded):
    if not isinstance(request, dict) or set(request) != {'schema', 'token', 'nonce', 'action'} \
            or type(request.get('schema')) is not int or request['schema'] != 1 \
            or not isinstance(request.get('action'), str) or request['action'] not in ACTIONS:
        raise AndroidFailure('android-request-invalid')
    identifier(request['token']); identifier(request['nonce'])
    if request['action'] == 'ping':
        return dict(request, status='ready', reason='android-service-ready')
    arguments = {'wifi': ['-a', 'android.settings.panel.action.WIFI'],
                 'bluetooth': ['-a', 'android.settings.BLUETOOTH_SETTINGS'],
                 'desktop': ['-n', 'com.termux.x11/com.termux.x11.MainActivity']}[request['action']]
    try:
        output = runner([str(Path(prefix) / 'bin/am'), 'start', *arguments],
                        env=env, timeout=8, max_bytes=4096)
        # TermuxAm acknowledges an intent without waiting for a visible activity.
        accepted = any(line.startswith('Starting: Intent {') for line in output.splitlines()) \
            and not any(line.startswith(('Error:', 'Exception:', 'SecurityException:'))
                        for line in output.splitlines())
    except (OSError, ValueError):
        accepted = False
    return dict(request, status='accepted' if accepted else 'unavailable',
                reason='android-launch-requested' if accepted else 'android-launch-unavailable')


def prepare(runtime, value):
    info = runtime.short.lstat()
    marker = {key: value[key] for key in ('schema', 'token', 'uid', 'root', 'runtime')}
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 \
            or [info.st_dev, info.st_ino, info.st_uid] != value['runtime'] \
            or info.st_uid != os.getuid() or read_json(runtime.short / 'owner.json') != marker:
        raise AndroidFailure('android-owner-invalid')
    path = runtime.short / 'android'
    if os.path.lexists(path):
        raise AndroidFailure('android-directory-existing')
    path.mkdir(mode=0o700)
    fd = os.open(path / 'cookie', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(os.urandom(32))
    owner = value['processes'][0]
    atomic_json(path / 'lease.json', dict(marker, owner=owner, serverPid=0))


def command(runtime, value):
    owner = value['processes'][0]
    return [str(runtime.prefix / 'bin/python3'), str(runtime.root / 'omarchy_android.py'),
            '_serve', value['token'], value['display'], str(owner['pid']), owner['starttime']]


def ready(runtime, value):
    record = value.get('androidProcess')
    if not isinstance(record, dict):
        return False
    if record.get('command') != command(runtime, value):
        raise AndroidFailure('android-process-command')
    if not live_peer(runtime.short / 'android/native', [record]):
        return False
    try:
        return call('ping', runtime.short / 'android')['status'] == 'ready'
    except (OSError, ValueError):
        return False


def start(runtime, value, owned, logs, stopping):
    prepare(runtime, value)
    args = command(runtime, value)
    log = StartupLog(runtime.root / 'sessions' / value['token'] / 'android.log')
    logs.append(log)
    child = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, env=runtime.env)
    owned.register(child.pid); log.attach(child.stdout)
    birth = None
    until = time.monotonic() + 5
    while time.monotonic() < until and not stopping.is_set():
        if child.poll() is not None:
            raise AndroidFailure('android-service-exited')
        owned.refresh()
        record = identity(child.pid, strict=True)
        if record is not None:
            current = {key: record[key] for key in ('pid', 'pgid', 'uid', 'starttime')}
            if record['pid'] != child.pid or record['uid'] != os.getuid() \
                    or record['ppid'] != os.getpid() or birth is not None and current != birth:
                raise AndroidFailure('android-process-identity')
            birth = current
            if record['command'] and record['command'] != args:
                raise AndroidFailure('android-process-command')
            if record['command'] == args:
                value['androidProcess'] = record
                if ready(runtime, value):
                    return child
        time.sleep(.05)
    raise AndroidFailure('android-startup-unconfirmed')


def serve(token, display, owner_pid, birth):
    prefix = Path('/data/data/com.termux/files/usr')
    root = Path(__file__).resolve().parent
    short = Path('/data/data/com.termux/lr')
    path = short / 'android'
    lease = read_json(path / 'lease.json')
    marker = read_json(short / 'owner.json')
    owner = lease.get('owner') if isinstance(lease, dict) else None
    expected = [str(prefix / 'bin/python3'), str(root / 'omarchy_runtime.py'), '_supervise', token, display]
    def parent_alive():
        return same_identity(owner, identity(owner_pid, strict=True))
    if not owner or owner.get('command') != expected or owner.get('pid') != owner_pid \
            or owner.get('starttime') != birth or owner.get('uid') != os.getuid() \
            or os.getppid() != owner_pid or not parent_alive() \
            or not isinstance(marker, dict) or any(lease.get(k) != marker.get(k)
                        for k in ('schema', 'token', 'uid', 'root', 'runtime')) \
            or marker.get('token') != token or marker.get('uid') != os.getuid():
        raise AndroidFailure('android-owner-invalid')
    key = private_file(path, 'cookie', 32)
    if len(key) != 32 or stat.S_IMODE(path.lstat().st_mode) != 0o700:
        raise AndroidFailure('android-cookie-invalid')
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    used = Nonces()
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(str(path / 'native'))  # Never unlink/adopt an existing endpoint.
        server.listen(4); server.settimeout(.25)
        lease['serverPid'] = os.getpid()
        atomic_json(path / 'lease.json', lease)
        while not stopping.is_set() and parent_alive():
            if read_json(short / 'owner.json') != marker:
                raise AndroidFailure('android-session-changed')
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            with connection:
                connection.settimeout(10)
                try:
                    _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid != os.getuid():
                        raise AndroidFailure('android-client-uid')
                    request = decode(receive(connection, timeout=3), key, token)
                    used.accept(request['nonce'])
                    if not parent_alive() or read_json(short / 'owner.json') != marker:
                        raise AndroidFailure('android-owner-changed')
                    reply = handle(request, prefix, os.environ.copy())
                    connection.sendall(encode(reply, key))
                except (OSError, ValueError, KeyError):
                    pass  # Malformed input/closed readiness probe cannot stop Linux.
    # Supervisor's inode ledger retires the endpoint only after ECHILD proof.


if __name__ == '__main__':
    try:
        serve(*service_arguments(sys.argv[1:]))
    except (OSError, ValueError):
        print('android-service-unavailable', file=sys.stderr)
        sys.exit(1)
