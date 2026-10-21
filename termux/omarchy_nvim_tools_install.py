"""Install the separate, pinned Neovim helper component without profile changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import uuid

import omarchy_install as base
import omarchy_guest_install as adapters
import omarchy_nvim_tools_guest as worker
import omarchy_proot as guard
from processes import run_bounded

JOURNAL = 'nvim-tools-install.json'
GUEST_SHA = 'd1930f36192e6df534042c57281caf7383501aa53b1e24eb5701fa6548224c85'


def guest_source():
    with base.regular(Path(__file__).with_name('omarchy_nvim_tools_guest.py'), 131072) as source:
        before = base.fingerprint(os.fstat(source.fileno())); data = source.read()
        base.require(hashlib.sha256(data).hexdigest() == GUEST_SHA
                     and base.fingerprint(os.fstat(source.fileno())) == before, 'nvim-tools-worker-sha')
    compile(data, 'omarchy_nvim_tools_guest.py', 'exec')
    return data.decode()


def validate(directory):
    guest_source()
    return worker.Payload(directory, owned=True)


def system_snapshot(rootfs):
    result = {}
    for name in ('etc/pacman.conf', 'var/lib/pacman/sync/core.db', 'var/lib/pacman/sync/extra.db'):
        path = PurePosixPath(name); fd = base.walk(rootfs, str(path.parent)); base.require(fd is not None)
        try:
            with base.regular(path.name, 33554432, fd) as source:
                before = base.fingerprint(os.fstat(source.fileno())); result[name] = base.hashed(source)
                base.require(base.fingerprint(os.fstat(source.fileno())) == before)
        finally: os.close(fd)
    return result


def guest_job(prefix, home, stage, *, install=False, before=None):
    private = guard.selection(home / '.local/share/loopy-omarchy')
    base.require(private is not None, 'nvim-tools-proot-required')
    args = [str(prefix / 'bin/proot-distro'), 'login', '--isolated', '--user', 'root', '-e', 'TMPDIR=/tmp']
    env = {'HOME': str(home), 'PREFIX': str(prefix), 'TERMUX__PREFIX': str(prefix), 'TERMUX__HOME': str(home),
           'TERMUX_APP__PACKAGE_NAME': 'com.termux', 'ANDROID_ROOT': '/system', 'ANDROID_DATA': '/data',
           'PATH': str(prefix / 'bin') + ':/system/bin', 'LANG': 'C.UTF-8', 'TMPDIR': str(prefix / 'tmp')}
    env['PD_PROOT_BIN'] = str(private / 'proot')
    args += ['-e', 'PROOT_LOADER=' + str(private / 'loader'), '-e', 'PROOT_EXITKILL=1']
    args += [base.CONTAINER, '--', '/usr/bin/python3', '-c', guest_source(), '/' + stage]
    if install: args += ['--install', '--before', before]
    result = json.loads(run_bounded(args, env=env, timeout=240, max_bytes=65536))
    base.require(result.get('schema') == 1 and result.get('guestUID') == 0
                 and result.get('status') in ('verified', 'installed'), 'nvim-tools-guest-result')
    return result


def stopped(fd, root):
    """This component only supports an already stopped, guarded installation."""
    base.require(guard.selection(root) is not None, 'nvim-tools-proot-required')
    try:
        state = json.loads(worker.read(fd, 'runtime-state.json', 16384, owned=True))
    except (FileNotFoundError, json.JSONDecodeError):
        raise ValueError('nvim-tools-runtime-state') from None
    base.require(isinstance(state, dict) and type(state.get('schema')) is int and state['schema'] == 1
                 and type(state.get('uid')) is int and state['uid'] == os.getuid()
                 and state.get('root') == base.identity(os.fstat(fd))
                 and state['root'] == base.identity(root.lstat()), 'nvim-tools-runtime-state')
    base.require(state.get('phase') == 'stopped' and state.get('terminationConfirmed') is True,
                 'nvim-tools-runtime-active')
    base.require(state.get('prootExitKillRequested') is True, 'nvim-tools-runtime-guard-state')


def stage_files(rootfs, row, payload):
    fd = base.walk(rootfs, row['stage'])
    base.require(fd is not None and base.identity(os.fstat(fd)) == row['stageIdentity'])
    try:
        for name, data in dict(payload.data, **{'pacman.conf': worker.CONFIG}).items():
            with os.fdopen(os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW, 0o600, dir_fd=fd), 'wb') as output:
                output.write(data); output.flush(); os.fsync(output.fileno())
        os.fsync(fd)
    finally: os.close(fd)


def verify_stage(rootfs, row):
    name = 'nvim-tools'
    base.require(isinstance(row.get('stage'), str) and re.fullmatch('opt/loopy-' + name + '-[a-f0-9]{32}', row['stage']))
    fd = base.walk(rootfs, row['stage'])
    base.require(fd is not None)
    try:
        base.require(base.identity(os.fstat(fd)) == row['stageIdentity'] and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700)
        base.require(worker.read(fd, 'pacman.conf', 4096, owned=True) == worker.CONFIG)
        worker.Payload(rootfs / row['stage'], owned=True)
    finally: os.close(fd)


def install(directory, home, prefix):
    payload = validate(directory)
    journal = JOURNAL
    home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
    root = home / '.local/share/loopy-omarchy'; rootfs = prefix / 'var/lib/proot-distro/containers' / base.CONTAINER / 'rootfs'
    fd, locks = None, []
    try:
        fd = base.walk(home, '.local/share/loopy-omarchy')
        base.require(fd is not None and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700)
        locks.append(adapters.lock(fd, 'install.lock'))
        locks.append(adapters.lock(fd, 'runtime-control.lock'))
        installed = base.read_journal(fd)
        base.require(installed.get('schema') == 1 and installed.get('phase') == 'INSTALLED'
            and installed.get('uid') == os.getuid() and installed.get('root') == base.identity(os.fstat(fd))
            and installed.get('home') == str(home) and installed.get('prefix') == str(prefix)
            and installed.get('container') == base.CONTAINER and installed.get('bundle_sha256') == base.OUTER_SHA)
        base.check_installed(root, prefix, installed)
        stopped(fd, root)
        binding = {'schema': 1, 'uid': os.getuid(), 'root': base.identity(os.fstat(fd)),
                   'rootfs': installed['rootfs_identity'], 'manifestSHA256': payload.manifest_sha,
                   'packages': {r['name']: r['version'] for r in payload.rows}}
        row = adapters.read_record(fd, journal)
        if row is not None:
            base.require(all(row.get(k) == v for k, v in binding.items()), 'nvim-tools-journal-identity')
            base.require(row.get('phase') in ('STAGED', 'INSTALLED'), 'nvim-tools-install-uncertain')
            verify_stage(rootfs, row)
        else:
            parent = base.walk(rootfs, 'opt', True)
            name = 'loopy-nvim-tools-' + uuid.uuid4().hex
            try:
                os.mkdir(name, 0o700, dir_fd=parent)
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | base.NOFOLLOW, dir_fd=parent)
                try: stage_identity = base.identity(os.fstat(child))
                finally: os.close(child)
                os.fsync(parent)
            finally: os.close(parent)
            row = dict(binding, phase='STAGING', stage='opt/' + name, stageIdentity=stage_identity)
            adapters.save_record(fd, row, journal=journal)
            old = dict(row)
            try:
                stage_files(rootfs, row, payload); verify_stage(rootfs, row)
                row = dict(row, phase='STAGED'); adapters.save_record(fd, row, old, journal=journal)
            except BaseException:
                adapters.save_record(fd, dict(old, phase='INSTALL_UNKNOWN'), old, journal=journal)
                raise ValueError('nvim-tools-install-uncertain') from None
        before_system = system_snapshot(rootfs)
        result = guest_job(prefix, home, row['stage'])
        base.require(result['signaturesVerified'] == len(payload.rows)
                     and system_snapshot(rootfs) == before_system, 'nvim-tools-preflight-system-changed')
        stopped(fd, root)
        if row['phase'] == 'INSTALLED':
            base.require(not result['missing'], 'nvim-tools-installed-packages-changed')
            return row
        if result['missing']:
            old = dict(row); row = dict(row, phase='INSTALLING')
            adapters.save_record(fd, row, old, journal=journal)
            try:
                result = guest_job(prefix, home, row['stage'], install=True, before=result['beforeSHA256'])
                base.require(result['status'] == 'installed' and system_snapshot(rootfs) == before_system,
                             'nvim-tools-install-system-changed')
                verify_stage(rootfs, row)
            except BaseException:
                adapters.save_record(fd, dict(row, phase='INSTALL_UNKNOWN'), row, journal=journal)
                raise ValueError('nvim-tools-install-uncertain') from None
        base.require(base.identity(rootfs.lstat()) == binding['rootfs'] and base.identity(root.lstat()) == binding['root'])
        final = dict(row, phase='INSTALLED', packageWrites=result['packageWrites'],
                     signaturesVerified=result['signaturesVerified'], beforePackageCount=result['beforePackageCount'],
                     beforeSHA256=result['beforeSHA256'], afterSHA256=result.get('afterSHA256', result['beforeSHA256']),
                     systemPacmanConfigAndSyncDBUnchanged=True)
        adapters.save_record(fd, final, row, journal=journal)
        return final
    finally:
        for lock in reversed(locks): os.close(lock)
        if fd is not None: os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install seven pinned signed Neovim helper packages; preserve user profiles')
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(install(args.directory, os.environ['HOME'], os.environ['PREFIX']), sort_keys=True))


if __name__ == '__main__': sys.exit(main())
