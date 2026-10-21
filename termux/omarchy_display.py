#!/data/data/com.termux/files/usr/bin/python3
"""Apply paired X11/Hyprland/app density while the managed desktop is stopped."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

PROFILES = {'hidpi': (100, 2.5), 'performance': (200, 1.25)}
BEGIN = '-- BEGIN LOOPY DISPLAY DENSITY\n'
END = '-- END LOOPY DISPLAY DENSITY\n'


def transform(monitors, flags, scale):
    monitors, count = re.subn(r'^local omarchy_monitor_scale = [0-9.]+$',
                             f'local omarchy_monitor_scale = {scale}', monitors, flags=re.M)
    if count != 1:
        raise ValueError('Expected exactly one Omarchy monitor scale declaration')
    block = BEGIN + 'hl.config({ xwayland = { force_zero_scaling = true } })\n' + END
    if BEGIN in monitors:
        if monitors.count(BEGIN) != 1 or monitors.count(END) != 1:
            raise ValueError('Invalid managed display block')
        monitors = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END), block, monitors, flags=re.S)
    else:
        monitors += '\n' + block
    # Keep all existing Chromium GPU, extension and user flags.
    flags = re.sub(r'^--force-device-scale-factor=[^\n]*\n?', '', flags, flags=re.M)
    flags = flags.rstrip() + f'\n--force-device-scale-factor={scale}\n'
    return monitors, flags


def atomic_write(path, content):
    temp = path.with_name(path.name + '.loopy-display-tmp')
    with temp.open('x') as out:
        os.chmod(temp, path.stat().st_mode & 0o777)
        out.write(content)
        out.flush()
        os.fsync(out.fileno())
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=PROFILES)
    args = parser.parse_args()
    home = Path(os.environ['HOME'])
    prefix = Path(os.environ['PREFIX'])
    root = home / '.local/share/loopy-omarchy'
    lock = os.open(root / 'display.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = json.loads((root / 'runtime-state.json').read_text())
    if state.get('terminationConfirmed') is not True:
        raise ValueError('Save work and run loopy-omarchy stop before changing density')
    guest = prefix / 'var/lib/proot-distro/containers/loopy-omarchy/rootfs/home/omarchy'
    paths = [guest / '.config/hypr/monitors.lua', guest / '.config/chromium-flags.conf']
    for path in paths:
        if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid():
            raise ValueError('Unexpected display configuration ownership')
    before = [path.read_text() for path in paths]
    percent, scale = PROFILES[args.profile]
    after = transform(*before, scale)
    command = str(prefix / 'bin/termux-x11-preference')
    # The Android preference helper needs the regular Termux environment.
    output = subprocess.run([command, 'list'], capture_output=True, text=True, timeout=15, check=True).stdout
    prefs = dict(re.findall(r'^"([A-Za-z0-9]+)"="([^"\n]*)"$', output, re.M))
    if prefs.get('storeSecondaryDisplayPreferencesSeparately') != 'false':
        raise ValueError('Separate external-display preferences need a separate profile')
    backup = root / 'display-before.json'
    if not backup.exists():
        with backup.open('x') as out:
            os.chmod(backup, 0o600)
            json.dump({'files': dict(zip(map(str, paths), before)), 'preferences': {
                key: prefs[key] for key in ('displayResolutionMode', 'displayScale')}}, out, indent=2)
    # Retain the backup if Android reports a partial preference update.
    subprocess.run([command, 'displayResolutionMode:scaled', f'displayScale:{percent}'],
                   capture_output=True, text=True, timeout=15, check=True)
    check = subprocess.run([command, 'list'], capture_output=True, text=True, timeout=15, check=True).stdout
    if f'"displayScale"="{percent}"' not in check or '"displayResolutionMode"="scaled"' not in check:
        raise ValueError('Android density update was not confirmed; backup retained')
    if [path.read_text() for path in paths] != before:
        raise ValueError('Display configuration changed during update; backup retained')
    if json.loads((root / 'runtime-state.json').read_text()).get('terminationConfirmed') is not True:
        raise ValueError('Desktop started during update; stop it before retrying')
    for path, content in zip(paths, after):
        atomic_write(path, content)
    print(json.dumps({'profile': args.profile, 'displayScale': percent, 'desktopScale': scale,
                      'sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                      'next': 'loopy-omarchy start'}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'incomplete', 'reason': str(error),
                          'recovery': 'Check display-before.json if settings changed before this error'}), file=sys.stderr)
        raise SystemExit(2)
