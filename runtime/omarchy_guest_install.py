"""Install pinned guest audio/Android adapters, retaining exact original backups."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
from typing import NamedTuple
import uuid

import omarchy_install as base

PAYLOAD_SHA = '49112da74b842970dde875334a1a1fd488c35dbd24a42badfbbb2cf94beb5e4f'
PAYLOAD_BYTES = 153600
MANIFEST_SHA = '23f46b7836d26ef0c2088ab172238b7f7c982cfc3d19f912e5325ded76a36547'
MANIFEST_BYTES = 2430
JOURNAL = 'guest-install.json'


class Component(NamedTuple):
    payload_sha: str
    payload_bytes: int
    manifest_sha: str
    manifest_bytes: int
    name: str
    journal: str
    original_modes: tuple = ()


def require(value, code='guest-install-boundary'):
    base.require(value, code)


def relative(name):
    require(isinstance(name, str) and 1 <= len(name) <= 256)
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and str(path) == name
            and all(p not in ('', '.', '..') for p in path.parts))
    return path


def valid_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def definition(component=None):
    value = component or Component(PAYLOAD_SHA, PAYLOAD_BYTES, MANIFEST_SHA, MANIFEST_BYTES,
                                   'guest-audio-android-settings', JOURNAL)
    require(isinstance(value, Component) and valid_sha(value.payload_sha) and valid_sha(value.manifest_sha)
            and type(value.payload_bytes) is int and 1 <= value.payload_bytes <= 4194304
            and type(value.manifest_bytes) is int and 1 <= value.manifest_bytes <= 16384
            and isinstance(value.name, str) and re.fullmatch('[a-z][a-z0-9-]{1,63}', value.name)
            and isinstance(value.journal, str)
            and re.fullmatch('[a-z][a-z0-9-]{0,40}-install[.]json', value.journal)
            and value.journal != 'weston-install.json', 'guest-component-boundary')
    require(type(value.original_modes) is tuple and len(value.original_modes) <= 32,
            'guest-original-mode-boundary')
    seen = set()
    for entry in value.original_modes:
        require(type(entry) is tuple and len(entry) == 2, 'guest-original-mode-boundary')
        name, mode = entry
        relative(name)
        require(name not in seen and type(mode) is int and mode in (0o600, 0o644, 0o700, 0o755),
                'guest-original-mode-boundary')
        seen.add(name)
    return value


class Payload:
    def __init__(self, payload, manifest, *, component=None):
        spec = definition(component)
        with base.regular(manifest, spec.manifest_bytes) as source:
            before = base.fingerprint(os.fstat(source.fileno()))
            raw = source.read()
            require(len(raw) == spec.manifest_bytes and hashlib.sha256(raw).hexdigest() == spec.manifest_sha,
                    'guest-manifest-sha')
            require(base.fingerprint(os.fstat(source.fileno())) == before)
        self.manifest = json.loads(raw)
        require(set(self.manifest) == {'schema', 'component', 'files'} and self.manifest['schema'] == 1
                and self.manifest['component'] == spec.name)
        self.files = self.manifest['files']
        require(isinstance(self.files, dict) and 1 <= len(self.files) <= 32)
        for name, row in self.files.items():
            relative(name)
            require(set(row) == {'sha256', 'mode', 'before'} and valid_sha(row['sha256'])
                    and row['mode'] in (0o600, 0o644, 0o700, 0o755)
                    and (row['before'] is None or valid_sha(row['before'])))
        self.original_modes = dict(spec.original_modes)
        require(set(self.original_modes) <= set(self.files)
                and all(self.files[name]['before'] is not None for name in self.original_modes),
                'guest-original-mode-boundary')
        names = set(self.files)
        require(not any(str(p) in names for name in names for p in relative(name).parents))
        self.data = {}
        with base.regular(payload, spec.payload_bytes) as source:
            before = base.fingerprint(os.fstat(source.fileno()))
            require(before[4] == spec.payload_bytes and base.hashed(source) == spec.payload_sha, 'guest-payload-sha')
            source.seek(0)
            with tarfile.open(fileobj=source, mode='r:') as archive:
                for index, row in enumerate(archive):
                    require(index < 32 and row.isfile() and row.mode == 0o600
                            and row.name.startswith('guest/') and 0 <= row.size <= 131072)
                    name = row.name[len('guest/'):]
                    relative(name)
                    require(name in self.files and name not in self.data)
                    with archive.extractfile(row) as stream:
                        data = stream.read()
                    require(hashlib.sha256(data).hexdigest() == self.files[name]['sha256'], 'guest-member-sha')
                    if name.endswith('.py'):
                        compile(data, name, 'exec')
                    self.data[name] = data
            require(set(self.data) == names)
            require(base.fingerprint(os.fstat(source.fileno())) == before)


def snapshot(rootfs, name):
    path = relative(name)
    fd = base.walk(rootfs, str(path.parent))
    if fd is None:
        return None
    try:
        try:
            with base.regular(path.name, 131072, fd) as source:
                before = base.fingerprint(os.fstat(source.fileno()))
                sha = base.hashed(source)
                require(base.fingerprint(os.fstat(source.fileno())) == before)
                return {'fingerprint': before, 'sha256': sha, 'mode': stat.S_IMODE(before[3])}
        except FileNotFoundError:
            return None
    finally:
        os.close(fd)


def plan(rootfs, files, original_modes=None):
    original_modes = original_modes or {}
    changes = []
    for name, row in files.items():
        current = snapshot(rootfs, name)
        if current is None:
            require(row['before'] is None, 'guest-original-missing')
        elif current['sha256'] == row['sha256']:
            require(current['mode'] == row['mode'], 'guest-installed-mode-changed')
            continue
        else:
            require(current['sha256'] == row['before']
                    and current['mode'] == original_modes.get(name, row['mode']),
                    'guest-user-file-changed')
        changes.append({'path': name, 'original': current, 'sha256': row['sha256'], 'mode': row['mode'],
                        'backup': 'original-' + str(len(changes)) if current is not None else None})
    return changes


def write_target(rootfs, entry, data):
    path = relative(entry['path'])
    fd = base.walk(rootfs, str(path.parent), True)
    name = '.guest-source-' + uuid.uuid4().hex
    try:
        require(snapshot(rootfs, entry['path']) == entry['original'], 'guest-target-concurrent-change')
        target = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(target, 'wb') as output:
            output.write(data)
            output.flush()
            os.fchmod(output.fileno(), entry['mode'])
            os.fsync(output.fileno())
        require(snapshot(rootfs, entry['path']) == entry['original'], 'guest-target-concurrent-change')
        if entry['original'] is None:
            base.publish(fd, name, path.name)
        else:
            os.replace(name, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try:
            os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            pass
        os.close(fd)


def read_record(fd, journal=JOURNAL):
    try:
        with base.regular(journal, 16384, fd) as source:
            return json.loads(source.read())
    except FileNotFoundError:
        return None


def save_record(fd, row, previous=None, *, journal=JOURNAL):
    require(read_record(fd, journal) == previous, 'guest-journal-concurrent-change')
    data = json.dumps(row, sort_keys=True, separators=(',', ':')).encode()
    require(len(data) <= 16384)
    name = '.guest-install-' + uuid.uuid4().hex
    target = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(target, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if previous is None:
            base.publish(fd, name, journal)
        else:
            require(read_record(fd, journal) == previous, 'guest-journal-concurrent-change')
            os.replace(name, journal, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try:
            os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            pass


def lock(fd, name):
    target = os.open(name, os.O_RDWR | os.O_CREAT | base.NOFOLLOW, 0o600, dir_fd=fd)
    try:
        row = os.fstat(target)
        require(stat.S_ISREG(row.st_mode) and row.st_uid == os.getuid() and row.st_nlink == 1
                and stat.S_IMODE(row.st_mode) == 0o600)
        fcntl.flock(target, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return target
    except BaseException:
        os.close(target)
        raise


def backup(rootfs, root, row):
    folder = root / row['backupDirectory']
    folder.mkdir(mode=0o700)
    row['backupIdentity'] = base.identity(folder.lstat())
    for entry in row['changes']:
        if entry['backup'] is None:
            continue
        require(snapshot(rootfs, entry['path']) == entry['original'], 'guest-backup-concurrent-change')
        parent = base.walk(rootfs, str(relative(entry['path']).parent))
        try:
            with base.regular(relative(entry['path']).name, 131072, parent) as source:
                data = source.read()
            require(hashlib.sha256(data).hexdigest() == entry['original']['sha256'])
            with os.fdopen(os.open(folder / entry['backup'], os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW, 0o600), 'wb') as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        finally:
            os.close(parent)
    fd = base.directory(folder)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def install(payload, manifest, home, prefix, *, component=None):
    spec = definition(component)
    source = Payload(payload, manifest, component=spec)
    fd, locks = None, []
    try:
        home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
        root = home / '.local/share/loopy-omarchy'
        fd = base.walk(home, '.local/share/loopy-omarchy')
        require(fd is not None and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700)
        locks.append(lock(fd, 'install.lock'))
        locks.append(lock(fd, 'runtime-control.lock'))
        installed = base.read_journal(fd)
        require(installed.get('schema') == 1 and installed.get('phase') == 'INSTALLED'
                and installed.get('uid') == os.getuid() and installed.get('root') == base.identity(os.fstat(fd))
                and installed.get('home') == str(home) and installed.get('prefix') == str(prefix)
                and installed.get('container') == base.CONTAINER and installed.get('bundle_sha256') == base.OUTER_SHA)
        base.check_installed(root, prefix, installed)
        rootfs = prefix / 'var/lib/proot-distro/containers' / base.CONTAINER / 'rootfs'
        row = {'schema': 1, 'uid': os.getuid(), 'root': base.identity(os.fstat(fd)),
               'rootfs': installed['rootfs_identity'], 'payloadSHA256': spec.payload_sha,
               'manifestSHA256': spec.manifest_sha, 'filesVerified': len(source.files)}
        previous = read_record(fd, spec.journal)
        if previous is not None:
            require(all(previous.get(k) == v for k, v in row.items()), 'guest-journal-identity')
            require(previous.get('phase') == 'INSTALLED', 'guest-install-uncertain')
        changes = plan(rootfs, source.files, source.original_modes)  # Inspect all targets before writes.
        if previous is not None:
            require(not changes, 'guest-installed-target-changed')
            return previous
        if not changes:
            row.update(phase='INSTALLED', changes=[], backupDirectory=None, adoptedExisting=True)
            save_record(fd, row, journal=spec.journal)
            return row
        try:
            with base.regular('runtime-state.json', 16384, fd) as data:
                state = json.loads(data.read())
            require(state.get('phase') == 'stopped' and state.get('terminationConfirmed') is True,
                    'guest-runtime-active')
        except FileNotFoundError:
            pass
        row.update(phase='BACKUP', changes=changes, backupDirectory='.guest-backup-' + uuid.uuid4().hex,
                   applied=[], adoptedExisting=False)
        save_record(fd, row, journal=spec.journal)
        saved = json.loads(json.dumps(row))
        try:
            backup(rootfs, root, row)
            row['phase'] = 'INSTALLING'
            save_record(fd, row, saved, journal=spec.journal)
            saved = json.loads(json.dumps(row))
            for entry in changes:
                require(base.identity(root.lstat()) == row['root']
                        and base.identity(rootfs.lstat()) == row['rootfs'], 'guest-root-replaced')
                write_target(rootfs, entry, source.data[entry['path']])
                row['applied'].append(entry['path'])
            require(not plan(rootfs, source.files, source.original_modes), 'guest-install-incomplete')
            row['phase'] = 'INSTALLED'
            save_record(fd, row, saved, journal=spec.journal)
            return row
        except BaseException:
            row['phase'] = 'INSTALL_UNKNOWN'
            save_record(fd, row, saved, journal=spec.journal)
            raise ValueError('guest-install-uncertain') from None
    except OSError:
        raise ValueError('guest-install-filesystem') from None
    finally:
        for target in reversed(locks):
            os.close(target)
        if fd is not None:
            os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install pinned guest audio and Android settings adapters')
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(install(args.payload, args.manifest, os.environ['HOME'], os.environ['PREFIX']), sort_keys=True))


if __name__ == '__main__':
    main()
