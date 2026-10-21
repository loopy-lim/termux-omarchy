"""Apply the reviewed personal profile, preserving user entry points and backups."""
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

FILES = ('zshrc', 'tmux.conf', 'bindings.lua', 'git.zsh', 'git.plugin.zsh')
MANAGED = '.local/share/loopy-omarchy-profile'
CONFIGS = ('.config/foot/foot.ini', '.config/hypr/bindings.lua')
TMUX = '.config/tmux/tmux.conf'
INCLUDE = 'dofile(os.getenv("HOME") .. "/.local/share/loopy-omarchy-profile/bindings.lua")\n'
ENTRIES = {'.zshrc': b'source "$HOME/.local/share/loopy-omarchy-profile/zshrc"\n',
           '.tmux.conf': b'source-file ~/.local/share/loopy-omarchy-profile/tmux.conf\n'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parents(path, home):
    current = home
    for part in path.relative_to(home).parts[:-1]:
        current /= part
        if os.path.lexists(current):
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise ValueError('profile-parent')


def read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() \
                or info.st_nlink != 1 or info.st_mode & 0o022 or info.st_size > 131072:
            raise ValueError('profile-file')
        data = stream.read(131073)
        if len(data) > 131072:
            raise ValueError('profile-bounds')
        return data


def create(path, data, home):
    parents(path, home)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    parents(path, home)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(data); output.flush(); os.fsync(output.fileno())


def replace(path, data, expected, home):
    parents(path, home)
    if digest(read(path)) != expected:
        raise ValueError('profile-concurrent-edit')
    temporary = path.with_name('.loopy-profile-' + str(uuid.uuid4()))
    create(temporary, data, home)
    try:
        if digest(read(path)) != expected:
            raise ValueError('profile-concurrent-edit')
        os.replace(temporary, path)
    finally:
        if os.path.lexists(temporary): temporary.unlink()


def render_foot(data):
    text = data.decode('utf-8')
    config = configparser.ConfigParser(interpolation=None, delimiters=('=',), strict=True)
    try:
        config.read_string(text)
    except configparser.Error as error:
        raise ValueError('profile-foot-ambiguous') from error
    if not config.has_section('main') or not config.has_section('key-bindings'):
        raise ValueError('profile-foot-sections')
    changes = {('main', 'shell'): '/usr/bin/zsh',
               ('key-bindings', 'font-decrease'): 'Control+minus Mod1+minus Mod1+KP_Subtract',
               ('key-bindings', 'font-increase'): 'Control+plus Control+equal Mod1+plus Mod1+equal Mod1+KP_Add',
               ('key-bindings', 'font-reset'): 'Control+0'}
    for key, fallback in (('clipboard-copy', 'Control+Insert Control+Shift+c XF86Copy'),
                          ('clipboard-paste', 'Shift+Insert Control+Shift+v XF86Paste')):
        tokens = config.get('key-bindings', key, fallback=fallback).split()
        tokens += ['Mod1+c' if key == 'clipboard-copy' else 'Mod1+v']
        changes[('key-bindings', key)] = ' '.join(dict.fromkeys(tokens))
    lines = text.splitlines(keepends=True)
    for (wanted, key), value in changes.items():
        section = None; end = len(lines); found = False
        for index, line in enumerate(lines):
            heading = re.match(r'^\s*\[([^\]]+)\]', line)
            if heading:
                if section == wanted: end = index; break
                section = heading.group(1)
            elif section == wanted and re.match(r'^\s*' + re.escape(key) + r'\s*=', line):
                lines[index] = f'{key}={value}\n'; found = True; break
        if not found:
            if end and not lines[end - 1].endswith('\n'): lines[end - 1] += '\n'
            lines.insert(end, f'{key}={value}\n')
    return ''.join(lines).encode()


def install(home, source, expected):
    home, source = Path(home).absolute(), Path(source).absolute()
    if home.is_symlink() or any(parent.is_symlink() for parent in home.parents):
        raise ValueError('profile-home-symlink')
    info = home.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError('profile-home')
    if set(expected) not in (set(CONFIGS), set((*CONFIGS, TMUX))):
        raise ValueError('profile-expected-files')
    payload = {name: read(source / name) for name in FILES}
    hashes = {name: digest(data) for name, data in payload.items()}
    targets = [home / name for name in expected]
    for path in [*targets, home / MANAGED / 'owner.json']:
        parents(path, home)
    lock_fd = os.open(home / '.loopy-omarchy-profile.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'wb') as lock:
        lock_info = os.fstat(lock.fileno())
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != os.getuid() or lock_info.st_nlink != 1:
            raise ValueError('profile-lock')
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        managed = home / MANAGED
        previous = None
        if os.path.lexists(managed):
            owner = json.loads(read(managed / 'owner.json'))
            if owner.get('schema') != 1 or owner.get('uid') != os.getuid() \
                    or owner.get('status') != 'applied' or set(owner.get('sources', {})) != set(FILES) \
                    or set(owner.get('after', {})) not in (set(CONFIGS), set((*CONFIGS, TMUX))):
                raise ValueError('profile-existing-owner')
            for name in owner['after']: parents(home / name, home)
            if any(digest(read(managed / name)) != owner['sources'][name] for name in FILES) \
                    or any(digest(read(home / name)) != value for name, value in owner['after'].items()):
                raise ValueError('profile-owned-files-changed')
            previous = owner
        names = tuple(dict.fromkeys((*expected, *(previous['after'] if previous else ()))))
        if os.path.lexists(home / TMUX) and TMUX not in names:
            raise ValueError('profile-tmux-review-required')
        original = {name: read(home / name) for name in names}
        known = {**expected, **(previous['after'] if previous else {})}
        if any(digest(data) != known[name] for name, data in original.items()):
            raise ValueError('profile-config-changed')
        bindings = original[CONFIGS[1]]
        if INCLUDE.encode().strip() in bindings and not previous:
            raise ValueError('profile-existing-include')
        updated = {CONFIGS[0]: render_foot(original[CONFIGS[0]]),
                   CONFIGS[1]: bindings if previous else
                   bindings.rstrip(b'\n') + b'\n\n-- Loopy personal tablet bindings.\n' + INCLUDE.encode()}
        if TMUX in original:
            include = b'source-file ~/.local/share/loopy-omarchy-profile/tmux.conf\n'
            tmux = original[TMUX]
            updated[TMUX] = tmux if include.strip() in tmux else tmux.rstrip(b'\n') + b'\n\n# Loopy personal tablet overrides.\n' + include
        if previous and previous['sources'] == hashes and updated == original:
            return dict(previous, unchanged=True)
        backup = home / '.local/state/loopy-omarchy-profile' / str(uuid.uuid4())
        owner = {'schema': 1, 'uid': os.getuid(), 'status': 'prepared', 'sources': hashes,
                 'before': {name: digest(data) for name, data in original.items()},
                 'after': {name: digest(data) for name, data in updated.items()},
                 'backup': str(backup), 'createdEntries': [], 'retainedEntries': []}
        if previous:
            owner.update(previousBackup=previous['backup'], createdEntries=previous['createdEntries'],
                         retainedEntries=previous['retainedEntries'])
        for name, data in original.items(): create(backup / Path(name).name, data, home)
        create(backup / 'receipt.json', json.dumps(owner, indent=2).encode(), home)
        if previous:
            for name in FILES:
                if previous['sources'][name] != hashes[name]:
                    create(backup / 'profile' / name, read(managed / name), home)
            replace(managed / 'owner.json', json.dumps(owner, indent=2).encode(),
                    digest(read(managed / 'owner.json')), home)
            for name, data in payload.items():
                if previous['sources'][name] != hashes[name]:
                    replace(managed / name, data, previous['sources'][name], home)
        else:
            for name, data in payload.items(): create(managed / name, data, home)
            create(managed / 'owner.json', json.dumps(owner, indent=2).encode(), home)
            for name, data in ENTRIES.items():
                if os.path.lexists(home / name):
                    owner['retainedEntries'].append(name)
                else:
                    create(home / name, data, home); owner['createdEntries'].append(name)
        for name, data in updated.items():
            if data != original[name]: replace(home / name, data, digest(original[name]), home)
        owner['status'] = 'applied'
        for path in (managed / 'owner.json', backup / 'receipt.json'):
            replace(path, json.dumps(owner, indent=2).encode(), digest(read(path)), home)
        return owner
