"""Real View callbacks/Session; inert GTK, scheduler and transport, no GTK/device run."""
import ast
import copy
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'android/assets/omarchy-bridge'
WINDOW = DIRECTORY / 'inside_window.py'
TARGET = dict(component='org.example/.Main', uid=10123)
INITIAL = dict(epoch=1, width=2512, height=1592, density=320)


class Scheduler:
    def __init__(self):
        self.next_id = 0
        self.timers = {}
        self.idles = []
        self.workers = []

    def timeout_add(self, delay, callback):
        self.next_id += 1
        self.timers[self.next_id] = (delay, callback)
        return self.next_id

    def source_remove(self, source):
        self.timers.pop(source, None)

    def idle_add(self, callback, *args):
        self.idles.append((callback, args))

    def debounce(self):
        for source, (delay, callback) in list(self.timers.items()):
            if delay == 150:
                del self.timers[source]
                callback()

    def network(self):
        with patch.dict(os.environ, {'LOOPY_SESSION': 'token-1'}):
            while self.workers or self.idles:
                workers, self.workers = self.workers, []
                for worker in workers:
                    worker()
                idles, self.idles = self.idles, []
                for callback, args in idles:
                    callback(*args)

    def Thread(self, *, target, name, daemon):
        return types.SimpleNamespace(start=lambda: self.workers.append(target))


class Widget:
    """Only the external widget operations used by the actual View constructor."""
    def __init__(self, **kwargs):
        self.signals = {}
        self.width, self.height, self.factor = 1256, 796, 2
        self.destroyed = False

    def connect(self, name, callback): self.signals[name] = callback
    def set_title(self, *args): pass
    def set_default_size(self, *args): pass
    def set_can_focus(self, *args): pass
    def set_hexpand(self, *args): pass
    def set_vexpand(self, *args): pass
    def add_events(self, *args): pass
    def add(self, *args): pass
    def add_overlay(self, *args): pass
    def set_halign(self, *args): pass
    def set_valign(self, *args): pass
    def set_line_wrap(self, *args): pass
    def pack_start(self, *args): pass
    def set_text(self, *args): pass
    def set_sensitive(self, *args): pass
    def show_all(self): pass
    def hide(self): pass
    def queue_draw(self): pass
    def grab_focus(self): pass
    def is_active(self): return True
    def get_allocation(self): return types.SimpleNamespace(width=self.width, height=self.height)
    def get_scale_factor(self): return self.factor
    def get_window(self): return types.SimpleNamespace(__gtype__=types.SimpleNamespace(name='GdkWaylandWindow'))
    def get_display(self): return types.SimpleNamespace(__gtype__=types.SimpleNamespace(name='GdkWaylandDisplay'))

    def destroy(self):
        if not self.destroyed:
            self.destroyed = True
            self.signals['destroy'](self)


class Socket:
    def __init__(self): self.closed = False; self.sent = []
    def close(self): self.closed = True
    def send(self, data):
        if self.closed: raise ValueError('closed-test-transport')
        self.sent.append(bytes(data))
        return len(data)


