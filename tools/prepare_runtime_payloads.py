#!/usr/bin/env python3
"""Reproduce reviewed workflow payloads; never fetch, install, or inspect HOME."""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC
PROFILE = 'home/omarchy/.local/share/loopy-omarchy-profile/'
WORKFLOW = {
    'home/omarchy/.config/foot/foot.ini': ('template:foot', 0o600, 'a5165f8a0a93c6d7262aaae6c00c11617ffb2f35bafca73f458b6549a9dca5cf'),
    'home/omarchy/.config/hypr/bindings.lua': ('template:bindings-loader', 0o600, 'daacd2f7a0e3844d485a8c9d0472dbeefd84b4ed405922061f94f0196207ffd3'),
    'home/omarchy/.config/tmux/tmux.conf': ('template:tmux-loader', 0o600, 'd3eeec762196b3132d4b187ed2eb95d113cea698a3833fe87a0f60df6e38e544'),
    **{PROFILE + name: ('profiles/' + name, 0o600, None)
       for name in ('bindings.lua', 'git.plugin.zsh', 'git.zsh', 'tmux.conf', 'zshrc')},
    'home/omarchy/.tmux.conf': ('template:tmux-home-loader', 0o600, None),
    'home/omarchy/.zshrc': ('template:zsh-loader', 0o600, None),
    'usr/local/bin/omarchy-remote': ('runtime/omarchy-remote', 0o755, None),
    'usr/local/share/applications/omarchy-remote.desktop': ('runtime/omarchy-remote.desktop', 0o600, None),
    'usr/share/omarchy/bin/omarchy-launch-or-focus': ('template:launch-or-focus', 0o755, '930a0d12ab270c6a5e55790f305230ef0f41602292320c01cba6978669a2a898'),
    'usr/share/omarchy/bin/omarchy-launch-or-focus-tui': ('template:launch-or-focus-tui', 0o755, 'd7d345e198146e0136a310680a70e40521d303e5a04bb86f72a40af6a3b7bb7b'),
    'usr/share/omarchy/bin/omarchy-launch-tui': ('runtime/omarchy-launch-tui', 0o700, 'f53f3f4747be5e19df5fc1e2fb91786a93c839cec84449a0fc13489a795577c0'),
}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(row):
    return (json.dumps(row, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode()


def relative(name):
    require(isinstance(name, str) and 0 < len(name) <= 256, 'preparation-path')
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and str(path) == name and
            all(p not in ('', '.', '..') for p in path.parts), 'preparation-path')
    return path


def fingerprint(row):
    return (row.st_dev, row.st_ino, row.st_uid, row.st_mode, row.st_nlink,
            row.st_size, row.st_mtime_ns, row.st_ctime_ns)


def read(root, name, maximum=262144):
    path = relative(name)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        source = os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW, dir_fd=fd)
        with os.fdopen(source, 'rb') as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                    and before.st_nlink == 1 and not before.st_mode & 0o022
                    and 0 <= before.st_size <= maximum, 'preparation-filesystem')
            data = stream.read(maximum + 1)
            require(len(data) <= maximum and fingerprint(before) == fingerprint(os.fstat(stream.fileno()))
                    == fingerprint(os.stat(path.name, dir_fd=fd, follow_symlinks=False)),
                    'preparation-source-changed')
            return data
    finally:
        os.close(fd)


def archive(files, *, prefix='guest', directories=False):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:', format=tarfile.USTAR_FORMAT) as target:
        if directories:
            parents = {prefix} | {prefix + '/' + str(p) for name in files
                                  for p in relative(name).parents if str(p) != '.'}
            for name in sorted(parents):
                row = tarfile.TarInfo(name)
                row.type, row.mode = tarfile.DIRTYPE, 0o700
                target.addfile(row)
        for name, (data, mode) in sorted(files.items()):
            row = tarfile.TarInfo(prefix + '/' + name)
            row.size, row.mode = len(data), mode
            target.addfile(row, io.BytesIO(data))
    return output.getvalue()


def match_artifacts(artifacts, expected):
    require(set(artifacts) == set(expected), 'preparation-output-members')
    for name, data in artifacts.items():
        require(expected[name] == {'bytes': len(data), 'sha256': sha(data)}, 'preparation-output-hash')


