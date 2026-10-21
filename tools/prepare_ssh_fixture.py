#!/usr/bin/env python3
"""Prepare fixed test-counterpart dependencies in a workspace-only virtualenv."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.fetch_runtime import RejectRedirects

BUNDLED = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'


def prepare(python: Path = BUNDLED, destination: Path = ROOT / 'build/ssh-fixture') -> dict:
    destination = destination.absolute()
    if not destination.is_relative_to(ROOT / 'build'):
        raise ValueError('SSH fixture dependencies must remain in this workspace build directory')
    if not python.is_file():
        raise ValueError('Select --python for a Python runtime with cryptography and cffi; no global packages are modified')
    lock_path = ROOT / 'third_party/ssh-fixture.lock.json'
    original = lock_path.read_bytes()
    lock = json.loads(original)
    if lock.get('schema') != 1 or len(lock.get('packages', [])) != 4:
        raise ValueError('Invalid SSH fixture lock')
    if destination.is_symlink() or any(parent.is_symlink() for parent in destination.parents):
        raise ValueError('SSH fixture workspace must not cross symlinks')
    destination.mkdir(parents=True, exist_ok=True)
    wheels = destination / 'wheels'
    wheels.mkdir(exist_ok=True)
    if wheels.is_symlink():
        raise ValueError('SSH fixture wheel cache cannot be a symlink')
    paths = []
    opener = urllib.request.build_opener(RejectRedirects())
    for record in lock['packages']:
        name, url = record['wheel'], record['url']
        if Path(name).name != name or not name.endswith('.whl') or not url.startswith('https://files.pythonhosted.org/packages/'):
            raise ValueError('Invalid fixed fixture wheel source')
        path = wheels / name
        if path.is_symlink():
            raise ValueError('Fixture wheel cache entry cannot be a symlink')
        if path.exists():
            data = path.read_bytes()
        else:
            with opener.open(url, timeout=30) as response:
                if response.geturl() != url:
                    raise ValueError('Fixture wheel download escaped its fixed URL')
                data = response.read(record['size_bytes'] + 1)
        if len(data) != record['size_bytes'] or hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ValueError('Fixture wheel SHA/size mismatch: ' + name)
        if not path.exists():
            with path.open('xb') as output:
                output.write(data)
        paths.append(path)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PIP_NO_CACHE_DIR='1')
    # Existing, configured crypto libraries are read from this selected runtime;
    # missing libraries fail here rather than trigger a global pip installation.
    dependency = subprocess.run([str(python), '-c',
        'import cryptography,cffi,json;print(json.dumps({"cryptography":cryptography.__version__,"cffi":cffi.__version__}))'],
        text=True, capture_output=True, env=environment, timeout=10, check=True)
    venv = destination / 'venv'
    if venv.is_symlink():
        raise ValueError('Fixture virtualenv cannot be a symlink')
    subprocess.run([str(python), '-m', 'venv', '--system-site-packages', str(venv)], env=environment, check=True, timeout=30)
    subprocess.run([str(venv / 'bin/python'), '-m', 'pip', 'install', '--disable-pip-version-check',
        '--no-index', '--no-deps', '--no-cache-dir', '--no-compile', '--force-reinstall', *map(str, paths)], env=environment, check=True, timeout=30)
    verified = subprocess.run([str(venv / 'bin/python'), '-c',
        'import paramiko,bcrypt,nacl,invoke,json;print(json.dumps({"paramiko":paramiko.__version__,"bcrypt":bcrypt.__version__,"pynacl":nacl.__version__,"invoke":invoke.__version__}))'],
        env=environment, text=True, capture_output=True, check=True, timeout=10)
    if lock_path.read_bytes() != original:
        raise ValueError('Fixture lock changed during preparation')
    receipt = {'schema': 1, 'lock_sha256': hashlib.sha256(original).hexdigest(),
               'python': str(python.resolve()), 'crypto': json.loads(dependency.stdout),
               'fixture_versions': json.loads(verified.stdout), 'wheels': lock['packages'],
               'workspace_virtualenv': str(venv), 'global_packages_modified': False, 'not_packaged_in_apk': True}
    (destination / 'prepared.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, default=BUNDLED)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/ssh-fixture')
    args = parser.parse_args()
    print(json.dumps(prepare(args.python, args.output), indent=2))
