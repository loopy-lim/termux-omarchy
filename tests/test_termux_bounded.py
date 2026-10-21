"""Real child output bounds must not limit ART cache or other ordinary files."""
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def processes():
    spec = importlib.util.spec_from_file_location('bounded_processes', ROOT / 'termux/processes.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BoundedCommandTests(unittest.TestCase):
    def setUp(self):
        self.proc = processes()
        self.directory = tempfile.TemporaryDirectory(prefix='loopy-bounded-')
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)

    def test_small_output_can_write_large_art_cache_artifact(self):
        artifact = self.base / 'art-cache'
        script = """import signal,sys
from pathlib import Path
signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
Path(sys.argv[1]).write_bytes(b'A' * 262144)
print('preference-ready')
"""
        output = self.proc.run_bounded([sys.executable, '-c', script, str(artifact)], max_bytes=4096)
        self.assertEqual(output, 'preference-ready\n')
        self.assertEqual(artifact.stat().st_size, 262144)

    def test_stdout_and_stderr_share_one_output_budget(self):
        script = "import os; os.write(1,b'A'*600); os.write(2,b'B'*600)"
        with self.assertRaisesRegex(ValueError, 'output exceeds bound'):
            self.proc.run_bounded([sys.executable, '-c', script], max_bytes=1024)

    def test_exited_empty_group_permission_error_preserves_output_failure_and_reaps_child(self):
        spawn, signal_group, children = subprocess.Popen, os.killpg, []
        def capture(*args, **kwargs):
            child = spawn(*args, **kwargs); children.append(child); return child
        def denied(pid, sig):
            if sig == signal.SIGKILL:
                self.assertEqual(pid, children[0].pid)
                children[0].wait(timeout=3)
                raise PermissionError('exited zombie group')
            return signal_group(pid, sig)
        with patch.object(self.proc.subprocess, 'Popen', side_effect=capture), \
                patch.object(self.proc.os, 'killpg', side_effect=denied):
            with self.assertRaisesRegex(ValueError, 'output exceeds bound'):
                self.proc.run_bounded([sys.executable, '-c',
                    "import os;os.write(1,b'A'*600);os.write(2,b'B'*600)"], max_bytes=1024)
        self.assertEqual(children[0].returncode, 0)

    def test_live_command_permission_error_is_not_hidden(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'],
                                 start_new_session=True)
        try:
            with patch.object(self.proc.os, 'killpg', side_effect=PermissionError('live group denied')):
                with self.assertRaises(PermissionError): self.proc.reap_failed_command(child)
            self.assertIsNone(child.poll())
        finally:
            child.kill(); child.wait(timeout=3)

    def test_exited_leader_with_live_descendant_permission_error_is_not_hidden(self):
        group, heartbeat = self.base / 'group', self.base / 'heartbeat'
        child = subprocess.Popen([sys.executable, '-c',
            self.group_script(False).replace('time.sleep(20)', 'os._exit(0)'),
            str(group), str(heartbeat)], start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        signal_group = os.killpg
        try:
            child.wait(timeout=3)
            def denied(pid, sig):
                if sig == signal.SIGKILL: raise PermissionError('descendant group denied')
                return signal_group(pid, sig)
            with patch.object(self.proc.os, 'killpg', side_effect=denied):
                with self.assertRaises(PermissionError): self.proc.reap_failed_command(child)
            self.assertTrue(heartbeat.exists())
        finally:
            try: signal_group(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            child.wait(timeout=3)

    def test_incremental_utf8_output_and_stdin_are_preserved(self):
        script = """import os,sys
data=sys.stdin.buffer.read()
for byte in data: os.write(1,bytes([byte]))
os.write(2,b'warning')
"""
        self.assertEqual(self.proc.run_bounded([sys.executable, '-c', script],
            stdin='한글😀', max_bytes=17), '한글😀')

    def group_script(self, overflow):
        worker = """import signal,sys,time
from pathlib import Path
signal.signal(signal.SIGTERM,signal.SIG_IGN)
path=Path(sys.argv[1]); n=0
while True:
    n+=1; path.write_text(str(n)); time.sleep(.02)
"""
        return f"""import os,signal,subprocess,sys,time
from pathlib import Path
signal.signal(signal.SIGXFSZ,signal.SIG_DFL)
Path(sys.argv[1]).write_text(str(os.getpid()))
child=subprocess.Popen([sys.executable,'-c',{worker!r},sys.argv[2]])
while not Path(sys.argv[2]).exists(): time.sleep(.01)
{'os.write(1,b"X"*100000)' if overflow else ''}
time.sleep(20)
"""

    def assert_group_reaped(self, *, overflow):
        group, heartbeat = self.base / 'group', self.base / 'heartbeat'
        sentinel = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(20)'],
                                    start_new_session=True)
        try:
            expected = 'output exceeds bound' if overflow else 'timeout'
            with self.assertRaisesRegex(ValueError, expected):
                self.proc.run_bounded([sys.executable, '-c', self.group_script(overflow),
                    str(group), str(heartbeat)], max_bytes=4096, timeout=.3 if not overflow else 3)
            self.assertTrue(heartbeat.exists(), 'owned descendant never started')
            time.sleep(.1)
            stopped = heartbeat.read_text()
            time.sleep(.15)
            self.assertEqual(heartbeat.read_text(), stopped, 'owned descendant survived failed command')
            self.assertIsNone(sentinel.poll(), 'failed command killed an unrelated process group')
        finally:
            if group.exists():
                try: os.killpg(int(group.read_text()), signal.SIGKILL)
                except ProcessLookupError: pass
            if sentinel.poll() is None: sentinel.kill()
            sentinel.wait(timeout=3)

    def test_output_overflow_reaps_own_group_and_preserves_foreign_group(self):
        self.assert_group_reaped(overflow=True)

    def test_timeout_reaps_own_group_and_preserves_foreign_group(self):
        self.assert_group_reaped(overflow=False)

    def test_exited_command_cannot_leave_pipe_holding_child_running(self):
        group, heartbeat = self.base / 'group', self.base / 'heartbeat'
        script = self.group_script(False).replace('time.sleep(20)', 'os._exit(0)')
        try:
            with self.assertRaisesRegex(ValueError, 'timeout'):
                self.proc.run_bounded([sys.executable, '-c', script, str(group), str(heartbeat)], timeout=.3)
            stopped = heartbeat.read_text()
            time.sleep(.15)
            self.assertEqual(heartbeat.read_text(), stopped, 'pipe-holding descendant survived')
        finally:
            if group.exists():
                try: os.killpg(int(group.read_text()), signal.SIGKILL)
                except ProcessLookupError: pass

    def test_exit_failure_retains_bounded_stderr(self):
        with self.assertRaisesRegex(ValueError, 'exit 7: preference unavailable'):
            self.proc.run_bounded([sys.executable, '-c',
                "import sys;sys.stderr.write('preference unavailable');sys.exit(7)"])

    def test_cold_preference_read_apply_and_restore_fit_official_response_deadline(self):
        sys.path.insert(0, str(ROOT / 'termux'))
        self.addCleanup(sys.path.remove, str(ROOT / 'termux'))
        spec = importlib.util.spec_from_file_location('bounded_preferences', ROOT / 'termux/preferences.py')
        prefs = importlib.util.module_from_spec(spec); spec.loader.exec_module(prefs)
        command = self.base / 'termux-x11-preference'
        command.write_text('#!' + sys.executable + '\n' + '''import json,sys,time
from pathlib import Path
root=Path(__file__).parent; state=root/'endpoint.json'; cold=root/'cold'
values=json.loads(state.read_text())
if sys.argv[1:] == ['list']:
    if not cold.exists(): time.sleep(3.2); cold.touch()
    for key,value in values.items(): print(f'"{key}"="{value}"')
else:
    time.sleep(3.2)
    for item in sys.argv[1:]:
        key,value=item.split(':',1); values[key]=value
    state.write_text(json.dumps(values))
''')
        command.chmod(0o700)
        import json
        original = {'fullscreen': 'false', 'pointerCapture': 'false', 'preferScancodes': 'false',
                    'hardwareKbdScancodesWorkaround': 'true',
                    'showAdditionalKbd': 'true', 'showIMEWhileExternalConnected': 'true',
                    'pauseKeyInterceptingWithEsc': 'false'}
        state = self.base / 'endpoint.json'; state.write_text(json.dumps(original))
        prefs.apply(command, self.base, os.environ.copy())
        self.assertTrue((self.base / 'input.json').exists())
        self.assertEqual(json.loads(state.read_text())['pointerCapture'], 'true')
        prefs.restore(command, self.base, os.environ.copy())
        self.assertEqual(json.loads(state.read_text()), original)
        self.assertFalse((self.base / 'input.json').exists())


if __name__ == '__main__':
    unittest.main()
