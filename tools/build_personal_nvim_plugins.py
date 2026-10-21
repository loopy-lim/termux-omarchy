"""Build exact-lock source-only plugin archive, reusing the reviewed local snapshot."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import configparser
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'build/diagnostics/tablet-shell-lock/nvim-plugin-sources-v3.tar.gz'
LOCAL_SHA = '35bdf7b9cc6bf20b103fb3d41386b104f41f4bd23fc7a4e81962730c0fb37102'
RECEIPT = ROOT / 'docs/validation/2026-10-06-y900-tablet-fit/mac-nvim-source.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(output):
    output = Path(output); output.mkdir(mode=0o700, exist_ok=True)
    lock = json.loads((ROOT / 'termux/nvim/lazy-lock.json').read_bytes())
    provenance = {r['plugin']: r for r in json.loads(RECEIPT.read_bytes())['plugins']}
    raw = LOCAL.read_bytes(); assert sha(raw) == LOCAL_SHA
    data = {}; origins = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            assert len(parts) >= 3 and parts[0] == 'lazy' and member.isfile()
            name = parts[1]
            assert name in lock and all(p not in ('', '.', '..', '.git') for p in parts)
            if provenance[name]['commit'] == lock[name]['commit']:
                data[member.name] = archive.extractfile(member).read()
    missing = [name for name in lock if provenance[name]['commit'] != lock[name]['commit']]
    def fetch(name):
        parser = configparser.ConfigParser()
        parser.read(Path.home() / '.local/share/nvim/lazy' / name / '.git/config')
        url = parser.get('remote "origin"', 'url')
        match = re.fullmatch(r'https://github.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+?)(?:\.git)?', url)
        assert match, name
        repo = match.group(1); commit = lock[name]['commit']
        url = f'https://codeload.github.com/{repo}/tar.gz/{commit}'
        cached = output / (name + '-' + commit + '.tar.gz')
        if cached.exists(): raw = cached.read_bytes()
        else:
            with urllib.request.urlopen(url, timeout=60) as response:
                raw = response.read(33554433); assert len(raw) <= 33554432
            cached.write_bytes(raw)
        entries = {}
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
            prefix = repo.split('/')[1] + '-' + commit
            for member in archive:
                parts = PurePosixPath(member.name).parts
                assert parts[0].lower() == prefix.lower() and all(p not in ('', '.', '..', '.git') for p in parts)
                if member.isdir(): continue
                assert member.isfile() and member.size <= 16777216
                entries['lazy/' + name + '/' + '/'.join(parts[1:])] = archive.extractfile(member).read()
        return name, entries, {'kind': 'pinned-github-commit', 'url': url, 'archiveSHA256': sha(raw)}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for name, entries, origin in pool.map(fetch, missing):
            data.update(entries); origins[name] = origin
    plugins = {}
    for name, row in lock.items():
        parser = configparser.ConfigParser()
        parser.read(Path.home() / '.local/share/nvim/lazy' / name / '.git/config')
        match = re.fullmatch(r'https://github.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+?)(?:\.git)?', parser.get('remote "origin"', 'url'))
        assert match, name
        entries = {p: v for p, v in data.items() if p.startswith('lazy/' + name + '/')}
        assert entries
        plugins[name] = {'repository': 'https://github.com/' + match.group(1), 'commit': row['commit'], 'files': len(entries), 'bytes': sum(map(len, entries.values())),
            'origin': origins.get(name, {'kind': 'reviewed-local-source-snapshot', 'archiveSHA256': LOCAL_SHA,
                'receiptCommit': provenance[name]['commit']})}
    manifest = {'schema': 1, 'component': 'personal-neovim-plugin-sources',
        'lockSHA256': sha((ROOT / 'termux/nvim/lazy-lock.json').read_bytes()), 'plugins': plugins,
        'files': {p: {'bytes': len(v), 'sha256': sha(v)} for p, v in sorted(data.items())},
        'networkOnDevice': False, 'pluginBuildScriptsRun': False}
    archive = output / 'personal-nvim-plugins.tar.gz'
    with archive.open('xb') as stream, gzip.GzipFile(fileobj=stream, mode='wb', mtime=0, filename='') as zipped:
        with tarfile.open(fileobj=zipped, mode='w|', format=tarfile.PAX_FORMAT) as bundle:
            for name, content in sorted(data.items()):
                row = tarfile.TarInfo(name); row.size = len(content); row.mode = 0o600; row.mtime = 0
                bundle.addfile(row, io.BytesIO(content))
    archive_sha = sha(archive.read_bytes())
    manifest['archiveSHA256'] = archive_sha; manifest['archiveBytes'] = archive.stat().st_size
    raw = (json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n').encode()
    (output / 'personal-nvim-plugins-manifest.json').write_bytes(raw)
    print(json.dumps({'plugins': len(plugins), 'files': len(data), 'archiveBytes': archive.stat().st_size,
        'archiveSHA256': archive_sha, 'manifestBytes': len(raw), 'manifestSHA256': sha(raw),
        'reusedPinnedPlugins': len(plugins) - len(missing), 'fetchedPinnedPlugins': len(missing)}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('output', type=Path)
    build(parser.parse_args().output)
