"""Read the pinned Microsoft ARM64 archive; never use tarfile extraction helpers."""
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile

import omarchy_install as base

VERSION = '1.141.0'
COMMIT = '2a59476c9bfcb90b3ddc372c36762471b7dfad1c'
SHA256 = '3b6ea238a2aa9000bab0137c19f06d4e8edcb5587438a3afc9dc9739e793e934'
BYTES = 349562023
TOP = 'VSCode-linux-arm64'
MAX_MEMBERS = 12000
MAX_FILE = 268435456
MAX_EXPANDED = 2147483648
require = base.require


def relative(name):
    require(isinstance(name, str) and 0 < len(name) <= 1024 and '\0' not in name,
            'vscode-archive-path')
    path = PurePosixPath(name)
    require(not path.is_absolute() and str(path) == name
            and all(p not in ('', '.', '..') for p in path.parts), 'vscode-archive-path')
    return path


def child(parent, name):
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | base.NOFOLLOW, dir_fd=parent)
    try:
        row = os.fstat(fd)
        require(row.st_uid == os.getuid() and stat.S_IMODE(row.st_mode) == 0o700,
                'vscode-private-directory')
        return fd
    except BaseException:
        os.close(fd)
        raise


def parent_fd(root_fd, name):
    fd = os.dup(root_fd)
    try:
        for part in relative(name).parts[:-1]:
            next_fd = child(fd, part); os.close(fd); fd = next_fd
        result, fd = fd, None
        return result
    finally:
        if fd is not None: os.close(fd)


class LimitedReader:
    def __init__(self, source):
        self.source, self.total = source, 0

    def read(self, size):
        data = self.source.read(min(size, MAX_EXPANDED - self.total + 1))
        self.total += len(data)
        require(self.total <= MAX_EXPANDED, 'vscode-archive-expanded-budget')
        return data


