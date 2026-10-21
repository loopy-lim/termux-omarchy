"""Pinned private Weston14 installation; preserve changed or uncertain work."""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile
import uuid

import omarchy_install as base

PAYLOAD_SHA = '939ad9f94b1cfe96d4472b3c3bb9323c8ec9191d8c88fa2fca3e2064c273f728'
PAYLOAD_BYTES = 2979840
MANIFEST_SHA = '6c07cb0968ef9aef7caaefc311aeaffe119290957eb5bbf11245d860f1155c3d'
MANIFEST_BYTES = 13376
DEB_SHA = '25d1c5ee4013e14097d6e37a3227d6fcef8f43d6d7a2dd0ee130a77e1af31c8a'
SOURCE_URL = 'https://github.com/lfdevs/anland-termux/releases/download/5.13.3/weston_14.0.2-3_aarch64.deb'
JOURNAL = 'weston-install.json'


def require(value, code='weston-install-boundary'):
    base.require(value, code)


def relative(name):
    require(isinstance(name, str) and len(name) <= 256)
    path = PurePosixPath(name)
    require(not path.is_absolute() and str(path) == name and all(p not in ('', '.', '..') for p in path.parts))
    return path


def parents(files):
    return {str(p) for name in files for p in relative(name).parents if str(p) != '.'}


class Payload:
    def __init__(self, payload, manifest):
        self.file, self.archive = None, None
        try:
            with base.regular(manifest, MANIFEST_BYTES) as data:
                before = base.fingerprint(os.fstat(data.fileno()))
                raw = data.read()
                require(len(raw) == MANIFEST_BYTES and hashlib.sha256(raw).hexdigest() == MANIFEST_SHA,
                        'weston-manifest-sha')
                require(base.fingerprint(os.fstat(data.fileno())) == before)
            self.manifest = json.loads(raw)
            require(set(self.manifest) == {'schema', 'debSHA256', 'sourceURL', 'files'})
            require(self.manifest['schema'] == 1 and self.manifest['debSHA256'] == DEB_SHA
                    and self.manifest['sourceURL'] == SOURCE_URL)
            self.files = self.manifest['files']
            require(isinstance(self.files, dict) and 1 <= len(self.files) <= 128)
            for name, expected in self.files.items():
                relative(name)
                require(set(expected) == {'sha256', 'mode'} and expected['mode'] in (0o600, 0o700))
                require(isinstance(expected['sha256'], str) and len(expected['sha256']) == 64
                        and all(c in '0123456789abcdef' for c in expected['sha256']))
            self.dirs = parents(self.files)
            require(not self.dirs.intersection(self.files))
            self.file = base.regular(payload, PAYLOAD_BYTES)
            self.original = base.fingerprint(os.fstat(self.file.fileno()))
            require(self.original[4] == PAYLOAD_BYTES and base.hashed(self.file) == PAYLOAD_SHA,
                    'weston-payload-sha')
            self.file.seek(0)
            self.archive = tarfile.open(fileobj=self.file, mode='r:')
            self.rows, seen = {}, set()
            allowed_dirs = {'weston-host'} | {'weston-host/' + p for p in self.dirs}
            for index, row in enumerate(self.archive):
                require(index < 256 and row.name not in seen)
                relative(row.name)
                seen.add(row.name)
                if row.name in allowed_dirs:
                    require(row.isdir() and row.mode in (0o700, 0o755) and row.size == 0)
                else:
                    require(row.name.startswith('weston-host/') and row.isfile())
                    name = row.name[len('weston-host/'):]
                    require(name in self.files and 0 <= row.size <= PAYLOAD_BYTES)
                    require(row.mode == self.files[name]['mode'])
                    with self.archive.extractfile(row) as stream:
                        require(base.hashed(stream) == self.files[name]['sha256'], 'weston-member-sha')
                    self.rows[name] = row
            require(set(self.rows) == set(self.files) and seen == allowed_dirs | {'weston-host/' + p for p in self.files})
            self.unchanged()
        except BaseException:
            self.close()
            raise

    def unchanged(self):
        require(base.fingerprint(os.fstat(self.file.fileno())) == self.original, 'weston-payload-changed')

    def close(self):
        if self.archive is not None:
            self.archive.close()
        if self.file is not None:
            self.file.close()

    def copy(self, root, stage):
        for name, row in self.rows.items():
            fd = base.walk(root / stage, str(relative(name).parent), True)
            try:
                target = os.open(relative(name).name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW,
                                 self.files[name]['mode'], dir_fd=fd)
                with os.fdopen(target, 'wb') as output, self.archive.extractfile(row) as source:
                    while data := source.read(65536):
                        output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                os.fsync(fd)
            finally:
                os.close(fd)
        self.unchanged()


