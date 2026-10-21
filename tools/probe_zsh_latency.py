#!/usr/bin/env python3
"""Private PTY typing benchmark; emits timings only and never reads user history.

Run through Sway exec under the ordinary app UID. This measures ZLE processing,
not Android keyboard transport or the time until the display presents a frame.
"""
import argparse
import json
import os
from pathlib import Path
import pty
import re
import select
import signal
import statistics
import tempfile
import time

ACK = re.compile(rb"\x1b\]777;loopy-zle;([0-9]+)\x07")


def measure(zsh, profile):
    with tempfile.TemporaryDirectory(prefix="loopy-zle-") as directory:
        directory = Path(directory)
        startup = ''
        if profile:
            # The path is passed through the environment, never interpolated as shell code.
            startup = 'source "$LOOPY_ZLE_PROFILE"\n'
        startup += '''
HISTFILE="$ZDOTDIR/fixture-history"
HISTSIZE=0 SAVEHIST=0
autoload -Uz add-zle-hook-widget
_loopy_zle_ack() { printf '\033]777;loopy-zle;%d\007' ${#BUFFER}; }
add-zle-hook-widget line-pre-redraw _loopy_zle_ack
add-zle-hook-widget line-init _loopy_zle_ack
'''
        (directory / '.zshrc').write_text(startup)
        environment = {key: os.environ[key] for key in ('HOME', 'PATH', 'LANG') if key in os.environ}
        environment.update(TERM='xterm-256color', ZDOTDIR=str(directory),
                           LOOPY_ZLE_PROFILE=str(profile or ''))
        pid, fd = pty.fork()
        if pid == 0:
            os.execve(zsh, [zsh, '-i'], environment)
        pending = bytearray()

        def await_length(length, timeout):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                matches = list(ACK.finditer(pending))
                if any(int(match.group(1)) == length for match in matches):
                    pending.clear()
                    return
                if select.select([fd], [], [], max(0, deadline - time.monotonic()))[0]:
                    data = os.read(fd, 8192)
                    if not data:
                        raise RuntimeError('private shell ended before acknowledgement')
                    pending.extend(data)
                    if len(pending) > 32768:
                        del pending[:-8192]
            raise TimeoutError('private shell redraw acknowledgement timed out')

        start = time.monotonic()
        try:
            await_length(0, 30)
            startup_ms = (time.monotonic() - start) * 1000
            samples = []
            for length, character in enumerate(b'abcdefghijklmnopqrst', 1):
                before = time.monotonic()
                os.write(fd, bytes([character]))
                await_length(length, 3)
                samples.append((time.monotonic() - before) * 1000)
            os.write(fd, b'\x15') # Discard the owned fixture, never execute it.
            await_length(0, 3)
            return {'samples': len(samples), 'startup_ms': round(startup_ms, 3),
                    'median_ms': round(statistics.median(samples), 3),
                    'p95_ms': round(sorted(samples)[18], 3), 'maximum_ms': round(max(samples), 3)}
        finally:
            try:
                # Interactive shells can ignore SIGTERM. This PID owns only the
                # disposable PTY and fixture, so cleanup must be bounded.
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(fd)
            os.waitpid(pid, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expect-uid', type=int, required=True)
    parser.add_argument('--zsh', default='/bin/zsh')
    parser.add_argument('--profile', type=Path, default=Path('/root/.zshrc'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.getuid() != args.expect_uid:
        parser.error('ordinary application UID differs from the expected UID')
    if not args.profile.is_file():
        parser.error('profile file is absent')
    report = {'uid': os.getuid(), 'scope': 'private PTY ZLE redraw; no Android/display transport'}
    for name, profile in (('stock', None), ('profile', args.profile.resolve())):
        try:
            report[name] = {'passed': True, **measure(args.zsh, profile)}
        except (OSError, RuntimeError, TimeoutError) as error:
            report[name] = {'passed': False, 'error_type': type(error).__name__}
    # Refuse to replace an existing measurement or follow an existing symlink.
    with args.output.open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
    return 0 if all(report[name]['passed'] for name in ('stock', 'profile')) else 1


if __name__ == '__main__':
    raise SystemExit(main())
