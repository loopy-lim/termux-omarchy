#!/usr/bin/env python3
"""Validate a detached Omarchy refresh candidate without publishing or changing APK inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

IMAGE = '7dcc1b5382007da2ef2a52d503ee646bdf863f00b45ad65098f8435d9689fd86'
STOCK = {
    'Aquamarine': ('/usr/lib/libaquamarine.so.0.15.1', 'libaquamarine.so.0.15.1',
                  '4b662e8a42595592378e970a5bdae1156f93ab909449d01c566be2d2c5bb4461', 1736888,
                  'hyprwm/aquamarine', 'f31c47a1b9d300847d8fc3108ad959448103dfc1', 'graphics_patches'),
    'Hyprland': ('/usr/bin/Hyprland', 'Hyprland',
                 '4491b2dbc8c6e15596ec05c4fbcefbaa2d97814e616dc619dd24be8be9662b92', 17319768,
                 'hyprwm/Hyprland', 'efb50993780079460b0cbed1363e2166a2de1d9f', 'hyprland_patches'),
}
PRODUCER = 'tools/build_omarchy_refresh.py'
DEPENDENCIES = ('third_party/omarchy.lock.json', PRODUCER,
                'tools/build_omarchy_graphics.py', 'tools/build_hyprland_rootless.py')
AQ_NEEDED = frozenset(('libEGL.so.1', 'libOpenGL.so.0', 'libGLESv2.so.2', 'libseat.so.1',
                       'libinput.so.10', 'libwayland-client.so.0', 'libhyprutils.so.13', 'libpixman-1.so.0',
                       'libdrm.so.2', 'libgbm.so.1', 'libudev.so.1', 'libdisplay-info.so.3',
                       'libstdc++.so.6', 'libm.so.6', 'libgcc_s.so.1', 'libc.so.6', 'ld-linux-aarch64.so.1'))


def _relative(name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise ValueError('Workspace-relative input path required')
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or str(path) != name or path == Path('.'):
        raise ValueError('Input path must remain in the workspace: ' + name)
    return path


def _hash(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('Complete SHA-256 input identity required')
    return value


def _object(data):
    try:
        result = json.loads(data)
    except (ValueError, UnicodeError) as error:
        raise ValueError('Valid component receipt JSON required') from error
    if not isinstance(result, dict):
        raise ValueError('Component receipt must be an object')
    return result


def _elf(data):
    """Read bounded ELF64 program headers and dynamic strings, never execute the candidate."""
    if len(data) < 64 or data[:7] != b'\x7fELF\x02\x01\x01':
        raise ValueError('Little-endian ELF64 component required')
    (_, kind, machine, version, _, phoff, _, _, _, stride, count, _, _, _) = \
        struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    if kind != 3 or machine != 183 or version != 1 or stride != 56 or not 1 <= count <= 128:
        raise ValueError('AArch64 dynamic component required')
    if phoff < 64 or phoff + count * stride > len(data):
        raise ValueError('Complete ELF program headers required')
    loads = []; dynamic = []
    for index in range(count):
        kind, _, offset, address, _, size, memory, _ = \
            struct.unpack_from('<IIQQQQQQ', data, phoff + index * stride)
        if offset + size > len(data) or size > memory:
            raise ValueError('ELF segment exceeds component byte budget')
        if kind == 1: loads.append((offset, address, size))
        if kind == 2: dynamic.append((offset, size))
    if len(dynamic) != 1 or not 16 <= dynamic[0][1] <= 1024**2 or dynamic[0][1] % 16:
        raise ValueError('One bounded ELF dynamic table required')
    tags = {}; ended = False
    for offset in range(dynamic[0][0], sum(dynamic[0]), 16):
        tag, value = struct.unpack_from('<QQ', data, offset)
        if tag == 0: ended = True; break
        tags.setdefault(tag, []).append(value)
    if not ended or len(tags.get(5, [])) != 1 or len(tags.get(10, [])) != 1:
        raise ValueError('Complete ELF dynamic string table required')
    address, size = tags[5][0], tags[10][0]
    matches = [offset + address - start for offset, start, length in loads
               if start <= address and address + size <= start + length]
    if len(matches) != 1 or not 1 <= size <= 1024**2:
        raise ValueError('ELF strings must fit one file-backed load segment')
    strings = data[matches[0]:matches[0] + size]

    def names(tag):
        result = []
        for index in tags.get(tag, []):
            if index >= len(strings) or strings.find(b'\0', index) < 0:
                raise ValueError('Complete ELF dynamic name required')
            try: result.append(strings[index:strings.index(0, index)].decode('ascii'))
            except UnicodeError as error: raise ValueError('ASCII ELF dependency required') from error
        return result

    return names(14), names(1), names(15) + names(29)


def _validate(root, candidate):
    root = Path(root).absolute()
    candidate = Path(candidate)
    if not candidate.is_absolute(): candidate = root / candidate
    try: candidate_relative = candidate.relative_to(root)
    except ValueError as error: raise ValueError('Candidate must remain in the workspace') from error
    if (len(candidate_relative.parts) != 2 or candidate_relative.parts[0] != 'build'
            or not candidate_relative.parts[1].startswith('omarchy-refresh-')
            or candidate.is_symlink() or not candidate.is_dir()
            or candidate.resolve() != root.resolve() / candidate_relative):
        raise ValueError('Separate regular build/omarchy-refresh-* candidate directory required')
    inputs = set()

    def regular(name, expected=None, maximum=64 * 1024**2):
        relative = _relative(name); path = root / relative
        if (path.is_symlink() or not path.is_file() or path.resolve() != root.resolve() / relative
                or not 0 <= path.stat().st_size <= maximum):
            raise ValueError('Bounded regular component input required: ' + name)
        data = path.read_bytes()
        if len(data) > maximum or (expected is not None and hashlib.sha256(data).hexdigest() != _hash(expected)):
            raise ValueError('Component input identity differs: ' + name)
        inputs.add(path)
        return data

    def within_candidate(name):
        relative = _relative(name)
        if candidate_relative not in relative.parents:
            raise ValueError('Candidate artifact must remain in its separate directory')
        return relative

    regular('tools/omarchy_refresh_inputs.py')
    record = _object(regular(str(candidate_relative / 'component-receipt.json'), maximum=1024**2))
    if (record.get('schema') != 1 or record.get('status') != 'compiled-in-reference-vm'
            or record.get('architecture') != 'aarch64' or type(record.get('build_exit')) is not int
            or record['build_exit'] != 0 or record.get('base_image_sha256') != IMAGE
            or not isinstance(record.get('components'), dict) or set(record['components']) != set(STOCK)):
        raise ValueError('Complete ARM refresh component pair and exact stock image required')
    catalog = regular('android/assets/omarchy-runtime.properties', maximum=65536).decode('utf-8')
    archive = [line.split('=', 1)[1] for line in catalog.splitlines() if line.startswith('archive_sha256=')]
    if archive != [IMAGE]: raise ValueError('Candidate is incompatible with the active catalog image')
    dependencies = record.get('inputs')
    if not isinstance(dependencies, dict) or not 1 <= len(dependencies) <= 512:
        raise ValueError('Pinned refresh build dependency map required')
    for name, identity in dependencies.items(): regular(name, identity)
    if not set(DEPENDENCIES) <= set(dependencies):
        raise ValueError('Refresh producer, existing builders and immutable lock must be pinned')
    lock = _object(regular('third_party/omarchy.lock.json', dependencies['third_party/omarchy.lock.json']))
    bindings = []
    for component, (guest, filename, base, base_size, repo, commit, patch_key) in STOCK.items():
        item = record['components'][component]
        if (not isinstance(item, dict) or item.get('guest') != guest
                or item.get('base_binary_sha256') != base or item.get('base_binary_bytes') != base_size
                or type(item.get('binary_bytes')) is not int or not 64 <= item['binary_bytes'] <= 64 * 1024**2
                or item.get('producer') != PRODUCER or item.get('producer_sha256') != dependencies[PRODUCER]):
            raise ValueError('Exact component guest path, stock preimage and candidate producer required')
        _hash(item.get('binary_sha256'))
        binary_name = str(within_candidate(item.get('binary')))
        if Path(binary_name).name != filename:
            raise ValueError('Candidate binary filename differs from the component')
        binary = regular(binary_name, item.get('binary_sha256'), item['binary_bytes'])
        if len(binary) != item['binary_bytes']: raise ValueError('Candidate binary is incomplete')
        sonames, needed, search_paths = _elf(binary)
        if (search_paths or len(set(needed)) != len(needed)
                or any('/' in name or not name for name in needed)
                or (component == 'Aquamarine' and not set(needed) <= AQ_NEEDED)):
            raise ValueError('Candidate cannot introduce dependency paths, duplicates or non-stock Aquamarine libraries')
        if ((component == 'Aquamarine' and sonames != ['libaquamarine.so.14'])
                or (component == 'Hyprland' and [name for name in needed if name.startswith('libaquamarine.so')]
                    != ['libaquamarine.so.14'])):
            raise ValueError('Aquamarine SONAME and Hyprland dependency must share the stock ABI name')
        receipts = {}
        for key in ('source_receipt', 'build_receipt'):
            name = str(within_candidate(item.get(key)))
            if name not in dependencies or item.get(key + '_sha256') != dependencies[name]:
                raise ValueError('Source and build receipts must be pinned build inputs')
            receipts[key] = _object(regular(name, dependencies[name], 4 * 1024**2))
        source, build = receipts['source_receipt'], receipts['build_receipt']
        role = build.get('provenance_role', 'build-record')
        if role not in ('build-record', 'audited-re-record'):
            raise ValueError('Known native build evidence role required')
        if role == 'audited-re-record':
            original_name = str(within_candidate(build.get('original_build_receipt')))
            if (build.get('original_build_receipt_sha256') != dependencies.get(original_name)
                    or original_name not in dependencies or original_name == item['build_receipt']
                    or build.get('audit_tool') != 'tools/omarchy_refresh_inputs.py'
                    or build.get('audit_tool_sha256') != dependencies.get('tools/omarchy_refresh_inputs.py')
                    or build.get('audit_method') != 'host-source-binary-and-record-equality; no rebuild'
                    or not isinstance(build.get('audited_at'), str)
                    or re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', build['audited_at']) is None):
                raise ValueError('Audited record requires pinned original evidence and explicit recorder role')
            original = _object(regular(original_name, dependencies[original_name], 4 * 1024**2))
            historical = _hash(build.get('historical_producer_sha256'))
            if original.get('producer_sha256') != historical or historical == item['producer_sha256']:
                raise ValueError('Historical build producer must remain separately identified')
            audit_fields = ('provenance_role', 'original_build_receipt', 'original_build_receipt_sha256',
                            'historical_producer_sha256', 'audit_tool', 'audit_tool_sha256', 'audit_method', 'audited_at')
            if any(key in original for key in audit_fields):
                raise ValueError('Audit origin must be the untouched original build record')
            expected_record = dict(original, producer_sha256=item['producer_sha256'])
            expected_record.update({key: build[key] for key in audit_fields})
            if build != expected_record:
                raise ValueError('Audited record cannot change original commands, source or binary evidence')
        upstream = [entry for entry in lock.get('graphics_sources', []) if entry.get('repo') == repo]
        if (len(upstream) != 1 or upstream[0].get('commit') != commit
                or source.get('upstream') != upstream[0] or build.get('upstream') != upstream[0]
                or source.get('architecture') != 'aarch64' or build.get('architecture') != 'aarch64'
                or source.get('status') != 'source-prepared' or build.get('status') != 'compiled-in-reference-vm'
                or type(build.get('build_exit')) is not int or build['build_exit'] != 0
                or type(build.get('uid')) is not int or build['uid'] <= 0
                or build.get('producer_sha256') != item['producer_sha256']
                or source.get('lock_sha256') != dependencies['third_party/omarchy.lock.json']
                or build.get('lock_sha256') != source['lock_sha256']
                or build.get('source_files') != source.get('source_files')
                or build.get('patches') != source.get('patches')):
            raise ValueError('Actual ARM build must match the complete prepared source')
        binaries = build.get('binaries')
        if not isinstance(binaries, dict): raise ValueError('ARM build binary inventory must be an object')
        built = binaries.get(filename)
        if (not isinstance(built, dict) or built.get('sha256') != item['binary_sha256']
                or built.get('bytes') != item['binary_bytes']):
            raise ValueError('Delivered candidate differs from the actual ARM build')
        patches = source.get('patches'); baseline = lock.get(patch_key)
        if (not isinstance(baseline, list) or not baseline or not isinstance(patches, list)
                or len(patches) != len(baseline) + 1 or patches[:-1] != baseline):
            raise ValueError('Candidate requires the exact canonical patch chain and one refresh patch')
        postimages = {}
        for patch in patches:
            if not isinstance(patch, dict) or patch.get('upstream_commit') != commit:
                raise ValueError('Refresh patch must belong to the exact upstream source')
            for key, digest in (('patch', 'patch_sha256'), ('metadata_file', 'metadata_sha256')):
                name = patch.get(key)
                if name not in dependencies or patch.get(digest) != dependencies[name]:
                    raise ValueError('All canonical and refresh patches must be pinned')
                regular(name, patch[digest])
            metadata = _object(regular(patch['metadata_file'], patch['metadata_sha256'], 1024**2))
            if metadata.get('upstream_commit') != commit or metadata.get('patch_sha256') != patch['patch_sha256']:
                raise ValueError('Refresh patch metadata identity differs')
            guarded = metadata.get('files') or {metadata.get('source_file'): metadata}
            if not isinstance(guarded, dict) or not guarded:
                raise ValueError('Guarded refresh patch files required')
            for name, identity in guarded.items():
                _relative(name)
                if not isinstance(identity, dict): raise ValueError('Guarded source identity required')
                before, after = _hash(identity.get('preimage_sha256')), _hash(identity.get('patched_sha256'))
                if name in postimages and postimages[name] != before:
                    raise ValueError('Guarded refresh patch preimage chain differs')
                postimages[name] = after
            added = metadata.get('added_files', {})
            if not isinstance(added, dict): raise ValueError('Added source inventory must be an object')
            for name, identity in added.items():
                _relative(name); _hash(identity)
                module = str(Path('native/omarchy') / ('aquamarine' if component == 'Aquamarine' else 'hyprland') / name)
                if name in postimages or dependencies.get(module) != identity:
                    raise ValueError('Added source must be new and pinned to its native module')
                regular(module, identity); postimages[name] = identity
        directory = within_candidate(item.get('source_directory'))
        if str(directory / 'loopy-source-receipt.json') != item['source_receipt']:
            raise ValueError('Prepared source receipt must belong to its source directory')
        files = source.get('source_files')
        if not isinstance(files, dict) or not 1 <= len(files) <= 10000:
            raise ValueError('Complete bounded prepared source inventory required')
        if any(files.get(name) != identity for name, identity in postimages.items()):
            raise ValueError('Prepared source differs from guarded patch postimages')
        actual = set()
        for path in (root / directory).rglob('*'):
            if path.is_symlink(): raise ValueError('Prepared source cannot contain links')
            if path.is_file() and path != root / Path(item['source_receipt']):
                actual.add(str(path.relative_to(root / directory)))
                if len(actual) > 10000: raise ValueError('Prepared source inventory exceeds budget')
        if actual != set(files): raise ValueError('Prepared source has missing or unlisted files')
        for name, identity in files.items(): regular(str(directory / _relative(name)), identity)
        bindings.append({'component': component, 'guest': guest, 'binary': binary_name,
                         'sha256': item['binary_sha256'], 'bytes': item['binary_bytes'],
                         'base_sha256': base, 'base_bytes': base_size, 'provenance_role': role})
    return sorted(inputs), bindings


def checked_inputs(root, candidate):
    """Return the verified file set; the caller may freeze or review it separately."""
    return _validate(root, candidate)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    try: inputs, bindings = _validate(args.root, args.candidate)
    except (ValueError, OSError, KeyError, TypeError) as error: parser.error(str(error))
    print(json.dumps({'status': 'candidate-inputs-verified', 'bindings': bindings,
                      'checked_inputs': len(inputs), 'physical_device': False, 'refresh_acceptance': False}))


if __name__ == '__main__': main()
