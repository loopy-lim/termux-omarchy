"""Remote terminal inputs and recent endpoints must remain argv-only and secret-free."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import warnings
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'guest/desktop/usr/local/lib/loopy/remote_connections.py'


def helper():
    if not SOURCE.is_file():
        return None
    spec = importlib.util.spec_from_file_location('remote_connections', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RemoteConnectionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.remote = helper()

    def setUp(self):
        self.assertIsNotNone(self.remote, 'Linux remote connection helper is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.file = self.directory / 'recent.json'

    def profile(self, host='example.org', user='alice', port=22):
        return self.remote.profile(host, user, port)

    def test_remote_cli_dispatch_reaches_native_wayland_launcher(self):
        source = SOURCE.with_name('desktop_ui.py')
        spec = importlib.util.spec_from_file_location('remote_desktop_ui', source)
        ui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ui)
        with patch.object(ui.sys, 'argv', [str(source), 'remote']), \
                patch.object(ui.subprocess, 'Popen') as spawn:
            ui.main()
        spawn.assert_called_once_with(['/usr/local/bin/loopy-remote'])

    def test_normalizes_ip_and_international_dns_without_commands(self):
        self.assertEqual(self.profile('[2001:db8::1]')['host'], '2001:db8::1')
        self.assertEqual(self.profile('한글.example')['host'], 'xn--bj0bj06e.example')
        for host in ('-oProxyCommand=x', 'a;id', 'a b', 'a\nb', 'user@host', 'https://host', 'a/b', ''):
            with self.subTest(host=host), self.assertRaises(ValueError): self.profile(host)

    def test_rejects_invalid_user_and_port_before_spawning(self):
        for user in ('-o', 'alice\nbob', 'alice;id', '', 'x' * 65):
            with self.assertRaises(ValueError): self.profile(user=user)
        for port in (0, 65536, -1, True, '22;id', 22.5):
            with self.assertRaises(ValueError): self.profile(port=port)

    def test_ssh_argv_has_interactive_host_confirmation_and_keepalive(self):
        argv = self.remote.ssh_argv(self.profile(host='2001:db8::1', port=2222))
        self.assertEqual(argv[0], '/usr/bin/ssh')
        for expected in ('-t', 'StrictHostKeyChecking=ask', 'ServerAliveInterval=30', 'ServerAliveCountMax=3',
                         'ConnectTimeout=10', 'ConnectionAttempts=1'):
            self.assertIn(expected, argv)
        self.assertEqual(argv[-6:], ['-p', '2222', '-l', 'alice', '--', '2001:db8::1'])

    def test_launch_detaches_terminal_streams_and_saves_endpoint_only(self):
        with patch.object(self.remote.subprocess, 'Popen', return_value=Mock(pid=123)) as spawn:
            pid = self.remote.connect(self.profile(), self.file)
        self.assertEqual(pid, 123)
        argv, = spawn.call_args.args
        self.assertEqual(argv[0], '/usr/bin/foot')
        self.assertIn('--hold', argv)
        self.assertEqual(argv[argv.index('--') + 1], '/usr/bin/ssh')
        self.assertNotIn('shell', spawn.call_args.kwargs)
        self.assertTrue(spawn.call_args.kwargs['start_new_session'])
        for stream in ('stdin', 'stdout', 'stderr'):
            self.assertEqual(spawn.call_args.kwargs[stream], self.remote.subprocess.DEVNULL)
        self.assertEqual(json.loads(self.file.read_text()), {'schema': 1, 'profiles': [self.profile()]})
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)

    def test_failed_terminal_start_does_not_change_recent_profiles(self):
        with patch.object(self.remote.subprocess, 'Popen', side_effect=OSError('missing foot')):
            with self.assertRaises(OSError): self.remote.connect(self.profile(), self.file)
        self.assertFalse(self.file.exists())

    def test_recent_profiles_are_bounded_deduplicated_and_reconnectable(self):
        for i in range(20): self.remote.save_recent(self.file, self.profile(host=f'host{i}.example'))
        self.remote.save_recent(self.file, self.profile(host='host18.example'))
        recent = self.remote.load_recent(self.file)
        self.assertEqual(len(recent), 16)
        self.assertEqual(recent[0]['host'], 'host18.example')
        self.assertEqual(len({p['host'] for p in recent}), 16)
        self.assertEqual(set(recent[0]), {'host', 'user', 'port'})

    def test_secret_fields_or_oversized_json_are_rejected_without_overwrite(self):
        malformed = {'schema': 1, 'profiles': [dict(self.profile(), password='do-not-store')]}
        raw = json.dumps(malformed)
        self.file.write_text(raw)
        with self.assertRaises(ValueError): self.remote.save_recent(self.file, self.profile())
        self.assertEqual(self.file.read_text(), raw)
        self.file.write_bytes(b' ' * (16384 + 1))
        with self.assertRaises(ValueError): self.remote.load_recent(self.file)

    def test_recent_path_never_follows_symlink_or_parent_alias(self):
        original = self.directory / 'original'
        original.write_text('preserve')
        self.file.symlink_to(original)
        with self.assertRaises(ValueError): self.remote.save_recent(self.file, self.profile())
        self.assertEqual(original.read_text(), 'preserve')
        self.file.unlink()
        alias = self.directory / 'alias'
        alias.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises(ValueError): self.remote.save_recent(alias / 'other.json', self.profile())

    def test_unknown_top_level_metadata_does_not_become_persistent_input(self):
        self.file.write_text(json.dumps({'schema': 1, 'profiles': [], 'key': 'private'}))
        with self.assertRaises(ValueError): self.remote.load_recent(self.file)

    def test_ssh_child_uses_wayland_and_preserves_owned_home(self):
        executable = self.directory / 'terminal'
        witness = self.directory / 'witness'
        executable.write_text('#!' + sys.executable + '\nimport json,os,pathlib,sys\n'
            'pathlib.Path(os.environ["WITNESS"]).write_text(json.dumps({'
            '"backend":os.environ.get("GDK_BACKEND"),"home":os.environ["HOME"],"argv":sys.argv[1:]}))\n')
        executable.chmod(0o700)
        # The public launcher intentionally returns only the detached process ID.
        with warnings.catch_warnings(), patch.dict(os.environ, {
                'WITNESS': str(witness), 'HOME': str(self.directory), 'GDK_BACKEND': 'x11'}):
            warnings.simplefilter('ignore', ResourceWarning)
            pid = self.remote.connect(self.profile(), self.file, terminal=str(executable))
        self.assertEqual(os.waitpid(pid, 0)[1], 0)
        result = json.loads(witness.read_text())
        self.assertEqual(result['backend'], 'wayland')
        self.assertEqual(result['home'], str(self.directory))
        self.assertEqual(result['argv'][-7:], ['ConnectionAttempts=1', '-p', '22', '-l', 'alice', '--', 'example.org'])

    def test_sibling_desktop_launcher_does_not_require_legacy_usr_local_path(self):
        source = self.directory / 'remote_connections.py'
        source.write_bytes(SOURCE.read_bytes())
        desktop = self.directory / 'remote_desktop.py'
        witness = self.directory / 'desktop-witness'
        desktop.write_text('from pathlib import Path\nPath(__file__).with_name("desktop-witness").write_text("opened")\n')
        spec = importlib.util.spec_from_file_location('owned_remote', source)
        owned = importlib.util.module_from_spec(spec); spec.loader.exec_module(owned)
        child = owned.launch_remote_desktop()
        self.assertEqual(child.wait(timeout=5), 0)
        self.assertEqual(witness.read_text(), 'opened')


if __name__ == '__main__':
    unittest.main()
