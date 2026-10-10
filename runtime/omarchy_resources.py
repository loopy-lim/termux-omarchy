"""Recorded resources of a fresh owned runtime; cleanup follows process retirement."""
import os
from pathlib import Path
import re
import socket
import stat
import struct
import threading

from processes import identity, same_identity


class ResourceFailure(ValueError):
    pass


def row(path):
    value = Path(path).lstat()
    if value.st_uid != os.getuid():
        raise ResourceFailure('resource-owner')
    return [value.st_dev, value.st_ino, value.st_uid, value.st_mode]


def same_runtime_entry(before, after):
    """tmux toggles owner execute on its socket when a client attaches/detaches."""
    if before == after:
        return True
    return isinstance(before, list) and isinstance(after, list) \
        and len(before) == len(after) == 4 and before[:3] == after[:3] \
        and stat.S_ISSOCK(before[3]) and stat.S_ISSOCK(after[3]) \
        and (before[3] ^ after[3]) == stat.S_IXUSR


def inventory(short, expected_root=None):
    """Snapshot volatile children through pinned, never-followed directory FDs."""
    root = row(short)
    if not stat.S_ISDIR(root[3]) or expected_root is not None and root[:3] != expected_root:
        raise ResourceFailure('runtime-directory-changed')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    root_fd = os.open(short, flags)
    count, size = 0, 0

    def metadata(info):
        if info.st_uid != os.getuid():
            raise ResourceFailure('resource-owner')
        return [info.st_dev, info.st_ino, info.st_uid, info.st_mode]

    def present(chain):
        if row(short)[:3] != root[:3]:
            raise ResourceFailure('runtime-directory-changed')
        for parent, name, expected in chain:
            try:
                current = metadata(os.stat(name, dir_fd=parent, follow_symlinks=False))
            except FileNotFoundError:
                return False
            if current[:3] != expected[:3] or not stat.S_ISDIR(current[3]):
                raise ResourceFailure('runtime-parent-changed')
        return True

    def walk(fd, relative, chain):
        nonlocal count, size
        found = {}
        if len(chain) > 64:
            raise ResourceFailure('resource-bounds')
        if not present(chain):
            return found
        try:
            names = os.listdir(fd)
        except FileNotFoundError:
            if not chain or present(chain):
                raise
            return {}  # A vanished child, never a missing root or a live directory.
        for name in names:
            try:
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                if not present(chain):
                    return {}
                continue  # Only an enumerated child may disappear normally.
            current = metadata(info)
            if not (stat.S_ISDIR(current[3]) or stat.S_ISREG(current[3])
                    or stat.S_ISSOCK(current[3]) or stat.S_ISLNK(current[3])
                    or stat.S_ISFIFO(current[3])):
                raise ResourceFailure('resource-type')
            count += 1
            size += info.st_size  # The same snapshot supplies ownership and size.
            if count > 4096 or size > 64 * 1024 * 1024:
                raise ResourceFailure('resource-bounds')
            child = name if not relative else relative + '/' + name
            if not stat.S_ISDIR(current[3]):
                found[child] = current
                continue
            try:
                child_fd = os.open(name, flags, dir_fd=fd)
            except FileNotFoundError:
                if not present(chain):
                    return {}
                continue
            try:
                opened = metadata(os.fstat(child_fd))
                if opened[:3] != current[:3] or not stat.S_ISDIR(opened[3]):
                    raise ResourceFailure('runtime-parent-changed')
                child_chain = chain + [(fd, name, current)]
                descendants = walk(child_fd, child, child_chain)
                if present(child_chain):
                    found[child] = current
                    found.update(descendants)
            finally:
                os.close(child_fd)
        return found if present(chain) else {}

    try:
        if metadata(os.fstat(root_fd))[:3] != root[:3]:
            raise ResourceFailure('runtime-directory-changed')
        return walk(root_fd, '', [])
    finally:
        os.close(root_fd)


