"""Real Bash/TTY argument boundaries; SSH/Waypipe/Gum are unavailable-host recorders."""
import json
import os
from pathlib import Path
import pty
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'termux/omarchy-remote'


class OmarchyRemoteTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'native Omarchy remote entry is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.runtime = self.root / 'runtime'
        self.runtime.mkdir(mode=0o700)
        self.record = self.root / 'arguments.json'
        python = shutil.which('python3')
        for name in ('ssh', 'waypipe'):
            p = self.bin / name
            p.write_text(f'#!{python}\nimport json,os,sys\n'
                         'with open(os.environ["RECORD"],"x") as out:'
                         'json.dump({"executable":os.path.basename(sys.argv[0]),"argv":sys.argv[1:]},out)\n')
            p.chmod(0o700)
        gum = self.bin / 'gum'
        gum.write_text(f'#!{python}\n' + '''import json,os,sys
if os.environ.get('GUM_CANCEL')=='1': sys.exit(130)
if sys.argv[1]=='choose': print(os.environ['GUM_MODE'])
elif sys.argv[1]=='input':
 p=os.environ['GUM_COUNT']
 try:
  with open(p) as f: count=int(f.read())
 except FileNotFoundError: count=0
 with open(p,'w') as f: f.write(str(count+1))
 print(os.environ['GUM_HOST'] if count==0 else os.environ['GUM_PROGRAM'])
else: sys.exit(4)
''')
        gum.chmod(0o700)
        fzf = self.bin / 'fzf'
        fzf.write_text(f'#!{python}\nimport os,sys\n'
                       "if os.environ.get('GUM_CANCEL')=='1': sys.exit(130)\n"
                       "print(os.environ['GUM_MODE'])\n")
        fzf.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.bin) + ':/usr/bin:/bin',
                        RECORD=str(self.record), WAYLAND_DISPLAY='wayland-1',
                        XDG_RUNTIME_DIR=str(self.runtime), GUM_COUNT=str(self.root / 'gum-count'),
                        GUM_MODE='SSH terminal', GUM_HOST='public-host', GUM_PROGRAM='foot')

    def run_script(self, *args, tty=False, **changes):
        env = dict(self.env, **changes)
        if tty:
            master, slave = pty.openpty()
            try:
                if 'PUBLIC_TTY_INPUT' in changes:
                    os.write(master, changes['PUBLIC_TTY_INPUT'].encode())
                result = subprocess.run(['/bin/bash', str(SCRIPT), *args], env=env, cwd=self.root,
                                        stdin=slave, stdout=slave, stderr=slave, timeout=5)
            finally:
                os.close(slave); os.close(master)
        else:
            result = subprocess.run(['/bin/bash', str(SCRIPT), *args], env=env, cwd=self.root,
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
        record = json.loads(self.record.read_text()) if self.record.exists() else None
        return result, record

    def test_ssh_preserves_options_destination_and_literal_command_arguments(self):
        args = ['-F', '/tmp/a config', 'user@public-host', 'printf', '$(touch LOCAL_EXECUTED); *']
        result, record = self.run_script('ssh', *args)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(record, {'executable': 'ssh', 'argv': args})
        self.assertFalse((self.root / 'LOCAL_EXECUTED').exists())

    def test_interactive_ssh_uses_installed_fzf_when_gum_is_missing(self):
        (self.bin / 'gum').unlink()
        result, record = self.run_script(tty=True, PUBLIC_TTY_INPUT='fixture-host\n')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(record, {'executable': 'ssh', 'argv': ['fixture-host']})

    def test_interactive_wayland_uses_read_line_without_losing_spaces(self):
        (self.bin / 'gum').unlink()
        result, record = self.run_script(tty=True, GUM_MODE='Wayland app',
                                         PUBLIC_TTY_INPUT='fixture-host\n/home/user/a program\n')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(record['argv'][4:], ['ssh', 'fixture-host', "'/home/user/a program'"])

    def test_interactive_app_path_is_quoted_for_the_remote_login_shell(self):
        program = self.root / "a program '$literal'"
        program.write_text("#!/bin/sh\nprintf '%s' Y900_REMOTE_LITERAL_PATH_OK\n")
        program.chmod(0o700)
        result, record = self.run_script(tty=True, GUM_MODE='Wayland app', GUM_PROGRAM=str(program))
        self.assertEqual(result.returncode, 0)
        remote = subprocess.run(['/bin/sh', '-c', 'exec ' + record['argv'][-1]],
                                capture_output=True, text=True, timeout=3)
        self.assertEqual(remote.returncode, 0, remote.stderr)
        self.assertEqual(remote.stdout, 'Y900_REMOTE_LITERAL_PATH_OK')

    def test_fzf_cancel_does_not_start_an_ssh_client(self):
        (self.bin / 'gum').unlink()
        result, record = self.run_script(tty=True, GUM_CANCEL='1')
        self.assertEqual(result.returncode, 130)
        self.assertIsNone(record)

    def test_wayland_uses_the_short_runtime_namespace_and_keeps_gpu_default(self):
        args = ['-F', '/tmp/a config', 'user@public-host', 'foot', '--title', 'a literal title']
        result, record = self.run_script('wayland', *args)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(record['executable'], 'waypipe')
        self.assertEqual(record['argv'][0], '--socket')
        self.assertEqual(Path(record['argv'][1]).parent, self.runtime)
        self.assertEqual(record['argv'][2], '--remote-socket')
        self.assertEqual(Path(record['argv'][3]).parent, Path('/tmp'))
        self.assertEqual(record['argv'][4:], ['ssh', *args])
        self.assertNotIn('--no-gpu', record['argv'])

    def test_no_gpu_is_an_explicit_option_and_other_ssh_arguments_survive(self):
        result, record = self.run_script('wayland', '--no-gpu', '-p', '2222', 'host', 'foot')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(record['argv'][4:], ['--no-gpu', 'ssh', '-p', '2222', 'host', 'foot'])

    def test_unknown_mode_does_not_launch_a_network_client(self):
        result, record = self.run_script('unsupported', 'host')
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(record)

    def test_noninteractive_no_arguments_is_a_usage_error(self):
        result, record = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(record)

    def test_wayland_without_a_display_does_not_launch(self):
        result, record = self.run_script('wayland', 'host', 'foot', WAYLAND_DISPLAY='')
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(record)

    def test_wayland_rejects_a_relative_runtime_path_before_launch(self):
        result, record = self.run_script('wayland', 'host', 'foot', XDG_RUNTIME_DIR='relative')
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(record)

    def test_interactive_ssh_choice_passes_the_host_to_normal_ssh(self):
        result, record = self.run_script(tty=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(record, {'executable': 'ssh', 'argv': ['public-host']})

    def test_interactive_wayland_choice_preserves_the_executable_as_one_argument(self):
        result, record = self.run_script(tty=True, GUM_MODE='Wayland app',
                                         GUM_PROGRAM='/home/user/a program')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(record['argv'][4:], ['ssh', 'public-host', "'/home/user/a program'"])

    def test_interactive_cancel_does_not_start_a_client(self):
        result, record = self.run_script(tty=True, GUM_CANCEL='1')
        self.assertEqual(result.returncode, 130)
        self.assertIsNone(record)

    def test_interactive_option_shaped_host_is_not_used_as_an_ssh_option(self):
        result, record = self.run_script(tty=True, GUM_HOST='-oProxyCommand=touch LOCAL_EXECUTED')
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(record)
        self.assertFalse((self.root / 'LOCAL_EXECUTED').exists())


if __name__ == '__main__':
    unittest.main()
