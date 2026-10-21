"""Install the pinned personal Nvim config only; preserve any existing config."""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import uuid

MANIFEST = 'personal-nvim-manifest.json'
MANIFEST_SHA = 'edf332d32f47f2047ed2f69519bb9d47f5a61634e4a75c35879c006aa7c8eacb'
MANIFEST_BYTES = 7199
OWNER = '.local/share/loopy-omarchy-personal-nvim/owner.json'
TARGET = '.config/nvim'


def require(value, reason='personal-nvim-boundary'):
    if not value: raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(info):
    return [info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns, info.st_nlink]


def directory(path, *, owned=True):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if info.st_mode & 0o022 or (owned and info.st_uid != os.getuid()):
        os.close(fd); raise ValueError('personal-nvim-directory')
    return fd


def walk(root, name, *, create=False, owned=True):
    fd = directory(root, owned=owned)
    try:
        for part in PurePosixPath(name).parts:
            require(part not in ('', '.', '..') and '/' not in part)
            if create:
                try: os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError: pass
            try: child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError: return None
            info = os.fstat(child)
            if info.st_mode & 0o022 or (owned and info.st_uid != os.getuid()):
                os.close(child); raise ValueError('personal-nvim-parent')
            os.close(fd); fd = child
        result, fd = fd, None
        return result
    finally:
        if fd is not None: os.close(fd)


def read(fd, name, maximum=131072, *, owned=True):
    descriptor = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=fd)
    with os.fdopen(descriptor, 'rb') as source:
        info = os.fstat(source.fileno()); before = fingerprint(info)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not info.st_mode & 0o022
                and info.st_size <= maximum and (not owned or info.st_uid == os.getuid()))
        data = source.read(maximum + 1)
        require(len(data) <= maximum and fingerprint(os.fstat(source.fileno())) == before
                and fingerprint(os.stat(name, dir_fd=fd, follow_symlinks=False)) == before,
                'personal-nvim-file-changed')
        return data


def read_relative(root, name, maximum=131072, *, owned=True):
    path = PurePosixPath(name); fd = walk(root, str(path.parent), owned=owned)
    require(fd is not None, 'personal-nvim-file-absent')
    try: return read(fd, path.name, maximum, owned=owned)
    finally: os.close(fd)


class Payload:
    def __init__(self, root, *, owned=True):
        root = Path(root)
        fd = directory(root, owned=owned)
        try: raw = read(fd, MANIFEST, MANIFEST_BYTES, owned=owned)
        finally: os.close(fd)
        require(len(raw) == MANIFEST_BYTES and sha(raw) == MANIFEST_SHA, 'personal-nvim-manifest-sha')
        self.manifest = json.loads(raw); self.data = {}
        require(self.manifest.get('schema') == 1 and self.manifest.get('component') == 'guest-personal-neovim')
        for name, row in self.manifest['files'].items():
            require(isinstance(name, str) and re.fullmatch('[a-zA-Z0-9_./-]{1,100}', name)
                    and all(p not in ('', '.', '..') for p in name.split('/')) and not name.startswith('/'))
            data = read_relative(root, name, owned=owned)
            require(len(data) == row['bytes'] and sha(data) == row['sha256'], 'personal-nvim-payload-sha')
            self.data[name] = data
        require(len(self.data) == 30 and 'init.lua' in self.data and 'lazy-lock.json' in self.data)
        self.lock = json.loads(self.data['lazy-lock.json'])
        require(len(self.lock) == 81 and all(re.fullmatch('[a-zA-Z0-9_.-]{1,80}', n)
                and re.fullmatch('[a-f0-9]{40}', r['commit']) for n, r in self.lock.items()))
        self.data[MANIFEST] = raw


def owner_record(home):
    path = PurePosixPath(OWNER); fd = walk(home, str(path.parent))
    if fd is None: return None
    try:
        try: return json.loads(read(fd, path.name))
        except FileNotFoundError: return None
    finally: os.close(fd)


def target_state(home, payload):
    owner = owner_record(home)
    if owner is not None:
        require(isinstance(owner, dict) and owner.get('schema') == 1 and owner.get('phase') == 'INSTALLED',
                'personal-nvim-install-uncertain')
        require(owner.get('uid') == os.getuid() and owner.get('manifestSHA256') == MANIFEST_SHA,
                'personal-nvim-owner-identity')
    parent = walk(home, '.config')
    if parent is None:
        require(owner is None, 'personal-nvim-owned-config-changed')
        return {'state': 'absent', 'identity': None}
    try:
        try: info = os.stat('nvim', dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            require(owner is None, 'personal-nvim-owned-config-changed')
            return {'state': 'absent', 'identity': None}
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o022,
                'personal-nvim-target-directory')
        identity = [info.st_dev, info.st_ino, info.st_uid]
        if owner is None: return {'state': 'existing', 'identity': fingerprint(info)}
        require(owner.get('targetIdentity') == identity, 'personal-nvim-owned-config-changed')
    finally: os.close(parent)
    target = home / TARGET
    expected = set(payload.data)
    allowed_dirs = {str(parent) for name in expected for parent in PurePosixPath(name).parents if str(parent) != '.'}
    def inspect(relative='.'):
        fd = walk(target, relative)
        require(fd is not None, 'personal-nvim-owned-config-changed')
        try:
            for name in os.listdir(fd):
                child = name if relative == '.' else relative + '/' + name
                entry = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(entry.st_mode):
                    require(child in allowed_dirs, 'personal-nvim-owned-config-changed'); inspect(child)
                else:
                    require(child in expected and read(fd, name) == payload.data[child],
                            'personal-nvim-owned-config-changed')
        finally: os.close(fd)
    inspect()
    for name in expected:
        require(read_relative(target, name) == payload.data[name], 'personal-nvim-owned-config-changed')
    return {'state': 'managed', 'identity': identity}


