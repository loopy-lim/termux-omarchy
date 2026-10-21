#!/usr/bin/python3
"""Open an interactive SSH client in a Wayland terminal; persist endpoints only."""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

RECENT = Path.home() / '.local/share/loopy/remote-connections.json'
MAX_JSON = 16384
MAX_PROFILES = 16


def profile(host, user, port=22):
    if not isinstance(host, str) or not host or host != host.strip() or len(host) > 253:
        raise ValueError('호스트 이름 또는 IP 주소를 확인하세요.')
    if host.startswith('[') and host.endswith(']'):
        host = host[1:-1]
    try:
        host = str(ipaddress.ip_address(host))
        if '%' in host:
            raise ValueError('Scoped addresses are unsupported')
    except ValueError:
        try:
            host = host.encode('idna').decode('ascii').lower()
        except UnicodeError as failure:
            raise ValueError('호스트 이름을 확인하세요.') from failure
        labels = host.rstrip('.').split('.')
        if len(host) > 253 or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels):
            raise ValueError('호스트 이름 또는 IP 주소를 확인하세요.')
    if not isinstance(user, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,63}', user):
        raise ValueError('SSH 사용자 이름을 확인하세요.')
    if isinstance(port, str) and re.fullmatch(r'[0-9]{1,5}', port):
        port = int(port)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('포트는 1부터 65535 사이여야 합니다.')
    return {'host': host, 'user': user, 'port': port}


def checked_profile(value):
    if not isinstance(value, dict) or set(value) != {'host', 'user', 'port'}:
        raise ValueError('최근 연결에는 호스트·사용자·포트만 저장할 수 있습니다.')
    return profile(value['host'], value['user'], value['port'])


def ssh_argv(endpoint):
    value = checked_profile(endpoint)
    return ['/usr/bin/ssh', '-t', '-o', 'StrictHostKeyChecking=ask',
            '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3',
            '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1',
            '-p', str(value['port']), '-l', value['user'], '--', value['host']]


def checked_path(path):
    path = Path(path)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('최근 연결 파일은 심볼릭 링크를 통과할 수 없습니다.')
    return path


def load_recent(path=RECENT):
    path = checked_path(path)
    if not path.exists():
        return []
    if not path.is_file() or path.stat().st_size > MAX_JSON:
        raise ValueError('최근 연결 파일의 크기나 형식을 확인하세요.')
    with path.open('rb') as source:
        data = source.read(MAX_JSON + 1)
    if len(data) > MAX_JSON:
        raise ValueError('최근 연결 파일의 크기 제한을 넘었습니다.')
    value = json.loads(data)
    if not isinstance(value, dict) or set(value) != {'schema', 'profiles'} or type(value['schema']) is not int \
            or value['schema'] != 1 or not isinstance(value['profiles'], list) or len(value['profiles']) > MAX_PROFILES:
        raise ValueError('최근 연결 파일의 형식을 확인하세요.')
    return [checked_profile(item) for item in value['profiles']]


def save_recent(path, endpoint):
    path, endpoint = checked_path(path), checked_profile(endpoint)
    entries = [endpoint] + [item for item in load_recent(path) if item != endpoint]
    data = (json.dumps({'schema': 1, 'profiles': entries[:MAX_PROFILES]}, ensure_ascii=False) + '\n').encode()
    if len(data) > MAX_JSON:
        raise ValueError('최근 연결 파일의 크기 제한을 넘었습니다.')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.remote-', delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        checked_path(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def connect(endpoint, recent=RECENT, *, terminal='/usr/bin/foot'):
    value = checked_profile(endpoint)
    # Validate a pre-existing file before opening a terminal. Unknown fields may
    # contain private data, so a malformed file is never silently replaced.
    load_recent(recent)
    argv = [terminal, '--hold', '--app-id=loopy-remote', '--title=SSH · ' + value['user'] + '@' + value['host'], '--']
    child = subprocess.Popen(argv + ssh_argv(value), stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                             env=dict(os.environ, GDK_BACKEND='wayland'))
    save_recent(recent, value)
    return child.pid


def launch_remote_desktop():
    return subprocess.Popen([sys.executable, str(Path(__file__).with_name('remote_desktop.py'))],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True,
                            env=dict(os.environ, GDK_BACKEND='wayland'))


def main():
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gio, Gtk

    app = Gtk.Application(application_id='dev.loopy.RemoteConnections', flags=Gio.ApplicationFlags.NON_UNIQUE)
    def activated(application):
        window = Gtk.ApplicationWindow(application=application, title='원격 SSH 연결')
        window.set_default_size(640, -1)
        window.set_border_width(20)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        window.add(box)
        explanation = Gtk.Label(label='다른 Linux·macOS 서버의 셸에 연결합니다.\n서버의 SSH 서비스와 네트워크 접근이 필요합니다.')
        explanation.set_line_wrap(True)
        explanation.set_xalign(0)
        box.pack_start(explanation, False, False, 0)
        recent = Gtk.ComboBoxText()
        recent.append_text('새 연결')
        recent.set_active(0)
        box.pack_start(recent, False, False, 0)
        fields = {}
        for key, title, default in (('host', '호스트 또는 IP', ''), ('user', 'SSH 사용자', ''), ('port', '포트', '22')):
            row = Gtk.Box(spacing=12)
            label = Gtk.Label(label=title)
            label.set_size_request(108, -1)
            label.set_xalign(0)
            entry = Gtk.Entry()
            entry.set_text(default)
            row.pack_start(label, False, False, 0)
            row.pack_start(entry, True, True, 0)
            box.pack_start(row, False, False, 0)
            fields[key] = entry
        status = Gtk.Label(label='비밀번호나 개인 키는 이 화면에 저장하지 않습니다.')
        status.set_line_wrap(True)
        status.set_xalign(0)
        box.pack_start(status, False, False, 0)
        entries = []
        try:
            entries = load_recent()
            for item in entries:
                recent.append_text(f"{item['user']}@{item['host']}:{item['port']}")
        except (OSError, ValueError) as failure:
            status.set_text(str(failure))
    
        def selected(combo):
            position = combo.get_active() - 1
            if 0 <= position < len(entries):
                for key, value in entries[position].items():
                    fields[key].set_text(str(value))
    
        def opened(_button):
            try:
                endpoint = profile(*(fields[key].get_text() for key in ('host', 'user', 'port')))
                connect(endpoint)
                status.set_text('SSH 터미널을 열었습니다. 서버 지문과 인증은 터미널에서 확인하세요.')
            except (OSError, ValueError) as failure:
                status.set_text(str(failure))
    
        recent.connect('changed', selected)
        button = Gtk.Button(label='SSH 터미널 열기')
        button.connect('clicked', opened)
        box.pack_start(button, False, False, 0)
        fields['host'].grab_focus()
        screen = Gtk.Button(label='원격 화면 · RDP/VNC')
        screen.set_size_request(-1, 44)
        def opened_desktop(_button):
            try:
                launch_remote_desktop()
                status.set_text('원격 화면 연결 창을 열었습니다.')
            except (OSError, ValueError) as failure:
                status.set_text(str(failure))
        screen.connect('clicked', opened_desktop)
        box.pack_start(screen, False, False, 0)
        window.show_all()
    app.connect('activate', activated)
    return app.run([sys.argv[0]])


if __name__ == '__main__':
    raise SystemExit(main())
