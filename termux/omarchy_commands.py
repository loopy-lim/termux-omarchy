"""Native host and isolated guest environments for the owned desktop."""
import os
import hashlib
import json
from omarchy_proot import selection

CONTAINER = 'loopy-omarchy'
HYPR = '/opt/omarchy-android/hyprland'
AQUA = '/opt/omarchy-android/aquamarine'
MESA = '/opt/omarchy-android/mesa'
SOCKET = 'wayland-omarchy'


def display_refresh(root):
    """Use a device-tested cadence, keeping other installations at 60 Hz."""
    path = root / 'display-refresh.json'
    if not path.exists():
        return '60000'
    row = path.lstat()
    if path.is_symlink() or not path.is_file() or row.st_uid != os.getuid() or row.st_mode & 0o022:
        raise ValueError('display-refresh-owner')
    value = json.loads(path.read_text())
    refresh = value.get('refreshMhz')
    if value.get('schema') != 1 or type(refresh) is not int or refresh not in (60000, 90000, 120000, 144000):
        raise ValueError('display-refresh-value')
    return str(refresh)


def native_graphics(root, env):
    """Select the explicitly installed, digest-checked native AHB transport."""
    directory = root / 'graphics-ahb'
    manifest = directory / 'selection.json'
    if not manifest.exists():
        return
    value = json.loads(manifest.read_text())
    if value.get('schema') != 1:
        raise ValueError('native-graphics-schema')
    for name in ('libvulkan_freedreno.so', 'icd.json'):
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid() \
                or path.stat().st_mode & 0o022 \
                or hashlib.sha256(path.read_bytes()).hexdigest() != value.get('sha256', {}).get(name):
            raise ValueError('native-graphics-integrity')
    icd = json.loads((directory / 'icd.json').read_text())
    if icd['ICD']['library_path'] != str(directory / 'libvulkan_freedreno.so'):
        raise ValueError('native-graphics-icd')
    env.update(VK_ICD_FILENAMES=str(directory / 'icd.json'), LOOPY_X11_AHB='1',
               LD_PRELOAD='/system/lib64/libbinder_ndk.so:/system/lib64/libnativewindow.so')


def environment(home, prefix, host):
    env = os.environ.copy()
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS',
                'DBUS_STARTER_ADDRESS', 'XAUTHORITY', 'TERMUX_X11_XSTARTUP', 'I3SOCK',
                'LIBGL_ALWAYS_SOFTWARE', 'MESA_LOADER_DRIVER_OVERRIDE', 'GALLIUM_DRIVER',
                'VK_DRIVER_FILES', 'VK_ICD_FILENAMES', 'VTEST_SOCKET_NAME', 'LD_LIBRARY_PATH',
                'LD_PRELOAD', 'LOOPY_X11_AHB', 'MESA_VK_WSI_PRESENT_MODE', 'vblank_mode',
                'PULSE_SERVER', 'PULSE_COOKIE', 'PULSE_SINK', 'PULSE_SOURCE',
                'PULSE_RUNTIME_PATH', 'PULSE_STATE_PATH', 'PD_PROOT_BIN', 'PROOT_LOADER', 'PROOT_EXITKILL', 'PROOT_TMP_DIR'):
        env.pop(key, None)
    env.update(HOME=str(home), PREFIX=str(prefix), TERMUX__HOME=str(home),
                    TERMUX__PREFIX=str(prefix), PATH=f'{prefix}/bin:/system/bin',
                    TMPDIR=str(prefix / 'tmp'), PROOT_TMP_DIR=str(prefix / 'tmp'), LANG='C.UTF-8', LC_ALL='C.UTF-8',
                    LD_LIBRARY_PATH=f'{host}/lib/weston:{host}/lib:{prefix}/lib')
    return env


