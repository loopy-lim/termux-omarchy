#!/usr/bin/env python3
"""Rebuild private Android futex libxshmfence and a bounded interop probe."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

SHA256 = 'd4a4df096aba96fea02c029ee3a44e11a47eb7f7213c1a729be83e85ec3fde10'
VERSION = 'libxshmfence-1.3.3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--cc', type=Path, required=True,
                        help='NDK r27 toolchain/bin/aarch64-linux-android29-clang')
    parser.add_argument('--include', type=Path, required=True,
                        help='Termux sysroot/include containing X11/xshmfence.h')
    parser.add_argument('--out', type=Path, required=True, help='new output directory')
    args = parser.parse_args()
    archive, cc, include, out = (p.absolute() for p in (args.archive, args.cc, args.include, args.out))
    if sha(archive) != SHA256: parser.error('official source SHA256 mismatch')
    if not cc.is_file() or not os.access(cc, os.X_OK): parser.error('compiler unavailable')
    if not (include / 'X11/xshmfence.h').is_file(): parser.error('xshmfence development header missing')
    if out.exists() or out.is_symlink(): parser.error('output must not exist; refusing overwrite')
    out.mkdir(mode=0o700, parents=True)
    with tarfile.open(archive, 'r:xz') as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts
            if not parts or parts[0] != VERSION or '..' in parts or member.name.startswith('/') \
                    or not (member.isfile() or member.isdir()):
                raise ValueError('unsafe source archive member')
        tar.extractall(out, filter='data')
    compat = out / 'compat'; compat.mkdir()
    (compat / 'values.h').write_text('#include <limits.h>\n#ifndef MAXINT\n#define MAXINT INT_MAX\n#endif\n')
    source = out / VERSION / 'src'
    library = out / 'libxshmfence.so'
    common = [str(cc), '-O2', '-fPIC', '-D_GNU_SOURCE', '-DHAVE_FUTEX=1',
              '-DHAVE_DECL___NR_MEMFD_CREATE=1', '-DHAVE_MKOSTEMP=1',
              '-DSHMDIR="/data/data/com.termux/files/usr/tmp"',
              '-I' + str(compat), '-I' + str(include)]
    command = common + ['-shared', '-Wl,-soname,libxshmfence.so',
                        str(source / 'xshmfence_futex.c'), str(source / 'xshmfence_alloc.c'), '-o', str(library)]
    subprocess.run(command, check=True)
    probe_source = Path(__file__).resolve().with_name('interop.c')
    probe = out / 'xshmfence-interop'
    probe_command = [str(cc), '-O2', '-Wall', '-Wextra', str(probe_source), '-ldl', '-o', str(probe)]
    subprocess.run(probe_command, check=True)
    compiler = subprocess.check_output([str(cc), '--version'], text=True)
    receipt = {'sourceUrl': 'https://www.x.org/releases/individual/lib/' + VERSION + '.tar.xz',
               'sourceSHA256': SHA256, 'compiler': compiler, 'libraryCommand': command,
               'probeCommand': probe_command, 'librarySHA256': sha(library),
               'probeSourceSHA256': sha(probe_source), 'probeSHA256': sha(probe),
               'scope': 'private native browser only; do not replace system library',
               'deviceTested': False}
    (out / 'build.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'library': str(library), 'sha256': receipt['librarySHA256'],
                      'probe': str(probe), 'deviceTested': False}))


if __name__ == '__main__': main()
