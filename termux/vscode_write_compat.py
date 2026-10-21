"""Build one pinned Code shared-process compatibility candidate; never install it.

Android PRoot may reject a zero-byte write backed by a zero-length allocation
with EFAULT. A one-byte backing allocation with the original zero write count
retains the real kernel call, including descriptor/access errors.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

BEFORE_SHA256 = 'ae097590baddecb463094d667dfc8851b2a3238e20af6527b4c341810b6978c6'
BEFORE_BYTES = 1458231
METHOD = (b'async doWrite(e,t,r,o,s){let a=this.normalizePos(e,t),l=null;try{'
          b'l=(await Se.write(e,r,o,s,a)).bytesWritten}catch(c){throw await '
          b'this.toFileSystemProviderWriteError(this.writeHandles.get(e),c)}'
          b'finally{this.updatePos(e,a,l)}return l}')
GUARD = b'if(r.byteLength===0&&o===0&&s===0)r=new Uint8Array(1);'
PATCHED_METHOD = METHOD.replace(b'try{', b'try{' + GUARD, 1)
FIXTURE = Path(__file__).resolve().parents[1] / 'tests/fixtures/vscode_write_compat_regression.cjs'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch_bytes(source):
    """Only the independently captured release and one unique method qualify."""
    if not isinstance(source, bytes) or len(source) != BEFORE_BYTES or sha(source) != BEFORE_SHA256:
        raise ValueError('unsupported shared-process source')
    if source.count(METHOD) != 1 or GUARD in source:
        raise ValueError('unsupported shared-process method')
    return source.replace(METHOD, PATCHED_METHOD, 1)


def read_regular(path, maximum):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum:
            raise ValueError('source must be a bounded regular file')
        data = bytearray()
        while len(data) <= maximum:
            block = os.read(fd, min(65536, maximum + 1 - len(data)))
            if not block:
                break
            data.extend(block)
        after = os.fstat(fd)
        identity = lambda row: (row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns, row.st_ctime_ns)
        if identity(before) != identity(after) or len(data) != before.st_size:
            raise ValueError('source changed while reading')
        return bytes(data)
    finally:
        os.close(fd)


def build(source, output):
    """Create exclusive host artifacts after source validation, preserving input."""
    try:
        before = read_regular(source, BEFORE_BYTES)
    except OSError as error:
        raise ValueError('source is unavailable or is a symlink') from error
    after = patch_bytes(before)
    fixture = read_regular(FIXTURE, 16384)
    row = dict(schema=1, phase='CANDIDATE', installed=False, beforeSha256=sha(before),
               afterSha256=sha(after), beforeBytes=len(before), afterBytes=len(after),
               changedMethods=1, writeCountPreserved=True, writesMocked=False,
               regressionSha256=sha(fixture), scope='Code shared-process file provider doWrite')
    os.mkdir(output, 0o700)
    directory = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for name, data in [('sharedProcessMain.js', after), ('regression.cjs', fixture),
                           ('manifest.json', (json.dumps(row, indent=2) + '\n').encode())]:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=directory)
            try:
                remaining = memoryview(data)
                while remaining:
                    written = os.write(fd, remaining)
                    if written <= 0:
                        raise OSError('artifact write did not advance')
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
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output)))
