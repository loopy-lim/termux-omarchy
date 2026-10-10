#!/usr/bin/env python3
"""Verify the portable source closure. This is an integrity check, not a signature."""
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ('runtime/', 'profiles/', 'installer/', 'tests/runtime/')
MANIFESTS = ('manifests/runtime-prerequisites.json', 'manifests/distribution.json',
             'manifests/companion.json')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(root, name, maximum=262144):
    path = PurePosixPath(name)
    require(not path.is_absolute() and str(path) == name and
            all(part not in ('', '.', '..') for part in path.parts), 'source-path')
    flags = os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | flags)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | flags, dir_fd=fd)
            os.close(fd)
            fd = child
        source = os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | flags, dir_fd=fd)
        with os.fdopen(source, 'rb') as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                    before.st_uid == os.getuid() and not before.st_mode & 0o022 and
                    0 <= before.st_size <= maximum, 'source-filesystem')
            data = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
            current = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
            fields = lambda row: (row.st_dev, row.st_ino, row.st_uid, row.st_mode,
                                  row.st_size, row.st_mtime_ns, row.st_ctime_ns, row.st_nlink)
            require(len(data) <= maximum and fields(before) == fields(after) == fields(current),
                    'source-changed')
            return data
    finally:
        os.close(fd)


def assignment(data, name):
    for node in ast.parse(data).body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and
                                              target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('source-runtime-pins')


def validate(root=ROOT):
    root = Path(root)
    manifest = json.loads(read(root, 'manifests/runtime-sources.json'))
    require(manifest['schema'] == 1 and manifest['sourceOnly'] is True and
            manifest['fullFreshInstallVerified'] is False, 'source-manifest')
    files = manifest['files']
    require(isinstance(files, dict) and 1 <= len(files) <= 256, 'source-manifest')
    data = {}
    for name, row in files.items():
        require(name.startswith(ALLOWED) or name in MANIFESTS,
                'source-path')
        require(isinstance(row['sha256'], str) and re.fullmatch('[a-f0-9]{64}', row['sha256'])
                and isinstance(row['bytes'], int), 'source-manifest')
        content = read(root, name)
        require(len(content) == row['bytes'] and digest(content) == row['sha256'], 'source-hash')
        data[name] = content
        if name.endswith('.py'):
            compile(content, name, 'exec')
    # No source inside our publication directories silently escapes the inventory.
    entries = [path for folder in ALLOWED for path in (root / folder).rglob('*')]
    require(not any(path.is_symlink() for path in entries), 'source-filesystem')
    actual = {str(path.relative_to(root)) for path in entries if not path.is_dir()}
    require(actual == {name for name in files if name.startswith(ALLOWED)}, 'source-unlisted')
    for name, content in data.items():
        if not name.startswith('runtime/') or not name.endswith('.py'):
            continue
        for node in ast.walk(ast.parse(content)):
            modules = [item.name for item in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for module in modules:
                if module.startswith('omarchy') or module == 'processes':
                    require('runtime/' + module + '.py' in data, 'source-import-closure')
    for name in ('omarchy_install.py', 'omarchy_terminal.py'):
        pins = assignment(data['runtime/' + name], 'RUNTIME_SHA')
        require(isinstance(pins, dict) and len(pins) == 11, 'source-runtime-pins')
        for module, expected in pins.items():
            require('runtime/' + module in data and digest(data['runtime/' + module]) == expected,
                    'source-runtime-pins')
    require(assignment(data['runtime/omarchy_terminal_install.py'], 'SOURCE_SHA') ==
            digest(data['runtime/omarchy_terminal.py']), 'source-launcher-pin')
    prerequisites = json.loads(data['manifests/runtime-prerequisites.json'])
    require(prerequisites['schema'] == 1 and prerequisites['binaryClosureComplete'] is False
            and prerequisites['automaticInstallEnabled'] is False, 'source-prerequisites')
    return {'schema': 1, 'status': 'source-verified', 'sourceOnly': True,
            'filesVerified': len(files), 'binaryClosureComplete': False,
            'fullFreshInstallVerified': False, 'signatureVerified': False,
            'missing': prerequisites['missing'], 'upstreamBundle': prerequisites['upstreamBundle']}


def main():
    try:
        result, code = validate(), 0
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('source-[a-z-]+', str(error)) else 'source-filesystem'
        result, code = {'schema': 1, 'status': 'failed', 'reason': reason}, 1
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
