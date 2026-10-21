#!/usr/bin/env python3
"""Real private Hyprland WLR/ext selection clearing, including source loss.

Runs only in the owned ARM build VM. This is compositor protocol evidence,
not Android clipboard, physical input, GPU or complete Omarchy acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT), str(ROOT / 'android/assets/omarchy-bridge')]
from tools.probe_hyprland_rootless import stop
from wayland_clipboard import Client, UINT, parse_string, string

PARENT = Path('/var/tmp/loopy-omarchy-target/debug/examples/omarchy_parent')
LIBRARY = Path('/var/tmp/loopy-aquamarine-cursor')
PROTOCOLS = ('zwlr_data_control_manager_v1', 'ext_data_control_manager_v1')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Observer(Client):
    """ext-data-control v1 uses the same request/event wire layout as WLR v2."""
    def __init__(self, path, protocol):
        self.protocol, self.primary, self.exports = protocol, [], []
        super().__init__(path, lambda state, data: self.exports.append((state, data)))

    def bind(self, interface, kind, maximum_version=1):
        if interface == PROTOCOLS[0]:
            interface = self.protocol
            if interface == PROTOCOLS[1]: maximum_version = 1
        return super().bind(interface, kind, maximum_version)

    def event(self, obj, opcode, body):
        if self.objects.get(obj) == 'registry' and opcode == 0:
            interface, end = parse_string(body, 4)
            if interface == PROTOCOLS[1]:
                self.globals[interface] = (UINT.unpack_from(body)[0], UINT.unpack_from(body, end)[0])
        if self.objects.get(obj) == 'device' and opcode == 3:
            self.primary.append(UINT.unpack(body)[0] != 0)
        return super().event(obj, opcode, body)

    def set_primary(self, value):
        source = 0
        if value:
            source = self.new('source'); self.sources[source] = value
            self.send(self.manager, 0, UINT.pack(source))
            self.send(source, 0, string('text/plain;charset=utf-8'))
        self.send(self.device, 2, UINT.pack(source))


def wait_for(clients, condition, seconds=1.5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        for client in clients: client.pump()
        if condition(): return True
        time.sleep(.005)
    return False


def exercise(path, protocol):
    result = {}; watcher, owner = Observer(path, protocol), None
    try:
        owner = Observer(path, protocol)
        for primary in (False, True):
            key = 'primary' if primary else 'clipboard'
            events = watcher.primary if primary else watcher.exports
            change = owner.set_primary if primary else owner.set_selection
            data = 'owned public 한글🙂'.encode()
            events.clear(); change(data)
            assert wait_for([owner, watcher], lambda: bool(events) and
                            (events[-1] is True if primary else events[-1] == ('data', data))), key + ' publication'
            events.clear(); change(b'')
            cleared = lambda: bool(events) and (events[-1] is False if primary else events[-1] == ('nil', b''))
            result[key + '_clear_notification'] = wait_for([owner, watcher], cleared)
            # A new binding independently reads the actual compositor state.
            fresh = Observer(path, protocol)
            try:
                result[key + '_actual_selection_empty'] = (fresh.primary == [False] if primary
                    else fresh.exports == [('nil', b'')])
            finally: fresh.close()
            events.clear(); change(data)
            assert wait_for([owner, watcher], lambda: bool(events) and
                            (events[-1] is True if primary else events[-1] == ('data', data))), key + ' republish'
            events.clear(); owner.close(); owner = None
            result[key + '_source_exit_notification'] = wait_for([watcher], cleared)
            owner = Observer(path, protocol)
        return result
    finally:
        if owner is not None: owner.close()
        watcher.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert ROOT == Path('/workspace') and os.getuid() == 501 and os.uname().machine == 'aarch64'
    assert Path('/etc/hostname').read_text().strip() == 'loopy-omarchy-build'
    assert args.binary.is_file() and digest(args.binary) == args.sha256
    assert args.output.parent == ROOT / 'docs/validation/2026-10-06-omarchy'
    assert args.output.name.startswith('clipboard-native-')
    args.output.mkdir(); resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    receipt = {'status': 'running', 'uid': os.getuid(), 'physical_device': False, 'android_surface': False,
               'hardware_gpu': False, 'omarchy_support_complete': False, 'binary_sha256': args.sha256,
               'observer_sha256': digest(Path(__file__)), 'wire_sha256': digest(ROOT / 'android/assets/omarchy-bridge/wayland_clipboard.py'),
               'parent_sha256': digest(PARENT), 'library_sha256': digest(LIBRARY / 'libaquamarine.so.0.15.1'),
               'ext_xml_sha256': digest(Path('/usr/share/wayland-protocols/staging/ext-data-control/ext-data-control-v1.xml'))}
    parent = compositor = None
    try:
        with tempfile.TemporaryDirectory(prefix='loopy-clipboard-') as directory:
            runtime = Path(directory); runtime.chmod(0o700)
            config = runtime / 'hyprland.lua'
            config.write_text('hl.config({animations={enabled=false},debug={disable_logs=false,enable_stdout_logs=true}})\n')
            env = dict(PATH='/usr/bin:/bin', HOME=directory, USER='loopy', LOGNAME='loopy', LANG='C.UTF-8',
                       XDG_RUNTIME_DIR=directory, XDG_CONFIG_HOME=directory + '/config', XDG_CACHE_HOME=directory + '/cache',
                       XDG_DATA_HOME=directory + '/data', XDG_STATE_HOME=directory + '/state', LD_LIBRARY_PATH=str(LIBRARY),
                       WAYLAND_DISPLAY='loopy-parent', AQ_SHM_ONLY='1', LIBGL_ALWAYS_SOFTWARE='1',
                       HYPRLAND_NO_SD_NOTIFY='1', HYPRLAND_NO_SD_VARS='1')
            with (args.output / 'parent.log').open('x') as p, (args.output / 'hyprland.log').open('x') as h:
                parent = subprocess.Popen([str(PARENT), str(runtime / 'loopy-parent'), '30', 'scene-fixture'],
                    stdin=subprocess.PIPE, stdout=p, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 3
                while not (runtime / 'loopy-parent').is_socket():
                    assert parent.poll() is None and time.monotonic() < deadline, 'owned parent startup'
                    time.sleep(.02)
                compositor = subprocess.Popen([str(args.binary), '--config', str(config)], env=env,
                    stdout=h, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 6; sockets = []
                while not sockets:
                    sockets = [p for p in runtime.glob('wayland-*') if p.is_socket()]
                    assert compositor.poll() is None and time.monotonic() < deadline, 'owned Hyprland startup'
                    time.sleep(.02)
                assert len(sockets) == 1, 'unique owned inner display'
                receipt['protocols'] = {name: exercise(sockets[0], name) for name in PROTOCOLS}
                receipt['compositor_alive'] = compositor.poll() is None
                receipt['status'] = 'passed' if receipt['compositor_alive'] and all(
                    all(checks.values()) for checks in receipt['protocols'].values()) else 'failed'
    except BaseException as error:
        receipt.update(status='failed', error=str(error))
    finally:
        stop(compositor); stop(parent)
        receipt['owned_children_stopped'] = all(p is None or p.poll() is not None for p in (compositor, parent))
        (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__': sys.exit(main())
