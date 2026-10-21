"""Real child argv/fatal plus injected read-only Linux process/window observations.

No GTK, JVM, SDK, device, URL fetch or user profile is required. Observations are
not proof of actual compositor presentation or browser sandbox support.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'android/assets/omarchy-bridge'


def module(name):
    spec = importlib.util.spec_from_file_location('loopy_browser_test_' + name, ASSETS / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(value)
    finally:
        sys.dont_write_bytecode = previous
    return value


STATE = module('browser_state')
SUID = (b'[17:17:1008/050851.590572:FATAL:sandbox/linux/suid/client/setuid_sandbox_host.cc:166] '
        b'The SUID sandbox helper binary was found, but is not configured correctly. '
        b'Rather than run without sandboxing I\'m aborting now.\n')
USERNS = (b'[17:17:1008/050851.590572:FATAL:content/browser/zygote_host/zygote_host_impl_linux.cc:129] '
          b'No usable sandbox!\n')


def processes():
    return {17: {'pid': 17, 'uid': 10330, 'birth': 100, 'ppid': 3, 'state': 'S'}}


def native_window(pid=17):
    return {'pid': pid, 'mapped': True, 'hidden': False, 'xwayland': False}


class BrowserStartupStateTests(unittest.TestCase):
    def attempt(self):
        return STATE.Startup(17, 10330, 100, started=10.0, timeout=20.0)

    def test_own_native_window_is_ready_with_one_clock_duration(self):
        attempt = self.attempt()
        self.assertEqual(attempt.observe(10.25, None, None, processes(), [native_window()]), 'READY')
        self.assertEqual(attempt.elapsed_ms, 250.0)

    def test_verified_descendant_can_own_the_browser_window(self):
        rows = processes()
        rows[18] = {'pid': 18, 'uid': 10330, 'birth': 101, 'ppid': 17, 'state': 'S'}
        self.assertEqual(self.attempt().observe(10.5, None, None, rows, [native_window(18)]), 'READY')

    def test_reused_pid_or_wrong_uid_cannot_be_ready(self):
        for change in ({'birth': 101}, {'uid': 2000}, {'state': 'Z'}, {'pid': 99}):
            with self.subTest(change=change):
                rows = processes(); rows[17].update(change)
                self.assertEqual(self.attempt().observe(10.5, None, None, rows, [native_window()]),
                                 'PROCESS_CHANGED')

    def test_foreign_descendant_and_unrelated_browser_window_are_not_ready(self):
        for change in ({'ppid': 3}, {'uid': 2000}, {'birth': 99}, {'state': 'Z'}):
            with self.subTest(change=change):
                rows = processes()
                rows[18] = {'pid': 18, 'uid': 10330, 'birth': 101, 'ppid': 17, 'state': 'S'}
                rows[18].update(change)
                self.assertEqual(self.attempt().observe(10.5, None, None, rows, [native_window(18)]),
                                 'PENDING')

    def test_xwayland_hidden_unmapped_and_malformed_windows_are_not_ready(self):
        for change in ({'xwayland': True}, {'hidden': True}, {'mapped': False},
                       {'pid': True}, {'mapped': 1}, {'hidden': 0}, {'xwayland': 0}):
            with self.subTest(change=change):
                row = native_window(); row.update(change)
                self.assertEqual(self.attempt().observe(10.5, None, None, processes(), [row]), 'PENDING')

    def test_ipc_ack_and_exit_zero_do_not_prove_a_new_window(self):
        attempt = self.attempt()
        self.assertEqual(attempt.observe(11, None, None, processes(), []), 'PENDING')
        self.assertEqual(attempt.observe(12, 0, None, {}, []), 'EXITED')
        self.assertIn('확인하지 못', STATE.message(attempt.status, 0))

    def test_dead_compositor_and_old_session_cannot_update_a_successor(self):
        for flag in ('session_current', 'compositor_current'):
            with self.subTest(flag=flag):
                self.assertEqual(self.attempt().observe(11, None, None, processes(), [native_window()],
                                                       **{flag: False}), 'SESSION_CHANGED')

    def test_readiness_has_a_deadline_without_treating_alive_as_success(self):
        attempt = self.attempt()
        self.assertEqual(attempt.observe(29.9, None, None, processes(), []), 'PENDING')
        self.assertEqual(attempt.observe(30, None, None, processes(), []), 'TIMEOUT')
        self.assertIn('아직', STATE.message(attempt.status))
        self.assertIsNone(attempt.elapsed_ms)

    def test_sandbox_failure_is_shown_before_generic_exit(self):
        for kind, expected in [('SUID_SANDBOX', 'SUID_SANDBOX'), ('USERNS_SANDBOX', 'USERNS_SANDBOX'),
                               ('ROOT_UNSUPPORTED', 'ROOT_UNSUPPORTED')]:
            with self.subTest(kind=kind):
                self.assertEqual(self.attempt().observe(11, -5, kind, {}, []), expected)
                self.assertTrue(STATE.message(expected))
                self.assertNotIn('--no-sandbox', STATE.message(expected))

    def test_unknown_exit_is_visible_without_user_content(self):
        self.assertEqual(self.attempt().observe(11, -5, None, {}, []), 'EXITED')
        self.assertIn('-5', STATE.message('EXITED', -5))


class BrowserStartupChildTests(unittest.TestCase):
    def stop_owned(self, child):
        if child is None:
            return
        if child.poll() is None:
            child.terminate()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill(); child.wait(timeout=3)
        if child.stderr is not None:
            child.stderr.close()

    def test_spawn_preserves_literal_argv_environment_and_profile_bytes(self):
        with tempfile.TemporaryDirectory(prefix='loopy-browser-argv-') as directory:
            base = Path(directory); profile = base / 'profile'; profile.mkdir()
            user = profile / 'Preferences'; user.write_bytes(b'KEEP_EXISTING_PROFILE\x00\xff')
            before = hashlib.sha256(user.read_bytes()).hexdigest()
            marker = base / 'owned-argv.json'
            values = ['--private', 'https://example.invalid/?literal=$(exit 99)&value=a b', '', "a'b"]
            env = dict(os.environ, LOOPY_BROWSER_PUBLIC_MARKER='kept')
            original = dict(env)
            code = ('import json,os,pathlib,sys; pathlib.Path(sys.argv[1]).write_text('
                    'json.dumps([sys.argv[2:],os.environ.get("LOOPY_BROWSER_PUBLIC_MARKER")]))')
            child = STATE.spawn([sys.executable, '-c', code, str(marker), *values], env=env)
            self.addCleanup(self.stop_owned, child)
            self.assertIsNotNone(child, 'Browser transport does not start the selected command')
            self.assertEqual(child.wait(timeout=5), 0)
            self.assertEqual(json.loads(marker.read_text()), [values, 'kept'])
            self.assertEqual(env, original)
            self.assertEqual(hashlib.sha256(user.read_bytes()).hexdigest(), before)

    def test_actual_child_suid_abort_is_classified_without_retaining_private_lines(self):
        code = 'import os,sys; os.write(2,' + repr(SUID) + '); sys.exit(5)'
        child = STATE.spawn([sys.executable, '-c', code])
        self.addCleanup(self.stop_owned, child)
        self.assertIsNotNone(child, 'No observed browser child')
        data = child.stderr.read(8193)
        self.assertEqual(child.wait(timeout=5), 5)
        fatal = STATE.FatalClassifier(); fatal.feed(data)
        self.assertEqual(fatal.kind, 'SUID_SANDBOX')

    def test_timeout_does_not_terminate_an_alive_child_or_change_profile(self):
        with tempfile.TemporaryDirectory(prefix='loopy-browser-timeout-') as directory:
            profile = Path(directory) / 'Preferences'; profile.write_bytes(b'KEEP_USER_PROFILE')
            child = STATE.spawn([sys.executable, '-c', 'import time; time.sleep(10)'])
            self.addCleanup(self.stop_owned, child)
            self.assertIsNotNone(child, 'No browser child for bounded observation')
            attempt = STATE.Startup(child.pid, os.getuid(), 1, started=1, timeout=1)
            rows = {child.pid: {'pid': child.pid, 'uid': os.getuid(), 'birth': 1, 'ppid': os.getpid(), 'state': 'S'}}
            self.assertEqual(attempt.observe(2, child.poll(), None, rows, []), 'TIMEOUT')
            self.assertIsNone(child.poll(), 'Readiness timeout killed the still-running browser')
            self.assertEqual(profile.read_bytes(), b'KEEP_USER_PROFILE')


class BrowserStartupPlanAndFatalTests(unittest.TestCase):
    def test_chromium_wayland_selection_preserves_every_original_argument(self):
        original = ['/usr/bin/chromium', '--incognito', 'https://example.invalid/a b']
        planned = STATE.plan(original)
        self.assertEqual(planned, [original[0], '--ozone-platform=wayland', *original[1:]])
        self.assertEqual(original, ['/usr/bin/chromium', '--incognito', 'https://example.invalid/a b'])
        self.assertFalse(any(flag in planned for flag in ('--no-sandbox', '--disable-setuid-sandbox',
                                                        '--no-zygote', '--disable-gpu')))

    def test_existing_wayland_flag_is_not_duplicated_and_other_browser_is_unchanged(self):
        original = ['/usr/bin/chromium', '--ozone-platform=wayland', '--private', 'https://example.invalid/']
        self.assertEqual(STATE.plan(original), original)
        firefox = ['/usr/bin/firefox', '--private-window', 'https://example.invalid/']
        self.assertEqual(STATE.plan(firefox), firefox)

    def test_invalid_or_unbounded_arguments_are_rejected_before_spawn(self):
        for argv in ([], [''], ['a\x00b'], [None], [True], ['chromium', object()],
                     ['chromium', 'x' * 8193], ['chromium'] + ['x'] * 256):
            with self.subTest(kind=type(argv[0]).__name__ if argv else 'empty'):
                with self.assertRaises(ValueError):
                    STATE.plan(argv)

    def test_fatal_recognition_survives_fragmentation_and_never_invents_namespace_failure(self):
        for data, expected in ((SUID, 'SUID_SANDBOX'), (USERNS, 'USERNS_SANDBOX'),
                               (b'Running as root without --no-sandbox is not supported.\n', 'ROOT_UNSUPPORTED')):
            with self.subTest(expected=expected):
                fatal = STATE.FatalClassifier()
                for byte in data:
                    fatal.feed(bytes([byte]))
                self.assertEqual(fatal.kind, expected)
        fatal = STATE.FatalClassifier(); fatal.feed(b'ERROR: No usable sandbox! is a page title\n')
        self.assertIsNone(fatal.kind)

    def test_stderr_classification_budget_is_exactly_eight_kib(self):
        fatal = STATE.FatalClassifier(); fatal.feed(b'x' * 8192); fatal.feed(SUID)
        self.assertEqual(fatal.seen_bytes, 8192)
        self.assertIsNone(fatal.kind, 'An unbounded later stderr line changed the startup cause')

    def test_menu_dispatches_through_the_same_original_browser_caller(self):
        actions = module('hyprland_actions')
        self.assertEqual(actions.action({'action': 'launch', 'app': 'browser'}),
                         'hl.dsp.exec_cmd("/usr/bin/bash /usr/share/omarchy/bin/omarchy-launch-browser")')


class BrowserCurrentWorkerLivenessTests(unittest.TestCase):
    def test_unchanged_ready_and_worker_identity_cannot_keep_a_dead_worker_current(self):
        launch = module('browser_launch')
        compositor = launch.Compositor.__new__(launch.Compositor)
        compositor.owner = {'pid': 19, 'uid': os.getuid(), 'birth': 200, 'ppid': 3, 'state': 'R'}
        compositor.worker = {'pid': 17, 'uid': os.getuid(), 'birth': 100, 'ppid': 19, 'state': 'S'}
        compositor.record = {'token': 'public-live-token', 'signature': 'public_live_signature',
                             'pid': 17, 'uid': os.getuid()}
        compositor.socket_identity = (1, 2, os.getuid(), 0o140600)
        compositor.lifetime = Mock()
        compositor.lifetime.alive.return_value = True
        for status, expected in (('Z', False), ('X', False), ('R', True)):
            with self.subTest(state=status):
                worker = dict(compositor.worker, state=status)
                with patch.object(launch, 'identity', side_effect=[dict(compositor.owner), worker]), \
                        patch.object(compositor, '_ready', return_value=dict(compositor.record)), \
                        patch.object(compositor, '_socket_identity', return_value=compositor.socket_identity):
                    self.assertIs(compositor.current(), expected,
                                  'Identical PID/UID/birth and ready metadata hid the worker live state')


class BrowserInitialWorkerAdmissionTests(unittest.TestCase):
    """Exercise the production admission seam without GTK, Linux /proc or a device."""
    def setUp(self):
        self.launch = module('browser_launch')
        self.expected = {'LOOPY_SESSION': 'public-worker-token',
                         'HYPRLAND_INSTANCE_SIGNATURE': 'public_signature_123',
                         'XDG_RUNTIME_DIR': '/run/loopy/o12345678'}
        self.row = {'pid': 17, 'uid': os.getuid(), 'birth': 100, 'ppid': 3, 'state': 'S'}
        self.argv = b'/usr/bin/python\0-B\0/usr/share/loopy/omarchy-bridge/session_actions.py\0'

    def environment(self, values=None):
        selected = self.expected if values is None else values
        return b'\0'.join((key + '=' + value).encode() for key, value in selected.items()) + b'\0'

    def admit(self, argv=None, environment=None, before=None, after=None, error=None):
        blobs = {'cmdline': self.argv if argv is None else argv,
                 'environ': self.environment() if environment is None else environment}
        def read(path, limit, private=False):
            self.assertEqual(path.parent, Path('/proc/17'))
            self.assertIn(path.name, ('cmdline', 'environ'))
            if error is not None:
                raise error
            data = blobs[path.name]
            if not 0 < len(data) <= limit:
                raise ValueError('Bounded metadata fixture')
            return data
        rows = [dict(self.row if before is None else before), dict(self.row if after is None else after)]
        with patch.object(self.launch, 'identity', side_effect=rows), patch.object(self.launch, '_read', side_effect=read):
            return self.launch.worker_identity(17, self.expected)

    def test_exact_worker_argv_and_selected_environment_admit_only_identity(self):
        environment = self.environment() + b'PRIVATE_URL=https://example.invalid/private\0TOKEN_SECRET=fixture\0'
        result = self.admit(environment=environment)
        self.assertEqual(result, self.row)
        self.assertEqual(set(result), {'pid', 'uid', 'birth', 'ppid', 'state'})

    def test_reused_pid_with_an_unrelated_command_is_refused(self):
        for argv in (b'/usr/bin/python\0-B\0/tmp/unrelated.py\0',
                     self.argv + b'--unexpected\0', self.argv.replace(b'-B\0', b''), self.argv[:-1]):
            with self.subTest(case=len(argv)):
                self.assertIsNone(self.admit(argv=argv), 'Fresh birth alone admitted a reused worker PID')

    def test_old_session_signature_or_runtime_is_refused(self):
        for key in self.expected:
            with self.subTest(key=key):
                values = dict(self.expected); values[key] = 'old-worker-value'
                self.assertIsNone(self.admit(environment=self.environment(values)),
                                  'Unrelated process environment admitted as current worker')

    def test_missing_or_duplicate_selected_environment_is_refused(self):
        for environment in (self.environment().replace(b'LOOPY_SESSION=public-worker-token\0', b''),
                            self.environment() + b'LOOPY_SESSION=public-worker-token\0',
                            self.environment()[:-1]):
            with self.subTest(size=len(environment)):
                self.assertIsNone(self.admit(environment=environment))

    def test_birth_or_uid_change_while_reading_proc_is_refused(self):
        for change in ({'birth': 101}, {'uid': os.getuid() + 1}, {'pid': 99}, {'state': 'Z'}):
            with self.subTest(change=change):
                after = dict(self.row); after.update(change)
                self.assertIsNone(self.admit(after=after), 'Worker changed while selected metadata was read')

    def test_unreadable_or_over_limit_metadata_cannot_be_admitted(self):
        self.assertIsNone(self.admit(error=PermissionError('Public fixture error')))
        self.assertIsNone(self.admit(environment=b'x' * 16385))


if __name__ == '__main__':
    unittest.main()
