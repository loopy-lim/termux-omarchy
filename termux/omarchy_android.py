"""Owned Unix-only bridge for fixed Android settings intents; no extra grants."""
from collections import deque
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

from processes import atomic_json, identity, read_json, run_bounded, same_identity
from omarchy_resources import StartupLog, live_peer
from omarchy_android_client import ACTIONS, call, decode, encode, identifier, private_file, receive


class AndroidFailure(ValueError):
    pass


def browser_profile_available(profile, records, identify=identity):
    """Let Chromium recover its own stale lock only after proving no live owner."""
    lock = profile / 'SingletonLock'
    if not os.path.lexists(lock):
        return True
    info = lock.lstat()
    if not stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
        return False
    match = re.fullmatch(re.escape(socket.gethostname()) + r'-(\d+)', os.readlink(lock))
    if not match or identify(int(match[1])) is not None:
        return False
    flag = '--user-data-dir=' + str(profile)
    if any(flag in row.get('command', []) for row in records.values()):
        return False
    return lock.lstat() == info


class Nonces:
    """Reject replay in a bounded recent window without exhausting the service."""
    def __init__(self):
        self.values, self.seen = deque(), set()

    def accept(self, nonce):
        if nonce in self.seen:
            raise AndroidFailure('android-request-repeated')
        if len(self.values) == 4096:
            self.seen.remove(self.values.popleft())
        self.values.append(nonce)
        self.seen.add(nonce)


def service_arguments(args):
    if len(args) != 5 or args[0] != '_serve' or not re.fullmatch(r':[2-9][0-9]', args[2]) \
            or not re.fullmatch(r'[0-9]{1,10}', args[3]) or int(args[3]) < 2 \
            or not re.fullmatch(r'[0-9]{1,32}', args[4]):
        raise AndroidFailure('android-service-arguments')
    return identifier(args[1]), args[2], int(args[3]), args[4]


def handle(request, prefix, env, runner=run_bounded):
    if not isinstance(request, dict) or set(request) != {'schema', 'token', 'nonce', 'action'} \
            or type(request.get('schema')) is not int or request['schema'] != 1 \
            or not isinstance(request.get('action'), str) or request['action'] not in ACTIONS - {'browser'}:
        raise AndroidFailure('android-request-invalid')
    identifier(request['token']); identifier(request['nonce'])
    if request['action'] == 'ping':
        return dict(request, status='ready', reason='android-service-ready')
    arguments = {'wifi': ['-a', 'android.settings.panel.action.WIFI'],
                 'bluetooth': ['-a', 'android.settings.BLUETOOTH_SETTINGS'],
                 'desktop': ['-n', 'com.termux.x11/com.termux.x11.MainActivity']}[request['action']]
    try:
        output = runner([str(Path(prefix) / 'bin/am'), 'start', *arguments],
                        env=env, timeout=8, max_bytes=4096)
        # TermuxAm acknowledges an intent without waiting for a visible activity.
        accepted = any(line.startswith('Starting: Intent {') for line in output.splitlines()) \
            and not any(line.startswith(('Error:', 'Exception:', 'SecurityException:'))
                        for line in output.splitlines())
    except (OSError, ValueError):
        accepted = False
    return dict(request, status='accepted' if accepted else 'unavailable',
                reason='android-launch-requested' if accepted else 'android-launch-unavailable')


