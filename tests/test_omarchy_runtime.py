"""Actual runtime environment regression; ROOT alone executes this harness."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import json
import os
import socket
import uuid
import inspect

REPO = Path(__file__).resolve().parents[1]
NEW = REPO / 'termux/omarchy_runtime.py'


class RuntimeEnvironmentTests(unittest.TestCase):
    def runtime(self, home, prefix):
        # Missing new implementation uses the actual shipped i3 environment,
        # so RED is a behavior mismatch rather than an absent API/import error.
        source = NEW if NEW.exists() else REPO / 'termux/runtime.py'
        import sys
        sys.path.insert(0, str(REPO / 'termux'))
        try:
            spec = importlib.util.spec_from_file_location('owned_omarchy_test', source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.Runtime(home, prefix)
        finally:
            sys.path.pop(0)

    def test_native_environment_does_not_force_software_or_x11_on_guest_apps(self):
        with tempfile.TemporaryDirectory() as temp:
            home, prefix = Path(temp) / 'home', Path(temp) / 'usr'
            home.mkdir(); prefix.mkdir()
            runtime = self.runtime(home, prefix)
            self.assertNotEqual(runtime.env.get('LIBGL_ALWAYS_SOFTWARE'), 'true',
                                'Omarchy must not inherit the old software i3 profile')
            self.assertNotEqual(runtime.env.get('GDK_BACKEND'), 'x11',
                                'guest native applications must use Wayland')

    def test_private_weston14_loader_is_selected_instead_of_global_weston16(self):
        with tempfile.TemporaryDirectory() as temp:
            home, prefix = Path(temp) / 'home', Path(temp) / 'usr'
            home.mkdir(); prefix.mkdir()
            runtime = self.runtime(home, prefix)
            managed = home.resolve() / '.local/share/loopy-omarchy/weston-host'
            expected = ':'.join(str(p) for p in
                                (managed / 'lib/weston', managed / 'lib', prefix.resolve() / 'lib'))
            self.assertEqual(runtime.env.get('LD_LIBRARY_PATH'), expected,
                             'bundled libweston14 backend requires a private ABI14 loader')

    def cleanup_fixture(self, temp):
        home, prefix = Path(temp) / 'home', Path(temp) / 'usr'
        home.mkdir(); prefix.mkdir()
        runtime = self.runtime(home, prefix)
        runtime.short = Path(temp) / 'owned-runtime'
        runtime.short.mkdir(mode=0o700)
        token = str(uuid.uuid4())
        item = runtime.short.stat()
        value = {'token': token, 'display': ':20', 'runtime': [item.st_dev, item.st_ino, os.getuid()],
                 'resources': {}, 'directories': {'.': [item.st_dev, item.st_ino, os.getuid()]}}
        (runtime.short / 'owner.json').write_text(json.dumps({'token': token}))
        runtime.state = lambda: value
        return runtime, value

    def test_cleanup_removes_only_recorded_owned_socket_after_retirement(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, value = self.cleanup_fixture(temp)
            path = runtime.short / 'wayland-omarchy'
            with socket.socket(socket.AF_UNIX) as child:
                child.bind(str(path))
                item = path.lstat()
                value['resources']['runtime:wayland-omarchy'] = [item.st_dev, item.st_ino,
                                                               item.st_uid, item.st_mode]
            # Retained native child has exited/reaped; this test owns no guest process.
            try:
                runtime.clear_runtime(value)
            except ValueError as error:
                raise AssertionError('known own socket retirement was refused') from error
            self.assertFalse(path.exists(), 'known own leftover socket must be cleaned after retirement')
            self.assertTrue((runtime.short / 'owner.json').is_file(), 'retained owner marker permits safe restart')

    def test_cleanup_refuses_replacement_inode_and_preserves_unowned_other_display(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, value = self.cleanup_fixture(temp)
            path = runtime.short / 'wayland-omarchy'
            foreign = runtime.prefix / 'tmp/.X11-unix/X21'
            foreign.parent.mkdir(parents=True)
            foreign.write_bytes(b'other-display')
            with socket.socket(socket.AF_UNIX) as old:
                old.bind(str(path))
                item = path.lstat()
                value['resources']['runtime:wayland-omarchy'] = [item.st_dev, item.st_ino,
                                                               item.st_uid, item.st_mode]
                path.unlink()
                with socket.socket(socket.AF_UNIX) as replacement:
                    replacement.bind(str(path))
                    with self.assertRaises(ValueError):
                        runtime.clear_runtime(value)
                    self.assertTrue(path.exists(), 'replacement socket must never be removed')
            self.assertEqual(foreign.read_bytes(), b'other-display')

    def test_same_uid_foreign_x_server_cannot_be_adopted_after_display_selection_race(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, value = self.cleanup_fixture(temp)
            path = runtime.prefix / 'tmp/.X11-unix/X20'
            path.parent.mkdir(parents=True)
            capture = runtime.clear_runtime.__globals__['capture']
            with socket.socket(socket.AF_UNIX) as foreign:
                foreign.bind(str(path)); foreign.listen(1)
                try:
                    # Old API exercises the actual unsafe capture. New API
                    # receives the empty set of owned descendants, not caller UID.
                    if len(inspect.signature(capture).parameters) == 3:
                        capture(runtime.short, runtime.prefix, value)
                    else:
                        capture(runtime.short, runtime.prefix, value, [])
                except ValueError:
                    pass
                self.assertNotIn('x-socket', value['resources'],
                                 'same-UID foreign Xserver was adopted after the free-display check')
                self.assertTrue(path.is_socket(), 'unknown foreign Xsocket must be preserved')

    def test_owned_quickshell_symlink_cleanup_never_follows_or_deletes_its_target(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, value = self.cleanup_fixture(temp)
            directory = runtime.short / 'quickshell/by-id'
            directory.mkdir(parents=True)
            target = Path(temp) / 'preserved-user-file'
            target.write_bytes(b'never-traverse')
            link = directory / 'own-fixture'
            link.symlink_to(target)
            capture = runtime.clear_runtime.__globals__['capture']
            try:
                capture(runtime.short, runtime.prefix, value, [])
                runtime.clear_runtime(value)
            except ValueError as error:
                raise AssertionError('legitimate owned runtime symlink was refused') from error
            self.assertFalse(os.path.lexists(link), 'only the recorded link inode should be removed')
            self.assertEqual(target.read_bytes(), b'never-traverse', 'link target must be preserved')

    def test_x_socket_replacement_after_authenticated_peer_is_not_registered(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, value = self.cleanup_fixture(temp)
            path = runtime.prefix / 'tmp/.X11-unix/X20'
            path.parent.mkdir(parents=True)
            capture = runtime.clear_runtime.__globals__['capture']
            globals_ = capture.__globals__
            original_peer = globals_['live_peer']
            with socket.socket(socket.AF_UNIX) as own, socket.socket(socket.AF_UNIX) as foreign:
                own.bind(str(path)); own.listen(1)
                def authenticated_then_replaced(path_, records):
                    path_.unlink()
                    foreign.bind(str(path_)); foreign.listen(1)
                    return {'pid': 42}  # Lower-level authentication completed before replacement.
                globals_['live_peer'] = authenticated_then_replaced
                try:
                    try:
                        capture(runtime.short, runtime.prefix, value, [{'pid': 42}])
                    except ValueError:
                        pass
                    self.assertNotIn('x-socket', value['resources'],
                                     'inode replaced after authentication must not be registered')
                    self.assertTrue(path.is_socket(), 'unverified replacement must remain untouched')
                finally:
                    globals_['live_peer'] = original_peer



class RecoveryGuidanceTests(unittest.TestCase):
    def module(self):
        import sys
        sys.path.insert(0, str(REPO / 'termux'))
        try:
            spec = importlib.util.spec_from_file_location('recovery_guidance_test', NEW)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        finally:
            sys.path.pop(0)

    def dead_session(self, **overrides):
        value = {'phase': 'ready', 'processes': [{'pid': 40, 'pgid': 40}],
                 'terminationConfirmed': False, 'reason': 'runtime-operation-failed'}
        value.update(overrides)
        return value

    def test_fixed_guidance_covers_every_refusal_family(self):
        m = self.module()
        dead = [False]
        cases = [
            (self.dead_session(), [True], True, 'none'),
            ({'phase': 'stopped', 'processes': [{'pid': 40, 'pgid': 40}],
              'terminationConfirmed': True, 'reason': 'clean'}, [False], False, 'none'),
            (self.dead_session(reason='boot-regular-unrecorded'), [False], False, 'retry-after-reboot'),
            (self.dead_session(), [False], False, 'reboot-and-start'),
            (self.dead_session(processes=[{'pid': 40, 'pgid': 40}, {'pid': 41, 'pgid': 41}]),
             [True, False], False, 'stop-then-start'),
            ({'phase': 'starting', 'processes': [{'pid': 40, 'pgid': 40}],
              'terminationConfirmed': False, 'reason': 'starting'}, [True], False, 'retry-start'),
        ]
        for value, live, ready, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(m.recovery_guidance(value, live, ready), expected)

    def test_live_ready_state_reports_none_and_live_list_length_is_respected(self):
        m = self.module()
        value = self.dead_session()
        self.assertEqual(m.recovery_guidance(value, [True], False), 'stop-then-start')

if __name__ == '__main__':
    unittest.main()
