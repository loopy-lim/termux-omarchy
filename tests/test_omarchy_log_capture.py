"""Real subprocess output, exit and signal behavior for the Android shell log transport."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'android/assets/omarchy-bridge/log_capture.py'


class OmarchyLogCaptureTests(unittest.TestCase):
    def load(self):
        self.assertTrue(MODULE.is_file(), 'Original Omarchy still needs an actual Android-owned log transport')
        spec = importlib.util.spec_from_file_location('omarchy_log_capture', MODULE)
        module = importlib.util.module_from_spec(spec)
        previous = sys.dont_write_bytecode; sys.dont_write_bytecode = True
        try: spec.loader.exec_module(module)
        finally: sys.dont_write_bytecode = previous
        return module

    def test_real_child_exit_status_and_latest_output_are_retained_with_bounded_rotation(self):
        module = self.load()
        with tempfile.TemporaryDirectory(prefix='loopy-omarchy-log-') as directory:
            root = Path(directory)
            code = "import sys;sys.stdout.buffer.write(b'A'*4096+b'B'*4096+b'C'*4096);sys.stdout.flush();sys.exit(23)"
            result = module.supervise([sys.executable, '-c', code], root, limit=4096)
            self.assertEqual(result, 23, 'logger hid the real shell failure')
            files = sorted(root.glob('omarchy-shell.log*'))
            logs = [p for p in files if not p.name.endswith('.lock')]
            self.assertLessEqual(len(logs), 3)
            self.assertTrue(all(p.stat().st_size <= 4096 for p in logs))
            self.assertEqual((root / 'omarchy-shell.log').read_bytes(), b'C'*4096)
            self.assertEqual((root / 'omarchy-shell.log.1').read_bytes(), b'B'*4096)

    def test_real_child_exit_does_not_wait_forever_for_a_descendant_output_pipe(self):
        module = self.load()
        with tempfile.TemporaryDirectory(prefix='loopy-omarchy-pipe-') as directory:
            root = Path(directory)
            child = "import subprocess,sys;subprocess.Popen([sys.executable,'-c','import time;time.sleep(2)']);print('SHELL_EXITED',flush=True)"
            started = time.monotonic(); status = module.supervise([sys.executable, '-c', child], root)
            self.assertEqual(status, 0)
            self.assertLess(time.monotonic()-started, 1.5, 'inherited output handle stalled the shell supervisor')
            self.assertIn(b'SHELL_EXITED', (root / 'omarchy-shell.log').read_bytes())

    def test_log_link_is_rejected_before_spawning_or_modifying_its_target(self):
        module = self.load()
        with tempfile.TemporaryDirectory(prefix='loopy-omarchy-link-') as directory:
            root = Path(directory); keep = root / 'keep'; keep.write_text('KEEP_USER_FILE')
            (root / 'omarchy-shell.log').symlink_to(keep)
            side_effect = root / 'unexpected-child'
            with self.assertRaises((ValueError, OSError)):
                module.supervise([sys.executable, '-c', 'from pathlib import Path;Path('+repr(str(side_effect))+').touch()'], root)
            self.assertEqual(keep.read_text(), 'KEEP_USER_FILE')
            self.assertFalse(side_effect.exists())

    def test_signal_is_forwarded_to_the_actual_child_and_exit_is_collected(self):
        self.load()
        with tempfile.TemporaryDirectory(prefix='loopy-omarchy-signal-') as directory:
            root = Path(directory); helper = root / 'case.py'
            helper.write_text('import sys\nsys.path.insert(0,' + repr(str(MODULE.parent)) + ')\n'
                + 'import log_capture\nraise SystemExit(log_capture.supervise([sys.executable,"-c",'
                + repr("import time;print('READY',flush=True);time.sleep(30)") + '],'+repr(str(root))+'))\n')
            import os
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            process = subprocess.Popen([sys.executable, str(helper)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
            try:
                deadline = time.monotonic()+3
                while time.monotonic()<deadline:
                    log = root/'omarchy-shell.log'
                    if log.exists() and b'READY' in log.read_bytes(): break
                    time.sleep(.02)
                self.assertTrue(log.exists() and b'READY' in log.read_bytes(), 'real child did not start')
                process.terminate(); output, errors = process.communicate(timeout=4)
                self.assertEqual(process.returncode, 143, output+errors)
            finally:
                if process.poll() is None: process.kill(); process.communicate(timeout=3)
