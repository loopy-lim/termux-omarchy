"""Install one new private official VS Code version without altering packages or profiles."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import uuid

import omarchy_guest_install as adapters
import omarchy_host_install as host
import omarchy_install as base
import omarchy_proot as guard
import omarchy_vscode_archive as archive

JOURNAL = 'vscode-install.json'
RELATIVE = 'opt/loopy-vscode'
SUPPORT = {
    'loopy-vscode': ('usr/local/bin/loopy-vscode', 0o700,
        '41481a28f3966ab5285a511ed4e5170175e94dbbad1fb46c72ec8d29903e4cb0'),
    'loopy-vscode.desktop': ('usr/share/applications/loopy-vscode.desktop', 0o600,
        '69840e643b88db972374400c1e10293f5026f0d74595a60c40088796eab2b23e'),
}
require = base.require


def support_source():
    result = {}
    for name, (_, _, expected) in SUPPORT.items():
        path = Path(__file__).with_name(name)
        with base.regular(path, 16384) as source:
            before = base.fingerprint(os.fstat(source.fileno())); data = source.read()
            require(hashlib.sha256(data).hexdigest() == expected, 'vscode-support-sha')
            require(base.fingerprint(os.fstat(source.fileno())) == before
                and base.fingerprint(path.lstat()) == before, 'vscode-support-changed')
        result[name] = data
    return result


def installed_base(root, fd, home, prefix, previous=None):
    row = base.read_journal(fd)
    require(isinstance(row, dict) and type(row.get('schema')) is int and row['schema'] == 1
        and row.get('phase') == 'INSTALLED' and type(row.get('uid')) is int and row['uid'] == os.getuid()
        and row.get('root') == base.identity(os.fstat(fd)) and row['root'] == base.identity(root.lstat())
        and row.get('home') == str(home) and row.get('prefix') == str(prefix)
        and row.get('container') == base.CONTAINER and row.get('bundle_sha256') == base.OUTER_SHA,
        'vscode-base-identity')
    require(previous is None or previous == row, 'vscode-base-changed')
    base.check_installed(root, prefix, row)
    require(guard.selection(root) is not None, 'vscode-proot-required')
    return row


def support_snapshot(rootfs, relative):
    path = PurePosixPath(relative); fd = base.walk(rootfs, str(path.parent))
    if fd is None: return None
    try:
        try: source = base.regular(path.name, 16384, fd)
        except FileNotFoundError: return None
        with source:
            before = base.fingerprint(os.fstat(source.fileno())); hashed = base.hashed(source)
            require(before == base.fingerprint(os.fstat(source.fileno()))
                and before == base.fingerprint(os.stat(path.name, dir_fd=fd, follow_symlinks=False)))
            return dict(identity=before[:3], mode=stat.S_IMODE(before[3]), sha256=hashed)
    finally: os.close(fd)


def publish_support(rootfs, name, data):
    relative, mode, expected = SUPPORT[name]; path = PurePosixPath(relative)
    fd = base.walk(rootfs, str(path.parent), True)
    temporary = '.loopy-vscode-' + uuid.uuid4().hex
    try:
        target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW, mode, dir_fd=fd)
        with os.fdopen(target, 'wb') as output:
            output.write(data); output.flush(); os.fchmod(output.fileno(), mode); os.fsync(output.fileno())
        base.publish(fd, temporary, path.name); os.fsync(fd)
    finally:
        try: os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError: pass
        os.close(fd)
    result = support_snapshot(rootfs, relative)
    require(result is not None and result['mode'] == mode and result['sha256'] == expected,
            'vscode-support-publication')
    return result


def portable_dirs(fd):
    result = {}
    data = archive.child(fd, 'data')
    try:
        result['data'] = base.identity(os.fstat(data))
        for name in ('user-data', 'extensions'):
            child = archive.child(data, name)
            try: result[name] = base.identity(os.fstat(child))
            finally: os.close(child)
    finally: os.close(data)
    return result


def verify(rootfs, payload, row):
    parent = base.walk(rootfs, RELATIVE)
    require(parent is not None, 'vscode-version-missing')
    try:
        require(base.identity(os.fstat(parent)) == row['parentIdentity']
            and stat.S_IMODE(os.fstat(parent).st_mode) == 0o700
            and set(os.listdir(parent)) == {archive.VERSION}, 'vscode-version-parent')
        version = archive.child(parent, archive.VERSION)
        try:
            require(payload.inventory(version, portable=True) == row['directory']
                and portable_dirs(version) == row['portableDirectories'], 'vscode-version-identity')
        finally: os.close(version)
    finally: os.close(parent)
    for name, (path, mode, expected) in SUPPORT.items():
        actual = support_snapshot(rootfs, path)
        require(actual is not None and actual == row['support'][name]
            and actual['mode'] == mode and actual['sha256'] == expected, 'vscode-support-changed')


def install(payload_path, home, prefix):
    support = support_source()
    payload = archive.Payload(payload_path)  # Complete pinned archive validation before installation writes.
    fd, locks = None, []
    try:
        home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
        root = home / '.local/share/loopy-omarchy'
        rootfs = prefix / 'var/lib/proot-distro/containers' / base.CONTAINER / 'rootfs'
        fd = base.walk(home, '.local/share/loopy-omarchy')
        require(fd is not None and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700)
        before = installed_base(root, fd, home, prefix)
        for name in ('install.lock', 'runtime-control.lock'): locks.append(adapters.lock(fd, name))
        installed_base(root, fd, home, prefix, before)
        binding = dict(schema=1, uid=os.getuid(), root=base.identity(os.fstat(fd)),
            rootfs=before['rootfs_identity'], version=archive.VERSION, commit=archive.COMMIT,
            archiveSHA256=archive.SHA256, archiveBytes=archive.BYTES, manifestSHA256=payload.manifest_sha)
        row = adapters.read_record(fd, JOURNAL)
        if row is not None:
            require(isinstance(row, dict) and row.get('phase') == 'INSTALLED'
                and all(row.get(k) == v for k, v in binding.items()), 'vscode-existing-journal')
            verify(rootfs, payload, row)
            installed_base(root, fd, home, prefix, before)
            return row  # Valid idempotent check performs no writes, including portable app state.
        parent = base.walk(rootfs, RELATIVE)
        if parent is not None:
            os.close(parent); raise ValueError('vscode-existing-version-preserved')
        require(all(support_snapshot(rootfs, value[0]) is None for value in SUPPORT.values()),
                'vscode-existing-launcher-preserved')
        installed_base(root, fd, home, prefix, before)
        opt = base.walk(rootfs, 'opt', True)
        try:
            os.mkdir('loopy-vscode', 0o700, dir_fd=opt); os.fsync(opt)
            parent = archive.child(opt, 'loopy-vscode')
        finally: os.close(opt)
        try:
            stage = '.stage-' + uuid.uuid4().hex
            os.mkdir(stage, 0o700, dir_fd=parent); os.fsync(parent)
            version = archive.child(parent, stage)
            try:
                row = dict(binding, phase='STAGING', parentIdentity=base.identity(os.fstat(parent)),
                           directory=base.identity(os.fstat(version)), stage=stage)
                adapters.save_record(fd, row, journal=JOURNAL)
                payload.copy(version); payload.inventory(version)
                os.mkdir('data', 0o700, dir_fd=version)
                data = archive.child(version, 'data')
                try:
                    for name in ('user-data', 'extensions'): os.mkdir(name, 0o700, dir_fd=data)
                    os.fsync(data)
                finally: os.close(data)
                os.fsync(version)
                portable = portable_dirs(version)
                payload.inventory(version, portable=True)
                require(base.identity(os.stat(stage, dir_fd=parent, follow_symlinks=False)) == row['directory'])
                installed_base(root, fd, home, prefix, before)
                require(all(support_snapshot(rootfs, value[0]) is None for value in SUPPORT.values()),
                        'vscode-launcher-concurrent-change')
                host.publish_directory(parent, stage, archive.VERSION)
            finally: os.close(version)
        finally: os.close(parent)
        published = {name: publish_support(rootfs, name, data) for name, data in support.items()}
        final = dict(row, phase='INSTALLED', portableDirectories=portable, support=published,
            packageWrites=False, existingProfilesChanged=False, applicationLaunched=False,
            chromiumSandboxDisabledByLauncher=True)
        final.pop('stage')
        installed_base(root, fd, home, prefix, before)
        verify(rootfs, payload, final)
        adapters.save_record(fd, final, row, journal=JOURNAL)
        return final
    finally:
        # An interrupted stage/publication is evidence: retain it and reject later adoption.
        for lock in reversed(locks): os.close(lock)
        if fd is not None: os.close(fd)
        payload.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install pinned private official Linux ARM64 VS Code')
    parser.add_argument('--archive', required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(install(args.archive, os.environ['HOME'], os.environ['PREFIX']), sort_keys=True))


if __name__ == '__main__': main()
