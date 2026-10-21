#!/usr/bin/env python3
"""Read-only ADB battery sampling. Never simulates unplugging or changes settings."""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path

POWER = ('AC powered', 'USB powered', 'Wireless powered')
NUMERIC = ('level', 'scale', 'status', 'voltage', 'temperature', 'Charge counter')


def parse_battery(raw):
    fields = {}
    for line in raw.splitlines():
        key, sep, value = line.strip().partition(':')
        if not sep:
            continue
        value = value.strip()
        if key in POWER or key == 'Dock powered':
            if value in ('true', 'false'):
                fields[key] = value == 'true'
        elif key in NUMERIC and re.fullmatch(r'-?\d+', value):
            fields[key] = int(value)
    # Missing power fields must never be interpreted as unplugged.
    fields['updatesStopped'] = 'UPDATES STOPPED' in raw.upper()
    return fields


def summarize(samples):
    result = {'status': 'INSUFFICIENT_DATA', 'samples': len(samples),
              'batterySavingsProven': False}
    if len(samples) < 2:
        return result
    duration = samples[-1]['elapsedSeconds'] - samples[0]['elapsedSeconds']
    result['durationSeconds'] = duration
    temps = [s['battery']['temperature'] / 10 for s in samples
             if 'temperature' in s['battery']]
    if temps:
        result['batteryTemperatureC'] = {'start': temps[0], 'max': max(temps)}
    for sample in samples:
        battery = sample['battery']
        if battery.get('updatesStopped'):
            result['status'] = 'SIMULATED_BATTERY_STATE'
            return result
        if not all(k in battery for k in POWER) or battery.get('status') != 3:
            result['status'] = 'NOT_CONFIRMED_DISCHARGING'
            return result
        if any(battery.get(k, False) for k in (*POWER, 'Dock powered')):
            result['status'] = 'EXTERNAL_POWER'
            return result
    counters = [s['battery'].get('Charge counter') for s in samples]
    if any(c is None or c <= 0 for c in counters):
        result['status'] = 'COUNTER_UNAVAILABLE'
        return result
    if any(b > a for a, b in zip(counters, counters[1:])):
        result['status'] = 'COUNTER_INCREASED'
        return result
    if duration < 600:
        result['status'] = 'TOO_SHORT'
        return result
    used = counters[0] - counters[-1]
    if used == 0:
        result['status'] = 'COUNTER_UNCHANGED'
        return result
    result.update(status='MEASURED_DISCHARGE', consumedMah=used / 1000,
                  averageDischargeMa=used / 1000 * 3600 / duration)
    # One run measures discharge only; a controlled comparison is still required.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--seconds', type=int, default=900)
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 600 <= args.seconds <= 3600 or not 10 <= args.interval <= 60:
        parser.error('seconds must be 600..3600; interval must be 10..60')
    # Exclusive output creation prevents replacement of an earlier receipt.
    with args.output.open('x') as output:
        samples = []
        result = {'schema': 1, 'readOnly': True, 'samples': samples}
        start = time.monotonic()
        try:
            while True:
                raw = subprocess.check_output(
                    ['adb', '-s', args.serial, 'shell', 'dumpsys', 'battery'],
                    timeout=10, text=True)
                elapsed = time.monotonic() - start
                samples.append({'elapsedSeconds': elapsed, 'battery': parse_battery(raw)})
                if elapsed >= args.seconds:
                    break
                time.sleep(min(args.interval, args.seconds - elapsed))
        except (subprocess.SubprocessError, OSError, KeyboardInterrupt) as exc:
            # Do not persist raw subprocess output or device identifiers.
            result['collectionError'] = type(exc).__name__
        result['summary'] = summarize(samples)
        if 'collectionError' in result:
            result['summary']['status'] = 'COLLECTION_INTERRUPTED'
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps(result['summary']))
    return 0 if result['summary']['status'] == 'MEASURED_DISCHARGE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
