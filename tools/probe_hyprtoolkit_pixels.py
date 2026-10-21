#!/usr/bin/env python3
"""Original toolkit -> real Hyprland -> actual parent pixels, in the owned VM."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import resource
import shlex
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from tools.probe_hyprland_watchdog import BINARY, SHA, PARENT, LIBRARY, digest, stop, wait, toolkit_library


def release_order(log):
    """Check actual client wire events: never reattach a buffer before release."""
    pending, reused, attaches, releases, seen = set(), 0, 0, 0, set()
    for line in log.splitlines():
        attach = re.search(r'-> wl_surface[#@]\d+\.attach\(wl_buffer[#@](\d+)', line)
        release = re.search(r'(?<!-> )wl_buffer[#@](\d+)\.release\(', line)
        destroy = re.search(r'-> wl_buffer[#@](\d+)\.destroy\(', line)
        if attach:
            buffer = attach[1]
            assert buffer not in pending, 'in-flight SHM buffer reattached before wl_buffer.release'
            reused += buffer in seen
            pending.add(buffer); seen.add(buffer); attaches += 1
        elif release:
            pending.discard(release[1]); releases += 1
        elif destroy:
            pending.discard(destroy[1]); seen.discard(destroy[1])
    assert attaches >= 12 and releases >= 10 and reused >= 10, 'insufficient actual release/reuse cycles'
    return {'attaches': attaches, 'releases': releases, 'reuses_after_release': reused}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--toolkit-build-receipt', type=Path)
    args = parser.parse_args()
    assert ROOT == Path('/workspace') and os.getuid() == 501 and os.uname().machine == 'aarch64'
    assert Path('/etc/hostname').read_text().strip() == 'loopy-omarchy-build'
    assert args.output.parent == ROOT / 'docs/validation/2026-10-06-omarchy'
    assert args.output.name.startswith('toolkit-pixels-')
    assert digest(BINARY) == SHA
    assert digest(PARENT) == 'b769a58dc0267e4a796c70dbcef82a79a526b0cda7a7c3e7b89106346d516dce'
    args.output.mkdir(); resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    (args.output / 'producer.py').write_bytes(Path(__file__).read_bytes())
    source = ROOT / 'native/omarchy/tests/toolkit_pixels.cpp'
    (args.output / source.name).write_bytes(source.read_bytes())
    receipt = {'status': 'running', 'uid': os.getuid(), 'producer_sha256': digest(Path(__file__)),
               'fixture_source_sha256': digest(source), 'hyprland_sha256': SHA, 'parent_sha256': digest(PARENT),
               'android': False, 'physical_device': False, 'hardware_gpu': False}
    toolkit = None
    parent = compositor = client = None
    try:
        if args.toolkit_build_receipt:
            toolkit, receipt['toolkit'] = toolkit_library(args.toolkit_build_receipt)
        with tempfile.TemporaryDirectory(prefix='htp-') as folder, contextlib.ExitStack() as children:
            runtime = Path(folder); runtime.chmod(0o700)
            binary = runtime / 'toolkit-pixels'
            flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'hyprtoolkit'], text=True))
            command = ['c++', '-std=c++26', str(source), '-o', str(binary), *flags]
            with (args.output / 'fixture-build.log').open('x') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
            receipt['fixture_build_command'] = command
            receipt['fixture_binary_sha256'] = digest(binary)
            config = runtime / 'hyprland.lua'
            config.write_text('hl.config({animations={enabled=false},debug={disable_logs=false,enable_stdout_logs=true}})\n')
            env = dict(PATH='/usr/bin:/bin', HOME=folder, USER='loopy', LOGNAME='loopy', LANG='C.UTF-8',
                XDG_RUNTIME_DIR=folder, XDG_CONFIG_HOME=folder + '/config', XDG_CACHE_HOME=folder + '/cache',
                XDG_DATA_HOME=folder + '/data', XDG_STATE_HOME=folder + '/state', LD_LIBRARY_PATH=str(LIBRARY),
                WAYLAND_DISPLAY='loopy-parent', AQ_SHM_ONLY='1', LIBGL_ALWAYS_SOFTWARE='1',
                HYPRLAND_NO_SD_NOTIFY='1', HYPRLAND_NO_SD_VARS='1', LOOPY_SESSION='owned-toolkit-pixels')
            if toolkit:
                env['LD_LIBRARY_PATH'] = str(toolkit.parent) + ':' + env['LD_LIBRARY_PATH']
            with (args.output / 'parent.log').open('x') as plog, (args.output / 'hyprland.log').open('x') as hlog, \
                 (args.output / 'fixture.log').open('x') as clog:
                parent = subprocess.Popen([str(PARENT), str(runtime / 'loopy-parent'), '12', 'orientation-fixture'],
                    stdin=subprocess.PIPE, stdout=plog, stderr=subprocess.STDOUT, text=True, start_new_session=True)
                children.callback(stop, parent)
                wait(lambda: (runtime / 'loopy-parent').is_socket(), [parent])
                compositor = subprocess.Popen([str(BINARY), '--config', str(config)], env=env,
                    stdout=hlog, stderr=subprocess.STDOUT, start_new_session=True)
                children.callback(stop, compositor)
                sockets = wait(lambda: [p for p in runtime.glob('wayland-*') if p.is_socket()], [parent, compositor])
                assert len(sockets) == 1
                client = subprocess.Popen([str(binary)], env={**env, 'WAYLAND_DISPLAY': sockets[0].name, 'WAYLAND_DEBUG': '1'},
                    stdout=clog, stderr=subprocess.STDOUT, start_new_session=True)
                children.callback(stop, client)
                wait(lambda: 'wl_surface#' in (args.output / 'fixture.log').read_text()
                     or 'wl_surface@' in (args.output / 'fixture.log').read_text(), [parent, compositor, client])
                if toolkit:
                    assert str(toolkit) in Path(f'/proc/{client.pid}/maps').read_text()
                    receipt['fixture_loaded_verified_toolkit'] = True
                # Allow the actual layer's configure/map round trip before fixed public input.
                time.sleep(.7)
                parent.stdin.write('click\ntype\n'); parent.stdin.flush()
                wait(lambda: 'fixture-ready clicked=true typed=loopy' in (args.output / 'fixture.log').read_text(),
                     [parent, compositor, client], seconds=8)
                receipt['actual_toolkit_click_and_keyboard'] = True
                time.sleep(.15)
                # Read only this private VM display's public fixture. Retain six
                # RGB samples, never a screenshot of the user's desktop.
                ppm = subprocess.check_output(['/usr/bin/grim', '-t', 'ppm', '-'],
                    env={**env, 'WAYLAND_DISPLAY': sockets[0].name}, timeout=3)
                magic, dimensions, maximum, pixels = ppm.split(b'\n', 3)
                assert (magic, dimensions, maximum) == (b'P6', b'640 360', b'255') and len(pixels) == 640 * 360 * 3
                receipt['fixture_rgb_samples'] = {str(y): [list(pixels[(y * 640 + x) * 3:(y * 640 + x) * 3 + 3])
                    for x in [80, 320, 560]] for y in [48, 312]}
                parent.wait(timeout=15)
                receipt['parent_exit'] = parent.returncode
                assert parent.returncode == 0
                receipt['wire_buffer_ownership'] = release_order((args.output / 'fixture.log').read_text())
                receipt['top_red_bottom_green'] = 'fixture_pixel_match=true' in (args.output / 'parent.log').read_text()
                assert receipt['top_red_bottom_green'], 'actual composited top/bottom pixels differ from original toolkit layout'
                receipt['status'] = 'passed'
    except BaseException as error:
        receipt.update(status='failed', error=str(error))
    finally:
        stop(client); stop(compositor); stop(parent)
        receipt['owned_children_stopped'] = all(p is None or p.poll() is not None for p in (client, compositor, parent))
        (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
