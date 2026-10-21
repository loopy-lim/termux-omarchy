"""Install only managed native runtime files; retain the user's existing configs."""
import hashlib
import os
from pathlib import Path
import tempfile
from processes import atomic_json, private_directory, read_json

FILES = ('runtime.py', 'processes.py', 'preferences.py', 'i3.config')


def install(home, source):
    root = private_directory(home, '.local/share/loopy-native')
    manifest = read_json(root / 'installed.json') or {'files': {}}
    records = {}
    # Validate the whole upgrade before replacing any managed executable.
    for name in FILES:
        path = root / name
        if path.is_symlink():
            raise ValueError('unsafe installed file symlink')
        if path.exists() and name != 'i3.config':
            recorded = manifest.get('files', {}).get(name)
            if recorded != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError('modified native helper; preserve it and inspect before upgrade')
    for name in FILES:
        path = root / name
        if name == 'i3.config' and path.exists():
            recorded = manifest.get('files', {}).get(name)
            if recorded != hashlib.sha256(path.read_bytes()).hexdigest():
                # Retain the managed baseline so later upgrades preserve edits too.
                records[name] = recorded
                continue
        content = (Path(source) / name).read_bytes()
        fd, temporary = tempfile.mkstemp(prefix='.install-', dir=root)
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(content)
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        records[name] = hashlib.sha256(content).hexdigest()
    atomic_json(root / 'installed.json', {'schema': 1, 'uid': os.getuid(), 'files': records})
    return root
