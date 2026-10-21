"""Actual child logging for Android, where the original systemd journal is unavailable.

Preserves the original Omarchy shell supervisor and its real child status.
This is a file transport, not a systemd/journal implementation.
"""
import fcntl
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time


class BoundedLog:
    def __init__(self, directory, limit):
        if type(limit) is not int or not 4096 <= limit <= 1048576:
            raise ValueError('Bounded shell log size required')
        self.limit, self.fd, self.lock, self.directory = limit, None, None, None
        directory = Path(directory)
        try:
            directory.mkdir(mode=0o700, exist_ok=True)
            self.directory = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            if os.fstat(self.directory).st_uid != os.getuid():
                raise ValueError('Owned shell log directory required')
            self.lock = self.open_regular('omarchy-shell.log.lock')
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd = self.open_regular('omarchy-shell.log')
            self.size = os.fstat(self.fd).st_size
            if self.size > self.limit:
                raise ValueError('Existing shell log exceeds its size budget')
        except BaseException:
            self.close(); raise

    def open_regular(self, name):
        fd = os.open(name, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     0o600, dir_fd=self.directory)
        item = os.fstat(fd)
        if not stat.S_ISREG(item.st_mode) or item.st_uid != os.getuid():
            os.close(fd); raise ValueError('Owned regular shell log required')
        return fd

    def rotate(self):
        for name in ('omarchy-shell.log.1', 'omarchy-shell.log.2'):
            try: item = os.stat(name, dir_fd=self.directory, follow_symlinks=False)
            except FileNotFoundError: continue
            if not stat.S_ISREG(item.st_mode) or item.st_uid != os.getuid() or item.st_size > self.limit:
                raise ValueError('Existing shell log rotation is not owned regular data')
        os.close(self.fd); self.fd = None
        try: os.replace('omarchy-shell.log.1', 'omarchy-shell.log.2', src_dir_fd=self.directory, dst_dir_fd=self.directory)
        except FileNotFoundError: pass
        os.replace('omarchy-shell.log', 'omarchy-shell.log.1', src_dir_fd=self.directory, dst_dir_fd=self.directory)
        self.fd = self.open_regular('omarchy-shell.log'); self.size = 0

    def write(self, data):
        data = memoryview(data)
        while data:
            if self.size == self.limit: self.rotate()
            chunk = data[:self.limit-self.size]
            written = os.write(self.fd, chunk)
            if written <= 0: raise OSError('Shell log made no write progress')
            self.size += written; data = data[written:]

    def close(self):
        for name in ('fd', 'lock', 'directory'):
            value = getattr(self, name, None)
            if value is not None:
                os.close(value); setattr(self, name, None)


def supervise(argv, directory, limit=1048576):
    log = BoundedLog(directory, limit)
    child = None; previous = {}; stopped = None
    events = selectors.DefaultSelector()
    def forward(signum, frame):
        nonlocal stopped
        stopped = stopped or time.monotonic()
        if child is not None and child.poll() is None: child.send_signal(signum)
    try:
        for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, forward)
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        os.set_blocking(child.stdout.fileno(), False)
        events.register(child.stdout, selectors.EVENT_READ)
        exited = None
        while True:
            now = time.monotonic()
            if stopped is not None and child.poll() is None and now-stopped >= 2: child.kill()
            if child.poll() is not None:
                exited = exited or now
                if not events.get_map() or now-exited >= .5: break
            for event, mask in events.select(.05):
                try: data = os.read(event.fileobj.fileno(), 65536)
                except BlockingIOError: continue
                if data: log.write(data)
                else: events.unregister(event.fileobj)
        status = child.wait(timeout=2)
        return status if status >= 0 else 128-status
    finally:
        if child is not None:
            if child.poll() is None:
                child.kill(); child.wait(timeout=2)
            child.stdout.close()
        events.close(); log.close()
        for signum, handler in previous.items(): signal.signal(signum, handler)


def main():
    directory = os.environ.get('LOOPY_OMARCHY_LOG_DIR', '')
    if not re.fullmatch(r'/run/loopy/o[0-9a-f]{8}/logs', directory):
        raise ValueError('Owned Omarchy session log path required')
    if sys.argv[1:] != ['--', 'quickshell', '-n', '-p', '/usr/share/omarchy/shell']:
        raise ValueError('Only the pinned original shell launch is accepted')
    return supervise(sys.argv[2:], directory)


if __name__ == '__main__': raise SystemExit(main())
