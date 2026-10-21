"""Exercise the shared browser main route using real owned catalog files.

Only the GTK launch boundaries are replaced. No GTK, device, profile, browser
child or network is started; inside_wire.catalog performs its real file checks.
"""
import importlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'android/assets/omarchy-bridge'
ALIAS = 'org.chromium.chrome/com.google.android.apps.chrome.Main'
# Hand-checked canonical base64url of ALIAS, without padding.
ENCODED = 'b3JnLmNocm9taXVtLmNocm9tZS9jb20uZ29vZ2xlLmFuZHJvaWQuYXBwcy5jaHJvbWUuTWFpbg'
TOKEN = 'public-browser-route-current'
PLAIN = ['/usr/bin/chromium']


def launch_module():
    spec = importlib.util.spec_from_file_location('loopy_browser_inside_route_test',
                                                 ASSETS / 'browser_launch.py')
    value = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(value)
    finally:
        sys.dont_write_bytecode = previous
    return value


class BrowserInsideRouteTests(unittest.TestCase):
    def setUp(self):
        self.launch = launch_module()
        self.wire = importlib.import_module('inside_wire')
        self.inside = importlib.import_module('inside_window')
        self.directory = tempfile.TemporaryDirectory(prefix='loopy-browser-route-')
        self.addCleanup(self.directory.cleanup)
        self.catalog_directory = Path(self.directory.name)
        self.catalog_directory.chmod(0o700)
        self.calls = []
        self.catalog_reads = []
        self.inside_error = None

    def catalog(self, text=None, token=TOKEN):
        path = self.catalog_directory / ('apps-' + token + '.tsv')
        path.write_text(ALIAS + '\tChromium Android\t10372\n' if text is None else text)
        path.chmod(0o600)
        return path

    def invoke(self, argv, token=TOKEN):
        original = list(argv)
        environment = dict(os.environ)
        environment.pop('LOOPY_SESSION', None)
        if token is not None:
            environment['LOOPY_SESSION'] = token
        native_open = os.open

        def open_catalog(path, flags, mode=0o777, *, dir_fd=None):
            if os.fspath(path) == '/run/loopy':
                self.catalog_reads.append('/run/loopy')
                path = self.catalog_directory
            return native_open(path, flags, mode, dir_fd=dir_fd)

        def linux_run(values):
            self.calls.append(('linux', list(values)))
            return 52

        def inside_run(encoded):
            self.calls.append(('inside', encoded))
            if self.inside_error is not None:
                raise self.inside_error
            return 17

        with patch.dict(os.environ, environment, clear=True), \
                patch.object(self.launch, 'run', side_effect=linux_run), \
                patch.object(self.inside, 'run', side_effect=inside_run), \
                patch.object(self.wire.os, 'open', side_effect=open_catalog):
            result = self.launch.main(['--', *argv])
        self.assertEqual(argv, original, 'Routing modified the selected browser arguments')
        return result

    def expect_linux(self, argv, token=TOKEN):
        self.calls.clear()
        self.assertEqual(self.invoke(argv, token), 52)
        self.assertEqual(self.calls, [('linux', argv)])

    def test_plain_default_chromium_opens_exact_catalog_alias_inside(self):
        self.catalog()
        self.assertEqual(self.invoke(PLAIN), 17,
                         'The normal browser route still launched Linux Chromium')
        self.assertEqual(self.calls, [('inside', ENCODED)])

    def test_existing_wayland_only_argument_opens_the_same_inside_alias(self):
        self.catalog()
        argv = ['/usr/bin/chromium', '--ozone-platform=wayland']
        self.assertEqual(self.invoke(argv), 17,
                         'The original Wayland-only browser call missed the inside route')
        self.assertEqual(self.calls, [('inside', ENCODED)])

    def test_other_catalog_apps_cannot_replace_the_fixed_chromium_alias(self):
        self.catalog('notion.id/notion.local.id.MainActivity\tNotion\t10316\n'
                     + ALIAS + '\tChromium Android\t10372\n')
        self.assertEqual(self.invoke(PLAIN), 17)
        self.assertEqual(self.calls, [('inside', ENCODED)])

    def test_custom_arguments_keep_every_linux_argument_literal(self):
        self.catalog()
        cases = [
            ['/usr/bin/chromium', 'https://example.invalid/a b?literal=$(exit 9)'],
            ['/usr/bin/chromium', '--incognito'],
            ['/usr/bin/chromium', '--private'],
            ['/usr/bin/chromium', '--user-data-dir=/tmp/public profile'],
            ['/usr/bin/chromium', '--profile-directory=Profile 2'],
            ['/usr/bin/chromium', '--ozone-platform=wayland', '--ozone-platform=wayland'],
            ['/usr/bin/chromium', ''],
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                self.expect_linux(argv)
        self.assertEqual(self.catalog_reads, [], 'Custom browser calls read routing authority')

    def test_other_executable_paths_keep_the_original_linux_command(self):
        self.catalog()
        for argv in (['/usr/lib/chromium/chromium'], ['/tmp/chromium'],
                     ['/usr/bin/chromium-browser'], ['/usr/bin/firefox'], ['chromium']):
            with self.subTest(argv=argv):
                self.expect_linux(argv)
        self.assertEqual(self.catalog_reads, [])

    def test_explicit_chromium_environment_keeps_the_selected_linux_profile(self):
        self.catalog()
        for name in ('CHROME_USER_DATA_DIR', 'CHROME_CONFIG_HOME'):
            with self.subTest(name=name), patch.dict(os.environ, {name: '/tmp/public custom profile'}):
                self.expect_linux(PLAIN)
        self.assertEqual(self.catalog_reads, [])

    def test_absent_or_old_session_catalog_keeps_linux_startup_errors(self):
        self.expect_linux(PLAIN)
        self.catalog(token='public-browser-route-old')
        self.expect_linux(PLAIN)
        self.catalog('org.chromium.chrome/org.chromium.chrome.browser.ChromeTabbedActivity'
                     '\tDifferent component\t10372\n')
        self.expect_linux(PLAIN)

    def test_missing_or_invalid_session_never_uses_a_current_catalog_by_guessing(self):
        self.catalog()
        for token in (None, '', '../public-browser-route-current', 'x' * 65):
            with self.subTest(token=token):
                self.expect_linux(PLAIN, token)
        self.assertEqual(self.catalog_reads, [])

    def test_duplicate_or_malformed_catalog_refuses_inside_before_launch(self):
        rows = [
            (ALIAS + '\tChromium Android\t10372\n') * 2,
            ALIAS + '\tChromium Android\n',
            ALIAS + '\tChromium Android\t2000\n',
            ALIAS + '\tChromium Android\t0\n',
            ALIAS + '\tChromium Android\tinvalid\n',
            ALIAS + '\tChromium Android\t2147483648\n',
            ALIAS + '\t' + 'x' * 65536 + '\t10372\n',
        ]
        for data in rows:
            with self.subTest(size=len(data)):
                self.catalog(data)
                self.expect_linux(PLAIN)

    def test_symlink_catalog_cannot_authorize_an_inside_launch(self):
        target = self.catalog(token='public-browser-route-other')
        (self.catalog_directory / ('apps-' + TOKEN + '.tsv')).symlink_to(target)
        self.expect_linux(PLAIN)

    def test_inside_launch_failure_does_not_start_a_second_linux_browser(self):
        self.catalog()
        self.inside_error = RuntimeError('Public inside launch refusal')
        with self.assertRaises(RuntimeError):
            self.invoke(PLAIN)
        self.assertEqual(self.calls, [('inside', ENCODED)])

    def test_invalid_main_arguments_are_rejected_before_any_launcher(self):
        for argv in ([], ['--'], ['--', ''], ['--', '/usr/bin/chromium', None],
                     ['--', '/usr/bin/chromium', '--ozone-platform=x11']):
            with self.subTest(size=len(argv)):
                with patch.object(self.launch, 'run', side_effect=AssertionError('Unexpected Linux launch')), \
                        patch.object(self.inside, 'run', side_effect=AssertionError('Unexpected inside launch')):
                    self.assertEqual(self.launch.main(argv), 64)


if __name__ == '__main__':
    unittest.main()
