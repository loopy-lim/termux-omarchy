"""Add signed Korean input packages and guarded session configuration."""
import argparse
import json
import os
from pathlib import Path
import re
import stat

import omarchy_install as base
import omarchy_guest_install as guest
import omarchy_tools_install as packages

COMPONENT = guest.Component(
    '9f26836651238aa8cebae609c9b9b8774b367ad07b817ebbd054466b5db35e92', 10240,
    '3281b825782d4291ca2fe4ef14d7e72c15d2906c171c9847edfbe3e6c6eb2fcd', 1035,
    'guest-korean-input-config', 'input-config-install.json', (
        ('home/omarchy/.config/hypr/autostart.lua', 0o644),
    ))


def validate(directory, payload, manifest):
    packages.validate(directory, korean_input=True)
    return guest.Payload(payload, manifest, component=COMPONENT)


def preflight_targets(source, home, prefix):
    """Refuse user config changes and an active session before package staging."""
    home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
    root = home / '.local/share/loopy-omarchy'
    rootfs = prefix / 'var/lib/proot-distro/containers' / base.CONTAINER / 'rootfs'
    fd, locks = None, []
    try:
        fd = base.walk(home, '.local/share/loopy-omarchy')
        base.require(fd is not None and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700)
        locks.append(guest.lock(fd, 'install.lock'))
        locks.append(guest.lock(fd, 'runtime-control.lock'))
        installed = base.read_journal(fd)
        base.require(installed.get('schema') == 1 and installed.get('phase') == 'INSTALLED'
            and installed.get('uid') == os.getuid() and installed.get('root') == base.identity(os.fstat(fd))
            and installed.get('home') == str(home) and installed.get('prefix') == str(prefix)
            and installed.get('container') == base.CONTAINER and installed.get('bundle_sha256') == base.OUTER_SHA)
        base.check_installed(root, prefix, installed)
        changes = guest.plan(rootfs, source.files, source.original_modes)
        previous = guest.read_record(fd, COMPONENT.journal)
        if previous is not None:
            binding = {'schema': 1, 'uid': os.getuid(), 'root': base.identity(os.fstat(fd)),
                       'rootfs': installed['rootfs_identity'], 'payloadSHA256': COMPONENT.payload_sha,
                       'manifestSHA256': COMPONENT.manifest_sha, 'filesVerified': len(source.files)}
            base.require(all(previous.get(k) == v for k, v in binding.items()), 'guest-journal-identity')
            base.require(previous.get('phase') == 'INSTALLED', 'guest-install-uncertain')
            base.require(not changes, 'guest-installed-target-changed')
        if changes:
            try:
                with base.regular('runtime-state.json', 16384, fd) as stream: state = json.loads(stream.read())
                base.require(state.get('phase') == 'stopped' and state.get('terminationConfirmed') is True,
                             'guest-runtime-active')
            except FileNotFoundError:
                pass
    finally:
        for lock in reversed(locks): os.close(lock)
        if fd is not None: os.close(fd)


def install(directory, payload, manifest, home, prefix):
    source = validate(directory, payload, manifest)
    preflight_targets(source, home, prefix)
    # Each component rechecks its targets under both locks and retains its own
    # transaction journal. A failure never marks the combined input as verified.
    added = packages.install(directory, home, prefix, korean_input=True)
    config = guest.install(payload, manifest, home, prefix, component=COMPONENT)
    return {'schema': 1, 'status': 'installed-input-components', 'packages': added, 'config': config,
            'physicalKoreanInputVerified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install pinned Omarchy Korean input components')
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = install(args.directory, args.payload, args.manifest, os.environ['HOME'], os.environ['PREFIX'])
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[a-z0-9-]{1,64}', str(error)) else 'input-install-unavailable'
        print(json.dumps({'schema': 1, 'status': 'failed', 'reason': reason,
                          'physicalKoreanInputVerified': False}, sort_keys=True))
        return 1


if __name__ == '__main__': raise SystemExit(main())