def location(short, prefix, display, name):
    if name.startswith('runtime:'):
        relative = name[8:]
        if not relative or relative.startswith('/') or any(p in ('', '.', '..') for p in relative.split('/')):
            raise ResourceFailure('resource-path')
        return Path(short) / relative
    if not re.fullmatch(r':[2-9][0-9]', display):
        raise ResourceFailure('resource-display')
    if name == 'x-lock':
        return Path(prefix) / f'tmp/.X{display[1:]}-lock'
    if name == 'x-socket':
        return Path(prefix) / f'tmp/.X11-unix/X{display[1:]}'
    raise ResourceFailure('resource-name')


def x_family(records, pid):
    family = {r['pid']: r for r in records if r['pid'] == pid}
    while True:
        added = [r for r in records if r['pid'] not in family and r.get('ppid') in family]
        if not added:
            return list(family.values())
        family.update((r['pid'], r) for r in added)


def lock_pid(path, expected_pid):
    before = row(path)
    if not stat.S_ISREG(before[3]):
        raise ResourceFailure('x-lock-type')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        current = os.fstat(fd)
        if [current.st_dev, current.st_ino, current.st_uid, current.st_mode] != before or current.st_size > 32:
            raise ResourceFailure('x-lock-changed')
        content = os.read(fd, 33).strip()
        if not 1 <= len(content) <= 12 or not content.isdigit() or int(content) != expected_pid:
            raise ResourceFailure('x-lock-pid')
    finally:
        os.close(fd)
    if row(path) != before:
        raise ResourceFailure('x-lock-changed')


def authenticated_yazi_rebind(short, relative, before, after, records):
    """Yazi recreates its DDS listener; only a live owned session peer can replace it."""
    if not records or not re.fullmatch(r'yazi\+[0-9]{1,10}/\.dds\.sock', relative) \
            or not isinstance(before, list) or len(before) != 4 \
            or before[0] != after[0] or before[1] == after[1] \
            or before[2:] != after[2:] or not stat.S_ISSOCK(before[3]):
        return False
    path = Path(short) / relative
    peer = live_peer(path, records)
    return bool(peer and row(path) == after)


def fixed_quickshell_index_rebind(short, relative, before, after, directories):
    """Permit only the immutable index into a recorded private shell directory.

    This index is recreated by short-lived qs IPC clients as well as the shell.
    Their lifetime is not the index lifetime. The literal target and the owned
    directory inode are the authority; cleanup only removes the link itself.
    """
    match = re.fullmatch(r'quickshell/by-path/([a-f0-9]{32})', relative)
    if not match or not isinstance(before, list) or len(before) != 4 \
            or before[0] != after[0] or before[1] == after[1] or before[2:] != after[2:] \
            or not stat.S_ISLNK(before[3]):
        return False
    target = 'quickshell/by-shell/' + match[1]
    # Guest absolute links cannot be resolved in the native namespace. Check
    # the literal selector and the already recorded native directory instead.
    path = Path(short) / relative
    directory = row(Path(short) / target)
    if not stat.S_ISDIR(directory[3]) or os.readlink(path) != '/run/user/1000/' + target \
            or directories.get(target) != directory[:3]:
        return False
    return row(path) == after and row(Path(short) / target) == directory


