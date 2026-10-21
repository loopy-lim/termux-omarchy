"""Typed actions on the original Lua compositor, inside its own PRoot tree.

Use the genuine Hyprland socket without spawning hyprctl for each key.
No user-provided command, Lua expression or process arguments enter this API.
"""
import json
import base64
import os
from pathlib import Path
import re
import socket
import stat
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from mac_commands import KEYS as EDIT_KEYS, OPERATIONS as EDIT_OPERATIONS
import loopy_input

TERMINALS = frozenset({'foot', 'footclient', 'loopy-terminal', 'loopy-code', 'loopy-monitor',
    'loopy-cli-files', 'loopy-owned-omarchy', 'alacritty', 'kitty', 'org.wezfurlong.wezterm', 'com.mitchellh.ghostty'})

QUERIES = frozenset({'activeworkspace', 'activewindow', 'clients', 'workspaces', 'monitors', 'cursorpos'})
NUMBERS = frozenset(map(str, range(1, 11)))
IME_KEYS = frozenset({'Return', 'BackSpace', 'Delete', 'Tab', 'Escape', 'Up', 'Down',
                      'Left', 'Right', 'Home', 'End', 'Prior', 'Next'})
WINDOWS = {
    'fullscreen': "hl.dsp.window.fullscreen({mode='fullscreen'})",
    'floating': "hl.dsp.window.float({action='toggle'})",
    'close': 'hl.dsp.window.close()',
    'focus-left': "hl.dsp.focus({direction='l'})",
    'focus-right': "hl.dsp.focus({direction='r'})",
    'focus-up': "hl.dsp.focus({direction='u'})",
    'focus-down': "hl.dsp.focus({direction='d'})",
    'focus-next': 'hl.dsp.window.cycle_next({next=true})',
    'focus-prev': 'hl.dsp.window.cycle_next({next=false})',
    'resize-grow-width': 'hl.dsp.window.resize({x=24,y=0,relative=true})',
    'resize-shrink-width': 'hl.dsp.window.resize({x=-24,y=0,relative=true})',
    'resize-grow-height': 'hl.dsp.window.resize({x=0,y=24,relative=true})',
    'resize-shrink-height': 'hl.dsp.window.resize({x=0,y=-24,relative=true})',
}
SCALES = {'scale-100': '1', 'scale-125': '1.25', 'scale-150': '1.5', 'scale-175': '1.75', 'scale-200': '2'}
APPLICATIONS = {
    'terminal': '/usr/bin/foot --app-id=foot /usr/bin/zsh -l',
    'code': '/usr/bin/foot --app-id=loopy-code /usr/bin/nvim',
    'code-ide': '/usr/bin/foot --app-id=loopy-code /usr/bin/nvim',
    'editor': '/usr/bin/foot --app-id=loopy-code /usr/bin/nvim',
    'files': '/usr/bin/nautilus --new-window',
    'monitor': '/usr/bin/foot --app-id=loopy-monitor /usr/bin/btop',
    'browser': '/usr/bin/bash /usr/share/omarchy/bin/omarchy-launch-browser',
    'launcher': '/usr/bin/bash /usr/share/omarchy/bin/omarchy-menu summon apps',
    'remote': '/usr/bin/python /usr/share/loopy/omarchy-bridge/remote_bridge.py ssh',
    'remote-desktop': '/usr/bin/python /usr/share/loopy/omarchy-bridge/remote_bridge.py desktop',
}
THEMES = {'Tokyo Night': "'Tokyo Night'", 'Catppuccin': 'Catppuccin', 'Nord': 'Nord'}