class ViewHarness:
    def __init__(self):
        modules = {}
        with patch.dict(sys.modules):
            for name in ('inside_wire', 'inside_input', 'inside_window'):
                path = DIRECTORY / (name + '.py')
                module = types.ModuleType(name); module.__file__ = str(path)
                sys.modules[name] = module
                exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
                modules[name] = module
        module = modules['inside_window']
        run = next(node for node in ast.parse(WINDOW.read_bytes(), str(WINDOW)).body
                   if isinstance(node, ast.FunctionDef) and node.name == 'run')
        view = next(node for node in run.body if isinstance(node, ast.ClassDef) and node.name == 'View')
        self.scheduler = Scheduler(); self.sockets = []; self.refuse_next = False
        self.peer = dict(app_uid=os.getuid(), app_pid=55, socket_dev=1, socket_ino=2)
        transport = types.SimpleNamespace(**modules['inside_wire'].__dict__)
        transport.catalog = lambda *args: copy.deepcopy(TARGET)
        transport.connect = self.connect
        transport.check_peer = lambda sock, peer: None
        gtk = types.SimpleNamespace(**{name: Widget for name in
            ('ApplicationWindow', 'DrawingArea', 'Overlay', 'Box', 'Label', 'Button')},
            Orientation=types.SimpleNamespace(VERTICAL=1), Align=types.SimpleNamespace(CENTER=1))
        masks = types.SimpleNamespace(**{name: 1 for name in
            ('BUTTON_PRESS_MASK', 'BUTTON_RELEASE_MASK', 'POINTER_MOTION_MASK', 'SCROLL_MASK',
             'SMOOTH_SCROLL_MASK', 'KEY_PRESS_MASK', 'KEY_RELEASE_MASK')})
        namespace = dict(module.__dict__, Gtk=gtk, Gdk=types.SimpleNamespace(EventMask=masks),
            GLib=self.scheduler, threading=self.scheduler, wire=transport,
            application_id='dev.loopy.android.w' + 'a' * 32, encoded='owned-component', initial_url=None,
            app=types.SimpleNamespace(quit=lambda: None))
        exec(compile(ast.Module(body=[view], type_ignores=[]), str(WINDOW), 'exec'), namespace)
        self.view = namespace['View']()

    def connect(self, token):
        if self.refuse_next:
            self.refuse_next = False
            raise ValueError('unavailable-test-transport')
        sock = Socket(); self.sockets.append(sock)
        return sock, copy.deepcopy(self.peer)

    def allocation(self, width=1256, height=796, factor=2):
        self.view.area.width, self.view.area.height, self.view.area.factor = width, height, factor
        self.view.size(self.view.area, self.view.area.get_allocation())

    def open_command(self):
        session = self.view.session
        if session is None: raise AssertionError('ready allocation did not establish a session')
        grant = dict(type='GRANT', session='token-1', app_uid=os.getuid(), app_pid=55,
                     shell_uid=2000, shell_pid=99, birth=123, generation=1)
        session.receive(grant)
        session.receive(dict(type='HELLO', **{k: grant[k] for k in
            ('session', 'app_uid', 'shell_uid', 'shell_pid', 'birth', 'generation')}, caps=127, keys=[30, 88]))
        return copy.deepcopy(session.inflight)

    def reply(self, kind='ACK'):
        session = self.view.session; command = session.inflight
        lease = session.task or dict(stamp=command['stamp'], target=TARGET, task_id=42, display_id=7)
        released = command['action'] in ('RELEASE_ALL', 'RESIZE') or command['action'] == 'FOCUS' and not command['pressed']
        session.receive(dict(type=kind, observation=dict(task=lease, top_uid=10123, visible=True,
            running=True, focused=True), geometry=command['geometry'],
            request_sequence=command['sequence'], inputs_released=released))


