"""Bounded child commands and Linux PID identity; never signal by process name."""
import json
import ctypes
import os
from pathlib import Path
import selectors
import signal
import subprocess
import tempfile
import time
import sys

# Count Linux PIDs, including adopted descendants, independently of thread count.
MAX_DESCENDANTS = 4096


def private_directory(home, relative):
    path = Path(home)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('unsafe native home')
    for part in relative.split('/'):
        path /= part
        if path.is_symlink():
            raise ValueError('unsafe symlink in owned native path')
        path.mkdir(mode=0o700, exist_ok=True)
        if not path.is_dir() or path.stat().st_uid != os.getuid():
            raise ValueError('native directory owner mismatch')
    return path


def atomic_json(path, value):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('unsafe native state symlink')
    data = json.dumps(value, separators=(',', ':')).encode()
    if len(data) > 16384:
        raise ValueError('native state too large')
    fd, name = tempfile.mkstemp(prefix='.loopy-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_json(path):
    path = Path(path)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid() \
            or path.stat().st_size > 16384:
        raise ValueError('unsafe native state')
    return json.loads(path.read_text())


def parse_stat(text):
    fields = text[text.rindex(')') + 2:].split()
    return {'ppid': int(fields[1]), 'pgid': int(fields[2]), 'tty_nr': int(fields[4]),
            'starttime': fields[19], 'state': fields[0]}


def identity(pid, proc=Path('/proc'), strict=False):
    try:
        directory = Path(proc) / str(int(pid))
        uid = next(l for l in (directory / 'status').read_text().splitlines() if l.startswith('Uid:'))
        parsed = parse_stat((directory / 'stat').read_text())
        if parsed['state'] == 'Z':
            return None
        command = (directory / 'cmdline').read_bytes().split(b'\0')
        return {'pid': int(pid), 'ppid': parsed['ppid'], 'pgid': parsed['pgid'], 'uid': int(uid.split()[1]),
                'tty_nr': parsed['tty_nr'],
                'starttime': parsed['starttime'],
                'command': [x.decode(errors='replace') for x in command if x]}
    except (OSError, ValueError, IndexError, StopIteration) as error:
        if strict and (not isinstance(error, (FileNotFoundError, ProcessLookupError)) or directory.exists()):
            raise ValueError('native process identity cannot be verified') from error
        return None


def snapshot(proc=Path('/proc')):
    """Only same-UID metadata. A known live process read failure is never exit proof."""
    found = {}
    for directory in Path(proc).iterdir():
        if not directory.name.isdigit():
            continue
        try:
            status = (directory / 'status').read_text()
            uid = next(line for line in status.splitlines() if line.startswith('Uid:'))
            if int(uid.split()[1]) != os.getuid():
                continue
        except (FileNotFoundError, PermissionError):
            continue  # Other UIDs may be hidden by Android /proc policy.
        except ProcessLookupError as error:
            if directory.exists():
                raise ValueError('native process identity cannot be verified') from error
            continue  # ESRCH is an exit only after this PID directory disappeared.
        current = identity(int(directory.name), proc, strict=True)
        if current is not None:
            found[current['pid']] = current
    return found


def child_ids(pid, proc=Path('/proc')):
    """Optional kernel child lists; None means discovery must use PPID/waitpid."""
    tasks = Path(proc) / str(pid) / 'task'
    try:
        directories = list(tasks.iterdir())
    except FileNotFoundError:
        if identity(pid, proc, strict=True) is None:
            return []
        return None
    except PermissionError:
        return None
    found = set()
    for directory in directories:
        if not directory.name.isdigit():
            continue
        try:
            values = (directory / 'children').read_text().split()
        except FileNotFoundError:
            if not directory.exists():
                continue  # Thread exited while its children were enumerated.
            return None  # CONFIG_CHECKPOINT_RESTORE/PROC_CHILDREN may be absent.
        except PermissionError:
            return None
        except OSError as error:
            raise ValueError('native child lineage cannot be verified') from error
        if any(not value.isdigit() for value in values):
            raise ValueError('native child lineage invalid')
        found.update(int(value) for value in values)
        if len(found) > MAX_DESCENDANTS:
            raise ValueError('native descendant count exceeds bound')
    return found


def enable_subreaper():
    """Keep double-fork/setsid descendants parented to the owned supervisor."""
    library = ctypes.CDLL(None, use_errno=True)
    prctl = library.prctl
    prctl.argtypes = [ctypes.c_int, *([ctypes.c_ulong] * 4)]
    prctl.restype = ctypes.c_int
    active = ctypes.c_int()
    if prctl(36, 1, 0, 0, 0) or prctl(37, ctypes.addressof(active), 0, 0, 0) or active.value != 1:
        raise ValueError('native descendant ownership unavailable')
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)


