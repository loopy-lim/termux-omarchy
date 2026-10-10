"""Foreground, output-only PulseAudio owned by the Omarchy supervisor."""
import json
import os
from pathlib import Path
import stat
import subprocess
import time

from processes import identity, read_json, run_bounded
from omarchy_resources import StartupLog, live_peer


class AudioFailure(ValueError):
    pass


def prepare(runtime, value):
    info = runtime.short.lstat()
    expected = {key: value[key] for key in ('schema', 'token', 'uid', 'root', 'runtime')}
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 \
            or [info.st_dev, info.st_ino, info.st_uid] != value['runtime'] \
            or info.st_uid != os.getuid() or read_json(runtime.short / 'owner.json') != expected:
        raise AudioFailure('audio-owner-invalid')
    path = runtime.short / 'pulse'
    if os.path.lexists(path):
        raise AudioFailure('audio-directory-existing')
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        raise AudioFailure('audio-directory-existing') from None
    (path / 'state').mkdir(mode=0o700)
    fd = os.open(path / 'cookie', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(os.urandom(256))


def command(runtime, value):
    path = runtime.short / 'pulse'
    env = dict(runtime.env, PULSE_RUNTIME_PATH=str(path), PULSE_STATE_PATH=str(path / 'state'),
               PULSE_SERVER='unix:' + str(path / 'native'), PULSE_COOKIE=str(path / 'cookie'))
    args = [str(runtime.prefix / 'bin/pulseaudio'), '-n', '--daemonize=no', '--use-pid-file=no',
            '--exit-idle-time=-1', '--disable-shm=yes', '--disallow-exit=yes',
            '--disallow-module-loading=yes', '--log-target=stderr',
            '-L', 'module-aaudio-sink sink_name=loopy_output rate=48000',
            '-L', f'module-native-protocol-unix socket={path}/native '
                  f'auth-cookie={path}/cookie auth-cookie-enabled=true']
    return args, env


def ready(runtime, value):
    record = value.get('audioProcess')
    if not isinstance(record, dict):
        return False
    if record.get('command') != command(runtime, value)[0]:
        raise AudioFailure('audio-process-command')
    if not live_peer(runtime.short / 'pulse/native', [record]):
        return False
    cookie = (runtime.short / 'pulse/cookie').lstat()
    if not stat.S_ISREG(cookie.st_mode) or cookie.st_uid != os.getuid() \
            or cookie.st_nlink != 1 or cookie.st_size != 256 or stat.S_IMODE(cookie.st_mode) != 0o600:
        raise AudioFailure('audio-cookie-ownership')
    try:
        text = run_bounded([str(runtime.prefix / 'bin/pactl'), '-f', 'json', 'list', 'sinks'],
                           env=command(runtime, value)[1], timeout=2, max_bytes=16384)
        sinks = json.loads(text)
    except (OSError, ValueError):
        return False
    return isinstance(sinks, list) and len(sinks) == 1 and sinks[0].get('name') == 'loopy_output' \
        and sinks[0].get('driver') == 'module-aaudio-sink.c'


def start(runtime, value, owned, logs, stopping):
    prepare(runtime, value)
    args, env = command(runtime, value)
    log = StartupLog(runtime.root / 'sessions' / value['token'] / 'audio.log')
    logs.append(log)
    child = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, env=env)
    owned.register(child.pid)
    log.attach(child.stdout)
    birth = None
    until = time.monotonic() + 8
    while time.monotonic() < until and not stopping.is_set():
        if child.poll() is not None:
            raise AudioFailure('audio-exited')
        owned.refresh()
        record = identity(child.pid, strict=True)
        if record is not None:
            current = {key: record[key] for key in ('pid', 'pgid', 'uid', 'starttime')}
            if record['pid'] != child.pid or record['uid'] != os.getuid() \
                    or record['ppid'] != os.getpid() or birth is not None and current != birth:
                raise AudioFailure('audio-process-identity')
            birth = current
            if record['command'] and record['command'] != args:
                raise AudioFailure('audio-process-command')
            if record['command'] == args:
                value['audioProcess'] = record  # Android may briefly expose an empty cmdline after exec.
                if ready(runtime, value):
                    return child
        time.sleep(.1)
    raise AudioFailure('audio-startup-unconfirmed')
