#!/data/data/com.termux/files/usr/bin/python3
"""Fixed launcher for the separately installed, owned Termux Omarchy session."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import uuid

from processes import run_bounded

HOME = Path('/data/data/com.termux/files/home')
PREFIX = Path('/data/data/com.termux/files/usr')
ACTIONS = frozenset(('start', 'stop', 'status', 'doctor'))
ACTIVITY_ATTEMPTS = 2  # The first activity start after boot may race the am socket or cold ART.
ACTIVITY_BACKOFF = 2.0
ENSURE_TIMEOUT = 40  # Warmup query (2×7s + backoff), write, and confirm must all fit.


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
        # Phase timing for re-entry attribution (tools/measure_termux_reentry.py);
        # runtime cost is the residual between totalMs and these two phases.
        phases, phase_start = {'activityStartMs': None, 'ensureMs': None}, time.monotonic()
        entry_clock = phase_start
        for attempt in range(ACTIVITY_ATTEMPTS):
            try:
                foreground = subprocess.run(
                    [str(activity), 'start', '-n', 'com.termux.x11/com.termux.x11.MainActivity'],
                    shell=False, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=7, check=False)
            except subprocess.TimeoutExpired:
                raise Failure('launcher-activity-timeout') from None
            except OSError:
                raise Failure('launcher-activity-unavailable') from None
            if foreground.returncode == 0:
                break
            if attempt + 1 == ACTIVITY_ATTEMPTS:
                raise Failure('launcher-activity-unavailable')
            time.sleep(ACTIVITY_BACKOFF)  # Transient first-start refusals recover once the service is warm.
        phases['activityStartMs'] = round((time.monotonic() - phase_start) * 1000)
        phase_start = time.monotonic()
        request = str(uuid.uuid4())
        try:
            output = run_bounded([str(interpreter), str(managed / 'omarchy_input.py'),
                                  'ensure', request], env=env, timeout=ENSURE_TIMEOUT, max_bytes=4096)
            value = json.loads(output)
        except (OSError, ValueError):
            raise Failure('launcher-input-unavailable') from None
        if not isinstance(value, dict) or value.get('schema') != 1 \
                or value.get('uid') != os.getuid() or value.get('action') != 'ensure' \
                or value.get('request') != request or value.get('status') != 'ensured':
            raise Failure('launcher-input-unconfirmed')
        phases['ensureMs'] = round((time.monotonic() - phase_start) * 1000)
        phases['totalMs'] = round((time.monotonic() - entry_clock) * 1000)
        # Emitted before execve so the runtime status JSON stays the final line.
        print(json.dumps(dict(schema=1, status='phases', **phases), separators=(',', ':')), flush=True)
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
