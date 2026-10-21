"""Run the real shell caller against a harmless browser boundary."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'termux/omarchy-launch-webapp'
ORIGINAL = ROOT / 'build/diagnostics/termux-omarchy-original-launch-service-source-20261009-01/omarchy-launch-webapp'
ORIGINAL_SHA = '3d4d96eb622789e597760a07b4288db2a7221eaa1635aee1c76a9f3d2c9b0aa5'


class WebappAudioTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'owned Unix-audio webapp source is missing')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.binary = self.base / 'bin'; self.binary.mkdir()
        self.home = self.base / 'home'; self.home.mkdir()
        self.personal = self.home / '.config/chromium/Default/Preferences'
        self.personal.parent.mkdir(parents=True)
        self.personal.write_bytes(b'personal profile remains untouched')
        self.before = (self.personal.read_bytes(), self.personal.stat().st_mtime_ns)
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.binary) + ':' + os.environ['PATH'],
                        PULSE_SERVER='tcp:foreign.invalid:4713', PULSE_COOKIE='/foreign/cookie',
                        OMARCHY_PROOT='1', WEBAPP_EXIT='0')
        self.command('chromium', 'exec ' + shlex.quote(sys.executable) + ' -c ' + shlex.quote(
            'import json,os,sys; print(json.dumps({"argv":sys.argv[1:],'
            '"server":os.environ.get("PULSE_SERVER"),"cookie":os.environ.get("PULSE_COOKIE")}));'
            'sys.exit(int(os.environ["WEBAPP_EXIT"]))') + ' "$@"\n')

    def command(self, name, body):
        path = self.binary / name; path.write_text('#!/bin/bash\n' + body); path.chmod(0o700)

    def run_webapp(self, args, exit_code=0):
        result = subprocess.run(['/bin/bash', str(SOURCE), *args], env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, exit_code, result.stderr)
        self.assertEqual((self.personal.read_bytes(), self.personal.stat().st_mtime_ns), self.before)
        return json.loads(result.stdout)

    def test_proot_uses_owned_unix_server_and_cookie_preserving_literal_arguments(self):
        url = 'https://example.invalid/a?literal=$(exit 99)&a=a b; echo bad'
        args = [url, '--user-data-dir=' + str(self.home / 'existing profile'), '', '--force-device-scale-factor=1.5']
        row = self.run_webapp(args)
        self.assertEqual(row['server'], 'unix:/run/user/1000/pulse/native')
        self.assertEqual(row['cookie'], '/run/user/1000/pulse/cookie')
        self.assertEqual(row['argv'], ['--no-sandbox', '--disable-dev-shm-usage', '--password-store=basic',
                                       '--app=' + url, *args[1:]])
        self.assertFalse((self.home / 'existing profile').exists())

    def test_browser_exit_status_is_preserved(self):
        self.env['WEBAPP_EXIT'] = '23'
        self.run_webapp(['https://example.invalid'], exit_code=23)

    def test_non_proot_branch_keeps_existing_default_browser_and_audio_environment(self):
        self.env['OMARCHY_PROOT'] = '0'
        self.command('xdg-settings', 'printf "%s\\n" chromium.desktop\n')
        self.command('setsid', 'exec "$@"\n')
        self.command('uwsm-app', '[[ $1 == -- ]] || exit 90\nshift\nexec "$@"\n')
        apps = self.home / '.local/share/applications'; apps.mkdir(parents=True)
        (apps / 'chromium.desktop').write_text('[Desktop Entry]\nExec=' + str(self.binary / 'chromium') + ' %U\n')
        row = self.run_webapp(['https://example.invalid', '--custom=value with spaces'])
        self.assertEqual(row['argv'], ['--app=https://example.invalid', '--custom=value with spaces'])
        self.assertEqual(row['server'], self.env['PULSE_SERVER']); self.assertEqual(row['cookie'], self.env['PULSE_COOKIE'])

    def test_only_owned_audio_environment_differs_from_pinned_bundle_script(self):
        original = ORIGINAL.read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), ORIGINAL_SHA)
        old = b'  export PULSE_SERVER=tcp:127.0.0.1:4715\n'
        replacement = (b'  export PULSE_SERVER=unix:/run/user/1000/pulse/native\n'
                       b'  export PULSE_COOKIE=/run/user/1000/pulse/cookie\n')
        self.assertEqual(original.count(old), 1)
        self.assertEqual(SOURCE.read_bytes(), original.replace(old, replacement))


if __name__ == '__main__': unittest.main()
