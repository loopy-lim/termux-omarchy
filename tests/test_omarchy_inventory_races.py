"""Real runtime-directory removals may not abort capture or authorize replacements."""
import importlib.util
from contextlib import contextmanager
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]


class InventoryRaces(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(REPO / 'termux'))
        self.addCleanup(sys.path.remove, str(REPO / 'termux'))
        spec = importlib.util.spec_from_file_location('tested_resources', REPO / 'termux/omarchy_resources.py')
        self.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.short, self.prefix = self.base / 'runtime', self.base / 'prefix'
        self.short.mkdir(mode=0o700); self.prefix.mkdir(mode=0o700)
        (self.short / 'owner.json').write_bytes(b'public owner marker')
        self.value = dict(runtime=self.m.row(self.short)[:3], display=':20', resources={},
                          directories={'.': self.m.row(self.short)[:3]})

    def capture(self):
        try: self.m.capture(self.short, self.prefix, self.value, [])
        except FileNotFoundError: self.fail('a disappearing volatile child aborted the live desktop capture')

    @contextmanager
    def metadata_race(self, callback):
        original_stat, original_lstat = os.stat, os.lstat
        with mock.patch.object(self.m.os, 'stat', side_effect=lambda p, *a, **k: callback(original_stat, p, *a, **k)), \
                mock.patch.object(self.m.os, 'lstat', side_effect=lambda p, *a, **k: callback(original_lstat, p, *a, **k)):
            yield

    def target(self, path, kw, expected):
        if kw.get('dir_fd') is None: return Path(path) == expected
        info = os.fstat(kw['dir_fd']); parent = expected.parent.stat()
        return str(path) == expected.name and (info.st_dev, info.st_ino) == (parent.st_dev, parent.st_ino)

    def test_entry_unlinked_after_enumeration_before_stat_is_skipped(self):
        leaf = self.short / 'ephemeral'; leaf.symlink_to('/never-follow-this-public-target')
        injected = False
        def race(original, path, *args, **kw):
            nonlocal injected
            if not injected and self.target(path, kw, leaf): injected = True; leaf.unlink()
            return original(path, *args, **kw)
        with self.metadata_race(race):
            try: self.capture()
            finally: self.assertTrue(injected)
        self.assertTrue(injected)
        self.assertNotIn('runtime:ephemeral', self.value['resources'])
        self.assertTrue((self.short / 'owner.json').is_file())

    def test_child_directory_removed_after_its_stat_is_not_a_parent_failure(self):
        directory = self.short / 'ephemeral'; directory.mkdir()
        injected = False
        def race(original, path, *args, **kw):
            nonlocal injected
            info = original(path, *args, **kw)
            if not injected and self.target(path, kw, directory): injected = True; directory.rmdir()
            return info
        with self.metadata_race(race):
            try: self.capture()
            finally: self.assertTrue(injected)
        self.assertTrue(injected)
        self.assertFalse(directory.exists())
        self.assertNotIn('ephemeral', self.value['directories'])

    def test_file_removed_after_one_metadata_snapshot_does_not_require_second_lstat(self):
        leaf = self.short / 'ephemeral'; leaf.write_bytes(b'public transient data')
        injected = False
        def race(original, path, *args, **kw):
            nonlocal injected
            info = original(path, *args, **kw)
            if not injected and self.target(path, kw, leaf): injected = True; leaf.unlink()
            return info
        with self.metadata_race(race):
            try: self.capture()
            finally: self.assertTrue(injected)
        self.assertTrue(injected)
        self.assertFalse(leaf.exists())

    def test_open_child_removed_during_listdir_is_skipped_only_when_absent(self):
        directory = self.short / 'ephemeral'; directory.mkdir()
        expected = self.m.row(directory)[:3]
        original = os.listdir; injected = False
        def race(path):
            nonlocal injected
            if isinstance(path, int):
                info = os.fstat(path)
                if not injected and [info.st_dev, info.st_ino, info.st_uid] == expected:
                    injected = True; directory.rmdir()
                    raise FileNotFoundError(2, 'removed public child directory')
            return original(path)
        with mock.patch.object(self.m.os, 'listdir', side_effect=race):
            try: self.capture()
            finally: self.assertTrue(injected)
        self.assertNotIn('ephemeral', self.value['directories'])
        self.assertTrue((self.short / 'owner.json').is_file())

    def test_replaced_parent_is_refused_and_its_new_entries_remain_untouched(self):
        directory = self.short / 'parent'; directory.mkdir()
        leaf = directory / 'entry'; leaf.write_bytes(b'public original')
        saved = self.short / 'retained-original'
        injected = False
        def race(original, path, *args, **kw):
            nonlocal injected
            if not injected and self.target(path, kw, leaf):
                injected = True; directory.rename(saved); directory.mkdir(); leaf.write_bytes(b'public replacement')
            return original(path, *args, **kw)
        with self.metadata_race(race):
            with self.assertRaises(self.m.ResourceFailure): self.m.capture(self.short, self.prefix, self.value, [])
        self.assertTrue(injected)
        self.assertEqual(leaf.read_bytes(), b'public replacement')
        self.assertEqual((saved / 'entry').read_bytes(), b'public original')

    def test_missing_runtime_root_is_never_treated_as_a_volatile_child(self):
        (self.short / 'owner.json').unlink(); self.short.rmdir()
        with self.assertRaises((FileNotFoundError, self.m.ResourceFailure)):
            self.m.capture(self.short, self.prefix, self.value, [])


if __name__ == '__main__': unittest.main()
