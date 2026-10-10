#!/data/data/com.termux/files/usr/bin/python3
"""Isolated owned Omarchy/Hyprland; no upstream start/stop or global preferences."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import struct
import subprocess
import sys
import threading
import time
import uuid

from processes import (OwnedProcesses, atomic_json, enable_subreaper, identity,
                       private_directory, read_json, run_bounded, same_identity, signal_process)
from omarchy_resources import ResourceFailure, StartupLog, capture, cleanup, live_peer, x_family
from omarchy_boot import prepare_start
from omarchy_commands import commands as desktop_commands, environment as desktop_environment
from omarchy_proot import selection as proot_selection
from omarchy_audio import AudioFailure, command as audio_command, ready as audio_ready, start as start_audio
from omarchy_android import (AndroidFailure, command as android_command,
                             ready as android_ready, start as start_android)

CONTAINER = 'loopy-omarchy'
TAG = 'loopy-omarchy'
BUNDLE = '7e9f1cd67533bc0d3988b5cb3831aef52f1527dd90391d9d868ed9345021cdb2'
BACKEND = '8cfb78a4a1a146596228c34f55562c3325c10bc355a5dff5f5765ca77093ea0e'
HYPR = '/opt/omarchy-android/hyprland'
AQUA = '/opt/omarchy-android/aquamarine'
MESA = '/opt/omarchy-android/mesa'
SOCKET = 'wayland-omarchy'
ACTIONS = {'start', 'stop', 'status', 'doctor'}

class Failure(ValueError):
    pass  # Every call site supplies a fixed public code, never child output.

def stamp(path):
    value = Path(path).lstat()
    if not stat.S_ISDIR(value.st_mode) or value.st_uid != os.getuid():
        raise Failure('directory-ownership')
    return [value.st_dev, value.st_ino, value.st_uid]

def request_id(value):
    if not isinstance(value, str) or len(value) != 36 or str(uuid.UUID(value)) != value:
        raise Failure('request-invalid')
    return value

def regular(path, maximum=16 * 1024 * 1024):
    value = Path(path).lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_uid != os.getuid() \
            or value.st_nlink != 1 or value.st_size > maximum or value.st_mode & 0o022:
        raise Failure('file-ownership')
    return value


def response(action, request, phase, display='', **values):
    value = {'schema': 1, 'action': action, 'request': request, 'status': phase,
             'uid': os.getuid(), 'display': display, 'container': CONTAINER}
    value.update(values)
    return value

class Runtime:
    def __init__(self, home, prefix):
        self.home, self.prefix = Path(home).resolve(), Path(prefix).resolve()
        self.root = private_directory(self.home, '.local/share/loopy-omarchy')
        self.path = self.root / 'runtime-state.json'
        self.short = self.home.parents[1] / 'lr'
        self.host = self.root / 'weston-host'
        self.rootfs = self.prefix / 'var/lib/proot-distro/containers' / CONTAINER / 'rootfs'
        self.env = desktop_environment(self.home, self.prefix, self.host)

    def installed(self):
        value = read_json(self.root / 'install.json')
        if not value or value.get('schema') != 1 or value.get('phase') != 'INSTALLED' \
                or value.get('uid') != os.getuid() or value.get('root') != stamp(self.root) \
                or value.get('home') != str(self.home) or value.get('prefix') != str(self.prefix) \
                or value.get('container') != CONTAINER or value.get('bundle_sha256') != BUNDLE \
                or value.get('rootfs_identity') != stamp(self.rootfs) \
                or value.get('container_identity') != stamp(self.rootfs.parent):
            raise Failure('installation-identity')
        if stat.S_IMODE(self.root.lstat().st_mode) != 0o700:
            raise Failure('installation-mode')
        backend = self.root / 'weston/x11-backend.so'
        regular(backend)
        if value.get('managed_files', {}).get('weston/x11-backend.so') != BACKEND \
                or hashlib.sha256(backend.read_bytes()).hexdigest() != BACKEND:
            raise Failure('backend-integrity')
        for name in ('python3', 'termux-x11', 'xprop', 'xwininfo', 'proot-distro', 'pulseaudio', 'pactl'):
            if not (self.prefix / 'bin' / name).is_file():
                raise Failure('host-tool-missing')
        for name in ('bin/weston', 'lib/libweston-14.so', 'lib/libweston-14/gl-renderer.so',
                     'lib/weston/kiosk-shell.so'):
            path = self.host / name
            # SONAME links within this wholly managed private host are permitted.
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(self.host.resolve()) or not resolved.is_file():
                raise Failure('weston14-layout')
            regular(resolved)
        regular(self.root / 'omarchy_runtime.py', 131072)
        return value

    def state(self):
        value = read_json(self.path)
        if value is None:
            return None
        if value.get('schema') != 1 or value.get('uid') != os.getuid() \
                or value.get('root') != stamp(self.root) \
                or not re.fullmatch(r':[2-9][0-9]', value.get('display', '')):
            raise Failure('state-identity')
        token = request_id(value.get('token'))
        session = self.root / 'sessions' / token
        if value.get('session') != stamp(session):
            raise Failure('session-identity')
        records = value.get('processes')
        if not isinstance(records, list) or len(records) > 4:
            raise Failure('state-processes')
        if records:
            expected = [str(self.prefix / 'bin/python3'), str(self.root / 'omarchy_runtime.py'),
                        '_supervise', token, value['display']]
            leader = records[0]
            if leader.get('command') != expected or leader.get('pid') != leader.get('pgid'):
                raise Failure('state-owner-command')
            for record in records:
                if record.get('uid') != os.getuid() or any(type(record.get(k)) is not int
                        or record[k] < 2 for k in ('pid', 'pgid')) \
                        or not re.fullmatch('[0-9]{1,32}', record.get('starttime', '')):
                    raise Failure('state-process-identity')
        audio = value.get('audioProcess')
        if audio is not None and (not isinstance(audio, dict) or audio.get('uid') != os.getuid()
                or audio.get('command') != audio_command(self, value)[0]
                or any(type(audio.get(k)) is not int or audio[k] < 2 for k in ('pid', 'pgid'))
                or not re.fullmatch('[0-9]{1,32}', audio.get('starttime', ''))):
            raise Failure('state-audio-identity')
        android = value.get('androidProcess')
        if android is not None and (not isinstance(android, dict) or android.get('uid') != os.getuid()
                or not records or android.get('command') != android_command(self, value)
                or any(type(android.get(k)) is not int or android[k] < 2 for k in ('pid', 'pgid'))
                or not re.fullmatch('[0-9]{1,32}', android.get('starttime', ''))):
            raise Failure('state-android-identity')
        if value.get('runtimeGone') is not True:
            if value.get('runtime') != stamp(self.short):
                raise Failure('runtime-directory-identity')
            marker = read_json(self.short / 'owner.json')
            if marker != {'schema': 1, 'token': token, 'uid': os.getuid(),
                          'root': value['root'], 'runtime': value['runtime']}:
                raise Failure('runtime-marker')
        return value

    def publish(self, value):
        atomic_json(self.root / 'sessions' / value['token'] / 'state.json', value)
        atomic_json(self.path, value)

    def x_ready(self, display):
        try:
            run_bounded([str(self.prefix / 'bin/xprop'), '-display', display, '-root',
                         '_NET_SUPPORTING_WM_CHECK'], env=self.env, timeout=.5, max_bytes=4096)
            return True
        except (OSError, ValueError):
            return False

    def choose_display(self):
        for number in range(20, 100):
            display = f':{number}'
            paths = (self.prefix / f'tmp/.X{number}-lock', self.prefix / f'tmp/.X11-unix/X{number}')
            if any(os.path.lexists(p) for p in paths) or self.x_ready(display):
                continue
            return display
        raise Failure('display-unavailable')

    def commands(self, value):
        return desktop_commands(self, value)

    def screen(self, display):
        out = run_bounded([str(self.prefix / 'bin/xwininfo'), '-display', display, '-root'],
                          env=self.env, timeout=2, max_bytes=4096)
        fields = [re.findall(rf'^\s*{key}:\s*([0-9]+)\s*$', out, re.MULTILINE) for key in ('Width', 'Height')]
        if any(len(f) != 1 or not 320 <= int(f[0]) <= 8192 for f in fields):
            raise Failure('x11-geometry-invalid')
        return int(fields[0][0]), int(fields[1][0])

    def hypr_ready(self, records):
        directory = self.short / 'hypr'
        if not directory.exists():
            return None
        stamp(directory)
        candidates = list(directory.iterdir())
        if len(candidates) != 1 or not re.fullmatch(r'[a-f0-9]{7,64}_[0-9]{1,20}_[0-9]{1,20}',
                                                   candidates[0].name):
            raise Failure('hyprland-instance-ambiguous')
        stamp(candidates[0])
        path = candidates[0] / '.socket.sock'
        if len(os.fsencode(path)) >= 108:
            raise Failure('hyprland-socket-path-too-long')
        if not path.exists():
            return None
        before = path.lstat()
        if not stat.S_ISSOCK(before.st_mode) or before.st_uid != os.getuid():
            raise Failure('hyprland-socket-ownership')
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(.5)
            client.connect(str(path))
            pid, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            record = next((r for r in records if r['pid'] == pid), None)
            if uid != os.getuid() or record is None or not same_identity(record, identity(pid, strict=True)):
                raise Failure('hyprland-peer-ownership')
            client.sendall(b'j/version')
            client.shutdown(socket.SHUT_WR)
            data = bytearray()
            while True:
                part = client.recv(min(4096, 8193 - len(data)))
                if not part:
                    break
                data.extend(part)
                if len(data) > 8192:
                    raise Failure('hyprland-ipc-bounds')
        after = path.lstat()
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino) \
                or not same_identity(record, identity(pid, strict=True)):
            raise Failure('hyprland-peer-changed')
        version = json.loads(data)
        if not isinstance(version, dict) or not re.fullmatch('[a-f0-9]{40}', version.get('commit', '')):
            raise Failure('hyprland-version-invalid')
        return record

    def status(self, request):
        value = self.state()
        if value is None:
            return response('status', request, 'stopped', reason='no-owned-session')
        live = [same_identity(r, identity(r['pid'], strict=True)) for r in value['processes']]
        ready = value.get('phase') == 'ready' and len(live) == 4 and all(live) \
            and same_identity(value.get('hyprland'), identity(value.get('hyprland', {}).get('pid', 0), strict=True))
        if ready:
            ready = self.x_ready(value['display']) and live_peer(self.short / SOCKET, value['processes']) \
                and self.hypr_ready([value['hyprland']]) is not None
        audio = audio_ready(self, value) if ready else False
        phase = 'failed' if value.get('phase') == 'ready' and not ready else value.get('phase', 'failed')
        return response('status', request, 'ready' if ready else phase, value['display'],
                        token=value['token'], xReady=ready, hyprlandReady=ready,
                        terminationConfirmed=value.get('terminationConfirmed') is True,
                        reason=value.get('reason', 'owned-hyprland-running' if ready else 'not-ready'),
                        graphics='KGSL/Turnip profile; physical FPS and input latency not measured',
                        browser_linux_sandbox_disabled_in_bundle=True, browser_launch_requested=False,
                        width=value.get('width'), height=value.get('height'), requestedRefreshMhz=60000,
                        geometrySource='owned-x11-root', shellReady=False,
                        prootExitKillRequested=value.get('prootExitKillRequested') is True,
                        audioReady=audio, audioOutput='owned-aaudio-unix', audioMicrophoneEnabled=False,
                        androidSettingsReady=android_ready(self, value) if ready else False)

    def start(self, request):
        boot_id = prepare_start(self)
        previous = self.state()
        if previous and previous.get('processes') \
                and same_identity(previous['processes'][0], identity(previous['processes'][0]['pid'], strict=True)):
            return self.status(request)
        if previous and (previous.get('phase') != 'stopped' or previous.get('terminationConfirmed') is not True):
            raise Failure('previous-cleanup-unconfirmed')
        self.installed()
        guarded = proot_selection(self.root) is not None
        display = self.choose_display()
        reuse = os.path.lexists(self.short)
        if reuse and (not previous or previous.get('terminationConfirmed') is not True
                      or {p.name for p in self.short.iterdir()} != {'owner.json'}):
            raise Failure('runtime-directory-existing')
        sessions = private_directory(self.root, 'sessions')
        session = sessions / request
        session.mkdir(mode=0o700)
        if not reuse:
            self.short.mkdir(mode=0o700)  # Unknown existing runtime is never adopted/unlinked.
        value = {'schema': 1, 'uid': os.getuid(), 'root': stamp(self.root), 'token': request,
                 'session': stamp(session), 'runtime': stamp(self.short), 'display': display,
                 'phase': 'starting', 'processes': [], 'terminationConfirmed': False, 'bootId': boot_id,
                 'prootExitKillRequested': guarded}
        atomic_json(self.short / 'owner.json', {'schema': 1, 'token': request, 'uid': os.getuid(),
                                             'root': value['root'], 'runtime': value['runtime']})
        descriptor = os.open(session / 'pci-devices', os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        self.publish(value)
        argv = [str(self.prefix / 'bin/python3'), str(self.root / 'omarchy_runtime.py'), '_supervise', request, display]
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, env=self.env, start_new_session=True)
        record = identity(child.pid, strict=True)
        if record is None:
            raise Failure('supervisor-identity-unavailable')
        value['processes'] = [record]
        self.publish(value)
        until = time.monotonic() + 45
        while time.monotonic() < until:
            latest = self.state()
            if latest['token'] != request:
                raise Failure('startup-token-changed')
            if latest.get('phase') == 'ready':
                return self.status(request)
            if latest.get('phase') in ('failed', 'stopped') or child.poll() is not None:
                return response('start', request, 'failed', display, reason=latest.get('reason', 'supervisor-exited'))
            time.sleep(.1)
        self.stop(request)
        return response('start', request, 'failed', display, reason='startup-timeout')

    def stop(self, request):
        value = self.state()
        if value is None:
            return response('stop', request, 'stopped', reason='no-owned-session')
        if not value['processes']:
            raise Failure('supervisor-anchor-unavailable')
        owner = value['processes'][0]
        current = identity(owner['pid'], strict=True)
        if current is not None:
            if not same_identity(owner, current):
                raise Failure('supervisor-identity-changed')
            signal_process(owner, signal.SIGTERM)
        elif value.get('terminationConfirmed') is not True:
            raise Failure('supervisor-lost-cleanup-unconfirmed')
        until = time.monotonic() + 12
        while time.monotonic() < until:
            latest = self.state()
            if latest['token'] != value['token']:
                raise Failure('cleanup-token-changed')
            if latest.get('phase') == 'stopped' and latest.get('terminationConfirmed') is True \
                    and identity(owner['pid'], strict=True) is None:
                return response('stop', request, 'stopped', value['display'], terminationConfirmed=True,
                                token=value['token'], runtimeGone=latest.get('runtimeGone') is True)
            time.sleep(.05)
        raise Failure('cleanup-unconfirmed')

    def clear_runtime(self, value):
        if self.state()['token'] != value['token']:
            raise Failure('cleanup-token-changed')
        cleanup(self.short, self.prefix, value)  # Exact recorded inode only, after subreaper/ECHILD proof.

    def run(self, action, request):
        request_id(request)
        if action not in ACTIONS:
            raise Failure('action-invalid')
        descriptor = os.open(self.root / 'runtime-control.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as lock:
            if os.fstat(lock.fileno()).st_uid != os.getuid():
                raise Failure('control-lock-owner')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise Failure('control-busy') from error
            result = self.status(request) if action == 'doctor' else getattr(self, action)(request)
            result['action'] = action
            return result

def operation_evidence(stage, error):
    result = {'stage': stage, 'errorType': type(error).__name__[:64],
                                'errno': error.errno if isinstance(error, OSError) else None}
    known = {'native process identity cannot be verified': 'process-identity-unavailable',
             'native process identity changed; refusing signal': 'process-identity-changed',
             'native descendant termination not confirmed': 'termination-incomplete',
             'native ownership anchor changed': 'owner-changed',
             'native spawned child identity/lineage cannot be verified': 'spawned-lineage-unavailable',
             'native descendant identity changed': 'descendant-changed',
             'native child identity/lineage cannot be verified': 'child-lineage-unavailable',
             'native descendant count exceeds bound': 'descendant-bound'}
    if str(error) in known:
        result['processReason'] = known[str(error)]
    resource_codes = {'resource-type', 'resource-owner', 'resource-bounds',
                      'regular-resource-count', 'fifo-resource-count', 'resource-count',
                      'runtime-directory-changed', 'runtime-parent-changed',
                      'resource-replaced', 'runtime-parent-unrecorded',
                      'runtime-entry-unrecorded', 'boot-regular-changed', 'boot-fifo-changed'}
    if isinstance(error, ResourceFailure) and str(error) in resource_codes:
        result['resourceReason'] = str(error)
    changed = getattr(error, 'identity_changed_fields', ())
    if isinstance(changed, tuple) and changed and all(key in ('pid', 'pgid', 'uid', 'starttime', 'command') for key in changed):
        result['identityChangedFields'] = list(changed)
    cause = error.__cause__
    if cause is not None:
        result.update(causeType=type(cause).__name__[:64],
                                       causeErrno=cause.errno if isinstance(cause, OSError) else None)
    return result


def retire(runtime, value, owned, logs, children):
    """Keep the ownership anchor and report only the failing retirement boundary."""
    stage = 'capture-processes'
    try:
        if owned is not None:
            capture_error = None
            try:
                descendants = owned.refresh()
                if descendants:
                    stage = 'capture-runtime'
                    capture(runtime.short, runtime.prefix, value, x_family(descendants, children[0].pid),
                            runtime_records=descendants)
            except Exception as error:
                capture_error, capture_stage = error, stage
            stage = 'terminate'
            owned.terminate()
            if capture_error is not None:
                stage = capture_stage
                raise capture_error
        stage = 'logs'
        for log in logs:
            log.finish()
        stage = 'resources'
        runtime.clear_runtime(value)
        value.pop('cleanupEvidence', None)
    except Exception as error:
        value['cleanupEvidence'] = operation_evidence(stage, error)
        raise


def supervise(runtime, token, display):
    stopping, children, owned, authorized, value = threading.Event(), [], None, False, None
    logs = []
    audio_child = None
    android_child = None
    operation = "startup"
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    try:
        until = time.monotonic() + 3
        while time.monotonic() < until:
            value = runtime.state()
            if value and value['token'] == token and value['processes'] and value['processes'][0]['pid'] == os.getpid():
                break
            time.sleep(.02)
        if not value or value['token'] != token or value['display'] != display or not value['processes'] \
                or not same_identity(value['processes'][0], identity(os.getpid(), strict=True)):
            return
        authorized = True
        enable_subreaper()
        owned = OwnedProcesses()
        runtime.installed()
        for index in range(3):
            argv, env = runtime.commands(value)[index]
            if stopping.is_set():
                raise Failure('startup-stopped')
            path = runtime.root / 'sessions' / token / ('x11.log', 'weston.log', 'hyprland.log')[index]
            log = StartupLog(path)
            logs.append(log)
            child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, env=env)
            children.append(child)
            owned.register(child.pid)
            log.attach(child.stdout)
            until = time.monotonic() + 12
            while time.monotonic() < until and not stopping.is_set():
                if any(c.poll() is not None for c in children):
                    raise Failure(('x11-exited', 'weston-exited', 'hyprland-exited')[index])
                descendants = owned.refresh()
                capture(runtime.short, runtime.prefix, value, x_family(descendants, children[0].pid),
                        runtime_records=descendants)
                value['processes'] = [owned.owner, *(identity(c.pid, strict=True) for c in children)]
                if any(r is None for r in value['processes']):
                    raise Failure('child-identity-unavailable')
                value['ownership'] = {'subreaper': True, 'kernelChildLists': owned.child_lists_available,
                                      'terminationCheck': 'waitpid-echild-all'}
                runtime.publish(value)
                ready = runtime.x_ready(display) if index == 0 else live_peer(runtime.short / SOCKET, descendants)
                if index == 2:
                    try:
                        value['hyprland'] = runtime.hypr_ready(descendants)
                    except (FileNotFoundError, ConnectionRefusedError, socket.timeout):
                        value['hyprland'] = None
                    ready = value['hyprland'] is not None
                if ready:
                    if index == 0:
                        value['width'], value['height'] = runtime.screen(display)
                        audio_child = start_audio(runtime, value, owned, logs, stopping)
                        try:
                            android_child = start_android(runtime, value, owned, logs, stopping)
                        except AndroidFailure as error:
                            if str(error) not in ('android-service-exited', 'android-startup-unconfirmed'):
                                raise
                            value['androidStatus'] = 'unavailable'
                    break
                time.sleep(.1)
            else:
                raise Failure(('x11-timeout', 'weston-timeout', 'hyprland-timeout')[index])
        value['phase'] = 'ready'
        runtime.publish(value)
        while not stopping.wait(.25):
            operation = "refresh"
            descendants = owned.refresh()
            operation = "resources"
            capture(runtime.short, runtime.prefix, value, x_family(descendants, children[0].pid),
                    runtime_records=descendants)
            operation = "children"
            if any(c.poll() is not None for c in children):
                raise Failure('session-child-exited')
            operation = 'audio'
            if audio_child.poll() is not None and value.get('audioStatus') != 'unavailable':
                value['audioStatus'] = 'unavailable'
                runtime.publish(value)  # Output failure must preserve running Linux applications.
            operation = 'android'
            if android_child is not None and android_child.poll() is not None \
                    and value.get('androidStatus') != 'unavailable':
                value['androidStatus'] = 'unavailable'
                runtime.publish(value)
    except Exception as error:
        if authorized:
            value['operationEvidence'] = operation_evidence(operation, error)
            value.update(phase='failed', reason=str(error) if isinstance(error, (Failure, ResourceFailure, AudioFailure, AndroidFailure)) else 'runtime-operation-failed')
            runtime.publish(value)
    finally:
        if authorized:
            while True:
                stopping.clear()
                try:
                    retire(runtime, value, owned, logs, children)
                    value.update(phase='stopped', terminationConfirmed=True, runtimeGone=False,
                                 processes=[identity(os.getpid(), strict=True)], hyprland=None,
                                 audioProcess=None, androidProcess=None)
                    runtime.publish(value)
                    break
                except Exception as error:
                    value.update(phase='failed', terminationConfirmed=False,
                                 reason=str(error) if isinstance(error, (Failure, ResourceFailure)) else 'cleanup-operation-failed')
                    runtime.publish(value)
                    stopping.wait()  # Retain the anchor for an explicit exact-owner cleanup retry.


def main():
    action, request = (sys.argv + ['', ''])[1:3]
    try:
        runtime = Runtime('/data/data/com.termux/files/home', '/data/data/com.termux/files/usr')
        if action == '_supervise' and len(sys.argv) == 4:
            request_id(request)
            supervise(runtime, request, sys.argv[3])
            return
        if len(sys.argv) != 3:
            raise Failure('argument-count')
        value = runtime.run(action, request)
    except Exception as error:
        value = response(action[:16], request[:36], 'failed',
                         reason=str(error) if isinstance(error, (Failure, ResourceFailure, AudioFailure, AndroidFailure)) else 'runtime-operation-failed')
    data = json.dumps(value, ensure_ascii=True, separators=(',', ':'))
    if len(data.encode()) > 16384:
        raise Failure('response-bounds')
    print(data, flush=True)


if __name__ == '__main__':
    main()
