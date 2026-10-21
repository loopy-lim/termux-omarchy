"""Separate native-Termux entry for the reviewed personal Nvim configuration."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import uuid

import omarchy_install as base
import omarchy_guest_install as adapters
import omarchy_proot as guard
import omarchy_personal_nvim_guest as worker
import omarchy_personal_nvim_plugins as plugins
from processes import identity, run_bounded, same_identity, snapshot

JOURNAL = 'personal-nvim-install.json'
GUEST_SHA = '176687214ea445d5bc9bfd39740900721c30b2111ee083abd0027e3777573102'


def guest_source():
    with base.regular(Path(__file__).with_name('omarchy_personal_nvim_guest.py'), 131072) as stream:
        data = stream.read()
        base.require(hashlib.sha256(data).hexdigest() == GUEST_SHA, 'personal-nvim-worker-sha')
    compile(data, 'omarchy_personal_nvim_guest.py', 'exec')
    return data.decode()


def context(home, prefix):
    home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
    root = home / '.local/share/loopy-omarchy'
    fd = base.walk(home, '.local/share/loopy-omarchy')
    base.require(fd is not None and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700)
    try:
        installed = base.read_journal(fd)
        base.require(installed.get('schema') == 1 and installed.get('phase') == 'INSTALLED'
            and installed.get('uid') == os.getuid() and installed.get('root') == base.identity(os.fstat(fd))
            and installed.get('home') == str(home) and installed.get('prefix') == str(prefix)
            and installed.get('container') == base.CONTAINER and installed.get('bundle_sha256') == base.OUTER_SHA)
        base.check_installed(root, prefix, installed)
        base.require(guard.selection(root) is not None, 'personal-nvim-proot-required')
        rootfs = prefix / 'var/lib/proot-distro/containers' / base.CONTAINER / 'rootfs'
        return home, prefix, root, rootfs, installed
    finally: os.close(fd)


def editor_command(record):
    """PRoot can expose a whole command in a single NUL-delimited argv field."""
    command = record.get('command') or []
    if not command: return False
    first = command[0]
    base.require(isinstance(first, str) and len(first) <= 32768, 'personal-nvim-process-command-bounds')
    names = {'nvim', 'nvim.real'}
    if len(command) > 1: return Path(first).name in names
    if len(command) == 1:
        try: tokens = shlex.split(first)
        except ValueError: tokens = first.split(None, 1)  # Folded argv may contain unescaped filename quotes.
        base.require(len(tokens) <= 256, 'personal-nvim-process-command-bounds')
        return bool(tokens and Path(tokens[0]).name in names)
    return False


def runtime_snapshot(fd, root, previous=None):
    try:
        with base.regular('runtime-state.json', 16384, fd) as stream: state = json.loads(stream.read())
    except (FileNotFoundError, json.JSONDecodeError): raise ValueError('personal-nvim-runtime-state') from None
    base.require(isinstance(state, dict) and type(state.get('schema')) is int and state['schema'] == 1
        and type(state.get('uid')) is int and state['uid'] == os.getuid()
        and state.get('root') == base.identity(os.fstat(fd)) and state['root'] == base.identity(root.lstat()),
        'personal-nvim-runtime-state')
    base.require(state.get('prootExitKillRequested') is True, 'personal-nvim-runtime-active')
    if state.get('phase') == 'stopped':
        base.require(state.get('terminationConfirmed') is True, 'personal-nvim-runtime-active')
    else:
        records = state.get('processes')
        base.require(state.get('phase') == 'ready' and state.get('terminationConfirmed') is not True
            and isinstance(records, list) and len(records) == 4 and isinstance(state.get('hyprland'), dict),
            'personal-nvim-runtime-active')
        records = [*records, state['hyprland'], *[state[k] for k in ('audioProcess', 'androidProcess') if state.get(k)]]
        for record in records:
            base.require(isinstance(record, dict) and type(record.get('pid')) is int
                and same_identity(record, identity(record['pid'], strict=True)), 'personal-nvim-runtime-process-changed')
        for record in snapshot().values():
            base.require(not editor_command(record), 'personal-nvim-editor-active')
    stable = {k: state.get(k) for k in ('phase', 'token', 'display', 'session', 'runtime', 'processes',
        'hyprland', 'audioProcess', 'androidProcess', 'terminationConfirmed', 'prootExitKillRequested')}
    base.require(previous is None or stable == previous, 'personal-nvim-runtime-changed')
    return stable


def preflight(directory, home, prefix, *, plugin_directory=None):
    guest_source(); payload = worker.Payload(directory)
    plugin_payload = plugins.Payload(plugin_directory) if plugin_directory is not None else None
    home, prefix, root, rootfs, installed = context(home, prefix)
    target_home = rootfs / 'home/omarchy'
    fd = base.walk(rootfs, 'home/omarchy/.config')
    try:
        try: info = os.stat('nvim', dir_fd=fd, follow_symlinks=False) if fd is not None else None
        except FileNotFoundError: info = None
        if info is not None:
            base.require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o022,
                         'personal-nvim-target-directory')
    finally:
        if fd is not None: os.close(fd)
    # Native PRoot files expose the Termux UID; final owner checks run as guest omarchy.
    return {'schema': 1, 'status': 'verified-native', 'configState': 'absent' if info is None else 'present',
        'manifestSHA256': worker.MANIFEST_SHA, 'lockedPlugins': len(payload.lock),
        'configWrites': False, 'networkRequested': False, 'guestVerificationRequired': True,
        'pluginSourcePayloadVerified': plugin_payload is not None, **worker.plugin_state(target_home, payload.lock)}


def guest_job(prefix, home, stage, *, install=False, before=None):
    private = guard.selection(home / '.local/share/loopy-omarchy')
    base.require(private is not None, 'personal-nvim-proot-required')
    args = [str(prefix / 'bin/proot-distro'), 'login', '--isolated', '--user', 'omarchy', '-e', 'TMPDIR=/tmp',
        '-e', 'PROOT_TMP_DIR=' + str(prefix / 'tmp'), '-e', 'PROOT_LOADER=' + str(private / 'loader'), '-e', 'PROOT_EXITKILL=1',
        base.CONTAINER, '--', '/usr/bin/python3', '-c', guest_source(), '/' + stage]
    if install: args += ['--install', '--before', before]
    env = {'HOME': str(home), 'PREFIX': str(prefix), 'TERMUX__PREFIX': str(prefix), 'TERMUX__HOME': str(home),
        'TERMUX_APP__PACKAGE_NAME': 'com.termux', 'ANDROID_ROOT': '/system', 'ANDROID_DATA': '/data',
        'PATH': str(prefix / 'bin') + ':/system/bin', 'LANG': 'C.UTF-8', 'TMPDIR': str(prefix / 'tmp'),
        'PD_PROOT_BIN': str(private / 'proot'), 'PROOT_TMP_DIR': str(prefix / 'tmp')}
    result = json.loads(run_bounded(args, env=env, timeout=90, max_bytes=65536))
    base.require(result.get('schema') == 1 and type(result.get('guestUID')) is int and result['guestUID'] > 0
        and result.get('status') in ('verified', 'installed', 'preserved-existing')
        and result.get('manifestSHA256') == worker.MANIFEST_SHA and result.get('networkRequested') is False,
        'personal-nvim-guest-result')
    return result


def verify_stage(rootfs, row):
    base.require(isinstance(row.get('stage'), str)
        and re.fullmatch('opt/loopy-personal-nvim-[a-f0-9]{32}', row['stage']), 'personal-nvim-stage')
    fd = base.walk(rootfs, row['stage']); base.require(fd is not None)
    try:
        base.require(base.identity(os.fstat(fd)) == row['stageIdentity'] and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700)
        worker.Payload(rootfs / row['stage'])
    finally: os.close(fd)


def install(directory, home, prefix, *, plugin_directory=None):
    guest_source(); payload = worker.Payload(directory)
    if plugin_directory is not None: plugins.Payload(plugin_directory)
    home, prefix, root, rootfs, installed = context(home, prefix)
    fd = base.walk(home, '.local/share/loopy-omarchy'); locks = []
    try:
        locks.append(adapters.lock(fd, 'install.lock')); locks.append(adapters.lock(fd, 'runtime-control.lock'))
        runtime = runtime_snapshot(fd, root)
        binding = {'schema': 1, 'uid': os.getuid(), 'root': base.identity(os.fstat(fd)),
            'rootfs': installed['rootfs_identity'], 'manifestSHA256': worker.MANIFEST_SHA,
            'pluginsManifestSHA256': plugins.MANIFEST_SHA if plugin_directory is not None else None}
        row = adapters.read_record(fd, JOURNAL)
        if row is not None:
            base.require(all(row.get(k) == v for k, v in binding.items()), 'personal-nvim-journal-identity')
            base.require(row.get('phase') in ('STAGED', 'INSTALLED', 'PRESERVED'), 'personal-nvim-install-uncertain')
            verify_stage(rootfs, row)
        else:
            parent = base.walk(rootfs, 'opt', True); name = 'loopy-personal-nvim-' + uuid.uuid4().hex
            try:
                os.mkdir(name, 0o700, dir_fd=parent)
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | base.NOFOLLOW, dir_fd=parent)
                try: identity = base.identity(os.fstat(child))
                finally: os.close(child)
            finally: os.close(parent)
            row = dict(binding, phase='STAGING', stage='opt/' + name, stageIdentity=identity)
            adapters.save_record(fd, row, journal=JOURNAL)
            try:
                for relative, data in payload.data.items():
                    path = PurePosixPath(relative); parent = base.walk(rootfs / row['stage'], str(path.parent), True)
                    try: worker.create(parent, path.name, data)
                    finally: os.close(parent)
                verify_stage(rootfs, row)
                staged = dict(row, phase='STAGED'); adapters.save_record(fd, staged, row, journal=JOURNAL); row = staged
            except BaseException:
                adapters.save_record(fd, dict(row, phase='INSTALL_UNKNOWN'), row, journal=JOURNAL)
                raise ValueError('personal-nvim-install-uncertain') from None
        result = guest_job(prefix, home, row['stage'])
        runtime_snapshot(fd, root, runtime)
        if row['phase'] in ('INSTALLED', 'PRESERVED'):
            expected = 'managed' if row['phase'] == 'INSTALLED' else 'existing'
            base.require(result.get('configState') == expected, 'personal-nvim-installed-state-changed')
            if plugin_directory is not None and row['phase'] == 'INSTALLED':
                plugins.install(plugin_directory, rootfs / 'home/omarchy')
            runtime_snapshot(fd, root, runtime)
            return row
        installing = dict(row, phase='INSTALLING'); adapters.save_record(fd, installing, row, journal=JOURNAL)
        try:
            plugin_result = None
            runtime_snapshot(fd, root, runtime)
            if plugin_directory is not None and result['configState'] != 'existing':
                plugin_result = plugins.install(plugin_directory, rootfs / 'home/omarchy')
            result = guest_job(prefix, home, row['stage'], install=True, before=result['beforeSHA256'])
            runtime_snapshot(fd, root, runtime); verify_stage(rootfs, row)
            base.require(base.identity(rootfs.lstat()) == binding['rootfs'] and base.identity(root.lstat()) == binding['root'])
        except BaseException:
            adapters.save_record(fd, dict(installing, phase='INSTALL_UNKNOWN'), installing, journal=JOURNAL)
            raise ValueError('personal-nvim-install-uncertain') from None
        final = dict(installing, phase='PRESERVED' if result['status'] == 'preserved-existing' else 'INSTALLED',
            configWrites=result['configWrites'], guestUID=result['guestUID'], networkRequested=False, runtimePhase=runtime['phase'],
            pluginResult=plugin_result, missingPlugins=result['missingPlugins'], pluginEvidence=result['pluginEvidence'])
        adapters.save_record(fd, final, installing, journal=JOURNAL)
        return final
    finally:
        for lock in reversed(locks): os.close(lock)
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--plugins', type=Path)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args(argv)
    action = preflight if args.preflight else install
    print(json.dumps(action(args.directory, os.environ['HOME'], os.environ['PREFIX'],
                            plugin_directory=args.plugins), sort_keys=True))


if __name__ == '__main__': main()
