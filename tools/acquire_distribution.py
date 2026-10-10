#!/usr/bin/env python3
"""Acquire a complete pinned delivery tree without building or installing it."""
import argparse
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'installer'))
import assets
import verify
import fetch_dependencies as fetch

LOCAL = {'tools/tools-manifest.json': 'manifests/packages/tools-manifest.json',
         'korean-input/ime-manifest.json': 'manifests/packages/ime-manifest.json'}


def plan(root=ROOT):
    """Validate every source and byte-identity mapping before output creation."""
    root = Path(root)
    verify.validate(root)
    entries = assets.catalog(root)
    downloads = fetch.catalog(root / 'manifests/downloads.json')
    assets.require(set(LOCAL) <= set(entries), 'delivery-local-manifests-missing')
    identities = {}
    for row in downloads.values():
        identities.setdefault((row['bytes'], row['sha256']), []).append(row)
    mapped, local = {}, {}
    for name, expected in sorted(entries.items()):
        if name in LOCAL:
            data = verify.read(root, LOCAL[name])
            assets.require(len(data) == expected['bytes'] and
                           hashlib.sha256(data).hexdigest() == expected['sha256'],
                           'delivery-local-manifest-hash')
            local[name] = data
        else:
            matches = identities.get((expected['bytes'], expected['sha256']), [])
            basename = PurePosixPath(name).name
            assets.require(len(matches) == 1 and
                           re.fullmatch('[A-Za-z0-9][A-Za-z0-9._+:-]{0,150}', basename),
                           'delivery-download-map')
            mapped[name] = dict(matches[0], file=basename)
    return entries, mapped, local


def directory(root, parts):
    fd = os.dup(root)
    try:
        for part in parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | assets.NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        row = os.fstat(fd)
        assets.require(row.st_uid == os.getuid() and not row.st_mode & 0o022,
                       'delivery-directory-boundary')
        return fd
    except BaseException:
        os.close(fd)
        raise


def new_output(output):
    output = Path(output).absolute()
    assets.require(output.name and output.parent.resolve(strict=True) == output.parent,
                   'delivery-output-parent')
    parent = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | assets.NOFOLLOW)
    try:
        row = os.fstat(parent)
        assets.require(row.st_uid == os.getuid() and not row.st_mode & 0o022,
                       'delivery-output-parent')
        os.mkdir(output.name, 0o700, dir_fd=parent)
        os.fsync(parent)
        root = os.open(output.name, os.O_RDONLY | os.O_DIRECTORY | assets.NOFOLLOW, dir_fd=parent)
    finally:
        os.close(parent)
    return output, root


def check_output(output, root):
    current = os.stat(output, follow_symlinks=False)
    opened = os.fstat(root)
    assets.require(stat.S_ISDIR(current.st_mode) and
                   (current.st_dev, current.st_ino, current.st_uid, current.st_mode) ==
                   (opened.st_dev, opened.st_ino, opened.st_uid, opened.st_mode),
                   'delivery-output-changed')


def acquire(root, output, *, progress=None):
    entries, downloads, local = plan(root)
    parents = assets.validate_entries(entries)
    output, fd = new_output(output)
    try:
        for name in sorted(parents, key=lambda value: (value.count('/'), value)):
            path = PurePosixPath(name)
            parent = directory(fd, path.parts[:-1])
            try:
                os.mkdir(path.name, 0o700, dir_fd=parent)
                os.fsync(parent)
            finally:
                os.close(parent)
        # Keep failed attempts; a subsequent invocation must choose a new root.
        for index, name in enumerate(sorted(entries), 1):
            check_output(output, fd)
            if progress is not None:
                progress(index, len(entries), name)
            path = PurePosixPath(name)
            if name in downloads:
                fetch.acquire(output.joinpath(*path.parts[:-1]), downloads[name])
            else:
                parent = directory(fd, path.parts[:-1])
                try:
                    target = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | assets.NOFOLLOW,
                                     0o600, dir_fd=parent)
                    with os.fdopen(target, 'wb') as destination:
                        destination.write(local[name])
                        destination.flush()
                        os.fsync(destination.fileno())
                    os.fsync(parent)
                finally:
                    os.close(parent)
        check_output(output, fd)
        return assets.verify_tree(output, entries)
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--plan', action='store_true', help='validate sources and maps without network or writes')
    operation.add_argument('--output', type=Path, metavar='NEW_DIRECTORY', help='acquire the closed asset set')
    args = parser.parse_args(argv)
    try:
        result = {'schema': 1, 'deviceChangesRequested': False,
                  'installationRequested': False, 'fullFreshInstallVerified': False}
        if args.plan:
            entries, downloads, local = plan(ROOT)
            result.update(status='delivery-acquisition-plan', filesRequired=len(entries),
                          downloadsRequired=len(downloads),
                          downloadURLs={name: row['url'] for name, row in downloads.items()},
                          localFiles={name: LOCAL[name] for name in local})
        else:
            def progress(index, total, name):
                print(f'Preparing asset {index}/{total}: {name}', file=sys.stderr, flush=True)
            result.update(status='installation-assets-acquired',
                          filesVerified=acquire(ROOT, args.output, progress=progress))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, HTTPException, ValueError, KeyError, TypeError, SyntaxError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch(
            r'(?:source|delivery|download)-[a-z-]+', str(error)) else 'delivery-unavailable'
        if isinstance(error, FileExistsError):
            reason = 'delivery-output-exists'
        print(json.dumps({'schema': 1, 'status': 'failed', 'reason': reason,
                          'installationRequested': False, 'deviceChangesRequested': False,
                          'fullFreshInstallVerified': False}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
