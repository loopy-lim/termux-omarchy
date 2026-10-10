"""Verify the private PRoot lifetime guard before selecting it for a guest."""
import hashlib
import json
import os
from pathlib import Path
import stat

FILES = {
    'proot': 'bdb15a8388038e2d1211ab6dd4d35fdf0bf3d9550cd03b24031eb4ba1de8c5c2',
    'loader': '95a47c09e5401637ce034304362bd179682fba470a9dab78d8be0a56d1f0745c',
    'libandroid-shmem.so': '84475798e07c8174dbbfaec70a827fdb02f19ffa69a589380c13e7507fd0e731',
}
MODES = {'proot': 0o700, 'loader': 0o700, 'libandroid-shmem.so': 0o600}
NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC


def require(value):
    if not value:
        raise ValueError('proot-guard-integrity')


def identity(row):
    return [row.st_dev, row.st_ino, row.st_uid]


def fingerprint(row):
    return identity(row) + [row.st_mode, row.st_size, row.st_mtime_ns, row.st_ctime_ns, row.st_nlink]


def directory(path, parent=None):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=parent)
    try:
        row = os.fstat(fd)
        require(row.st_uid == os.getuid() and stat.S_IMODE(row.st_mode) == 0o700)
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_file(parent, name, mode, maximum):
    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW, dir_fd=parent)
    with os.fdopen(fd, 'rb') as source:
        before = os.fstat(source.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == mode
                and before.st_size <= maximum)
        data = source.read(maximum + 1)
        require(len(data) == before.st_size and fingerprint(os.fstat(source.fileno())) == fingerprint(before))
        require(fingerprint(os.stat(name, dir_fd=parent, follow_symlinks=False)) == fingerprint(before))
        return data


def inventory(fd):
    require(set(os.listdir(fd)) == set(FILES))
    for name, expected in FILES.items():
        data = read_file(fd, name, MODES[name], 1024 * 1024)
        require(hashlib.sha256(data).hexdigest() == expected)
    return identity(os.fstat(fd))


def selection(root):
    """Old installations remain explicit legacy; a partial guard never falls back."""
    root = Path(root)
    fd, child = None, None
    try:
        fd = directory(root)
        entries = set(os.listdir(fd))
        if not {'proot-guard', 'proot-guard.json'}.intersection(entries):
            return None
        record = json.loads(read_file(fd, 'proot-guard.json', 0o600, 16384))
        require(isinstance(record, dict))
        require(record == dict(schema=1, phase='INSTALLED', uid=os.getuid(),
                               root=identity(os.fstat(fd)), directory=record.get('directory'), files=FILES))
        child = directory('proot-guard', fd)
        require(inventory(child) == record['directory'])
        require(identity(os.stat('proot-guard', dir_fd=fd, follow_symlinks=False)) == record['directory'])
        require(identity(root.lstat()) == record['root'])
        return root / 'proot-guard'
    except (OSError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise ValueError('proot-guard-integrity') from error
    finally:
        if child is not None:
            os.close(child)
        if fd is not None:
            os.close(fd)
