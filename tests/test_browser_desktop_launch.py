"""Behavioral gtk-launch routing through the actual Bash transport and owned catalog.

The child runner replaces only Gio/GLib and GUI/exec boundaries unavailable on
the host. Production routing, argument validation and catalog file checks run.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'android/assets/omarchy-bridge'
ALIAS = 'org.chromium.chrome/com.google.android.apps.chrome.Main'
ENCODED = 'b3JnLmNocm9taXVtLmNocm9tZS9jb20uZ29vZ2xlLmFuZHJvaWQuYXBwcy5jaHJvbWUuTWFpbg'
TOKEN = 'public-desktop-browser-current'

# exec is intercepted at the process boundary, without altering production Bash.
BASH_ENV = '''exec() {
  if [[ ${1-} == -- ]]; then shift; fi
  "$LOOPY_TEST_PYTHON" "$LOOPY_TEST_RUNNER" "$@"
  exit $?
}
'''
RUNNER = r'''import importlib.util,json,os,pathlib,shlex,sys,types
args=sys.argv[1:]
record=pathlib.Path(os.environ['LOOPY_TEST_RECORD'])
def observed(kind,value,code):
 record.write_text(json.dumps({'kind':kind,'value':value}))
 return code
helper='/usr/share/loopy/omarchy-bridge/browser_desktop_launch.py'
if args[:3]!=['/usr/bin/python','-B',helper]:
 raise SystemExit(observed('linux',args,23))
assets=pathlib.Path(os.environ['LOOPY_TEST_ASSETS']);sys.path.insert(0,str(assets))
class Desktop:
 def get_commandline(self):return os.environ['LOOPY_TEST_COMMANDLINE']
 def get_filename(self):return '/usr/share/applications/chromium.desktop'
class DesktopAppInfo:
 @staticmethod
 def new(name):
  if name!='chromium.desktop':raise ValueError('Unexpected desktop id')
  return None if os.environ.get('LOOPY_TEST_ENTRY_ABSENT')=='1' else Desktop()
gi=types.ModuleType('gi');gi.require_version=lambda *_:None
repository=types.ModuleType('gi.repository')
repository.Gio=types.SimpleNamespace(DesktopAppInfo=DesktopAppInfo)
repository.GLib=types.SimpleNamespace(shell_parse_argv=lambda value:(True,shlex.split(value)),Error=ValueError)
gi.repository=repository;sys.modules['gi']=gi;sys.modules['gi.repository']=repository
inside=types.ModuleType('inside_window')
inside.run=lambda encoded:observed('inside',encoded,17)
sys.modules['inside_window']=inside
native_open=os.open
def catalog_open(path,flags,mode=0o777,*,dir_fd=None):
 if os.fspath(path)=='/run/loopy':path=os.environ['LOOPY_TEST_CATALOG']
 return native_open(path,flags,mode,dir_fd=dir_fd)
os.open=catalog_open
def fallback(file,values):
 if not values or file!=values[0]:raise ValueError('Changed exec boundary')
 raise SystemExit(observed('linux',list(values),23))
os.execvp=fallback
spec=importlib.util.spec_from_file_location('loopy_desktop_route_subject',assets/'browser_desktop_launch.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
raise SystemExit(module.main(args[3:]))
'''


class BrowserDesktopLaunchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='loopy-browser-desktop-')
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.catalog_directory = self.base / 'catalog'
        self.catalog_directory.mkdir(mode=0o700)
        self.runner = self.base / 'runner.py'
        self.runner.write_text(RUNNER)
        self.bash_environment = self.base / 'bash-env'
        self.bash_environment.write_text(BASH_ENV)
        self.record = self.base / 'result.json'

    def catalog(self, text=None, token=TOKEN):
        path = self.catalog_directory / ('apps-' + token + '.tsv')
        path.write_text(ALIAS + '\tChromium Android\t10372\n' if text is None else text)
        path.chmod(0o600)
        return path

    def invoke(self, argv, commandline='/usr/bin/chromium %U', absent=False):
        if self.record.exists():
            self.record.unlink()
        environment = dict(os.environ, LOOPY_SESSION=TOKEN, BASH_ENV=str(self.bash_environment),
                           LOOPY_TEST_PYTHON=sys.executable, LOOPY_TEST_RUNNER=str(self.runner),
                           LOOPY_TEST_RECORD=str(self.record), LOOPY_TEST_ASSETS=str(ASSETS),
                           LOOPY_TEST_CATALOG=str(self.catalog_directory),
                           LOOPY_TEST_COMMANDLINE=commandline, LOOPY_TEST_ENTRY_ABSENT=str(int(absent)),
                           PYTHONDONTWRITEBYTECODE='1')
        child = subprocess.run(['/bin/bash', str(ASSETS / 'loopy-app-launch'), '--', *argv],
                               env=environment, capture_output=True, timeout=5)
        self.assertEqual(child.stderr, b'', 'The routing fixture crashed instead of choosing a route')
        return child.returncode, json.loads(self.record.read_text())

    def expect_linux(self, argv, commandline='/usr/bin/chromium %U', absent=False):
        self.assertEqual(self.invoke(argv, commandline, absent),
                         (23, {'kind': 'linux', 'value': argv}))

    def test_exact_stock_desktop_launch_reaches_the_canonical_inside_alias(self):
        self.catalog()
        for commandline in ('/usr/bin/chromium', '/usr/bin/chromium %U',
                            '/usr/bin/chromium --ozone-platform=wayland %u'):
            with self.subTest(commandline=commandline):
                self.assertEqual(self.invoke(['gtk-launch', 'chromium.desktop'], commandline),
                                 (17, {'kind': 'inside', 'value': ENCODED}),
                                 'AppLibrary still launched the Linux desktop entry directly')

    def test_absolute_gtk_launcher_uses_the_same_stock_inside_route(self):
        self.catalog()
        self.assertEqual(self.invoke(['/usr/bin/gtk-launch', 'chromium.desktop']),
                         (17, {'kind': 'inside', 'value': ENCODED}))

    def test_custom_desktop_exec_keeps_original_gtk_launch_semantics(self):
        self.catalog()
        for commandline in ('/tmp/chromium %U', '/usr/bin/firefox %U',
                            '/usr/bin/chromium --incognito %U',
                            '/usr/bin/chromium --user-data-dir="/tmp/public profile" %U',
                            '/usr/bin/chromium --profile-directory="Profile 2" %U',
                            '/usr/bin/chromium https://example.invalid/a',
                            '/usr/bin/chromium --ozone-platform=x11 %U'):
            with self.subTest(commandline=commandline):
                self.expect_linux(['gtk-launch', 'chromium.desktop'], commandline)

    def test_ambiguous_or_unsupported_field_codes_do_not_discard_arguments(self):
        self.catalog()
        for commandline in ('/usr/bin/chromium %U %u', '/usr/bin/chromium %U%U',
                            '/usr/bin/chromium %F', '/usr/bin/chromium %f',
                            '/usr/bin/chromium --profile-directory=%U',
                            '/usr/bin/chromium %%', '/usr/bin/chromium "'):
            with self.subTest(commandline=commandline):
                self.expect_linux(['gtk-launch', 'chromium.desktop'], commandline)

    def test_gtk_url_arguments_and_other_desktop_entries_are_left_literal(self):
        self.catalog()
        for argv in (['gtk-launch', 'chromium.desktop', 'https://example.invalid/a b'],
                     ['gtk-launch', 'firefox.desktop'], ['gtk-launch', 'chromium'],
                     ['/tmp/gtk-launch', 'chromium.desktop'],
                     ['/usr/bin/foot', '--app-id=public-terminal'],
                     ['gtk-launch', 'chromium.desktop', '']):
            with self.subTest(argv=argv):
                self.expect_linux(argv)

    def test_absent_desktop_or_current_catalog_keeps_original_launcher(self):
        self.expect_linux(['gtk-launch', 'chromium.desktop'])
        self.catalog(token='public-desktop-browser-old')
        self.expect_linux(['gtk-launch', 'chromium.desktop'])
        self.catalog()
        self.expect_linux(['gtk-launch', 'chromium.desktop'], absent=True)

    def test_duplicate_malformed_and_symlink_catalog_cannot_open_inside(self):
        path = self.catalog((ALIAS + '\tChromium Android\t10372\n') * 2)
        self.expect_linux(['gtk-launch', 'chromium.desktop'])
        path.write_text(ALIAS + '\tChromium Android\t2000\n')
        self.expect_linux(['gtk-launch', 'chromium.desktop'])
        path.unlink()
        target = self.catalog(token='public-desktop-browser-other')
        path.symlink_to(target)
        self.expect_linux(['gtk-launch', 'chromium.desktop'])


if __name__ == '__main__':
    unittest.main()