def plugin_state(home, lock):
    fd = walk(home, '.local/share/nvim/lazy')
    if fd is None: return {'missingPlugins': len(lock), 'pluginEvidence': 'directory-presence-only'}
    try:
        missing = 0
        for name in lock:
            try: info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError: missing += 1; continue
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
                missing += 1
        return {'missingPlugins': missing, 'pluginEvidence': 'directory-presence-only'}
    finally: os.close(fd)


def create(fd, name, data):
    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    with os.fdopen(descriptor, 'wb') as output:
        output.write(data); output.flush(); os.fsync(output.fileno())
    os.fsync(fd)


def publish_directory(fd, temporary, name):
    """Atomic no-clobber publication, including an empty directory that appeared."""
    library = ctypes.CDLL(None, use_errno=True)
    rename = library.renameatx_np if sys.platform == 'darwin' else library.renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    flag = 4 if sys.platform == 'darwin' else 1  # RENAME_EXCL / RENAME_NOREPLACE.
    if rename(fd, os.fsencode(temporary), fd, os.fsencode(name), flag) != 0:
        error = ctypes.get_errno(); raise OSError(error, os.strerror(error), name)
    os.fsync(fd)


def save_owner(home, row, previous=None):
    path = PurePosixPath(OWNER); fd = walk(home, str(path.parent), create=True)
    name = '.owner-' + uuid.uuid4().hex
    try:
        require(owner_record(home) == previous, 'personal-nvim-owner-changed')
        raw = json.dumps(row, sort_keys=True).encode()
        if previous is None: create(fd, path.name, raw)
        else:
            create(fd, name, raw)
            require(owner_record(home) == previous, 'personal-nvim-owner-changed')
            os.replace(name, path.name, src_dir_fd=fd, dst_dir_fd=fd); os.fsync(fd)
    finally:
        try: os.unlink(name, dir_fd=fd)
        except FileNotFoundError: pass
        os.close(fd)


def execute(source, home, *, install=False, before=None):
    home = Path(home).absolute()
    require(not any(path.is_symlink() for path in (home, *home.parents)), 'personal-nvim-home-symlink')
    fd = directory(home); os.close(fd)
    payload = Payload(source)
    state = target_state(home, payload)
    reviewed = sha(json.dumps({'manifestSHA256': MANIFEST_SHA, 'target': state}, sort_keys=True).encode())
    row = {'schema': 1, 'guestUID': os.getuid(), 'status': 'verified', 'configState': state['state'],
           'beforeSHA256': reviewed, 'manifestSHA256': MANIFEST_SHA, 'configFiles': len(payload.data),
           'lockedPlugins': len(payload.lock), 'configWrites': False, 'networkRequested': False,
           'packageWrites': False, **plugin_state(home, payload.lock)}
    if not install: return row
    require(before == reviewed, 'personal-nvim-review-changed')
    if state['state'] != 'absent':
        return dict(row, status='installed' if state['state'] == 'managed' else 'preserved-existing')
    home_fd = directory(home)
    lock = os.open('.loopy-personal-nvim.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=home_fd)
    try:
        info = os.fstat(lock)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600, 'personal-nvim-lock')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(target_state(home, payload) == state, 'personal-nvim-review-changed')
        Payload(source)
        owner = {'schema': 1, 'uid': os.getuid(), 'phase': 'INSTALLING', 'manifestSHA256': MANIFEST_SHA}
        save_owner(home, owner)
        try:
            parent = walk(home, '.config', create=True)
            candidate = '.loopy-personal-nvim-' + uuid.uuid4().hex
            try:
                os.mkdir(candidate, 0o700, dir_fd=parent); os.fsync(parent)
            finally: os.close(parent)
            target = home / '.config' / candidate
            for name, data in payload.data.items():
                path = PurePosixPath(name); fd = walk(target, str(path.parent), create=True)
                try: create(fd, path.name, data)
                finally: os.close(fd)
            info = target.lstat(); identity = [info.st_dev, info.st_ino, info.st_uid]
            parent = walk(home, '.config')
            try: publish_directory(parent, candidate, 'nvim')
            finally: os.close(parent)
            final = dict(owner, phase='INSTALLED', targetIdentity=identity)
            save_owner(home, final, owner)
            require(target_state(home, payload)['state'] == 'managed', 'personal-nvim-install-verification')
        except BaseException:
            current = owner_record(home)
            if current in (owner, locals().get('final')):
                save_owner(home, dict(owner, phase='INSTALL_UNKNOWN'), current)
            raise ValueError('personal-nvim-install-uncertain') from None
        return dict(row, status='installed', configState='managed', configWrites=True)
    finally:
        os.close(lock); os.close(home_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--home', type=Path, default=Path('/home/omarchy'))
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--before')
    args = parser.parse_args(argv)
    print(json.dumps(execute(args.source, args.home, install=args.install, before=args.before), sort_keys=True))


if __name__ == '__main__': main()