class CompositorLifetime:
    """The original event socket closes when this exact compositor exits."""
    def __init__(self, control):
        path = Path(control).with_name('.socket2.sock')
        info = path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Owned compositor lifetime socket required')
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.socket.settimeout(2)
            self.socket.connect(str(path))
            if hasattr(socket, 'SO_PEERCRED'):
                _, uid, _ = struct.unpack('3i', self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if uid != os.getuid():
                    raise ValueError('Compositor lifetime peer belongs to another UID')
            self.socket.setblocking(False)
        except BaseException:
            self.close(); raise

    def alive(self, timeout=0):
        import select
        if not 0 <= timeout <= .1:
            raise ValueError('Bounded compositor liveness wait required')
        if not select.select([self.socket], [], [], timeout)[0]:
            return True
        # Discard event payloads; they contain no commands for this worker.
        # Bound each drain so a busy compositor cannot starve keyboard jobs.
        for _ in range(16):
            try:
                if not self.socket.recv(16384):
                    return False
            except BlockingIOError:
                return True
            except (ConnectionResetError, BrokenPipeError):
                return False
        return True

    def close(self):
        self.socket.close()


def action(job):
    if not isinstance(job, dict) or type(job.get('action')) is not str:
        raise ValueError('Typed desktop action required')
    kind = job['action']
    fields = {'workspace': 'target', 'move-workspace': 'target', 'window': 'operation', 'ime-key': 'key',
              'launch': 'app', 'theme': 'name', 'android-inside': 'component'}
    key = fields.get(kind)
    if key is None or set(job) != {'action', key} or type(job[key]) is not str:
        raise ValueError('Unsupported desktop action fields')
    value = job[key]
    if kind == 'android-inside':
        if len(value) > 512 or not re.fullmatch(r'[A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+', value):
            raise ValueError('Installed Android launcher component required')
        encoded = base64.urlsafe_b64encode(value.encode('ascii')).decode('ascii').rstrip('=')
        return 'hl.dsp.exec_cmd(' + json.dumps('/usr/bin/python -B /usr/share/loopy/omarchy-bridge/inside_window.py --component ' + encoded) + ')'
    if kind == 'launch' and value == 'overview':
        return WINDOWS['focus-next']
    if kind == 'launch' and value in APPLICATIONS:
        return 'hl.dsp.exec_cmd(' + json.dumps(APPLICATIONS[value]) + ')'
    if kind == 'theme' and value in THEMES:
        return 'hl.dsp.exec_cmd(' + json.dumps('/usr/bin/bash /usr/share/omarchy/bin/omarchy-theme-set ' + THEMES[value]) + ')'
    if kind == 'workspace':
        if value not in NUMBERS | {'next', 'prev'}:
            raise ValueError('Unknown workspace')
        target = {'next': 'e+1', 'prev': 'e-1'}.get(value, value)
        return "hl.dsp.focus({workspace='%s'})" % target
    if kind == 'move-workspace':
        if value not in NUMBERS:
            raise ValueError('Unknown destination workspace')
        return "hl.dsp.window.move({workspace='%s',follow=false})" % value
    if kind == 'window' and value in WINDOWS:
        return WINDOWS[value]
    if kind == 'ime-key' and value in IME_KEYS:
        return "hl.dsp.send_shortcut({mods='',key='%s'})" % value
    raise ValueError('Unknown desktop action')


class Hyprland:
    def __init__(self, path, timeout=2, reply_limit=1048576):
        if not .01 <= timeout <= 10 or not 1 <= reply_limit <= 1048576:
            raise ValueError('Bounded IPC deadline and response required')
        self.path, self.timeout, self.reply_limit = Path(path), timeout, reply_limit

    def _request(self, request):
        data = request.encode('utf-8')
        # The pinned server reads 1023-byte chunks. Half-close also handles
        # fragmentation, without waiting for a delimiter it never implements.
        if not 1 <= len(data) <= 1022 or b'\0' in data:
            raise ValueError('Bounded compositor request required')
        info = self.path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Owned compositor socket required')
        deadline = time.monotonic() + self.timeout
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(self.timeout)
            client.connect(str(self.path))
            if hasattr(socket, 'SO_PEERCRED'):
                _, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if uid != os.getuid():
                    raise ValueError('Compositor peer belongs to another UID')
            client.sendall(data)
            client.shutdown(socket.SHUT_WR)
            reply = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Compositor response deadline exceeded')
                client.settimeout(remaining)
                chunk = client.recv(min(16384, self.reply_limit + 1 - len(reply)))
                if not chunk:
                    break
                reply.extend(chunk)
                if len(reply) > self.reply_limit:
                    raise ValueError('Compositor response exceeds its bound')
        return reply.decode('utf-8')

    def execute(self, job):
        if isinstance(job, dict) and job.get('action') == 'window' and job.get('operation') in SCALES:
            if set(job) != {'action', 'operation'}:
                raise ValueError('Unsupported monitor scale fields')
            reply = self._request("eval hl.monitor({output='',mode='preferred',position='auto',scale=%s})" % SCALES[job['operation']])
            if reply.strip() != 'ok':
                raise ValueError('Original compositor rejected the monitor scale')
            return
        if isinstance(job, dict) and job.get('action') == 'edit':
            if (set(job) != {'action', 'operation'} or type(job['operation']) is not str
                    or job['operation'] not in EDIT_OPERATIONS):
                raise ValueError('Unsupported editing action')
            loopy_input.close() # Restore the physical keymap before resolving accelerator keysyms.
            self._edit(job['operation'])
            return
        if isinstance(job, dict) and job.get('action') == 'input':
            if (set(job) != {'action', 'text', 'backspaces'} or type(job['text']) is not str
                    or '\0' in job['text'] or len(job['text'].encode('utf-8')) > 4096
                    or type(job['backspaces']) is not int or not 0 <= job['backspaces'] <= 64):
                raise ValueError('Bounded Unicode input required')
            loopy_input.inject(job['text'], job['backspaces'], timeout=5)
            return
        planned = action(job) # Validate before any input connection/cleanup side effect.
        if job['action'] == 'ime-key':
            loopy_input.close()
        self._dispatch(planned)

    def _dispatch(self, planned):
        reply = self._request('dispatch ' + planned)
        if reply.strip() != 'ok':
            # Lua/dispatcher failures can contain user titles; never propagate
            # their contents into the Android error log.
            raise ValueError('Original compositor rejected the desktop action')

    def _edit(self, operation):
        window = self.query('activewindow')
        if (not isinstance(window, dict) or type(window.get('class')) is not str
                or type(window.get('address')) is not str
                or not re.fullmatch(r'0x[0-9a-fA-F]{1,16}', window['address'])
                or int(window['address'], 16) == 0):
            raise ValueError('Editing requires a selected application window')
        selector = 'address:' + window['address']
        terminal = window['class'].lower() in TERMINALS
        if operation in {'quit', 'minimize'} or operation == 'close' and terminal:
            planned = ("hl.dsp.window.move({workspace='special:scratchpad',follow=false,window='%s'})" % selector
                if operation == 'minimize' else "hl.dsp.window.close({window='%s'})" % selector)
            self._dispatch(planned)
            return
        if operation == 'deleteline':
            sequence = [('u', ('ctrl',))] if terminal else [('Home', ('shift',)), ('BackSpace', ())]
        else:
            key, modifiers = EDIT_KEYS[operation]
            if terminal and operation in {'copy', 'paste'}:
                modifiers = ('ctrl', 'shift')
            if operation == 'zoom_in':
                # Lua resolves the base keysym without modifiers. Foot accepts
                # Ctrl+equal; other apps retain Ctrl+plus via Shift+equal.
                key, modifiers = 'equal', ('ctrl',) if terminal else ('ctrl', 'shift')
            sequence = [(key, modifiers)]
        for key, modifiers in sequence:
            mods = ' '.join(modifier.upper() for modifier in modifiers)
            self._dispatch("hl.dsp.send_shortcut({mods='%s',key='%s',window='%s'})" % (mods, key, selector))

    def query(self, kind):
        if type(kind) is not str or kind not in QUERIES:
            raise ValueError('Unsupported compositor query')
        return json.loads(self._request('j/' + kind))
