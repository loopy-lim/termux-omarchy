"""Owned, fixed local VS Code web backend; never adopt an unrelated listener."""
import fcntl
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode

COMMIT = '2a59476c9bfcb90b3ddc372c36762471b7dfad1c'
CLI = '/opt/loopy-vscode/1.141.0/bin/code-tunnel'
BRIDGE = '/usr/local/bin/omarchy-proot-settings'
PORT = 8765


def private_dir(path):
    path = Path(path)
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError('code-web-directory-symlink')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('code-web-directory-private')
    return path


def read_private(path, limit=32768):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_nlink != 1 \
                or info.st_uid != os.getuid() or info.st_size > limit:
            raise ValueError('code-web-file-private')
        data = os.read(fd, limit + 1)
        if len(data) > limit: raise ValueError('code-web-file-bounds')
        return data
    finally:
        os.close(fd)


def exclusive(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(data)
        out.flush(); os.fsync(out.fileno())


def atomic(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def identity(pid, proc=Path('/proc')):
    try:
        base = proc / str(int(pid))
        fields = (base / 'stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] == 'Z': return None
        uid = next(line for line in (base / 'status').read_text().splitlines() if line.startswith('Uid:'))
        return {'pid': int(pid), 'ppid': int(fields[1]), 'pgid': int(fields[2]),
                'starttime': fields[19], 'uid': int(uid.split()[1]),
                'command': [s.decode() for s in (base / 'cmdline').read_bytes().split(b'\0') if s]}
    except (FileNotFoundError, ProcessLookupError):
        return None
    except (IndexError, StopIteration, UnicodeError) as error:
        raise ValueError('code-web-process-unreadable') from error


def same(a, b):
    return isinstance(a, dict) and isinstance(b, dict) and all(
        a.get(k) == b.get(k) for k in ('pid', 'pgid', 'starttime', 'uid', 'command'))


def owned(record, owner):
    seen = set()
    while record and record['pid'] != owner['pid']:
        if record['pid'] in seen or len(seen) >= 64 or record['uid'] != owner['uid']:
            return False
        seen.add(record['pid']); record = identity(record['ppid'])
    return same(record, owner)


def session():
    lease = json.loads(read_private(Path('/run/user/1000/android/lease.json')))
    owner = lease['owner']
    command = owner.get('command', [])
    if len(command) != 5 or command[2] != '_supervise' or command[3] != lease['token'] \
            or not same(owner, identity(owner['pid'])) or not owned(identity(os.getpid()), owner):
        raise ValueError('code-web-session-unowned')
    return lease['token'], owner


def arguments(base):
    return [CLI, '--cli-data-dir', str(base / 'cli'), 'serve-web', '--host', '127.0.0.1',
            '--port', str(PORT), '--connection-token-file', str(base / 'connection-token'),
            '--server-data-dir', str(base / 'data'), '--commit-id', COMMIT,
            '--accept-server-license-terms', '--disable-telemetry']


def response(token, port=PORT):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
    try:
        connection.request('GET', '/', headers={'Cookie': 'vscode-tkn=' + token})
        reply = connection.getresponse()
        return reply.status, reply.read(262144)
    finally:
        connection.close()


def authenticated_ready(token, port=PORT):
    try:
        status, body = response(token, port)
        rejected, _ = response('invalid-' + secrets.token_hex(16), port)
        return status == 200 and b'vscode-workbench-web-configuration' in body and rejected in (401, 403)
    except (OSError, http.client.HTTPException):
        return False


def ensure_backend(base, session_token, owner, timeout=45):
    args = arguments(base)
    state_path = base / 'backend.json'
    child = None
    if os.path.lexists(state_path):
        state = json.loads(read_private(state_path))
        previous = state.get('process', {})
        current = identity(previous.get('pid', 0))
        if current:
            if state.get('session') != session_token or state.get('args') != args \
                    or not same(previous, current) or not owned(current, owner):
                raise ValueError('code-web-backend-existing-unowned')
            record = current
        else:
            record = None
    else:
        record = None
    token_file = base / 'connection-token'
    if not os.path.lexists(token_file): exclusive(token_file, secrets.token_hex(32).encode())
    token = read_private(token_file, 64).decode()
    if not re.fullmatch(r'[a-f0-9]{64}', token): raise ValueError('code-web-token-invalid')
    if record is None:
        # No signals, shutdown requests or state adoption for an unrelated listener.
        with socket.socket() as probe:
            # Match Node's listener semantics: a previous owned connection in
            # TIME_WAIT must not block restart. An active listener still fails.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', PORT))
        env = dict(os.environ, TMPDIR=str(base / 'tmp'))
        for key in ('ELECTRON_RUN_AS_NODE', 'VSCODE_IPC_HOOK_CLI', 'VSCODE_PORTABLE'):
            env.pop(key, None)
        # CLI logs print an authenticated URL. Do not persist or echo that secret.
        child = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        until = time.monotonic() + 3
        record = None
        while time.monotonic() < until:
            if child.poll() is not None: raise ValueError('code-web-backend-exited')
            record = identity(child.pid)
            if record and record['command'] == args: break
            time.sleep(.025)
        if not record or record['command'] != args or record['pgid'] != os.getpgrp() or not owned(record, owner):
            raise ValueError('code-web-child-unverified')
        atomic(state_path, {'session': session_token, 'args': args, 'process': record})
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if child and child.poll() is not None or not same(record, identity(record['pid'])) \
                or not owned(identity(record['pid']), owner):
            raise ValueError('code-web-backend-changed')
        if authenticated_ready(token): return token
        time.sleep(.2)
    raise ValueError('code-web-readiness-timeout')


def destination(values):
    if len(values) > 1 or values and values[0].startswith('-'):
        raise ValueError('code-web-use-one-file-or-folder')
    path = Path(values[0] if values else Path.home()).resolve(strict=True)
    if not path.is_dir() and not path.is_file(): raise ValueError('code-web-path-invalid')
    return ('folder' if path.is_dir() else 'file'), str(path)


def main():
    try:
        target = destination(sys.argv[1:])
        session_token, owner = session()
        base = private_dir(Path.home() / '.local/share/loopy-code-web')
        for name in ('cli', 'data', 'tmp'): private_dir(base / name)
        fd = os.open(base / 'launcher.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'r+') as lock:
            info = os.fstat(lock.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_nlink != 1 \
                    or info.st_uid != os.getuid():
                raise ValueError('code-web-lock-invalid')
            until = time.monotonic() + 3
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= until: raise ValueError('code-web-start-in-progress')
                    time.sleep(.05)
            token = ensure_backend(base, session_token, owner)
        url = 'http://127.0.0.1:8765/?' + urlencode({'tkn': token, target[0]: target[1]})
        result = subprocess.run([BRIDGE, '--browser', url], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if result.returncode: raise ValueError('code-web-browser-unavailable')
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        # Only fixed internal reason codes may be logged; subprocess errors can
        # contain the authenticated browser URL and must never be printed.
        reason = str(error) if isinstance(error, ValueError) else ''
        if isinstance(error, OSError) and isinstance(error.errno, int):
            reason = 'code-web-os-error-' + str(error.errno)
        suffix = ' (' + reason + ')' if re.fullmatch(r'code-web-[a-z0-9-]+', reason) else ''
        print('Local web editor unavailable' + suffix + '; the original Visual Studio Code launcher is preserved.', file=sys.stderr)
        return 1