def prepare(runtime, value):
    info = runtime.short.lstat()
    marker = {key: value[key] for key in ('schema', 'token', 'uid', 'root', 'runtime')}
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 \
            or [info.st_dev, info.st_ino, info.st_uid] != value['runtime'] \
            or info.st_uid != os.getuid() or read_json(runtime.short / 'owner.json') != marker:
        raise AndroidFailure('android-owner-invalid')
    path = runtime.short / 'android'
    if os.path.lexists(path):
        raise AndroidFailure('android-directory-existing')
    path.mkdir(mode=0o700)
    fd = os.open(path / 'cookie', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(os.urandom(32))
    owner = value['processes'][0]
    atomic_json(path / 'lease.json', dict(marker, owner=owner, serverPid=0))


def command(runtime, value):
    owner = value['processes'][0]
    return [str(runtime.prefix / 'bin/python3'), str(runtime.root / 'omarchy_android.py'),
            '_serve', value['token'], value['display'], str(owner['pid']), owner['starttime']]


def ready(runtime, value):
    record = value.get('androidProcess')
    if not isinstance(record, dict):
        return False
    if record.get('command') != command(runtime, value):
        raise AndroidFailure('android-process-command')
    if not live_peer(runtime.short / 'android/native', [record]):
        return False
    try:
        return call('ping', runtime.short / 'android')['status'] == 'ready'
    except (OSError, ValueError):
        return False


def start(runtime, value, owned, logs, stopping):
    prepare(runtime, value)
    args = command(runtime, value)
    log = StartupLog(runtime.root / 'sessions' / value['token'] / 'android.log')
    logs.append(log)
    child = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, env=runtime.env)
    owned.register(child.pid); log.attach(child.stdout)
    birth = None
    until = time.monotonic() + 5
    while time.monotonic() < until and not stopping.is_set():
        if child.poll() is not None:
            raise AndroidFailure('android-service-exited')
        owned.refresh()
        record = identity(child.pid, strict=True)
        if record is not None:
            current = {key: record[key] for key in ('pid', 'pgid', 'uid', 'starttime')}
            if record['pid'] != child.pid or record['uid'] != os.getuid() \
                    or record['ppid'] != os.getpid() or birth is not None and current != birth:
                raise AndroidFailure('android-process-identity')
            birth = current
            if record['command'] and record['command'] != args:
                raise AndroidFailure('android-process-command')
            if record['command'] == args:
                value['androidProcess'] = record
                if ready(runtime, value):
                    return child
        time.sleep(.05)
    raise AndroidFailure('android-startup-unconfirmed')


