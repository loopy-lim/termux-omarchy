"""Single public URI routing through the real selectors and Bash transport.

Only GTK/exec boundaries are replaced; current catalog ownership checks and
production argv parsing run unchanged. Fixture URLs contain no private data.
"""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'android/assets/omarchy-bridge'
ALIAS = 'org.chromium.chrome/com.google.android.apps.chrome.Main'
ENCODED = 'b3JnLmNocm9taXVtLmNocm9tZS9jb20uZ29vZ2xlLmFuZHJvaWQuYXBwcy5jaHJvbWUuTWFpbg'
TOKEN = 'public-browser-url-current'
URL = 'https://example.invalid/public%20page?q=one%2Ftwo#section'
WAYLAND = '--ozone-platform=wayland'


def module(name):
    spec = importlib.util.spec_from_file_location('loopy_url_test_' + name, ASSETS / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(value)
    finally:
        sys.dont_write_bytecode = previous
    return value


def fake_gi(commandline, absent=False):
    class Desktop:
        def get_commandline(self):
            return commandline

    class DesktopAppInfo:
        @staticmethod
        def new(name):
            if name != 'chromium.desktop':
                raise AssertionError('Unexpected desktop id')
            return None if absent else Desktop()

    gi = types.ModuleType('gi')
    gi.require_version = lambda *_: None
    repository = types.ModuleType('gi.repository')
    repository.Gio = types.SimpleNamespace(DesktopAppInfo=DesktopAppInfo)
    repository.GLib = types.SimpleNamespace(shell_parse_argv=lambda value: (True, shlex.split(value)),
                                            Error=ValueError)
    gi.repository = repository
    return {'gi': gi, 'gi.repository': repository}


class BrowserUrlRouteTests(unittest.TestCase):
    def setUp(self):
        self.path_patch = patch.object(sys, 'path', [str(ASSETS), *sys.path])
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.route = importlib.import_module('browser_inside_route')
        self.wire = importlib.import_module('inside_wire')
        self.inside = importlib.import_module('inside_window')
        self.launch = module('browser_launch')
        self.desktop = module('browser_desktop_launch')
        self.directory = tempfile.TemporaryDirectory(prefix='loopy-browser-url-')
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.catalog_directory = self.base / 'catalog'
        self.catalog_directory.mkdir(mode=0o700)
        self.calls = []
        self.catalog_reads = []
        self.inside_error = None
        self.environment = {key: value for key, value in os.environ.items()
                            if key not in ('CHROME_USER_DATA_DIR', 'CHROME_CONFIG_HOME')}
        self.environment['LOOPY_SESSION'] = TOKEN

    def catalog(self, text=None, token=TOKEN):
        path = self.catalog_directory / ('apps-' + token + '.tsv')
        path.write_text(ALIAS + '\tChromium Android\t10372\n' if text is None else text)
        path.chmod(0o600)
        return path

    def boundaries(self):
        native_open = os.open

        def open_catalog(path, flags, mode=0o777, *, dir_fd=None):
            if os.fspath(path) == '/run/loopy':
                self.catalog_reads.append('/run/loopy')
                path = self.catalog_directory
            return native_open(path, flags, mode, dir_fd=dir_fd)

        def inside_run(encoded, **kwargs):
            self.calls.append(('inside', encoded, dict(kwargs)))
            if self.inside_error is not None:
                raise self.inside_error
            return 17

        def linux_run(values):
            self.calls.append(('linux', list(values)))
            return 52

        def fallback(file, values):
            self.assertEqual(file, values[0])
            self.calls.append(('exec', list(values)))
            return 23

        return (patch.dict(os.environ, self.environment, clear=True),
                patch.object(self.wire.os, 'open', side_effect=open_catalog),
                patch.object(self.inside, 'run', side_effect=inside_run),
                patch.object(self.launch, 'run', side_effect=linux_run),
                patch.object(os, 'execvp', side_effect=fallback))

    def invoke(self, values, desktop=False, commandline='/usr/bin/chromium %U', absent=False):
        original = list(values)
        environment, catalog, inside, linux, fallback = self.boundaries()
        with environment, catalog, inside, linux, fallback, patch.dict(sys.modules, fake_gi(commandline, absent)):
            result = self.desktop.main(values) if desktop else self.launch.main(['--', *values])
        self.assertEqual(values, original, 'Routing changed caller-owned arguments')
        return result

    def selection(self, values):
        original = list(values)
        environment, catalog, inside, linux, fallback = self.boundaries()
        with environment, catalog, inside, linux, fallback:
            # The pre-feature source is an inert selector, yielding behavioral RED.
            select = getattr(self.route, 'selection', lambda _values: None)
            result = select(values)
        self.assertEqual(values, original)
        self.assertEqual(self.calls, [], 'A selector launched a browser')
        return result

    def test_empty_selection_preserves_encoded_only_legacy_component_api(self):
        self.catalog()
        for values in (['/usr/bin/chromium'], ['/usr/bin/chromium', WAYLAND]):
            with self.subTest(values=values):
                self.assertEqual(self.selection(values), (ENCODED, None))
                environment, catalog, inside, linux, fallback = self.boundaries()
                with environment, catalog, inside, linux, fallback:
                    self.assertEqual(self.route.component(values), ENCODED)

    def test_single_uri_selection_returns_original_serialization(self):
        self.catalog()
        for uri in (URL, 'http://localhost:1/', 'http://127.0.0.1:65535/public',
                    'https://[2001:db8::1]:443/a%2fb?x=%25#part'):
            for values in (['/usr/bin/chromium', uri], ['/usr/bin/chromium', WAYLAND, uri]):
                with self.subTest(values=values):
                    self.assertEqual(self.selection(values), (ENCODED, uri),
                                     'The typed selector discarded a valid single URI')
        environment, catalog, inside, linux, fallback = self.boundaries()
        with environment, catalog, inside, linux, fallback:
            self.assertIsNone(self.route.component(['/usr/bin/chromium', URL]),
                              'The legacy encoded-only API silently discarded a URI')

    def test_invalid_uri_and_nonstock_argv_do_not_read_catalog_authority(self):
        self.catalog()
        cases = [['/usr/bin/chromium', value] for value in (
            '', 'https://example.invalid/a b', 'https://u:p@example.invalid/',
            'https://example.invalid/%x0', 'https://example.invalid/%',
            'https://example.invalid/\\path', 'https://example.invalid/\x7f',
            'https://example.invalid/\n', 'https://example.invalid/한글',
            'https:///missing-host', 'http://localhost:0/', 'http://localhost:65536/',
            'file:///tmp/public', 'intent://example.invalid/', 'javascript:1',
            'https://example.invalid/' + 'a' * 2048)]
        cases.extend([
            ['/usr/bin/chromium', '--incognito', URL],
            ['/usr/bin/chromium', '--private', URL],
            ['/usr/bin/chromium', '--user-data-dir=/tmp/public profile', URL],
            ['/usr/bin/chromium', '--profile-directory=Profile 2', URL],
            ['/usr/bin/chromium', URL, 'https://example.invalid/second'],
            ['/usr/bin/chromium', URL, WAYLAND],
            ['/usr/bin/chromium', WAYLAND, WAYLAND, URL],
            ['/usr/bin/chromium', '--ozone-platform=x11', URL],
            ['/tmp/chromium', URL], ['chromium', URL], ['/usr/bin/firefox', URL]])
        for values in cases:
            with self.subTest(values=values):
                self.assertIsNone(self.selection(values))
        self.assertEqual(self.catalog_reads, [], 'Ineligible calls read routing authority')

    def test_profile_environment_override_keeps_original_linux_arguments(self):
        self.catalog()
        for name in ('CHROME_USER_DATA_DIR', 'CHROME_CONFIG_HOME'):
            self.environment[name] = '/tmp/public profile'
            values = ['/usr/bin/chromium', URL]
            with self.subTest(name=name):
                self.assertIsNone(self.selection(values))
                self.assertEqual(self.invoke(values), 52)
                self.assertEqual(self.calls, [('linux', values)])
                self.calls.clear()
            self.environment.pop(name)
        self.assertEqual(self.catalog_reads, [])

    def test_current_catalog_is_required_for_uri_selection(self):
        values = ['/usr/bin/chromium', URL]
        self.assertIsNone(self.selection(values))
        self.catalog(token='public-browser-url-old')
        self.assertIsNone(self.selection(values))
        path = self.catalog((ALIAS + '\tChromium Android\t10372\n') * 2)
        self.assertIsNone(self.selection(values))
        path.unlink()
        path.symlink_to(self.catalog(token='public-browser-url-other'))
        self.assertIsNone(self.selection(values))

    def test_main_passes_initial_uri_to_inside_without_linux_or_desktop_fallback(self):
        self.catalog()
        for values in (['/usr/bin/chromium', URL], ['/usr/bin/chromium', WAYLAND, URL]):
            with self.subTest(values=values):
                self.calls.clear()
                self.assertEqual(self.invoke(values), 17)
                self.assertEqual(self.calls, [('inside', ENCODED, {'initial_url': URL})],
                                 'The main route did not forward the initial URI')

    def test_empty_main_keeps_existing_inside_call_signature(self):
        self.catalog()
        self.assertEqual(self.invoke(['/usr/bin/chromium']), 17)
        self.assertEqual(self.calls, [('inside', ENCODED, {})])

    def test_selected_inside_failure_propagates_without_second_browser(self):
        self.catalog()
        self.inside_error = RuntimeError('Public inside refusal')
        with self.assertRaises(RuntimeError):
            self.invoke(['/usr/bin/chromium', URL])
        self.assertEqual(self.calls, [('inside', ENCODED, {'initial_url': URL})])

    def test_private_profile_custom_and_multi_uri_fallback_preserves_literal_data(self):
        self.catalog()
        profile = self.base / 'public profile'
        profile.mkdir()
        retained = profile / 'Preferences'
        retained.write_bytes(b'public fixture preferences\n')
        before = retained.read_bytes()
        for values in (['/usr/bin/chromium', '--user-data-dir=' + str(profile), URL],
                       ['/usr/bin/chromium', '--incognito', URL],
                       ['/usr/bin/chromium', URL, URL],
                       ['/usr/bin/firefox', URL],
                       ['/usr/bin/chromium', 'https://example.invalid/a b?literal=$(exit 9)']):
            with self.subTest(values=values):
                self.calls.clear()
                self.assertEqual(self.invoke(values), 52)
                self.assertEqual(self.calls, [('linux', values)])
                self.assertEqual(retained.read_bytes(), before)
        self.assertEqual(self.catalog_reads, [])

    def test_x11_main_is_rejected_before_any_route_as_before(self):
        self.catalog()
        self.assertEqual(self.invoke(['/usr/bin/chromium', '--ozone-platform=x11', URL]), 64)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.catalog_reads, [])

    def test_stock_desktop_single_uri_is_substituted_at_exact_terminal_field(self):
        self.catalog()
        for launcher in ('gtk-launch', '/usr/bin/gtk-launch'):
            for commandline in ('/usr/bin/chromium %u', '/usr/bin/chromium %U',
                                '/usr/bin/chromium --ozone-platform=wayland %U'):
                with self.subTest(launcher=launcher, commandline=commandline):
                    self.calls.clear()
                    self.assertEqual(self.invoke([launcher, 'chromium.desktop', URL], True, commandline), 17)
                    self.assertEqual(self.calls, [('inside', ENCODED, {'initial_url': URL})])

    def test_ambiguous_custom_or_fieldless_desktop_keeps_exact_launcher(self):
        self.catalog()
        values = ['gtk-launch', 'chromium.desktop', URL]
        for commandline in ('/usr/bin/chromium', '/usr/bin/chromium %u %U',
                            '/usr/bin/chromium %U%U', '/usr/bin/chromium %F',
                            '/usr/bin/chromium %%', '/usr/bin/chromium %U --ozone-platform=wayland',
                            '/usr/bin/chromium --incognito %U', '/tmp/chromium %U',
                            '/usr/bin/chromium --profile-directory="Profile 2" %U'):
            with self.subTest(commandline=commandline):
                self.calls.clear()
                self.assertEqual(self.invoke(values, True, commandline), 23)
                self.assertEqual(self.calls, [('exec', values)])
        self.assertEqual(self.catalog_reads, [])

    def test_desktop_rejected_uri_extra_arguments_or_missing_catalog_stay_literal(self):
        for values in (['gtk-launch', 'chromium.desktop', URL],
                       ['gtk-launch', 'chromium.desktop', URL, URL],
                       ['gtk-launch', 'chromium.desktop', 'https://example.invalid/a b'],
                       ['gtk-launch', 'firefox.desktop', URL]):
            with self.subTest(values=values):
                self.calls.clear()
                self.assertEqual(self.invoke(values, True), 23)
                self.assertEqual(self.calls, [('exec', values)])


