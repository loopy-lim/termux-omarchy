"""Exercise Bash eval/exec through the current generic focus helper, with real jq."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TuiFocusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.record = self.root / 'foot.json'
        self.dispatches = self.root / 'dispatches.jsonl'
        python = shutil.which('python3')
        jq = shutil.which('jq')
        self.assertIsNotNone(jq, 'real jq is required for the focus helper contract')
        for name, source in {
            'omarchy-launch-tui': ROOT / 'termux/omarchy-launch-tui',
            'omarchy-launch-or-focus': ROOT / 'termux/omarchy-launch-or-focus',
            'jq': Path(jq),
        }.items():
            (self.bin / name).symlink_to(source)
        helpers = {
            'foot': 'with open(os.environ["RECORD"],"x") as out: json.dump(sys.argv[1:],out)\n',
            'setsid': 'os.execvp(sys.argv[1],sys.argv[1:])\n',
            'hyprctl': '''if sys.argv[1:]==['clients','-j']:
 print(os.environ['CLIENTS'])
elif sys.argv[1:2]==['dispatch']:
 with open(os.environ['DISPATCHES'],'a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')
else: sys.exit(4)
''',
        }
        for name, source in helpers.items():
            p = self.bin / name
            p.write_text(f'#!{python}\nimport json,os,sys\n' + source)
            p.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.bin) + ':/usr/bin:/bin',
                        OMARCHY_PROOT='1', RECORD=str(self.record),
                        CLIENTS='[]', DISPATCHES=str(self.dispatches))

    def run_script(self, *args, clients=None):
        env = self.env if clients is None else dict(self.env, CLIENTS=json.dumps(clients))
        result = subprocess.run(['/bin/bash', str(ROOT / 'termux/omarchy-launch-or-focus-tui'), *args],
                                cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=5)
        record = json.loads(self.record.read_text()) if self.record.exists() else None
        return result, record

    def test_spaced_directory_reaches_yazi_as_one_argument(self):
        result, record = self.run_script('yazi', '/tmp/a directory with spaces')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(record, ['--app-id=org.omarchy.yazi', '--', 'yazi', '/tmp/a directory with spaces'])

    def test_shell_characters_are_literal_and_empty_arguments_survive(self):
        literal = 'a file; $(touch ARGUMENT_EXECUTED) * "quote" $HOME\\back\n한글'
        result, record = self.run_script('nvim', literal, '')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'ARGUMENT_EXECUTED').exists())
        self.assertEqual(record, ['--app-id=org.omarchy.nvim', '--', 'nvim', literal, ''])

    def test_explicit_app_id_and_command_path_are_preserved(self):
        result, record = self.run_script('--app-id=org.loopy.custom', '/usr/bin/yazi', '/tmp/a file')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(record, ['--app-id=org.loopy.custom', '--', '/usr/bin/yazi', '/tmp/a file'])

    def test_existing_window_is_focused_without_a_second_terminal(self):
        client = {'class': 'org.omarchy.yazi', 'title': 'public test', 'address': '0x123'}
        result, record = self.run_script('yazi', '/tmp/a file', clients=[client])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(record)
        dispatches = [json.loads(line) for line in self.dispatches.read_text().splitlines()]
        self.assertEqual(dispatches, [['dispatch', 'hl.dsp.focus({ window = "address:0x123" })']])

    def test_no_command_does_not_launch_or_focus(self):
        result, record = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(record)
        self.assertFalse(self.dispatches.exists())

    def test_app_id_without_command_does_not_launch_or_focus(self):
        result, record = self.run_script('--app-id=org.loopy.custom')
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(record)
        self.assertFalse(self.dispatches.exists())


if __name__ == '__main__':
    unittest.main()
