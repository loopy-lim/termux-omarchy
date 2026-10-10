#!/usr/bin/env python3
"""Install only the audited source-built X11 companion, preserving other nightlies."""
from contextlib import contextmanager
import gzip
import hashlib
import io
import lzma
import os
from pathlib import Path
import re
import stat
import tarfile

import native

PACKAGE = 'termux-x11-nightly'
MODES = {'bin/termux-x11': 0o755, 'bin/termux-x11-preference': 0o755,
         'libexec/termux-x11/loader.apk': 0o400}
DEB_PREFIX = 'data/data/com.termux/files/usr'
POSTINST = (b'#!/data/data/com.termux/files/usr/bin/sh\n'
            b'chmod 400 /data/data/com.termux/files/usr/libexec/termux-x11/loader.apk\n')
MAX_DEB = 16 * 1024 * 1024
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def require(value, reason):
    if not value:
        raise ValueError(reason)


def validate_spec(spec):
    require(isinstance(spec, dict) and set(spec) == {'schema', 'package', 'version', 'files', 'deb'}
            and spec['schema'] == 1 and spec['package'] == PACKAGE
            and isinstance(spec['version'], str)
            and re.fullmatch(r'[0-9][A-Za-z0-9:._+~-]{0,127}', spec['version'])
            and isinstance(spec['files'], dict) and set(spec['files']) == set(MODES), 'companion-spec')
    for name, row in [*spec['files'].items(), ('deb', spec['deb'])]:
        fields = {'bytes', 'sha256'} | ({'mode'} if name != 'deb' else set())
        require(isinstance(row, dict) and set(row) == fields
                and type(row['bytes']) is int and 0 < row['bytes'] <= MAX_DEB
                and isinstance(row['sha256'], str)
                and re.fullmatch(r'[0-9a-f]{64}', row['sha256']), 'companion-spec')
        if name != 'deb':
            require(type(row['mode']) is int and row['mode'] == MODES[name], 'companion-spec')


def directory_safe(fd):
    row = os.fstat(fd)
    require(stat.S_ISDIR(row.st_mode) and row.st_uid == os.getuid()
            and not row.st_mode & 0o022, 'companion-filesystem')


@contextmanager
def parent_fd(prefix, relative):
    """Traverse existing directories without following a target or parent symlink."""
    fds = []
    try:
        try:
            fd = os.open(prefix, DIRECTORY_FLAGS)
            fds.append(fd)
            directory_safe(fd)
            for part in relative.split('/')[:-1]:
                fd = os.open(part, DIRECTORY_FLAGS, dir_fd=fd)
                fds.append(fd)
                directory_safe(fd)
        except FileNotFoundError:
            yield None
            return
        except OSError as error:
            raise ValueError('companion-filesystem') from error
        yield fd
    finally:
        for fd in reversed(fds):
            os.close(fd)


def fingerprint(row):
    return (row.st_dev, row.st_ino, row.st_size, row.st_mode, row.st_uid, row.st_gid,
            row.st_nlink, row.st_mtime_ns, row.st_ctime_ns)


def read_verified(fd, row, expected, reason, *, mode=None, collect=False):
    require(stat.S_ISREG(row.st_mode) and row.st_uid == os.getuid() and row.st_nlink == 1
            and not row.st_mode & 0o022 and row.st_size == expected['bytes']
            and (mode is None or stat.S_IMODE(row.st_mode) == mode), reason)
    digest = hashlib.sha256()
    contents = bytearray()
    count = 0
    while True:
        block = os.read(fd, 1024 * 1024)
        if not block:
            break
        count += len(block)
        require(count <= expected['bytes'], reason)
        digest.update(block)
        if collect:
            contents.extend(block)
    require(count == expected['bytes'] and digest.hexdigest() == expected['sha256']
            and fingerprint(os.fstat(fd)) == fingerprint(row), reason)
    return bytes(contents) if collect else None


def inspect_target(prefix, name, expected, *, installed):
    with parent_fd(prefix, name) as parent:
        try:
            row = None if parent is None else os.stat(name.split('/')[-1], dir_fd=parent,
                                                      follow_symlinks=False)
        except FileNotFoundError:
            row = None
        if not installed:
            require(row is None, 'companion-target-exists')
            return
        require(row is not None, 'companion-file-missing')
        try:
            fd = os.open(name.split('/')[-1], FILE_FLAGS, dir_fd=parent)
        except OSError as error:
            raise ValueError('companion-filesystem') from error
        try:
            require(fingerprint(os.fstat(fd)) == fingerprint(row), 'companion-file-mismatch')
            read_verified(fd, row, expected, 'companion-file-mismatch', mode=expected['mode'])
            require(fingerprint(os.stat(name.split('/')[-1], dir_fd=parent,
                                        follow_symlinks=False)) == fingerprint(row), 'companion-file-mismatch')
        finally:
            os.close(fd)