def inventory(path, files):
    """Inspect a closed file set through directory FDs, never through symlinks."""
    expected_dirs, found, identities = parents(files), set(), {}
    root_fd = base.directory(path)
    try:
        identities[''] = base.identity(os.fstat(root_fd))
        def visit(fd, parent=''):
            for leaf in os.listdir(fd):
                name = parent + leaf
                row = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
                require(row.st_uid == os.getuid() and not row.st_mode & 0o022)
                if name in expected_dirs:
                    require(stat.S_ISDIR(row.st_mode))
                    child = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | base.NOFOLLOW, dir_fd=fd)
                    try:
                        require(base.identity(os.fstat(child)) == base.identity(row))
                        identities[name] = base.identity(row)
                        visit(child, name + '/')
                    finally:
                        os.close(child)
                else:
                    require(name in files, 'weston-existing-extra')
                    with base.regular(leaf, PAYLOAD_BYTES, fd) as data:
                        before = base.fingerprint(os.fstat(data.fileno()))
                        require(before[:3] == base.identity(row) and stat.S_IMODE(before[3]) == files[name]['mode'])
                        require(base.hashed(data) == files[name]['sha256'], 'weston-existing-changed')
                        require(base.fingerprint(os.fstat(data.fileno())) == before)
                        identities[name] = before
                        found.add(name)
        visit(root_fd)
        require(found == set(files) and set(identities) == set(files) | expected_dirs | {''},
                'weston-existing-incomplete')
        return identities
    finally:
        os.close(root_fd)


def publish_directory(fd, stage, name):
    """Atomic exclusive directory rename on Android/Linux and macOS."""
    libc = ctypes.CDLL(None, use_errno=True)
    if hasattr(libc, 'renameat2'):
        rename, flags = libc.renameat2, 1  # RENAME_NOREPLACE
    else:
        rename, flags = libc.renameatx_np, 4  # Darwin RENAME_EXCL, sys/stdio.h
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(fd, os.fsencode(stage), fd, os.fsencode(name), flags) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), name)
    os.fsync(fd)


def read_record(fd):
    try:
        with base.regular(JOURNAL, 16384, fd) as source:
            return json.loads(source.read())
    except FileNotFoundError:
        return None


