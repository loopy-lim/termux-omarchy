"""Real owned runtime FIFOs are metadata, never streams opened by the supervisor."""
import importlib.util
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]


class RuntimeFIFOTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(REPO / 'runtime'))
        self.addCleanup(sys.path.remove, str(REPO / 'runtime'))
        spec = importlib.util.spec_from_file_location('fifo_resources', REPO / 'runtime/omarchy_resources.py')
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory(prefix='of-', dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.short, self.prefix = self.base / 'r', self.base / 'u'
        self.short.mkdir(mode=0o700); self.prefix.mkdir(mode=0o700)
        (self.short / 'owner.json').write_bytes(b'public owned marker')
        self.value = dict(runtime=self.metadata(self.short)[:3], display=':98')

    @staticmethod
    def metadata(path):
        value = path.lstat()
        return [value.st_dev, value.st_ino, value.st_uid, value.st_mode]

    def fifo(self, name='public-pipe'):
        path = self.short / name; os.mkfifo(path, mode=0o700)
        return path

    def capture(self):
        try: self.module.capture(self.short, self.prefix, self.value, [])
        except self.module.ResourceFailure as error:
            self.fail(f'An owned FIFO must not retire the live desktop: {error}')

    def forbid_fifo_streams(self):
        original = os.open
        def guarded(path, flags, *args, **kwargs):
            if isinstance(path, (str, bytes, os.PathLike)):
                candidate = Path(os.fsdecode(path))
                if not kwargs.get('dir_fd') and candidate.exists() and stat.S_ISFIFO(candidate.lstat().st_mode):
                    self.fail('The supervisor tried to open a FIFO stream')
                if kwargs.get('dir_fd') and not candidate.is_absolute():
                    info = os.stat(path, dir_fd=kwargs['dir_fd'], follow_symlinks=False)
                    if stat.S_ISFIFO(info.st_mode): self.fail('The supervisor tried to open a FIFO stream')
            return original(path, flags, *args, **kwargs)
        return patch.object(self.module.os, 'open', side_effect=guarded)

    def test_four_root_fifos_are_captured_without_open_or_read(self):
        paths = [self.fifo('public-pipe-' + str(index)) for index in range(4)]
        expected = {path.name: self.metadata(path) for path in paths}
        with self.forbid_fifo_streams(), patch.object(self.module.os, 'read', side_effect=AssertionError('FIFO read')):
            self.capture()
        self.assertEqual(self.value.get('fifoResources'), expected)
        self.assertEqual(self.value['regularResources'], {})
        self.assertTrue(all(path.exists() and path.is_fifo() for path in paths))

    def test_fifo_snapshot_refreshes_after_normal_recreate_and_removal(self):
        path = self.fifo(); self.capture(); original = self.value['fifoResources'][path.name]
        path.rename(self.base / 'retained-original'); self.fifo(); self.capture()
        self.assertNotEqual(original[1], self.value['fifoResources'][path.name][1])
        self.assertEqual(self.value['fifoResources'][path.name], self.metadata(path))
        path.unlink(); self.capture()
        self.assertEqual(self.value['fifoResources'], {})

    def test_fifo_count_is_bounded(self):
        for index in range(257): self.fifo('public-pipe-' + str(index))
        with self.assertRaisesRegex(self.module.ResourceFailure, 'fifo-resource-count'):
            self.module.capture(self.short, self.prefix, self.value, [])
        self.assertEqual(sum(path.is_fifo() for path in self.short.iterdir()), 257)

    def test_confirmed_retirement_unlinks_fifo_metadata_without_opening_stream(self):
        path = self.fifo(); self.capture()
        # cleanup is the existing leaf seam; Runtime.retire supplies ECHILD/log proof.
        with self.forbid_fifo_streams(), patch.object(self.module.os, 'read', side_effect=AssertionError('FIFO read')):
            self.module.cleanup(self.short, self.prefix, self.value)
        self.assertFalse(path.exists())
        self.assertEqual({path.name for path in self.short.iterdir()}, {'owner.json'})

    def test_boot_cleanup_removes_only_exact_recorded_fifo(self):
        path = self.fifo(); self.capture()
        self.module.cleanup(self.short, self.prefix, dict(self.value, _bootRegularWitness=True))
        self.assertFalse(path.exists()); self.assertTrue((self.short / 'owner.json').exists())

    def test_boot_cleanup_unknown_fifo_refuses_before_any_removal(self):
        preserved = self.short / 'public-recorded-file'; preserved.write_bytes(b'preserve')
        self.capture(); path = self.fifo()
        with self.assertRaisesRegex(self.module.ResourceFailure, 'boot-fifo-changed'):
            self.module.cleanup(self.short, self.prefix, dict(self.value, _bootRegularWitness=True))
        self.assertTrue(path.is_fifo()); self.assertEqual(preserved.read_bytes(), b'preserve')

    def test_boot_cleanup_replaced_fifo_refuses_before_any_removal(self):
        preserved = self.short / 'public-recorded-file'; preserved.write_bytes(b'preserve')
        path = self.fifo(); self.capture()
        path.rename(self.base / 'retained-original'); replacement = self.fifo()
        with self.assertRaisesRegex(self.module.ResourceFailure, 'boot-fifo-changed'):
            self.module.cleanup(self.short, self.prefix, dict(self.value, _bootRegularWitness=True))
        self.assertTrue(replacement.is_fifo()); self.assertEqual(preserved.read_bytes(), b'preserve')

    def test_fifo_replacement_during_unlink_recheck_is_preserved(self):
        path = self.fifo(); self.capture(); original = self.module.row; replaced = False
        def race(candidate):
            nonlocal replaced
            if Path(candidate) == path and not replaced:
                replaced = True; path.rename(self.base / 'retained-original'); self.fifo()
            return original(candidate)
        with patch.object(self.module, 'row', side_effect=race):
            with self.assertRaisesRegex(self.module.ResourceFailure, 'runtime-entry-changed'):
                self.module.cleanup(self.short, self.prefix, self.value)
        self.assertTrue(replaced); self.assertTrue(path.is_fifo())
        self.assertTrue((self.base / 'retained-original').is_fifo())

    def test_critical_socket_replacement_stays_refused(self):
        path = self.short / 'wayland-omarchy'
        with socket.socket(socket.AF_UNIX) as first, socket.socket(socket.AF_UNIX) as second:
            first.bind(str(path)); self.capture(); path.rename(self.base / 'retained-socket')
            second.bind(str(path))
            with self.assertRaisesRegex(self.module.ResourceFailure, 'resource-replaced'):
                self.module.capture(self.short, self.prefix, self.value, [])
            self.assertTrue(path.is_socket())


if __name__ == '__main__': unittest.main()