class InitialGeometryTests(unittest.TestCase):
    def test_fast_connect_waits_for_valid_debounced_allocation_before_open(self):
        harness = ViewHarness(); view = harness.view
        view.realized(); harness.allocation(); harness.scheduler.network()
        self.assertIsNone(view.session, 'initial connection must not use placeholder density')
        self.assertEqual(harness.sockets, [], 'no transport acquisition before initial allocation settles')
        harness.scheduler.debounce(); harness.scheduler.network()
        command = harness.open_command()
        self.assertEqual(command['action'], 'OPEN_ZLIB'); self.assertEqual(command['geometry'], INITIAL)
        self.assertEqual(len(harness.sockets), 1)

    def test_debounced_allocation_before_realize_opens_once_at_actual_geometry(self):
        harness = ViewHarness(); harness.allocation(); harness.scheduler.debounce(); harness.scheduler.network()
        self.assertIsNone(harness.view.session); self.assertEqual(harness.sockets, [])
        harness.view.realized(); harness.scheduler.network()
        self.assertEqual(harness.open_command()['geometry'], INITIAL)
        harness.allocation(); harness.scheduler.debounce(); harness.scheduler.network()
        self.assertEqual(len(harness.sockets), 1)
        self.assertFalse(harness.view.session._changed())

    def test_invalid_initial_allocation_and_retry_never_acquire_placeholder(self):
        harness = ViewHarness(); harness.view.realized(); harness.allocation(0, 0, 2)
        harness.scheduler.debounce(); harness.view.start(); harness.scheduler.network()
        self.assertIsNone(harness.view.session); self.assertEqual(harness.sockets, [])
        harness.allocation(); harness.scheduler.debounce(); harness.scheduler.network()
        self.assertEqual(harness.open_command()['geometry'], INITIAL)

    def test_close_or_destroy_before_initial_allocation_never_opens(self):
        for cancel in ('close', 'destroy'):
            with self.subTest(cancel=cancel):
                harness = ViewHarness(); harness.view.realized(); harness.allocation()
                getattr(harness.view, cancel)()
                harness.scheduler.debounce(); harness.scheduler.network()
                self.assertIsNone(harness.view.session)
                self.assertTrue(all(sock.closed and not sock.sent for sock in harness.sockets))

    def test_close_with_acquire_queued_retires_delayed_socket_without_open(self):
        harness = ViewHarness(); harness.view.realized(); harness.allocation(); harness.scheduler.debounce()
        harness.view.close(); harness.scheduler.network()
        self.assertIsNone(harness.view.session)
        self.assertTrue(all(sock.closed and not sock.sent for sock in harness.sockets))

    def test_retry_during_new_allocation_waits_for_latest_geometry(self):
        harness = ViewHarness(); harness.refuse_next = True; harness.view.realized(); harness.allocation()
        harness.scheduler.debounce(); harness.scheduler.network(); self.assertIsNone(harness.view.session)
        harness.allocation(1000, 700, 2); harness.view.start(); harness.scheduler.network()
        self.assertIsNone(harness.view.session); self.assertEqual(harness.sockets, [])
        harness.scheduler.debounce(); harness.scheduler.network()
        self.assertEqual(harness.open_command()['geometry'], dict(epoch=1, width=2000, height=1400, density=320))

    def test_allocation_during_acquire_closes_socket_and_waits_latest_debounce(self):
        harness = ViewHarness(); harness.view.realized(); harness.allocation(); harness.scheduler.debounce()
        harness.allocation(900, 600, 1); harness.scheduler.network()
        self.assertIsNone(harness.view.session, 'queued acquire must not open the previous density while allocation is pending')
        self.assertEqual(len(harness.sockets), 1); self.assertTrue(harness.sockets[0].closed)
        harness.scheduler.debounce(); harness.scheduler.network()
        command = harness.open_command()
        self.assertEqual(command['action'], 'OPEN_ZLIB')
        self.assertEqual(command['geometry'], dict(epoch=1, width=900, height=600, density=160))
        self.assertEqual(len(harness.sockets), 2); self.assertTrue(harness.sockets[0].closed)
        self.assertFalse(harness.sockets[1].closed)

    def test_later_resize_keeps_balanced_retirement_epoch_and_focus_ack(self):
        harness = ViewHarness(); harness.view.realized(); harness.allocation()
        harness.scheduler.debounce(); harness.scheduler.network()
        self.assertEqual(harness.open_command()['geometry'], INITIAL)
        harness.reply('OPENED'); harness.reply(); session = harness.view.session
        self.assertTrue(session.input.focused)
        harness.allocation(1000, 700, 2); harness.scheduler.debounce()
        self.assertFalse(session.input.focused); self.assertEqual(session.inflight['action'], 'RELEASE_ALL')
        harness.reply(); self.assertEqual(session.inflight['action'], 'FOCUS'); self.assertFalse(session.inflight['pressed'])
        harness.reply(); self.assertEqual(session.inflight['action'], 'RESIZE')
        self.assertEqual(session.inflight['geometry'], dict(epoch=2, width=2000, height=1400, density=320))
        harness.reply(); self.assertEqual(session.inflight['action'], 'FOCUS'); self.assertTrue(session.inflight['pressed'])
        self.assertFalse(session.input.focused); harness.reply(); self.assertTrue(session.input.focused)


if __name__ == '__main__': unittest.main()