def receipt(status, spec, *, writes=False):
    return {'schema': 1, 'status': status, 'package': PACKAGE, 'version': spec['version'],
            'filesVerified': 0 if status == 'companion-absent' else len(MODES),
            'packageWrites': writes, 'packageUpgradesAllowed': False,
            'fullFreshInstallVerified': False, 'androidPermissionsGranted': False}


def database_state(prefix):
    """Do not mistake dpkg's removed or unfinished records for an absent package."""
    with parent_fd(prefix, 'var/lib/dpkg/status') as parent:
        if parent is None:
            return None
        try:
            fd = os.open('status', FILE_FLAGS, dir_fd=parent)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise ValueError('companion-package-database') from error
        try:
            row = os.fstat(fd)
            require(stat.S_ISREG(row.st_mode) and row.st_uid == os.getuid()
                    and row.st_nlink == 1 and not row.st_mode & 0o022
                    and row.st_size <= MAX_DEB, 'companion-package-database')
            with os.fdopen(os.dup(fd), 'rb') as source:
                data = source.read(MAX_DEB + 1)
            require(len(data) == row.st_size and fingerprint(os.fstat(fd)) == fingerprint(row)
                    and fingerprint(os.stat('status', dir_fd=parent, follow_symlinks=False)) == fingerprint(row),
                    'companion-package-database')
        finally:
            os.close(fd)
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError as error:
        raise ValueError('companion-package-database') from error
    found = None
    for paragraph in text.split('\n\n'):
        fields = {}
        for line in paragraph.splitlines():
            if line.startswith((' ', '\t')) or not line:
                continue
            require(':' in line, 'companion-package-database')
            name, value = line.split(':', 1)
            if name in ('Package', 'Status', 'Version'):
                require(name not in fields, 'companion-package-database')
                fields[name] = value.strip()
        if fields.get('Package') == PACKAGE:
            require(found is None and {'Status', 'Version'} <= set(fields), 'companion-package-database')
            found = fields
    return found


def check_database(prefix, installed_version, spec):
    state = database_state(prefix)
    if state is not None:
        require(state['Status'] == 'install ok installed', 'companion-package-state-pending')
        require(installed_version is not None and state['Version'] == installed_version,
                'companion-package-state-changed')
        require(state['Version'] == spec['version'], 'companion-version-mismatch')
    if installed_version is None:
        with parent_fd(prefix, 'var/lib/dpkg/info/__check__') as info:
            require(info is None or not any(name.startswith((PACKAGE + '.', PACKAGE + ':'))
                    for name in os.listdir(info)), 'companion-package-metadata-exists')


def preflight(prefix, installed, spec):
    validate_spec(spec)
    prefix = Path(prefix)
    require(prefix.is_absolute() and '..' not in prefix.parts, 'companion-filesystem')
    require(isinstance(installed, dict), 'companion-package-query')
    version = installed.get(PACKAGE)
    require(version is None or version == spec['version'], 'companion-version-mismatch')
    check_database(prefix, version, spec)
    for name, expected in spec['files'].items():
        inspect_target(prefix, name, expected, installed=version is not None)
    return receipt('companion-absent' if version is None else 'companion-verified', spec)


def ar_members(blob):
    require(blob.startswith(b'!<arch>\n'), 'companion-deb-archive')
    members = {}
    position = 8
    while position < len(blob):
        header = blob[position:position + 60]
        require(len(header) == 60 and header[58:] == b'`\n', 'companion-deb-archive')
        try:
            name = header[:16].decode('ascii').rstrip().removesuffix('/')
            length = header[48:58].decode('ascii').strip()
        except UnicodeDecodeError as error:
            raise ValueError('companion-deb-archive') from error
        require(name in ('debian-binary', 'control.tar.gz', 'data.tar.xz') and name not in members
                and re.fullmatch(r'[0-9]+', length), 'companion-deb-archive')
        length = int(length)
        position += 60
        require(length <= MAX_DEB and position + length <= len(blob), 'companion-deb-archive')
        members[name] = blob[position:position + length]
        position += length
        if length % 2:
            require(blob[position:position + 1] == b'\n', 'companion-deb-archive')
            position += 1
    require(set(members) == {'debian-binary', 'control.tar.gz', 'data.tar.xz'}
            and members['debian-binary'] == b'2.0\n', 'companion-deb-archive')
    return members


