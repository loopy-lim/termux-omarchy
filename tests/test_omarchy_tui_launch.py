"""Real Bash/exec argv contract; the unavailable display executables are recorders."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'termux/omarchy-launch-tui'


class TuiLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.record = self.root / 'arguments.json'
        python = shutil.which('python3')
        for name in ('foot', 'setsid'):
            path = self.bin / name
            path.write_text(f'#!{python}\nimport json,os,sys\n'
                            'with open(os.environ["LOOPY_TEST_RECORD"],"x") as out:'
                            'json.dump({"executable":os.path.basename(sys.argv[0]),"argv":sys.argv[1:]},out)\n')
            path.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.bin) + ':/usr/bin:/bin',
                        LOOPY_TEST_RECORD=str(self.record))

    def run_script(self, *args, proot='1'):
        result = subprocess.run(['/bin/bash', str(SCRIPT), *args],
                                env=dict(self.env, OMARCHY_PROOT=proot),
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
        record = json.loads(self.record.read_text()) if self.record.exists() else None
        return result, record

    def test_proot_launches_foot_with_command_and_literal_arguments(self):
        result, record = self.run_script('nvim', '/tmp/a file; $(touch nope).txt', '--headless')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(record, {'executable': 'foot', 'argv': [
            '--app-id=org.omarchy.nvim', '--', 'nvim', '/tmp/a file; $(touch nope).txt', '--headless']})

    def test_proot_preserves_explicit_app_id(self):
        result, record = self.run_script('--app-id=org.omarchy.custom', '/usr/bin/yazi', '/tmp')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(record, {'executable': 'foot', 'argv': [
            '--app-id=org.omarchy.custom', '--', '/usr/bin/yazi', '/tmp']})

    def test_missing_command_is_an_argument_error_without_launch(self):
        result, record = self.run_script('--app-id=org.omarchy.custom')
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(record)

    def test_no_arguments_do_not_launch(self):
        result, record = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(record)

    def test_normal_desktop_retains_uwsm_terminal_path(self):
        result, record = self.run_script('nvim', '/tmp/a file.txt', proot='0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(record, {'executable': 'setsid', 'argv': [
            'uwsm-app', '--', 'xdg-terminal-exec', '--app-id=org.omarchy.nvim', '-e', 'nvim', '/tmp/a file.txt']})


if __name__ == '__main__':
    unittest.main()
