#!/usr/bin/python3
"""Omarchy PRoot panel controls for the owned Android AAudio output."""
import json
import os
import re
import sys

from processes import run_bounded


def status_fields(sinks):
    if not isinstance(sinks, list) or len(sinks) != 1:
        return 0, 1, 0
    sink = sinks[0]
    if not isinstance(sink, dict) or sink.get('name') != 'loopy_output' \
            or sink.get('driver') != 'module-aaudio-sink.c' or type(sink.get('mute')) is not bool:
        return 0, 1, 0
    try:
        values = [channel['value'] for channel in sink['volume'].values()]
        if not values or any(type(value) is not int or not 0 <= value <= 196608 for value in values):
            return 0, 1, 0
        return min(100, round(max(values) * 100 / 65536)), int(sink['mute']), 1
    except (KeyError, TypeError, AttributeError):
        return 0, 1, 0


def dispatch(args, runner=run_bounded):
    if args not in (['status'], ['mute-toggle']) and not (len(args) == 2 and args[0] == 'volume'
            and re.fullmatch(r'(0|[1-9][0-9]?|100)', args[1])):
        raise ValueError('audio-arguments')
    env = dict(os.environ, PULSE_SERVER='unix:/run/user/1000/pulse/native',
               PULSE_COOKIE='/run/user/1000/pulse/cookie')
    def call(arguments):
        return runner(['/usr/bin/pactl', *arguments], env=env, timeout=3, max_bytes=16384)
    def status():
        return status_fields(json.loads(call(['-f', 'json', 'list', 'sinks'])))
    before = status()
    if args == ['status']:
        return before
    if before[2] != 1:
        raise ValueError('audio-output-unavailable')
    if args[0] == 'volume':
        expected = (int(args[1]), before[1], 1)
        call(['set-sink-volume', 'loopy_output', args[1] + '%'])
    else:
        expected = (before[0], 1 - before[1], 1)
        call(['set-sink-mute', 'loopy_output', str(expected[1])])
    after = status()
    if after != expected:
        raise ValueError('audio-change-unconfirmed')
    return after


def main():
    args = sys.argv[1:]
    try:
        values = dispatch(args)
    except (OSError, ValueError):
        if args == ['status']:
            values = (0, 1, 0)
        else:
            print('audio-control-unavailable', file=sys.stderr)
            return 1
    print(' '.join(str(value) for value in values), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
