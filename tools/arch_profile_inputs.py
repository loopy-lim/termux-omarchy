"""Verify the small public Arch shell payload and its real native cache provenance."""
import hashlib
import json
from pathlib import Path
import tarfile


def digest(path):
    with path.open('rb') as source: return hashlib.file_digest(source, 'sha256').hexdigest()


def check_compositor_only_update(before, after):
    allowed = {'usr/bin/Hyprland', 'usr/bin/hyprctl', 'usr/share/loopy/omarchy-reference-provenance.json'}
    original, current = before['files'], after['files']
    if original.keys() != current.keys() or any(original[name] != current[name] for name in original if name not in allowed):
        raise ValueError('Arch shell/compiler/completion inventory changed; regenerate native cache')


def image_transition_inputs(root, previous_sha, current_sha):
    from .omarchy_catalog import BUNDLE
    return _image_transition_inputs(root, previous_sha, current_sha, BUNDLE)


def _image_transition_inputs(root, previous_sha, current_sha, current_bundle):
    old = root / 'build/deliverables/Omarchy-2026-10-07-arm64-rootfs'
    new = root / current_bundle
    paths = [old / 'receipt.json', old / 'manifest.json', new / 'receipt.json', new / 'manifest.json']
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise ValueError('Cache image transition provenance missing')
    before, after = json.loads(paths[0].read_text()), json.loads(paths[2].read_text())
    if before['archive_sha256'] != previous_sha or after['archive_sha256'] != current_sha \
            or after.get('base_archive_sha256') != previous_sha \
            or after.get('base_manifest_sha256') != before['manifest_sha256'] \
            or digest(paths[1]) != before['manifest_sha256'] or digest(paths[3]) != after['manifest_sha256']:
        raise ValueError('Cache image transition identity differs')
    check_compositor_only_update(json.loads(paths[1].read_text()), json.loads(paths[3].read_text()))
    return paths


def checked_inputs(root):
    root = Path(root); assets = root / 'android/assets'
    artifact = assets / 'arch-profile.tar.gz'; provenance = assets / 'arch-profile.provenance.json'
    if not artifact.exists() and not artifact.is_symlink():
        if (assets / 'omarchy-runtime.properties').exists():
            raise ValueError('Pinned Arch profile payload is missing')
        return []
    for path, maximum in ((artifact, 8 * 1024**2), (provenance, 65536)):
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= maximum:
            raise ValueError('Bounded regular Arch profile input required')
    record = json.loads(provenance.read_text())
    if record.get('schema') != 1 or record.get('zsh_version') != '5.9.2' or not record.get('public_data_only') \
            or record.get('architecture') != 'aarch64' or record.get('asset_sha256') != digest(artifact) \
            or record.get('asset_bytes') != artifact.stat().st_size:
        raise ValueError('Arch profile payload identity mismatch')
    source = root / 'build/desktop/rootfs.tar.gz'
    if digest(source) != record.get('source_rootfs_sha256'):
        raise ValueError('Portable source rootfs changed; regenerate matched Arch profile')
    catalog = dict(line.split('=', 1) for line in (assets / 'omarchy-runtime.properties').read_text().splitlines())
    transition = []
    if catalog['archive_sha256'] != record.get('arch_image_sha256'):
        # Keep the original compilation receipt bound to its original image.
        # Reuse is permitted only after comparing every other image entry.
        try:
            from .omarchy_catalog import BUNDLE
        except ImportError:
            from omarchy_catalog import BUNDLE
        transition = _image_transition_inputs(root, record.get('arch_image_sha256'), catalog['archive_sha256'], BUNDLE)
    actual = {}; total = 0; entries = 0
    with tarfile.open(artifact, 'r|gz') as archive:
        for member in archive:
            entries += 1; name = member.name.rstrip('/')
            if entries > 256 or name.startswith('/') or '..' in name.split('/') or name in actual \
                    or not any(name == p or name.startswith(p + '/') for p in ('usr/share/loopy/shell', 'usr/share/zsh/plugins')) \
                    and name not in ('usr', 'usr/share', 'usr/share/loopy', 'usr/share/zsh'):
                raise ValueError('Bounded portable profile paths required')
            if member.isdir(): continue
            if not member.isfile() or member.size > 8 * 1024**2 - total:
                raise ValueError('Regular portable profile payload budget')
            total += member.size; stream = archive.extractfile(member)
            actual[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != record.get('file_sha256') or total != record.get('payload_bytes') or len(actual) != record.get('regular_files'):
        raise ValueError('Arch profile member identity mismatch')
    originals = record.get('original_regular_files', {})
    if len(originals) != 34 or any(actual.get(n) != h for n, h in originals.items()):
        raise ValueError('Original portable profile sources differ')
    for name in actual:
        if name.endswith('.zwc') and name[:-4] not in actual:
            raise ValueError('Compiled profile source pair is absent')
    evidence = []
    for key in ('native_compile_receipt', 'native_warm_receipt'):
        path = root / record[key]
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink() or not path.is_file():
            raise ValueError('Owned native profile provenance required')
        proof = json.loads(path.read_text())
        if proof.get('app_uid') != 10228 or proof.get('physical_device') is not False:
            raise ValueError('Native ordinary app profile provenance differs')
        evidence.append(path)
    compile_proof = json.loads(evidence[0].read_text())['profile_compilation']
    warm_proof = json.loads(evidence[1].read_text())
    if compile_proof['exit_code'] != 0 or compile_proof['timed_out'] \
            or compile_proof['stdout'] != 'LOOPY_PROFILE_BYTECODE_READY 5.9.2 29\n' or warm_proof['status'] != 'passed':
        raise ValueError('Native profile compilation or controlled warm startup failed')
    return [artifact, provenance, source, *evidence, *transition, root / 'tools/arch_profile_inputs.py']
