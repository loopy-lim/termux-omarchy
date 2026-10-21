"""Build a pinned, helper-only .NET heap compatibility candidate; never install it.

The official signature verifier remains byte-identical. Its launcher constrains
only that child process's GC heap, retaining all package and certificate checks.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

ORIGINAL_SHA256 = '62dbbc4da520c1b2923a862487e68714542f364bd600ea3a3049e9bd3ab59c5d'
ORIGINAL_BYTES = 16409133
BACKUP_NAME = 'vsce-sign.loopy-original-62dbbc4da520c1b2'
ORIGINAL_GUEST_PATH = ('/opt/loopy-vscode/1.141.0/resources/app/'
                       'node_modules.asar.unpacked/@vscode/vsce-sign/bin/' + BACKUP_NAME)


def wrapper_bytes():
    return ('#!/bin/sh\n'
            '# Pinned official verifier; only this process receives the GC cap.\n'
            'export DOTNET_GCHeapHardLimit=0x10000000\n'
            'exec ' + ORIGINAL_GUEST_PATH + ' "$@"\n').encode('ascii')


def read_original(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as error:
        raise ValueError('original verifier is unavailable or a symlink') from error
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_size != ORIGINAL_BYTES):
            raise ValueError('unsupported signature verifier')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            data = stream.read(ORIGINAL_BYTES + 1)
        after = os.fstat(fd)
        fingerprint = lambda row: (row.st_dev, row.st_ino, row.st_size,
                                   row.st_mtime_ns, row.st_ctime_ns)
        if (fingerprint(before) != fingerprint(after)
                or hashlib.sha256(data).hexdigest() != ORIGINAL_SHA256):
            raise ValueError('unsupported or changing signature verifier')
        return data
    finally:
        os.close(fd)


def build(source, output):
    original = read_original(source)
    wrapper = wrapper_bytes()
    row = dict(schema=1, phase='CANDIDATE', installed=False,
               originalSHA256=ORIGINAL_SHA256, originalBytes=len(original),
               wrapperSHA256=hashlib.sha256(wrapper).hexdigest(),
               wrapperBytes=len(wrapper), backupName=BACKUP_NAME,
               originalGuestPath=ORIGINAL_GUEST_PATH,
               signatureVerificationBypassed=False, originalModuleChanged=False,
               childEnvironment={'DOTNET_GCHeapHardLimit': '0x10000000'})
    os.mkdir(output, 0o700)
    directory = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for name, data, mode in [('vsce-sign', wrapper, 0o755),
                                 (BACKUP_NAME, original, 0o755),
                                 ('manifest.json', (json.dumps(row, indent=2) + '\n').encode(), 0o600)]:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         mode, dir_fd=directory)
            try:
                remaining = memoryview(data)
                while remaining:
                    written = os.write(fd, remaining)
                    if written <= 0:
                        raise OSError('candidate write did not advance')
                    remaining = remaining[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
        os.fsync(directory)
    finally:
        os.close(directory)
    return row


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output)))
