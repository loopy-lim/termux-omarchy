#!/usr/bin/env python3
"""Build a separate native Wayland probe using verified installed public headers."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NDK = Path.home() / 'Library/Android/sdk/ndk/27.1.12297006'
CAPTURE = ROOT / 'build/diagnostics/termux-omarchy-wayland-input-sysroot-device-20261009-01'
XML = ROOT / 'build/cargo-home/registry/src/index.crates.io-1949cf8c6b5b557f/wayland-protocols-0.32.13/protocols/stable/xdg-shell/xdg-shell.xml'
XML_SHA = '7ba7f9c8473deee674cb1f154a18abd0bb0cc072604fc055b0c15e459fc4c7df'
SOURCES = ('probe_termux_input_latency_wayland_native.c', 'probe_termux_input_latency_identity.h',
           'probe_termux_input_latency_frame.py', 'probe_termux_input_latency_common.py',
           'probe_termux_input_latency_wayland_build.py')


def record(path):
    data = Path(path).read_bytes()
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes':len(data)}


def descriptors(raw):
    """Mechanical full message tables from the pinned MIT-licensed protocol XML."""
    protocol = ET.fromstring(raw)
    interfaces = protocol.findall('interface')
    parts = ['/* ' + protocol.findtext('copyright').strip() + ' */', '#include <wayland-client.h>']
    parts += ['extern const struct wl_interface ' + i.get('name') + '_interface;' for i in interfaces]
    code = {'int':'i', 'uint':'u', 'fixed':'f', 'string':'s', 'object':'o', 'new_id':'n', 'array':'a', 'fd':'h'}
    for interface in interfaces:
        name = interface.get('name')
        for group in ('request','event'):
            messages = interface.findall(group)
            for index, message in enumerate(messages):
                args = message.findall('arg')
                if args:
                    types = [('&' + a.get('interface') + '_interface') if a.get('interface') else 'NULL' for a in args]
                    parts.append('static const struct wl_interface *' + name + '_' + group + str(index) + '[] = {' + ','.join(types) + '};')
            parts.append('static const struct wl_message ' + name + '_' + group + '[] = {')
            for index, message in enumerate(messages):
                args = message.findall('arg'); since = int(message.get('since','1'))
                signature = (str(since) if since > 1 else '') + ''.join(
                    ('?' if a.get('allow-null') == 'true' else '') + code[a.get('type')] for a in args)
                types = name + '_' + group + str(index) if args else 'NULL'
                parts.append('{' + json.dumps(message.get('name')) + ',' + json.dumps(signature) + ',' + types + '},')
            parts.append('};')
        parts.append('const struct wl_interface ' + name + '_interface = {' + json.dumps(name) + ',' + interface.get('version') +
                     ',' + str(len(interface.findall('request'))) + ',' + name + '_request,' +
                     str(len(interface.findall('event'))) + ',' + name + '_event};')
    return ('\n'.join(parts) + '\n').encode()


def build(output):
    if output.exists() or output.is_symlink(): raise ValueError('wayland-probe-output-exists')
    sources = {name:record(ROOT/'tools'/name) for name in SOURCES}
    receipt = json.loads((CAPTURE/'receipt.json').read_bytes())
    if receipt['missing'] != ['share/wayland-protocols/stable/xdg-shell/xdg-shell.xml']:
        raise ValueError('wayland-probe-sysroot')
    for row in receipt['files']:
        if record(CAPTURE/'sysroot'/row['path']) != {k:row[k] for k in ('sha256','bytes')}:
            raise ValueError('wayland-probe-input-changed')
    if record(XML)['sha256'] != XML_SHA: raise ValueError('wayland-probe-xml')
    # The protocol input provenance was pinned from native/wayland-host/Cargo.lock
    # (wayland-protocols 0.32.13, checksum 23d0c813de3daa2ed6520af85a3bd49b0e722a3078506899aa9686fea58dc4b6);
    # the crate tree is retired, and XML_SHA plus the sysroot receipt remain the live gates.
    compiler = NDK/'toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android28-clang'
    if 'Pkg.Revision = 27.1.12297006' not in (NDK/'source.properties').read_text():
        raise ValueError('wayland-probe-ndk')
    output.mkdir(parents=True,mode=0o700)
    protocol = output/'xdg-shell-protocol.c'; protocol.write_bytes(descriptors(XML.read_bytes()))
    artifact = output/'probe-input-latency-wayland'
    command = [str(compiler),'-std=gnu11','-Wall','-Wextra','-Werror','-O2','-fPIE','-fstack-protector-strong',
               '-I',str(CAPTURE/'sysroot/include'),str(ROOT/'tools/probe_termux_input_latency_wayland_native.c'),
               str(protocol),'-L',str(CAPTURE/'sysroot/lib'),'-lwayland-client','-pie',
               '-Wl,-z,relro,-z,now,--allow-shlib-undefined','-o',str(artifact)]
    compile_result = subprocess.run(command,capture_output=True)
    (output/'compiler.stderr').write_bytes(compile_result.stderr)
    if compile_result.returncode: raise ValueError('wayland-probe-compile')
    artifact.chmod(0o700)
    readelf = compiler.parent/'llvm-readelf'
    elf = subprocess.run([str(readelf),'-h','-d',str(artifact)],check=True,capture_output=True,text=True).stdout
    needed = re.findall(r'Shared library: \[([^]]+)\]',elf)
    if set(needed) != {'libwayland-client.so','libdl.so','libc.so'} or 'AArch64' not in elf or 'NOW PIE' not in elf:
        raise ValueError('wayland-probe-elf')
    if {name:record(ROOT/'tools'/name) for name in SOURCES} != sources:
        raise ValueError('wayland-probe-source-changed')
    result = dict(schema=1,status='BUILD_PASS',device_executed=False,target='aarch64-linux-android28',
        sources=sources,sysroot_receipt=record(CAPTURE/'receipt.json'),xml=record(XML),cargo_lock=record(lock),
        generated_protocol=record(protocol),compiler=record(compiler),compiler_binary=record(compiler.parent/'clang'),
        command=command,elf_needed=needed,artifact=record(artifact),
        runtime_libraries='existing Termux libwayland-client + libffi + libandroid-support; not bundled')
    (output/'build-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(build(parser.parse_args().output.resolve()),sort_keys=True))
