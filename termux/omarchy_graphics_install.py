#!/data/data/com.termux/files/usr/bin/python3
"""Install the verified Y900 AHB driver after the owned desktop is stopped."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat

from omarchy_install import RUNTIME_SHA

DRIVER_SHA = '7f05d872e36f32fc130477fb2d6c01da88715dd97b22155bbbca4945092c14d1'


def read(path, maximum):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('graphics-symlink')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as f:
        row = os.fstat(f.fileno())
        if not stat.S_ISREG(row.st_mode) or row.st_uid != os.getuid() \
                or row.st_mode & 0o022 or row.st_size > maximum:
            raise ValueError('graphics-file')
        return f.read(maximum + 1)


def install(root, driver):
    data = read(driver, 32 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != DRIVER_SHA:
        raise ValueError('graphics-driver-sha')
    if root.is_symlink() or stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise ValueError('graphics-root')
    with os.fdopen(os.open(root / 'runtime-control.lock', os.O_RDWR | os.O_NOFOLLOW), 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads(read(root / 'runtime-state.json', 131072))
        if state.get('phase') != 'stopped' or state.get('terminationConfirmed') is not True:
            raise ValueError('save-work-and-stop-desktop-first')
        for name, expected in RUNTIME_SHA.items():
            if hashlib.sha256(read(root / name, 131072)).hexdigest() != expected:
                raise ValueError('update-runtime-before-graphics')
        target = root / 'graphics-ahb'
        if target.exists():
            if hashlib.sha256(read(target / 'libvulkan_freedreno.so', 32 * 1024 * 1024)).hexdigest() != DRIVER_SHA:
                raise ValueError('graphics-existing-driver')
            from omarchy_commands import native_graphics
            env = {}; native_graphics(root, env)
            if env.get('LOOPY_X11_AHB') != '1':
                raise ValueError('graphics-existing-selection')
            return {'status': 'ALREADY_INSTALLED'}
        staging = root / 'graphics-ahb-staging'
        staging.mkdir(mode=0o700)  # Preserve an interrupted installation for inspection.
        icd = json.dumps({'file_format_version': '1.0.0', 'ICD': {
            'library_path': str(target / 'libvulkan_freedreno.so'), 'api_version': '1.4.0'}}).encode()
        files = {'libvulkan_freedreno.so': data, 'icd.json': icd}
        selection = {'schema': 1, 'sha256': {n: hashlib.sha256(v).hexdigest() for n, v in files.items()}}
        files['selection.json'] = json.dumps(selection).encode()
        for name, content in files.items():
            with os.fdopen(os.open(staging / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f:
                f.write(content); f.flush(); os.fsync(f.fileno())
        os.rename(staging, target)
        return {'status': 'INSTALLED', 'driverSHA256': DRIVER_SHA}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    args = parser.parse_args()
    print(json.dumps(install(Path('/data/data/com.termux/files/home/.local/share/loopy-omarchy'), args.driver)))
