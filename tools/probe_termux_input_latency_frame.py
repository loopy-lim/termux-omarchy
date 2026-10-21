"""Separate native wl_surface.frame collector; original GTK/X11 parser is unchanged."""
import os
from pathlib import Path
import json
import stat
import probe_termux_input_latency_common as base


class Collector(base.Collector):
    def receive(self, row):
        if type(row) is dict and row.get('type') == 'READY':
            base.require(row.get('backend') == 'wayland-frame-callback')
            row = dict(row, backend='wayland-after-paint')
        super().receive(row)

    def result(self):
        result = super().result()
        result.update(backend='wayland-frame-callback', callback_kind='wl_surface.frame-done')
        return result


def collect(path, identity):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        base.require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                     and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600
                     and before.st_size <= 2 * 1024 * 1024)
        obj = Collector(identity)
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            count = 0
            while line := stream.readline(65537):
                count += 1
                base.require(len(line) <= 65536 and line.endswith(b'\n') and count <= 2 * base.LIMIT + 2)
                obj.receive(json.loads(line))
        after, named = os.fstat(fd), Path(path).lstat()
        base.require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                     (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                     and (named.st_dev, named.st_ino, named.st_uid, named.st_mode, named.st_size,
                          named.st_mtime_ns, named.st_nlink) ==
                         (before.st_dev, before.st_ino, before.st_uid, before.st_mode, before.st_size,
                          before.st_mtime_ns, before.st_nlink))
        return obj.result()
    finally:
        os.close(fd)
