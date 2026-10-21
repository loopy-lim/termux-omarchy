"""Observe one selected browser inside Wayland; never write its profile or kill it."""
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import struct
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).parent))
import browser_state as state
from hyprland_actions import CompositorLifetime, Hyprland


def _read(path, limit, private=False):
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or private and (before.st_uid != os.getuid()
                or stat.S_IMODE(before.st_mode) != 0o600 or not 0 < before.st_size <= limit)):
            raise ValueError('Regular read-only metadata required')
        result = bytearray()
        while len(result) <= limit:
            data = os.read(fd, min(4096, limit + 1 - len(result)))
            if not data:
                break
            result.extend(data)
        if not 0 < len(result) <= limit:
            raise ValueError('Metadata exceeds its bound')
        after = os.fstat(fd)
        if private and any(getattr(before, name) != getattr(after, name) for name in
                ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_size', 'st_mtime_ns', 'st_ctime_ns')):
            raise ValueError('Owned readiness metadata changed')
        return bytes(result)
    finally:
        os.close(fd)


def _stat(pid):
    text = _read(Path('/proc') / str(pid) / 'stat', 4096).decode('utf-8', errors='replace')
    if not text.startswith(str(pid) + ' ('):
        raise ValueError('Process stat identity differs')
    end = text.rfind(') '); fields = text[end + 2:].split()
    if (end < 0 or len(fields) < 20 or len(fields[0]) != 1 or fields[0] not in 'RSDTtWIPZX'
            or not all(re.fullmatch('[0-9]{1,19}', fields[index]) for index in (1, 19))):
        raise ValueError('Process stat is incomplete')
    return dict(pid=pid, state=fields[0], ppid=int(fields[1]), birth=int(fields[19]))


def identity(pid):
    if type(pid) is not int or not 0 < pid < 2**31:
        return None
    try:
        first = _stat(pid)
        raw = _read(Path('/proc') / str(pid) / 'status', 16384).decode('utf-8', errors='replace')
        rows = [line.split()[1:] for line in raw.splitlines() if line.startswith('Uid:')]
        if (len(rows) != 1 or len(rows[0]) != 4 or len(set(rows[0])) != 1
                or not all(re.fullmatch('[0-9]{1,10}', value) for value in rows[0])):
            return None
        second = _stat(pid)
        if first['birth'] != second['birth']:
            return None
        second['uid'] = int(rows[0][0]); return second
    except (OSError, ValueError, UnicodeError):
        return None


def process_rows(leader, clients, uid):
    """Read only candidate PIDs and bounded ancestry, never enumerate all tasks."""
    result = {}
    for candidate in [leader] + [row['pid'] for row in clients]:
        current = candidate
        for _ in range(16):
            if current in result or len(result) >= 512:
                break
            row = identity(current)
            if row is None:
                break
            result[current] = row
            if row['uid'] != uid or current == leader:
                break
            current = row['ppid']
    return result


def worker_identity(pid, expected):
    """Admit the fixed action worker only within the same process lifetime."""
    keys = {'LOOPY_SESSION', 'HYPRLAND_INSTANCE_SIGNATURE', 'XDG_RUNTIME_DIR'}
    if (type(pid) is not int or not 0 < pid < 2**31 or type(expected) is not dict
            or set(expected) != keys or any(type(value) is not str or not value
                or '\0' in value or len(value) > 8192 for value in expected.values())):
        return None

    def owned(row):
        return (type(row) is dict and type(row.get('pid')) is int and row['pid'] == pid and type(row.get('uid')) is int
                and row['uid'] == os.getuid() and type(row.get('birth')) is int and row['birth'] > 0
                and type(row.get('ppid')) is int and 0 <= row['ppid'] < 2**31
                and type(row.get('state')) is str and row['state'] in 'RSDTtWIP' and len(row['state']) == 1)

    try:
        first = identity(pid)
        if not owned(first):
            return None
        path = Path('/proc') / str(pid)
        if _read(path / 'cmdline', 4096) != b'/usr/bin/python\0-B\0/usr/share/loopy/omarchy-bridge/session_actions.py\0':
            return None
        environment = _read(path / 'environ', 16384)
        if not environment.endswith(b'\0'):
            return None
        wanted = {key.encode('ascii'): value.encode('utf-8') for key, value in expected.items()}
        selected = {}
        for entry in environment[:-1].split(b'\0'):
            key, separator, value = entry.partition(b'=')
            if key in wanted:
                if not separator or key in selected:
                    return None
                selected[key] = value
        second = identity(pid)
        if (selected != wanted or not owned(second)
                or any(first[key] != second[key] for key in ('pid', 'uid', 'birth'))):
            return None
        return {key: second[key] for key in ('pid', 'uid', 'birth', 'ppid', 'state')}
    except (OSError, ValueError, UnicodeError):
        return None


class Compositor:
    def __init__(self):
        token = os.environ.get('LOOPY_SESSION', '')
        signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')
        runtime = os.environ.get('XDG_RUNTIME_DIR', '')
        if (not re.fullmatch('[A-Za-z0-9-]{1,64}', token)
                or not re.fullmatch('[A-Za-z0-9_-]{1,128}', signature)
                or not re.fullmatch('/run/loopy(?:/o[0-9a-f]{8})?', runtime)
                or not os.environ.get('WAYLAND_DISPLAY')):
            raise ValueError('Current owned Wayland session required')
        self.path = Path(runtime) / 'hypr' / signature / '.socket.sock'
        for parent in reversed(self.path.parents):
            if not stat.S_ISDIR(parent.lstat().st_mode):
                raise ValueError('Regular compositor path required')
        self.client = Hyprland(self.path, timeout=.25, reply_limit=65536)
        self.socket_identity = self._socket_identity()
        self.lifetime = CompositorLifetime(self.path)
        try:
            peer = self.lifetime.socket.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            pid, actual_uid, _ = struct.unpack('3i', peer)
            self.owner = identity(pid)
            if actual_uid != os.getuid() or self.owner is None or self.owner['uid'] != actual_uid:
                raise ValueError('Current compositor identity required')
            self.ready = Path('/run/loopy') / ('actions-' + token + '.ready.json')
            self.record = self._ready()
            if (self.record.get('token') != token or self.record.get('signature') != signature
                    or self.record.get('uid') != os.getuid()):
                raise ValueError('Current action worker required')
            self.worker_environment = {'LOOPY_SESSION': token, 'HYPRLAND_INSTANCE_SIGNATURE': signature,
                                       'XDG_RUNTIME_DIR': runtime}
            self.worker = worker_identity(self.record['pid'], self.worker_environment)
            if self.worker is None or self.worker['uid'] != os.getuid():
                raise ValueError('Live owned action worker required')
        except Exception:
            self.close(); raise

    def _socket_identity(self):
        info = self.path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Owned compositor socket required')
        return info.st_dev, info.st_ino, info.st_uid, info.st_mode

    def _ready(self):
        value = json.loads(_read(self.ready, 1024, private=True))
        if (type(value) is not dict or set(value) != {'token', 'signature', 'pid', 'uid'}
                or type(value['pid']) is not int or not 0 < value['pid'] < 2**31
                or type(value['uid']) is not int or type(value['token']) is not str
                or type(value['signature']) is not str):
            raise ValueError('Bounded current action worker metadata required')
        return value

    def current(self):
        try:
            owner = identity(self.owner['pid'])
            worker = identity(self.worker['pid'])
            return (self.lifetime.alive() and self._socket_identity() == self.socket_identity
                    and owner is not None and all(owner[key] == self.owner[key] for key in ('pid', 'uid', 'birth'))
                    and self._ready() == self.record and worker is not None
                    and worker['state'] in ('R', 'S', 'D', 'T', 't', 'W', 'I', 'P')
                    and all(worker[key] == self.worker[key] for key in ('pid', 'uid', 'birth')))
        except (OSError, ValueError, UnicodeError):
            return False

    def clients(self):
        if not self.current():
            raise ValueError('Original compositor retired')
        raw = json.loads(self.client._request('j/clients'))
        if not self.current() or type(raw) is not list or len(raw) > 256:
            raise ValueError('Bounded original compositor clients required')
        # Drop titles, classes and every other field immediately after parsing.
        return [{key: row.get(key) for key in ('pid', 'mapped', 'hidden', 'xwayland')}
                for row in raw if type(row) is dict and type(row.get('pid')) is int and 0 < row['pid'] < 2**31]

    def close(self):
        self.lifetime.close()


def run(argv):
    import gi
    gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
    from gi.repository import Gtk, Gdk, GLib, Gio
    name = 'dev.loopy.browser.startup.w' + secrets.token_hex(16)
    app = Gtk.Application(application_id=name, flags=Gio.ApplicationFlags.NON_UNIQUE)
    GLib.set_prgname(name)

    class View:
        def __init__(self):
            self.closed = False
            self.window = Gtk.ApplicationWindow(application=app)
            self.window.set_title('브라우저 시작'); self.window.set_default_size(440, 200)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16); box.set_border_width(20)
            self.label = Gtk.Label(label=state.message('PENDING')); self.label.set_line_wrap(True)
            self.label.set_max_width_chars(48); box.pack_start(self.label, True, True, 0)
            self.button = Gtk.Button(label='닫기'); self.button.connect('clicked', lambda *_: self.window.destroy())
            box.pack_start(self.button, False, False, 0); self.window.add(box)
            self.window.connect('destroy', lambda *_: setattr(self, 'closed', True))
            self.window.connect('realize', self.start); self.window.show_all()

        def render(self, status, code=None):
            if self.closed:
                return False
            if status == 'READY':
                self.window.destroy()
            else:
                self.label.set_text(state.message(status, code))
            return False

        def start(self, *_):
            native = self.window.get_window(); display = self.window.get_display()
            if (native is None or native.__gtype__.name != 'GdkWaylandWindow'
                    or display.__gtype__.name != 'GdkWaylandDisplay'):
                self.render('UNAVAILABLE'); return
            app.hold()
            threading.Thread(target=self.observe, name='loopy-browser-startup', daemon=True).start()

        def observe(self):
            child = compositor = reader = None
            fatal = state.FatalClassifier(); lock = threading.Lock()
            stage = 'session'
            try:
                compositor = Compositor()
                stage = 'command'
                started = time.monotonic(); child = state.spawn(argv)
                stage = 'observe'
                def drain():
                    while True:
                        data = child.stderr.read1(4096)
                        with lock:
                            if not data:
                                fatal.finish(); return
                            fatal.feed(data)
                reader = threading.Thread(target=drain, name='loopy-browser-stderr', daemon=True); reader.start()
                owner = identity(child.pid)
                attempt = state.Startup(child.pid, os.getuid(), owner['birth'] if owner else 1, started)
                while True:
                    code = child.poll()
                    if code is not None:
                        reader.join(timeout=1)
                    with lock:
                        cause = fatal.kind
                    current = compositor.current()
                    try:
                        windows = compositor.clients() if code is None and current else []
                        rows = process_rows(child.pid, windows, os.getuid()) if code is None else {}
                    except (OSError, ValueError, UnicodeError):
                        windows = []; rows = {child.pid: owner} if owner else {}
                        current = compositor.current()
                    result = attempt.observe(time.monotonic(), code, cause, rows, windows,
                                             compositor_current=current)
                    if result != 'PENDING':
                        GLib.idle_add(self.render, result, code); break
                    time.sleep(.2)
            except (OSError, ValueError, UnicodeError):
                GLib.idle_add(self.render, 'COMMAND_FAILED' if stage == 'command' else 'UNAVAILABLE')
            finally:
                if compositor is not None:
                    compositor.close()
                # Closing the progress/error UI never kills the browser. Keep its
                # stderr drained until it exits, including after READY or TIMEOUT.
                if child is not None:
                    child.wait()
                    if reader is not None:
                        reader.join(timeout=1)
                        if not reader.is_alive():
                            child.stderr.close()
                GLib.idle_add(app.release)

    app.connect('activate', lambda *_: View())
    return app.run([])


def main(argv=None):
    values = sys.argv[1:] if argv is None else argv
    if not values or values[0] != '--':
        return 64
    try:
        state.plan(values[1:])
    except ValueError:
        return 64
    os.environ['GDK_BACKEND'] = 'wayland'
    from browser_inside_route import selection
    selected = selection(values[1:])
    if selected is not None:
        import inside_window
        encoded, initial_url = selected
        if initial_url is None:
            return inside_window.run(encoded)
        return inside_window.run(encoded, initial_url=initial_url)
    return run(values[1:])


if __name__ == '__main__':
    raise SystemExit(main())
