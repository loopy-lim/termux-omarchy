"""One typed Android activation owns one real Pulse/PipeWire source, never a recorder."""
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile
import time


def private_directory(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid():
        raise ValueError('Owned private microphone directory required')


def read_owned(path, limit):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > limit):
            raise ValueError('Owned bounded microphone file required')
        value = os.read(descriptor, limit + 1)
        if len(value) > limit:
            raise ValueError('Microphone file budget exceeded')
        return value
    finally:
        os.close(descriptor)


class Endpoint:
    def __init__(self, directory, environment, pactl='/usr/bin/pactl', timeout=.5):
        self.directory = Path(directory)
        private_directory(self.directory)
        session = read_owned(self.directory / 'session', 65)
        if not re.fullmatch(rb'[A-Za-z0-9-]{1,64}\n', session):
            raise ValueError('Current microphone session required')
        self.session = session[:-1].decode('ascii')
        self.environment = dict(environment)
        self.pactl = pactl
        self.timeout = timeout
        self.activation = None
        self.module = None
        self.processed = None
        self.unknown = False
        self.pending_file = None
        self.epoch = 0
        self.state = 'armed'
        self.refresh_seconds = .2
        self.next_refresh = 0

    def publish(self, activation, state):
        private_directory(self.directory)
        if read_owned(self.directory / 'session', 65) != (self.session + '\n').encode('ascii'):
            raise ValueError('Stale microphone session')
        target = self.directory / 'microphone-state.json'
        if target.exists() or target.is_symlink():
            read_owned(target, 512)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=self.directory, prefix='.microphone-state-', delete=False) as output:
                temporary = Path(output.name)
                os.chmod(temporary, 0o600)
                json.dump({'session': self.session, 'activation': activation, 'state': state, 'epoch': self.epoch}, output)
            temporary.replace(target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def command(self, arguments):
        output = subprocess.run([self.pactl, *arguments], env=self.environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=self.timeout, check=True).stdout
        if len(output) > 65536:
            raise ValueError('Microphone metadata budget exceeded')
        return output

    def recover_identity(self):
        identities = []
        for line in self.command(['list', 'modules', 'short']).decode('utf-8').splitlines():
            fields = line.split('\t')
            if len(fields) >= 3 and fields[1] == 'module-pipe-source':
                arguments = shlex.split(fields[2])
                if ('file=' + self.pending_file in arguments
                        and 'source_name=loopy_android_microphone' in arguments):
                    if not re.fullmatch('[0-9]{1,10}', fields[0]):
                        raise ValueError('Owned Pulse module identity required')
                    identities.append(fields[0])
        if len(identities) > 1:
            raise ValueError('Ambiguous microphone module ownership')
        self.module = identities[0] if identities else None
        self.unknown = False

    def unload(self):
        if self.unknown:
            self.recover_identity()
        if self.module is not None:
            self.command(['unload-module', self.module])
            self.module = None

    def refresh(self):
        if self.module is None or time.monotonic() < self.next_refresh:
            return
        self.next_refresh = time.monotonic() + self.refresh_seconds
        sources = json.loads(self.command(['-f', 'json', 'list', 'sources']))
        if not isinstance(sources, list):
            raise ValueError('Typed source metadata required')
        owned = [item for item in sources if isinstance(item, dict) and item.get('name') == 'loopy_android_microphone']
        if (len(owned) != 1 or owned[0].get('state') not in ('RUNNING', 'IDLE', 'SUSPENDED')
                or type(owned[0].get('mute')) is not bool):
            raise ValueError('Owned source state unavailable')
        state = 'running' if owned[0]['state'] == 'RUNNING' and not owned[0]['mute'] else 'armed'
        if state == 'running' and self.state != 'running':
            self.epoch += 1
        self.state = state
        self.publish(self.activation, state)

    def owned_fifo(self, activation):
        owned = self.directory / ('mic-' + activation)
        private_directory(owned)
        fifo = (owned / 'input.pcm').lstat()
        if (not stat.S_ISFIFO(fifo.st_mode) or fifo.st_uid != os.geteuid()
                or stat.S_IMODE(fifo.st_mode) != 0o600):
            raise ValueError('Owned microphone FIFO required')
        return owned / 'input.pcm'

    def tick(self):
        try:
            private_directory(self.directory)
            if read_owned(self.directory / 'session', 65) != (self.session + '\n').encode('ascii'):
                self.close()
                return
            value = json.loads(read_owned(self.directory / 'microphone-request.json', 512))
            if (not isinstance(value, dict) or set(value) != {'action', 'session', 'activation'}
                    or value['session'] != self.session or value['action'] not in ('start', 'stop')
                    or not isinstance(value['activation'], str)
                    or not re.fullmatch('[0-9a-f]{32}', value['activation'])):
                return
            action, activation = value['action'], value['activation']
            if self.processed == (action, activation):
                self.refresh()
                return
            if action == 'stop':
                if activation != self.activation:
                    if self.activation is None and self.module is None and not self.unknown:
                        self.owned_fifo(activation)
                        self.publish(activation, 'off')
                        self.processed = (action, activation)
                    return
                self.unload()
                self.publish(activation, 'off')
                self.activation = None
            else:
                fifo = self.owned_fifo(activation)
                self.unload()
                self.activation = activation
                self.pending_file = str(fifo)
                self.unknown = True
                result = self.command(['load-module', 'module-pipe-source', 'file=' + str(fifo),
                    'source_name=loopy_android_microphone', 'format=s16le', 'rate=48000', 'channels=1', 'channel_map=mono'])
                if not re.fullmatch(rb'[0-9]{1,10}\s*', result):
                    raise ValueError('Owned Pulse module identity required')
                self.module = result.strip().decode('ascii')
                self.unknown = False
                self.epoch = 0
                self.state = 'armed'
                self.next_refresh = 0
                self.refresh()
            self.processed = (action, activation)
        except (OSError, ValueError, subprocess.SubprocessError):
            if self.activation is not None:
                self.processed = ('start', self.activation)
                try:
                    self.publish(self.activation, 'unavailable')
                    self.unload()
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass

    def close(self):
        activation = self.activation
        try:
            self.unload()
            if activation is not None:
                self.publish(activation, 'off')
        except (OSError, ValueError, subprocess.SubprocessError):
            if activation is not None:
                try:
                    self.publish(activation, 'unavailable')
                except (OSError, ValueError):
                    pass
            return False
        self.activation = None
        return True
