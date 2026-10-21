"""Remember successful first-run notices without marking system setup complete."""
import fcntl
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

DELIVERED = b'notifier-exited-successfully-v1\n'
NAMES = {'welcome', 'wifi', 'update'}


def _directory(home):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(home, flags)
    try:
        for part in ('.local', 'state', 'loopy', 'omarchy-first-run-notices'):
            if os.fstat(fd).st_uid != os.getuid():
                raise ValueError('Owned notice state required')
            try: os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError: pass
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd); fd = child
        if os.fstat(fd).st_uid != os.getuid():
            raise ValueError('Owned notice state required')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _regular(fd, limit):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > limit or info.st_nlink != 1:
        raise ValueError('Bounded owned notice record required')


def deliver(home, name, command):
    if name not in NAMES:
        raise ValueError('Known first-run notice required')
    directory = _directory(home)
    lock = None
    try:
        lock = os.open(name + '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                       0o600, dir_fd=directory)
        _regular(lock, 0)
        fcntl.flock(lock, fcntl.LOCK_EX)
        marker = name + '.done'
        try:
            fd = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         dir_fd=directory)
        except FileNotFoundError:
            pass
        else:
            with os.fdopen(fd, 'rb') as source:
                _regular(source.fileno(), len(DELIVERED))
                if source.read(len(DELIVERED) + 1) != DELIVERED:
                    raise ValueError('Existing notice record differs; preserved')
            return 0
        result = subprocess.run(command, timeout=15, check=False)
        if result.returncode != 0:
            return result.returncode
        temporary = name + '.' + os.urandom(8).hex() + '.new'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=directory)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(DELIVERED); output.flush(); os.fsync(output.fileno())
            # Publish a complete record without replacing existing data, even after a race.
            os.link(temporary, marker, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        finally:
            os.unlink(temporary, dir_fd=directory)
        return 0
    finally:
        if lock is not None: os.close(lock)
        os.close(directory)


def main():
    if len(sys.argv) < 3 or not re.fullmatch(r'[A-Za-z0-9-]{1,64}', os.environ.get('LOOPY_SESSION', '')):
        raise ValueError('Current Android Omarchy session required')
    return deliver(Path(os.environ['HOME']), sys.argv[1],
                   ['/usr/share/omarchy/bin/omarchy-notification-send', *sys.argv[2:]])


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print('First-run notice was not recorded: ' + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
