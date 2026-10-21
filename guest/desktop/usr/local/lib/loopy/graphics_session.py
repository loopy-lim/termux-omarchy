#!/usr/bin/python3
"""Apply only verified CPU OpenGL routes at a new desktop session boundary."""
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

TOKEN = re.compile(r'[A-Za-z0-9-]{1,64}\Z')
SOFTWARE = ('llvmpipe', 'softpipe')
GRAPHICS_ENV = ('GALLIUM_DRIVER', 'LIBGL_ALWAYS_SOFTWARE', 'MESA_LOADER_DRIVER_OVERRIDE',
                'EGL_PLATFORM', 'VK_ICD_FILENAMES', 'VK_DRIVER_FILES', 'LD_PRELOAD',
                'LD_LIBRARY_PATH', 'VTEST_SOCKET_NAME', 'VTEST_RENDERER_SOCKET_NAME')


def selected_provider(report, token):
    if not TOKEN.fullmatch(token) or not isinstance(report, dict) or type(report.get('schema')) is not int \
            or report.get('schema') != 1 or type(report.get('uid')) is not int \
            or report.get('uid') != os.getuid() or report.get('token') != token:
        return 'cairo'
    selected = report.get('selected')
    if selected not in SOFTWARE:
        return 'cairo'
    providers = report.get('providers')
    if not isinstance(providers, list): return 'cairo'
    for provider in providers:
        if isinstance(provider, dict) and provider.get('id') == selected \
                and provider.get('status') == 'ready' and provider.get('pixelVerified') is True \
                and str(provider.get('renderer', '')).lower().startswith(selected):
            return selected
    return 'cairo'


def session_environment(report, token, original):
    environment = dict(original)
    for key in list(environment):
        if key in GRAPHICS_ENV or key.startswith(('MESA_', 'GALLIUM_', 'LIBGL_', 'EGL_', 'VK_', 'VTEST_', 'LD_')):
            environment.pop(key, None)
    selected = selected_provider(report, token)
    if selected in SOFTWARE:
        environment.update(LIBGL_ALWAYS_SOFTWARE='true', GALLIUM_DRIVER=selected)
    # wl_shm output remains independent of an offscreen EGL context.
    environment.update(WLR_RENDERER='pixman', GDK_BACKEND='wayland', GDK_GL='disable',
                       GSK_RENDERER='cairo', LOOPY_GL_PROVIDER=selected)
    return environment


def write_report(path, report):
    path = Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Graphics report must not cross symlinks')
    data = (json.dumps(report, separators=(',', ':')) + '\n').encode()
    if len(data) > 32768:
        raise ValueError('Graphics report exceeds its limit')
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.graphics-', delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(data); output.flush(); os.fsync(output.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def read_report(token, directory=Path('/run/loopy')):
    if not TOKEN.fullmatch(token):
        return {}
    path = Path(directory) / ('graphics-' + token + '.json')
    try:
        if path.is_symlink() or not path.is_file():
            return {}
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode): return {}
            data = source.read(32769)
        report = json.loads(data) if len(data) <= 32768 else {}
        if not isinstance(report, dict) or not isinstance(report.get('providers'), list) \
                or any(not isinstance(p, dict) for p in report['providers']): return {}
        return report
    except (OSError, ValueError):
        return {}


def desktop(token):
    if not TOKEN.fullmatch(token):
        raise ValueError('Invalid graphics session token')
    try:
        from graphics_probe import collect
        socket = os.environ.get('LOOPY_VIRGL_SOCKET') or None
        report = collect(virgl_socket=socket)
        report['token'] = token
        if socket: report['virglSocket'] = socket
    except Exception as error:
        report = dict(schema=1, uid=os.getuid(), token=token, selected='cairo',
                      providers=[], reason=str(error)[:256])
    try:
        write_report(Path('/run/loopy') / ('graphics-' + token + '.json'), report)
    except (OSError, ValueError) as error:
        print('Graphics diagnosis unavailable: ' + str(error), file=sys.stderr)
    environment = session_environment(report, token, os.environ)
    os.execve('/usr/bin/dbus-run-session', ['/usr/bin/dbus-run-session', '--',
              '/usr/bin/sway', '-c', '/root/.config/sway/config'], environment)


def run_gl(arguments):
    proxy = bool(arguments and arguments[0] == '--virgl')
    if proxy: arguments = arguments[1:]
    if not arguments or arguments[0].startswith('-'):
        raise ValueError('Usage: loopy-gl executable [arguments]')
    token = os.environ.get('LOOPY_SESSION', '')
    report = read_report(token)
    environment = session_environment(report, token, os.environ)
    environment.pop('GDK_GL', None)
    if proxy:
        environment = proxy_environment(report, token, environment)
        if environment is None:
            print('VirGL render/transport not verified for this session. Use the CPU route.', file=sys.stderr)
            return 69
    elif environment['LOOPY_GL_PROVIDER'] == 'cairo':
        print('No verified OpenGL route. Open GPU alternatives with loopy-graphics.', file=sys.stderr)
        return 69
    os.execvpe(arguments[0], arguments, environment)


def proxy_environment(report, token, original):
    if not TOKEN.fullmatch(token) or not isinstance(report, dict) or type(report.get('schema')) is not int \
            or report.get('schema') != 1 or type(report.get('uid')) is not int \
            or report.get('uid') != os.getuid() or report.get('token') != token:
        return None
    socket = '/run/loopy/virgl-' + token + '.sock'
    providers = report.get('providers')
    if report.get('virglSocket') != socket or not isinstance(providers, list): return None
    for provider in providers:
        if isinstance(provider, dict) and provider.get('id') == 'virpipe' \
                and provider.get('status') == 'ready' and provider.get('pixelVerified') is True \
                and str(provider.get('renderer', '')).lower().startswith('virgl'):
            from graphics_probe import socket_available
            if not socket_available(socket): return None
            environment = session_environment(report, token, original)
            environment.update(GALLIUM_DRIVER='virpipe', LIBGL_ALWAYS_SOFTWARE='true',
                               VTEST_SOCKET_NAME=socket, LOOPY_GL_PROVIDER='virpipe', GDK_GL='gles')
            return environment
    return None


if __name__ == '__main__':
    try:
        if len(sys.argv) >= 3 and sys.argv[1] == '--run':
            sys.exit(run_gl(sys.argv[2:]))
        elif len(sys.argv) == 2:
            desktop(sys.argv[1])
        else:
            raise ValueError('Expected desktop token or --run executable')
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(64)