def capture(short, prefix, value, x_records, *, runtime_records=()):
    if row(short)[:3] != value['runtime']:
        raise ResourceFailure('runtime-directory-changed')
    found = inventory(short, value['runtime'])
    regulars = {relative: current for relative, current in found.items()
                if stat.S_ISREG(current[3]) and relative != 'owner.json'}
    fifos = {relative: current for relative, current in found.items() if stat.S_ISFIFO(current[3])}
    if len(regulars) > 256:
        raise ResourceFailure('regular-resource-count')
    if len(regulars) + len(fifos) > 256:
        raise ResourceFailure('fifo-resource-count')
    value['regularResources'] = regulars  # Metadata only; each successful capture refreshes the bounded ledger.
    value['fifoResources'] = fifos  # Never open FIFO streams; temp FIFOs may disappear or be recreated.
    resources = value.setdefault('resources', {})
    directories = value.setdefault('directories', {'.': row(short)[:3]})
    for relative, current in found.items():
        if stat.S_ISDIR(current[3]):
            if relative in directories and directories[relative] != current[:3]:
                raise ResourceFailure('runtime-parent-changed')
            directories[relative] = current[:3]
        elif stat.S_ISSOCK(current[3]) or stat.S_ISLNK(current[3]):
            name = 'runtime:' + relative
            if name in resources and not same_runtime_entry(resources[name], current) \
                    and not authenticated_yazi_rebind(short, relative, resources[name], current,
                                                     runtime_records) \
                    and not fixed_quickshell_index_rebind(short, relative, resources[name], current, directories):
                raise ResourceFailure('resource-replaced')
            resources[name] = current
    if len(resources) > 256:
        raise ResourceFailure('resource-count')
    x_socket = location(short, prefix, value['display'], 'x-socket')
    if not os.path.lexists(x_socket):
        return
    if not x_records:
        raise ResourceFailure('x-peer-unowned')
    verified = {'x-socket': row(x_socket)}
    peer = live_peer(x_socket, x_records)
    if not peer:
        return  # The new Xserver may have bound but not yet begun accepting.
    if row(x_socket) != verified['x-socket']:
        raise ResourceFailure('x-resource-changed-after-authentication')
    x_lock = location(short, prefix, value['display'], 'x-lock')
    if os.path.lexists(x_lock):
        verified['x-lock'] = row(x_lock)
        lock_pid(x_lock, peer['pid'])
        if row(x_lock) != verified['x-lock']:
            raise ResourceFailure('x-resource-changed-after-authentication')
    for name in ('x-lock', 'x-socket'):
        path = location(short, prefix, value['display'], name)
        if os.path.lexists(path):
            for relative in ('tmp', 'tmp/.X11-unix'):
                parent = Path(prefix) / relative
                if os.path.lexists(parent):
                    current_parent = row(parent)
                    previous = value.setdefault('x_directories', {}).get(relative)
                    if not stat.S_ISDIR(current_parent[3]) or previous and previous != current_parent[:3]:
                        raise ResourceFailure('x-parent-changed')
                    value['x_directories'][relative] = current_parent[:3]
            current = row(path)
            if current != verified.get(name):
                raise ResourceFailure('x-resource-changed-after-authentication')
            if not (stat.S_ISSOCK(current[3]) if name == 'x-socket' else stat.S_ISREG(current[3])):
                raise ResourceFailure('x-resource-type')
            if name in resources and resources[name] != current:
                raise ResourceFailure('resource-replaced')
            resources[name] = current
    if len(resources) > 256:
        raise ResourceFailure('resource-count')


def parents(short, prefix, value, path):
    path = Path(path)
    if path.is_relative_to(short):
        parent = path.parent
        while parent != Path(short).parent:
            relative = str(parent.relative_to(short))
            if os.path.lexists(parent) and row(parent)[:3] != value.get('directories', {}).get(relative):
                raise ResourceFailure('runtime-parent-changed')
            parent = parent.parent
    else:
        for relative in ('tmp', 'tmp/.X11-unix'):
            parent = Path(prefix) / relative
            if os.path.lexists(parent) and row(parent)[:3] != value.get('x_directories', {}).get(relative):
                raise ResourceFailure('x-parent-changed')


def live_peer(path, records):
    if not os.path.lexists(path):
        return False
    before = row(path)
    if not stat.S_ISSOCK(before[3]):
        raise ResourceFailure('socket-type')
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(.5)
            client.connect(str(path))
            pid, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            record = next((r for r in records if r['pid'] == pid), None)
            if uid != os.getuid() or record is None or not same_identity(record, identity(pid, strict=True)):
                raise ResourceFailure('socket-peer-ownership')
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout):
        return False
    if row(path) != before or not same_identity(record, identity(pid, strict=True)):
        raise ResourceFailure('socket-peer-changed')
    return record


