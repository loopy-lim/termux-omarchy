#!/usr/bin/env python3
"""Prepare and build the supervised ARM64 PRoot guard from public sources."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import shutil
import struct
import subprocess
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent
MAX_ARCHIVE = 8 * 1024 * 1024
MAX_SOURCE = 32 * 1024 * 1024


def require(value, reason):
    if not value:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def new_output(path):
    require(not path.exists() and not path.is_symlink(), 'output-exists')
    require(not path.resolve().is_relative_to(HERE), 'output-inside-builder')
    path.mkdir(mode=0o700, parents=True)


def check_inputs():
    lock = json.loads((HERE / 'sources.lock.json').read_text())
    require(lock['schema'] == 1 and set(lock['sources']) ==
            {'proot', 'talloc', 'android-shmem'}, 'source-lock')
    for name, expected in lock['buildInputs'].items():
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'build-input-path')
        path = HERE / relative
        require(path.is_file() and not path.is_symlink() and digest(path.read_bytes()) == expected,
                'build-input-checksum:' + name)
    return lock


def copy_relink_source(source, output):
    require(source.is_dir() and not source.is_symlink() and
            {path.name for path in source.iterdir()} == {'proot', 'talloc', 'android-shmem'},
            'relink-source-layout')
    total = 0
    for path in source.rglob('*'):
        require(not path.is_symlink(), 'relink-source-symlink')
        require(path.is_file() or path.is_dir(), 'relink-source-member')
        if path.is_file():
            relative = path.relative_to(source).as_posix()
            require(path.suffix not in ('.o', '.a', '.so', '.dll', '.dylib')
                    and '.so.' not in path.name and relative not in (
                        'proot/src/proot', 'proot/src/loader/loader',
                        'proot/src/loader/loader-m32', 'proot/src/loader/loader-info.c',
                        'talloc/config.h'), 'relink-source-generated-file')
            total += path.stat().st_size
            require(total <= MAX_SOURCE, 'relink-source-size')
    shutil.copytree(source, output)


def extract_source(data, output, expected):
    require(digest(data) == expected, 'source-checksum')
    require(not output.exists(), 'source-output-exists')
    rows, roots, total = [], set(), 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as source:
        for member in source.getmembers():
            path = PurePosixPath(member.name)
            parts = path.parts
            require(parts and not path.is_absolute() and '..' not in parts
                    and member.name.rstrip('/') == path.as_posix()
                    and (member.isfile() or member.isdir()), 'source-member')
            roots.add(parts[0])
            total += member.size
            require(total <= MAX_SOURCE, 'source-size')
            if len(parts) > 1 and member.isfile():
                rows.append((Path(*parts[1:]), source.extractfile(member).read(), member.mode))
        require(len(roots) == 1 and rows, 'source-top-directory')
    require(len({str(row[0]) for row in rows}) == len(rows), 'source-duplicate-member')
    output.mkdir()
    for relative, content, mode in rows:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        target.chmod(0o755 if mode & 0o111 else 0o644)


def source_archive(inputs, output):
    require(not output.exists(), 'source-archive-exists')
    with output.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for path in sorted(inputs.rglob('*')):
                require(not path.is_symlink(), 'source-bundle-symlink')
                if path.is_file():
                    data = path.read_bytes()
                    member = tarfile.TarInfo('guard-source/' + path.relative_to(inputs).as_posix())
                    member.size = len(data)
                    member.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                    member.mtime = 0
                    archive.addfile(member, io.BytesIO(data))


def run(args, cwd, output, env=None):
    with (output / 'build.log').open('a') as log:
        result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                timeout=240)
    require(result.returncode == 0, 'build-step-failed:' + Path(args[0]).name)


def prepare(output, cache=None, relink_source=None):
    lock = check_inputs()
    inputs = output / 'corresponding-source'
    inputs.mkdir()
    builder = inputs / 'builder'
    shutil.copytree(HERE, builder, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    source_root = inputs / 'source'
    source_root.mkdir()
    archives = inputs / 'archives'
    archives.mkdir()
    for name, row in lock['sources'].items():
        if cache is None:
            with urllib.request.urlopen(row['url'], timeout=40) as response:
                data = response.read(MAX_ARCHIVE + 1)
        else:
            path = cache / (name + '.tar.gz')
            require(path.is_file() and not path.is_symlink(), 'source-cache-missing:' + name)
            data = path.read_bytes()
        require(len(data) == row['bytes'] and len(data) <= MAX_ARCHIVE, 'source-size:' + name)
        extract_source(data, source_root / name, row['sha256'])
        (archives / (name + '.tar.gz')).write_bytes(data)
        require((source_root / name / row['licenseFile']).is_file(), 'source-license:' + name)
    proot = source_root / 'proot'
    for name in ('proot-exitkill.patch', 'proot-string-declarations.patch'):
        patch = HERE / 'patches' / name
        with patch.open('rb') as stream, (output / 'build.log').open('a') as log:
            result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1'], cwd=proot,
                                    stdin=stream, stdout=log, stderr=subprocess.STDOUT, timeout=30)
        require(result.returncode == 0, 'source-patch:' + name)
    require(digest((proot / 'src/tracee/event.c').read_bytes()) ==
            '1d8ce47d4c24a46ef6b4d0dc8526562a72341efd86d32475e24795d168567978', 'patched-event')
    require(digest((proot / 'src/extension/ashmem_memfd/ashmem_memfd.c').read_bytes()) ==
            '05d27a7a3f50afd1de9f5bb9c20c8d47985a5fd8efcfb130a761e5969054f942', 'patched-declarations')
    if relink_source is not None:
        source_root.rename(inputs / 'baseline-source')
        copy_relink_source(relink_source, source_root)
    # Include the GPL text required alongside the LGPL text in talloc/LICENSE.
    project_license = HERE.parents[1] / 'LICENSE'
    if not project_license.is_file():
        project_license = HERE.parent / 'GPL-3.0.txt'
    if project_license.is_file():
        shutil.copyfile(project_license, inputs / 'GPL-3.0.txt')
    else:
        raise ValueError('gpl-text-missing')
    write_json(inputs / 'SOURCE-MANIFEST.json', {
        'schema': 1, 'sourceInputMode': 'editable-source' if relink_source else 'pinned-upstream',
        'modifications': ['PROOT_EXITKILL=1 opt-in ptrace exitkill',
                          'ashmem_memfd string declarations', 'Android API 28 talloc feature preset',
                          'private $ORIGIN linkage; standalone ARM64 loader'],
        'modificationDate': '2026-10-10',
        'files': {path.relative_to(inputs).as_posix(): digest(path.read_bytes())
                  for path in sorted(inputs.rglob('*')) if path.is_file()}})
    artifact = output / 'guard-corresponding-source.tar.gz'
    source_archive(inputs, artifact)
    return lock, source_root, artifact


def ndk_tools(ndk):
    require((ndk / 'source.properties').is_file() and
            re.search(r'^Pkg.Revision\s*=\s*27\.1\.12297006\s*$',
                      (ndk / 'source.properties').read_text(), re.M), 'ndk-version')
    host = {'Darwin': 'darwin-x86_64', 'Linux': 'linux-x86_64'}.get(platform.system())
    require(host is not None, 'ndk-host')
    directory = ndk / 'toolchains/llvm/prebuilt' / host / 'bin'
    names = ('aarch64-linux-android28-clang', 'llvm-ar', 'llvm-strip', 'llvm-readelf',
             'llvm-objcopy', 'llvm-objdump')
    require(all((directory / name).is_file() for name in names), 'ndk-tools-missing')
    return {name: directory / name for name in names}


def elf_record(path, tools):
    data = path.read_bytes()
    require(data[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', data, 18)[0] == 183,
            'elf-aarch64:' + path.name)
    offset = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    loads = []
    for index in range(count):
        row = struct.unpack_from('<IIQQQQQQ', data, offset + index * size)
        if row[0] == 1:
            require(row[7] == 16384 and row[2] % 16384 == row[3] % 16384, 'elf-page-alignment')
            loads.append(row[7])
    require(loads, 'elf-load-segments')
    result = subprocess.run([str(tools['llvm-readelf']), '-d', str(path)],
                            capture_output=True, text=True, check=True, timeout=30)
    return {'sha256': digest(data), 'bytes': len(data), 'machine': 'aarch64',
            'loadAlignments': loads,
            'needed': re.findall(r'\(NEEDED\).*?\[(.*?)\]', result.stdout),
            'runpath': re.findall(r'\((?:RUNPATH|RPATH)\).*?\[(.*?)\]', result.stdout)}


def compile_guard(output, source_root, ndk):
    tools = ndk_tools(ndk)
    work = output / 'work'
    shutil.copytree(source_root, work)
    proot, talloc, shmem = (work / name for name in ('proot', 'talloc', 'android-shmem'))
    deps, artifacts = output / 'dependencies', output / 'arm64-v8a'
    (deps / 'include/sys').mkdir(parents=True)
    (deps / 'lib').mkdir()
    artifacts.mkdir()
    cc = tools['aarch64-linux-android28-clang']
    pages = ['-Wl,-z,max-page-size=16384', '-Wl,-z,common-page-size=16384']
    env = {key: value for key, value in os.environ.items()
           if key in ('PATH', 'HOME', 'TMPDIR', 'SYSTEMROOT')}
    env.update(LC_ALL='C', SOURCE_DATE_EPOCH='0', CC=shlex.quote(str(cc)),
               AR=shlex.quote(str(tools['llvm-ar'])),
               CFLAGS='-O2 -ffile-prefix-map=' + shlex.quote(str(output)) + '=.',
               LDFLAGS=shlex.join(pages + ['-Wl,-soname,libandroid-shmem.so']))
    run([cc, '-O2', '-fPIC', '-std=c11', '-Wall', '-Wextra',
         '-D_PATH_TMP="/data/data/com.termux/files/usr/tmp/"',
         '-ffile-prefix-map=' + str(output) + '=.', '-c', 'shmem.c', '-o', 'shmem.o'],
        shmem, output)
    run([cc, *pages, '-shared', '-Wl,-soname,libandroid-shmem.so',
         '-Wl,--version-script=exports.txt', 'shmem.o', '-o', 'libandroid-shmem.so',
         '-llog', '-landroid'], shmem, output)
    shutil.copyfile(shmem / 'libandroid-shmem.so', deps / 'lib/libandroid-shmem.so')
    shutil.copyfile(shmem / 'shm.h', deps / 'include/sys/shm.h')
    config = talloc / 'config.h'
    config.write_bytes((HERE / 'talloc-android-api28.h').read_bytes())
    run([cc, '-std=c11', '-I' + str(talloc), '-c', HERE / 'talloc-api28-check.c',
         '-o', deps / 'talloc-api28-check.o'], talloc, output)
    run([cc, '-O2', '-fPIC', '-D__STDC_WANT_LIB_EXT1__=1',
         '-ffile-prefix-map=' + str(output) + '=.', '-I' + str(talloc),
         '-I' + str(talloc / 'lib/replace'), '-c', talloc / 'talloc.c', '-o', deps / 'talloc.o'], talloc, output)
    run([tools['llvm-ar'], 'rcs', deps / 'lib/libtalloc.a', deps / 'talloc.o'], talloc, output)
    shutil.copyfile(talloc / 'talloc.h', deps / 'include/talloc.h')
    env.update(STRIP=str(tools['llvm-strip']), OBJCOPY=str(tools['llvm-objcopy']),
               OBJDUMP=str(tools['llvm-objdump']), GIT='false', PROOT_UNBUNDLE_LOADER='.',
               PROOT_WITH_LIBANDROID_SHMEM='true',
               CFLAGS=shlex.join(['-I' + str(deps / 'include'), '-Werror=implicit-function-declaration',
                                 '-ffile-prefix-map=' + str(output) + '=.']),
               CPPFLAGS='-DARG_MAX=131072 -DVERSION=\\"v5.1.107.92-omarchy-guard\\"',
               LDFLAGS='-L' + shlex.quote(str(deps / 'lib')))
    linker = 'LD=' + shlex.join([str(cc), *pages])
    src = proot / 'src'
    run(['make', '-C', src, linker, 'loader/loader'], proot, output, env)
    symbols = subprocess.run([str(tools['llvm-readelf']), '-s', str(src / 'loader/loader')],
                             capture_output=True, text=True, check=True, timeout=30).stdout
    entries = {row.split()[-1]: int(row.split()[1], 16) for row in symbols.splitlines()
               if len(row.split()) >= 8 and row.split()[-1] in ('_start', 'pokedata_workaround')}
    require(set(entries) == {'_start', 'pokedata_workaround'}, 'loader-symbols')
    offset = entries['pokedata_workaround'] - entries['_start']
    require(0 < offset < 65536, 'loader-offset')
    (src / 'loader/loader-info.c').write_text('#include <unistd.h>\nconst ssize_t '
                                           'offset_to_pokedata_workaround=' + str(offset) + ';\n')
    block = re.search(r'OBJECTS \+= \\\n(.*?)\n\ndefine ', (src / 'GNUmakefile').read_text(), re.S)
    require(block is not None, 'proot-object-list')
    objects = re.findall(r'[a-zA-Z0-9_/-]+\.o', block[1]) + ['loader/loader-info.o']
    require(len(objects) == 67 and len(set(objects)) == 67, 'proot-object-list')
    run(['make', '-C', src, linker, *objects], proot, output, env)
    # Link fresh ARM64 objects only; upstream's optional ARM32 loader is excluded.
    run([cc, *pages, '-Wl,-rpath,$ORIGIN', '-o', artifacts / 'proot',
         *(src / name for name in objects), '-L' + str(deps / 'lib'),
         '-ltalloc', '-Wl,-z,noexecstack', '-landroid-shmem'], proot, output)
    shutil.copyfile(src / 'loader/loader', artifacts / 'loader')
    shutil.copyfile(deps / 'lib/libandroid-shmem.so', artifacts / 'libandroid-shmem.so')
    records = {}
    for path in sorted(artifacts.iterdir()):
        run([tools['llvm-strip'], path], proot, output)
        path.chmod(0o700 if path.name != 'libandroid-shmem.so' else 0o600)
        records[path.name] = elf_record(path, tools)
    require(records['proot']['runpath'] == ['$ORIGIN'] and
            set(records['proot']['needed']) == {'libandroid-shmem.so', 'libdl.so', 'libc.so'},
            'proot-private-linkage')
    require(not records['loader']['needed'], 'loader-dynamic-dependency')
    return {'artifacts': records, 'loaderWorkaroundOffset': offset,
            'toolchain': {name: digest(path.read_bytes()) for name, path in tools.items()},
            'tallocConfigSHA256': digest(config.read_bytes()), 'arm32LoaderIncluded': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare', action='store_true')
    action.add_argument('--build', action='store_true')
    action.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--ndk', type=Path)
    parser.add_argument('--source-cache', type=Path)
    parser.add_argument('--relink-source', type=Path,
                        help='explicitly rebuild modified proot/talloc/android-shmem source directories')
    args = parser.parse_args()
    lock = check_inputs()
    if args.check:
        print(json.dumps({'status': 'CHECKED', 'networkUsed': False, 'sources': list(lock['sources'])}))
        return
    require(args.output is not None and (not args.build or args.ndk is not None), 'output-and-ndk-required')
    require(args.relink_source is None or args.build, 'relink-requires-build')
    output = args.output.absolute()
    new_output(output)
    try:
        lock, sources, artifact = prepare(output, args.source_cache, args.relink_source)
        result = compile_guard(output, sources, args.ndk.absolute()) if args.build else {}
        receipt = {'schema': 1, 'status': 'BUILT' if args.build else 'PREPARED',
                   'sourceLockSHA256': digest((HERE / 'sources.lock.json').read_bytes()),
                   'sourceArchive': {'file': artifact.name, 'sha256': digest(artifact.read_bytes()),
                                     'bytes': artifact.stat().st_size},
                   'ndk': lock['ndk'], 'androidAPI': lock['androidAPI'],
                   'sourceInputMode': 'editable-source' if args.relink_source else 'pinned-upstream',
                   'deviceInstalled': False, 'deviceRuntimeVerified': False, **result}
        write_json(output / 'receipt.json', receipt)
        print(json.dumps(receipt, sort_keys=True))
    except Exception as error:
        write_json(output / 'receipt.json', {'schema': 1, 'status': 'FAILED',
                                           'reason': type(error).__name__ + ': ' + str(error)[:300]})
        raise


if __name__ == '__main__':
    main()