class NativeBrowser:
    """Fixed native executable/profile; descendants remain owned by the supervisor."""
    def __init__(self, prefix, token, owner):
        self.prefix, self.token, self.owner = Path(prefix), token, owner
        self.children, self.links = [], {}

    def open(self, fields):
        from omarchy_runtime import Runtime
        from omarchy_android_client import browser_fields
        fields = browser_fields(fields)
        runtime = Runtime('/data/data/com.termux/files/home', str(self.prefix))
        state = runtime.state()
        if not state or state.get('token') != self.token or state.get('phase') != 'ready' \
                or not same_identity(self.owner, identity(self.owner['pid'], strict=True)):
            raise AndroidFailure('browser-session-unavailable')
        target = runtime.rootfs / ('tmp/.X11-unix/X' + fields['display'][1:])
        info = target.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise AndroidFailure('browser-x-socket-invalid')
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(1); connection.connect(str(target))
            pid, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        record = identity(pid, strict=True)
        hypr = state.get('hyprland')
        if uid != os.getuid() or not record or not same_identity(hypr, record):
            raise AndroidFailure('browser-x-server-invalid')
        from processes import snapshot
        candidates = [p for p in snapshot().values() if p.get('ppid') == pid and p.get('command')
                      and p['command'][0] == '/opt/loopy-xwayland-kgsl/bin/Xwayland'
                      and fields['display'] in p['command'] and '-rootless' in p['command']]
        if len(candidates) != 1:
            raise AndroidFailure('browser-x-child-invalid')
        child = candidates[0]
        listeners = [child['command'][i + 1] for i, arg in enumerate(child['command'][:-1])
                     if arg == '-listenfd']
        if not listeners or not all(n.isdecimal() for n in listeners):
            raise AndroidFailure('browser-x-listeners-invalid')
        inherited = {os.readlink('/proc/%d/fd/%s' % (child['pid'], n)) for n in listeners}
        parent_sockets = set()
        for path in Path('/proc/%d/fd' % pid).iterdir():
            try: parent_sockets.add(os.readlink(path))
            except FileNotFoundError: pass
        if not inherited <= parent_sockets or not same_identity(child, identity(child['pid'], strict=True)):
            raise AndroidFailure('browser-x-listeners-changed')
        # Verify the current socket peer's ancestry, not a scan for any Xwayland PID.
        seen = set()
        while record['pid'] != self.owner['pid']:
            if record['pid'] in seen or len(seen) > 32 or record['uid'] != os.getuid():
                raise AndroidFailure('browser-x-owner-invalid')
            seen.add(record['pid']); record = identity(record['ppid'], strict=True)
            if record is None:
                raise AndroidFailure('browser-x-owner-invalid')
        if not same_identity(record, self.owner) or target.lstat() != info:
            raise AndroidFailure('browser-x-owner-changed')
        link = self.prefix / ('tmp/.X11-unix/X' + fields['display'][1:])
        if not os.path.lexists(link):
            link.symlink_to(target)
            self.links[link] = link.lstat()
        if not link.is_symlink() or os.readlink(link) != str(target):
            raise AndroidFailure('browser-x-link-collision')
        flags = (runtime.rootfs / 'home/omarchy/.config/chromium-flags.conf').read_text()
        scales = re.findall(r'^--force-device-scale-factor=(1\.25|2\.5)$', flags, re.M)
        if len(scales) != 1:
            raise AndroidFailure('browser-density-unavailable')
        profile = runtime.home / '.config/loopy-native-chromium'
        if profile.is_symlink():
            raise AndroidFailure('browser-profile-invalid')
        profile.mkdir(mode=0o700, parents=True, exist_ok=True)
        if profile.stat().st_uid != os.getuid():
            raise AndroidFailure('browser-profile-invalid')
        self.children = [child for child in self.children if child.poll() is None]
        if len(self.children) >= 8 or not self.children and not browser_profile_available(profile, snapshot()):
            raise AndroidFailure('browser-profile-already-owned')
        futex = runtime.root / 'graphics-native-futex/libxshmfence.so'
        import hashlib
        if futex.is_symlink() or hashlib.sha256(futex.read_bytes()).hexdigest() != 'ffd9e69982a4937fe6ce3c23379fb6fd3980660c2b63cfee2b57cc2d34f4e87c':
            raise AndroidFailure('browser-fence-integrity')
        env = dict(runtime.env, DISPLAY=fields['display'], XDG_RUNTIME_DIR=str(runtime.short),
                   PULSE_SERVER='unix:' + str(runtime.short / 'pulse/native'),
                   PULSE_COOKIE=str(runtime.short / 'pulse/cookie'),
                   VK_ICD_FILENAMES=str(self.prefix / 'share/vulkan/icd.d/freedreno_icd.aarch64.json'),
                   LD_LIBRARY_PATH=str(futex.parent) + ':' + str(self.prefix / 'lib'), FD_KGSL_ENABLE_DMABUF='1',
                   MESA_LOADER_DRIVER_OVERRIDE='kgsl', MESA_VK_WSI_PRESENT_MODE='mailbox')
        for name in ('LD_PRELOAD', 'XAUTHORITY', 'WAYLAND_DISPLAY'):
            env.pop(name, None)
        extension = runtime.rootfs / 'home/omarchy/.local/share/loopy-browser-performance'
        import hashlib
        expected = {'manifest.json': '4504d5e61c021b51fedc0361e9002f92246e114c4433e266cb850ab7c1ca0e84', 'prefer-h264.js': 'ffc68658e9dc5d2fa5ee526ca8ee00f484515f1055905e4eb31d9f1d48025684'}
        for name, digest in expected.items():
            path = extension / name
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise AndroidFailure('browser-extension-integrity')
        args = [str(self.prefix / 'lib/chromium/chrome'), '--user-data-dir=' + str(profile),
                '--class=LoopyNativeBrowser', '--no-sandbox', '--disable-gpu-sandbox',
                '--disable-dev-shm-usage', '--password-store=basic', '--ozone-platform=x11', '--use-gl=angle',
                '--use-angle=vulkan', '--enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan',
                '--force-device-scale-factor=' + scales[0], '--disable-gpu-memory-buffer-video-frames',
                '--ignore-gpu-blocklist', '--no-first-run', '--load-extension=' + str(extension)]
        from urllib.parse import urlsplit
        url = urlsplit(fields['url'])
        if url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port == 8765:
            args.append('--app=' + fields['url'])
        else:
            args.extend(['--new-window', fields['url']])
        with open(runtime.root / 'sessions' / self.token / 'native-browser.log', 'ab') as log:
            child = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env)
        self.children.append(child)
        time.sleep(.15)
        if child.poll() not in (None, 0):
            raise AndroidFailure('browser-launch-failed')

    def cleanup_links(self):
        # The supervisor terminates/reaps the process subtree. Only our symlinks are removed.
        for path, before in self.links.items():
            try:
                after = path.lstat()
                if (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino):
                    path.unlink()
            except FileNotFoundError:
                pass