def save_record(fd, row, previous=None):
    require(read_record(fd) == previous, 'weston-journal-concurrent-change')
    data = json.dumps(row, sort_keys=True, separators=(',', ':')).encode()
    require(len(data) <= 16384)
    name = '.weston-install-' + uuid.uuid4().hex
    temporary = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(temporary, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if previous is None:
            base.publish(fd, name, JOURNAL)
        else:
            require(read_record(fd) == previous, 'weston-journal-concurrent-change')
            os.replace(name, JOURNAL, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try:
            os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            pass


def version(path, home, prefix):
    env = {k: v for k, v in os.environ.items() if k not in ('LD_PRELOAD', 'LD_LIBRARY_PATH')}
    env.update(HOME=str(home), PREFIX=str(prefix), PATH=f'{prefix}/bin:/system/bin',
               LD_LIBRARY_PATH=f'{path}/lib/weston:{path}/lib:{prefix}/lib')
    result = subprocess.run([str(path / 'bin/weston'), '--version'], shell=False, env=env,
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=False)
    require(result.returncode == 0 and result.stdout.strip() == b'weston 14.0.2'
            and len(result.stderr) <= 4096, 'weston-version-unavailable')


def install(payload, manifest, home, prefix):
    source = Payload(payload, manifest)  # Validate every byte before touching installation state.
    fd, lock = None, None
    try:
        home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
        root = home / '.local/share/loopy-omarchy'
        fd = base.walk(home, '.local/share/loopy-omarchy')
        require(fd is not None and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700)
        installed = base.read_journal(fd)
        require(installed.get('schema') == 1 and installed.get('phase') == 'INSTALLED'
                and installed.get('uid') == os.getuid() and installed.get('root') == base.identity(os.fstat(fd))
                and installed.get('home') == str(home) and installed.get('prefix') == str(prefix)
                and installed.get('container') == base.CONTAINER and installed.get('bundle_sha256') == base.OUTER_SHA)
        base.check_installed(root, prefix, installed)
        lock = os.open('install.lock', os.O_RDWR | os.O_CREAT | base.NOFOLLOW, 0o600, dir_fd=fd)
        info = os.fstat(lock)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(base.read_journal(fd) == installed, 'weston-base-concurrent-change')
        previous = read_record(fd)
        if previous is not None:
            require(previous.get('schema') == 1 and previous.get('uid') == os.getuid()
                    and previous.get('root') == base.identity(os.fstat(fd))
                    and previous.get('payloadSHA256') == PAYLOAD_SHA and previous.get('manifestSHA256') == MANIFEST_SHA)
            require(previous.get('phase') == 'INSTALLED', 'weston-install-uncertain')
        row = {'schema': 1, 'uid': os.getuid(), 'root': base.identity(os.fstat(fd)),
               'payloadSHA256': PAYLOAD_SHA, 'manifestSHA256': MANIFEST_SHA,
               'debSHA256': DEB_SHA, 'filesVerified': len(source.files), 'westonVersion': '14.0.2'}
        try:
            os.stat('weston-host', dir_fd=fd, follow_symlinks=False)
            exists = True
        except FileNotFoundError:
            exists = False
        if exists:
            before = inventory(root / 'weston-host', source.files)
            if previous is not None:
                require(previous.get('host') == before[''], 'weston-host-replaced')
            require(base.identity(root.lstat()) == row['root'], 'weston-root-replaced')
            version(root / 'weston-host', home, prefix)
            require(inventory(root / 'weston-host', source.files) == before, 'weston-host-concurrent-change')
            if previous is not None:
                require(previous.get('filesVerified') == len(source.files)
                        and previous.get('debSHA256') == DEB_SHA and previous.get('westonVersion') == '14.0.2')
                return previous
            row.update(phase='INSTALLED', host=before[''], adoptedExisting=True)
            if previous != row:
                save_record(fd, row, previous)
            return row
        require(previous is None, 'weston-host-missing')
        try:
            with base.regular('runtime-state.json', 16384, fd) as data:
                state = json.loads(data.read())
            require(state.get('phase') == 'stopped' and state.get('terminationConfirmed') is True,
                    'weston-runtime-active')
        except FileNotFoundError:
            pass
        row.update(phase='STAGING', stage='.weston-host-' + uuid.uuid4().hex)
        save_record(fd, row)
        saved = dict(row)
        try:
            os.mkdir(row['stage'], 0o700, dir_fd=fd)
            row['stageIdentity'] = base.identity(os.stat(row['stage'], dir_fd=fd, follow_symlinks=False))
            row['phase'] = 'INSTALLING'
            save_record(fd, row, saved)
            saved = dict(row)
            source.copy(root, row['stage'])
            before = inventory(root / row['stage'], source.files)
            version(root / row['stage'], home, prefix)
            require(inventory(root / row['stage'], source.files) == before, 'weston-stage-concurrent-change')
            require(base.identity(root.lstat()) == row['root'], 'weston-root-replaced')
            publish_directory(fd, row['stage'], 'weston-host')
            require(inventory(root / 'weston-host', source.files) == before, 'weston-published-changed')
            row.update(phase='INSTALLED', host=before[''], adoptedExisting=False)
            save_record(fd, row, saved)
            return row
        except BaseException:
            row['phase'] = 'INSTALL_UNKNOWN'
            save_record(fd, row, saved)
            raise ValueError('weston-install-uncertain') from None
    except OSError:
        raise ValueError('weston-install-filesystem') from None
    finally:
        if lock is not None:
            os.close(lock)
        if fd is not None:
            os.close(fd)
        source.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install pinned private Weston14 into the owned Omarchy root')
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(install(args.payload, args.manifest, os.environ['HOME'], os.environ['PREFIX']), sort_keys=True))


if __name__ == '__main__':
    main()
