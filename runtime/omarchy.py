#!/data/data/com.termux/files/usr/bin/python3
"""Fixed launcher for the separately installed, owned Termux Omarchy session."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import uuid

from processes import run_bounded

HOME = Path('/data/data/com.termux/files/home')
PREFIX = Path('/data/data/com.termux/files/usr')
ACTIONS = frozenset(('start', 'stop', 'status', 'doctor'))


class Failure(ValueError):
    pass


def directory(path):
    value = path.lstat()
    if not stat.S_ISDIR(value.st_mode) or value.st_uid != os.getuid() or value.st_mode & 0o022:
        raise Failure('launcher-directory')


def regular(path, maximum):
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_uid != os.getuid() \
            or value.st_nlink != 1 or value.st_mode & 0o022 or value.st_size > maximum:
        raise Failure('launcher-file')
    return value


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1 or args and args[0] not in ACTIONS:
        raise Failure('launcher-action')
    action = args[0] if args else 'start'
    home, prefix = HOME.resolve(strict=True), PREFIX.resolve(strict=True)
    directory(home)
    directory(prefix)
    managed = home
    for part in ('.local', 'share', 'loopy-omarchy'):
        managed /= part
        directory(managed)
    if stat.S_IMODE(managed.lstat().st_mode) != 0o700:
        raise Failure('launcher-managed-mode')
    for name in ('omarchy_runtime.py', 'omarchy_resources.py', 'processes.py'):
        regular(managed / name, 131072)
    regular(managed / 'install.json', 16384)
    interpreter = prefix / 'bin/python3'
    resolved = interpreter.resolve(strict=True)
    if not resolved.is_relative_to(prefix) or not regular(resolved, 32 * 1024 * 1024).st_mode & 0o100:
        raise Failure('launcher-interpreter')
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env.update(HOME=str(home), PREFIX=str(prefix), TERMUX__HOME=str(home), TERMUX__PREFIX=str(prefix))
    if action == 'start':
        regular(managed / 'omarchy_input.py', 131072)
        activity = prefix / 'bin/am'
        if not regular(activity, 65536).st_mode & 0o100:
            raise Failure('launcher-activity-unavailable')
        try:
            foreground = subprocess.run(
                [str(activity), 'start', '-n', 'com.termux.x11/com.termux.x11.MainActivity'],
                shell=False, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=7, check=False)
        except subprocess.TimeoutExpired:
            raise Failure('launcher-activity-timeout') from None
        except OSError:
            raise Failure('launcher-activity-unavailable') from None
        if foreground.returncode != 0:
            raise Failure('launcher-activity-unavailable')
        request = str(uuid.uuid4())
        try:
            output = run_bounded([str(interpreter), str(managed / 'omarchy_input.py'),
                                  'ensure', request], env=env, timeout=25, max_bytes=4096)
            value = json.loads(output)
        except (OSError, ValueError):
            raise Failure('launcher-input-unavailable') from None
        if not isinstance(value, dict) or value.get('schema') != 1 \
                or value.get('uid') != os.getuid() or value.get('action') != 'ensure' \
                or value.get('request') != request or value.get('status') != 'ensured':
            raise Failure('launcher-input-unconfirmed')
    os.execve(str(interpreter), [str(interpreter), str(managed / 'omarchy_runtime.py'),
                                action, str(uuid.uuid4())], env)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        reason = str(error) if isinstance(error, Failure) else 'launcher-unavailable'
        print(json.dumps({'schema': 1, 'status': 'failed', 'reason': reason}, separators=(',', ':')),
              flush=True)
        sys.exit(1)
