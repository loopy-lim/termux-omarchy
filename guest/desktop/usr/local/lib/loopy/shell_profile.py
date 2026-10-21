"""Install portable profile entry points only when the user's file is absent."""
from pathlib import Path
import os


def install(home=Path.home(), source=Path('/usr/share/loopy/shell')):
    home, source = Path(home), Path(source)
    if home.is_symlink() or any(parent.is_symlink() for parent in home.parents):
        raise ValueError('Shell HOME must not cross symlinks')
    entries = {'.zshrc': b'source /usr/share/loopy/shell/zshrc\n',
               '.tmux.conf': b'source-file /usr/share/loopy/shell/tmux.conf\n'}
    home.mkdir(parents=True, exist_ok=True)
    for name, data in entries.items():
        target = home / name
        if target.exists() or target.is_symlink(): continue
        if not (source / ('zshrc' if name == '.zshrc' else 'tmux.conf')).is_file(): continue
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(descriptor, 'wb') as output: output.write(data)