def workflow(root, component):
    names = {source for source, _, _ in WORKFLOW.values() if not source.startswith('template:')}
    names.add('tools/prepare_runtime_templates.py')
    require(set(component['sources']) == names, 'preparation-source-members')
    sources = {}
    for name in sorted(names):
        data = read(root, name)
        require(component['sources'][name] == {'bytes': len(data), 'sha256': sha(data)},
                'preparation-source-hash')
        sources[name] = data
    templates = None
    for node in ast.parse(sources['tools/prepare_runtime_templates.py']).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TEMPLATES' for t in node.targets):
            templates = ast.literal_eval(node.value)
    required = {source.removeprefix('template:') for source, _, _ in WORKFLOW.values()
                if source.startswith('template:')}
    require(isinstance(templates, dict) and set(templates) == required
            and all(isinstance(value, str) for value in templates.values()), 'preparation-templates')
    files, manifest = {}, {'schema': 1, 'component': 'guest-personal-workflow', 'files': {}}
    for name, (source, mode, before) in sorted(WORKFLOW.items()):
        data = templates[source.removeprefix('template:')].encode() if source.startswith('template:') else sources[source]
        files[name] = (data, 0o600)
        manifest['files'][name] = {'sha256': sha(data), 'mode': mode, 'before': before}
    result = {'workflow-payload.tar': archive(files), 'workflow-manifest.json': encoded(manifest)}
    match_artifacts(result, component['artifacts'])
    return result


def write_output(path, artifacts, report):
    """Create an exclusive output directory; preserve an incomplete result on error."""
    path = Path(path)
    relative(path.name)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    child = None
    try:
        row = os.fstat(parent)
        require(row.st_uid == os.getuid() and not row.st_mode & 0o022, 'preparation-output-parent')
        os.mkdir(path.name, 0o700, dir_fd=parent)
        child = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=parent)
        # Publish the completion receipt only after every payload is durable.
        for name, data in [*sorted(artifacts.items()), ('preparation.json', encoded(report))]:
            require(relative(name).name == name, 'preparation-output-path')
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600, dir_fd=child)
            with os.fdopen(fd, 'wb') as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        os.fsync(child)
        os.fsync(parent)
    finally:
        if child is not None:
            os.close(child)
        os.close(parent)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true', help='reproduce in memory and compare pinned outputs')
    action.add_argument('--output', type=Path, help='create a new directory containing the reviewed payloads')
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--weston-deb', type=Path, help='also prepare Weston from its separately acquired pinned .deb')
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(read(args.source_root, 'manifests/runtime-build.json'))
        require(manifest['schema'] == 1 and manifest['binaryClosureComplete'] is False
                and manifest['fullFreshInstallVerified'] is False, 'preparation-manifest')
        artifacts = workflow(args.source_root, manifest['components']['workflow'])
        components = {'workflow': {'filesVerified': 15, 'artifacts': manifest['components']['workflow']['artifacts']}}
        from prepare_runtime_guest import prepare
        for name, count in (('guest', 11), ('inputConfig', 5)):
            artifacts.update(prepare(args.source_root, name, manifest['components'][name]))
            components[name] = {'filesVerified': count, 'artifacts': manifest['components'][name]['artifacts']}
        if args.weston_deb is not None:
            from prepare_runtime_weston import prepare
            prepared = prepare(args.weston_deb, manifest['components']['nativeWeston'])
            artifacts.update(prepared)
            components['nativeWeston'] = {'filesVerified': 87, 'artifacts': manifest['components']['nativeWeston']['artifacts']}
        report = {'schema': 1, 'status': 'payloads-prepared' if args.output else 'payloads-verified',
                  'components': components, 'binaryClosureComplete': False,
                  'fullFreshInstallVerified': False, 'deviceChangesRequested': False,
                  'missing': manifest['missing']}
        if args.output:
            write_output(args.output, artifacts, report)
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, tarfile.TarError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('preparation-[a-z-]+', str(error)) else 'preparation-filesystem'
        print(json.dumps({'schema': 1, 'status': 'failed', 'reason': reason, 'deviceChangesRequested': False}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