class VideoDirect:
    """Fullscreen playback on the host X server; the nested re-composite is frozen.

    Bypassing the nested chain measured termux-x11 13.2%->1.8%. A lease file makes the
    SHM output consume without attaching (aquamarine-video-freeze), so the parent
    compositor idles while the fullscreen client covers the desktop. Process-level
    suspension was attempted and reaped by the session watchdog, so the presentation
    pauses at the damage source instead: the desktop keeps running and repaints on
    the first input after the lease is gone.
    """

    LEASE = 'video-direct.lease'

    def __init__(self, prefix, token, owner, short):
        self.prefix, self.token, self.owner = Path(prefix), token, owner
        self.short = Path(short)
        self.process = None

    def lease_path(self):
        return self.short / self.LEASE

    def lease_active(self):
        return self.lease_path().exists()

    def freeze(self):
        path = self.lease_path()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            if self.running():
                raise AndroidFailure('video-busy') from None
            try:
                path.unlink()  # A lease without a live playback owner cannot be ours.
            except FileNotFoundError:
                pass
            fd = os.open(path, flags, 0o600)
        os.close(fd)

    def thaw(self):
        try:
            self.lease_path().unlink()
        except FileNotFoundError:
            pass

    def profile_owner(self):
        best = None
        for pid in os.listdir('/proc'):
            if not pid.isdigit():
                continue
            try:
                cmd = open(f'/proc/{pid}/cmdline', 'rb').read().decode(errors='replace')
            except OSError:
                continue
            if 'loopy-video-chromium' in cmd and int(pid) != os.getpid():
                pid = int(pid)
                if best is None or pid < best:
                    best = pid
        return best

    def running(self):
        if self.process is not None and self.process.poll() is None:
            return True
        return self.profile_owner() is not None

    def open(self, url):
        from omarchy_runtime import Runtime
        if self.running():
            raise AndroidFailure('video-busy')
        runtime = Runtime('/data/data/com.termux/files/home', str(self.prefix))
        state = runtime.state()
        if not state or state.get('token') != self.token or state.get('phase') != 'ready' \
                or not same_identity(self.owner, identity(self.owner['pid'], strict=True)):
            raise AndroidFailure('video-session-unavailable')
        extension = runtime.rootfs / 'home/omarchy/.local/share/loopy-browser-performance'
        import hashlib
        expected = {'manifest.json': '4504d5e61c021b51fedc0361e9002f92246e114c4433e266cb850ab7c1ca0e84', 'prefer-h264.js': 'ffc68658e9dc5d2fa5ee526ca8ee00f484515f1055905e4eb31d9f1d48025684'}
        for name, digest in expected.items():
            path = extension / name
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise AndroidFailure('browser-extension-integrity')
        futex = runtime.root / 'graphics-native-futex/libxshmfence.so'
        if futex.is_symlink() or hashlib.sha256(futex.read_bytes()).hexdigest() != 'ffd9e69982a4937fe6ce3c23379fb6fd3980660c2b63cfee2b57cc2d34f4e87c':
            raise AndroidFailure('browser-fence-integrity')
        env = dict(runtime.env, DISPLAY=':20', XDG_RUNTIME_DIR=str(runtime.short),
                   PULSE_SERVER='unix:' + str(runtime.short / 'pulse/native'),
                   PULSE_COOKIE=str(runtime.short / 'pulse/cookie'),
                   VK_ICD_FILENAMES=str(self.prefix / 'share/vulkan/icd.d/freedreno_icd.aarch64.json'),
                   LD_LIBRARY_PATH=str(futex.parent) + ':' + str(self.prefix / 'lib'), FD_KGSL_ENABLE_DMABUF='1',
                   MESA_LOADER_DRIVER_OVERRIDE='kgsl', MESA_VK_WSI_PRESENT_MODE='mailbox')
        for name in ('LD_PRELOAD', 'XAUTHORITY', 'WAYLAND_DISPLAY'):
            env.pop(name, None)
        args = [str(self.prefix / 'lib/chromium/chrome'), '--user-data-dir=' + str(runtime.home / '.config/loopy-video-chromium'),
                '--no-sandbox', '--disable-gpu-sandbox', '--disable-dev-shm-usage', '--password-store=basic',
                '--ozone-platform=x11', '--use-gl=angle', '--use-angle=vulkan',
                '--enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan',
                '--force-device-scale-factor=2.5', '--disable-gpu-memory-buffer-video-frames',
                '--ignore-gpu-blocklist', '--no-first-run', '--start-fullscreen',
                '--window-position=0,0', '--window-size=3840,2560', '--load-extension=' + str(extension),
                url]
        self.freeze()
        with open(runtime.root / 'sessions' / self.token / 'video.log', 'ab') as log:
            self.process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env)
        time.sleep(.4)
        if self.process.poll() not in (None, 0):
            self.thaw()
            raise AndroidFailure('video-launch-failed')


