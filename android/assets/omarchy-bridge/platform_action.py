"""Typed requests to the Android Activity that owns this Linux session."""
import os
import re
import base64
import stat
import sys
from urllib.parse import urlsplit


def request(directory, token, action, payload=None):
    if action not in {'wifi', 'launch', 'web', 'inside-backend'} or not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,64}', token):
        raise ValueError('Current session and supported Android action required')
    directory = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    temporary = 'request-' + token + '.' + os.urandom(8).hex() + '.new'
    try:
        if os.fstat(directory).st_uid != os.getuid():
            raise ValueError('Owned Android request directory required')
        text = action
        if action in {'launch', 'inside-backend'}:
            if action == 'launch' and (not isinstance(payload, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,1400}', payload)):
                raise ValueError('Encoded Android component required')
            if action == 'inside-backend' and payload is not None:
                raise ValueError('Unexpected Android action argument')
            component = None
            if action == 'launch':
                component = base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)).decode('ascii')
                if not re.fullmatch(r'[A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+', component):
                    raise ValueError('Android component required')
            try:
                fd = os.open('apps-' + token + '.tsv', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
            except FileNotFoundError:
                raise ValueError('Current Android catalog unavailable') from None
            with os.fdopen(fd, 'rb') as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 65536:
                    raise ValueError('Owned bounded Android catalog required')
                catalog = source.read(65537)
            if len(catalog) > 65536 or (component is not None and component not in {line.split('\t', 1)[0] for line in catalog.decode('utf-8').splitlines()}):
                raise ValueError('Android component is outside the current catalog')
            if component is not None: text += '\t' + component
        elif action == 'web':
            if not isinstance(payload, str) or len(payload.encode('utf-8')) > 3072 or any(ord(c) < 33 or ord(c) == 127 for c in payload):
                raise ValueError('HTTP/HTTPS web address required')
            url = urlsplit(payload)
            if url.scheme not in {'https', 'http'} or not url.hostname or url.username is not None or url.password is not None:
                raise ValueError('HTTP/HTTPS web address required')
            text += '\t' + payload
        elif payload is not None:
            raise ValueError('Unexpected Android action argument')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=directory)
        with os.fdopen(fd, 'wb') as output:
            output.write((text + '\n').encode('utf-8'))
        os.rename(temporary, 'request-' + token, src_dir_fd=directory, dst_dir_fd=directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass
        os.close(directory)


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        raise SystemExit('Android action and optional app/web address required')
    request('/run/loopy', os.environ.get('LOOPY_SESSION'), *sys.argv[1:])
