"""One session-owned, ordered Android job consumer for genuine Hyprland.

The compositor launches this worker in its own PRoot process tree. inotify
avoids a polling child or one subprocess per action. Errors contain no input.
"""
import ctypes
import fcntl
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from hyprland_actions import Hyprland, CompositorLifetime
import loopy_input
from omarchy_clipboard import Relay


class DisplayBinding:
    """Unpublish only the marker owned by this worker, through its directory fd."""
    def __init__(self, directory, name, info):
        self.fd, self.name = os.dup(directory), name
        self.identity = (info.st_dev, info.st_ino)

    def close(self):
        if self.fd is None:
            return
        try:
            info = os.stat(self.name, dir_fd=self.fd, follow_symlinks=False)
            if (info.st_dev, info.st_ino) == self.identity:
                os.unlink(self.name, dir_fd=self.fd)
        except FileNotFoundError:
            pass
        finally:
            os.close(self.fd); self.fd = None


def configure_input(runtime, token, display):
    if (type(token) is not str or not re.fullmatch(r'[A-Za-z0-9-]{1,64}', token)
            or type(display) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', display)
            or display in {'.', '..'}):
        raise ValueError('Current session Wayland display required')
    runtime = Path(runtime)
    directory = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        if os.fstat(directory).st_uid != os.getuid():
            raise ValueError('Owned input directory required')
        info = os.stat(display, dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Owned inner compositor display required')
        marker, expected = 'display-' + token, (display + '\n').encode('ascii')
        try:
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=directory)
            with os.fdopen(fd, 'wb') as output:
                output.write(expected)
                info = os.fstat(output.fileno())
        except FileExistsError:
            fd = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
            with os.fdopen(fd, 'rb') as source:
                info = os.fstat(source.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 65
                        or source.read(66) != expected):
                    raise ValueError('Existing session display record differs; data preserved')
        loopy_input.IPC_ROOT = runtime
        return DisplayBinding(directory, marker, info)
    finally:
        os.close(directory)


