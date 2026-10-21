"""Execute selection and session-report validation, without trusting guest env text."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
TOKEN = '12345678-1234-1234-1234-123456789abc'


class GraphicsSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'guest/desktop/usr/local/lib/loopy/graphics_session.py'
        spec = importlib.util.spec_from_file_location('graphics_session', path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        sys.path.insert(0, str(path.parent))

    def report(self, selected='llvmpipe'):
        return dict(schema=1, uid=os.getuid(), token=TOKEN, selected=selected,
                    providers=[dict(id=selected, status='ready', pixelVerified=True,
                                    renderer='llvmpipe (LLVM 20.1)', presentationVerified=False)])

    def test_unverified_or_foreign_selection_cannot_enable_gl(self):
        for change in ({'uid': 0}, {'token': 'other'}, {'selected': 'virpipe'}, {'schema': 2}):
            report = self.report(); report.update(change)
            self.assertEqual(self.module.selected_provider(report, TOKEN), 'cairo')
        report = self.report(); report['providers'][0]['pixelVerified'] = False
        self.assertEqual(self.module.selected_provider(report, TOKEN), 'cairo')

    def test_malformed_report_and_renderer_claim_fail_closed(self):
        for providers in (None, 3, 'bad', [None, 3]):
            report = self.report(); report['providers'] = providers
            self.assertEqual(self.module.selected_provider(report, TOKEN), 'cairo')
        report = self.report(); report['providers'][0]['renderer'] = 'Adreno (llvmpipe unavailable)'
        self.assertEqual(self.module.selected_provider(report, TOKEN), 'cairo')
        report = self.report(); report['schema'] = True
        self.assertEqual(self.module.selected_provider(report, TOKEN), 'cairo')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ('graphics-' + TOKEN + '.json')
            path.write_text('[]')
            self.assertEqual(self.module.read_report(TOKEN, folder), {})
            path.unlink(); os.mkfifo(path)
            self.assertEqual(self.module.read_report(TOKEN, folder), {})

    def test_software_route_sanitizes_graphics_env_and_preserves_output(self):
        env = self.module.session_environment(self.report(), TOKEN,
            {'HOME': '/root', 'LD_PRELOAD': 'evil', 'GALLIUM_DRIVER': 'virpipe',
             'MESA_LOADER_DRIVER_OVERRIDE': 'zink', 'MESA_GLES_VERSION_OVERRIDE': '99.0',
             'VK_ICD_FILENAMES': '/bad', 'GDK_GL': 'evil'})
        self.assertEqual(env['GALLIUM_DRIVER'], 'llvmpipe')
        self.assertEqual(env['LIBGL_ALWAYS_SOFTWARE'], 'true')
        self.assertEqual(env['WLR_RENDERER'], 'pixman')
        self.assertEqual(env['GDK_GL'], 'disable')
        self.assertNotIn('LD_PRELOAD', env)
        self.assertNotIn('VK_ICD_FILENAMES', env)
        self.assertNotIn('MESA_GLES_VERSION_OVERRIDE', env)

    def test_atomic_report_is_private_and_does_not_cross_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve() / ('graphics-' + TOKEN + '.json')
            self.module.write_report(path, self.report())
            self.assertEqual(json.loads(path.read_text())['token'], TOKEN)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.unlink(); path.symlink_to(Path(folder) / 'outside')
            with self.assertRaises(ValueError): self.module.write_report(path, self.report())

    def test_proxy_requires_verified_current_session_and_live_socket(self):
        report = self.report()
        report['virglSocket'] = '/run/loopy/virgl-' + TOKEN + '.sock'
        report['providers'].append(dict(id='virpipe', status='ready', pixelVerified=True, renderer='virgl (ANGLE)'))
        with patch('graphics_probe.socket_available', return_value=True):
            environment = self.module.proxy_environment(report, TOKEN, {})
            self.assertEqual(environment['GALLIUM_DRIVER'], 'virpipe')
            self.assertEqual(environment['VTEST_SOCKET_NAME'], report['virglSocket'])
            self.assertEqual(environment['GDK_GL'], 'gles')
            report['token'] = 'stale'
            self.assertIsNone(self.module.proxy_environment(report, TOKEN, {}))
        report['token'] = TOKEN
        with patch('graphics_probe.socket_available', return_value=False):
            self.assertIsNone(self.module.proxy_environment(report, TOKEN, {}))

    def test_proxy_execution_keeps_native_gles_profile_without_enabling_default_desktop_gl(self):
        report = self.report()
        report['virglSocket'] = '/run/loopy/virgl-' + TOKEN + '.sock'
        report['providers'].append(dict(id='virpipe', status='ready', pixelVerified=True,
                                        renderer='virgl (ANGLE)'))
        with patch.dict(os.environ, LOOPY_SESSION=TOKEN), \
                patch.object(self.module, 'read_report', return_value=report), \
                patch('graphics_probe.socket_available', return_value=True), \
                patch.object(self.module.os, 'execvpe', side_effect=RuntimeError('exec boundary')) as execute:
            with self.assertRaisesRegex(RuntimeError, 'exec boundary'):
                self.module.run_gl(['--virgl', '/usr/bin/python3', 'graphics_demo.py'])
        environment = execute.call_args.args[2]
        self.assertEqual(environment['GDK_GL'], 'gles')
        self.assertEqual(environment['GALLIUM_DRIVER'], 'virpipe')
        self.assertEqual(self.module.session_environment(report, TOKEN, {})['GDK_GL'], 'disable')


if __name__ == '__main__':
    unittest.main()
