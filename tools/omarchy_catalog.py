#!/usr/bin/env python3
"""Pin the external complete image into an APK asset, with build-time byte verification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = 'build/deliverables/Omarchy-2026-10-07-arm64-output-orientation-rootfs'
VERIFICATION = 'docs/validation/2026-10-06-omarchy/output-orientation-rootfs-bytes-verified.json'
ASSET = 'android/assets/omarchy-runtime.properties'
KEYS = ('schema', 'id', 'name', 'release', 'architecture', 'format', 'omarchy_commit', 'archive_sha256',
        'archive_bytes', 'materialized_bytes', 'entries', 'packages', 'original_requests')


def digest(path):
    with path.open('rb') as reader: return hashlib.file_digest(reader, 'sha256').hexdigest()


def encode_catalog(fields):
    if set(fields) != set(KEYS): raise ValueError('catalog fields differ')
    values = []
    for key in KEYS:
        value = str(fields[key])
        if not value or any(ord(character) < 32 for character in value): raise ValueError('invalid catalog value')
        values.append(key + '=' + value + '\n')
    result = ''.join(values).encode('utf-8')
    if len(result) > 4096: raise ValueError('catalog byte budget exceeded')
    return result


def expected_catalog(root):
    bundle = root / BUNDLE
    paths = [bundle / 'receipt.json', bundle / 'manifest.json', bundle / 'rootfs.tar.zst',
             root / 'third_party/omarchy.lock.json', root / VERIFICATION]
    if any(path.is_symlink() or not path.is_file() for path in paths): raise ValueError('complete image input missing/unsafe')
    receipt, lock, verified = [json.loads(paths[index].read_text()) for index in (0, 3, 4)]
    archive = paths[2]
    scope = lock.get('scope_counts', {})
    if receipt.get('status') != 'packaged-reference-rootfs' or receipt.get('format') != 'PAX tar + zstd' \
            or verified.get('status') != 'all-rootfs-bytes-and-links-verified' \
            or scope != {'package_requests': 158, 'manual_chapters': 51, 'qml_files': 119} \
            or len(lock.get('requested', [])) != 158 or receipt.get('packages') != len(receipt.get('package_names', [])) \
            or verified.get('original_source_files') != lock['omarchy_source']['git_blobs_verified'] \
            or verified.get('original_manual_files') != 51 or verified.get('original_qml_files') != 119 \
            or verified.get('patched_binaries_match') is not True or verified.get('user_home_imported') is not False:
        raise ValueError('image does not retain the full verified Omarchy scope')
    for key in ('entries', 'packages', 'materialized_bytes', 'archive_sha256', 'manifest_sha256'):
        if receipt.get(key) != verified.get(key): raise ValueError('image inventory differs from verified evidence')
    if archive.stat().st_size != receipt.get('archive_bytes') or digest(archive) != receipt.get('archive_sha256') \
            or digest(paths[1]) != receipt.get('manifest_sha256'):
        raise ValueError('complete image or manifest bytes changed')
    fields = {'schema': '1', 'id': 'omarchy-' + receipt['archive_sha256'][:16], 'name': 'Omarchy Arch ARM64',
              'release': lock['omarchy_source']['version'], 'architecture': 'arm64-v8a', 'format': 'zstd-pax',
              'omarchy_commit': lock['omarchy_source']['commit'], 'archive_sha256': receipt['archive_sha256'],
              'archive_bytes': receipt['archive_bytes'], 'materialized_bytes': receipt['materialized_bytes'],
              'entries': receipt['entries'], 'packages': receipt['packages'], 'original_requests': 158}
    return encode_catalog(fields), paths


def checked_catalog(root, decoder):
    asset = root / ASSET
    if not asset.exists() and not asset.is_symlink(): return []
    if decoder is None: raise ValueError('Omarchy image catalog requires the source-matched native decoder')
    if asset.is_symlink() or not asset.is_file() or asset.stat().st_size > 4096: raise ValueError('runtime asset missing/unsafe')
    expected, paths = expected_catalog(root)
    if asset.read_bytes() != expected: raise ValueError('runtime catalog differs from the complete verified image')
    return [asset, *paths, root / 'tools/omarchy_catalog.py']


def publish_catalog(asset, content, *, expected_previous_sha256=None):
    asset = Path(asset)
    if not content or len(content) > 4096: raise ValueError('catalog byte budget exceeded')
    if asset.is_symlink(): raise ValueError('redirected catalog preserved')
    asset.parent.mkdir(parents=True, exist_ok=True)
    if not asset.exists():
        if expected_previous_sha256 is not None: raise ValueError('expected existing catalog disappeared')
        with asset.open('xb') as output: output.write(content)
        return
    if not asset.is_file() or asset.stat().st_size > 4096: raise ValueError('existing catalog is not a bounded regular file')
    before = asset.read_bytes()
    if before == content: return
    if expected_previous_sha256 != hashlib.sha256(before).hexdigest():
        raise ValueError('existing catalog differs; explicit exact previous identity required')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.' + asset.name + '-', dir=asset.parent, delete=False) as output:
            temporary = Path(output.name); output.write(content); output.flush(); os.fsync(output.fileno())
        if asset.is_symlink() or not asset.is_file() or asset.read_bytes() != before:
            raise ValueError('catalog changed during version preparation; preserved')
        os.replace(temporary, asset)
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous-sha256', help='exact prior catalog identity for an explicit version update')
    args = parser.parse_args()
    try:
        content, _ = expected_catalog(ROOT)
        publish_catalog(ROOT / ASSET, content, expected_previous_sha256=args.previous_sha256)
        print('Pinned complete runtime catalog: ' + ASSET); return 0
    except (OSError, ValueError, KeyError) as failure:
        print(str(failure), file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
