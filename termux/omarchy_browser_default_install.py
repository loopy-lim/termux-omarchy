"""Route guest web opens to the GPU-direct native browser, with exact rollback."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import uuid

import omarchy_guest_install as adapters
import omarchy_install as base
import omarchy_proot as guard

JOURNAL = 'browser-default.json'
# Reviewed entry points must already exist in the guest; this component only routes to them.
ENTRY_POINTS = {
    'loopy-native-browser': ('usr/local/bin/loopy-native-browser', 0o755,
        '4c8fcfe16f836735168064d99dafa4a8acdc01092231a4d04cdc7329b0c8f189'),
    'loopy-native-browser.desktop': ('home/omarchy/.local/share/applications/loopy-native-browser.desktop', 0o644,
        '752e35e941927262558d38a055fc26b3a743d9d7076393e8109184d70f6d5501'),
}
RELATIVE_MIMEAPPS = 'home/omarchy/.config/mimeapps.list'
DEFAULT_KEYS = ('x-scheme-handler/http', 'x-scheme-handler/https', 'text/html')
ENTRY = 'loopy-native-browser.desktop'
SECTION = 'Default Applications'
NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC


def require(value, reason='browser-default-boundary'):
    if not value: raise ValueError(reason)


def render(previous):
    """Set the three default keys to the native entry, preserving every other line."""
    text = previous.decode('utf-8') if previous is not None else ''
    if '\x00' in text: raise ValueError('browser-mimeapps-binary')
    lines = text.splitlines(keepends=True)
    # Guest xdg tools or the user may write the file without a trailing newline;
    # append would otherwise glue new keys onto the last line (CRLF lines are
    # preserved verbatim; only lines this component writes use LF).
    if lines and not lines[-1].endswith('\n'):
        lines[-1] += '\n'
    counts, section = {}, None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'): continue
        heading = re.fullmatch(r'\[([^\]]+)\]', stripped)
        if heading: section = heading.group(1); continue
        key, sep, _ = stripped.partition('=')
        if not sep or section is None: raise ValueError('browser-mimeapps-line')
        if section == SECTION:
            key = key.strip()
            counts[key] = counts.get(key, 0) + 1
    if any(counts.get(key, 0) > 1 for key in DEFAULT_KEYS): raise ValueError('browser-mimeapps-ambiguous')
    out, state, done = [], {'section': None, 'seen': False}, set()
    def flush():
        if state['section'] == SECTION:
            out.extend(f'{key}={ENTRY}\n' for key in DEFAULT_KEYS if key not in done)
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            heading = re.fullmatch(r'\[([^\]]+)\]', stripped)
            if heading:
                flush()
                state['section'] = heading.group(1)
                if state['section'] == SECTION: state['seen'] = True
                out.append(line)
                continue
            key, sep, _ = stripped.partition('=')
            if state['section'] == SECTION and sep and key.strip() in DEFAULT_KEYS:
                key = key.strip()
                out.append(f'{key}={ENTRY}\n')
                done.add(key)
                continue
        out.append(line)
    flush()
    if not state['seen']:
        out.append(f'[{SECTION}]\n')
        out.extend(f'{key}={ENTRY}\n' for key in DEFAULT_KEYS)
    return ''.join(out).encode()


def snapshot(rootfs, relative):
    path = PurePosixPath(relative)
    fd = base.walk(rootfs, str(path.parent))
    if fd is None: return None
    try:
        try:
            with base.regular(path.name, 16384, fd) as source:
                before = base.fingerprint(os.fstat(source.fileno()))
                data = source.read()
                return dict(identity=before[:3], mode=stat.S_IMODE(before[3]),
                            sha256=hashlib.sha256(data).hexdigest(), data=data)
        except FileNotFoundError:
            return None
    finally: os.close(fd)


def entry_points(rootfs):
    found = {}
    for name, (relative, mode, expected) in ENTRY_POINTS.items():
        current = snapshot(rootfs, relative)
        require(current is not None and current['sha256'] == expected and current['mode'] == mode,
                'browser-entry-integrity')
        found[name] = dict(relative=relative, mode=mode, sha256=expected)
    return found


def publish(rootfs, relative, data, mode, replacing):
    path = PurePosixPath(relative)
    fd = base.walk(rootfs, str(path.parent), True)
    temporary = '.publish-' + uuid.uuid4().hex
    try:
        target = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, mode, dir_fd=fd)
        with os.fdopen(target, 'wb') as output:
            output.write(data); output.flush(); os.fchmod(output.fileno(), mode); os.fsync(output.fileno())
        if replacing:
            os.replace(temporary, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        else:
            base.publish(fd, temporary, path.name)
        os.fsync(fd)
    finally:
        try: os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError: pass
        os.close(fd)
    published = snapshot(rootfs, RELATIVE_MIMEAPPS)
    require(published is not None and published['sha256'] == hashlib.sha256(data).hexdigest()
            and published['mode'] == mode, 'browser-default-publication')
    return published


def installed_base(root, fd, home, prefix, previous=None):
    row = base.read_journal(fd)
    require(isinstance(row, dict) and type(row.get('schema')) is int and row['schema'] == 1
        and row.get('phase') == 'INSTALLED' and type(row.get('uid')) is int and row['uid'] == os.getuid()
        and row.get('root') == base.identity(os.fstat(fd)) and row['root'] == base.identity(root.lstat())
        and row.get('home') == str(home) and row.get('prefix') == str(prefix)
        and row.get('container') == base.CONTAINER and row.get('bundle_sha256') == base.OUTER_SHA,
        'browser-base-identity')
    require(previous is None or previous == row, 'browser-base-changed')
    base.check_installed(root, prefix, row)
    require(guard.selection(root) is not None, 'browser-proot-required')
    return row


def backup_previous(fd, row, current):
    os.mkdir(row['backupDirectory'], 0o700, dir_fd=fd)
    child = os.open(row['backupDirectory'], os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=fd)
    try:
        row['backupIdentity'] = base.identity(os.fstat(child))
        if current is not None:
            target = os.open('mimeapps.list', os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600, dir_fd=child)
            with os.fdopen(target, 'wb') as output:
                output.write(current['data']); output.flush(); os.fsync(output.fileno())
    finally: os.close(child)
    os.fsync(fd)


def backup_bytes(fd, row):
    child = os.open(row['backupDirectory'], os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW, dir_fd=fd)
    try:
        if row.get('previous') is None: return None
        with base.regular('mimeapps.list', 16384, child) as source:
            before = base.fingerprint(os.fstat(source.fileno()))
            data = source.read()
        require(base.fingerprint(os.stat('mimeapps.list', dir_fd=child, follow_symlinks=False)) == before
                and stat.S_IMODE(before[3]) == 0o600, 'browser-backup-integrity')
        return data
    finally: os.close(child)


def prepare(home, prefix):
    home, prefix = Path(home).resolve(strict=True), Path(prefix).resolve(strict=True)
    root = home / '.local/share/loopy-omarchy'
    rootfs = prefix / 'var/lib/proot-distro/containers' / base.CONTAINER / 'rootfs'
    fd = base.walk(home, '.local/share/loopy-omarchy')
    require(fd is not None and stat.S_IMODE(os.fstat(fd).st_mode) == 0o700)
    return home, prefix, root, rootfs, fd


def install(home, prefix):
    fd, locks = None, []
    try:
        home, prefix, root, rootfs, fd = prepare(home, prefix)
        before = installed_base(root, fd, home, prefix)
        for name in ('install.lock', 'runtime-control.lock'): locks.append(adapters.lock(fd, name))
        installed_base(root, fd, home, prefix, before)
        binding = dict(schema=1, uid=os.getuid(), root=base.identity(os.fstat(fd)),
            rootfs=before['rootfs_identity'], entry=ENTRY, keys=list(DEFAULT_KEYS))
        row = adapters.read_record(fd, JOURNAL)
        entries = entry_points(rootfs)
        current = snapshot(rootfs, RELATIVE_MIMEAPPS)
        wanted = render(None if current is None else current['data'])  # Inspect before any journal write.
        if row is not None and not (isinstance(row, dict) and row.get('phase') == 'RESTORED'
                                    and all(row.get(k) == v for k, v in binding.items())):
            # A restored journal may be re-applied; any other existing journal is terminal evidence.
            require(isinstance(row, dict) and row.get('phase') == 'INSTALLED'
                and all(row.get(k) == v for k, v in binding.items()), 'browser-existing-journal')
            require(row.get('entryPoints') == entries, 'browser-entry-changed')
            require(current is not None and current['sha256'] == row['after']['sha256'], 'browser-default-changed')
            installed_base(root, fd, home, prefix, before)
            return row  # Valid idempotent check performs no writes.
        reapplied = row if isinstance(row, dict) and row.get('phase') == 'RESTORED' else None
        row = dict(binding, phase='BACKUP',
            previous=None if current is None else dict(mode=current['mode'], sha256=current['sha256']),
            backupDirectory='.browser-default-' + uuid.uuid4().hex)
        journal_now = dict(row)
        adapters.save_record(fd, row, reapplied, journal=JOURNAL)
        try:
            backup_previous(fd, row, current)
            row['phase'] = 'UPDATING'
            adapters.save_record(fd, row, journal_now, journal=JOURNAL); journal_now = dict(row)
            require(snapshot(rootfs, RELATIVE_MIMEAPPS) == current, 'browser-mimeapps-concurrent-change')
            published = publish(rootfs, RELATIVE_MIMEAPPS, wanted, 0o600 if current is None else current['mode'],
                                replacing=current is not None)
            final = dict(row, phase='INSTALLED', entryPoints=entries,
                after=dict(identity=published['identity'], mode=published['mode'], sha256=published['sha256']))
            installed_base(root, fd, home, prefix, before)
            adapters.save_record(fd, final, journal_now, journal=JOURNAL)
            return final
        except BaseException:
            row['phase'] = 'UPDATE_UNKNOWN'
            try: adapters.save_record(fd, row, journal_now, journal=JOURNAL)
            except (ValueError, OSError): pass
            raise ValueError('browser-default-uncertain') from None
    finally:
        for lock in reversed(locks): os.close(lock)
        if fd is not None: os.close(fd)


def restore(home, prefix):
    fd, locks = None, []
    try:
        home, prefix, root, rootfs, fd = prepare(home, prefix)
        before = installed_base(root, fd, home, prefix)
        for name in ('install.lock', 'runtime-control.lock'): locks.append(adapters.lock(fd, name))
        installed_base(root, fd, home, prefix, before)
        row = adapters.read_record(fd, JOURNAL)
        require(isinstance(row, dict) and row.get('phase') == 'INSTALLED'
                and row.get('entry') == ENTRY, 'browser-restore-journal')
        current = snapshot(rootfs, RELATIVE_MIMEAPPS)
        require(current is not None and current['sha256'] == row['after']['sha256'], 'browser-restore-current')
        previous_bytes = backup_bytes(fd, row)
        if previous_bytes is None:
            path = PurePosixPath(RELATIVE_MIMEAPPS)
            parent = base.walk(rootfs, str(path.parent))
            require(parent is not None, 'browser-restore-parent')
            try:
                try: os.unlink(path.name, dir_fd=parent)
                except FileNotFoundError: raise ValueError('browser-restore-current') from None
                os.fsync(parent)
            finally: os.close(parent)
        else:
            require(hashlib.sha256(previous_bytes).hexdigest() == row['previous']['sha256'], 'browser-backup-integrity')
            publish(rootfs, RELATIVE_MIMEAPPS, previous_bytes, row['previous']['mode'], replacing=True)
        final = dict(row, phase='RESTORED')
        adapters.save_record(fd, final, row, journal=JOURNAL)
        return final
    finally:
        for lock in reversed(locks): os.close(lock)
        if fd is not None: os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true', help='Restore the journaled previous mimeapps.list')
    args = parser.parse_args(argv)
    try:
        action = restore(os.environ['HOME'], os.environ['PREFIX']) if args.restore \
            else install(os.environ['HOME'], os.environ['PREFIX'])
    except (ValueError, OSError, KeyError) as error:
        reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[a-z0-9-]{1,64}', str(error)) \
            else 'browser-default-unavailable'
        print(json.dumps(dict(schema=1, status='failed', reason=reason), sort_keys=True))
        return 1
    print(json.dumps(action, sort_keys=True))
    return 0


if __name__ == '__main__': sys.exit(main())
