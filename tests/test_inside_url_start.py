"""Initial URI uses the authenticated OPEN path; no address-bar typing or real URLs."""
import copy
import ast
import importlib.util
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'android/assets/omarchy-bridge'
TARGET = dict(component='org.chromium.chrome/com.google.android.apps.chrome.Main', uid=10372)
GEOMETRY = dict(epoch=1, width=2, height=2, density=160)
PEER = dict(app_uid=10330, app_pid=55, socket_dev=1, socket_ino=2)
STAMP = dict(session='token-1', window='a' * 32, generation=1)
URL = 'https://example.com/public%20fixture?q=1#section'
GRANT = dict(type='GRANT', session='token-1', app_uid=10330, app_pid=55,
             shell_uid=2000, shell_pid=99, birth=123, generation=1)
HELLO = dict(type='HELLO', session='token-1', app_uid=10330, shell_uid=2000,
             shell_pid=99, birth=123, generation=1, caps=127, keys=[30, 88])


def load(name):
    spec = importlib.util.spec_from_file_location(name, ASSETS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class InitialUrlTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ASSETS))
        self.addCleanup(sys.path.remove, str(ASSETS))
        self.wire = load('inside_wire')
        load('inside_input')
        self.window = load('inside_window')

    def value(self, action='OPEN_URL', **extra):
        value = dict(stamp=STAMP, sequence=1, action=action, target=TARGET,
                     task_id=0, display_id=0, geometry=GEOMETRY,
                     x=0, y=0, code=0, pressed=False)
        if action == 'OPEN_URL':
            value.update(initial_url=URL, compact=True)
        return {**value, **extra}

    def session(self, **extra):
        return self.window.Session('token-1', 'a' * 32, 10330, TARGET, PEER,
                                   GEOMETRY, clock=lambda: 1, **extra)

    def test_open_url_has_separate_action_and_exact_bounded_tail(self):
        packet = self.wire.command(self.value())
        legacy = self.wire.command(self.value('OPEN_ZLIB'))
        body = bytearray(legacy[4:])
        body[5] = 12
        body.extend(b'\x01' + struct.pack('>H', len(URL)) + URL.encode('ascii'))
        self.assertEqual(packet, struct.pack('>i', len(body)) + body)
        self.assertTrue(self.wire.is_open('OPEN_URL'))
        self.assertEqual(self.wire.command(self.value('OPEN_ZLIB'))[9], 11)
        self.assertEqual(self.wire.command(self.value('OPEN'))[9], 1)

    def test_url_opens_only_after_matching_grant_and_hello_without_input(self):
        session = self.session(initial_url=URL, compressed=True)
        self.assertFalse(session.output.pending)
        session.receive(copy.deepcopy(GRANT))
        self.assertFalse(session.output.pending)
        session.receive(copy.deepcopy(HELLO))
        self.assertEqual(session.inflight['action'], 'OPEN_URL')
        self.assertEqual(session.inflight['initial_url'], URL)
        self.assertIs(session.inflight['compact'], True)
        self.assertEqual(session.inputs, [])
        self.assertEqual(bytes(session.output.buffer), self.wire.command(session.inflight))
        self.assertEqual(session.deadline, 16)

    def test_actual_view_connected_callback_forwards_uri_to_authenticated_session(self):
        tree = ast.parse((ASSETS / 'inside_window.py').read_text())
        run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
        view = next(node for node in run.body if isinstance(node, ast.ClassDef) and node.name == 'View')
        connected = next(node for node in view.body if isinstance(node, ast.FunctionDef) and node.name == 'connected')
        namespace = dict(wire=self.wire, Session=self.window.Session, initial_url=URL,
                         application_id='dev.loopy.android.w' + 'a' * 32,
                         os=types.SimpleNamespace(getuid=lambda: 10330))
        exec(compile(ast.Module(body=[connected], type_ignores=[]), 'actual-view-connected', 'exec'), namespace)
        window = types.SimpleNamespace(is_active=lambda: True)
        view = types.SimpleNamespace(dead=False, generation=1, close_at=None, resize_timer=0,
                                     view_geometry=GEOMETRY, window=window)
        failures = []
        view.unavailable = lambda: failures.append(True)
        with patch.object(self.wire, 'check_peer'):
            namespace['connected'](view, 1, (object(), PEER, 'token-1', TARGET))
        self.assertEqual(failures, [])
        self.assertEqual(view.session.initial_url, URL)
        self.assertEqual(view.session.state, 'GRANT')
        self.assertFalse(view.session.output.pending)
        view.session.receive(copy.deepcopy(GRANT)); view.session.receive(copy.deepcopy(HELLO))
        self.assertEqual(view.session.inflight['action'], 'OPEN_URL')
        self.assertIs(view.session.inflight['compact'], True)

    def test_open_url_lease_and_close_still_use_exact_ack_and_owned_cleanup(self):
        session = self.session(initial_url=URL)
        session.receive(copy.deepcopy(GRANT)); session.receive(copy.deepcopy(HELLO))
        command = session.inflight
        lease = dict(stamp=STAMP, target=TARGET, task_id=42, display_id=7)
        opened = dict(type='OPENED', observation=dict(task=lease, top_uid=TARGET['uid'],
                      visible=True, running=True, focused=True), geometry=GEOMETRY,
                      request_sequence=command['sequence'], inputs_released=False)
        with self.assertRaises(ValueError):
            session.receive({**opened, 'request_sequence': 99})
        session.receive(opened)
        self.assertEqual(session.task, lease)
        session.close()
        for _ in range(3):
            if session.inflight['action'] == 'CLOSE':
                break
            command = session.inflight
            session.receive(dict(type='ACK', observation=dict(task=lease, top_uid=TARGET['uid'],
                            visible=True, running=True, focused=True), geometry=GEOMETRY,
                            request_sequence=command['sequence'], inputs_released=True))
        self.assertEqual(session.inflight['action'], 'CLOSE')
        session.receive(dict(type='CLOSED', stamp=STAMP, task_id=42, display_id=7,
                        task_removed=True, display_removed=True, inputs_released=True))
        self.assertEqual(session.state, 'CLOSED')

    def test_malformed_uri_and_foreign_target_reject_before_any_packet(self):
        for uri in ('javascript:alert(1)', 'https://user@example.com/',
                    'https://example.com/%zz', 'https://example.com/\n', 'https://example.com:0/'):
            with self.subTest(kind='invalid'), self.assertRaises(ValueError):
                self.session(initial_url=uri)
        for change in ({'target': dict(component='org.example/.Main', uid=10123)},
                       {'task_id': 42, 'display_id': 7}, {'compact': 1}):
            with self.subTest(change=tuple(change)), self.assertRaises(ValueError):
                self.wire.command(self.value(**change))

    def test_legacy_action_cannot_silently_drop_uri_and_url_cannot_retry_plain(self):
        for action in ('OPEN', 'OPEN_ZLIB'):
            with self.subTest(action=action), self.assertRaises(ValueError):
                self.wire.command(self.value(action, initial_url=URL, compact=True))
        session = self.session(initial_url=URL)
        session.receive(copy.deepcopy(GRANT)); session.receive(copy.deepcopy(HELLO))
        sequence = session.sequence
        with self.assertRaises(ValueError):
            session.receive(dict(type='ERROR', request_sequence=sequence, code=12))
        self.assertEqual(session.sequence, sequence)
        self.assertEqual(session.inflight['action'], 'OPEN_URL')


if __name__ == '__main__':
    unittest.main()
