"""Prepare only empty managed D-Bus machine IDs, preserving live sessions."""
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import sys
import uuid

import omarchy_install as base
import omarchy_guest_install as guest

FILES = ('etc/machine-id', 'var/lib/dbus/machine-id')
JOURNAL = 'machine-id-install.json'
BACKUP = '.machine-id-backup-'


def require(value, code='machine-id-boundary'):
    base.require(value, code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(rootfs, name):
    path = PurePosixPath(name)
    fd = base.walk(rootfs, str(path.parent))
    require(fd is not None, 'machine-id-parent-missing')
    try:
        info = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
        before = base.fingerprint(info)
        if stat.S_ISLNK(info.st_mode):
            require(name == FILES[1] and info.st_uid == os.getuid() and info.st_nlink == 1,
                    'machine-id-symlink')
            target = os.readlink(path.name, dir_fd=fd)
            require(target == '/etc/machine-id', 'machine-id-symlink')
            data, kind = target.encode(), 'symlink'
        else:
            require(stat.S_IMODE(info.st_mode) in (0o400, 0o444, 0o600, 0o644), 'machine-id-file-mode')
            with base.regular(path.name, 64, fd) as stream:
                require(base.fingerprint(os.fstat(stream.fileno())) == before, 'machine-id-replaced')
                data = stream.read()
                require(base.fingerprint(os.fstat(stream.fileno())) == before, 'machine-id-replaced')
            kind = 'regular'
        require(base.fingerprint(os.stat(path.name, dir_fd=fd, follow_symlinks=False)) == before,
                'machine-id-replaced')
        return dict(kind=kind, fingerprint=before, mode=stat.S_IMODE(info.st_mode),
                    parent=base.identity(os.fstat(fd)), sha256=digest(data)), data
    finally:
        os.close(fd)


def inspect(rootfs):
    pairs = {name: snapshot(rootfs, name) for name in FILES}
    files = {name: pair[0] for name, pair in pairs.items()}
    first, second = pairs[FILES[0]][1], pairs[FILES[1]][1]
    require(files[FILES[0]]['kind'] == 'regular', 'machine-id-etc-symlink')
    if files[FILES[1]]['kind'] == 'symlink':
        second = first  # Interpret the literal guest link inside this rootfs, never on the host.
    if first == second == b'':
        return files, None
    require(re.fullmatch(rb'[0-9a-f]{32}\n?', first) is not None
            and re.fullmatch(rb'[0-9a-f]{32}\n?', second) is not None
            and first.rstrip(b'\n') == second.rstrip(b'\n'), 'machine-id-invalid-or-partial')
    return files, digest(first.rstrip(b'\n'))


def context(root, fd, home, prefix, previous=None):
    require(stat.S_IMODE(os.fstat(fd).st_mode) == 0o700
            and base.identity(root.lstat()) == base.identity(os.fstat(fd)), 'machine-id-root')
    row = base.read_journal(fd)
    require(isinstance(row, dict) and row.get('schema') == 1 and row.get('phase') == 'INSTALLED'
            and row.get('uid') == os.getuid() and row.get('root') == base.identity(os.fstat(fd))
            and row.get('home') == str(home) and row.get('prefix') == str(prefix)
            and row.get('container') == base.CONTAINER and row.get('bundle_sha256') == base.OUTER_SHA,
            'machine-id-base-identity')
    require(previous is None or row == previous, 'machine-id-base-changed')
    base.check_installed(root, prefix, row)
    return row


def lock_existing(fd, name):
    lock = os.open(name, os.O_RDWR | base.NOFOLLOW, dir_fd=fd)
    try:
        row = os.fstat(lock)
        require(stat.S_ISREG(row.st_mode) and row.st_uid == os.getuid() and row.st_nlink == 1
                and stat.S_IMODE(row.st_mode) == 0o600, 'machine-id-lock')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(base.identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) == base.identity(row),
                'machine-id-lock-replaced')
        return lock
    except BaseException:
        os.close(lock)
        raise


def read_record(fd):
    try:
        stream = base.regular(JOURNAL, 16384, fd)
    except FileNotFoundError:
        return None
    with stream:
        before = base.fingerprint(os.fstat(stream.fileno()))
        require(stat.S_IMODE(before[3]) == 0o600, 'machine-id-journal-mode')
        row = json.loads(stream.read())
        require(isinstance(row, dict), 'machine-id-journal-invalid')
        require(base.fingerprint(os.stat(JOURNAL, dir_fd=fd, follow_symlinks=False)) == before,
                'machine-id-journal-replaced')
        return row


def verify_files(rootfs, expected):
    require({name: snapshot(rootfs, name)[0] for name in FILES} == expected, 'machine-id-replaced')


