"""Native host and isolated guest environments for the owned desktop."""
import os
from omarchy_proot import selection

CONTAINER = 'loopy-omarchy'
HYPR = '/opt/omarchy-android/hyprland'
AQUA = '/opt/omarchy-android/aquamarine'
MESA = '/opt/omarchy-android/mesa'
SOCKET = 'wayland-omarchy'


def environment(home, prefix, host):
    env = os.environ.copy()
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS',
                'DBUS_STARTER_ADDRESS', 'XAUTHORITY', 'TERMUX_X11_XSTARTUP', 'I3SOCK',
                'LIBGL_ALWAYS_SOFTWARE', 'MESA_LOADER_DRIVER_OVERRIDE', 'GALLIUM_DRIVER',
                'VK_DRIVER_FILES', 'VK_ICD_FILENAMES', 'VTEST_SOCKET_NAME', 'LD_LIBRARY_PATH',
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
    width, height = str(value.get('width', 2560)), str(value.get('height', 1706))
    native = dict(runtime.env, DISPLAY=display, XDG_RUNTIME_DIR=str(runtime.short),
                  MESA_LOADER_DRIVER_OVERRIDE='zink', GALLIUM_DRIVER='zink',
                  VK_ICD_FILENAMES=str(runtime.prefix / 'share/vulkan/icd.d/freedreno_icd.aarch64.json'),
                  WESTON_X11_REFRESH_MHZ='60000')
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
             'OMARCHY_REFRESH_MHZ': '60000', 'OMARCHY_SCALE': '1.5',
             'OMARCHY_KEYBOARD_LAYOUT': 'us', 'NO_AT_BRIDGE': '1', 'QT_ACCESSIBILITY': '0',
             'GTK_A11Y': 'none', 'XWAYLAND_NO_GLAMOR': '1',
             'MESA_LOADER_DRIVER_OVERRIDE': 'kgsl', 'LIBGL_DRIVERS_PATH': f'{MESA}/root/usr/lib/dri',
             'VK_ICD_FILENAMES': f'{MESA}/freedreno_icd.json',
             'LD_LIBRARY_PATH': f'{MESA}/root/usr/lib:{AQUA}/lib', 'FD_KGSL_ENABLE_DMABUF': '1',
             'AQ_NO_KMS_REQUIREMENT': '1', 'AQ_ANDROID_DMABUF_HEAP': '0',
             'AQ_ANDROID_DMABUF_GLFINISH': '0', 'AQ_ANDROID_DMABUF_VULKAN': '0',
             'AQ_WAYLAND_REFRESH_MHZ': '60000', 'HYPRLAND_ANDROID_DMABUF': '1',
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
