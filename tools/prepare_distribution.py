#!/usr/bin/env python3
"""Assemble a verified local installation kit; never fetch, install or inspect HOME."""
import argparse
import os
from pathlib import Path
import re
import stat
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'installer'))
from assets import NOFOLLOW, catalog, check_stream, fingerprint, require, validate_entries, verify_file, verify_tree


def prepare(inputs, entries, output):
    validate_entries(entries)
    require(set(inputs) == set(entries), 'delivery-input-members')
    for name, source in sorted(inputs.items()):
        verify_file(source, entries[name])
    output = Path(output)
    parent = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    try:
        row = os.fstat(parent)
        require(row.st_uid == os.getuid() and not row.st_mode & 0o022, 'delivery-output-parent')
        os.mkdir(output.name, 0o700, dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(parent)
    # A failed assembly is retained, never silently removed or reused.
    for name, source_path in sorted(inputs.items()):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with os.fdopen(os.open(source_path, os.O_RDONLY | os.O_NONBLOCK | NOFOLLOW), 'rb') as source:
            before = check_stream(source, entries[name])
            source.seek(0)
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as destination:
                while data := source.read(1024 * 1024):
                    destination.write(data)
                destination.flush()
                os.fsync(destination.fileno())
            require(fingerprint(os.fstat(source.fileno())) == before
                    and fingerprint(os.stat(source_path, follow_symlinks=False)) == before,
                    'delivery-file-changed')
    return verify_tree(output, entries)


def input_paths(args, entries):
    inputs = {}
    downloads = json.loads((ROOT / 'manifests/downloads.json').read_text())
    # The original upstream base and package files remain separately acquired.
    upstream = {row['file']: key for key, row in downloads['artifacts'].items()}
    for name in entries:
        if name == 'omarchy-base.bundle.tar':
            inputs[name] = args.downloads / downloads['artifacts']['omarchy-base']['file']
        elif name.startswith('proot-guard/'):
            inputs[name] = args.guard / 'arm64-v8a' / Path(name).name
        elif name == 'input/termux-x11.apk':
            inputs[name] = args.apk
        elif name == 'input/termux-x11-companion.deb':
            inputs[name] = args.companion
        elif name == 'sources/termux-x11-source.tar.gz':
            inputs[name] = args.apk_source
        elif name == 'sources/proot-guard-source.tar.gz':
            inputs[name] = args.guard / 'guard-corresponding-source.tar.gz'
        elif name in ('tools/tools-manifest.json', 'korean-input/ime-manifest.json'):
            inputs[name] = ROOT / 'manifests/packages' / Path(name).name
        elif name.startswith(('tools/', 'korean-input/')):
            require(Path(name).name in upstream, 'delivery-input-catalog')
            inputs[name] = args.downloads / Path(name).name
        else:
            require('/' not in name, 'delivery-input-catalog')
            inputs[name] = args.payloads / name
    return inputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--downloads', type=Path, required=True)
    parser.add_argument('--payloads', type=Path, required=True)
    parser.add_argument('--guard', type=Path, required=True)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--companion', type=Path, required=True)
    parser.add_argument('--apk-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from verify import validate
        validate()
        entries = catalog(ROOT)
        count = prepare(input_paths(args, entries), entries, args.output)
        print(json.dumps({'schema': 1, 'status': 'installation-assets-prepared',
                          'filesVerified': count, 'fullFreshInstallVerified': False,
                          'deviceChangesRequested': False}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch(r'(?:source|delivery)-[a-z-]+', str(error)) else 'delivery-unavailable'
        print(json.dumps({'schema': 1, 'status': 'failed', 'reason': reason,
                          'deviceChangesRequested': False}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