def tar_members(blob, compression, limit, reason):
    """Read a bounded archive as data; never extract package-controlled paths."""
    try:
        compressed = (gzip.GzipFile(fileobj=io.BytesIO(blob), mode='rb') if compression == 'gz'
                      else lzma.LZMAFile(io.BytesIO(blob), 'rb'))
        with compressed:
            data = compressed.read(limit + 1)
        require(len(data) <= limit, reason)
        result = {}
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
            for entry in archive:
                name = entry.name.removeprefix('./').rstrip('/')
                require(name not in result and not entry.pax_headers
                        and (entry.isdir() or entry.isreg()) and entry.size <= limit, reason)
                if entry.isdir():
                    require(entry.size == 0 and stat.S_IMODE(entry.mode) == 0o755, reason)
                    result[name] = (None, 0o755)
                else:
                    require(stat.S_IFMT(entry.mode) in (0, stat.S_IFREG), reason)
                    with archive.extractfile(entry) as source:
                        contents = source.read(limit + 1)
                    require(len(contents) == entry.size, reason)
                    result[name] = (contents, stat.S_IMODE(entry.mode))
        return result
    except (OSError, EOFError, tarfile.TarError, lzma.LZMAError) as error:
        raise ValueError(reason) from error


def audit_deb(blob, spec):
    """Audit the exact reviewed control scripts and complete payload target set."""
    members = ar_members(blob)
    control = tar_members(members['control.tar.gz'], 'gz', 65536, 'companion-deb-control')
    require(set(control) in ({'control', 'postinst'}, {'.', 'control', 'postinst'})
            and control.get('.') in (None, (None, 0o755)), 'companion-deb-control')
    control_text = (f'Package: {PACKAGE}\nArchitecture: all\nMaintainer: Termux Omarchy contributors\n'
                    f'Version: {spec["version"]}\nHomepage: https://github.com/loopy-lim/termux-omarchy\n'
                    'Depends: xkeyboard-config\nDescription: Termux Omarchy input source alpha companion (Termux:X11 fork)\n').encode()
    require(control['control'] == (control_text, 0o644)
            and control['postinst'] == (POSTINST, 0o755), 'companion-deb-control')
    data = tar_members(members['data.tar.xz'], 'xz',
                       sum(row['bytes'] for row in spec['files'].values()) + 65536, 'companion-deb-data')
    allowed_directories = {'.'}
    for name in MODES:
        parts = (DEB_PREFIX + '/' + name).split('/')
        allowed_directories.update('/'.join(parts[:count]) for count in range(1, len(parts)))
    expected_files = {DEB_PREFIX + '/' + name: row for name, row in spec['files'].items()}
    require({name for name, (value, mode) in data.items() if value is not None} == set(expected_files)
            and all(name in allowed_directories for name, (value, mode) in data.items() if value is None),
            'companion-deb-data')
    for name, expected in expected_files.items():
        contents, mode = data[name]
        require(len(contents) == expected['bytes'] and hashlib.sha256(contents).hexdigest() == expected['sha256']
                and mode == (0o644 if expected['mode'] == 0o400 else expected['mode']), 'companion-deb-data')


def verified_deb(directory, spec):
    name = 'input/termux-x11-companion.deb'
    with parent_fd(Path(directory), name) as parent:
        require(parent is not None, 'companion-deb-missing')
        try:
            fd = os.open(name.split('/')[-1], FILE_FLAGS, dir_fd=parent)
        except OSError as error:
            raise ValueError('companion-deb-filesystem') from error
        try:
            row = os.fstat(fd)
            blob = read_verified(fd, row, spec['deb'], 'companion-deb-mismatch', collect=True)
            require(fingerprint(os.stat(name.split('/')[-1], dir_fd=parent,
                                        follow_symlinks=False)) == fingerprint(row), 'companion-deb-mismatch')
            audit_deb(blob, spec)
            return fingerprint(row)
        finally:
            os.close(fd)


def apply(directory, prefix, installed, spec):
    before = preflight(prefix, installed, spec)
    signature = verified_deb(directory, spec)
    if before['status'] == 'companion-verified':
        return before
    require('xkeyboard-config' in installed, 'companion-dependency-missing')
    require(native.installed_packages() == installed, 'companion-package-state-changed')
    preflight(prefix, installed, spec)
    # Revalidate the audited local input immediately before passing its path to dpkg.
    require(verified_deb(directory, spec) == signature, 'companion-deb-mismatch')
    path = Path(directory) / 'input/termux-x11-companion.deb'
    native.run([str(Path(prefix) / 'bin/dpkg'), '--no-triggers', '-i', str(path)], capture=False, timeout=120)
    after = native.installed_packages()
    require(after == {**installed, PACKAGE: spec['version']}, 'companion-package-result-changed')
    preflight(prefix, after, spec)
    return receipt('companion-installed', spec, writes=True)
