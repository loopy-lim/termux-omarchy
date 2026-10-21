"""Install reviewed tablet config/source snapshots without replacing user files."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tarfile

SHIPPED_INIT_VIM = 'e973fc1834f0c3ad42c1789a1997b460970c17c421a48be2ee8d57551da811de'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_parent(path):
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Destination must not cross a symlink')


def install(archive, expected, home, kind):
    archive, home = Path(archive), Path(home)
    if kind not in ('config', 'plugins'):
        raise ValueError('Unknown snapshot kind')
    if digest(archive) != expected:
        raise ValueError('Snapshot SHA256 mismatch')
    base = home if kind == 'config' else home / '.local/share/nvim'
    safe_parent(base)
    plans, names, total = [], set(), 0
    with tarfile.open(archive, 'r:gz') as source:
        for member in source:
            parts = PurePosixPath(member.name).parts
            allowed = (parts[:2] in (('.config', 'nvim'), ('.config', 'yazi'))
                       if kind == 'config' else parts[:1] == ('lazy',))
            if (not member.isfile() or not allowed or len(parts) < 3
                    or any(p in ('', '.', '..') for p in parts)
                    or member.name.startswith('/') or member.name in names):
                raise ValueError('Invalid snapshot member')
            names.add(member.name)
            total += member.size
            if len(names) > 16000 or total > 256 * 1024 * 1024 or member.size > 32 * 1024 * 1024:
                raise ValueError('Snapshot exceeds its extraction budget')
            target = base.joinpath(*parts)
            safe_parent(target)
            data = source.extractfile(member).read()
            if len(data) != member.size:
                raise ValueError('Truncated snapshot member')
            if target.exists():
                if not target.is_file() or target.read_bytes() != data:
                    raise FileExistsError('Existing user file differs: ' + member.name)
                continue
            plans.append((target, data, 0o700 if member.mode & 0o111 else 0o600))
        # Retire only the original shipped alternative, keeping its bytes as a backup.
        legacy = home / '.config/nvim/init.vim'
        backup = home / '.config/nvim/init.vim.loopy-before-mac-profile'
        retire = kind == 'config' and '.config/nvim/init.lua' in names and legacy.exists()
        if retire:
            safe_parent(legacy)
            safe_parent(backup)
            if not legacy.is_file() or digest(legacy) != SHIPPED_INIT_VIM:
                raise FileExistsError('Existing custom init.vim must be preserved')
            if backup.exists() and digest(backup) != SHIPPED_INIT_VIM:
                raise FileExistsError('Existing init.vim backup differs')
        # Validate the entire snapshot before adding the first file.
        if retire:
            if backup.exists():
                legacy.unlink()
            else:
                legacy.rename(backup)
        for target, data, mode in plans:
            safe_parent(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
            with os.fdopen(descriptor, 'wb') as output:
                output.write(data)
    return {'uid': os.getuid(), 'kind': kind, 'sha256': expected,
            'files': len(names), 'created': len(plans), 'bytes': total,
            'shipped_init_vim_backed_up': retire}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('sha256')
    parser.add_argument('kind', choices=('config', 'plugins'))
    parser.add_argument('--home', type=Path, default=Path.home())
    args = parser.parse_args()
    print(json.dumps(install(args.archive, args.sha256, args.home, args.kind)))