def signal_process(record, sig):
    current = identity(record.get('pid', 0), strict=True)
    if current is None:
        return False
    if not same_identity(record, current):
        error = ValueError('native process identity changed; refusing signal')
        error.identity_changed_fields = tuple(key for key in ('pid', 'pgid', 'uid', 'starttime', 'command')
                                               if record.get(key) != current.get(key))
        raise error
    try:
        os.kill(record['pid'], sig)
        return True
    except ProcessLookupError:
        return False


def reap_children():
    options = os.WNOHANG | (0x40000000 if sys.platform in ('linux', 'android') else 0)  # Linux __WALL.
    while True:
        try:
            if os.waitpid(-1, options)[0] == 0:
                return False  # At least one direct/adopted child is still alive.
        except ChildProcessError:
            return True


class OwnedProcesses:
    """A live supervisor anchors PPID lineage, even across new process sessions."""
    def __init__(self):
        self.owner = identity(os.getpid(), strict=True)
        if self.owner is None or self.owner['pgid'] != os.getpid():
            raise ValueError('native ownership anchor unavailable')
        self.known = {}
        self.spawned = set()
        self.child_lists_available = True

    def register(self, pid):
        self.spawned.add(pid)
        current = identity(pid, strict=True)
        if current is None:
            return  # Exited/not visible yet; waitpid remains the independent completion guard.
        if current['uid'] != self.owner['uid'] or current.get('ppid') != self.owner['pid']:
            raise ValueError('native spawned child identity/lineage cannot be verified')
        self.known[pid] = current

    def refresh(self):
        if not same_identity(self.owner, identity(self.owner['pid'], strict=True)):
            raise ValueError('native ownership anchor changed')
        current = snapshot()
        for pid in self.spawned:
            live = identity(pid, strict=True)
            if live is not None:
                if live['uid'] != self.owner['uid'] or live.get('ppid') != self.owner['pid']:
                    raise ValueError('native spawned child identity/lineage cannot be verified')
                current[pid] = live
        owned = {self.owner['pid']: self.owner}
        # Current parentage authorizes new descendants and legitimate exec changes.
        while True:
            added = [p for p in current.values() if p['pid'] not in owned and p.get('ppid') in owned]
            if not added:
                break
            owned.update((p['pid'], p) for p in added)
            if len(owned) > MAX_DESCENDANTS + 1:
                raise ValueError('native descendant count exceeds bound')
        for pid, record in self.known.items():
            if pid in owned:
                continue
            live = identity(pid, strict=True)
            if live is not None:
                if not same_identity(record, live):
                    raise ValueError('native descendant identity changed')
                owned[pid] = live
        pending, visited = list(owned), set()
        while pending:
            parent = pending.pop()
            if parent in visited:
                continue
            visited.add(parent)
            children = child_ids(parent)
            if children is None:
                self.child_lists_available = False
                continue
            for pid in children:
                live = identity(pid, strict=True)
                if live is None:
                    continue
                if live['uid'] != self.owner['uid'] or live.get('ppid') not in owned:
                    raise ValueError('native child identity/lineage cannot be verified')
                owned[pid] = live
                pending.append(pid)
                if len(owned) > MAX_DESCENDANTS + 1:
                    raise ValueError('native descendant count exceeds bound')
        if len(owned) > MAX_DESCENDANTS + 1:
            raise ValueError('native descendant count exceeds bound')
        owned.pop(self.owner['pid'])
        self.known = owned
        return list(owned.values())

    def terminate(self):
        # Never signal this process group: it contains the ownership anchor.
        sent = set()
        for sig, seconds in ((signal.SIGTERM, 2), (signal.SIGKILL, 2)):
            until = time.monotonic() + seconds
            while True:
                empty = reap_children()
                live = self.refresh()
                if not live and empty:
                    return
                for record in live:
                    key = (sig, record['pid'], record['starttime'], tuple(record['command']))
                    if key not in sent:
                        try:
                            signal_process(record, sig)
                        except ValueError as error:
                            if getattr(error, 'identity_changed_fields', ()) == ('command',):
                                continue  # Refresh owned lineage after exec; never signal the stale record.
                            raise
                        sent.add(key)
                if time.monotonic() >= until:
                    break
                time.sleep(.05)
        raise ValueError('native descendant termination not confirmed')


