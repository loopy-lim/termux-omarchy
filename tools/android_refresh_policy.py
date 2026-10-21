#!/usr/bin/env python3
"""Reversibly release the known 120 Hz Android minimum; does not change Linux cadence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

KEYS = ('min_refresh_rate', 'peak_refresh_rate')


def read_settings(shell, user):
    return {key: shell(['settings', '--user', str(user), 'get', 'system', key]).strip()
            for key in KEYS}


def release_minimum(shell, user, before):
    if read_settings(shell, user) != before:
        raise ValueError('refresh-settings-changed')
    if before['min_refresh_rate'] not in ('120', '120.0') or before['peak_refresh_rate'] not in ('120', '120.0'):
        raise ValueError('expected-previous-120hz-test-settings')
    shell(['settings', '--user', str(user), 'delete', 'system', 'min_refresh_rate'])
    after = read_settings(shell, user)
    if after != {'min_refresh_rate': 'null', 'peak_refresh_rate': before['peak_refresh_rate']}:
        raise ValueError('refresh-change-unconfirmed-use-receipt-to-recover')
    return after


def restore_minimum(shell, user, before):
    current = read_settings(shell, user)
    if current == before:
        return current
    if current != {'min_refresh_rate': 'null', 'peak_refresh_rate': before['peak_refresh_rate']}:
        raise ValueError('refresh-settings-changed-do-not-overwrite')
    shell(['settings', '--user', str(user), 'put', 'system', 'min_refresh_rate', before['min_refresh_rate']])
    if read_settings(shell, user) != before:
        raise ValueError('refresh-restore-unconfirmed')
    return before


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('release-minimum', 'restore'))
    parser.add_argument('--serial', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    def shell(words):
        return subprocess.check_output(['adb', '-s', args.serial, 'shell', *words], text=True, timeout=10)
    user_text = shell(['am', 'get-current-user']).strip()
    if not user_text.isdecimal():
        raise ValueError('android-user-unavailable')
    user = int(user_text)
    device = hashlib.sha256(args.serial.encode()).hexdigest()
    if args.action == 'release-minimum':
        before = read_settings(shell, user)
        if before['min_refresh_rate'] not in ('120', '120.0') or before['peak_refresh_rate'] not in ('120', '120.0'):
            raise ValueError('expected-previous-120hz-test-settings')
        # Persist recovery authority BEFORE the first device write, including on adb timeout.
        record = {'schema': 1, 'deviceHash': device, 'user': user, 'before': before,
                  'purpose': 'release-120hz-test-minimum', 'physicalBatteryBenefitVerified': False}
        fd = os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump(record, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        result = release_minimum(shell, user, before)
    else:
        fd = os.open(args.receipt, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd) as source:
            row = os.fstat(source.fileno())
            if not stat.S_ISREG(row.st_mode) or row.st_uid != os.getuid() or row.st_mode & 0o077 or row.st_size > 4096:
                raise ValueError('private-receipt-required')
            record = json.load(source)
        if record.get('schema') != 1 or record.get('deviceHash') != device or record.get('user') != user \
                or record.get('purpose') != 'release-120hz-test-minimum':
            raise ValueError('receipt-target-mismatch')
        before = record.get('before', {})
        if set(before) != set(KEYS) or any(before[k] not in ('120', '120.0') for k in KEYS):
            raise ValueError('receipt-settings-invalid')
        result = restore_minimum(shell, user, before)
    print(json.dumps({'status': 'SETTINGS_VERIFIED', 'settings': result,
                      'physicalBatteryBenefitVerified': False}))


if __name__ == '__main__':
    main()
