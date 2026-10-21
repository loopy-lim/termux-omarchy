"""Install reviewed exact-commit source files; never build or fetch on the device."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile
import uuid

import omarchy_personal_nvim_guest as files

MANIFEST = 'personal-nvim-plugins-manifest.json'
ARCHIVE = 'personal-nvim-plugins.tar.gz'
MANIFEST_SHA = 'a01ee2bdfa620220975e7a9c465857b729b3ff0d9a45ff4aae0ad4f02748ee77'
MANIFEST_BYTES = 1242388
OWNER = '.local/share/loopy-omarchy-personal-nvim-plugins/owner.json'
TARGET = '.local/share/nvim/lazy'


class Payload:
    def __init__(self, directory):
        self.directory = Path(directory)
        fd = files.directory(self.directory)
        try: raw = files.read(fd, MANIFEST, MANIFEST_BYTES)
        finally: os.close(fd)
        files.require(len(raw) == MANIFEST_BYTES and files.sha(raw) == MANIFEST_SHA,
                      'personal-nvim-plugin-manifest-sha')
        self.manifest = json.loads(raw)
        files.require(self.manifest['schema'] == 1 and self.manifest['component'] == 'personal-neovim-plugin-sources')
        files.require(len(self.manifest['plugins']) == 81 and len(self.manifest['files']) == 8261)
        for name in self.manifest['files']:
            parts = PurePosixPath(name).parts
            files.require(len(parts) >= 3 and parts[0] == 'lazy' and parts[1] in self.manifest['plugins']
                          and all(p not in ('', '.', '..', '.git') for p in parts))
        for _ in self.entries(): pass

    def entries(self):
        fd = files.directory(self.directory)
        descriptor = os.open(ARCHIVE, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=fd)
        try:
            with os.fdopen(descriptor, 'rb') as source:
                info = os.fstat(source.fileno()); identity = files.fingerprint(info)
                files.require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                    and not info.st_mode & 0o022 and info.st_size == self.manifest['archiveBytes'])
                digest = hashlib.sha256()
                while chunk := source.read(1048576): digest.update(chunk)
                files.require(digest.hexdigest() == self.manifest['archiveSHA256'], 'personal-nvim-plugin-archive-sha')
                source.seek(0); seen = set()
                with tarfile.open(fileobj=source, mode='r:gz') as archive:
                    for entry in archive:
                        row = self.manifest['files'].get(entry.name)
                        files.require(entry.isfile() and row is not None and entry.name not in seen
                            and entry.size == row['bytes'] and entry.size <= 16777216,
                            'personal-nvim-plugin-member')
                        data = archive.extractfile(entry).read(entry.size + 1)
                        files.require(len(data) == entry.size and files.sha(data) == row['sha256'],
                                      'personal-nvim-plugin-content-sha')
                        seen.add(entry.name); yield entry.name, data
                files.require(seen == set(self.manifest['files']) and files.fingerprint(os.fstat(source.fileno())) == identity
                    and files.fingerprint(os.stat(ARCHIVE, dir_fd=fd, follow_symlinks=False)) == identity,
                    'personal-nvim-plugin-archive-changed')
        finally: os.close(fd)


def owner(home):
    path = PurePosixPath(OWNER); fd = files.walk(home, str(path.parent))
    if fd is None: return None
    try:
        try: return json.loads(files.read(fd, path.name))
        except FileNotFoundError: return None
    finally: os.close(fd)


def save(home, row, previous=None):
    path = PurePosixPath(OWNER); fd = files.walk(home, str(path.parent), create=True)
    try:
        files.require(owner(home) == previous, 'personal-nvim-plugin-owner-changed')
        raw = json.dumps(row, sort_keys=True).encode()
        if previous is None: files.create(fd, path.name, raw)
        else:
            files.create(fd, '.owner-next', raw)
            files.require(owner(home) == previous, 'personal-nvim-plugin-owner-changed')
            os.replace('.owner-next', path.name, src_dir_fd=fd, dst_dir_fd=fd); os.fsync(fd)
    finally: os.close(fd)


def verify(home, payload, record):
    files.require(record.get('schema') == 1 and record.get('phase') == 'INSTALLED', 'personal-nvim-plugin-install-uncertain')
    files.require(record.get('uid') == os.getuid() and record.get('manifestSHA256') == MANIFEST_SHA,
                  'personal-nvim-plugin-owner-identity')
    target = home / TARGET
    fd = files.walk(home, TARGET); files.require(fd is not None, 'personal-nvim-plugin-changed')
    try:
        info = os.fstat(fd)
        files.require(record.get('targetIdentity') == [info.st_dev, info.st_ino, info.st_uid],
                      'personal-nvim-plugin-changed')
    finally: os.close(fd)
    for name, expected in payload.manifest['files'].items():
        relative = '/'.join(PurePosixPath(name).parts[1:])
        data = files.read_relative(target, relative, expected['bytes'])
        files.require(len(data) == expected['bytes'] and files.sha(data) == expected['sha256'],
                      'personal-nvim-plugin-changed')


def install(directory, home):
    home = Path(home).absolute(); payload = Payload(directory)
    record = owner(home)
    result = {'schema': 1, 'plugins': 81, 'manifestSHA256': MANIFEST_SHA,
              'pluginWrites': False, 'networkRequested': False, 'buildScriptsRun': False}
    if record is not None:
        verify(home, payload, record)
        return dict(result, status='installed')
    fd = files.walk(home, TARGET)
    if fd is not None:
        try:
            return dict(result, status='preserved-existing')
        finally: os.close(fd)
    record = {'schema': 1, 'phase': 'INSTALLING', 'uid': os.getuid(), 'manifestSHA256': MANIFEST_SHA}
    save(home, record)
    try:
        parent = files.walk(home, '.local/share/nvim', create=True)
        candidate = '.loopy-personal-plugins-' + uuid.uuid4().hex
        try:
            os.mkdir(candidate, 0o700, dir_fd=parent); os.fsync(parent)
        finally: os.close(parent)
        target = home / '.local/share/nvim' / candidate
        fd = files.directory(target)
        try:
            info = os.fstat(fd); identity = [info.st_dev, info.st_ino, info.st_uid]
        finally: os.close(fd)
        for name, data in payload.entries():
            relative = PurePosixPath('/'.join(PurePosixPath(name).parts[1:]))
            fd = files.walk(target, str(relative.parent), create=True)
            try: files.create(fd, relative.name, data)
            finally: os.close(fd)
        parent = files.walk(home, '.local/share/nvim')
        try: files.publish_directory(parent, candidate, 'lazy')
        finally: os.close(parent)
        final = dict(record, phase='INSTALLED', targetIdentity=identity)
        save(home, final, record); verify(home, payload, final)
        return dict(result, status='installed', pluginWrites=True)
    except BaseException:
        current = owner(home)
        if current in (record, locals().get('final')): save(home, dict(record, phase='INSTALL_UNKNOWN'), current)
        raise ValueError('personal-nvim-plugin-install-uncertain') from None
