#!/usr/bin/env python3
"""Build isolated real ARM watchdog sources; no canonical or APK promotion."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import prepare_omarchy_watchdog_v4 as source_guard
from tools.omarchy_remote_elf import needed

OLD_SOURCE = Path('/var/tmp/loopy-hyprland-reproduced-source')
OLD_BUILD = Path('/var/tmp/loopy-hyprland-reproduced-build')
IMAGE = ROOT / 'build/deliverables/Omarchy-2026-10-07-arm64-output-orientation-rootfs/manifest.json'
REFERENCE = ROOT / 'build/omarchy-refresh-20261008/hyprland-source/loopy-source-receipt.json'
STOCK = '29f40097d5fe3ded68c57a9b53d6a39e1051cafb9d05474a205316dfe1baf8d0'
HARDENING = ['-Wl,-z,relro,-z,now']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(path):
    path = Path(path)
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or resolved.stat().st_size > 128 * 1024**2:
        raise ValueError('Bounded regular build input required: ' + str(path))
    return {'resolved': str(resolved), 'sha256': sha(resolved), 'bytes': resolved.stat().st_size}


def verify_inputs(inputs):
    for path, expected in inputs.items():
        if identity(path) != expected:
            raise ValueError('Build input changed: ' + path)


def protected_inputs():
    paths = list((ROOT / 'android/assets/omarchy-native').rglob('*'))
    paths += [ROOT / 'android/assets' / name for name in
              ('omarchy-remote-client.tar.gz', 'omarchy-remote-client.provenance.json',
               'omarchy-remote-client.inventory')]
    paths += [ROOT / 'build/native/arm64-v8a' / name for name in
              ('libloopy_wayland.so', 'libloopy_wayland.receipt.json',
               'libloopy_files.so', 'libloopy_files.receipt.json')]
    return {str(path): identity(path) for path in paths if path.is_file()}


def vm_guard():
    if ROOT != Path('/workspace') or os.getuid() != 501 or os.uname().machine != 'aarch64' \
            or Path('/etc/hostname').read_text().strip() != 'loopy-omarchy-build':
        raise ValueError('Named owned ARM VM and ordinary uid501 required')


def fresh(path):
    if path.exists() or path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Fresh non-redirected destination required: ' + str(path))


def rootfs_identity(path, manifest):
    resolved = Path(path).resolve(strict=True)
    name = str(resolved).removeprefix('/')
    current, seen = name, set()
    for _ in range(16):
        if current in seen:
            raise ValueError('Cyclic frozen image input: ' + name)
        seen.add(current)
        expected = manifest.get(current)
        if not expected or expected['kind'] == 'file':
            break
        if expected['kind'] not in ('symlink', 'hardlink'):
            break
        current = expected['target']
        if Path(current).is_absolute() or '..' in Path(current).parts or '\\' in current:
            raise ValueError('Redirected frozen image input: ' + name)
    else:
        raise ValueError('Frozen image input link budget exceeded: ' + name)
    if not expected or expected['kind'] != 'file' or expected['sha256'] != sha(resolved) \
            or expected['size'] != resolved.stat().st_size:
        raise ValueError('Actual sysroot input differs from frozen image: ' + name)
    return identity(path)


def captured_commands():
    lines = subprocess.check_output(['ninja', '-t', 'commands', 'start-hyprland'],
                                    cwd=OLD_BUILD, text=True).splitlines()
    if len(lines) != 4:
        raise ValueError('Exact three compile commands and one link command required')
    commands = [shlex.split(line) for line in lines]
    if commands[-1][:2] != [':', '&&'] or commands[-1][-2:] != ['&&', ':']:
        raise ValueError('Captured wrapper link command changed')
    commands[-1] = commands[-1][2:-2]
    names = {str(OLD_SOURCE / 'start/src' / name) for name in
             ('main.cpp', 'core/Instance.cpp', 'helpers/Nix.cpp')}
    if {command[command.index('-c') + 1] for command in commands[:3]} != names \
            or any(command[0] != '/usr/sbin/c++' for command in commands):
        raise ValueError('Real pinned wrapper translation units required')
    return lines, commands


def adapt(commands, source, glaze):
    result = []
    for command in commands:
        result.append([part.replace(str(OLD_SOURCE / 'subprojects/loopy-glaze'), str(glaze))
                       .replace(str(OLD_SOURCE), str(source)) for part in command])
    return result


def run_commands(commands, build, log):
    build.mkdir()
    for command in commands[:3]:
        (build / command[command.index('-o') + 1]).parent.mkdir(parents=True, exist_ok=True)
    with log.open('x') as output:
        for command in commands:
            subprocess.run(command, cwd=build, stdout=output, stderr=subprocess.STDOUT,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), check=True)
    return build / 'start/start-hyprland'


def header_inputs(build):
    result = set()
    for dep in sorted(build.rglob('*.o.d')):
        words = shlex.split(dep.read_text().replace('\\\n', ' '))
        for word in words[1:]:
            path = Path(word)
            if path.is_absolute():
                result.add(str(path))
    if not 50 < len(result) < 4096:
        raise ValueError('Bounded complete compiler header inventory required')
    return result


def linker_inputs(build):
    dependency = build / 'start/CMakeFiles/start-hyprland.dir/link.d'
    # GNU ld appends dummy Make rules after the actual dependency rule.
    words = shlex.split(dependency.read_text().split('\n\n', 1)[0].replace('\\\n', ' '))
    paths = {str(Path(word).resolve(strict=True)) for word in words[1:] if Path(word).is_absolute()}
    if not 10 <= len(paths) <= 64:
        raise ValueError('Complete bounded actual linker input inventory required')
    return paths


def elf(path):
    data = path.read_bytes()
    dependencies = needed(data)
    if struct.unpack_from('<H', data, 16)[0] != 3:
        raise ValueError('ARM64 PIE wrapper required')
    program = subprocess.check_output(['readelf', '-Wl', str(path)], text=True)
    interpreter = re.search(r'Requesting program interpreter: ([^]]+)', program)
    if not interpreter or interpreter.group(1) != '/lib/ld-linux-aarch64.so.1':
        raise ValueError('Pinned ARM glibc interpreter required')
    dynamic = subprocess.check_output(['readelf', '-Wd', str(path)], text=True)
    if '(RPATH)' in dynamic or '(RUNPATH)' in dynamic:
        raise ValueError('Private build paths must not leak into wrapper loader search')
    symbols = subprocess.check_output(['readelf', '-Ws', str(path)], text=True)
    hardening = {'relro': 'GNU_RELRO' in program, 'bind_now': 'BIND_NOW' in dynamic,
                 'nx_stack': bool(re.search(r'GNU_STACK\s+.*\sRW\s+', program)),
                 'stack_canary': '__stack_chk_fail' in symbols}
    if not all(hardening.values()):
        raise ValueError('Stock wrapper ELF hardening must be retained')
    return {'machine': 'aarch64', 'elf_type': 3, 'interpreter': interpreter.group(1), 'hardening': hardening,
            'needed': dependencies, 'sha256': sha(path), 'bytes': len(data)}


def build(source, output):
    vm_guard()
    if output.parent != ROOT / 'build' or not output.name.startswith('omarchy-watchdog-'):
        raise ValueError('Separate workspace build/omarchy-watchdog-* output required')
    fresh(output)
    private = Path('/var/tmp/loopy-' + output.name)
    fresh(private)
    receipt = source_guard.verify_candidate(source)
    protected = protected_inputs()
    archive = ROOT / ('build/omarchy-sources/hyprland-' + source_guard.COMMIT + '.tar.gz')
    source_guard.verify_file(archive, source_guard.ARCHIVE_SHA256)
    guard_names = [Path(__file__), Path(source_guard.__file__), source_guard.PATCH, source_guard.METADATA,
                   source_guard.MODULES / 'LoopyGpuRecovery.hpp', IMAGE, REFERENCE, archive,
                   ROOT / 'tools/omarchy_remote_elf.py']
    guard_names += [ROOT / name for name in source_guard.DEPENDENCIES]
    guards = {str(path): identity(path) for path in guard_names}
    manifest = json.loads(IMAGE.read_text())['files']
    if sha('/usr/bin/start-hyprland') != STOCK:
        raise ValueError('Original image wrapper does not match VM package')
    stock = rootfs_identity('/usr/bin/start-hyprland', manifest)
    runtime = {str(Path('/usr/lib') / name): rootfs_identity(Path('/usr/lib') / name, manifest)
               for name in ('libhyprutils.so', 'libstdc++.so.6', 'libgcc_s.so.1', 'libm.so.6',
                            'libc.so.6', 'ld-linux-aarch64.so.1')}
    compiler_paths = ['/usr/sbin/c++', '/usr/sbin/ld', '/usr/sbin/as']
    for name in ('cc1plus', 'collect2', 'crtbeginS.o', 'crtendS.o', 'libgcc.a', 'libgcc_eh.a'):
        compiler_paths.append(subprocess.check_output(['c++', '-print-file-name=' + name], text=True).strip())
    compiler = {path: rootfs_identity(path, manifest) for path in compiler_paths}
    lines, captured = captured_commands()
    reference = json.loads(REFERENCE.read_text())['source_files']
    glaze_files = {name.removeprefix('subprojects/loopy-glaze/'): digest for name, digest in reference.items()
                   if name.startswith('subprojects/loopy-glaze/')}
    if not 100 < len(glaze_files) < 4096:
        raise ValueError('Pinned full real Glaze source inventory required')
    output.mkdir()
    private.mkdir()
    baseline_source, candidate_source = private / 'baseline-source', private / 'candidate-source'
    source_guard.extract_wrapper(archive, baseline_source, source_guard.inputs())
    shutil.copytree(source, candidate_source)
    glaze = private / 'glaze'
    for name, expected in glaze_files.items():
        origin = OLD_SOURCE / 'subprojects/loopy-glaze' / name
        if origin.is_symlink() or sha(origin) != expected:
            raise ValueError('Frozen real Glaze input changed: ' + name)
        destination = glaze / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
    commands = {name: adapt(captured, tree, glaze) for name, tree in
                (('baseline', baseline_source), ('candidate', candidate_source))}
    for variant in commands.values():
        variant[-1][1:1] = HARDENING
    baseline = run_commands(commands['baseline'], private / 'baseline-build', output / 'baseline-build.log')
    candidate = run_commands(commands['candidate'], private / 'candidate-build', output / 'candidate-build.log')
    used = header_inputs(private / 'baseline-build') | header_inputs(private / 'candidate-build')
    linked = linker_inputs(private / 'baseline-build') | linker_inputs(private / 'candidate-build')
    link_inputs = {path: rootfs_identity(path, manifest) for path in sorted(linked)}
    loaded = subprocess.check_output(['ldd', str(candidate)], text=True)
    for path in re.findall(r'(?:=> )?(/[^\s]+) \(', loaded):
        runtime[path] = rootfs_identity(path, manifest)
    sysroot = {path: rootfs_identity(path, manifest) for path in sorted(used) if path.startswith('/usr/')}
    local = {path: identity(path) for path in sorted(used) if not path.startswith('/usr/')}
    all_inputs = dict(compiler)
    for inputs in (runtime, sysroot, local, link_inputs):
        all_inputs.update(inputs)
    # Fresh second compilation proves the pinned dependency inventory and commands,
    # independently of first-pass header discovery or cached wrapper objects.
    repeated = {}
    for name in ('baseline', 'candidate'):
        binary = run_commands(commands[name], private / (name + '-repeat'), output / (name + '-repeat.log'))
        original = baseline if name == 'baseline' else candidate
        if sha(binary) != sha(original):
            raise ValueError('Fresh wrapper compilation did not reproduce exact bytes: ' + name)
        repeated[name] = sha(binary)
    components = output / 'components'
    components.mkdir()
    shutil.copyfile('/usr/bin/start-hyprland', components / 'start-hyprland-stock')
    for name, binary in (('start-hyprland-baseline', baseline), ('start-hyprland', candidate)):
        shutil.copyfile(binary, components / name)
        (components / name).chmod(0o755)
    for name, origin in (('baseline-source', baseline_source), ('candidate-source', candidate_source), ('glaze-source', glaze)):
        shutil.copytree(origin, output / name)
    # Preserve actual compiler, headers and link/runtime inputs as a standalone
    # input snapshot; paths remain recorded so another exact VM can repeat commands.
    for name, record in all_inputs.items():
        destination = output / 'build-inputs' / name.removeprefix('/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(record['resolved'], destination)
    for path, record in guards.items():
        destination = output / 'reference-inputs' / Path(path).relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(record['resolved'], destination)
    verify_inputs(all_inputs)
    verify_inputs(guards)
    verify_inputs(protected)
    source_guard.verify_candidate(source)
    binaries = {'stock': elf(components / 'start-hyprland-stock'),
                'baseline': elf(components / 'start-hyprland-baseline'), 'candidate': elf(components / 'start-hyprland')}
    if binaries['baseline']['needed'] != binaries['candidate']['needed']:
        raise ValueError('Recovery must not add runtime dependencies')
    snapshot = {str(path.relative_to(ROOT)): {'sha256': sha(path), 'bytes': path.stat().st_size}
                for path in sorted(output.rglob('*')) if path.is_file()}
    frozen_mapping = {path: str((output / 'build-inputs' / path.removeprefix('/')).relative_to(ROOT)) for path in all_inputs}
    frozen_mapping.update({path: str((output / 'reference-inputs' / Path(path).relative_to(ROOT)).relative_to(ROOT)) for path in guards})
    record = {'schema_version': 1, 'component': 'start-hyprland', 'status': 'compiled-in-reference-vm',
              'architecture': 'aarch64', 'uid': os.getuid(), 'hostname': Path('/etc/hostname').read_text().strip(),
              'producer_sha256': sha(__file__), 'source_receipt_sha256': sha(source / source_guard.RECEIPT),
              'source_receipt': receipt, 'source_guard_inputs': guards, 'stock_rootfs_preimage': stock,
              'rootfs_manifest_sha256': sha(IMAGE), 'captured_commands': lines,
              'captured_commands_sha256': hashlib.sha256(('\n'.join(lines) + '\n').encode()).hexdigest(),
              'stock_hardening_link_flags': HARDENING,
              'build_commands': commands, 'build_commands_sha256': hashlib.sha256(json.dumps(commands, sort_keys=True).encode()).hexdigest(),
              'command_working_directories': {name: str(private / (name + '-build')) for name in commands},
              'compiler_version': subprocess.check_output(['c++', '--version'], text=True).splitlines()[0],
              'compiler_inputs': compiler, 'runtime_inputs': runtime, 'sysroot_inputs': sysroot,
              'linker_inputs': link_inputs,
              'compiled_local_inputs': local, 'glaze_files': glaze_files, 'binaries': binaries,
              'fresh_repeat_sha256': repeated, 'baseline_matches_stock': binaries['baseline']['sha256'] == STOCK,
              'standalone_snapshot': snapshot, 'frozen_path_mapping': frozen_mapping,
              'protected_inputs': protected, 'packaged': False, 'physical_device': False, 'hardware_gpu': False,
              'evidence_boundary': 'Real upstream main/Instance/Nix with frozen ARM glibc/toolchain/Hyprutils/Glaze; fresh repeated builds. No APK or Android GUI/GPU recovery acceptance.'}
    (output / 'build-receipt.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'status': record['status'], 'binaries': binaries, 'baseline_matches_stock': record['baseline_matches_stock']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source.absolute(), args.output.absolute())