BASH_ENV = '''exec() {
  if [[ ${1-} == -- ]]; then shift; fi
  "$LOOPY_TEST_PYTHON" "$LOOPY_TEST_RUNNER" "$@"
  exit $?
}
'''
RUNNER = r'''import importlib.util,json,os,pathlib,shlex,sys,types
args=sys.argv[1:];record=pathlib.Path(os.environ['LOOPY_TEST_RECORD'])
def observed(kind,value,code):
 record.write_text(json.dumps({'kind':kind,'value':value}));return code
helper='/usr/share/loopy/omarchy-bridge/browser_desktop_launch.py'
if args[:3]!=['/usr/bin/python','-B',helper]:raise SystemExit(observed('linux',args,23))
assets=pathlib.Path(os.environ['LOOPY_TEST_ASSETS']);sys.path.insert(0,str(assets))
class Desktop:
 def get_commandline(self):return '/usr/bin/chromium %U'
class DesktopAppInfo:
 @staticmethod
 def new(name):return Desktop() if name=='chromium.desktop' else None
gi=types.ModuleType('gi');gi.require_version=lambda *_:None
repository=types.ModuleType('gi.repository')
repository.Gio=types.SimpleNamespace(DesktopAppInfo=DesktopAppInfo)
repository.GLib=types.SimpleNamespace(shell_parse_argv=lambda value:(True,shlex.split(value)),Error=ValueError)
gi.repository=repository;sys.modules['gi']=gi;sys.modules['gi.repository']=repository
inside=types.ModuleType('inside_window')
inside.run=lambda encoded,**kwargs:observed('inside',{'encoded':encoded,**kwargs},17)
sys.modules['inside_window']=inside
native_open=os.open
def catalog_open(path,flags,mode=0o777,*,dir_fd=None):
 if os.fspath(path)=='/run/loopy':path=os.environ['LOOPY_TEST_CATALOG']
 return native_open(path,flags,mode,dir_fd=dir_fd)
os.open=catalog_open
os.execvp=lambda file,values:observed('linux',list(values),23)
spec=importlib.util.spec_from_file_location('loopy_url_desktop_subject',assets/'browser_desktop_launch.py')
value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
raise SystemExit(value.main(args[3:]))
'''


