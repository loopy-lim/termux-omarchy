#!/usr/bin/env python3
"""Run the real action worker against a real, owned Hyprland and then kill that compositor."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from tools.probe_hyprland_watchdog import BINARY, CONTROL, SHA, PARENT, LIBRARY, digest, stop, wait

CHILD = '''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from hyprland_actions import Hyprland
from session_actions import Worker,configure_input
runtime=Path(os.environ['XDG_RUNTIME_DIR'])
token=os.environ['LOOPY_SESSION']; signature=os.environ['HYPRLAND_INSTANCE_SIGNATURE']
with Worker(runtime,token,Hyprland(runtime/'hypr'/signature/'.socket.sock')) as worker:
    worker.compositor.query('activeworkspace')
    worker.display=configure_input(runtime,token,os.environ['WAYLAND_DISPLAY'])
    worker.ready(signature)
    worker.watch()
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    assert ROOT == Path('/workspace') and os.getuid() == 501 and os.uname().machine == 'aarch64'
    assert Path('/etc/hostname').read_text().strip() == 'loopy-omarchy-build'
    assert args.output.parent == ROOT / 'docs/validation/2026-10-06-omarchy'
    assert args.output.name.startswith('worker-native-') and digest(BINARY) == SHA
    args.output.mkdir(); resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    (args.output / 'producer.py').write_bytes(Path(__file__).read_bytes())
    assets = ROOT / 'android/assets/omarchy-bridge'
    sys.path.insert(0, str(assets))
    from hyprland_actions import Hyprland
    inputs = {str(p.relative_to(ROOT)): digest(p) for p in assets.glob('*.py')}
    for name in inputs:
        target = args.output / 'inputs' / name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    receipt = {'status': 'running', 'uid': os.getuid(), 'hyprland_sha256': SHA,
        'producer_sha256': digest(Path(__file__)), 'inputs': inputs, 'android': False,
        'hardware_gpu': False, 'physical_device': False}
    parent = compositor = worker = None
    try:
        with tempfile.TemporaryDirectory(prefix='hlw-') as folder, contextlib.ExitStack() as children:
            runtime = Path(folder); runtime.chmod(0o700); token = str(uuid.uuid4())
            config = runtime / 'hyprland.lua'
            config.write_text('hl.config({animations={enabled=false},debug={disable_logs=false,enable_stdout_logs=true}})\n')
            env = dict(PATH='/usr/bin:/bin', HOME=folder, USER='loopy', LOGNAME='loopy', LANG='C.UTF-8',
                XDG_RUNTIME_DIR=folder, XDG_CONFIG_HOME=folder + '/config', XDG_CACHE_HOME=folder + '/cache',
                XDG_DATA_HOME=folder + '/data', XDG_STATE_HOME=folder + '/state', LD_LIBRARY_PATH=str(LIBRARY),
                WAYLAND_DISPLAY='loopy-parent', AQ_SHM_ONLY='1', LIBGL_ALWAYS_SOFTWARE='1',
                HYPRLAND_NO_SD_NOTIFY='1', HYPRLAND_NO_SD_VARS='1', LOOPY_SESSION=token)
            with (args.output / 'parent.log').open('x') as plog, (args.output / 'hyprland.log').open('x') as hlog, \
                 (args.output / 'worker.log').open('x') as wlog:
                parent = subprocess.Popen([str(PARENT), str(runtime / 'loopy-parent'), '40', 'scene-fixture'],
                    stdout=plog, stderr=subprocess.STDOUT, start_new_session=True)
                children.callback(stop, parent)
                wait(lambda: (runtime / 'loopy-parent').is_socket(), [parent])
                compositor = subprocess.Popen([str(BINARY), '--config', str(config)], env=env,
                    stdout=hlog, stderr=subprocess.STDOUT, start_new_session=True)
                children.callback(stop, compositor)
                sockets = wait(lambda: [p for p in runtime.glob('hypr/*/.socket.sock') if p.is_socket()], [parent, compositor])
                assert len(sockets) == 1
                def instance_ready():
                    try:
                        instances = json.loads(subprocess.check_output([str(CONTROL), 'instances', '-j'], env=env, timeout=3))
                        return next((v for v in instances if v['pid'] == compositor.pid and
                            (runtime / v['wl_socket']).is_socket()), None)
                    except (ValueError, KeyError, subprocess.SubprocessError):
                        return None
                instance = wait(instance_ready, [parent, compositor])
                def client():
                    return Hyprland(runtime / 'hypr' / instance['instance'] / '.socket.sock')
                def enqueue(index, target, created):
                    name = runtime / ('command-%s-%016d.json' % (token, index))
                    temporary = name.with_suffix('.new')
                    temporary.write_text(json.dumps({'action': 'workspace', 'target': target, 'created_ns': created}))
                    temporary.rename(name)
                    return name
                enqueue(1, '2', time.monotonic_ns())
                worker_env = {**env, 'WAYLAND_DISPLAY': instance['wl_socket'], 'HYPRLAND_INSTANCE_SIGNATURE': instance['instance']}
                worker = subprocess.Popen(['/usr/bin/python', '-B', '-c', CHILD, str(assets)], env=worker_env,
                    stdout=wlog, stderr=subprocess.STDOUT, start_new_session=True)
                children.callback(stop, worker)
                ready = runtime / ('actions-' + token + '.ready.json')
                wait(ready.is_file, [parent, compositor, worker])
                wait(lambda: client().query('activeworkspace')['id'] == 2, [parent, compositor, worker])
                time.sleep(.2)
                assert worker.poll() is None
                assert not (runtime / ('error-' + token + '.log')).exists(), 'worker already failed before compositor exit'
                receipt['ready'] = json.loads(ready.read_text())
                stale_created = time.monotonic_ns()
                os.kill(compositor.pid, signal.SIGKILL); compositor.wait(timeout=3)
                try:
                    worker.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
                receipt['worker_exit'] = worker.poll()
                receipt['worker_still_live'] = worker.poll() is None
                receipt['ready_after_compositor_exit'] = ready.exists()
                error = runtime / ('error-' + token + '.log')
                receipt['idle_disconnect_error'] = error.read_text() if error.is_file() else None
                assert worker.poll() == 0, 'old action worker survived compositor loss'
                assert not ready.exists() and not (runtime / ('ready-' + token)).exists(), 'stale readiness remains'
                assert not error.exists(), 'idle compositor loss was reported as a failed input command'
                assert not (runtime / ('display-' + token)).exists(), 'old display binding remains'
                previous = instance
                stale = enqueue(2, '9', stale_created)
                replacement_socket = children.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
                replacement_socket.bind(str(runtime / 'replacement-wayland')); replacement_socket.listen(16)
                compositor = subprocess.Popen([str(BINARY), '--config', str(config), '--socket', 'replacement-wayland',
                    '--wayland-fd', str(replacement_socket.fileno())], env=env, pass_fds=(replacement_socket.fileno(),),
                    stdout=hlog, stderr=subprocess.STDOUT, start_new_session=True)
                children.callback(stop, compositor)
                instance = wait(instance_ready, [parent, compositor])
                assert instance['instance'] != previous['instance'], 'replacement compositor identity did not change'
                assert instance['wl_socket'] != previous['wl_socket'], 'explicit Wayland socket handover did not apply'
                worker_env.update(WAYLAND_DISPLAY=instance['wl_socket'], HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
                worker = subprocess.Popen(['/usr/bin/python', '-B', '-c', CHILD, str(assets)], env=worker_env,
                    stdout=wlog, stderr=subprocess.STDOUT, start_new_session=True)
                children.callback(stop, worker)
                wait(ready.is_file, [parent, compositor, worker])
                wait(lambda: not stale.exists(), [parent, compositor, worker])
                assert error.is_file() and client().query('activeworkspace')['id'] == 1, 'stale input entered the new compositor'
                enqueue(3, '3', time.monotonic_ns())
                wait(lambda: client().query('activeworkspace')['id'] == 3, [parent, compositor, worker])
                receipt['replacement'] = {'first_display': previous['wl_socket'], 'new_display': instance['wl_socket'],
                    'new_signature': instance['instance'], 'stale_workspace_rejected': True, 'fresh_workspace': 3,
                    'display_marker': (runtime / ('display-' + token)).read_text().strip()}
                error.unlink()  # This probe created and checked the expected stale-input error.
                os.kill(compositor.pid, signal.SIGKILL); compositor.wait(timeout=3); worker.wait(timeout=3)
                assert worker.returncode == 0 and not ready.exists() and not error.exists()
                assert not (runtime / ('display-' + token)).exists()
                receipt['status'] = 'passed'
    except BaseException as error:
        import traceback
        receipt.update(status='failed', error=repr(error), traceback=traceback.format_exc())
    finally:
        stop(worker); stop(compositor); stop(parent)
        receipt['owned_children_stopped'] = all(p is None or p.poll() is not None for p in (worker, compositor, parent))
        (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'inputs'}), flush=True)
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
