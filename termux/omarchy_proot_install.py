"""Install a pinned, private PRoot guard without changing global Termux tools."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

import omarchy_guest_install as adapters
import omarchy_host_install as host
import omarchy_install as base
import omarchy_proot as guard

JOURNAL = 'proot-guard.json'
STAGE_PREFIX = '.proot-guard-stage-'


def source_files(directory):
    """Read every pinned byte before opening or locking managed installation state."""
    directory = Path(directory)
    fd = base.directory(directory)
    try:
        before = base.identity(os.fstat(fd))
        base.require(set(os.listdir(fd)) == set(guard.FILES), 'proot-source-members')
        result = {}
        for name, expected in guard.FILES.items():
            with base.regular(name, 1024 * 1024, fd) as source:
                original = base.fingerprint(os.fstat(source.fileno()))
                data = source.read()
                base.require(hashlib.sha256(data).hexdigest() == expected, 'proot-source-sha')
                base.require(base.fingerprint(os.fstat(source.fileno())) == original
                    and base.fingerprint(os.stat(name, dir_fd=fd, follow_symlinks=False)) == original,
                    'proot-source-changed')
                result[name] = data
        base.require(set(os.listdir(fd)) == set(guard.FILES)
            and base.identity(directory.lstat()) == before, 'proot-source-changed')
        return result
    finally:
        os.close(fd)


def installed_base(root, fd, home, prefix, previous=None):
    row = base.read_journal(fd)
    base.require(isinstance(row, dict) and row.get('schema') == 1 and row.get('phase') == 'INSTALLED'
        and row.get('uid') == os.getuid() and row.get('root') == base.identity(os.fstat(fd))
        and row.get('home') == str(home) and row.get('prefix') == str(prefix)
        and row.get('container') == base.CONTAINER and row.get('bundle_sha256') == base.OUTER_SHA,
        'proot-base-identity')
    base.require(base.identity(root.lstat()) == row['root'], 'proot-root-replaced')
    base.require(previous is None or previous == row, 'proot-base-changed')
    base.check_installed(root, prefix, row)
    return row


def stopped(fd):
    try:
        source = base.regular('runtime-state.json', 16384, fd)
    except FileNotFoundError:
        return None
    with source:
        before = base.fingerprint(os.fstat(source.fileno()))
        state = json.loads(source.read())
        base.require(base.fingerprint(os.fstat(source.fileno())) == before
            and base.fingerprint(os.stat('runtime-state.json', dir_fd=fd, follow_symlinks=False)) == before,
            'proot-runtime-state-changed')
    base.require(isinstance(state, dict) and state.get('phase') == 'stopped'
        and state.get('terminationConfirmed') is True, 'proot-runtime-active')
    return state


def write_stage(fd, name, files):
    os.mkdir(name, 0o700, dir_fd=fd)
    child = guard.directory(name, fd)
    try:
        for leaf, data in files.items():
            target = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW,
                             0o600, dir_fd=child)
            with os.fdopen(target, 'wb') as output:
                output.write(data)
                output.flush()
                os.fchmod(output.fileno(), guard.MODES[leaf])
                os.fsync(output.fileno())
        os.fsync(child)
        result = guard.inventory(child)
        base.require(base.identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) == result,
                     'proot-stage-replaced')
        os.fsync(fd)
        return result
    finally:
        os.close(child)


def install(directory, home, prefix):
    files = source_files(directory)
    home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
    root = home / '.local/share/loopy-omarchy'
    fd, locks = None, []
    try:
        fd = base.walk(home, '.local/share/loopy-omarchy')
        base.require(fd is not None and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700,
                     'proot-managed-root')
        before = installed_base(root, fd, home, prefix)
        for name in ('install.lock', 'runtime-control.lock'):
            locks.append(adapters.lock(fd, name))
        installed_base(root, fd, home, prefix, before)
        runtime = stopped(fd)
        entries = set(os.listdir(fd))
        base.require(not any(name.startswith(STAGE_PREFIX) for name in entries), 'proot-install-partial')
        if {'proot-guard', JOURNAL}.intersection(entries):
            base.require(guard.selection(root) == root / 'proot-guard', 'proot-install-partial')
            return adapters.read_record(fd, JOURNAL)

        stage = STAGE_PREFIX + uuid.uuid4().hex
        folder = write_stage(fd, stage, files)
        installed_base(root, fd, home, prefix, before)
        base.require(stopped(fd) == runtime, 'proot-runtime-state-changed')
        base.require(adapters.read_record(fd, JOURNAL) is None, 'proot-journal-concurrent-change')
        host.publish_directory(fd, stage, 'proot-guard')
        child = guard.directory('proot-guard', fd)
        try:
            base.require(guard.inventory(child) == folder, 'proot-published-changed')
        finally:
            os.close(child)
        installed_base(root, fd, home, prefix, before)
        base.require(stopped(fd) == runtime, 'proot-runtime-state-changed')
        row = dict(schema=1, phase='INSTALLED', uid=os.getuid(), root=base.identity(os.fstat(fd)),
                   directory=folder, files=dict(guard.FILES))
        adapters.save_record(fd, row, journal=JOURNAL)
        base.require(guard.selection(root) == root / 'proot-guard', 'proot-published-changed')
        return row
    finally:
        # A partial stage/publication is evidence. Preserve it and refuse later adoption.
        for lock in reversed(locks):
            os.close(lock)
        if fd is not None:
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install the private Omarchy PRoot lifetime guard')
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(install(args.directory, os.environ['HOME'], os.environ['PREFIX']), sort_keys=True))


if __name__ == '__main__':
    main()
