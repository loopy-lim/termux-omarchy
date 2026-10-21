"""Native-client boundaries: endpoint injection, secret storage and file ownership."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'guest/desktop/usr/local/lib/loopy/remote_desktop.py'


class RemoteDesktopTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), 'native RDP/VNC integration is missing')
        spec = importlib.util.spec_from_file_location('remote_desktop', MODULE)
        self.remote = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.remote)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()

    def test_ipv6_windows_identity_and_native_settings(self):
        value = self.remote.profile('RDP', '[2001:db8::1]', 'DOMAIN\\user', '3389')
        text = self.remote.connection_text(value)
        self.assertIn('server=[2001:db8::1]:3389\n', text)
        self.assertIn('username=DOMAIN\\\\user\n', text)
        self.assertIn('disablepasswordstoring=1\n', text)
        self.assertIn('ignore-tls-errors=0\n', text)
        self.assertIn('disableclipboard=1\n', text)
        self.assertIn('sharefolder=\n', text)
        self.assertNotIn('password=', text)

    def test_vnc_uses_absolute_port_and_scaling(self):
        text = self.remote.connection_text(self.remote.profile('VNC', 'localhost', '', 5901))
        self.assertIn('server=localhost:5901\n', text)
        self.assertIn('scale=1\n', text)
        self.assertIn('protocol=VNC\n', text)

    def test_injection_and_secret_fields_are_rejected(self):
        for args in [('SSH', 'host', '', 22), ('RDP', '-option', '', 3389),
                     ('VNC', 'host\npassword=secret', '', 5900),
                     ('RDP', 'host', 'u\npassword=secret', 3389),
                     ('RDP', 'host', 'u', True), ('VNC', 'fe80::1%eth0', '', 5900)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.remote.profile(*args)
        endpoint = self.remote.profile('RDP', 'host', 'user', 3389)
        with self.assertRaises(ValueError):
            self.remote.connection_text(dict(endpoint, password='secret'))

    def test_actual_child_receives_wayland_and_only_profile_path(self):
        executable = self.directory / 'client'
        witness = self.directory / 'witness'
        executable.write_text('#!/usr/bin/env python3\nimport os,sys,pathlib\n'
                              'pathlib.Path(os.environ["WITNESS"]).write_text('
                              'os.environ.get("GDK_BACKEND","")+"\\n"+"\\n".join(sys.argv[1:]))\n')
        executable.chmod(0o700)
        endpoint = self.remote.profile('RDP', '127.0.0.1', 'user', 3389)
        child, path = self.remote.connect(endpoint, self.directory / 'profiles',
                                         executable=str(executable), extra_env={'WITNESS': str(witness)})
        self.assertEqual(child.wait(timeout=5), 0)
        self.assertEqual(witness.read_text().splitlines(),
                         ['wayland', '--disable-news', '--no-tray-icon', '--connect', str(path)])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertIn('username=user', path.read_text())
        self.assertNotIn('password=', path.read_text())

    def test_symlink_never_overwrites_external_file(self):
        endpoint = self.remote.profile('VNC', 'localhost', '', 5900)
        folder = self.directory / 'profiles'
        folder.mkdir()
        victim = self.directory / 'victim'
        victim.write_text('preserve')
        path = self.remote.profile_path(folder, endpoint)
        path.symlink_to(victim)
        with self.assertRaises(ValueError):
            self.remote.connect(endpoint, folder, executable='/usr/bin/true')
        self.assertEqual(victim.read_text(), 'preserve')
        alias = self.directory / 'alias'
        alias.symlink_to(folder, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.remote.connect(endpoint, alias, executable='/usr/bin/true')

    def test_client_start_failure_removes_new_profile(self):
        endpoint = self.remote.profile('RDP', 'host', 'user', 3389)
        folder = self.directory / 'profiles'
        with self.assertRaises(OSError):
            self.remote.connect(endpoint, folder, executable=str(self.directory / 'missing'))
        self.assertFalse(self.remote.profile_path(folder, endpoint).exists())

    def test_existing_user_profile_is_preserved_before_any_client_launch(self):
        endpoint = self.remote.profile('RDP', 'host', 'user', 3389)
        folder = self.directory / 'profiles'; folder.mkdir()
        path = self.remote.profile_path(folder, endpoint)
        original = '[remmina]\npassword=USER_MANAGED_PRIVATE_VALUE\n'
        path.write_text(original)
        with self.assertRaises(ValueError):
            self.remote.connect(endpoint, folder, executable='/usr/bin/true')
        self.assertEqual(path.read_text(), original)

    def test_reconnecting_preserves_existing_identical_profile_bytes_and_timestamp(self):
        endpoint = self.remote.profile('VNC', 'localhost', '', 5900)
        folder = self.directory / 'profiles'; folder.mkdir()
        path = self.remote.profile_path(folder, endpoint)
        path.write_text(self.remote.connection_text(endpoint)); path.chmod(0o600)
        os.utime(path, ns=(1000000000, 1000000000))
        before = path.stat()
        child, opened = self.remote.connect(endpoint, folder, executable='/usr/bin/true')
        self.assertEqual(child.wait(timeout=5), 0)
        self.assertEqual(opened, path)
        self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(path.stat().st_ino, before.st_ino)

    def test_signed_extension_library_paths_apply_to_client_child_only(self):
        runtime = self.directory / 'runtime'
        executable = runtime / 'usr/bin/remmina'; executable.parent.mkdir(parents=True)
        witness = self.directory / 'extension-witness'
        executable.write_text('#!/usr/bin/env python3\nimport json,os,pathlib\n'
            'pathlib.Path(os.environ["WITNESS"]).write_text(json.dumps({'
            'k:os.environ[k] for k in ["GDK_BACKEND","LD_LIBRARY_PATH","XDG_DATA_DIRS","HOME"]}))\n')
        executable.chmod(0o700)
        before = dict(os.environ)
        endpoint = self.remote.profile('VNC', 'localhost', '', 5900)
        child, _ = self.remote.connect(endpoint, self.directory / 'profiles', runtime=runtime,
            extra_env={'WITNESS': str(witness), 'LD_LIBRARY_PATH': '/existing/lib', 'XDG_DATA_DIRS': '/existing/share'})
        self.assertEqual(child.wait(timeout=5), 0)
        import json
        result = json.loads(witness.read_text())
        self.assertEqual(result['GDK_BACKEND'], 'wayland')
        self.assertEqual(result['LD_LIBRARY_PATH'], str(runtime / 'usr/lib') + ':/existing/lib')
        self.assertEqual(result['XDG_DATA_DIRS'], str(runtime / 'usr/share') + ':/existing/share')
        self.assertEqual(result['HOME'], before['HOME'])
        self.assertEqual(dict(os.environ), before)

    def test_profile_publication_does_not_require_android_denied_hardlinks(self):
        endpoint = self.remote.profile('VNC', 'localhost', '', 5900)
        with patch.object(self.remote.os, 'link', side_effect=PermissionError('Android SELinux rejects link(2)')):
            child, path = self.remote.connect(endpoint, self.directory / 'profiles', executable='/usr/bin/true')
            self.assertEqual(child.wait(timeout=5), 0)
        self.assertIn('protocol=VNC\n', path.read_text())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
