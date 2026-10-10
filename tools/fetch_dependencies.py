#!/usr/bin/env python3
"""Fetch pinned upstream files; never install, unpack or run downloaded content."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'manifests/downloads.json'
NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC
ARCH_HOST = 'ca.us.mirror.archlinuxarm.org'
HOSTS = {'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com', ARCH_HOST}


def require(value, code):
    if not value:
        raise ValueError(code)


def allowed_url(url):
    parts = urlsplit(url)
    require(parts.scheme == 'https' and parts.hostname in HOSTS and
            parts.username is None and parts.password is None and
            parts.port in (None, 443) and not parts.fragment, 'download-url')
    return parts


class PinnedRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, url):
        allowed_url(url)
        return super().redirect_request(request, fp, code, msg, headers, url)


def open_response(url):
    allowed_url(url)
    request = Request(url, headers={'User-Agent': 'termux-omarchy-source-preparation',
                                    'Accept-Encoding': 'identity'})
    return build_opener(PinnedRedirect()).open(request, timeout=60)


def catalog(path=CATALOG):
    path = Path(path)
    require(not path.is_symlink() and path.is_file() and path.stat().st_size <= 65536,
            'download-catalog')
    data = json.loads(path.read_text())
    require(set(data) == {'schema', 'artifacts'} and type(data['schema']) is int
            and data['schema'] == 1 and isinstance(data['artifacts'], dict)
            and 1 <= len(data['artifacts']) <= 128, 'download-catalog')
    fields = {'file', 'url', 'bytes', 'sha256', 'purpose', 'licenseNote'}
    filenames = set()
    for name, row in data['artifacts'].items():
        require(re.fullmatch('[a-z][a-z0-9-]{0,63}', name) and isinstance(row, dict)
                and set(row) == fields, 'download-catalog')
        require(isinstance(row['file'], str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9._+:-]{0,150}', row['file'])
                and row['file'] not in filenames, 'download-catalog')
        filenames.add(row['file'])
        require(type(row['bytes']) is int and 0 < row['bytes'] <= 2 * 1024**3
                and isinstance(row['sha256'], str) and re.fullmatch('[a-f0-9]{64}', row['sha256']),
                'download-catalog')
        require(all(isinstance(row[key], str) and 0 < len(row[key]) <= 1024
                    for key in ('url', 'purpose', 'licenseNote')), 'download-catalog')
        try:
            parts = allowed_url(row['url'])
        except (ValueError, TypeError):
            raise ValueError('download-catalog') from None
        github_release = (parts.hostname == 'github.com'
                          and re.fullmatch(r'/[^/]+/[^/]+/releases/download/[^/]+/[^/]+', parts.path)
                          and '/latest/' not in parts.path)
        arch_package = (parts.hostname == ARCH_HOST
                        and re.fullmatch(r'/aarch64/(?:core|extra)/[A-Za-z0-9][A-Za-z0-9._+:-]*[.]pkg[.]tar[.]xz(?:[.]sig)?', parts.path))
        require(not parts.query and (github_release or arch_package), 'download-catalog')
    return data['artifacts']


def fingerprint(row):
    return (row.st_dev, row.st_ino, row.st_mode, row.st_uid, row.st_nlink,
            row.st_size, row.st_mtime_ns, row.st_ctime_ns)


def existing(directory_fd, row):
    try:
        fd = os.open(row['file'], os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW, dir_fd=directory_fd)
    except FileNotFoundError:
        return False
    with os.fdopen(fd, 'rb') as source:
        before = os.fstat(source.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and before.st_nlink == 1 and not before.st_mode & 0o022,
                'download-existing-filesystem')
        require(before.st_size == row['bytes'], 'download-existing-mismatch')
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
        require(digest == row['sha256'], 'download-existing-mismatch')
        after = os.stat(row['file'], dir_fd=directory_fd, follow_symlinks=False)
        require(fingerprint(before) == fingerprint(os.fstat(source.fileno())) == fingerprint(after),
                'download-existing-changed')
    return True


def publish(fd, source, target):
    """Atomic no-replace publication, including native Termux Python without link."""
    if callable(getattr(os, 'link', None)):
        os.link(source, target, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(fd, os.fsencode(source), fd, os.fsencode(target), 1):
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number), target)


def acquire(directory, row):
    directory = Path(directory).absolute()
    require(directory.resolve(strict=True) == directory, 'download-directory')
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    temporary = None
    try:
        before = os.fstat(fd)
        require(before.st_uid == os.getuid() and not before.st_mode & 0o022, 'download-directory')
        if existing(fd, row):
            return {'status': 'cached', 'file': row['file'], 'sha256': row['sha256'], 'bytes': row['bytes']}
        file_fd, temporary_path = tempfile.mkstemp(prefix='.download-', dir=directory)
        temporary = Path(temporary_path).name
        count, digest = 0, hashlib.sha256()
        with os.fdopen(file_fd, 'wb') as output:
            with open_response(row['url']) as source:
                allowed_url(source.geturl())
                while True:
                    block = source.read(min(1024 * 1024, row['bytes'] + 1 - count))
                    if not block:
                        break
                    count += len(block)
                    require(count <= row['bytes'], 'download-integrity')
                    digest.update(block)
                    output.write(block)
            require(count == row['bytes'] and digest.hexdigest() == row['sha256'], 'download-integrity')
            output.flush()
            os.fsync(output.fileno())
        current = directory.stat(follow_symlinks=False)
        require((before.st_dev, before.st_ino, before.st_uid, before.st_mode) ==
                (current.st_dev, current.st_ino, current.st_uid, current.st_mode), 'download-directory-changed')
        publish(fd, temporary, row['file'])
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:  # renameat2 moved the temporary entry.
            pass
        temporary = None
        os.fsync(fd)
        require(existing(fd, row), 'download-publish')
        return {'status': 'downloaded', 'file': row['file'], 'sha256': row['sha256'], 'bytes': count}
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=fd)
            except FileNotFoundError:
                pass
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--check', action='store_true', help='inspect pins without network or writes')
    operation.add_argument('--fetch', metavar='ARTIFACT', help='download one catalog ID')
    parser.add_argument('--directory', type=Path, help='existing owned output directory')
    args = parser.parse_args(argv)
    try:
        artifacts = catalog()
        if args.check:
            result = {'schema': 1, 'status': 'catalog-verified', 'artifacts': artifacts,
                      'installationRequested': False}
        else:
            require(args.fetch in artifacts and args.directory is not None, 'download-arguments')
            result = acquire(args.directory, artifacts[args.fetch])
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, HTTPException, ValueError, TypeError, KeyError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('download-[a-z-]+', str(error)) else 'download-unavailable'
        print(json.dumps({'schema': 1, 'status': 'failed', 'reason': reason}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
