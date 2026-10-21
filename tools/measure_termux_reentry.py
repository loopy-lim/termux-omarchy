#!/usr/bin/env python3
"""Wall-clock the real `loopy-omarchy` re-entry on the device. Read-only wrapper.

Runs inside the primary Termux shell and times the actual user entry command.
No settings are changed and no component boundaries are attributed: this
receipt records end-to-end seconds only; am/ensure/runtime attribution needs
the phase timestamps that the launcher does not emit.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def run_once(command, timeout):
    """One real entry; returns seconds, parsed status, and a fixed failure kind."""
    start = time.monotonic()
    try:
        row = subprocess.run(command, capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {'seconds': time.monotonic() - start, 'status': 'TIMEOUT', 'reason': 'timeout'}
    except OSError as exc:
        return {'seconds': time.monotonic() - start, 'status': 'UNAVAILABLE',
                'reason': type(exc).__name__}
    seconds = time.monotonic() - start
    value = {}
    for line in reversed((row.stdout or '').splitlines()):
        try:
            value = json.loads(line)
            break
        except ValueError:
            continue
    reason = value.get('reason') if isinstance(value, dict) else None
    if row.returncode == 0 and value.get('status') == 'ready':
        return {'seconds': seconds, 'status': 'ready', 'reason': reason}
    return {'seconds': seconds, 'status': 'NOT_READY', 'reason': reason or f'exit-{row.returncode}'}


def summarize(runs):
    seconds = sorted(r['seconds'] for r in runs)
    result = {'runs': len(runs), 'minSeconds': seconds[0], 'maxSeconds': seconds[-1],
              'medianSeconds': seconds[len(seconds) // 2],
              'reentryLatencyProven': False}
    if all(r['status'] == 'ready' for r in runs):
        result['status'] = 'MEASURED_REENTRY'
        # End-to-end wall clock only; saving time or first-run cold starts are excluded by the caller.
        result['reentryLatencyProven'] = True
    else:
        result['status'] = next(r['status'] for r in runs if r['status'] != 'ready')
    return result


def measure(command, runs, timeout, pause):
    collected = []
    for index in range(runs):
        row = run_once(command, timeout)
        row['run'] = index + 1
        collected.append(row)
        if index + 1 < runs:
            time.sleep(pause)
    return collected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, default=10)
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--pause', type=float, default=2.0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 3 <= args.runs <= 30 or not 5 <= args.timeout <= 300 or not 0 <= args.pause <= 30:
        parser.error('runs must be 3..30; timeout 5..300; pause 0..30')
    prefix = os.environ.get('PREFIX', '')
    home = os.environ.get('HOME', '')
    if (prefix, home) != ('/data/data/com.termux/files/usr', '/data/data/com.termux/files/home') \
            or os.getuid() <= 0:
        # adb shell or a foreign UID would measure a different trust domain entirely.
        parser.error('run inside the primary-user native Termux shell')
    command = [str(Path(prefix) / 'bin' / 'loopy-omarchy')]
    with args.output.open('x') as output:
        result = {'schema': 1, 'readOnly': True, 'command': 'loopy-omarchy',
                  'runs': measure(command, args.runs, args.timeout, args.pause)}
        result['summary'] = summarize(result['runs'])
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps(result['summary']))
    return 0 if result['summary']['status'] == 'MEASURED_REENTRY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
