#!/usr/bin/env python3
"""Public GTK3 Wayland window; time metadata only, no text or pixel capture."""
import argparse
import json
import os
import signal
import sys
import time

from probe_termux_input_latency_common import own_identity, require, LIMIT


def run(args):
    require(os.getuid() == args.expect_guest_uid and 1 <= args.seconds <= 60)
    if os.getsid(0) != os.getpid(): os.setsid()
    owner = own_identity(args.nonce, args.session)
    require(owner['uid'] == args.expect_native_uid)
    require(os.environ.get('GDK_BACKEND') == 'wayland')
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gdk, GLib, GObject, Gtk
    Gtk.init([])
    display = Gdk.Display.get_default()
    require(display is not None and GObject.type_name(display.__gtype__) == 'GdkWaylandDisplay')
    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title('Loopy latency ' + args.nonce)
    win.set_wmclass('loopy-latency-' + args.nonce, 'LoopyLatencyWayland')
    win.set_default_size(640, 420)
    win.set_resizable(False)
    area = Gtk.DrawingArea()
    area.set_size_request(640, 420)
    win.add(area)
    win.add_events(Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.KEY_RELEASE_MASK |
                   Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                   Gdk.EventMask.POINTER_MOTION_MASK)
    pending, drawn = [], []
    sequence = 0
    ready = False
    closing = False
    failed = False
    reason = 'deadline'

    def emit(row):
        print(json.dumps(row, separators=(',', ':')), flush=True)

    def finish(cause='deadline'):
        nonlocal closing, reason
        if not closing:
            closing, reason = True, cause
            win.destroy()
            Gtk.main_quit()
        return False

    def after_paint(_clock):
        if closing or not drawn: return
        completed = time.monotonic_ns()
        emit(dict(type='PAINT', ids=list(drawn), complete_ns=completed))
        drawn.clear()

    def guarded(callback):
        def call(*values):
            nonlocal failed
            try: return callback(*values)
            except Exception:
                failed = True
                finish('own-close')
                return False
        return call

    def draw(_widget, cr):
        if sequence & 1: cr.set_source_rgb(0x31/255, 0x55/255, 0x4a/255)
        else: cr.set_source_rgb(0x24/255, 0x34/255, 0x4d/255)
        cr.paint()
        cr.set_source_rgb(0xe8/255, 0xed/255, 0xf2/255)
        cr.rectangle(240, 130, 160, 160)
        cr.fill()
        drawn.extend(pending)
        pending.clear()
        return False

    def mapped(_window, _event):
        nonlocal ready
        if not ready:
            require(area.get_allocated_width() == 640 and area.get_allocated_height() == 420)
            clock = win.get_frame_clock()
            require(clock is not None)
            clock.connect('after-paint', guarded(after_paint))
            emit(dict(type='READY', schema=1, **owner, backend='wayland-after-paint',
                      width=640, height=420, window=None))
            ready = True
        return False

    def event(_window, value, kind):
        nonlocal sequence
        arrival = time.monotonic_ns()
        if not ready or closing or not win.is_active() or sequence >= LIMIT: return True
        sequence += 1
        emit(dict(type='EVENT', id=sequence, kind=kind, arrival_ns=arrival,
                  source_ms=int(value.get_time()) & 0xffffffff))
        pending.append(sequence)
        area.queue_draw()
        if sequence == LIMIT: GLib.idle_add(lambda: finish('event-limit'))
        return True

    for name, kind in (('key-press-event', 'key_down'), ('key-release-event', 'key_up'),
                       ('button-press-event', 'button_down'), ('button-release-event', 'button_up'),
                       ('motion-notify-event', 'motion')):
        win.connect(name, guarded(event), kind)
    win.connect('delete-event', lambda *_: finish('own-close') or True)
    win.connect('map-event', guarded(mapped))
    area.connect('draw', guarded(draw))
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: finish('own-close'))
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: finish('own-close'))
    GLib.timeout_add_seconds(args.seconds, finish)
    try:
        win.show_all()
        win.present()
        Gtk.main()
    finally:
        win.destroy()
    require(ready and closing and not failed)
    emit(dict(type='DONE', reason=reason, window_destroyed=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nonce', required=True)
    parser.add_argument('--session', required=True)
    parser.add_argument('--expect-guest-uid', type=int, default=1000)
    parser.add_argument('--expect-native-uid', type=int, default=10323)
    parser.add_argument('--seconds', type=int, default=30)
    args = parser.parse_args()
    try:
        run(args)
        return 0
    except Exception:
        print('latency-fixture-unavailable', file=sys.stderr)
        return 3


if __name__ == '__main__': raise SystemExit(main())
