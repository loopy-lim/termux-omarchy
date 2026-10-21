"""Exercise native/isolated guest selection with real pinned artifact files."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'termux'))
from omarchy_runtime import Runtime

ARTIFACTS = REPO / 'build/diagnostics/termux-omarchy-proot-private-runpath-build-20261009-01/arm64-v8a'
FILES = ('proot', 'loader', 'libandroid-shmem.so')


def stamp(path):
    row = path.lstat()
    return [row.st_dev, row.st_ino, row.st_uid]


def guard_fixture(runtime):
    target = runtime.root / 'proot-guard'
    target.mkdir(mode=0o700)
    pins = {}
    for name in FILES:
        shutil.copyfile(ARTIFACTS / name, target / name)
        (target / name).chmod(0o700 if name != 'libandroid-shmem.so' else 0o600)
        pins[name] = hashlib.sha256((target / name).read_bytes()).hexdigest()
    row = {'schema': 1, 'phase': 'INSTALLED', 'uid': os.getuid(),
           'root': stamp(runtime.root), 'directory': stamp(target), 'files': pins}
    path = runtime.root / 'proot-guard.json'
    path.write_text(json.dumps(row)); path.chmod(0o600)
    return target


class ProotSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        p = Path(self.temp.name)
        home, prefix = p / 'home', p / 'usr'
        home.mkdir(); prefix.mkdir()
        self.runtime = Runtime(home, prefix)
        self.value = {'display': ':20', 'token': 'public-fixture', 'width': 1920, 'height': 1280}

    def test_ambient_proot_switches_cannot_disable_or_replace_managed_selection(self):
        original = os.environ.copy()
        try:
            os.environ.update(PD_PROOT_BIN='/foreign/proot', PROOT_LOADER='/foreign/loader', PROOT_EXITKILL='0')
            runtime = Runtime(self.runtime.home, self.runtime.prefix)
        finally:
            os.environ.clear(); os.environ.update(original)
        for key in ('PD_PROOT_BIN', 'PROOT_LOADER', 'PROOT_EXITKILL'):
            self.assertFalse(key in runtime.env, key + ' must not be inherited')

    def test_private_guard_survives_isolated_guest_environment_reconstruction(self):
        target = guard_fixture(self.runtime)
        commands = self.runtime.commands(self.value)
        args, env = commands[2]
        self.assertEqual(env.get('PD_PROOT_BIN'), str(target / 'proot'))
        extras = {args[i + 1].split('=', 1)[0]: args[i + 1].split('=', 1)[1]
                  for i, value in enumerate(args) if value == '-e'}
        self.assertEqual(extras.get('PROOT_EXITKILL'), '1')
        self.assertEqual(extras.get('PROOT_LOADER'), str(target / 'loader'))
        self.assertFalse('PD_PROOT_BIN' in commands[0][1])
        self.assertFalse('PROOT_EXITKILL' in commands[1][1])
        self.assertIn('/opt/omarchy-android/mesa/root/usr/lib', extras['LD_LIBRARY_PATH'])

    def test_guest_temp_sockets_use_the_short_bound_runtime_directory(self):
        guard_fixture(self.runtime)
        commands = self.runtime.commands(self.value)
        args, _ = commands[2]
        extras = {args[i + 1].split('=', 1)[0]: args[i + 1].split('=', 1)[1]
                  for i, value in enumerate(args) if value == '-e'}
        self.assertEqual(extras.get('TMPDIR'), '/run/user/1000')
        self.assertEqual(commands[0][1]['TMPDIR'], str(self.runtime.prefix / 'tmp'))

    def test_recorded_guarded_session_never_falls_back_after_guard_removal(self):
        target = guard_fixture(self.runtime)
        shutil.rmtree(target)
        (self.runtime.root / 'proot-guard.json').unlink()
        with self.assertRaises(ValueError):
            self.runtime.commands(dict(self.value, prootExitKillRequested=True))

    def test_recorded_legacy_session_does_not_switch_tracers_mid_session(self):
        guard_fixture(self.runtime)
        with self.assertRaises(ValueError):
            self.runtime.commands(dict(self.value, prootExitKillRequested=False))

    def test_invalid_guard_does_not_leave_unowned_runtime_after_start_failure(self):
        from unittest.mock import patch
        import uuid
        target = guard_fixture(self.runtime)
        (target / 'proot').write_bytes(b'changed')
        self.runtime.short = Path(self.temp.name) / 'runtime'
        request = str(uuid.uuid4())
        with patch('omarchy_runtime.prepare_start', return_value='public-boot'), \
                patch.object(self.runtime, 'installed'), \
                patch.object(self.runtime, 'choose_display', return_value=':20'):
            with self.assertRaises(ValueError):
                self.runtime.start(request)
        self.assertFalse(self.runtime.short.exists(), 'failed guard preflight stranded runtime directory')
        self.assertFalse((self.runtime.root / 'sessions' / request).exists())

    def test_tampered_private_proot_is_refused_instead_of_falling_back(self):
        target = guard_fixture(self.runtime)
        (target / 'proot').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.runtime.commands(self.value)

    def test_missing_private_loader_is_refused_instead_of_falling_back(self):
        target = guard_fixture(self.runtime)
        (target / 'loader').unlink()
        with self.assertRaises(ValueError):
            self.runtime.commands(self.value)

    def test_replaced_private_directory_is_not_adopted(self):
        target = guard_fixture(self.runtime)
        target.rename(target.with_name('preserved-guard'))
        shutil.copytree(target.with_name('preserved-guard'), target)
        with self.assertRaises(ValueError):
            self.runtime.commands(self.value)

    def test_symlink_library_is_never_followed(self):
        target = guard_fixture(self.runtime)
        library = target / 'libandroid-shmem.so'
        before = library.read_bytes()
        preserved = self.runtime.root / 'preserved-library'
        library.rename(preserved); library.symlink_to(preserved)
        with self.assertRaises(ValueError):
            self.runtime.commands(self.value)
        self.assertEqual(preserved.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
