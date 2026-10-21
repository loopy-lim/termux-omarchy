#!/data/data/com.termux/files/usr/bin/python3
"""Owned native i3/X11 session. Public actions return one bounded JSON object."""
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import uuid

from processes import (OwnedProcesses, atomic_json, enable_subreaper, identity, private_directory,
                       read_json, run_bounded, same_identity, same_process, signal_process)
import preferences

ACTIONS = {'start', 'stop', 'doctor', 'input', 'restore'}
TAG = 'loopy-native'


def validate_request(action, request):
    if action not in ACTIONS or not isinstance(request, str) or len(request) != 36:
        raise ValueError('invalid native action/request')
    if str(uuid.UUID(request)) != request:
        raise ValueError('request must be a canonical UUID')


def result(action, request, status, display='', **fields):
    response = {'schema': 1, 'action': action, 'request': request, 'status': status,
                'uid': os.getuid(), 'display': display}
    response.update(fields)
    if 'reason' in response:
        response['reason'] = str(response['reason'])[:2048]
    return response


def encode_result(response):
    encoded = json.dumps(response, ensure_ascii=True, separators=(',', ':'))
    if len(encoded.encode()) > 16384:
        raise ValueError('native result exceeds 16KiB')
    return encoded


class Runtime:
    def __init__(self, home, prefix):
        self.home, self.prefix = Path(home), Path(prefix)
        self.root = private_directory(self.home, '.local/share/loopy-native')
        self.path = self.root / 'state.json'
        self.env = os.environ.copy()
        for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'DBUS_SESSION_BUS_ADDRESS', 'LD_LIBRARY_PATH',
                    'GALLIUM_DRIVER', 'MESA_LOADER_DRIVER_OVERRIDE', 'VTEST_SOCKET_NAME',
                    'VK_DRIVER_FILES', 'VK_ICD_FILENAMES', 'VN_DEBUG', 'TERMUX_X11_XSTARTUP',
                    'I3SOCK', 'XAUTHORITY', 'DBUS_STARTER_ADDRESS'):
            self.env.pop(key, None)
        self.env.update(HOME=str(self.home), PREFIX=str(self.prefix),
                        PATH=f'{self.prefix}/bin:/system/bin', TMPDIR=str(self.prefix / 'tmp'),
                        LIBGL_ALWAYS_SOFTWARE='true', GDK_BACKEND='x11')
        for key in ('LANG', 'LC_ALL', 'LC_CTYPE'):
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_@.-]{0,63}', self.env.get(key, '')):
                self.env.pop(key, None)
        self.env.setdefault('LANG', 'C.UTF-8')

    def state(self):
        value = read_json(self.path)
        if value is None:
            return None
        if value.get('schema') != 1 or value.get('uid') != os.getuid() \
                or not re.fullmatch(r':(?:[2-9][0-9])', value.get('display', '')):
            raise ValueError('native state identity/display mismatch')
        validate_request('start', value.get('token'))
        if not isinstance(value.get('processes'), list) or len(value['processes']) > 4:
            raise ValueError('native state process identities invalid')
        records = value['processes']
        if records:
            leader = records[0]
            expected = [str(self.prefix / 'bin/python3'), str(self.root / 'runtime.py'),
                        '_supervise', value['token'], value['display']]
            if leader.get('command') != expected or leader.get('pid') != leader.get('pgid'):
                raise ValueError('native owner command identity mismatch')
            for record in records:
                if any(type(record.get(k)) is not int or record[k] < 2 for k in ('pid', 'pgid')) \
                        or record.get('uid') != os.getuid() or record.get('pgid') != leader['pid'] \
                        or not re.fullmatch('[0-9]{1,32}', record.get('starttime', '')) \
                        or not isinstance(record.get('command'), list) or not record['command']:
                    raise ValueError('native process owner identity mismatch')
        return value

    def readiness(self, display):
        env = dict(self.env, DISPLAY=display)
        try:
            out = run_bounded([str(self.prefix / 'bin/xprop'), '-display', display, '-root',
                               '_NET_SUPPORTING_WM_CHECK'], env=env, timeout=2, max_bytes=4096)
            match = re.search(r'window id # (0x[0-9a-fA-F]+)', out)
            return True, bool(match and int(match[1], 16) != 0)
        except (OSError, ValueError):
            return False, False

    def alive(self, state):
        for record in state['processes']:
            current = identity(record.get('pid', 0))
            if current is not None and not same_process(record, current):
                raise ValueError('native PID identity changed; refusing ownership')
        return any(same_process(p, identity(p.get('pid', 0))) for p in state['processes'])

    def evidence(self, state):
        evidence = {'token': state['token'], 'processes': state['processes'], 'tag': TAG,
                    'ownership': state.get('ownership', {}),
                    'runtime': 'native Termux Bionic/i3/X11; no PRoot',
                    'pythonVersion': sys.version.split()[0],
                    'graphics': 'software profile; host GPU and displayed pixels require separate probes'}
        try:
            output = run_bounded([str(self.prefix / 'bin/dpkg-query'), '-W', '-f=${Package}=${Version}\n',
                                  'python', 'termux-x11-nightly', 'i3', 'dbus'],
                                 env=self.env, timeout=2, max_bytes=4096)
            evidence['packages'] = dict(line.split('=', 1) for line in output.splitlines()
                                        if re.fullmatch('[a-z0-9+.-]+=[^\r\n=]{1,128}', line))
        except (OSError, ValueError) as error:
            evidence['packageProbeError'] = str(error)[:256]
        for package in ('xfce4-terminal', 'aterm'):
            if not (self.prefix / 'bin' / package).is_file():
                continue
            try:
                output = run_bounded([str(self.prefix / 'bin/dpkg-query'), '-W', '-f=${Package}=${Version}\n',
                                      package], env=self.env, timeout=2, max_bytes=4096)
                name, version = output.strip().split('=', 1)
                if name == package and re.fullmatch('[^\r\n=]{1,128}', version):
                    evidence.setdefault('packages', {})[name] = version
            except (OSError, ValueError):
                pass  # Missing optional provider must not discard installed core versions.
        return evidence

    def terminal_shell_ready(self, pid, proc=Path('/proc')):
        """Default terminal readiness; no ptrace-gated cross-process fd reads."""
        try:
            parent = identity(pid, proc, strict=True)
            if parent is None or parent['uid'] != os.getuid():
                return False
            until = time.monotonic() + 1
            for index, directory in enumerate(Path(proc).iterdir()):
                if index >= 4096 or time.monotonic() >= until:
                    return False
                if not directory.name.isdigit():
                    continue
                child = identity(int(directory.name), proc)
                if child is None or child['uid'] != os.getuid() or child['ppid'] != pid \
                        or child['command'] != [str(self.prefix / 'bin/bash'), '-l'] or not child['tty_nr']:
                    continue
                current = identity(child['pid'], proc, strict=True)
                return bool(same_identity(child, current) and current.get('tty_nr')
                            and current.get('ppid') == pid
                            and same_identity(parent, identity(pid, proc, strict=True)))
        except (OSError, ValueError, TypeError):
            pass
        return False

    def window_evidence(self, display, proc=Path('/proc')):
        try:
            tree = json.loads(run_bounded([str(self.prefix / 'bin/i3-msg'), '-t', 'get_tree'],
                                         env=dict(self.env, DISPLAY=display), timeout=2, max_bytes=65536))
            pending, count, visited = [(tree, '')], 0, 0
            evidence = {'windowCount': 0, 'activeTerminalShellReady': False}
            while pending:
                node, workspace = pending.pop()
                visited += 1
                if visited > 512 or not isinstance(node, dict):
                    raise ValueError('native window tree exceeds bound')
                if node.get('type') == 'workspace':
                    workspace = str(node.get('name', ''))[:64]
                window = node.get('window')
                if workspace and type(window) is int and window > 0:
                    count += 1
                    if node.get('focused') is True:
                        evidence.update(activeWindowId=window, workspace=workspace)
                        if type(node.get('pid')) is int and node['pid'] > 0:
                            evidence['activeWindowPid'] = node['pid']
                for key in ('nodes', 'floating_nodes'):
                    children = node.get(key, [])
                    if not isinstance(children, list) or len(children) > 512:
                        raise ValueError('native window tree exceeds bound')
                    pending.extend((child, workspace) for child in children)
            evidence['windowCount'] = count
            if 'activeWindowId' in evidence and 'activeWindowPid' not in evidence:
                prop = run_bounded([str(self.prefix / 'bin/xprop'), '-display', display,
                                    '-id', str(evidence['activeWindowId']), '_NET_WM_PID'],
                                   env=dict(self.env, DISPLAY=display), timeout=2, max_bytes=4096)
                match = re.search(r'_NET_WM_PID\(CARDINAL\) = ([0-9]+)', prop)
                if match and int(match[1]) > 0:
                    evidence['activeWindowPid'] = int(match[1])
            if 'activeWindowPid' in evidence:
                evidence['activeTerminalShellReady'] = self.terminal_shell_ready(evidence['activeWindowPid'], proc)
            return evidence
        except (OSError, ValueError, TypeError) as error:
            return {'windowProbeError': str(error)[:256], 'activeTerminalShellReady': False}

    def doctor(self, request):
        state = self.state()
        if state is None:
            return result('doctor', request, 'stopped', state['display'] if state else '',
                          reason='owned session not running', xReady=False, wmReady=False)
        if not self.alive(state):
            confirmed = state.get('phase') == 'stopped' and state.get('terminationConfirmed') is True
            return result('doctor', request, 'stopped' if confirmed else 'failed', state['display'],
                          reason='owned session stopped' if confirmed else 'native owner lost; cleanup not confirmed',
                          xReady=False, wmReady=False)
        x, wm = self.readiness(state['display'])
        complete = state.get('phase') == 'ready' and len(state['processes']) == 3 \
            and all(same_process(p, identity(p['pid'])) for p in state['processes'])
        ready = x and wm and complete
        evidence = self.evidence(state)
        if ready:
            evidence.update(self.window_evidence(state['display']))
        return result('doctor', request, 'ready' if ready else 'failed', state['display'],
                      xReady=x, wmReady=wm and complete, evidence=evidence,
                      reason='native display and WM verified' if ready else 'native display/WM not ready')

    def start(self, request):
        state = self.state()
        if state is not None and self.alive(state):
            response = self.doctor(request)
            response['action'] = 'start'
            return response
        if state is not None and (state.get('phase') != 'stopped' or state.get('terminationConfirmed') is not True):
            raise ValueError('native owner lost; cleanup not confirmed; owner marker retained')
        required = ('python3', 'termux-x11', 'i3', 'xprop', 'dbus-run-session', 'xfce4-terminal')
        if any(not (self.prefix / 'bin' / n).is_file() for n in required) \
                or not (self.root / 'runtime.py').is_file() or not (self.root / 'i3.config').is_file():
            return result('start', request, 'failed', reason='native setup/packages required')
        run_bounded([str(self.prefix / 'bin/i3'), '-C', '-c', str(self.root / 'i3.config')], env=self.env)
        display = self.choose_display()
        state = {'schema': 1, 'uid': os.getuid(), 'token': request, 'display': display,
                 'phase': 'starting', 'processes': []}
        atomic_json(self.path, state)
        argv = [str(self.prefix / 'bin/python3'), str(self.root / 'runtime.py'), '_supervise', request, display]
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, env=self.env, start_new_session=True)
        record = identity(child.pid)
        if not record:
            child.terminate(); child.wait(timeout=3)
            self.path.unlink()
            return result('start', request, 'failed', display, reason='cannot establish native PID identity')
        state['processes'] = [record]
        atomic_json(self.path, state)
        until = time.monotonic() + 35
        while time.monotonic() < until:
            state = self.state()
            if state['phase'] == 'ready':
                response = self.doctor(request)
                response['action'] = 'start'
                return response
            if state['phase'] in ('failed', 'stopped') or child.poll() is not None:
                self.stop(request)
                return result('start', request, 'failed', display,
                              reason=state.get('reason', 'native supervisor exited'))
            time.sleep(.1)
        self.stop(request)
        return result('start', request, 'failed', display, reason='native startup timeout')

    def choose_display(self):
        tmp = self.prefix / 'tmp'
        until = time.monotonic() + 6
        for number in range(20, 100):
            if time.monotonic() >= until:
                raise ValueError('native display scan timeout')
            if (tmp / f'.X{number}-lock').exists() or (tmp / f'.X11-unix/X{number}').exists():
                continue
            if not self.readiness(f':{number}')[0]:
                return f':{number}'
        raise ValueError('no unclaimed native X display available')

    def stop(self, request):
        state = self.state()
        if state is None:
            return result('stop', request, 'stopped', reason='owned session not running')
        if not state['processes']:
            raise ValueError('native ownership anchor unavailable; cleanup not confirmed')
        owner = state['processes'][0]
        current = identity(owner['pid'], strict=True)
        if current is not None:
            if not same_process(owner, current):
                raise ValueError('native owner identity changed; refusing signal')
            signal_process(owner, signal.SIGTERM)
        elif state.get('phase') != 'stopped' or state.get('terminationConfirmed') is not True:
            raise ValueError('native ownership anchor lost; cleanup not confirmed')
        until = time.monotonic() + 8
        while time.monotonic() < until:
            latest = self.state()
            if latest is None or latest['token'] != state['token']:
                raise ValueError('native cleanup owner marker changed')
            if latest.get('phase') == 'stopped' and latest.get('terminationConfirmed') is True \
                    and identity(owner['pid'], strict=True) is None:
                break
            time.sleep(.05)
        else:
            raise ValueError('native descendant termination not confirmed; owner marker retained')
        self.path.unlink(missing_ok=True)
        return result('stop', request, 'stopped', state['display'],
                      evidence={'terminationConfirmed': True, 'token': state['token']})

    def run(self, action, request):
        validate_request(action, request)
        descriptor = os.open(self.root / 'control.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as lock:
            until = time.monotonic() + 5
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= until:
                        raise ValueError('native control command busy')
                    time.sleep(.05)
            if action in ('start', 'stop', 'doctor'):
                return getattr(self, action)(request)
            command = self.prefix / 'bin/termux-x11-preference'
            function = preferences.apply if action == 'input' else preferences.restore
            evidence = function(command, self.root, self.env)
            state = self.state()
            return result(action, request, 'applied' if action == 'input' else 'restored',
                          state['display'] if state else '', evidence=evidence)


def supervise(runtime, token, display):
    children, stopping = [], threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    state = None
    owned = None
    authorized = False
    try:
        until = time.monotonic() + 3
        while time.monotonic() < until:
            state = runtime.state()
            if state and state['token'] == token and any(p['pid'] == os.getpid() for p in state['processes']):
                break
            time.sleep(.02)
        if not state or state['token'] != token or state['display'] != display \
                or os.getpgrp() != os.getpid() or not any(p['pid'] == os.getpid() for p in state['processes']):
            return
        authorized = True
        enable_subreaper()  # Before the first fork; inherited descendants stay owned.
        owned = OwnedProcesses()
        env = dict(runtime.env, DISPLAY=display)
        commands = [[str(runtime.prefix / 'bin/termux-x11'), display, '-tag', TAG, '-noreset'],
                    [str(runtime.prefix / 'bin/dbus-run-session'), '--', str(runtime.prefix / 'bin/i3'),
                     '-c', str(runtime.root / 'i3.config')]]
        for index, argv in enumerate(commands):
            child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, env=env)
            children.append(child)
            owned.register(child.pid)
            until = time.monotonic() + 12
            while time.monotonic() < until and not stopping.is_set():
                if any(c.poll() is not None for c in children):
                    raise ValueError(f'native {"X server" if index == 0 else "WM"} exited')
                x, wm = runtime.readiness(display)
                records = [identity(os.getpid()), *(identity(c.pid) for c in children)]
                state['processes'] = [p for p in records if p is not None]
                owned.refresh()
                state['ownership'] = {'subreaper': True, 'kernelChildLists': owned.child_lists_available,
                                      'terminationCheck': 'waitpid-echild-all'}
                atomic_json(runtime.path, state)
                if x and (index == 0 or wm):
                    break
                time.sleep(.1)
            else:
                raise ValueError('native display/WM startup timeout')
        state['phase'] = 'ready'
        atomic_json(runtime.path, state)
        while not stopping.wait(.25):
            owned.refresh()
            if any(c.poll() is not None for c in children):
                raise ValueError('native X server or WM exited')
    except Exception as error:
        if state:
            state.update(phase='failed', reason=str(error)[:1024])
            atomic_json(runtime.path, state)
    finally:
        if authorized and owned is None:
            state.update(phase='stopped', terminationConfirmed=True)
            atomic_json(runtime.path, state)  # Capability failure happened before any child fork.
        elif authorized and owned:
            while True:
                stopping.clear()  # Keep any retry arriving during cleanup/publication queued.
                try:
                    owned.terminate()
                    state.update(phase='stopped', terminationConfirmed=True, processes=[owned.owner])
                    atomic_json(runtime.path, state)
                    break
                except Exception as error:
                    state.update(phase='failed', terminationConfirmed=False, reason=str(error)[:1024],
                                 processes=[owned.owner])
                    atomic_json(runtime.path, state)
                    # Keep the anchor for an explicit retry; never abandon unknown descendants.
                    stopping.wait()


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ''
    request = sys.argv[2] if len(sys.argv) > 2 else ''
    try:
        prefix, home = Path('/data/data/com.termux/files/usr'), Path('/data/data/com.termux/files/home')
        runtime = Runtime(home, prefix)
        if action == '_supervise' and len(sys.argv) == 4:
            validate_request('start', request)
            supervise(runtime, request, sys.argv[3])
            return
        if len(sys.argv) != 3:
            raise ValueError('fixed native action/request argv required')
        response = runtime.run(action, request)
    except Exception as error:
        response = result(action[:16], request[:36], 'failed', reason=str(error))
    print(encode_result(response), flush=True)


if __name__ == '__main__':
    main()
