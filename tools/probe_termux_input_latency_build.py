#!/usr/bin/env python3
"""Build only the isolated ARM64 input probe; never deploy or run a device."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NDK = Path.home() / 'Library/Android/sdk/ndk/27.1.12297006'
SYSROOT = ROOT / 'build/diagnostics/termux-omarchy-input-latency-native-sysroot-20261009-01'
SOURCES = ('probe_termux_input_latency_x11.c', 'probe_termux_input_latency_common.py',
           'probe_termux_input_latency_wayland.py', 'probe_termux_input_latency_build.py')


def record(path):
    path = path.resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 1024 * 1024 * 1024: raise ValueError('probe-build-input')
    with path.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(sha256=digest, bytes=path.stat().st_size)


def build(output):
    if output.exists() or output.is_symlink(): raise ValueError('probe-build-output-exists')
    source = {name: record(ROOT / 'tools' / name) for name in SOURCES}
    capture = json.loads((SYSROOT / 'receipt.json').read_bytes())
    for name, expected in capture['files'].items():
        if record(SYSROOT / 'sysroot' / name) != expected: raise ValueError('probe-sysroot-changed')
    compiler = NDK / 'toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android28-clang'
    readelf = compiler.parent / 'llvm-readelf'
    compiler_record = record(compiler)
    compiler_binary = record(compiler.parent / 'clang')
    if 'Pkg.Revision = 27.1.12297006' not in (NDK / 'source.properties').read_text():
        raise ValueError('probe-ndk-mismatch')
    output.mkdir(mode=0o700, parents=True)
    target = output / 'probe-input-latency-x11'
    command = [str(compiler), '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-fPIE', '-O2',
               '-fstack-protector-strong', '-I', str(SYSROOT / 'sysroot/include'),
               str(ROOT / 'tools/probe_termux_input_latency_x11.c'), '-pie',
               '-Wl,-z,relro,-z,now', '-ldl', '-o', str(target)]
    subprocess.run(command, check=True, capture_output=True)
    target.chmod(0o700)
    elf = subprocess.run([str(readelf), '-h', '-d', str(target)], check=True,
                         capture_output=True, text=True).stdout
    needed = re.findall(r'Shared library: \[([^]]+)\]', elf)
    if 'AArch64' not in elf or set(needed) != {'libdl.so', 'libc.so'} or 'NOW PIE' not in elf:
        raise ValueError('probe-elf-boundary')
    if {name: record(ROOT / 'tools' / name) for name in SOURCES} != source:
        raise ValueError('probe-source-changed')
    result = dict(schema=1, status='BUILD_PASS', device_executed=False, target='aarch64-linux-android28',
                  sources=source, sysroot_receipt=record(SYSROOT / 'receipt.json'),
                  compiler=compiler_record, compiler_binary=compiler_binary,
                  command=command, elf_needed=needed, artifact=record(target),
                  runtime_library='existing Termux prefix/lib/libX11.so; dlopen, not bundled')
    with (output / 'build-receipt.json').open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output.resolve()), sort_keys=True))
