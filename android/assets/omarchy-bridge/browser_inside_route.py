"""Select only stock Chromium with no arguments or one serialized HTTP(S) URI."""
import os
import inside_wire as wire


ENCODED = 'b3JnLmNocm9taXVtLmNocm9tZS9jb20uZ29vZ2xlLmFuZHJvaWQuYXBwcy5jaHJvbWUuTWFpbg'


def selection(argv):
    if (not isinstance(argv, (list, tuple)) or not 1 <= len(argv) <= 3
            or any(type(value) is not str for value in argv)
            or argv[0] != '/usr/bin/chromium'):
        return None
    if any(os.environ.get(name) for name in ('CHROME_USER_DATA_DIR', 'CHROME_CONFIG_HOME')):
        return None
    arguments = list(argv[1:])
    if arguments and arguments[0] == '--ozone-platform=wayland':
        arguments = arguments[1:]
    if len(arguments) > 1:
        return None
    initial_url = None
    if arguments:
        from inside_uri import validate
        try:
            initial_url = validate(arguments[0])
        except ValueError:
            return None
    try:
        wire.catalog('/run/loopy', os.environ.get('LOOPY_SESSION', ''), ENCODED)
    except (OSError, ValueError, UnicodeError):
        return None
    return ENCODED, initial_url


def component(argv):
    """The legacy encoded-only API must never silently discard a URI."""
    if not isinstance(argv, (list, tuple)) or tuple(argv) not in (
            ('/usr/bin/chromium',), ('/usr/bin/chromium', '--ozone-platform=wayland')):
        return None
    selected = selection(argv)
    return selected[0] if selected is not None else None
