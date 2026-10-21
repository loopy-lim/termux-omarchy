"""Linux ESRCH at a /proc read is exit only after the PID directory disappears."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]


class ProcessExitRaceTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('exit_race_processes', REPO / 'termux/processes.py')
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory(prefix='proc-exit-'); self.addCleanup(self.temp.cleanup)
        self.proc = Path(self.temp.name); self.pid = self.proc / '100001'; self.pid.mkdir()
        (self.pid / 'status').write_text(f'Uid:\t{os.getuid()}\t{os.getuid()}\n')
        fields = ['S', '100000', '100001', '0', '0', *(['0'] * 14), '12345', '0']
        (self.pid / 'stat').write_text('100001 (public test) ' + ' '.join(fields))
        (self.pid / 'cmdline').write_bytes(b'public-test\0')

    def test_esrch_read_after_pid_disappears_does_not_abort_strict_identity(self):
        original = Path.read_bytes
        def exited(path, *args, **kwargs):
            if path == self.pid / 'cmdline':
                shutil.rmtree(self.pid)
                raise ProcessLookupError(3, 'No such process')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_bytes', exited):
            try: value = self.module.identity(100001, self.proc, strict=True)
            except ValueError as error: self.fail(f'A disappeared PID is terminal: {error}')
        self.assertIsNone(value)

    def test_esrch_with_live_pid_directory_remains_an_unverified_identity(self):
        original = Path.read_bytes
        def unavailable(path, *args, **kwargs):
            if path == self.pid / 'cmdline': raise ProcessLookupError(3, 'No such process')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_bytes', unavailable):
            with self.assertRaisesRegex(ValueError, 'identity.*verified'):
                self.module.identity(100001, self.proc, strict=True)
        self.assertTrue(self.pid.exists())

    def test_permission_error_with_a_live_pid_is_not_an_exit(self):
        original = Path.read_bytes
        def denied(path, *args, **kwargs):
            if path == self.pid / 'cmdline': raise PermissionError(13, 'Permission denied')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_bytes', denied):
            with self.assertRaisesRegex(ValueError, 'identity.*verified'):
                self.module.identity(100001, self.proc, strict=True)

    def test_esrch_during_snapshot_enumeration_skips_only_a_disappeared_pid(self):
        original = Path.read_text
        def exited(path, *args, **kwargs):
            if path == self.pid / 'status':
                shutil.rmtree(self.pid)
                raise ProcessLookupError(3, 'No such process')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', exited):
            try: result = self.module.snapshot(self.proc)
            except OSError as error: self.fail(f'An exited enumeration entry is normal: {error}')
        self.assertEqual(result, {})


if __name__ == '__main__': unittest.main()