def serve(token, display, owner_pid, birth):
    prefix = Path('/data/data/com.termux/files/usr')
    root = Path(__file__).resolve().parent
    short = Path('/data/data/com.termux/lr')
    path = short / 'android'
    lease = read_json(path / 'lease.json')
    marker = read_json(short / 'owner.json')
    owner = lease.get('owner') if isinstance(lease, dict) else None
    expected = [str(prefix / 'bin/python3'), str(root / 'omarchy_runtime.py'), '_supervise', token, display]
    def parent_alive():
        return same_identity(owner, identity(owner_pid, strict=True))
    if not owner or owner.get('command') != expected or owner.get('pid') != owner_pid \
            or owner.get('starttime') != birth or owner.get('uid') != os.getuid() \
            or os.getppid() != owner_pid or not parent_alive() \
            or not isinstance(marker, dict) or any(lease.get(k) != marker.get(k)
                        for k in ('schema', 'token', 'uid', 'root', 'runtime')) \
            or marker.get('token') != token or marker.get('uid') != os.getuid():
        raise AndroidFailure('android-owner-invalid')
    key = private_file(path, 'cookie', 32)
    if len(key) != 32 or stat.S_IMODE(path.lstat().st_mode) != 0o700:
        raise AndroidFailure('android-cookie-invalid')
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    used = Nonces()
    browser = NativeBrowser(prefix, token, owner)
    video = VideoDirect(prefix, token, owner, short)
    video.thaw()  # Only a dead previous session can leave a lease; this one owns no playback.
    try:
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(path / 'native'))  # Never unlink/adopt an existing endpoint.
            server.listen(4); server.settimeout(.25)
            lease['serverPid'] = os.getpid()
            atomic_json(path / 'lease.json', lease)
            while not stopping.is_set() and parent_alive():
                if read_json(short / 'owner.json') != marker:
                    raise AndroidFailure('android-session-changed')
                if video.lease_active() and not video.running():
                    video.thaw()  # The playback client is gone; unfreeze even without a close call.
                try:
                    connection, _ = server.accept()
                except socket.timeout:
                    continue
                with connection:
                    connection.settimeout(10)
                    try:
                        _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                        if uid != os.getuid():
                            raise AndroidFailure('android-client-uid')
                        request = decode(receive(connection, timeout=3), key, token)
                        used.accept(request['nonce'])
                        if not parent_alive() or read_json(short / 'owner.json') != marker:
                            raise AndroidFailure('android-owner-changed')
                        if request.get('action') == 'browser':
                            if set(request) != {'schema', 'token', 'nonce', 'action', 'url', 'display'}:
                                raise AndroidFailure('browser-request-invalid')
                            try:
                                browser.open({k: request[k] for k in ('url', 'display')})
                                reply = dict(request, status='accepted', reason='android-launch-requested')
                            except (OSError, ValueError):
                                reply = dict(request, status='unavailable', reason='android-launch-unavailable')
                        elif request.get('action') == 'video':
                            if set(request) != {'schema', 'token', 'nonce', 'action', 'url'}:
                                raise AndroidFailure('video-request-invalid')
                            try:
                                video.open(request['url'])
                                reply = dict(request, status='accepted', reason='android-video-requested')
                            except (OSError, ValueError):
                                reply = dict(request, status='unavailable', reason='android-launch-unavailable')
                        else:
                            reply = handle(request, prefix, os.environ.copy())
                        connection.sendall(encode(reply, key))
                    except (OSError, ValueError, KeyError):
                        pass  # Malformed input/closed readiness probe cannot stop Linux.
    finally:
        video.thaw()
        browser.cleanup_links()
    # Supervisor's inode ledger retires the endpoint only after ECHILD proof.


if __name__ == '__main__':
    try:
        serve(*service_arguments(sys.argv[1:]))
    except (OSError, ValueError):
        print('android-service-unavailable', file=sys.stderr)
        sys.exit(1)
