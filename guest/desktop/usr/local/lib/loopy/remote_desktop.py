#!/usr/bin/python3
"""Wayland RDP/VNC windows with endpoint-only profiles and native authentication."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parent))
import remote_connections as ssh

PROFILES = Path.home() / '.local/share/loopy/remote-desktop'
REMOTE_RUNTIME = Path('/loopy-remote-client')


def profile(protocol, host, user='', port=None):
    if protocol not in ('RDP', 'VNC'):
        raise ValueError('RDP 또는 VNC를 선택하세요.')
    if port is None:
        port = 3389 if protocol == 'RDP' else 5900
    address = ssh.profile(host, 'loopy', port)
    if not isinstance(user, str) or len(user) > 256 or user != user.strip() \
            or any(ord(char) < 32 or ord(char) == 127 for char in user):
        raise ValueError('사용자 이름을 확인하세요. DOMAIN\\user와 이메일 이름을 사용할 수 있습니다.')
    return {'protocol': protocol, 'host': address['host'], 'user': user, 'port': address['port']}


def checked_profile(value):
    if not isinstance(value, dict) or set(value) != {'protocol', 'host', 'user', 'port'}:
        raise ValueError('연결에는 주소·프로토콜·사용자·포트만 사용할 수 있습니다.')
    return profile(value['protocol'], value['host'], value['user'], value['port'])


def connection_text(endpoint):
    value = checked_profile(endpoint)
    host = value['host']
    if ':' in host:
        host = '[' + host + ']'
    # GLib key files escape backslashes, including Windows domain identities.
    user = value['user'].replace('\\', '\\\\')
    return ('[remmina]\nname=' + value['protocol'] + ' · ' + value['host']
            + '\nprotocol=' + value['protocol'] + '\nserver=' + host + ':' + str(value['port'])
            + '\nusername=' + user + '\ndisablepasswordstoring=1\ncert_ignore=0\nignore-tls-errors=0'
            + '\ndisableclipboard=1\nsharefolder=\nssh_tunnel_enabled=0\n'
            + 'resolution_mode=2\nscale=1\nviewmode=1\ncolordepth=32\nquality=2\n')


def profile_path(directory, endpoint):
    canonical = json.dumps(checked_profile(endpoint), sort_keys=True, ensure_ascii=True).encode()
    return Path(directory) / (hashlib.sha256(canonical).hexdigest() + '.remmina')


def connect(endpoint, directory=PROFILES, *, executable=None, extra_env=None, runtime=REMOTE_RUNTIME):
    value = checked_profile(endpoint)
    directory = ssh.checked_path(Path(directory))
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not directory.is_dir():
        raise ValueError('연결 파일 폴더를 확인하세요.')
    destination = ssh.checked_path(profile_path(directory, value))
    content = connection_text(value).encode('utf-8')
    def verify_existing():
        ssh.checked_path(destination)
        if not destination.is_file() or destination.stat().st_size != len(content) \
                or destination.read_bytes() != content:
            raise ValueError('기존 연결 파일을 보존했습니다. 사용자가 수정한 파일은 덮어쓰지 않습니다.')
    existed = destination.exists()
    if existed:
        verify_existing()
    published = None
    try:
        if not existed:
            ssh.checked_path(destination)
            try:
                descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            except FileExistsError:
                verify_existing()
            else:
                published = os.fstat(descriptor).st_ino
                with os.fdopen(descriptor, 'wb') as output:
                    output.write(content)
                    output.flush()
                    os.fsync(output.fileno())
        environment = dict(os.environ, **(extra_env or {}), GDK_BACKEND='wayland')
        extension = Path(runtime) / 'usr/bin/remmina'
        if executable is None and extension.is_file() and os.access(extension, os.X_OK):
            executable = str(extension)
            for key, relative, fallback in (('LD_LIBRARY_PATH', 'usr/lib', '/usr/lib'),
                                             ('XDG_DATA_DIRS', 'usr/share', '/usr/local/share:/usr/share')):
                environment[key] = str(Path(runtime) / relative) + ':' + environment.get(key, fallback)
        executable = executable or '/usr/bin/remmina'
        child = subprocess.Popen([executable, '--disable-news', '--no-tray-icon', '--connect', str(destination)],
                                 env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
        return child, destination
    except OSError:
        if published is not None and not destination.is_symlink() and destination.stat().st_ino == published:
            destination.unlink(missing_ok=True)
        raise


def main():
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gio, Gtk

    app = Gtk.Application(application_id='dev.loopy.RemoteDesktop', flags=Gio.ApplicationFlags.NON_UNIQUE)

    def activated(application):
        window = Gtk.ApplicationWindow(application=application, title='원격 화면 · RDP/VNC')
        window.set_default_size(640, -1)
        window.set_border_width(24)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        window.add(box)
        description = Gtk.Label(label='다른 컴퓨터의 화면을 엽니다.\nWindows는 RDP, Linux·Mac은 설정한 VNC 서버를 사용하세요.')
        description.set_line_wrap(True)
        description.set_xalign(0)
        box.pack_start(description, False, False, 0)
        protocol = Gtk.ComboBoxText()
        for item in ('RDP', 'VNC'):
            protocol.append_text(item)
        protocol.set_active(0)
        box.pack_start(protocol, False, False, 0)
        fields = {}
        for key, label, default in (('host', '호스트 또는 IP', ''), ('user', '사용자 (선택)', ''), ('port', '포트', '3389')):
            row = Gtk.Box(spacing=12)
            title = Gtk.Label(label=label)
            title.set_xalign(0)
            title.set_size_request(120, -1)
            entry = Gtk.Entry()
            entry.set_text(default)
            row.pack_start(title, False, False, 0)
            row.pack_start(entry, True, True, 0)
            box.pack_start(row, False, False, 0)
            fields[key] = entry
        status = Gtk.Label(label='인증은 열린 원격 창에서 진행합니다. 비밀번호 저장·클립보드·폴더 공유는 꺼져 있습니다.\nCtrl+Alt+Esc로 태블릿 입력을 반납할 수 있습니다.')
        status.set_line_wrap(True)
        status.set_xalign(0)
        box.pack_start(status, False, False, 0)

        def changed(combo):
            fields['port'].set_text('3389' if combo.get_active_text() == 'RDP' else '5900')

        def opened(_button):
            try:
                value = profile(protocol.get_active_text(), *(fields[key].get_text() for key in ('host', 'user', 'port')))
                connect(value)
                status.set_text('원격 클라이언트를 열었습니다. 서버 인증서를 확인하고 인증하세요. 연결 실패·재시도는 원격 창에서 확인할 수 있습니다.')
            except (OSError, ValueError) as failure:
                status.set_text(str(failure))

        protocol.connect('changed', changed)
        button = Gtk.Button(label='원격 화면 열기')
        button.set_size_request(-1, 44)
        button.connect('clicked', opened)
        box.pack_start(button, False, False, 0)
        fields['host'].grab_focus()
        window.show_all()

    app.connect('activate', activated)
    return app.run([sys.argv[0]])


if __name__ == '__main__':
    raise SystemExit(main())
