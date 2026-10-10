"""Verify a closed set of locally prepared distribution assets without installation."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC
MAXIMUM = 2 * 1024 * 1024 * 1024


def require(value, reason):
    if not value:
        raise ValueError(reason)


def relative(name):
    require(isinstance(name, str) and 0 < len(name) <= 256, 'delivery-path')
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and str(path) == name
            and all(p not in ('', '.', '..') for p in path.parts), 'delivery-path')
    return path


def validate_entries(entries):
    require(isinstance(entries, dict) and 1 <= len(entries) <= 128, 'delivery-manifest')
    for name, row in entries.items():
        relative(name)
        require(isinstance(row, dict) and set(row) == {'bytes', 'sha256'}
                and type(row['bytes']) is int and 1 <= row['bytes'] <= MAXIMUM
                and isinstance(row['sha256'], str)
                and re.fullmatch('[a-f0-9]{64}', row['sha256']), 'delivery-manifest')
    parents = {str(p) for name in entries for p in relative(name).parents if str(p) != '.'}
    require(not parents.intersection(entries), 'delivery-path')
    return parents


def catalog(root):
    from verify import read
    row = json.loads(read(root, 'manifests/distribution.json'))
    require(set(row) == {'schema', 'status', 'files', 'fullFreshInstallVerified'}
            and row['schema'] == 1 and row['fullFreshInstallVerified'] is False
            and row['status'] == 'build-closure-prepared', 'delivery-closure-unavailable')
    validate_entries(row['files'])
    return row['files']


def fingerprint(row):
    return (row.st_dev, row.st_ino, row.st_uid, row.st_mode, row.st_nlink,
            row.st_size, row.st_mtime_ns, row.st_ctime_ns)


def check_stream(source, expected, *, owned=True, platform_links=False):
    before = os.fstat(source.fileno())
    require(not platform_links or not owned, 'delivery-file-boundary')
    require(stat.S_ISREG(before.st_mode)
            and (1 <= before.st_nlink <= 16 if platform_links else before.st_nlink == 1)
            and (not owned or before.st_uid == os.getuid())
            and not before.st_mode & 0o022 and before.st_size == expected['bytes'],
            'delivery-file-boundary')
    digest, length = hashlib.sha256(), 0
    while data := source.read(1024 * 1024):
        length += len(data)
        require(length <= expected['bytes'], 'delivery-file-size')
        digest.update(data)
    require(length == expected['bytes'] and digest.hexdigest() == expected['sha256'],
            'delivery-file-hash')
    require(fingerprint(os.fstat(source.fileno())) == fingerprint(before), 'delivery-file-changed')
    return fingerprint(before)


def verify_file(path, expected, *, owned=True, platform_links=False):
    validate_entries({'file': expected})
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW), 'rb') as source:
        before = check_stream(source, expected, owned=owned, platform_links=platform_links)
        require(fingerprint(os.stat(path, follow_symlinks=False)) == before, 'delivery-file-changed')


def verify_tree(directory, entries):
    parents = validate_entries(entries)
    root = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    seen = set()
    try:
        def visit(fd, parent=''):
            row = os.fstat(fd)
            require(row.st_uid == os.getuid() and not row.st_mode & 0o022, 'delivery-directory-boundary')
            for leaf in os.listdir(fd):
                name = parent + leaf
                require(name in entries or name in parents, 'delivery-members')
                if name in parents:
                    child = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=fd)
                    try:
                        visit(child, name + '/')
                    finally:
                        os.close(child)
                else:
                    source = os.open(leaf, os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW, dir_fd=fd)
                    with os.fdopen(source, 'rb') as stream:
                        before = check_stream(stream, entries[name])
                        require(fingerprint(os.stat(leaf, dir_fd=fd, follow_symlinks=False)) == before,
                                'delivery-file-changed')
                seen.add(name)
        visit(root)
        require(seen == set(entries) | parents, 'delivery-members')
        require(fingerprint(os.stat(directory, follow_symlinks=False))[:3]
                == fingerprint(os.fstat(root))[:3], 'delivery-directory-changed')
        return len(entries)
    finally:
        os.close(root)
