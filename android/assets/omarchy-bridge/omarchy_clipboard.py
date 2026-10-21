"""Session-owned Android UTF-8 records and an in-process Wayland clipboard.

The existing action worker watches Android records and compositor/transfer
file descriptors. Clipboard changes never create a child process.
"""
import os
from pathlib import Path
import re
import stat

LIMIT = 65536


def checked(data):
    if len(data) > LIMIT or b'\0' in data:
        raise ValueError('Unsupported clipboard record')
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError('Unsupported clipboard encoding') from None
    return data


class Records:
    def __init__(self, directory, token):
        if type(token) is not str or not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', token):
            raise ValueError('Current clipboard session required')
        self.fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        if os.fstat(self.fd).st_uid != os.getuid():
            self.close(); raise ValueError('Owned clipboard directory required')
        self.android, self.guest = 'clip-android-' + token, 'clip-guest-' + token

    def read_android(self):
        try:
            fd = os.open(self.android, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=self.fd)
        except FileNotFoundError:
            return None, None
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > LIMIT:
                raise ValueError('Bounded owned clipboard file required')
            data = checked(source.read(LIMIT + 1))
        return data, (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size)

    def guest_exists(self):
        try:
            info = os.stat(self.guest, dir_fd=self.fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Existing clipboard record is not owned regular data')
        return True

    def publish_guest(self, data):
        checked(data); self.guest_exists()
        name = '.clipboard-' + os.urandom(16).hex()
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.fd)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(data); output.flush(); os.fsync(output.fileno())
            os.rename(name, self.guest, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        finally:
            try: os.unlink(name, dir_fd=self.fd)
            except FileNotFoundError: pass

    def export(self, state, data):
        if state == 'sensitive' or (state == 'nil' and not self.guest_exists()):
            return
        if state in ('nil', 'clear'): data = b''
        self.publish_guest(data)

    def close(self):
        if self.fd is not None:
            os.close(self.fd); self.fd = None


class Relay:
    def __init__(self, directory, token):
        import loopy_input
        from wayland_clipboard import Client
        self.records, self.client, self.previous_revision = Records(directory, token), None, None
        try:
            self.client = Client(loopy_input._socket_path(), self.records.export)
        except BaseException:
            self.close(); raise

    @property
    def readers(self):
        return self.client.readers

    @property
    def writers(self):
        return self.client.writers

    def poll(self):
        self.client.pump()
        data, revision = self.records.read_android()
        if data is not None and revision != self.previous_revision and self.client.set_selection(data):
            self.previous_revision = revision

    def close(self):
        if self.client is not None:
            self.client.close(); self.client = None
        self.records.close()
