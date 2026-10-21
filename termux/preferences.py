"""Explicit Termux:X11 preset; restore only values still owned by this preset."""
import re
from processes import atomic_json, read_json, run_bounded

PRESET = {'fullscreen': 'true', 'pointerCapture': 'true', 'preferScancodes': 'false',
          'hardwareKbdScancodesWorkaround': 'false', 'showAdditionalKbd': 'false', 'showIMEWhileExternalConnected': 'false',
          'pauseKeyInterceptingWithEsc': 'true'}
# Upstream allows five seconds for the X11 Activity; include cold ART startup.
COMMAND_TIMEOUT = 7


def restore_values(before, applied, current):
    return {key: value for key, value in before.items()
            if key in PRESET and current.get(key) == applied.get(key)}


def read_preferences(command, env):
    text = run_bounded([str(command), 'list'], env=env, timeout=COMMAND_TIMEOUT, max_bytes=32768)
    pairs = dict(re.findall(r'^"([A-Za-z0-9]+)"="([^"\n]*)"$', text, re.MULTILINE))
    if any(pairs.get(key) not in ('true', 'false') for key in PRESET):
        raise ValueError('X11 preference snapshot is incomplete')
    if pairs.get('storeSecondaryDisplayPreferencesSeparately') == 'true':
        raise ValueError('separate X11 window preferences require manual setup')
    return pairs


def apply(command, root, env):
    snapshot = root / 'input.json'
    if read_json(snapshot) is not None:
        raise ValueError('input snapshot already exists; restore it first')
    before = read_preferences(command, env)
    owned = {k: before[k] for k in PRESET}
    atomic_json(snapshot, {'before': owned, 'applied': PRESET})
    try:
        run_bounded([str(command), *(f'{k}:{v}' for k, v in PRESET.items())], env=env, timeout=COMMAND_TIMEOUT)
        current = read_preferences(command, env)
        if any(current.get(k) != v for k, v in PRESET.items()):
            raise ValueError('X11 did not accept the input preset')
    except Exception:
        # Preserve snapshot even after partial application for explicit restore.
        raise
    return {'changedKeys': list(PRESET), 'accessibilityGranted': False}


def restore(command, root, env):
    path = root / 'input.json'
    snapshot = read_json(path)
    if snapshot is None:
        return {'changedKeys': []}
    current = read_preferences(command, env)
    changes = restore_values(snapshot['before'], snapshot['applied'], current)
    if changes:
        run_bounded([str(command), *(f'{k}:{v}' for k, v in changes.items())], env=env, timeout=COMMAND_TIMEOUT)
        after = read_preferences(command, env)
        if any(after.get(k) != v for k, v in changes.items()):
            raise ValueError('X11 did not restore the owned input keys')
    path.unlink()
    return {'changedKeys': list(changes), 'preservedUserEdits': True}
