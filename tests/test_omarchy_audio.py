"""Owned output audio lifecycle and the actual Omarchy panel CLI contract."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

REPO = Path(__file__).resolve().parents[1]


def load(test, name):
    source = REPO / 'termux' / (name + '.py')
    test.assertTrue(source.is_file(), 'owned audio integration is missing')
    sys.path.insert(0, str(source.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class AudioHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.short = self.base / 'lr'
        self.short.mkdir(mode=0o700)
        item = self.short.lstat()
        self.value = {'schema': 1, 'token': str(uuid.uuid4()), 'uid': os.getuid(),
                      'runtime': [item.st_dev, item.st_ino, item.st_uid], 'root': [1, 2, os.getuid()]}
        (self.short / 'owner.json').write_text(json.dumps({key: self.value[key] for key in
                                                         ('schema', 'token', 'uid', 'runtime', 'root')}))
        self.session = self.base / 'session'
        self.session.mkdir(mode=0o700)
        self.prefix = self.base / 'usr'
        self.prefix.mkdir(mode=0o700)
        from types import SimpleNamespace
        self.runtime = SimpleNamespace(short=self.short, prefix=self.prefix, env={},
                                       root=self.base, state=lambda: self.value)

    def test_cookie_is_fresh_private_and_never_reuses_an_existing_audio_directory(self):
        module = load(self, 'omarchy_audio')
        module.prepare(self.runtime, self.value)
        cookie = self.short / 'pulse/cookie'
        self.assertEqual(cookie.stat().st_size, 256)
        self.assertEqual(cookie.stat().st_mode & 0o777, 0o600)
        before = cookie.read_bytes()
        with self.assertRaises(ValueError):
            module.prepare(self.runtime, self.value)
        self.assertEqual(cookie.read_bytes(), before)

    def test_different_owner_marker_is_preserved_without_creating_audio(self):
        module = load(self, 'omarchy_audio')
        path = self.short / 'owner.json'
        path.write_text(json.dumps(dict(self.value, token=str(uuid.uuid4()))))
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            module.prepare(self.runtime, self.value)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.short / 'pulse').exists())

    def test_existing_symlink_audio_directory_does_not_touch_its_target(self):
        module = load(self, 'omarchy_audio')
        target = self.base / 'preserved'
        target.mkdir()
        (target / 'cookie').write_bytes(b'preserved')
        (self.short / 'pulse').symlink_to(target)
        with self.assertRaises(ValueError):
            module.prepare(self.runtime, self.value)
        self.assertEqual((target / 'cookie').read_bytes(), b'preserved')

    def test_audio_command_is_foreground_output_only_and_cookie_authenticated_unix(self):
        module = load(self, 'omarchy_audio')
        args, env = module.command(self.runtime, self.value)
        self.assertEqual(args[0], str(self.prefix / 'bin/pulseaudio'))
        self.assertIn('--daemonize=no', args)
        self.assertIn('--use-pid-file=no', args)
        self.assertIn('--disallow-module-loading=yes', args)
        self.assertIn('module-suspend-on-idle timeout=30', args)
        self.assertIn('--exit-idle-time=-1', args)  # Suspend the unused sink, not the owned service.
        self.assertIn('module-aaudio-sink sink_name=loopy_output rate=48000', args)
        self.assertFalse(any('protocol-tcp' in value or 'sles-source' in value for value in args))
        self.assertTrue(any('auth-cookie-enabled=true' in value for value in args))
        self.assertEqual(env['PULSE_SERVER'], 'unix:' + str(self.short / 'pulse/native'))
        self.assertEqual(env['PULSE_COOKIE'], str(self.short / 'pulse/cookie'))

    def test_inherited_foreign_audio_configuration_is_removed(self):
        module = load(self, 'omarchy_runtime')
        original = os.environ.copy()
        try:
            os.environ.update(PULSE_SERVER='tcp:foreign:4713', PULSE_COOKIE='/foreign/cookie',
                              PULSE_SINK='foreign', PULSE_SOURCE='microphone',
                              PULSE_RUNTIME_PATH='/foreign/runtime', PULSE_STATE_PATH='/foreign/state')
            home = self.base / 'home'; home.mkdir()
            runtime = module.Runtime(home, self.prefix)
        finally:
            os.environ.clear(); os.environ.update(original)
        self.assertFalse(any(key.startswith('PULSE_') for key in runtime.env),
                         'Omarchy inherited another session audio server/source')

    def test_guest_commands_select_the_owned_unix_socket_and_cookie(self):
        module = load(self, 'omarchy_runtime')
        home = self.base / 'home'; home.mkdir()
        runtime = module.Runtime(home, self.prefix)
        runtime.short = self.short
        value = dict(self.value, display=':20', width=1920, height=1280)
        args, env = runtime.commands(value)[2]
        self.assertIn('PULSE_SERVER=unix:/run/user/1000/pulse/native', args)
        self.assertIn('PULSE_COOKIE=/run/user/1000/pulse/cookie', args)
        self.assertFalse(any('tcp:127.0.0.1:4715' in arg for arg in args))

    def test_start_never_publishes_a_transient_empty_android_cmdline(self):
        module = load(self, 'omarchy_audio')
        from unittest.mock import Mock, patch
        import subprocess
        import threading
        (self.base / 'sessions' / self.value['token']).mkdir(parents=True)
        child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(5)'],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        expected = module.command(self.runtime, self.value)[0]
        record = {'pid': child.pid, 'ppid': os.getpid(), 'pgid': os.getpgrp(), 'uid': os.getuid(),
                  'starttime': '12345', 'command': []}
        owned = type('Owned', (), {'register': Mock(), 'refresh': Mock()})()
        logs = []
        def ready(runtime, value):
            self.assertEqual(value['audioProcess']['command'], expected,
                             'transient empty cmdline was persisted before validation')
            return True
        try:
            with patch.object(module.subprocess, 'Popen', return_value=child), \
                    patch.object(module, 'identity', side_effect=[record, dict(record, command=expected)]), \
                    patch.object(module, 'ready', side_effect=ready):
                self.assertIs(module.start(self.runtime, self.value, owned, logs, threading.Event()), child)
        finally:
            child.terminate(); child.wait(timeout=3)
            for log in logs: log.finish()

    def test_start_refuses_a_different_executable_before_publishing_audio_identity(self):
        module = load(self, 'omarchy_audio')
        from unittest.mock import Mock, patch
        import subprocess
        import threading
        (self.base / 'sessions' / self.value['token']).mkdir(parents=True)
        child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(5)'],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        record = {'pid': child.pid, 'ppid': os.getpid(), 'pgid': os.getpgrp(), 'uid': os.getuid(),
                  'starttime': '12345', 'command': ['/foreign/executable']}
        owned = type('Owned', (), {'register': Mock(), 'refresh': Mock()})()
        logs=[]
        try:
            with patch.object(module.subprocess, 'Popen', return_value=child), \
                    patch.object(module, 'identity', return_value=record), \
                    patch.object(module, 'ready', return_value=True):
                with self.assertRaises(ValueError):
                    module.start(self.runtime, self.value, owned, logs, threading.Event())
            self.assertNotIn('audioProcess', self.value, 'unverified process was written into the journal')
        finally:
            child.terminate(); child.wait(timeout=3)
            for log in logs: log.finish()

    def test_audio_unavailable_does_not_misclassify_a_live_graphical_session_as_dead(self):
        module = load(self, 'omarchy_runtime')
        from unittest.mock import patch
        home = self.base / 'home'; home.mkdir()
        runtime = module.Runtime(home, self.prefix)
        value = dict(self.value, phase='ready', display=':20', processes=[{'pid': i} for i in range(2, 6)],
                     hyprland={'pid': 6})
        runtime.state = lambda: value
        runtime.x_ready = lambda display: True
        runtime.hypr_ready = lambda records: records[0]
        with patch.object(module, 'identity', return_value={'pid': 6}), \
                patch.object(module, 'same_identity', return_value=True), \
                patch.object(module, 'live_peer', return_value=True), \
                patch.object(module, 'audio_ready', return_value=False):
            report = runtime.status(str(uuid.uuid4()))
        self.assertEqual(report['status'], 'ready')
        self.assertTrue(report['hyprlandReady'])
        self.assertFalse(report['audioReady'])


class AudioPanelTests(unittest.TestCase):
    def sink(self, volume=65536, mute=False, driver='module-aaudio-sink.c'):
        return {'name': 'loopy_output', 'driver': driver, 'mute': mute,
                'volume': {'front-left': {'value': volume}, 'front-right': {'value': volume}}}

    def test_panel_status_reports_real_output_volume_mute_and_availability(self):
        module = load(self, 'omarchy_audio_guest')
        self.assertEqual(module.status_fields([self.sink(32768, True)]), (50, 1, 1))
        self.assertEqual(module.status_fields([]), (0, 1, 0))

    def test_other_sink_or_duplicate_output_is_not_reported_as_our_hardware(self):
        module = load(self, 'omarchy_audio_guest')
        self.assertEqual(module.status_fields([self.sink(driver='module-null-sink.c')]), (0, 1, 0))
        self.assertEqual(module.status_fields([self.sink(), self.sink()]), (0, 1, 0))

    def test_invalid_volume_is_rejected_before_any_client_command(self):
        module = load(self, 'omarchy_audio_guest')
        calls = []
        def run(*args, **kwargs): calls.append(args); return '[]'
        for value in ('-1', '101', 'NaN', '1;exit', '+4', '00', '3.5'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.dispatch(['volume', value], runner=run)
        self.assertEqual(calls, [])

    def test_volume_and_mute_use_only_the_fixed_owned_sink_and_verify_after_write(self):
        module = load(self, 'omarchy_audio_guest')
        calls = []
        current = [self.sink()]
        def run(args, **kwargs):
            calls.append((args, kwargs['env']))
            if args[-1] == 'sinks': return json.dumps(current)
            if args[1] == 'set-sink-volume':
                current[0] = self.sink(16384); return ''
            if args[1] == 'set-sink-mute':
                current[0]['mute'] = True; return ''
            raise AssertionError('unexpected command')
        self.assertEqual(module.dispatch(['volume', '25'], runner=run), (25, 0, 1))
        self.assertEqual(module.dispatch(['mute-toggle'], runner=run), (25, 1, 1))
        self.assertIn(['/usr/bin/pactl', 'set-sink-volume', 'loopy_output', '25%'], [row[0] for row in calls])
        self.assertIn(['/usr/bin/pactl', 'set-sink-mute', 'loopy_output', '1'], [row[0] for row in calls])
        for args, env in calls:
            self.assertEqual(env['PULSE_SERVER'], 'unix:/run/user/1000/pulse/native')
            self.assertEqual(env['PULSE_COOKIE'], '/run/user/1000/pulse/cookie')

    def test_unconfirmed_volume_write_is_not_accepted(self):
        module = load(self, 'omarchy_audio_guest')
        def run(args, **kwargs):
            return json.dumps([self.sink()]) if args[-1] == 'sinks' else ''
        with self.assertRaises(ValueError):
            module.dispatch(['volume', '25'], runner=run)


if __name__ == '__main__':
    unittest.main()