class BrowserUrlTransportTests(unittest.TestCase):
    def test_actual_bash_transport_forwards_exact_stock_gtk_url_to_inside(self):
        with tempfile.TemporaryDirectory(prefix='loopy-browser-url-transport-') as directory:
            base = Path(directory)
            catalog = base / 'catalog'
            catalog.mkdir(mode=0o700)
            row = catalog / ('apps-' + TOKEN + '.tsv')
            row.write_text(ALIAS + '\tChromium Android\t10372\n')
            row.chmod(0o600)
            runner = base / 'runner.py'
            runner.write_text(RUNNER)
            bash = base / 'bash-env'
            bash.write_text(BASH_ENV)
            record = base / 'result.json'
            environment = {key: value for key, value in os.environ.items()
                           if key not in ('CHROME_USER_DATA_DIR', 'CHROME_CONFIG_HOME')}
            environment.update(LOOPY_SESSION=TOKEN, BASH_ENV=str(bash), LOOPY_TEST_PYTHON=sys.executable,
                               LOOPY_TEST_RUNNER=str(runner), LOOPY_TEST_RECORD=str(record),
                               LOOPY_TEST_ASSETS=str(ASSETS), LOOPY_TEST_CATALOG=str(catalog),
                               PYTHONDONTWRITEBYTECODE='1')
            child = subprocess.run(['/bin/bash', str(ASSETS / 'loopy-app-launch'), '--',
                                    'gtk-launch', 'chromium.desktop', URL],
                                   env=environment, capture_output=True, timeout=5)
            self.assertEqual(child.stderr, b'', 'The transport fixture crashed')
            self.assertEqual(child.returncode, 17, 'Bash bypassed the typed desktop URI route')
            self.assertEqual(json.loads(record.read_text()),
                             {'kind': 'inside', 'value': {'encoded': ENCODED, 'initial_url': URL}})


if __name__ == '__main__':
    unittest.main()