class Payload:
    def __init__(self, path):
        self.path, self.file = Path(path), None
        try:
            self.file = base.regular(self.path, BYTES)
            self.original = base.fingerprint(os.fstat(self.file.fileno()))
            require(self.original[4] == BYTES and base.hashed(self.file) == SHA256, 'vscode-archive-sha')
            self.files, self.metadata = {}, {}
            self.scan()
            self.manifest_sha = hashlib.sha256(json.dumps(self.files, sort_keys=True,
                separators=(',', ':')).encode()).hexdigest()
            self.unchanged()
        except BaseException:
            self.close()
            raise

    def unchanged(self):
        require(base.fingerprint(os.fstat(self.file.fileno())) == self.original
            and base.fingerprint(self.path.lstat()) == self.original, 'vscode-archive-changed')

    def close(self):
        if self.file is not None: self.file.close()

    def members(self):
        self.file.seek(0)
        with gzip.GzipFile(fileobj=self.file) as compressed:
            stream = LimitedReader(compressed)
            with tarfile.open(fileobj=stream, mode='r|') as source:
                for index, row in enumerate(source):
                    require(index < MAX_MEMBERS, 'vscode-archive-member-budget')
                    yield source, row
            while stream.read(65536): pass

    def scan(self):
        seen, total = set(), 0
        for source, row in self.members():
            relative(row.name)
            require(row.name not in seen, 'vscode-archive-duplicate'); seen.add(row.name)
            require(row.name == TOP or row.name.startswith(TOP + '/'), 'vscode-archive-top')
            require(row.isdir() or row.isfile() or row.issym(), 'vscode-archive-type')
            require(not row.mode & ~0o777 and 0 <= row.size <= MAX_FILE, 'vscode-archive-mode-size')
            total += row.size; require(total <= MAX_EXPANDED, 'vscode-archive-size-budget')
            if row.name == TOP:
                require(row.isdir() and row.size == 0, 'vscode-archive-top')
                continue
            name = row.name[len(TOP) + 1:]
            if row.isdir():
                require(row.size == 0); value = dict(kind='directory', mode=0o700)
            elif row.issym():
                require(row.size == 0 and row.linkname and len(row.linkname) <= 1024
                    and not row.linkname.startswith('/') and '\0' not in row.linkname, 'vscode-archive-link')
                value = dict(kind='symlink', target=row.linkname)
            else:
                hashed, capture = hashlib.sha256(), bytearray()
                wanted = name in ('code', 'resources/app/package.json', 'resources/app/product.json')
                with source.extractfile(row) as data:
                    while block := data.read(65536):
                        hashed.update(block)
                        if wanted and len(capture) < 2097152: capture.extend(block[:2097152 - len(capture)])
                if wanted: self.metadata[name] = bytes(capture)
                value = dict(kind='file', size=row.size, mode=0o700 if row.mode & 0o111 else 0o600,
                             sha256=hashed.hexdigest())
            self.files[name] = value
        require(TOP in seen and self.files, 'vscode-archive-top')
        for name, value in self.files.items():
            for parent in relative(name).parents:
                if str(parent) != '.':
                    require(self.files.get(str(parent), {}).get('kind') == 'directory', 'vscode-archive-parent')
            if value['kind'] == 'symlink': self.resolve_link(name)
        for name in ('code', 'bin/code', 'resources/app/package.json', 'resources/app/product.json',
                     'resources/app/resources/linux/code.png'):
            require(self.files.get(name, {}).get('kind') == 'file', 'vscode-archive-required')
        require(self.files['code']['mode'] == self.files['bin/code']['mode'] == 0o700)
        elf = self.metadata['code']
        require(elf[:6] == b'\x7fELF\x02\x01' and elf[18:20] == b'\xb7\x00', 'vscode-archive-architecture')
        require(json.loads(self.metadata['resources/app/package.json']).get('version') == VERSION
            and json.loads(self.metadata['resources/app/product.json']).get('version') == VERSION
            and json.loads(self.metadata['resources/app/product.json']).get('commit') == COMMIT,
            'vscode-archive-version')
        require('data' not in self.files, 'vscode-archive-portable-data')

    def resolve_link(self, name):
        pending, stack, hops = name.split('/'), [], 0
        while pending:
            part = pending.pop(0)
            if part in ('', '.'): continue
            if part == '..':
                require(stack, 'vscode-archive-link-escape'); stack.pop(); continue
            stack.append(part); value = self.files.get('/'.join(stack))
            require(value is not None, 'vscode-archive-link-missing')
            if value['kind'] == 'symlink':
                hops += 1; require(hops <= 40, 'vscode-archive-link-cycle')
                stack.pop(); pending = value['target'].split('/') + pending
            elif pending: require(value['kind'] == 'directory', 'vscode-archive-link-parent')

    def copy(self, fd):
        for name, row in sorted(self.files.items(), key=lambda item: (item[0].count('/'), item[0])):
            if row['kind'] != 'directory': continue
            parent = parent_fd(fd, name)
            try: os.mkdir(PurePosixPath(name).name, 0o700, dir_fd=parent); os.fsync(parent)
            finally: os.close(parent)
        for source, item in self.members():
            if item.name == TOP: continue
            name = item.name[len(TOP) + 1:]; row = self.files[name]
            if row['kind'] == 'directory': continue
            parent = parent_fd(fd, name)
            try:
                leaf = PurePosixPath(name).name
                if row['kind'] == 'symlink': os.symlink(row['target'], leaf, dir_fd=parent)
                else:
                    target = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | base.NOFOLLOW, row['mode'], dir_fd=parent)
                    with os.fdopen(target, 'wb') as output, source.extractfile(item) as data:
                        hashed = hashlib.sha256()
                        while block := data.read(65536): output.write(block); hashed.update(block)
                        require(hashed.hexdigest() == row['sha256'], 'vscode-extract-changed')
                        output.flush(); os.fchmod(output.fileno(), row['mode']); os.fsync(output.fileno())
                os.fsync(parent)
            finally: os.close(parent)
        self.unchanged()

    def inventory(self, fd, *, portable=False):
        found = set()
        def visit(parent, prefix=''):
            for leaf in os.listdir(parent):
                name = prefix + leaf
                if portable and name == 'data':
                    child_fd = child(parent, leaf)
                    try:
                        for required in ('user-data', 'extensions'):
                            check = child(child_fd, required); os.close(check)
                    finally: os.close(child_fd)
                    continue  # Portable settings/extensions are deliberately mutable.
                require(name in self.files, 'vscode-installed-extra'); found.add(name)
                row, info = self.files[name], os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                require(info.st_uid == os.getuid(), 'vscode-installed-owner')
                if row['kind'] == 'directory':
                    next_fd = child(parent, leaf)
                    try: visit(next_fd, name + '/')
                    finally: os.close(next_fd)
                elif row['kind'] == 'symlink':
                    require(stat.S_ISLNK(info.st_mode) and os.readlink(leaf, dir_fd=parent) == row['target'],
                            'vscode-installed-link')
                else:
                    with base.regular(leaf, MAX_FILE, parent) as data:
                        before = base.fingerprint(os.fstat(data.fileno()))
                        require(before[4] == row['size'] and stat.S_IMODE(before[3]) == row['mode']
                            and base.hashed(data) == row['sha256'], 'vscode-installed-file')
                        require(before == base.fingerprint(os.fstat(data.fileno()))
                            and before == base.fingerprint(os.stat(leaf, dir_fd=parent, follow_symlinks=False)))
        visit(fd)
        require(found == set(self.files), 'vscode-installed-incomplete')
        if portable: require('data' in os.listdir(fd), 'vscode-portable-missing')
        return base.identity(os.fstat(fd))
