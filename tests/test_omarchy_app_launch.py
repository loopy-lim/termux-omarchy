"""The guest app-launch bridge must exec the actual command without shell reinterpretation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ROOT / 'android/assets/omarchy-bridge/loopy-app-launch'


class OmarchyAppLaunchTests(unittest.TestCase):
    def test_real_exec_preserves_argv_pid_and_exit_status(self):
        args = ['a b', '$(exit 99)', '; exit 99', '', '--flag', "a'b"]
        child = subprocess.Popen(['/bin/bash', str(LAUNCH), '--', sys.executable, '-c',
            'import json,os,sys; print(json.dumps([os.getpid(),sys.argv[1:]])); sys.exit(23)', *args],
            env=dict(os.environ, LOOPY_SESSION='public-app-launch-1'), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        stdout, stderr = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 23, stderr)
        self.assertEqual(json.loads(stdout), [child.pid, args])

    def test_invalid_session_or_options_do_not_start_a_command(self):
        for token, args in [('', ['--']), ('../old', ['--']), ('a' * 65, ['--']),
                            ('current', ['--scope']), ('current', [])]:
            with self.subTest(token=token, args=args):
                result = subprocess.run(['/bin/bash', str(LAUNCH), *args, sys.executable,
                    '-c', 'print("MUST_NOT_RUN")'], env=dict(os.environ, LOOPY_SESSION=token),
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 64, result.stderr)
                self.assertNotIn('MUST_NOT_RUN', result.stdout)

    def test_missing_command_is_an_actual_failure(self):
        result = subprocess.run(['/bin/bash', str(LAUNCH), '--', '/no-such-public-command'],
            env=dict(os.environ, LOOPY_SESSION='current'), capture_output=True, text=True, timeout=10)
        self.assertIn(result.returncode, (126, 127), result.stderr)
