"""Real UNIX transport and owned job files; this is not a compositor simulation proof."""
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'android/assets/omarchy-bridge'


def module(name):
    path = ASSETS / (name + '.py')
    if not path.is_file():
        raise AssertionError('Production Omarchy semantic actions are unavailable: ' + name)
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(result)
    finally:
        sys.dont_write_bytecode = previous
    return result


class OwnedSocket:
    """Only replace the external socket peer; exercise production framing and file handling."""
    def __init__(self, path, replies):
        self.requests = []
        self.replies = replies
        self.error = None
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(path))
        self.socket.listen(4)
        self.socket.settimeout(3)
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        try:
            for fragments in self.replies:
                with self.socket.accept()[0] as client:
                    client.settimeout(2)
                    request = bytearray()
                    while True:
                        chunk = client.recv(1024)
                        if not chunk:
                            break
                        request.extend(chunk)
                    self.requests.append(request.decode())
                    for fragment in fragments:
                        if isinstance(fragment, float):
                            time.sleep(fragment)
                        else:
                            client.sendall(fragment)
        except (OSError, UnicodeError) as error:
            self.error = error

    def close(self):
        self.thread.join(3)
        self.socket.close()


class OmarchyActionTests(unittest.TestCase):
    def test_window_switcher_forward_reverse_and_overview_dispatch_to_original_compositor(self):
        ipc = module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-switch-', dir='/tmp') as directory:
            path = Path(directory) / 'ctl'; peer = OwnedSocket(path, [[b'ok']] * 3)
            try:
                client = ipc.Hyprland(path)
                client.execute({'action': 'window', 'operation': 'focus-next'})
                client.execute({'action': 'window', 'operation': 'focus-prev'})
                client.execute({'action': 'launch', 'app': 'overview'})
            finally: peer.close()
            self.assertEqual(peer.requests, [
                'dispatch hl.dsp.window.cycle_next({next=true})',
                'dispatch hl.dsp.window.cycle_next({next=false})',
                'dispatch hl.dsp.window.cycle_next({next=true})',
            ])

    def test_product_launcher_theme_and_scale_use_native_original_session(self):
        ipc = module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-product-', dir='/tmp') as directory:
            path = Path(directory) / 'ctl'; peer = OwnedSocket(path, [[b'ok']] * 3)
            try:
                client = ipc.Hyprland(path)
                client.execute({'action': 'launch', 'app': 'terminal'})
                client.execute({'action': 'theme', 'name': 'Nord'})
                client.execute({'action': 'window', 'operation': 'scale-125'})
            finally: peer.close()
            self.assertEqual(peer.requests, [
                'dispatch hl.dsp.exec_cmd("/usr/bin/foot --app-id=foot /usr/bin/zsh -l")',
                'dispatch hl.dsp.exec_cmd("/usr/bin/bash /usr/share/omarchy/bin/omarchy-theme-set Nord")',
                "eval hl.monitor({output='',mode='preferred',position='auto',scale=1.25})",
            ])
        client = ipc.Hyprland(Path('/tmp/loopy-never-open-product-ipc'))
        for job in ({'action': 'launch', 'app': "terminal');evil()"},
                    {'action': 'theme', 'name': "Nord; evil"}, {'action': 'window', 'operation': 'scale-999'}):
            with self.assertRaises(ValueError): client.execute(job)

    def test_fullscreen_readiness_belongs_to_live_worker_and_preserves_replacements(self):
        worker = module('session_actions')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with worker.Worker(root, 'owned', None) as queue:
                queue.ready('owned-signature')
                self.assertEqual((root / 'ready-owned').read_bytes(), b'ready\n')
            self.assertFalse((root / 'ready-owned').exists())
            self.assertFalse((root / 'actions-owned.ready.json').exists())
            with worker.Worker(root, 'owned', None) as queue:
                queue.ready('owned-signature')
                other = root / 'replacement'; other.write_bytes(b'new owner')
                other.replace(root / 'ready-owned')
            self.assertEqual((root / 'ready-owned').read_bytes(), b'new owner')

    def test_native_input_uses_only_the_selected_owned_wayland_display(self):
        worker = module('session_actions')
        configure = getattr(worker, 'configure_input', None)
        self.assertTrue(callable(configure), 'Omarchy has no owned-display native input preparation')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-text-', dir='/tmp') as d:
            root = Path(d)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); server.bind(str(root / 'wayland-1'))
            try:
                previous = worker.loopy_input.IPC_ROOT
                try:
                    configure(root, 'owned', 'wayland-1')
                    self.assertEqual((root / 'display-owned').read_bytes(), b'wayland-1\n')
                    configure(root, 'owned', 'wayland-1')
                    self.assertEqual(worker.loopy_input.IPC_ROOT, root)
                finally:
                    worker.loopy_input.IPC_ROOT = previous
            finally:
                server.close()

    def test_native_input_preserves_an_existing_redirected_display_record(self):
        worker = module('session_actions')
        configure = getattr(worker, 'configure_input', None)
        self.assertTrue(callable(configure), 'Omarchy has no owned-display native input preparation')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-text-', dir='/tmp') as d:
            root = Path(d); keep = root / 'keep'; keep.write_text('KEEP_USER_DATA')
            (root / 'display-owned').symlink_to(keep)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); server.bind(str(root / 'wayland-1'))
            try:
                with self.assertRaises((OSError, ValueError)):
                    configure(root, 'owned', 'wayland-1')
                self.assertEqual(keep.read_text(), 'KEEP_USER_DATA')
                self.assertTrue((root / 'display-owned').is_symlink())
            finally:
                server.close()

    def test_app_copy_and_terminal_paste_use_the_selected_window_and_appropriate_modifiers(self):
        ipc = module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-edit-', dir='/tmp') as d:
            path = Path(d) / 'ctl'
            peer = OwnedSocket(path, [
                [b'{"address":"0x1234","class":"org.quickshell"}'], [b'ok'],
                [b'{"address":"0xabcd","class":"foot"}'], [b'ok'],
            ])
            try:
                client = ipc.Hyprland(path)
                try:
                    client.execute({'action': 'edit', 'operation': 'copy'})
                    client.execute({'action': 'edit', 'operation': 'paste'})
                except ValueError as error:
                    self.fail('Omarchy editing must deliver the allowed copy/paste actions: ' + str(error))
            finally:
                peer.close()
            self.assertIsNone(peer.error)
            self.assertEqual(peer.requests, [
                'j/activewindow',
                "dispatch hl.dsp.send_shortcut({mods='CTRL',key='c',window='address:0x1234'})",
                'j/activewindow',
                "dispatch hl.dsp.send_shortcut({mods='CTRL SHIFT',key='v',window='address:0xabcd'})",
            ])

    def test_invalid_edit_and_untrusted_window_selector_cannot_become_lua(self):
        ipc = module('hyprland_actions')
        client = ipc.Hyprland(Path('/tmp/loopy-never-open-this-ipc'))
        with self.assertRaises(ValueError):
            client.execute({'action': 'edit', 'operation': "copy'}); os.execute('bad')"})
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-edit-', dir='/tmp') as d:
            path = Path(d) / 'ctl'
            peer = OwnedSocket(path, [[b'{"address":"0x1234\u0027);bad()","class":"foot"}']])
            try:
                with self.assertRaises(ValueError):
                    ipc.Hyprland(path).execute({'action': 'edit', 'operation': 'copy'})
            finally:
                peer.close()
            self.assertEqual(peer.requests, ['j/activewindow'])

    def test_foot_zoom_resolves_unshifted_equal_and_preserves_exact_window(self):
        ipc = module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-font-', dir='/tmp') as d:
            path = Path(d) / 'ctl'
            peer = OwnedSocket(path, [
                [b'{"address":"0x1234","class":"foot"}'], [b'ok'],
                [b'{"address":"0xabcd","class":"footclient"}'], [b'ok'],
                [b'{"address":"0x1234","class":"foot"}'], [b'ok'],
            ])
            try:
                client = ipc.Hyprland(path)
                for operation in ('zoom_in', 'zoom_out', 'zoom_reset'):
                    client.execute({'action': 'edit', 'operation': operation})
            finally:
                peer.close()
            self.assertIsNone(peer.error)
            self.assertEqual(peer.requests, [
                'j/activewindow',
                "dispatch hl.dsp.send_shortcut({mods='CTRL',key='equal',window='address:0x1234'})",
                'j/activewindow',
                "dispatch hl.dsp.send_shortcut({mods='CTRL',key='minus',window='address:0xabcd'})",
                'j/activewindow',
                "dispatch hl.dsp.send_shortcut({mods='CTRL',key='0',window='address:0x1234'})",
            ])

    def test_nonterminal_zoom_in_keeps_plus_semantics_through_base_equal(self):
        ipc = module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-zoom-', dir='/tmp') as d:
            path = Path(d) / 'ctl'
            peer = OwnedSocket(path, [
                [b'{"address":"0xf00d","class":"loopy-owned-browser"}'], [b'ok'],
            ])
            try:
                ipc.Hyprland(path).execute({'action': 'edit', 'operation': 'zoom_in'})
            finally:
                peer.close()
            self.assertIsNone(peer.error)
            self.assertEqual(peer.requests, [
                'j/activewindow',
                "dispatch hl.dsp.send_shortcut({mods='CTRL SHIFT',key='equal',window='address:0xf00d'})",
            ])

    def test_empty_focus_cannot_send_an_edit_to_an_unselected_application(self):
        ipc = module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-edit-', dir='/tmp') as d:
            path = Path(d) / 'ctl'; peer = OwnedSocket(path, [[b'{}']])
            try:
                with self.assertRaises(ValueError):
                    ipc.Hyprland(path).execute({'action': 'edit', 'operation': 'paste'})
            finally:
                peer.close()
            self.assertEqual(peer.requests, ['j/activewindow'])

    def test_workspace_switch_and_silent_move_use_original_lua_dispatch(self):
        ipc = module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-ipc-', dir='/tmp') as d:
            path = Path(d) / 'ctl'
            peer = OwnedSocket(path, [[b'ok']] * 4)
            try:
                client = ipc.Hyprland(path)
                for job in [
                    {'action': 'workspace', 'target': '10'},
                    {'action': 'move-workspace', 'target': '2'},
                    {'action': 'workspace', 'target': 'next'},
                    {'action': 'window', 'operation': 'floating'},
                ]:
                    client.execute(job)
            finally:
                peer.close()
            self.assertIsNone(peer.error)
            self.assertEqual(peer.requests, [
                "dispatch hl.dsp.focus({workspace='10'})",
                "dispatch hl.dsp.window.move({workspace='2',follow=false})",
                "dispatch hl.dsp.focus({workspace='e+1'})",
                "dispatch hl.dsp.window.float({action='toggle'})",
            ])

    def test_fragmented_query_is_complete_and_response_size_is_bounded(self):
        ipc = module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-ipc-', dir='/tmp') as d:
            path = Path(d) / 'ctl'
            peer = OwnedSocket(path, [[b'{"id":', .02, b'10}'], [b'x' * 200]])
            try:
                self.assertEqual(ipc.Hyprland(path).query('activeworkspace'), {'id': 10})
                with self.assertRaises(ValueError):
                    ipc.Hyprland(path, reply_limit=64).query('activewindow')
            finally:
                peer.close()
            self.assertEqual(peer.requests, ['j/activeworkspace', 'j/activewindow'])

    def test_invalid_fields_and_lua_injection_never_reach_socket(self):
        ipc = module('hyprland_actions')
        client = ipc.Hyprland(Path('/tmp/loopy-never-open-this-ipc'))
        for job in [
            {'action': 'workspace', 'target': "1'}); os.execute('bad')"},
            {'action': 'move-workspace', 'target': 'next'},
            {'action': 'workspace', 'target': True},
            {'action': 'window', 'operation': 'close', 'argv': ['/bin/sh']},
            {'action': 'exec', 'command': 'bad'},
            {'action': 'ime-key', 'key': 'unrecognized'},
        ]:
            with self.subTest(job=job), self.assertRaises(ValueError):
                client.execute(job)
        with self.assertRaises(ValueError):
            client.query('rollinglog')

    def test_socket_deadline_bounds_a_peer_that_never_replies(self):
        ipc = module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-ipc-', dir='/tmp') as d:
            path = Path(d) / 'ctl'
            peer = OwnedSocket(path, [[.2]])
            started = time.monotonic()
            try:
                with self.assertRaises(TimeoutError):
                    ipc.Hyprland(path, timeout=.05).execute({'action': 'workspace', 'target': '1'})
                self.assertLess(time.monotonic() - started, .18)
            finally:
                peer.close()

    def test_worker_orders_own_jobs_and_reports_errors_without_input_content(self):
        ipc = module('hyprland_actions')
        worker = module('session_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-jobs-', dir='/tmp') as d:
            directory = Path(d); path = directory / 'ctl'
            peer = OwnedSocket(path, [[b'ok']] * 2)
            try:
                (directory / 'command-owned-0000000000000003.json').write_text(json.dumps({'action': 'workspace', 'target': '10'}))
                (directory / 'command-owned-0000000000000001.json').write_text(json.dumps({'action': 'workspace', 'target': '1'}))
                invalid = directory / 'command-owned-0000000000000002.json'
                invalid.write_text(json.dumps({'action': 'workspace', 'target': 'PRIVATE_TYPED_SENTINEL'}))
                stale = directory / 'command-previous-0000000000000000.json'
                stale.write_text(json.dumps({'action': 'workspace', 'target': '9'}))
                outside = directory / 'outside-user-document'; outside.write_text('KEEP_USER_DOCUMENT')
                link = directory / 'command-owned-0000000000000004.json'; link.symlink_to(outside)
                with worker.Worker(directory, 'owned', ipc.Hyprland(path)) as queue:
                    self.assertEqual(queue.consume(), 4)
                self.assertTrue(stale.is_file())
                self.assertEqual(outside.read_text(), 'KEEP_USER_DOCUMENT')
                self.assertFalse(link.is_symlink())
                errors = (directory / 'error-owned.log').read_text()
                self.assertIn('ValueError', errors)
                self.assertNotIn('PRIVATE_TYPED_SENTINEL', errors)
                self.assertFalse(invalid.exists())
            finally:
                peer.close()
            self.assertEqual(peer.requests, [
                "dispatch hl.dsp.focus({workspace='1'})", "dispatch hl.dsp.focus({workspace='10'})"])

    def test_duplicate_worker_cannot_consume_another_owners_queue(self):
        worker = module('session_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-hypr-jobs-', dir='/tmp') as d:
            with worker.Worker(Path(d), 'owned', None):
                with self.assertRaises(BlockingIOError):
                    worker.Worker(Path(d), 'owned', None)
            with worker.Worker(Path(d), 'owned', None):
                pass


if __name__ == '__main__':
    unittest.main()
