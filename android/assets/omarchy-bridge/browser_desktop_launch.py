"""Preserve gtk-launch unless its stock Chromium entry selects an inside launch."""
import os
import sys
from browser_inside_route import selection


def resolved_selection(initial_url=None):
    try:
        import gi
        gi.require_version('Gio', '2.0')
        gi.require_version('GLib', '2.0')
        from gi.repository import Gio, GLib
        entry = Gio.DesktopAppInfo.new('chromium.desktop')
        if entry is None:
            return None
        commandline = entry.get_commandline()
        if (type(commandline) is not str or '\0' in commandline
                or not 0 < len(commandline.encode('utf-8')) <= 8192):
            return None
        valid, argv = GLib.shell_parse_argv(commandline)
        if (valid is not True or not isinstance(argv, (list, tuple))
                or not 1 <= len(argv) <= 256 or any(type(value) is not str for value in argv)):
            return None
    except (ImportError, OSError, ValueError):
        return None
    except GLib.Error:
        return None
    field = argv[-1] in ('%u', '%U')
    if field:
        argv = argv[:-1]
    if (any('%' in value for value in argv) or initial_url is not None and not field
            or tuple(argv) not in (('/usr/bin/chromium',),
                                   ('/usr/bin/chromium', '--ozone-platform=wayland'))):
        return None
    # Field substitution follows validation of the original desktop tokens.
    # A URI percent escape is never interpreted as another desktop field code.
    return selection([*argv, initial_url] if initial_url is not None else argv)


def resolved_component():
    selected = resolved_selection()
    return selected[0] if selected is not None else None


def main(argv=None):
    values = sys.argv[1:] if argv is None else argv
    if not values:
        return 64
    if (len(values) in (2, 3) and tuple(values[:2]) in (
            ('gtk-launch', 'chromium.desktop'), ('/usr/bin/gtk-launch', 'chromium.desktop'))
            and (len(values) == 2 or type(values[2]) is str)):
        selected = resolved_selection(values[2] if len(values) == 3 else None)
        if selected is not None:
            import inside_window
            encoded, initial_url = selected
            if initial_url is None:
                return inside_window.run(encoded)
            return inside_window.run(encoded, initial_url=initial_url)
    return os.execvp(values[0], values)


if __name__ == '__main__':
    raise SystemExit(main())
