#!/usr/bin/env python3
"""Exercise genuine pinned start-hyprland crash recovery in the owned ARM VM."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import shlex
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.probe_hyprland_clipboard import PARENT, LIBRARY, digest
from tools.probe_hyprland_rootless import stop

BINARY = Path('/var/tmp/loopy-hyprland-reproduced-build/Hyprland')
WATCHDOG = Path('/usr/bin/start-hyprland')
CONTROL = BINARY.parent / 'hyprctl/hyprctl'
SHA = '1c61c2910a7fe92cd716c58cb57b3cc7d67c1b181040138ea30d2f041038ddfc'
WATCHDOG_SHA = '29f40097d5fe3ded68c57a9b53d6a39e1051cafb9d05474a205316dfe1baf8d0'


def toolkit_library(path):
    """Accept only a completed, byte-verified build in this owned ARM VM."""
    assert path.parent == ROOT / 'docs/validation/2026-10-06-omarchy'
    assert path.name.startswith('hyprtoolkit-build-') and path.suffix == '.json'
    assert path.is_file() and not path.is_symlink()
    build = json.loads(path.read_text())
    assert build['status'] == 'compiled-in-reference-vm' and build['build_exit'] == 0
    assert build['architecture'] == 'aarch64' and build['uid'] == os.getuid() == 501
    binary = Path(build['binary_path'])
    assert binary == Path('/var/tmp/loopy-hyprtoolkit-build-20261007/libhyprtoolkit.so.0.6.0')
    assert binary.is_file() and not binary.is_symlink()
    assert binary.stat().st_size == build['binary_bytes'] and digest(binary) == build['binary_sha256']
    assert digest(LIBRARY / 'libaquamarine.so.0.15.1') == build['aquamarine_sha256']
    return binary, {'build_receipt': str(path.relative_to(ROOT)), 'build_receipt_sha256': digest(path),
                    'binary_path': str(binary), 'binary_sha256': digest(binary)}


def wait(check, processes, seconds=12):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = check()
        if value: return value
        assert all(p.poll() is None for p in processes), 'owned process exited before readiness'
        time.sleep(.03)
    raise AssertionError('owned compositor readiness timed out')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['direct', 'watchdog'], required=True)
    parser.add_argument('--private-dialog', action='store_true')
    parser.add_argument('--trace-dialog', action='store_true')
    parser.add_argument('--debug-dialog', action='store_true')
    parser.add_argument('--check-toolkit', action='store_true')
    parser.add_argument('--toolkit-build-receipt', type=Path)
    parser.add_argument('--load-config', action='store_true')
    parser.add_argument('--binary', type=Path, default=BINARY)
    parser.add_argument('--sha256', default=SHA)
    args = parser.parse_args()
    if args.trace_dialog and not args.private_dialog:
        parser.error('--trace-dialog requires the private owned dialog fixture')
    if (args.debug_dialog or args.check_toolkit) and not args.trace_dialog:
        parser.error('dialog diagnostics require --trace-dialog')
    if args.load_config and not args.trace_dialog:
        parser.error('load-config acceptance requires the original dialog output witness')
    assert ROOT == Path('/workspace') and os.getuid() == 501 and os.uname().machine == 'aarch64'
    assert Path('/etc/hostname').read_text().strip() == 'loopy-omarchy-build'
    assert args.output.parent == ROOT / 'docs/validation/2026-10-06-omarchy'
    assert args.output.name.startswith('watchdog-native-')
    binary = args.binary
    assert binary.name == 'Hyprland' and binary.parent.parent == Path('/var/tmp')
    assert binary.parent.name.startswith('loopy-hyprland-') and not binary.is_symlink()
    assert digest(binary) == args.sha256 and digest(WATCHDOG) == WATCHDOG_SHA
    args.output.mkdir(); resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    (args.output / 'producer.py').write_bytes(Path(__file__).read_bytes())
    receipt = {'status': 'running', 'mode': args.mode, 'uid': os.getuid(),
        'producer_sha256': digest(Path(__file__)), 'hyprland_sha256': args.sha256, 'watchdog_sha256': WATCHDOG_SHA,
        'parent_sha256': digest(PARENT), 'private_dialog': args.private_dialog,
        'android': False, 'physical_device': False, 'hardware_gpu': False}
    toolkit = None
    if args.toolkit_build_receipt:
        toolkit, receipt['toolkit'] = toolkit_library(args.toolkit_build_receipt)
    parent = launcher = None
    try:
        with tempfile.TemporaryDirectory(prefix='lhw-') as folder, contextlib.ExitStack() as children:
            runtime = Path(folder); runtime.chmod(0o700)
            config = runtime / 'hyprland.lua'
            config.write_text('hl.config({animations={enabled=false},debug={disable_logs=false,enable_stdout_logs=true}})\n')
            if args.load_config:
                with config.open('a') as output:
                    output.write("local p=assert(io.open(" + json.dumps(str(runtime / 'parsed-events')) + ", 'a')); p:write('parsed\\n'); p:close()\n"
                        + "hl.on('hyprland.start', function() local f=assert(io.open(" + json.dumps(str(runtime / 'startup-events'))
                        + ", 'a')); f:write(os.getenv('HYPRLAND_INSTANCE_SIGNATURE')..'\\n'); f:close() end)\n")
                (args.output / 'witness-config.lua').write_bytes(config.read_bytes())
            programs = runtime / 'bin'; programs.mkdir()
            if args.private_dialog:
                dialog = programs / 'hyprland-dialog'
                shutil.copyfile('/usr/bin/hyprland-dialog', dialog); dialog.chmod(0o700)
                receipt['private_dialog_sha256'] = digest(dialog)
                if args.trace_dialog:
                    real = programs / 'hyprland-dialog-real'; dialog.rename(real)
                    debugger = "/usr/bin/gdb --batch --return-child-result -ex 'set debuginfod enabled off' -ex run -ex bt --args " if args.debug_dialog else ''
                    check = ''
                    if args.check_toolkit:
                        probe = Path('/var/tmp/loopy-watchdog-toolkit-20261007/probe')
                        assert digest(probe) == '195ecbd67a4b6d180c1a19bd4be194a2e2256a5cfad22ea8f88b03edcf7bb6b0'
                        check = shlex.quote(str(probe)) + ' >' + shlex.quote(str(args.output / 'toolkit.log')) + ' 2>&1\n'
                    wire = 'WAYLAND_DEBUG=1 ' if args.load_config else ''
                    dialog.write_text('#!/bin/sh\n' + check + wire + debugger + shlex.quote(str(real))
                        + ' "$@" >' + shlex.quote(str(args.output / 'dialog-stdout.log'))
                        + ' 2>' + shlex.quote(str(args.output / 'dialog-stderr.log'))
                        + '\ncode=$?\nprintf "%s\\n" "$code" >' + shlex.quote(str(args.output / 'dialog-exit.txt'))
                        + '\ncat ' + shlex.quote(str(args.output / 'dialog-stdout.log')) + '\nexit "$code"\n')
                    dialog.chmod(0o700)
            env = dict(PATH=str(programs) + ':/usr/bin:/bin', HOME=folder, USER='loopy', LOGNAME='loopy', LANG='C.UTF-8',
                XDG_RUNTIME_DIR=folder, XDG_CONFIG_HOME=folder + '/config', XDG_CACHE_HOME=folder + '/cache',
                XDG_DATA_HOME=folder + '/data', XDG_STATE_HOME=folder + '/state', LD_LIBRARY_PATH=str(LIBRARY),
                WAYLAND_DISPLAY='loopy-parent', AQ_SHM_ONLY='1', LIBGL_ALWAYS_SOFTWARE='1',
                HYPRLAND_NO_SD_NOTIFY='1', HYPRLAND_NO_SD_VARS='1', LOOPY_SESSION='owned-watchdog-reference')
            if toolkit:
                env['LD_LIBRARY_PATH'] = str(toolkit.parent) + ':' + env['LD_LIBRARY_PATH']
            with (args.output / 'parent.log').open('x') as plog, (args.output / 'hyprland.log').open('x') as hlog:
                parent = subprocess.Popen([str(PARENT), str(runtime / 'loopy-parent'), '55', 'scene-fixture'],
                    stdin=subprocess.PIPE, stdout=plog, stderr=subprocess.STDOUT, text=True, start_new_session=True)
                children.callback(stop, parent)
                wait(lambda: (runtime / 'loopy-parent').is_socket(), [parent])
                command = [str(binary), '--config', str(config)]
                if args.mode == 'watchdog':
                    command = [str(WATCHDOG), '--no-nixgl', '--path', str(binary), '--', '--config', str(config)]
                receipt['command'] = command
                launcher = subprocess.Popen(command, env=env, stdout=hlog, stderr=subprocess.STDOUT, start_new_session=True)
                children.callback(stop, launcher)

                def current(exclude=0):
                    try:
                        entries = json.loads(subprocess.check_output([str(CONTROL), 'instances', '-j'], env=env, timeout=2))
                        for entry in entries:
                            pid = entry['pid']
                            if pid == exclude: continue
                            proc = Path('/proc') / str(pid)
                            words = proc.joinpath('cmdline').read_bytes().split(b'\0')
                            if words[0] != str(binary).encode(): continue
                            stat = proc.joinpath('stat').read_text().split(') ', 1)[1].split()
                            if stat[0] == 'Z' or int(stat[1]) != (launcher.pid if args.mode == 'watchdog' else os.getpid()): continue
                            response = subprocess.run([str(CONTROL), '-i', entry['instance'], '-j', 'monitors'],
                                env=env, capture_output=True, text=True, timeout=2)
                            if response.returncode != 0 or not json.loads(response.stdout): continue
                            return {'pid': pid, 'parent': int(stat[1]), 'start_ticks': stat[19],
                                    'instance': entry['instance'], 'argv': [v.decode() for v in words if v]}
                    except (OSError, ValueError, KeyError, subprocess.SubprocessError): pass
                    return None

                first = wait(current, [parent, launcher]); receipt['first'] = first
                if args.load_config:
                    wait(lambda: (runtime / 'startup-events').is_file(), [parent, launcher])
                    assert (runtime / 'startup-events').read_text().splitlines() == [first['instance']]
                assert '--watchdog-fd' in first['argv'], 'actual compositor bypasses the original watchdog'
                fd = int(first['argv'][first['argv'].index('--watchdog-fd') + 1])
                pipe = os.readlink(f'/proc/{first["pid"]}/fd/{fd}')
                assert pipe.startswith('pipe:[')
                assert any(os.readlink(p) == pipe for p in Path(f'/proc/{launcher.pid}/fd').iterdir())
                receipt['shared_watchdog_pipe'] = True
                os.kill(first['pid'], signal.SIGKILL)
                recovered = wait(lambda: current(first['pid']), [parent, launcher]); receipt['recovered'] = recovered
                assert '--safe-mode' in recovered['argv'] and '--watchdog-fd' in recovered['argv']
                receipt['original_watchdog_restarted_safe_mode'] = True
                def dialog_window():
                    try:
                        clients = json.loads(subprocess.check_output([str(CONTROL), '-i', recovered['instance'], '-j', 'clients'],
                            env=env, timeout=2))
                        receipt['last_recovery_clients'] = clients
                        for client in clients:
                            executable = Path('/proc') / str(client['pid']) / 'exe'
                            if (client['mapped'] and
                                digest(executable) == '4092556c0a1acb05c106f246e24ec0d687baddf721c621ace06d3b957d1c5e36'):
                                if toolkit:
                                    maps = executable.parent.joinpath('maps').read_text()
                                    assert str(toolkit) in maps, 'dialog did not load the verified toolkit'
                                    receipt['dialog_loaded_verified_toolkit'] = True
                                return {key: client[key] for key in ['pid', 'class', 'title', 'mapped']}
                    except (OSError, ValueError, KeyError, subprocess.SubprocessError): pass
                    return None
                try:
                    receipt['original_recovery_dialog_window'] = wait(dialog_window, [parent, launcher])
                finally:
                    for number, log in enumerate(sorted(runtime.glob('hypr/*/hyprland.log'))):
                        shutil.copyfile(log, args.output / f'compositor-{number}.log')
                if args.load_config:
                    from tools.probe_wayland_pointer import click
                    helper = ROOT / 'tools/probe_wayland_pointer.py'
                    (args.output / helper.name).write_bytes(helper.read_bytes())
                    receipt['pointer_producer_sha256'] = digest(helper)
                    # Give the real original dialog an ordinary 640x360 logical output.
                    reply = subprocess.check_output([str(CONTROL), '-i', recovered['instance'], 'eval',
                        "hl.monitor({output='',mode='preferred',position='auto',scale=1})"], env=env, timeout=3)
                    assert reply.strip() == b'ok'
                    reply = subprocess.check_output([str(CONTROL), '-i', recovered['instance'], 'dispatch',
                        "hl.dsp.window.move({x=40,y=60,relative=false,window='class:hyprland-dialog'})"], env=env, timeout=3)
                    assert reply.strip() == b'ok'
                    time.sleep(.5)
                    clients = json.loads(subprocess.check_output([str(CONTROL), '-i', recovered['instance'], '-j', 'clients'], env=env, timeout=3))
                    window = next(v for v in clients if v['class'] == 'hyprland-dialog' and v['mapped'])
                    wl_socket = (runtime / 'hypr' / recovered['instance'] / 'hyprland.lock').read_text().splitlines()[1]
                    # Measured on this original 550px native dialog: the button
                    # row is right-aligned, so Load config is centered at x=185.
                    point = (window['at'][0] + 185, window['at'][1] + window['size'][1] - 20)
                    receipt['load_config_click'] = {'window': window, 'point': point, 'display': wl_socket}
                    subprocess.run(['/usr/bin/grim', str(args.output / 'dialog-before.png')],
                        env={**env, 'WAYLAND_DISPLAY': wl_socket}, check=True, timeout=3)
                    click(runtime / wl_socket, *point, 640, 360)
                    receipt['cursor_after_click'] = json.loads(subprocess.check_output([str(CONTROL), '-i', recovered['instance'],
                        '-j', 'cursorpos'], env=env, timeout=3))
                    wait(lambda: (args.output / 'dialog-exit.txt').exists(), [parent, launcher])
                    receipt['dialog_choice'] = (args.output / 'dialog-stdout.log').read_text().strip()
                    assert receipt['dialog_choice'].startswith('Load config'), 'original dialog selected another action'
                    wait(lambda: len((runtime / 'parsed-events').read_text().splitlines()) == 2, [parent, launcher])
                    time.sleep(.4)
                    receipt['parsed_events'] = (runtime / 'parsed-events').read_text().splitlines()
                    receipt['startup_events'] = (runtime / 'startup-events').read_text().splitlines()
                    assert receipt['startup_events'] == [first['instance'], recovered['instance']], 'original config startup was not delivered after leaving safe mode'
                    reply = subprocess.check_output([str(CONTROL), '-i', recovered['instance'], 'reload'], env=env, timeout=3)
                    assert reply.strip() == b'ok'
                    wait(lambda: len((runtime / 'parsed-events').read_text().splitlines()) == 3, [parent, launcher])
                    time.sleep(.2)
                    assert (runtime / 'startup-events').read_text().splitlines() == receipt['startup_events'], 'ordinary reload duplicated session startup'
                    receipt['ordinary_reload_preserves_single_startup'] = True
                reply = subprocess.run([str(CONTROL), '-i', recovered['instance'], 'dispatch', 'hl.dsp.exit()'],
                    env=env, capture_output=True, text=True, timeout=3)
                receipt['clean_exit_reply'] = {'code': reply.returncode, 'stdout': reply.stdout, 'stderr': reply.stderr}
                assert reply.returncode == 0, 'Lua-config compositor rejected explicit exit'
                launcher.wait(timeout=8)
                assert launcher.returncode == 0 and not Path(f'/proc/{recovered["pid"]}').exists()
                receipt['clean_exit_without_restart'] = True
                receipt['status'] = 'passed'
    except BaseException as error:
        import traceback
        receipt.update(status='failed', error=repr(error), traceback=traceback.format_exc())
    finally:
        stop(launcher); stop(parent)
        receipt['owned_children_stopped'] = all(p is None or p.poll() is not None for p in (launcher, parent))
        (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__': raise SystemExit(main())