class Worker:
    def __init__(self, directory, token, compositor, signature=None, handoff_seconds=6):
        if type(token) is not str or not re.fullmatch(r'[A-Za-z0-9-]{1,64}', token):
            raise ValueError('Session token required')
        self.directory, self.token, self.compositor = Path(directory), token, compositor
        self.pattern = re.compile('command-' + re.escape(token) + r'-[0-9]{16}\.json')
        self.fd = self.lock = self.lifetime = None
        self.started_ns, self.minimum_ns = time.monotonic_ns(), None
        self.display = None
        self.published = {}
        try:
            self.fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            if os.fstat(self.fd).st_uid != os.getuid():
                raise ValueError('Owned action directory required')
            self.lock = os.open('actions-' + token + '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                                0o600, dir_fd=self.fd)
            self._regular(self.lock, 16384)
            if signature is None:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                if (type(signature) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', signature)
                        or not .05 <= handoff_seconds <= 6):
                    raise ValueError('Bounded compositor handoff required')
                self.lifetime = CompositorLifetime(self.compositor.path)
                self._acquire(signature, handoff_seconds)
        except BaseException:
            self.close()
            raise

    def _acquire(self, signature, seconds):
        deadline = time.monotonic() + seconds
        while self.lifetime.alive():
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # Reloads are duplicates; a different compositor gets one bounded
                # chance to inherit the token after the old worker finishes.
                if self._ready_signature() == signature:
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Compositor worker handoff deadline exceeded')
                self.lifetime.alive(min(.05, remaining))
            else:
                if self.lifetime.alive():
                    return
                break
        raise ConnectionError('Requested compositor exited during worker handoff')

    def _ready_signature(self):
        try:
            fd = os.open('actions-' + self.token + '.ready.json', os.O_RDONLY | os.O_NOFOLLOW
                         | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=self.fd)
        except FileNotFoundError:
            return None  # The retiring owner unpublishes before releasing flock.
        with os.fdopen(fd, 'rb') as source:
            info = self._regular(source.fileno(), 1024)
            if stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError('Private compositor readiness required')
            data = source.read(1025)
            after = self._regular(source.fileno(), 1024)
            if (len(data) > 1024 or stat.S_IMODE(after.st_mode) != 0o600
                    or (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
                raise ValueError('Compositor readiness changed or exceeded its bound')
            value = json.loads(data)
        if (type(value) is not dict or set(value) != {'token', 'signature', 'pid', 'uid'}
                or value['token'] != self.token or type(value['signature']) is not str
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value['signature'])
                or type(value['pid']) is not int or not 0 < value['pid'] < 2**31
                or type(value['uid']) is not int or value['uid'] != os.getuid()):
            raise ValueError('Existing compositor readiness differs; data preserved')
        return value['signature']

    @staticmethod
    def _regular(fd, limit):
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > limit:
            raise ValueError('Bounded owned regular job file required')
        return info

    def _error(self, error):
        name = 'error-' + self.token + '.log'
        message = ('Desktop command failed: ' + type(error).__name__ + '\n').encode()
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.fd)
            with os.fdopen(fd, 'wb') as output:
                self._regular(output.fileno(), 2048)
                output.truncate(0); output.write(message[:2048])
        except (OSError, ValueError):
            pass

    def consume(self, lifetime=None):
        jobs = []
        # Bound both discovery and each batch; replacement-session jobs stay
        # untouched. Java limits the current session to 256 pending records.
        with os.scandir(self.fd) as entries:
            for index, entry in enumerate(entries):
                if index >= 8192:
                    self._error(ValueError('Action directory exceeds discovery bound'))
                    break
                if self.pattern.fullmatch(entry.name):
                    jobs.append(entry.name)
        count = 0
        for name in sorted(jobs)[:128]:
            if lifetime is not None and not lifetime.alive():
                return count  # Leave pending records for the successor's generation fence.
            identity = None
            try:
                identity = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
                if not stat.S_ISREG(identity.st_mode):
                    raise ValueError('Regular action record required')
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=self.fd)
                with os.fdopen(fd, 'rb') as source:
                    info = self._regular(source.fileno(), 16384)
                    if (info.st_dev, info.st_ino) != (identity.st_dev, identity.st_ino):
                        raise ValueError('Action identity changed before read')
                    data = source.read(16385)
                if len(data) > 16384:
                    raise ValueError('Action record exceeds its byte bound')
                job = json.loads(data)
                if self.minimum_ns is not None:
                    created = job.pop('created_ns', None) if isinstance(job, dict) else None
                    if type(created) is not int or not 0 < created <= min(time.monotonic_ns(), 2**63 - 1):
                        raise ValueError('Input belongs to an earlier compositor generation')
                    if created < self.minimum_ns:
                        continue  # Normal recovery retirement; preserve the existing error record.
                self.compositor.execute(job)
            except (OSError, ValueError, TypeError, KeyError, UnicodeError) as error:
                self._error(error)
            finally:
                if identity is not None:
                    try:
                        current = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
                        if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                            os.unlink(name, dir_fd=self.fd)
                    except OSError:
                        pass
                count += 1
        return count

    def ready(self, signature):
        if self.lifetime is not None and not self.lifetime.alive():
            raise ConnectionError('Requested compositor exited before worker readiness')
        self._generation(signature)
        name = 'actions-' + self.token + '.ready.json'
        data = json.dumps({'token': self.token, 'signature': signature, 'pid': os.getpid(), 'uid': os.getuid()}).encode()
        self._publish(name, data)
        self._publish('ready-' + self.token, b'ready\n')

    def _generation(self, signature):
        if type(signature) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', signature):
            raise ValueError('Bounded compositor signature required')
        name = 'actions-' + self.token + '.generation.json'
        minimum = 0  # Initial scale/input can be queued before the first worker is ready.
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=self.fd)
        except FileNotFoundError:
            pass
        else:
            with os.fdopen(fd, 'rb') as source:
                self._regular(source.fileno(), 1024)
                previous = json.loads(source.read(1025))
            if (type(previous) is not dict or set(previous) != {'signature', 'minimum_ns'}
                    or type(previous['signature']) is not str
                    or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', previous['signature'])
                    or type(previous['minimum_ns']) is not int
                    or not 0 <= previous['minimum_ns'] <= self.started_ns):
                raise ValueError('Existing compositor generation differs; data preserved')
            minimum = previous['minimum_ns'] if previous['signature'] == signature else self.started_ns
        self._publish(name, json.dumps({'signature': signature, 'minimum_ns': minimum}).encode(), transient=False)
        self.minimum_ns = minimum

    def _publish(self, name, data, transient=True):
        temporary = name + '.' + os.urandom(8).hex() + '.new'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=self.fd)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(data)
            os.rename(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
            info = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            if transient:
                self.published[name] = (info.st_dev, info.st_ino)
        finally:
            try:
                os.unlink(temporary, dir_fd=self.fd)
            except FileNotFoundError:
                pass

    def watch(self):
        libc = ctypes.CDLL(None, use_errno=True)
        libc.inotify_init1.argtypes, libc.inotify_init1.restype = [ctypes.c_int], ctypes.c_int
        libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        libc.inotify_add_watch.restype = ctypes.c_int
        notify = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if notify < 0:
            raise OSError(ctypes.get_errno(), 'inotify initialization failed')
        clipboard, retry_at, lifetime = None, 0, None
        try:
            lifetime = self.lifetime or CompositorLifetime(self.compositor.path)
            if libc.inotify_add_watch(notify, os.fsencode(self.directory), 0x8 | 0x80) < 0:
                raise OSError(ctypes.get_errno(), 'inotify action watch failed')
            while lifetime.alive():
                while self.consume(lifetime) == 128:
                    if not lifetime.alive(): return
                if not lifetime.alive(): return
                try:
                    if clipboard is None and time.monotonic() >= retry_at:
                        clipboard = Relay(self.directory, self.token)
                    if clipboard is not None:
                        clipboard.poll()
                except ValueError as error:
                    self._error(error)  # Invalid clipboard data cannot stop keyboard jobs.
                except OSError as error:
                    if not lifetime.alive(.05): return
                    self._error(error)
                    if clipboard is not None: clipboard.close()
                    clipboard, retry_at = None, time.monotonic() + 3
                reads = [notify, lifetime.socket] + (clipboard.readers if clipboard is not None else [])
                writes = clipboard.writers if clipboard is not None else []
                if notify in select.select(reads, writes, [], 1)[0]:
                    try:
                        os.read(notify, 65536)
                    except BlockingIOError:
                        pass
        finally:
            if clipboard is not None: clipboard.close()
            if lifetime is not None:
                lifetime.close()
                if self.lifetime is lifetime: self.lifetime = None
            os.close(notify)

    def close(self):
        if self.lifetime is not None:
            self.lifetime.close(); self.lifetime = None
        if self.display is not None:
            self.display.close(); self.display = None
        if self.fd is not None:
            for name, identity in self.published.items():
                try:
                    current = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) == identity:
                        os.unlink(name, dir_fd=self.fd)
                except FileNotFoundError:
                    pass
            self.published.clear()
        for name in ('lock', 'fd'):
            fd = getattr(self, name, None)
            if fd is not None:
                os.close(fd); setattr(self, name, None)

    def __enter__(self):
        return self

    def __exit__(self, *ignored):
        self.close()


def main():
    runtime = os.environ.get('XDG_RUNTIME_DIR', '')
    signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')
    if not re.fullmatch(r'/run/loopy(?:/o[0-9a-f]{8})?', runtime):
        raise ValueError('Owned session runtime directory required')
    if not re.fullmatch(r'[0-9a-f]{7,64}_[0-9]{1,20}_[0-9]{1,20}', signature):
        raise ValueError('Original compositor instance required')
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    client = Hyprland(Path(runtime) / 'hypr' / signature / '.socket.sock')
    try:
        with Worker(Path('/run/loopy'), os.environ.get('LOOPY_SESSION'), client, signature=signature) as worker:
            client.query('activeworkspace')
            worker.display = configure_input(Path(runtime), worker.token, os.environ.get('WAYLAND_DISPLAY'))
            worker.ready(signature)
            worker.watch()
    except BlockingIOError:
        return # An original-config reload may ask for the same worker again.
    except KeyboardInterrupt:
        return


if __name__ == '__main__':
    main()
