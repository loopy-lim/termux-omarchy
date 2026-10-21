"""Bounded serialized HTTP(S) URI, retained in memory without rewriting or resolving."""
import ipaddress
import re
from urllib.parse import urlsplit


BROWSER = 'org.chromium.chrome/com.google.android.apps.chrome.Main'
MAXIMUM = 2048


def validate(value):
    if (type(value) is not str or not 1 <= len(value) <= MAXIMUM
            or any(not 33 <= ord(char) <= 126 for char in value)
            or any(char in '<>{}|^"`\\' for char in value)
            or re.search(r'%(?![0-9A-Fa-f]{2})', value)):
        raise ValueError('inside-uri')
    try:
        parsed = urlsplit(value)
        if (parsed.scheme.lower() not in ('http', 'https') or not parsed.netloc
                or '@' in parsed.netloc or parsed.username is not None
                or parsed.password is not None or '%' in parsed.netloc
                or any(char in '[]' for char in parsed.path + parsed.query + parsed.fragment)
                or '#' in parsed.fragment):
            raise ValueError('inside-uri')
        host = parsed.hostname
        if not host or parsed.netloc.endswith(':'):
            raise ValueError('inside-uri')
        port = parsed.port
        if port is not None and not 1 <= port <= 65535:
            raise ValueError('inside-uri')
        if parsed.netloc.startswith('['):
            end = parsed.netloc.index(']')
            suffix = parsed.netloc[end + 1:]
            if suffix and not re.fullmatch(r':[0-9]+', suffix):
                raise ValueError('inside-uri')
            ipaddress.IPv6Address(host)
        else:
            if ':' in host or '[' in parsed.netloc or ']' in parsed.netloc:
                raise ValueError('inside-uri')
            labels = host.removesuffix('.').split('.')
            if (len(host) > 253 or any(not 1 <= len(label) <= 63
                    or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?', label)
                    for label in labels)):
                raise ValueError('inside-uri')
            if len(labels) == 4 and all(label.isdigit() for label in labels):
                if any(int(label) > 255 for label in labels):
                    raise ValueError('inside-uri')
    except (ValueError, UnicodeError):
        raise ValueError('inside-uri') from None
    return value


def initial(target, value):
    if type(target) is not dict or target.get('component') != BROWSER:
        raise ValueError('inside-uri-target')
    return validate(value)
