"""Install the native command, or migrate its exact reviewed predecessor with a backup."""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types
import uuid

SOURCE_SHA = 'ab2ffaa94a40be53b086957fe220897f5b5da335c5735f4a469e019495636de5'
PREVIOUS_SOURCE_SHA = '684c23650a5c2d6801fef84268e84df6bd3aa55e3166f2c76d394e2fde25396a'
JOURNAL = 'terminal-command-update.json'
NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC


def require(value, reason='terminal-install-boundary'):
    if not value: raise ValueError(reason)


def load_source(source):
    source = Path(source).absolute()
    fd = os.open(source, os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        row = os.fstat(stream.fileno())
        require(stat.S_ISREG(row.st_mode) and row.st_uid == os.getuid() and row.st_nlink == 1
                and not row.st_mode & 0o022 and row.st_size <= 131072, 'terminal-source-file')
        data = stream.read(131073)
    require(hashlib.sha256(data).hexdigest() == SOURCE_SHA, 'terminal-source-sha')
    module = types.ModuleType('pinned_terminal_command')
    exec(compile(data, str(source), 'exec'), module.__dict__)
    return module, data


def publish(fd, source, target):
    if callable(getattr(os, 'link', None)):
        os.link(source, target, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        return
    rename = ctypes.CDLL(None, use_errno=True).renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(fd, os.fsencode(source), fd, os.fsencode(target), 1):
        number = ctypes.get_errno(); raise OSError(number, os.strerror(number), target)


def read_record(launcher, fd):
    try: data = launcher.read(JOURNAL, 16384, fd)
    except FileNotFoundError: return None
    row = json.loads(data)
    require(isinstance(row, dict), 'terminal-update-uncertain')
    return row


def save_record(launcher, fd, row, previous):
    require(read_record(launcher, fd) == previous, 'terminal-update-journal-changed')
    data = json.dumps(row, sort_keys=True, separators=(',', ':')).encode()
    require(len(data) <= 16384)
    temporary = '.terminal-update-' + uuid.uuid4().hex
    try:
        target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(target, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        require(read_record(launcher, fd) == previous, 'terminal-update-journal-changed')
        if previous is None: publish(fd, temporary, JOURNAL)
        else: os.replace(temporary, JOURNAL, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
        return json.loads(data)
    finally:
        try: os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError: pass


def binding(checked):
    return dict(schema=1, uid=checked['uid'], root=checked['rootIdentity'], prefix=checked['prefix'],
                previousLauncherSHA256=PREVIOUS_SOURCE_SHA, launcherSHA256=SOURCE_SHA)


def verify_migration(launcher, root, checked, row, after):
    require(all(row.get(key) == value for key, value in binding(checked).items())
            and row.get('phase') == 'INSTALLED' and row.get('after') == after
            and row.get('original', {}).get('sha256') == PREVIOUS_SOURCE_SHA
            and row.get('original', {}).get('mode') == 0o700, 'terminal-update-uncertain')
    name = row.get('backupDirectory', '')
    require(isinstance(name, str) and re.fullmatch(r'\.terminal-command-backup-[0-9a-f]{32}', name),
            'terminal-update-backup')
    fd = launcher.directory(name, root)
    try:
        require(launcher.identity(os.fstat(fd)) == row.get('backupIdentity')
                and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700
                and os.listdir(fd) == ['loopy-omarchy'], 'terminal-update-backup')
        original = launcher.read('loopy-omarchy', 131072, fd)
        require(hashlib.sha256(original).hexdigest() == PREVIOUS_SOURCE_SHA
                and stat.S_IMODE(os.stat('loopy-omarchy', dir_fd=fd, follow_symlinks=False).st_mode) == 0o600,
                'terminal-update-backup')
    finally: os.close(fd)


def migrate(launcher, checked, fd, root, original, before, data, home, prefix, prior_journal=None):
    locks, saved = [], None
    row = dict(binding(checked), phase='BACKUP', original=dict(fingerprint=before,
        sha256=PREVIOUS_SOURCE_SHA, mode=0o700), backupDirectory='.terminal-command-backup-' + uuid.uuid4().hex)
    temporary = '.loopy-omarchy-' + uuid.uuid4().hex
    try:
        for name in ('install.lock', 'runtime-control.lock'):
            lock = os.open(name, os.O_RDWR | NOFOLLOW, dir_fd=root)
            info = os.fstat(lock)
            try:
                require(stat.S_ISREG(info.st_mode) and info.st_uid == checked['uid']
                        and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600, 'terminal-update-lock')
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException: os.close(lock); raise
            locks.append((name, lock))
        def recheck():
            require(launcher.context(home, prefix) == checked
                    and launcher.identity(os.fstat(root)) == checked['rootIdentity'], 'terminal-update-context')
            current = launcher.walk(checked['prefix'], 'bin')
            try: require(launcher.identity(os.fstat(current)) == launcher.identity(os.fstat(fd)), 'terminal-bin-changed')
            finally: os.close(current)
            for name, lock in locks:
                require(launcher.fingerprint(os.fstat(lock)) ==
                        launcher.fingerprint(os.stat(name, dir_fd=root, follow_symlinks=False)), 'terminal-update-lock')
        recheck()
        require(launcher.fingerprint(os.stat('loopy-omarchy', dir_fd=fd, follow_symlinks=False)) == before,
                'terminal-command-changed')
        saved = save_record(launcher, root, row, prior_journal)
        os.mkdir(row['backupDirectory'], 0o700, dir_fd=root)
        backup = launcher.directory(row['backupDirectory'], root)
        try:
            row['backupIdentity'] = launcher.identity(os.fstat(backup))
            target = os.open('loopy-omarchy', os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600, dir_fd=backup)
            with os.fdopen(target, 'wb') as stream:
                stream.write(original); stream.flush(); os.fsync(stream.fileno())
            require(launcher.read('loopy-omarchy', 131072, backup) == original, 'terminal-update-backup')
            os.fsync(backup); os.fsync(root)
        finally: os.close(backup)
        row['phase'] = 'UPDATING'; saved = save_record(launcher, root, row, saved)
        target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(target, 'wb') as stream:
            stream.write(data); stream.flush(); os.fchmod(stream.fileno(), 0o700); os.fsync(stream.fileno())
        recheck()
        require(launcher.fingerprint(os.stat('loopy-omarchy', dir_fd=fd, follow_symlinks=False)) == before,
                'terminal-command-changed')
        os.replace(temporary, 'loopy-omarchy', src_dir_fd=fd, dst_dir_fd=fd); os.fsync(fd)
        require(launcher.read('loopy-omarchy', len(data), fd) == data, 'terminal-command-changed')
        row.update(phase='INSTALLED', after=launcher.fingerprint(os.stat('loopy-omarchy', dir_fd=fd, follow_symlinks=False)))
        verify_migration(launcher, root, checked, row, row['after'])
        save_record(launcher, root, row, saved); saved = None
        return row
    except BaseException:
        if saved is not None:
            try: save_record(launcher, root, dict(row, phase='UPDATE_UNKNOWN'), saved)
            except (ValueError, OSError): pass
        raise
    finally:
        try: os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError: pass
        for _, lock in reversed(locks): os.close(lock)


def install(source, home, prefix):
    launcher, data = load_source(source)
    checked = launcher.context(home, prefix)
    fd = launcher.walk(checked['prefix'], 'bin')
    root = launcher.walk(checked['home'], '.local/share/loopy-omarchy')
    name, temporary = 'loopy-omarchy', '.loopy-omarchy-' + uuid.uuid4().hex
    result = dict(schema=1, uid=checked['uid'], command=str(Path(checked['prefix']) / 'bin' / name),
                  launcherSHA256=SOURCE_SHA, existingRuntimeChanged=False)
    try:
        require(launcher.identity(os.fstat(root)) == checked['rootIdentity'], 'terminal-update-root')
        previous = read_record(launcher, root)
        try:
            row = os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError: row = None
        if row is not None:
            original = launcher.read(name, 131072, fd)
            require(stat.S_IMODE(row.st_mode) == 0o700, 'terminal-command-exists')
            require(launcher.fingerprint(os.stat(name, dir_fd=fd, follow_symlinks=False)) ==
                    launcher.fingerprint(row), 'terminal-command-changed')
            if original == data:
                if previous is not None: verify_migration(launcher, root, checked, previous, launcher.fingerprint(row))
                return dict(result, status='unchanged')
            if previous is None:
                require(hashlib.sha256(original).hexdigest() == PREVIOUS_SOURCE_SHA, 'terminal-command-exists')
            else:
                # Successor migration: the bytes must be the exact reviewed predecessor;
                # the prior journal only has to belong to this managed runtime root. A
                # stale launcher claim inside it (from an unjournalled replacement) does
                # not change what the bytes prove.
                require(hashlib.sha256(original).hexdigest() == PREVIOUS_SOURCE_SHA
                        and previous.get('schema') == 1 and previous.get('phase') == 'INSTALLED'
                        and previous.get('uid') == checked['uid']
                        and isinstance(previous.get('root'), list) and len(previous['root']) == 3
                        and previous['root'][1:] == checked['rootIdentity'][1:]
                        and previous.get('prefix') == checked['prefix'], 'terminal-command-exists')
            migrated = migrate(launcher, checked, fd, root, original, launcher.fingerprint(row), data, home, prefix,
                               prior_journal=previous)
            return dict(result, status='updated', journal=JOURNAL, backupDirectory=migrated['backupDirectory'])
        require(previous is None, 'terminal-update-uncertain')
        target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(target, 'wb') as stream:
            stream.write(data); stream.flush(); os.fchmod(stream.fileno(), 0o700); os.fsync(stream.fileno())
        require(launcher.context(home, prefix) == checked, 'terminal-install-changed')
        current = launcher.walk(checked['prefix'], 'bin')
        try:
            require(launcher.identity(os.fstat(current)) == launcher.identity(os.fstat(fd)),
                    'terminal-bin-changed')
        finally: os.close(current)
        publish(fd, temporary, name)
        try: os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError: pass  # renameat2 already consumed it on Android.
        os.fsync(fd)
        require(launcher.read(name, len(data), fd) == data, 'terminal-command-changed')
        return dict(result, status='installed')
    finally:
        try: os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError: pass
        os.close(fd)
        os.close(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).parent / 'omarchy_terminal.py')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(install(args.source, os.environ['HOME'], os.environ['PREFIX']), sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[a-z0-9-]{1,64}', str(error)) else 'terminal-install-unavailable'
        print(json.dumps(dict(schema=1, status='failed', reason=reason), sort_keys=True))
        return 1


if __name__ == '__main__': sys.exit(main())
