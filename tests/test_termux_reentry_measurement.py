"""Honest wall-clock re-entry measurement; fake CLI through the real functions."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import measure_termux_reentry as m  # noqa: E402


def load():
    spec = importlib.util.spec_from_file_location('mtr', ROOT / 'tools/measure_termux_reentry.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReentryMeasurementTests(unittest.TestCase):
    def test_all_ready_runs_are_measured_with_honest_bounds(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / 'fake-omarchy'
            fake.write_text('#!' + sys.executable + "\nimport json;print(json.dumps({'status': 'ready'}))\n")
            fake.chmod(0o700)
            runs = m.measure([str(fake)], runs=3, timeout=30, pause=0)
        summary = m.summarize(runs)
        self.assertEqual(summary['status'], 'MEASURED_REENTRY')
        self.assertTrue(summary['reentryLatencyProven'])
        self.assertLessEqual(summary['minSeconds'], summary['medianSeconds'] <= summary['maxSeconds'] + 1)
        self.assertEqual([r['run'] for r in runs], [1, 2, 3])
        for row in runs:
            self.assertEqual(row['status'], 'ready')
            self.assertGreater(row['seconds'], 0)

    def test_not_ready_and_timeout_are_labeled_without_proven_latency(self):
        self.assertEqual(m.summarize([{'seconds': 1.0, 'status': 'NOT_READY', 'reason': 'exit-1'},
                                      {'seconds': 2.0, 'status': 'ready', 'reason': None}])['status'],
                         'NOT_READY')
        self.assertFalse(m.summarize([{'seconds': 99.0, 'status': 'TIMEOUT', 'reason': 'timeout'}])
                         ['reentryLatencyProven'])
        parsed = m.run_once([sys.executable, '-c', "print('{\"status\": \"failed\", \"reason\": \"x\"}')"],
                            timeout=10)
        self.assertEqual((parsed['status'], parsed['reason']), ('NOT_READY', 'x'))

    def test_timeout_is_bounded_and_recorded(self):
        row = m.run_once([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=2)
        self.assertEqual(row['status'], 'TIMEOUT')
        self.assertLess(row['seconds'], 10)

    def test_unavailable_command_is_a_fixed_kind_not_a_traceback(self):
        row = m.run_once(['/no/such/public/command'], timeout=5)
        self.assertEqual(row['status'], 'UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
