#!/data/data/com.termux/files/usr/bin/python3
"""Reversible Omarchy input profile with the upstream keyboard-service launch path."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

from processes import atomic_json, read_json, run_bounded

PRESET = {'fullscreen': 'true', 'pointerCapture': 'true', 'preferScancodes': 'true',
          'hardwareKbdScancodesWorkaround': 'false', 'showAdditionalKbd': 'false',
          'showIMEWhileExternalConnected': 'false', 'pauseKeyInterceptingWithEsc': 'false',
          'filterOutWinkey': 'false', 'enforceCharBasedInput': 'false',
          'enableAccessibilityServiceAutomatically': 'true'}
AUTO_SERVICE = 'enableAccessibilityServiceAutomatically'
LEGACY_PRESET = {key: value for key, value in PRESET.items() if key != AUTO_SERVICE}
SECONDARY = 'storeSecondaryDisplayPreferencesSeparately'
COMMAND_TIMEOUT = 7  # Includes the upstream Activity wait and cold ART startup.


class InputFailure(ValueError):
    pass


@contextmanager
def locked(root):
    root = Path(root)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise InputFailure('input-root-ownership')
    fd = os.open(root / 'omarchy-input.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as lock:
        info = os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise InputFailure('input-lock-ownership')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise InputFailure('input-command-busy') from error
        yield root


def read_preferences(command, env):
    try:
        text = run_bounded([str(command), 'list'], env=env, timeout=COMMAND_TIMEOUT, max_bytes=32768)
    except (OSError, ValueError) as error:
        raise InputFailure('input-query-unavailable') from error
    rows = re.findall(r'^"([A-Za-z0-9]+)"="([^"\n]*)"$', text, re.MULTILINE)
    keys = (*PRESET, SECONDARY)
    if any(sum(k == key for k, _ in rows) != 1 for key in keys):
        raise InputFailure('input-snapshot-incomplete')
    values = dict(rows)
    if any(values[key] not in ('true', 'false') for key in keys):
        raise InputFailure('input-snapshot-invalid')
    if values[SECONDARY] != 'false':
        raise InputFailure('input-separate-display-preferences')
    return {key: values[key] for key in PRESET}


def restore_values(before, applied, current):
    return {key: value for key, value in before.items()
            if key in PRESET and current.get(key) == applied.get(key)}


def snapshot(root):
    value = read_json(root / 'omarchy-input.json')
    if value is None:
        return None
    applied = value.get('applied')
    if value.get('schema') != 1 or value.get('uid') != os.getuid() \
            or value.get('profile') != 'omarchy-wayland' or applied not in (PRESET, LEGACY_PRESET) \
            or not isinstance(value.get('before'), dict) or set(value['before']) != set(applied) \
            or any(v not in ('true', 'false') for v in value['before'].values()):
        raise InputFailure('input-owner-snapshot-invalid')
    return value


def write_preferences(command, changes, env):
    try:
        run_bounded([str(command), *(f'{key}:{value}' for key, value in changes.items())],
                    env=env, timeout=COMMAND_TIMEOUT, max_bytes=32768)
    except (OSError, ValueError) as error:
        raise InputFailure('input-write-unconfirmed') from error


def input_result(changes):
    return {'changedKeys': list(changes), 'keyboardInterceptionPausedByEscape': False,
            'upstreamEscapeMayReleasePointerCapture': True, 'androidPermissionGrantsChanged': False,
            'accessibilityAutoLaunch': True}


def apply_locked(command, root, env):
    if os.path.lexists(root / 'omarchy-input.json'):
        raise InputFailure('input-snapshot-existing-restore-first')
    before = read_preferences(command, env)
    atomic_json(root / 'omarchy-input.json', {'schema': 1, 'uid': os.getuid(),
                'profile': 'omarchy-wayland', 'before': before, 'applied': PRESET})
    write_preferences(command, PRESET, env)
    if read_preferences(command, env) != PRESET:
        raise InputFailure('input-apply-unconfirmed')  # Retain the originals after partial application.
    return input_result(PRESET)


def apply(command, root, env):
    with locked(root) as root:
        return apply_locked(command, root, env)


def ensure(command, root, env):
    with locked(root) as root:
        value = snapshot(root)
        if value is None:
            return apply_locked(command, root, env)
        current = read_preferences(command, env)
        if any(current[key] != val for key, val in value['applied'].items()):
            raise InputFailure('input-owned-profile-changed')
        if value['applied'] == PRESET:
            return input_result({})
        if snapshot(root) != value:
            raise InputFailure('input-snapshot-changed')
        upgraded = dict(value, before={**value['before'], AUTO_SERVICE: current[AUTO_SERVICE]},
                        applied=PRESET)
        atomic_json(root / 'omarchy-input.json', upgraded)
        changes = {AUTO_SERVICE: 'true'} if current[AUTO_SERVICE] != 'true' else {}
        if changes:
            write_preferences(command, changes, env)
        if read_preferences(command, env) != PRESET:
            raise InputFailure('input-apply-unconfirmed')
        return input_result(changes)


def restore(command, root, env):
    with locked(root) as root:
        value = snapshot(root)
        if value is None:
            return {'changedKeys': [], 'preservedUserEdits': True, 'androidPermissionGrantsChanged': False}
        current = read_preferences(command, env)
        changes = restore_values(value['before'], value['applied'], current)
        if changes:
            write_preferences(command, changes, env)
            after = read_preferences(command, env)
            if any(after[key] != val for key, val in changes.items()):
                raise InputFailure('input-restore-unconfirmed')
        if snapshot(root) != value:
            raise InputFailure('input-snapshot-changed')
        (root / 'omarchy-input.json').unlink()
        return {'changedKeys': list(changes), 'preservedUserEdits': True,
                'androidPermissionGrantsChanged': False}


def main():
    action, request = (sys.argv + ['', ''])[1:3]
    value = {'schema': 1, 'uid': os.getuid(), 'action': action[:16], 'request': request[:36]}
    try:
        if len(sys.argv) != 3 or action not in ('apply', 'ensure', 'restore') \
                or len(request) != 36 or str(uuid.UUID(request)) != request:
            raise InputFailure('input-arguments-invalid')
        home = Path('/data/data/com.termux/files/home').resolve()
        prefix = Path('/data/data/com.termux/files/usr').resolve()
        root = home / '.local/share/loopy-omarchy'
        env = dict(os.environ, HOME=str(home), PREFIX=str(prefix), TERMUX__HOME=str(home),
                   TERMUX__PREFIX=str(prefix), PATH=f'{prefix}/bin:/system/bin', TMPDIR=str(prefix / 'tmp'))
        operation = {'apply': apply, 'ensure': ensure, 'restore': restore}[action]
        result = operation(prefix / 'bin/termux-x11-preference', root, env)
        value.update(result, status={'apply': 'applied', 'ensure': 'ensured', 'restore': 'restored'}[action])
    except Exception as error:
        value.update(status='failed', reason=str(error) if isinstance(error, InputFailure) else 'input-operation-failed')
    print(json.dumps(value, ensure_ascii=True, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
