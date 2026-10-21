"""Owned GPU recovery preserves normal config; foreign restarts retain upstream safe mode."""
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from unittest import mock

from tests import test_omarchy_watchdog as legacy

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'native/omarchy/patches/hyprland-gpu-recovery-v4.patch'
try:
    from tools import prepare_omarchy_watchdog_v4 as version
except ImportError:
    version = legacy.prepare


class WatchdogV4ProcessTests(legacy.OmarchyWatchdogProcessTests):
    @classmethod
    def setUpClass(cls):
        selected = PATCH if PATCH.exists() else legacy.PATCH
        with mock.patch.multiple(legacy, prepare=version, PATCH=selected, METADATA=selected.with_suffix('.json')):
            super().setUpClass()

    def start(self, mode, *, gpu=True, route=None):
        log = self.work / (self.id().split('.')[-1] + str(time.monotonic_ns()) + '.jsonl')
        env = {'PATH': os.defpath, 'LOOPY_SESSION': 'current-1', 'LOOPY_TEST_LOG': str(log),
               'LOOPY_TEST_MODE': mode, 'LIBGL_ALWAYS_SOFTWARE': '1',
               'QT_QUICK_BACKEND': 'software', 'LOOPY_TEST_KEEP': 'owned-session'}
        if gpu:
            env.update(GALLIUM_DRIVER='virpipe', VTEST_SOCKET_NAME=route or '/run/loopy/virgl-current-1.sock',
                       EGL_PLATFORM='surfaceless')
        child = subprocess.Popen([str(self.binary), '--path', str(self.child), '--no-nixgl', '--',
                                  '--config', '/run/loopy/private/hyprland.lua'],
            env=env, cwd=self.work, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True)
        return child, log

    def assert_software(self, launch):
        env = launch['env']
        for variable in ('GALLIUM_DRIVER', 'VTEST_SOCKET_NAME', 'EGL_PLATFORM'):
            self.assertNotIn(variable, env, 'GPU route leaked into software retry')
        self.assertEqual(env['LIBGL_ALWAYS_SOFTWARE'], '1')
        self.assertEqual(env['QT_QUICK_BACKEND'], 'software')
        self.assertEqual(env['LOOPY_TEST_KEEP'], 'owned-session')
        self.assertEqual(env['LOOPY_SESSION'], 'current-1')
        self.assertNotIn('--safe-mode', launch['args'], 'owned software recovery disabled normal config/start callbacks')
        self.assertEqual(launch['args'][launch['args'].index('--config') + 1], '/run/loopy/private/hyprland.lua')

    def test_normal_private_config_is_replayed_once_after_owned_gpu_exit(self):
        code, launches, errors = self.finish(*self.start('recover'))
        self.assertEqual(code, 0, errors)
        self.assertEqual(len(launches), 2)
        for launch in launches:
            self.assertNotIn('--safe-mode', launch['args'])
            self.assertEqual(launch['args'][launch['args'].index('--config') + 1], '/run/loopy/private/hyprland.lua')
        self.assert_software(launches[1])

    def test_existing_software_and_foreign_gpu_restart_still_enter_safe_mode(self):
        for gpu, route in ((False, None), (True, '/run/loopy/virgl-stale.sock')):
            with self.subTest(gpu=gpu):
                code, launches, errors = self.finish(*self.start('software', gpu=gpu, route=route))
                self.assertEqual(code, 0, errors)
                self.assertEqual(len(launches), 2)
                self.assertNotIn('--safe-mode', launches[0]['args'])
                self.assertIn('--safe-mode', launches[1]['args'])


class WatchdogV4SourceGuardTests(legacy.OmarchyWatchdogSourceGuardTests):
    def setUp(self):
        selected = PATCH if PATCH.exists() else legacy.PATCH
        fixture = mock.patch.multiple(legacy, prepare=version, PATCH=selected, METADATA=selected.with_suffix('.json'))
        fixture.start(); self.addCleanup(fixture.stop)
        super().setUp()


if __name__ == '__main__': unittest.main()
