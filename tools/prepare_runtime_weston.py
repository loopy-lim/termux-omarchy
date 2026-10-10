"""Read one pinned public Weston package without extracting files on the host."""
import io
from pathlib import Path
import tarfile

from prepare_runtime_payloads import archive, encoded, match_artifacts, read, relative, require, sha

PREFIX = 'data/data/com.termux/files/usr/'


def ar_members(data):
    require(data.startswith(b'!<arch>\n'), 'preparation-weston-ar')
    members, offset = {}, 8
    while offset < len(data):
        header = data[offset:offset + 60]
        require(len(header) == 60 and header[-2:] == b'`\n', 'preparation-weston-ar')
        name = header[:16].decode('ascii').strip().removesuffix('/')
        require(name in ('debian-binary', 'control.tar.xz', 'data.tar.xz') and name not in members,
                'preparation-weston-ar-members')
        size = int(header[48:58])
        require(0 <= size <= len(data) - offset - 60, 'preparation-weston-ar')
        members[name] = data[offset + 60:offset + 60 + size]
        offset += 60 + size
        if size % 2:
            require(data[offset:offset + 1] == b'\n', 'preparation-weston-ar')
            offset += 1
    require(set(members) == {'debian-binary', 'control.tar.xz', 'data.tar.xz'}
            and members['debian-binary'] == b'2.0\n', 'preparation-weston-ar-members')
    return members


def weston_files(data, expected):
    require(isinstance(expected, dict) and 1 <= len(expected) <= 128, 'preparation-weston-files')
    for name, row in expected.items():
        relative(name)
        require(set(row) == {'sha256', 'mode'} and row['mode'] in (0o600, 0o700),
                'preparation-weston-files')
    allowed_dirs = {'data', 'data/data', 'data/data/com.termux', 'data/data/com.termux/files', PREFIX[:-1]}
    allowed_dirs.update(PREFIX + str(p) for name in expected for p in relative(name).parents if str(p) != '.')
    result, seen, total = {}, set(), 0
    with tarfile.open(fileobj=io.BytesIO(ar_members(data)['data.tar.xz']), mode='r:xz') as source:
        for index, row in enumerate(source):
            name = row.name.removeprefix('./')
            require(index < 256 and name not in seen and not row.linkname and not row.pax_headers,
                    'preparation-weston-member')
            seen.add(name)
            if name == '.':
                require(row.isdir() and row.size == 0, 'preparation-weston-member')
                continue
            relative(name)
            if row.isdir():
                require(name in allowed_dirs and row.size == 0, 'preparation-weston-member')
                continue
            require(row.isfile() and name.startswith(PREFIX), 'preparation-weston-member')
            leaf = name[len(PREFIX):]
            require(leaf in expected and 0 <= row.size <= 4194304, 'preparation-weston-member')
            total += row.size
            require(total <= 16777216, 'preparation-weston-size')
            with source.extractfile(row) as content:
                raw = content.read(row.size + 1)
            require(len(raw) == row.size and sha(raw) == expected[leaf]['sha256'],
                    'preparation-weston-member-hash')
            result[leaf] = (raw, expected[leaf]['mode'])
    require(set(result) == set(expected), 'preparation-weston-members')
    return result


def prepare(path, component):
    path = Path(path)
    package = component['package']
    data = read(path.parent, path.name, package['bytes'])
    require(len(data) == package['bytes'] and sha(data) == package['sha256'], 'preparation-weston-deb-hash')
    require(len(component['files']) == 87, 'preparation-weston-files')
    files = weston_files(data, component['files'])
    manifest = {'schema': 1, 'debSHA256': package['sha256'], 'sourceURL': package['url'],
                'files': component['files']}
    artifacts = {'payload.tar': archive(files, prefix='weston-host', directories=True),
                 'payload-manifest.json': encoded(manifest)}
    match_artifacts(artifacts, component['artifacts'])
    return artifacts