def same_identity(record, current):
    keys = ('pid', 'pgid', 'uid', 'starttime', 'command')
    return bool(isinstance(record, dict) and isinstance(current, dict)
                and record.get('uid') == os.getuid()
                and record.get('pgid', 0) > 1
                and all(record.get(k) == current.get(k) for k in keys))


def same_process(record, current):
    return same_identity(record, current) and record['pgid'] != os.getpgrp()


def signal_owned(record, sig):
    current = identity(record.get('pid', 0))
    if not same_process(record, current):
        return False
    try:
        os.killpg(record['pgid'], sig)
        return True
    except ProcessLookupError:
        return False


def reap_failed_command(child):
    # Signal before reaping: a failed command may leave pipe-holding descendants.
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        # macOS can report EPERM for a group containing only an exited zombie.
        # Do not hide permission failures while the leader or any group survives.
        if child.poll() is None:
            raise
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise
    child.wait(timeout=3)


def run_bounded(argv, *, timeout=3, max_bytes=65536, env=None, stdin=None):
    # An inherited RLIMIT_FSIZE also limits ART caches and unrelated files.
    # Bound only the two captured streams, and keep their pipes under a deadline.
    if max_bytes < 0 or timeout <= 0:
        raise ValueError('invalid native child bounds')
    with tempfile.TemporaryFile() as source, selectors.DefaultSelector() as streams:
        if stdin is not None:
            source.write(stdin.encode())
            source.seek(0)
        child = subprocess.Popen(argv, stdin=source if stdin is not None else subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env=env, start_new_session=True)
        stdout, stderr = bytearray(), bytearray()
        total, deadline = 0, time.monotonic() + timeout
        try:
            for stream, output in ((child.stdout, stdout), (child.stderr, stderr)):
                streams.register(stream, selectors.EVENT_READ, output)
            while streams.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError('native child timeout')
                for key, _ in streams.select(remaining):
                    data = os.read(key.fd, min(65536, max_bytes - total + 1))
                    if not data:
                        streams.unregister(key.fileobj)
                        continue
                    total += len(data)
                    if total > max_bytes:
                        raise ValueError('native child output exceeds bound')
                    key.data.extend(data)
            try:
                code = child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as error:
                raise ValueError('native child timeout') from error
        except BaseException:
            reap_failed_command(child)
            raise
        finally:
            child.stdout.close(); child.stderr.close()
        if code != 0:
            raise ValueError(f'native child exit {code}: {stderr.decode(errors="replace")[:512]}')
        return stdout.decode(errors='strict')