def cleanup(short, prefix, value):
    """Caller proves owned ECHILD or different boot plus exact inode witnesses."""
    if row(short)[:3] != value['runtime']:
        raise ResourceFailure('runtime-directory-changed')
    found = inventory(short, value['runtime'])
    resources, directories = value.get('resources', {}), value.get('directories', {})
    fifo_ledger = value.get('fifoResources', {})
    if value.get('_bootRegularWitness') is True and (not isinstance(fifo_ledger, dict) or len(fifo_ledger) > 256):
        raise ResourceFailure('boot-fifo-ledger')
    for relative, current in found.items():
        if value.get('_bootRegularWitness') is True and stat.S_ISREG(current[3]) \
                and relative != 'owner.json' and value.get('regularResources', {}).get(relative) != current:
            raise ResourceFailure('boot-regular-changed')
        if value.get('_bootRegularWitness') is True and stat.S_ISFIFO(current[3]) \
                and fifo_ledger.get(relative) != current:
            raise ResourceFailure('boot-fifo-changed')
        if stat.S_ISDIR(current[3]) and directories.get(relative) != current[:3]:
            raise ResourceFailure('runtime-parent-unrecorded')
        if (stat.S_ISSOCK(current[3]) or stat.S_ISLNK(current[3])) \
                and not same_runtime_entry(resources.get('runtime:' + relative), current):
            raise ResourceFailure('runtime-entry-unrecorded')
    # Validate the complete removal set before deleting any owned entry.
    paths = {location(short, prefix, value['display'], name): expected
             for name, expected in resources.items()}
    def matches(path, expected):
        current = row(path)
        return same_runtime_entry(expected, current) if path.is_relative_to(short) else current == expected
    for path, expected in paths.items():
        parents(short, prefix, value, path)
        if os.path.lexists(path) and not matches(path, expected):
            raise ResourceFailure('resource-replaced')
    for path, expected in paths.items():
        if os.path.lexists(path):
            parents(short, prefix, value, path)
            if row(short)[:3] != value['runtime'] or not matches(path, expected):
                raise ResourceFailure('resource-replaced')
            path.unlink()
    for relative, expected in reversed(list(found.items())):
        if relative == 'owner.json' or stat.S_ISSOCK(expected[3]) or stat.S_ISLNK(expected[3]):
            continue
        path = Path(short) / relative
        parents(short, prefix, value, path)
        if row(short)[:3] != value['runtime'] or row(path) != expected:
            raise ResourceFailure('runtime-entry-changed')
        path.rmdir() if stat.S_ISDIR(expected[3]) else path.unlink()
    if {p.name for p in Path(short).iterdir()} != {'owner.json'}:
        raise ResourceFailure('runtime-not-empty')
    for name in ('x-lock', 'x-socket'):
        if os.path.lexists(location(short, prefix, value['display'], name)):
            raise ResourceFailure('x-resource-remains')


class StartupLog:
    """Keep only the first 1MiB of own startup stdout; continue draining thereafter."""
    def __init__(self, path):
        self.output = os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), 'wb')
        self.thread, self.ok, self.stream = None, True, None

    def attach(self, stream):
        self.stream = stream
        thread = threading.Thread(target=self.drain, daemon=True)
        thread.start()
        self.thread = thread

    def drain(self):
        saved = 0
        try:
            while True:
                part = os.read(self.stream.fileno(), 4096)
                if not part:
                    break
                take = min(len(part), max(0, 1024 * 1024 - saved))
                if take:
                    self.output.write(part[:take]); self.output.flush()
                    saved += take
        except OSError:
            self.ok = False
        finally:
            self.stream.close(); self.output.close()

    def finish(self):
        if self.thread is None:
            self.output.close()
            if self.stream is not None:
                self.stream.close()
            return
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            raise ResourceFailure('startup-log-drain-unconfirmed')
        return self.ok
