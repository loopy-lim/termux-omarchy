"""Real tmux attachment changes socket permissions without replacing its inode."""
import importlib.util
import os
from pathlib import Path
import pty
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]


class RuntimeSocketModesTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(REPO / 'termux'))
        self.addCleanup(sys.path.remove, str(REPO / 'termux'))
        spec = importlib.util.spec_from_file_location('socket_mode_resources', REPO / 'termux/omarchy_resources.py')
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory(prefix='os-', dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.short = Path(self.temp.name).resolve()
        (self.short / 'owner.json').write_text('{}')
        self.prefix = self.short.parent / (self.short.name + '-absent-prefix')
        self.value = {'runtime': self.module.row(self.short)[:3], 'display': ':98'}

    def capture(self):
        self.module.capture(self.short, self.prefix, self.value, [])

    def test_real_tmux_attach_and_detach_keep_runtime_alive_for_the_same_socket(self):
        command = shutil.which('tmux'); self.assertIsNotNone(command)
        path = self.short / 's'; env = dict(os.environ, TERM='xterm-256color')
        def tmux(*args):
            return subprocess.run([command, '-S', str(path), *args], env=env,
                                  capture_output=True, text=True, timeout=4, check=True)
        master = slave = None; client = None
        try:
            tmux('-f', '/dev/null', 'new-session', '-d', '-s', 'public-mode-check',
                 '/bin/sh -c "sleep 30"')
            self.capture(); initial = self.value['resources']['runtime:s'][:]
            master, slave = pty.openpty()
            client = subprocess.Popen([command, '-S', str(path), 'attach', '-t', 'public-mode-check'],
                                      env=env, stdin=slave, stdout=slave, stderr=slave)
            deadline = time.monotonic() + 3
            while not path.stat().st_mode & stat.S_IXUSR:
                self.assertLess(time.monotonic(), deadline); time.sleep(.02)
            self.assertEqual(self.module.row(path)[:3], initial[:3])
            try: self.capture()
            except ValueError as error:
                self.fail(f'Attaching tmux must not retire the desktop: {error}')
            self.assertEqual(self.value['resources']['runtime:s'], self.module.row(path))
            tmux('detach-client', '-s', 'public-mode-check')
            client.wait(timeout=4)
            self.capture()
            self.assertEqual(self.value['resources']['runtime:s'], self.module.row(path))
        finally:
            subprocess.run([command, '-S', str(path), 'kill-server'], env=env, capture_output=True, timeout=4)
            if client is not None and client.poll() is None: client.wait(timeout=4)
            for fd in (master, slave):
                if fd is not None: os.close(fd)

    def test_changed_inode_is_rejected_and_never_removed(self):
        path = self.short / 's'
        with socket.socket(socket.AF_UNIX) as first, socket.socket(socket.AF_UNIX) as replacement:
            first.bind(str(path)); path.chmod(0o600); self.capture(); old = self.module.row(path)
            path.unlink(); replacement.bind(str(path)); path.chmod(0o700)
            self.assertNotEqual(self.module.row(path)[1], old[1])
            with self.assertRaises(ValueError): self.capture()
            with self.assertRaises(ValueError): self.module.cleanup(self.short, self.prefix, self.value)
            self.assertTrue(path.is_socket())

    def test_group_write_permission_change_is_not_accepted_as_tmux_attachment(self):
        path = self.short / 's'
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(path)); path.chmod(0o600); self.capture()
            path.chmod(0o620)
            with self.assertRaises(ValueError): self.capture()
            self.assertTrue(path.is_socket())

    def test_retirement_accepts_the_same_socket_after_its_final_detach(self):
        path = self.short / 's'
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(path)); path.chmod(0o700); self.capture()
            path.chmod(0o600)
        try: self.module.cleanup(self.short, self.prefix, self.value)
        except ValueError as error:
            self.fail(f'Final detach must not prevent exact-inode cleanup: {error}')
        self.assertFalse(path.exists())
        self.assertTrue((self.short / 'owner.json').exists())


if __name__ == '__main__': unittest.main()
