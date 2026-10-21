#!/data/data/com.termux/files/usr/bin/python3 -I
"""Short Termux command for the existing pinned native Omarchy launcher."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

HOME = Path('/data/data/com.termux/files/home')
PREFIX = Path('/data/data/com.termux/files/usr')
PROC_STATUS = Path('/proc/self/status')
BUNDLE_SHA = '7e9f1cd67533bc0d3988b5cb3831aef52f1527dd90391d9d868ed9345021cdb2'
RUNTIME_SHA = {
    'omarchy_proot.py': '4240de2a165af00be564f449c047a0e46614f4e9f4e1943756aa5d20f6e4d03a',
    'omarchy_commands.py': '12ea29e0358e2ca435888d5c2319490495a322c32192b6d8b257faeefc9b46fa',
    'omarchy.py': '304996e5d33c770a4d9cf2c28c6309bc0843af9d283b99a50d93d0e88707909f',
    'processes.py': 'cda6028651ccb08a55bacf91c68186e4e9189bf9456cfd79ca587f354d3c946e',
    'omarchy_runtime.py': '976fa75c259ecf97c0b105786f0f22e0f4245a0d2e51e549da5e57c7510dd4d4',
    'omarchy_resources.py': 'e3276fcdd7af97cdc7286d7f694cac5bf9eff2d7b87dda679f661ef52499fff3',
    'omarchy_boot.py': '2966eeaf3b02c593a2638f2a13f0e3c069c43899e6da66b5bab37991b38f0203',
    'omarchy_input.py': 'baa102398d8b1525f5061eaccf27bad84b668d57e7875a59758eeda999df3389',
    'omarchy_audio.py': '3cebf98a8ee56f4b37a8edc2ccba8a481b303589d6dc4f188797f9309e7fe105',
    'omarchy_android.py': '89fb4bb6cb2c76e0350ea460303479ac2d076834b80674d0adb357f7c0b34fad',
    'omarchy_android_client.py': '6b0e9308e2b88337309450b7d32a3bc2963dbd4fcfbaf50c1e82dace20cb3823',
}
NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC


def require(value, reason='terminal-command-boundary'):
    if not value: raise ValueError(reason)


def identity(row):
    return [row.st_dev, row.st_ino, row.st_uid]


def fingerprint(row):
    return identity(row) + [row.st_mode, row.st_size, row.st_mtime_ns, row.st_ctime_ns, row.st_nlink]


def native_uid():
    with PROC_STATUS.open('r') as source: text = source.read(65537)
    fields = re.findall(r'^Uid:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', text, re.MULTILINE)
    uid = os.getuid()
    require(len(text) <= 65536 and len(fields) == 1 and uid > 0 and os.geteuid() == uid
            and all(int(value) == uid for value in fields[0]), 'terminal-native-uid')
    return uid


def directory(path, dir_fd=None):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=dir_fd)
    try:
        row = os.fstat(fd)
        require(row.st_uid == os.getuid() and not row.st_mode & 0o022, 'terminal-directory')
        return fd
    except BaseException:
        os.close(fd); raise


def walk(root, relative):
    fd = directory(root)
    try:
        for part in relative.split('/'):
            child = directory(part, fd)
            os.close(fd); fd = child
        result, fd = fd, None
        return result
    finally:
        if fd is not None: os.close(fd)


def read(path, maximum, dir_fd=None):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW, dir_fd=dir_fd)
    with os.fdopen(fd, 'rb') as stream:
        before = fingerprint(os.fstat(stream.fileno()))
        require(stat.S_ISREG(before[3]) and before[2] == os.getuid() and before[-1] == 1
                and not before[3] & 0o022 and before[4] <= maximum, 'terminal-file')
        data = stream.read(maximum + 1)
        require(len(data) <= maximum and fingerprint(os.fstat(stream.fileno())) == before
                and fingerprint(os.stat(path, dir_fd=dir_fd, follow_symlinks=False)) == before,
                'terminal-file-changed')
        return data


def context(home, prefix):
    uid = native_uid()
    home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
    root = home / '.local/share/loopy-omarchy'
    fd = walk(home, '.local/share/loopy-omarchy')
    try:
        require(stat.S_IMODE(os.fstat(fd).st_mode) == 0o700, 'terminal-root-mode')
        raw = read('install.json', 32768, fd)
        row = json.loads(raw)
        expected = dict(schema=1, phase='INSTALLED', uid=uid, root=identity(os.fstat(fd)),
                        home=str(home), prefix=str(prefix), container='loopy-omarchy',
                        bundle_sha256=BUNDLE_SHA, runtime_files=RUNTIME_SHA)
        require(isinstance(row, dict) and all(row.get(key) == value for key, value in expected.items()),
                'terminal-install-identity')
        require(identity(root.lstat()) == expected['root'], 'terminal-root-changed')
        for name, expected_sha in RUNTIME_SHA.items():
            require(hashlib.sha256(read(name, 131072, fd)).hexdigest() == expected_sha,
                    'terminal-runtime-sha')
    finally: os.close(fd)
    for relative, field in [('var/lib/proot-distro/containers/loopy-omarchy', 'container_identity'),
                            ('var/lib/proot-distro/containers/loopy-omarchy/rootfs', 'rootfs_identity')]:
        fd = walk(prefix, relative)
        try: require(identity(os.fstat(fd)) == row.get(field), 'terminal-rootfs-identity')
        finally: os.close(fd)
    fd = walk(prefix, 'bin')
    os.close(fd)
    interpreter = (prefix / 'bin/python3').resolve(strict=True)
    require(interpreter.is_relative_to(prefix), 'terminal-interpreter')
    read(interpreter, 32 * 1024 * 1024)
    require(interpreter.lstat().st_mode & 0o100, 'terminal-interpreter')
    return dict(uid=uid, home=str(home), prefix=str(prefix), root=str(root),
                rootIdentity=expected['root'], interpreter=str(interpreter),
                installSHA256=hashlib.sha256(raw).hexdigest())


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args in (['--help'], ['-h']):
        print('Usage: loopy-omarchy [start|stop|status|doctor] (default: start)')
        return 0
    require(len(args) <= 1 and (not args or args[0] in ('start', 'stop', 'status', 'doctor')),
            'terminal-action')
    checked = context(HOME, PREFIX)
    env = os.environ.copy()
    for name in ('PYTHONPATH', 'PYTHONHOME'): env.pop(name, None)
    env.update(HOME=checked['home'], PREFIX=checked['prefix'], TERMUX__HOME=checked['home'],
               TERMUX__PREFIX=checked['prefix'])
    interpreter = checked['interpreter']
    os.execve(interpreter, [interpreter, str(Path(checked['root']) / 'omarchy.py'), args[0] if args else 'start'], env)


if __name__ == '__main__':
    try: sys.exit(main())
    except (ValueError, OSError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[a-z0-9-]{1,64}', str(error)) else 'terminal-unavailable'
        print(json.dumps(dict(schema=1, status='failed', reason=reason), sort_keys=True))
        sys.exit(1)
