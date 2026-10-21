"""Install the GPU-direct fullscreen video launcher entry points in the owned guest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

import omarchy_browser_default_install as route
import omarchy_guest_install as adapters
import omarchy_install as base
import omarchy_proot as guard

JOURNAL = 'video-direct.json'
SUPPORT = {
    'loopy-video-direct': ('usr/local/bin/loopy-video-direct', 0o755,
        '640db255c3f296882ea79f5e344ff5bc8576c9f4219cc90f3fecc7b9da4e1413'),
    'loopy-video-direct.desktop': ('home/omarchy/.local/share/applications/loopy-video-direct.desktop', 0o644,
        'a657796d61dd9d96fa1d4c9267c73b6d090afee633a1dcc37d9f02a632f56b26'),
}
NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC


def require(value, reason='video-direct-boundary'):
    if not value: raise ValueError(reason)


def support_snapshot(rootfs, relative):
    return route.snapshot(rootfs, relative)


def support_source():
    result = {}
    for name, (relative, mode, expected) in SUPPORT.items():
        source = Path(__file__).with_name(name)
        with base.regular(source, 16384) as stream:
            before = base.fingerprint(os.fstat(stream.fileno())); data = stream.read()
            require(hashlib.sha256(data).hexdigest() == expected
                    and base.fingerprint(os.fstat(stream.fileno())) == before
                    and base.fingerprint(source.lstat()) == before, 'video-support-sha')
        result[name] = data
    return result


def entry_points(rootfs):
    found = {}
    for name, (relative, mode, expected) in SUPPORT.items():
        current = support_snapshot(rootfs, relative)
        require(current is not None and current['sha256'] == expected and current['mode'] == mode,
                'video-entry-integrity')
        found[name] = dict(relative=relative, mode=mode, sha256=expected)
    return found


def publish_support(rootfs, name, data):
    relative, mode, expected = SUPPORT[name]
    fd = base.walk(rootfs, str(Path(relative).parent), True)
    temporary = '.video-support-' + uuid.uuid4().hex
    try:
        target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, mode, dir_fd=fd)
        with os.fdopen(target, 'wb') as output:
            output.write(data); output.flush(); os.fchmod(output.fileno(), mode); os.fsync(output.fileno())
        base.publish(fd, temporary, Path(relative).name); os.fsync(fd)
    finally:
        try: os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError: pass
        os.close(fd)
    published = support_snapshot(rootfs, relative)
    require(published is not None and published['sha256'] == hashlib.sha256(data).hexdigest()
            and published['mode'] == mode, 'video-support-publication')
    return published


def installed_base(root, fd, home, prefix, previous=None):
    row = base.read_journal(fd)
    require(isinstance(row, dict) and type(row.get('schema')) is int and row['schema'] == 1
        and row.get('phase') == 'INSTALLED' and type(row.get('uid')) is int and row['uid'] == os.getuid()
        and row.get('root') == base.identity(os.fstat(fd)) and row['root'] == base.identity(root.lstat())
        and row.get('home') == str(home) and row.get('prefix') == str(prefix)
        and row.get('container') == base.CONTAINER and row.get('bundle_sha256') == base.OUTER_SHA,
        'video-base-identity')
    require(previous is None or previous == row, 'video-base-changed')
    base.check_installed(root, prefix, row)
    require(guard.selection(root) is not None, 'video-proot-required')
    return row


def install(home, prefix):
    fd, locks = None, []
    try:
        home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
        root = home / '.local/share/loopy-omarchy'
        rootfs = prefix / 'var/lib/proot-distro/containers' / base.CONTAINER / 'rootfs'
        fd = base.walk(home, '.local/share/loopy-omarchy')
        require(fd is not None and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700)
        before = installed_base(root, fd, home, prefix)
        for name in ('install.lock', 'runtime-control.lock'): locks.append(adapters.lock(fd, name))
        installed_base(root, fd, home, prefix, before)
        binding = dict(schema=1, uid=os.getuid(), root=base.identity(os.fstat(fd)),
            rootfs=before['rootfs_identity'], component='video-direct')
        row = adapters.read_record(fd, JOURNAL)
        support = support_source()
        if row is not None:
            require(isinstance(row, dict) and row.get('phase') == 'INSTALLED'
                and all(row.get(k) == v for k, v in binding.items()), 'video-existing-journal')
            require(row.get('support') == entry_points(rootfs), 'video-entry-changed')
            installed_base(root, fd, home, prefix, before)
            return row  # Valid idempotent check performs no writes.
        require(all(support_snapshot(rootfs, value[0]) is None for value in SUPPORT.values()),
                'video-existing-launcher-preserved')
        row = dict(binding, phase='STAGING', support=None)
        journal_now = dict(row)
        adapters.save_record(fd, row, journal=JOURNAL)
        try:
            row['phase'] = 'UPDATING'
            adapters.save_record(fd, row, journal_now, journal=JOURNAL); journal_now = dict(row)
            published = {name: publish_support(rootfs, name, data) for name, data in support.items()}
            final = dict(row, phase='INSTALLED',
                support={name: dict(relative=SUPPORT[name][0], mode=SUPPORT[name][1], sha256=snap['sha256'])
                         for name, snap in published.items()})
            installed_base(root, fd, home, prefix, before)
            adapters.save_record(fd, final, journal_now, journal=JOURNAL)
            return final
        except BaseException:
            row['phase'] = 'UPDATE_UNKNOWN'
            try: adapters.save_record(fd, row, journal_now, journal=JOURNAL)
            except (ValueError, OSError): pass
            raise ValueError('video-direct-uncertain') from None
    finally:
        for lock in reversed(locks): os.close(lock)
        if fd is not None: os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args(argv)
    try:
        result = install(os.environ['HOME'], os.environ['PREFIX'])
    except (ValueError, OSError, KeyError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[a-z0-9-]{1,64}', str(error)) \
            else 'video-direct-unavailable'
        print(json.dumps(dict(schema=1, status='failed', reason=reason), sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__': sys.exit(main())
