import http.server
import importlib
import json
import os
import socket
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'termux'))
web = importlib.import_module('omarchy_code_web')
profiles = importlib.import_module('omarchy_code_profile')


class CodeWebTests(unittest.TestCase):
    def test_restart_accepts_time_wait_but_rejects_live_listener(self):
        with socket.socket() as listener, tempfile.TemporaryDirectory() as directory:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(('127.0.0.1', 0)); listener.listen()
            port = listener.getsockname()[1]
            with patch.object(web, 'PORT', port), patch.object(web.subprocess, 'Popen') as spawn:
                with self.assertRaises(OSError): web.ensure_backend(Path(directory), 'session', {})
                spawn.assert_not_called()
            with socket.create_connection(('127.0.0.1', port)) as client:
                accepted, _ = listener.accept()
                accepted.close()
                self.assertEqual(client.recv(1), b'')
        with tempfile.TemporaryDirectory() as directory, patch.object(web, 'PORT', port), \
                patch.object(web.subprocess, 'Popen', side_effect=ValueError('test-spawn-reached')) as spawn:
            with self.assertRaisesRegex(ValueError, 'test-spawn-reached'):
                web.ensure_backend(Path(directory), 'session', {})
            spawn.assert_called_once()

    def test_authenticated_readiness_requires_rejection_of_wrong_token(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            accept_all = False
            def do_GET(self):
                valid = self.accept_all or self.headers.get('Cookie') == 'vscode-tkn=correct'
                self.send_response(200 if valid else 403); self.end_headers()
                self.wfile.write(b'vscode-workbench-web-configuration' if valid else b'Forbidden')
            def log_message(self, *_): pass
        server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            self.assertTrue(web.authenticated_ready('correct', server.server_port))
            Handler.accept_all = True
            self.assertFalse(web.authenticated_ready('correct', server.server_port))
        finally:
            server.shutdown(); thread.join(); server.server_close()

    def test_unowned_live_backend_never_spawns_or_signals(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            web.atomic(base / 'backend.json', {'session': 'old', 'args': [], 'process': {'pid': 99}})
            with patch.object(web, 'identity', return_value={'pid': 99}), \
                    patch.object(web.subprocess, 'Popen') as spawn:
                with self.assertRaisesRegex(ValueError, 'existing-unowned'):
                    web.ensure_backend(base, 'new', {})
                spawn.assert_not_called()

    def test_profile_export_preserves_jsonc_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); source = root / 'User'; source.mkdir()
            original = '// custom\n{"editor.fontSize": 17,}\n'
            (source / 'settings.json').write_text(original)
            (source / 'keybindings.json').write_text('[{"key":"ctrl+k","command":"custom"}]')
            (source / 'snippets').mkdir(); (source / 'snippets/python.json').write_text('{"test":{}}')
            target = profiles.export_profile(source, root / 'export')
            data = json.loads(target.read_text())
            self.assertEqual(json.loads(data['settings'])['settings'], original)
            self.assertEqual(json.loads(data['snippets'])['snippets']['python.json'], '{"test":{}}')
            self.assertEqual(profiles.export_profile(source, root / 'export'), target)
            target.write_text('user edited export')
            with self.assertRaisesRegex(ValueError, 'collision'):
                profiles.export_profile(source, root / 'export')
            self.assertEqual((source / 'settings.json').read_text(), original)
            self.assertEqual(target.read_text(), 'user edited export')

    def test_private_storage_rejects_symlink_and_public_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); token = root / 'token'
            token.write_text('a' * 64); token.chmod(0o644)
            with self.assertRaises(ValueError): web.read_private(token)
            link = root / 'link'; link.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError): web.private_dir(link / 'nested')

    def test_reused_pid_cannot_match_old_identity(self):
        first = {'pid': 2, 'pgid': 2, 'starttime': '10', 'uid': 1000, 'command': ['server']}
        self.assertFalse(web.same(first, dict(first, starttime='20')))
        self.assertFalse(web.same(first, dict(first, command=['other'])))

if __name__ == '__main__': unittest.main()
