"""Real subprocess delivery, durable retry and concurrent first-run invocations."""
import importlib.util
import multiprocessing
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'android/assets/omarchy-bridge/notice_once.py'


def deliver(home, key, command):
    if not SOURCE.exists():
        # Original first-run scripts execute their notifier on every retry.
        return subprocess.run(command, check=False).returncode
    spec = importlib.util.spec_from_file_location('notice_once', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.deliver(Path(home), key, command)


class FirstRunNoticeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='loopy-notice-test-')
        self.home = Path(self.temp.name)
        self.log = self.home / 'deliveries'
        self.command = [sys.executable, '-B', '-c',
            'import pathlib,sys; p=pathlib.Path(sys.argv[1]); '
            'p.open("a").write("actual notifier invocation\\n")', str(self.log)]

    def tearDown(self):
        self.temp.cleanup()

    def test_success_survives_new_invocation_without_repeating_notice(self):
        self.assertEqual(deliver(self.home, 'welcome', self.command), 0)
        self.assertEqual(deliver(self.home, 'welcome', self.command), 0)
        self.assertEqual(len(self.log.read_text().splitlines()), 1,
                         'A successful first-run notice must not repeat on the next login')
        self.assertFalse((self.home / '.local/state/omarchy/done/first-run-user').exists())

    def test_failed_delivery_retries_and_other_notices_remain_independent(self):
        self.assertEqual(deliver(self.home, 'wifi', [sys.executable, '-c', 'raise SystemExit(7)']), 7)
        self.assertEqual(deliver(self.home, 'wifi', self.command), 0)
        self.assertEqual(deliver(self.home, 'update', self.command), 0)
        self.assertEqual(deliver(self.home, 'wifi', self.command), 0)
        self.assertEqual(len(self.log.read_text().splitlines()), 2)

    def test_concurrent_processes_deliver_one_notice(self):
        ctx = multiprocessing.get_context('fork')
        workers = [ctx.Process(target=deliver, args=(self.home, 'welcome', self.command)) for _ in range(4)]
        for worker in workers: worker.start()
        for worker in workers:
            worker.join(10)
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(len(self.log.read_text().splitlines()), 1)

    def test_redirected_user_state_is_preserved_without_delivery(self):
        outside = self.home / 'user-data'; outside.mkdir()
        (outside / 'keep').write_text('KEEP')
        (self.home / '.local').symlink_to(outside, target_is_directory=True)
        with self.assertRaises((OSError, ValueError)):
            deliver(self.home, 'welcome', self.command)
        self.assertEqual((outside / 'keep').read_text(), 'KEEP')
        self.assertFalse(self.log.exists())


if __name__ == '__main__': unittest.main()