def commands(runtime, value):
    display, token = value['display'], value['token']
    refresh = value.get('requestedRefreshMhz')
    if refresh is None:  # Compatibility for older session records and direct callers.
        refresh = int(display_refresh(runtime.root))
    if type(refresh) is not int or refresh not in (60000, 90000, 120000, 144000):
        raise ValueError('session-refresh-value')
    refresh = str(refresh)
    width, height = str(value.get('width', 2560)), str(value.get('height', 1706))
    native = dict(runtime.env, DISPLAY=display, XDG_RUNTIME_DIR=str(runtime.short),
                  MESA_LOADER_DRIVER_OVERRIDE='zink', GALLIUM_DRIVER='zink',
                  VK_ICD_FILENAMES=str(runtime.prefix / 'share/vulkan/icd.d/freedreno_icd.aarch64.json'),
                  WESTON_X11_REFRESH_MHZ=refresh)
    native_graphics(runtime.root, native)
    native['WESTON_MODULE_MAP'] = ';'.join((
        f'x11-backend.so={runtime.root}/weston/x11-backend.so',
        f'gl-renderer.so={runtime.host}/lib/libweston-14/gl-renderer.so',
        f'kiosk-shell.so={runtime.host}/lib/weston/kiosk-shell.so'))
    guest = {'XDG_RUNTIME_DIR': '/run/user/1000', 'TMPDIR': '/run/user/1000', 'WAYLAND_DISPLAY': SOCKET,
             'PROOT_TMP_DIR': str(runtime.prefix / 'tmp'),
             'PULSE_SERVER': 'unix:/run/user/1000/pulse/native',
             'PULSE_COOKIE': '/run/user/1000/pulse/cookie',
             'XDG_SESSION_TYPE': 'wayland', 'XDG_CURRENT_DESKTOP': 'Hyprland',
             'XDG_SESSION_DESKTOP': 'Hyprland', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
             'OMARCHY_PROOT': '1', 'OMARCHY_GPU_MODE': 'kgsl', 'OMARCHY_UNLIMITED_PROCS': '1',
             'OMARCHY_OUTPUT_WIDTH': width, 'OMARCHY_OUTPUT_HEIGHT': height,
             'OMARCHY_REFRESH_MHZ': refresh, 'OMARCHY_SCALE': '1.5',
             'OMARCHY_KEYBOARD_LAYOUT': 'us', 'NO_AT_BRIDGE': '1', 'QT_ACCESSIBILITY': '0',
             'GTK_A11Y': 'none', 'XWAYLAND_NO_GLAMOR': '1',
             'MESA_LOADER_DRIVER_OVERRIDE': 'kgsl', 'LIBGL_DRIVERS_PATH': f'{MESA}/root/usr/lib/dri',
             'VK_ICD_FILENAMES': f'{MESA}/freedreno_icd.json',
             'LD_LIBRARY_PATH': f'{MESA}/root/usr/lib:{AQUA}/lib', 'FD_KGSL_ENABLE_DMABUF': '1',
             # Loopy 2026-10-20: mailbox present removes vsync-aligned acquire stalls in
             # ANGLE/Vulkan clients (YouTube 1080p60 presented 28->52.5fps, measured on Y900).
             'MESA_VK_WSI_PRESENT_MODE': 'mailbox',
             'AQ_NO_KMS_REQUIREMENT': '1', 'AQ_ANDROID_DMABUF_HEAP': '0',
             'AQ_ANDROID_DMABUF_GLFINISH': '0', 'AQ_ANDROID_DMABUF_VULKAN': '0',
             'AQ_WAYLAND_REFRESH_MHZ': refresh, 'HYPRLAND_ANDROID_DMABUF': '1',
             'HYPRLAND_SHM_GLFINISH': '0', 'HYPRLAND_SHM_DAMAGE': '1', 'HYPRLAND_SHM_PROFILE': '0',
             'HYPRLAND_GL_DMABUF_EXPORT': '1', 'AQ_NO_MODIFIERS': '1',
             'HYPRLAND_EGL_NO_MODIFIERS': '1', 'HYPRLAND_EGL_SURFACELESS': '1',
             'HYPRLAND_NO_SD_NOTIFY': '1', 'HYPRLAND_NO_SD_VARS': '1', 'HYPRLAND_NO_RT': '1',
             'QT_QPA_PLATFORM': 'wayland', 'GDK_BACKEND': 'wayland', 'SDL_VIDEODRIVER': 'wayland',
             'OMARCHY_PATH': '/usr/share/omarchy',
             'PATH': f'{HYPR}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
             'XDG_DATA_DIRS': f'{HYPR}/share:/usr/local/share:/usr/share'}
    proot = [str(runtime.prefix / 'bin/proot-distro'), 'login', '--isolated',
             '--bind', f'{runtime.short}:/run/user/1000', '--bind',
             f'{runtime.root}/sessions/{token}/pci-devices:/proc/bus/pci/devices', '--user', 'omarchy']
    guard = selection(runtime.root)
    if 'prootExitKillRequested' in value and (type(value['prootExitKillRequested']) is not bool
            or value['prootExitKillRequested'] != (guard is not None)):
        raise ValueError('proot-guard-session-changed')
    proot_env = dict(runtime.env)
    if guard is not None:
        proot_env['PD_PROOT_BIN'] = str(guard / 'proot')
        guest.update(PROOT_EXITKILL='1', PROOT_LOADER=str(guard / 'loader'))
    for key, val in guest.items():
        proot.extend(('-e', f'{key}={val}'))
    proot.extend((CONTAINER, '--', 'dbus-run-session',
                  '--config-file=/home/omarchy/.config/omarchy/proot-session-bus.conf', '--',
                  f'{HYPR}/bin/Hyprland', '--config', '/home/omarchy/.config/hypr/hyprland.lua'))
    return [([str(runtime.prefix / 'bin/termux-x11'), display, '-nolisten', 'tcp'], runtime.env),
            ([str(runtime.host / 'bin/weston'), '-B', 'x11', '--renderer=gl', '--shell=kiosk',
              f'--socket={SOCKET}', f'--width={width}', f'--height={height}', '--scale=1', '--idle-time=0'], native),
            (proot, proot_env)]
