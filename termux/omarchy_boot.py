"""Recover only inode-pinned resources of a provably earlier kernel boot.

This is not a process reaper. Same-boot supervisor loss remains refused; a
different authenticated kernel boot proves old kernel processes cannot survive.
No signal, service configuration, guest command, or container removal is used.
"""
import os
from pathlib import Path
import stat
import uuid

from processes import identity, same_identity
from omarchy_resources import ResourceFailure, inventory, location

BOOT_ID = Path('/proc/sys/kernel/random/boot_id')


class BootFailure(ResourceFailure):
    pass


def canonical(value):
    try:
        if not isinstance(value, str) or len(value) != 36 or str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError, TypeError):
        raise BootFailure('boot-id-invalid') from None
    return value


def current_boot_id(path=BOOT_ID):
    descriptor = None
    try:
        before = Path(path).lstat()
        if not stat.S_ISREG(before.st_mode):
            raise BootFailure('boot-id-invalid')
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        opened = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_mode) != \
                (opened.st_dev, opened.st_ino, opened.st_mode):
            raise BootFailure('boot-id-changed')
        raw = os.read(descriptor, 65)
        text = raw.decode('ascii')
        value = canonical(text[:-1] if text.endswith('\n') else text)
        after = Path(path).lstat()
        if (before.st_dev, before.st_ino, before.st_mode) != \
                (after.st_dev, after.st_ino, after.st_mode):
            raise BootFailure('boot-id-changed')
        return value
    except BootFailure:
        raise
    except (OSError, UnicodeError):
        raise BootFailure('boot-id-unavailable') from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def process_collision(value):
    records = [*value.get('processes', [])]
    if value.get('hyprland') is not None:
        records.append(value['hyprland'])
    for record in records:
        if not isinstance(record, dict) or type(record.get('pid')) is not int or record['pid'] < 2 \
                or record.get('uid') != os.getuid():
            raise BootFailure('boot-process-invalid')
        try:
            current = identity(record['pid'], strict=True)
        except (OSError, ValueError):
            raise BootFailure('boot-process-unverified') from None
        if current is not None and same_identity(record, current):
            raise BootFailure('boot-process-collision')


def regular_witness(runtime, value):
    ledger = value.get('regularResources', {})
    if not isinstance(ledger, dict) or len(ledger) > 256:
        raise BootFailure('boot-regular-ledger')
    for relative, expected in ledger.items():
        if relative == 'owner.json' or not isinstance(relative, str) \
                or not isinstance(expected, list) or len(expected) != 4 \
                or any(type(item) is not int or item < 0 for item in expected) \
                or expected[1] == 0 or expected[2] != os.getuid() or not stat.S_ISREG(expected[3]):
            raise BootFailure('boot-regular-ledger')
        location(runtime.short, runtime.prefix, value['display'], 'runtime:' + relative)
    found = inventory(runtime.short)
    for relative, current in found.items():
        if stat.S_ISREG(current[3]) and relative != 'owner.json' and ledger.get(relative) != current:
            raise BootFailure('boot-regular-unrecorded')


def prepare_start(runtime, boot_path=BOOT_ID):
    current = current_boot_id(boot_path)
    previous = runtime.state()  # Exact root/session/runtime inode and owner marker, never adoption.
    if previous is None:
        return current
    legacy = 'bootId' not in previous
    if legacy:
        if previous.get('phase') != 'stopped' or previous.get('terminationConfirmed') is not True:
            raise BootFailure('boot-legacy-cleanup-unconfirmed')
    else:
        old = canonical(previous['bootId'])
        if old == current:
            return current  # Existing start/stop code retains same-boot lost-anchor refusal.
    runtime.installed()
    process_collision(previous)
    regular_witness(runtime, previous)
    if runtime.state() != previous or current_boot_id(boot_path) != current:
        raise BootFailure('boot-witness-changed')
    # The existing cleanup validates the complete socket/link/parent removal set
    # before mutation. Different boot substitutes only for old-process ECHILD;
    # regular files have the additional exact ledger preflight above.
    runtime.clear_runtime(dict(previous, _bootRegularWitness=True))
    if runtime.state() != previous or current_boot_id(boot_path) != current:
        raise BootFailure('boot-witness-changed')
    # Match supervise cleanup: empty processes with leftover peer stamps make
    # Runtime.state() refuse android/audio identity and block every later start.
    runtime.publish(dict(previous, phase='stopped', terminationConfirmed=True,
                         processes=[], hyprland=None, audioProcess=None, androidProcess=None,
                         bootId=current,
                         terminationEvidence='legacy-clean-stop' if legacy else 'previous-boot'))
    return current