def backup_files(root, fd, rootfs, row):
    os.mkdir(row['backupDirectory'], 0o700, dir_fd=fd)
    folder = base.directory(root / row['backupDirectory'])
    try:
        identity = base.identity(os.fstat(folder))
        for index, name in enumerate(FILES):
            current, data = snapshot(rootfs, name)
            require(current == row['before'][name], 'machine-id-replaced')
            out = os.open('original-' + str(index), os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW,
                          0o600, dir_fd=folder)
            with os.fdopen(out, 'wb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.fsync(folder); os.fsync(fd)
        return identity
    finally:
        os.close(folder)


def verify_backup(root, row):
    name = row.get('backupDirectory', '')
    require(re.fullmatch(re.escape(BACKUP) + '[0-9a-f]{32}', name) is not None)
    fd = base.directory(root / name)
    try:
        require(base.identity(os.fstat(fd)) == row.get('backupIdentity')
                and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700
                and set(os.listdir(fd)) == {'original-0', 'original-1'}, 'machine-id-backup-changed')
        for index, name in enumerate(FILES):
            with base.regular('original-' + str(index), 64, fd) as stream:
                require(stat.S_IMODE(os.fstat(stream.fileno()).st_mode) == 0o600
                        and digest(stream.read()) == row['before'][name]['sha256'], 'machine-id-backup-changed')
    finally:
        os.close(fd)


def replace_file(rootfs, name, expected, data):
    path = PurePosixPath(name)
    fd = base.walk(rootfs, str(path.parent))
    require(fd is not None)
    temporary = '.machine-id-' + uuid.uuid4().hex
    try:
        require(snapshot(rootfs, name)[0] == expected, 'machine-id-replaced')
        out = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(out, 'wb') as stream:
            stream.write(data); stream.flush()
            os.fchmod(stream.fileno(), expected['mode']); os.fsync(stream.fileno())
        require(snapshot(rootfs, name)[0] == expected, 'machine-id-replaced')
        os.replace(temporary, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try: os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError: pass
        os.close(fd)


def install(home, prefix):
    home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
    root = home / '.local/share/loopy-omarchy'
    rootfs = prefix / 'var/lib/proot-distro/containers' / base.CONTAINER / 'rootfs'
    fd, locks, saved = None, [], None
    try:
        fd = base.walk(home, '.local/share/loopy-omarchy')
        require(fd is not None, 'machine-id-root-missing')
        installed = context(root, fd, home, prefix)
        for name in ('install.lock', 'runtime-control.lock'):
            locks.append((name, lock_existing(fd, name)))
        def recheck():
            context(root, fd, home, prefix, installed)
            for name, lock in locks:
                require(base.fingerprint(os.fstat(lock)) ==
                        base.fingerprint(os.stat(name, dir_fd=fd, follow_symlinks=False)), 'machine-id-lock-replaced')
        recheck()
        previous = read_record(fd)
        existing_backups = {name for name in os.listdir(fd) if name.startswith(BACKUP)}
        before, id_sha = inspect(rootfs)
        binding = dict(schema=1, uid=os.getuid(), root=installed['root'], rootfs=installed['rootfs_identity'])
        if previous is not None:
            require(all(previous.get(k) == v for k, v in binding.items())
                    and previous.get('phase') == 'INSTALLED' and previous.get('after') == before
                    and previous.get('machineIDSHA256') == id_sha and id_sha is not None
                    and existing_backups == {previous.get('backupDirectory')}, 'machine-id-install-uncertain')
            verify_backup(root, previous)
            return previous
        require(not existing_backups, 'machine-id-orphan-backup')
        if id_sha is not None:
            return dict(binding, status='existing-valid', files=before, machineIDSHA256=id_sha)
        data = secrets.token_hex(16).encode() + b'\n'
        row = dict(binding, phase='BACKUP', before=before, machineIDSHA256=digest(data.rstrip(b'\n')),
                   backupDirectory=BACKUP + uuid.uuid4().hex)
        recheck(); verify_files(rootfs, before)
        guest.save_record(fd, row, journal=JOURNAL); saved = row
        backup_id = backup_files(root, fd, rootfs, row)
        row = dict(row, phase='INSTALLING', backupIdentity=backup_id)
        guest.save_record(fd, row, previous=saved, journal=JOURNAL); saved = row
        current = dict(before)
        for name in FILES:
            recheck(); verify_files(rootfs, current)
            if current[name]['kind'] == 'regular':
                replace_file(rootfs, name, current[name], data)
                current[name] = snapshot(rootfs, name)[0]
                require(current[name]['sha256'] == digest(data), 'machine-id-write-mismatch')
        recheck(); verify_files(rootfs, current)
        after, id_sha = inspect(rootfs)
        require(id_sha == row['machineIDSHA256'], 'machine-id-write-mismatch')
        row = dict(row, phase='INSTALLED', after=after)
        verify_backup(root, row)
        guest.save_record(fd, row, previous=saved, journal=JOURNAL); saved = None
        return row
    except BaseException:
        if saved is not None:
            try: guest.save_record(fd, dict(saved, phase='INSTALL_UNKNOWN'), previous=saved, journal=JOURNAL)
            except (ValueError, OSError): pass
        raise
    finally:
        for _, lock in reversed(locks): os.close(lock)
        if fd is not None: os.close(fd)


def main():
    try:
        print(json.dumps(install(os.environ['HOME'], os.environ['PREFIX']), sort_keys=True))
        return 0
    except Exception as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[a-z0-9-]{1,64}', str(error)) else 'machine-id-unavailable'
        print(json.dumps(dict(schema=1, status='failed', reason=reason), sort_keys=True))
        return 1


if __name__ == '__main__': sys.exit(main())
