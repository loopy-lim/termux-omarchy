#!/usr/bin/env python3
"""Prepare a separate v4 source-only watchdog candidate; never replace packaged assets."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.build_omarchy_graphics import apply_guarded_patch
from tools.prepare_omarchy import relative, verify_file

COMMIT = 'efb50993780079460b0cbed1363e2166a2de1d9f'
ARCHIVE_SHA256 = '5b05ce7ba5296fa46e666852bf108ab5af121bf577f8043787e2d2c252d8f109'
METADATA_SHA256 = 'ed4c1009d32150597b808eb69f105955b1df79207e6547c5c3969291c2e114fd'
PATCH = ROOT / 'native/omarchy/patches/hyprland-gpu-recovery-v4.patch'
METADATA = PATCH.with_suffix('.json')
MODULES = ROOT / 'native/omarchy/watchdog'
POLICY_DEST = 'start/src/helpers/LoopyGpuRecovery.hpp'
RECEIPT = 'loopy-watchdog-source-receipt.json'
DEPENDENCIES = ('tools/build_omarchy_graphics.py', 'tools/prepare_omarchy.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def producer_dependencies():
    return {name: sha(ROOT / name) for name in DEPENDENCIES}


def inputs():
    verify_file(METADATA, METADATA_SHA256)
    metadata = json.loads(METADATA.read_text())
    if metadata['upstream_commit'] != COMMIT or metadata['upstream_archive_sha256'] != ARCHIVE_SHA256:
        raise ValueError('Watchdog source identity mismatch')
    verify_file(PATCH, metadata['patch_sha256'])
    if set(metadata['added_files']) != {POLICY_DEST} or metadata['added_file_inputs'] != {
            POLICY_DEST: 'native/omarchy/watchdog/LoopyGpuRecovery.hpp'}:
        raise ValueError('Separate watchdog policy input required')
    verify_file(MODULES / 'LoopyGpuRecovery.hpp', metadata['added_files'][POLICY_DEST])
    return metadata


def apply_recovery_patch(source, patch, metadata):
    # The shared canonical Hyprland patch helper remains unchanged. Its addition
    # namespace is frozen; this isolated component verifies/copies its own policy.
    policy = MODULES / 'LoopyGpuRecovery.hpp'
    verify_file(policy, metadata['added_files'][POLICY_DEST])
    target = Path(source) / POLICY_DEST
    if target.exists() or target.is_symlink():
        raise ValueError('Recovery policy would replace existing source')
    guarded = dict(metadata, added_files={})
    apply_guarded_patch(source, patch, guarded, project='hyprland')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(policy.read_bytes())


def expected_files(metadata):
    inventory = dict(metadata['wrapper_preimages'])
    for name, identity in metadata['files'].items():
        inventory[name] = identity['patched_sha256']
    inventory.update(metadata['added_files'])
    return inventory


def extract_wrapper(archive, candidate, metadata):
    expected = metadata['wrapper_preimages']
    found, seen, total = {}, set(), 0
    with tarfile.open(archive, 'r:gz') as reader:
        for number, member in enumerate(reader):
            path = PurePosixPath(member.name)
            if number > 4096 or not path.parts or path.parts[0] != 'Hyprland-' + COMMIT \
                    or path.is_absolute() or '..' in path.parts or '\\' in member.name:
                raise ValueError('Unsafe upstream source path')
            if member.isdir():
                continue
            name = str(PurePosixPath(*path.parts[1:]))
            if not member.isfile() or len(path.parts) < 2 or name in seen \
                    or not 0 <= member.size <= 64 * 1024**2:
                raise ValueError('Unsafe upstream source entry')
            seen.add(name)
            total += member.size
            if total > 256 * 1024**2:
                raise ValueError('Upstream source budget exceeded')
            if not (name.startswith('start/') or name == 'LICENSE'):
                continue
            if name not in expected or member.size > 1024**2:
                raise ValueError('Unguarded watchdog source input')
            data = reader.extractfile(member).read()
            if len(data) != member.size or hashlib.sha256(data).hexdigest() != expected[name]:
                raise ValueError('Watchdog source preimage mismatch: ' + name)
            found[name] = data
    if set(found) != set(expected):
        raise ValueError('Incomplete watchdog source')
    candidate.mkdir()
    for name, data in found.items():
        target = candidate / relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def validate_destination(destination):
    if destination.exists() or destination.is_symlink():
        raise ValueError('Refuse to replace watchdog candidate')
    for parent in destination.parents:
        if parent.is_symlink():
            raise ValueError('Refuse redirected candidate parent')


def prepare(archive, destination):
    archive, destination = Path(archive), Path(destination).absolute()
    validate_destination(destination)
    metadata = inputs()
    verify_file(archive, ARCHIVE_SHA256)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.watchdog-', dir=destination.parent) as temporary:
        candidate = Path(temporary) / 'source'
        extract_wrapper(archive, candidate, metadata)
        apply_recovery_patch(candidate, PATCH, metadata)
        receipt = {
            'schema_version': 1, 'component': 'start-hyprland', 'architecture': 'aarch64',
            'status': 'source-prepared', 'upstream_commit': COMMIT,
            'upstream_archive_sha256': ARCHIVE_SHA256, 'metadata_sha256': METADATA_SHA256,
            'patch_sha256': metadata['patch_sha256'],
            'producer_sha256': sha(__file__), 'producer_dependencies': producer_dependencies(),
            'source_files': expected_files(metadata),
            'compiled': False, 'packaged': False, 'android_gui_accepted': False,
            'evidence_boundary': 'Separate guarded watchdog sources only. Host tests use dependency adapters; no ARM component or APK acceptance.'}
        (candidate / RECEIPT).write_text(json.dumps(receipt, indent=2) + '\n')
        verify_candidate(candidate)
        candidate.rename(destination)
    return receipt


def verify_candidate(candidate):
    candidate = Path(candidate).absolute()
    if any(parent.is_symlink() for parent in candidate.parents):
        raise ValueError('Missing or redirected watchdog candidate parent')
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValueError('Missing or redirected watchdog candidate')
    metadata = inputs()
    receipt_path = candidate / RECEIPT
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ValueError('Missing or redirected watchdog receipt')
    receipt = json.loads(receipt_path.read_text())
    inventory = expected_files(metadata)
    if receipt.get('status') != 'source-prepared' or receipt.get('source_files') != inventory \
            or receipt.get('producer_sha256') != sha(__file__) \
            or receipt.get('producer_dependencies') != producer_dependencies() \
            or receipt.get('metadata_sha256') != METADATA_SHA256 \
            or receipt.get('patch_sha256') != metadata['patch_sha256'] \
            or receipt.get('upstream_commit') != COMMIT \
            or receipt.get('upstream_archive_sha256') != ARCHIVE_SHA256 \
            or any(receipt.get(key) is not False for key in ('compiled', 'packaged', 'android_gui_accepted')):
        raise ValueError('Watchdog receipt identity mismatch')
    actual = set()
    for path in candidate.rglob('*'):
        if path.is_symlink():
            raise ValueError('Redirected watchdog source')
        if path.is_file() and path != receipt_path:
            actual.add(str(path.relative_to(candidate)))
    if actual != set(inventory):
        raise ValueError('Watchdog source inventory mismatch')
    for name, digest in inventory.items():
        verify_file(candidate / relative(name), digest)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ROOT / ('build/omarchy-sources/hyprland-' + COMMIT + '.tar.gz'))
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--output', type=Path)
    choice.add_argument('--verify', type=Path)
    args = parser.parse_args()
    receipt = prepare(args.archive, args.output) if args.output else verify_candidate(args.verify)
    print(json.dumps({key: receipt[key] for key in ('status', 'compiled', 'packaged', 'android_gui_accepted')}))


if __name__ == '__main__':
    main()
