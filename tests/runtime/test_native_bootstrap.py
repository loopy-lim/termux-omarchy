"""Native prerequisite planning must refuse guests and unreviewed upgrades."""
import importlib.util
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'runtime'))


def native():
    spec = importlib.util.spec_from_file_location('native_prerequisites', ROOT / 'installer/native.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeBootstrapTests(unittest.TestCase):
    def test_reviewed_proot_versions_are_accepted_without_widening_future_versions(self):
        import omarchy_install
        module = native()
        for value in ('5.8', '5.8.0', '5.8.2-1', '5.9.0', '5.9.0-2'):
            with self.subTest(value=value):
                self.assertTrue(omarchy_install.supported_proot_version(value))
                self.assertTrue(module.supported_proot(value))
        for value in ('5.7.9', '5.9', '5.9.1', '5.10.0', '6.0.0', '5.9.0-2junk'):
            with self.subTest(value=value):
                self.assertFalse(omarchy_install.supported_proot_version(value))
                self.assertFalse(module.supported_proot(value))

    def test_install_constrains_existing_dependency_versions_before_apt_execution(self):
        module = native()
        state = {'python': '3.13', 'proot-distro': '5.9.0'}
        events = []
        def command(args, *, capture=True, timeout=30):
            self.assertIn('python=3.13', args)
            self.assertIn('proot-distro=5.9.0', args)
            self.assertIn('--no-upgrade', args)
            self.assertIn('--no-remove', args)
            self.assertIn('APT::Get::AllowUnauthenticated=false', args)
            if '--simulate' in args:
                events.append('simulate')
                return 'Inst mesa (26.2.4 repository [aarch64])\n'
            self.assertIn('-y', args)
            self.assertFalse(capture)
            events.append('install')
            state['mesa'] = '26.2.4'
            return ''
        module.run = command
        module.installed_packages = lambda: dict(state)
        result = module.install_missing(['mesa'], dict(state))
        self.assertEqual(events, ['simulate', 'install'])
        self.assertEqual(result, {'python': '3.13', 'proot-distro': '5.9.0', 'mesa': '26.2.4'})

    def test_native_context_refuses_guest_secondary_user_and_wrong_architecture(self):
        module = native()
        env = {'HOME': '/data/data/com.termux/files/home', 'PREFIX': '/data/data/com.termux/files/usr'}
        kwargs = dict(system='linux', machine='aarch64', uid=10300,
                      executable='/data/data/com.termux/files/usr/bin/python3.13', tracer=0)
        module.validate_context(env, **kwargs)
        module.validate_context(env, **dict(kwargs, system='android'))
        for changes in ({'system': 'darwin'}, {'machine': 'x86_64'}, {'uid': 1010300},
                        {'uid': 0}, {'tracer': 23}, {'executable': '/usr/bin/python3'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                module.validate_context(env, **dict(kwargs, **changes))
        for key in ('PD_CONTAINER', 'OMARCHY_PROOT', 'PROOT_ROOTFS'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.validate_context(dict(env, **{key: 'guest'}), **kwargs)

    def test_android_python_reads_tracer_before_native_check_and_delivery_readiness(self):
        module = native()
        env = {'HOME': str(module.HOME), 'PREFIX': str(module.PREFIX)}
        module.sources = lambda: None
        module.installed_packages = lambda: dict.fromkeys(module.PACKAGES, '1.0') | {'proot-distro': '5.9.0'}
        verification = SimpleNamespace(validate=lambda: {}, read=lambda *args: b'{}')
        spec = importlib.util.spec_from_file_location('delivery_install', ROOT / 'installer/install.py')
        delivery = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'verify': verification}):
            spec.loader.exec_module(delivery)
        asset_api = SimpleNamespace(require=module.require, verify_file=lambda *args, **kwargs: None)
        def command(args, **kwargs):
            if args == ['/system/bin/getprop', 'ro.build.version.sdk']:
                return SimpleNamespace(returncode=0, stdout='35\n')
            self.assertEqual(args, ['/system/bin/pm', 'path', 'com.termux.x11'])
            return SimpleNamespace(returncode=0, stdout='package:/data/app/reviewed/base.apk\n')
        with patch.dict(os.environ, env, clear=True), patch.object(sys, 'platform', 'android'), \
             patch.object(sys, 'executable', str(module.PREFIX / 'bin/python3')), \
             patch.object(os, 'uname', return_value=SimpleNamespace(machine='aarch64')), \
             patch.object(os, 'getuid', return_value=10323), \
             patch.object(Path, 'read_text', return_value='TracerPid:\t0\n') as status, \
             patch.object(Path, 'is_file', return_value=True), \
             patch.object(Path, 'stat', return_value=SimpleNamespace(st_mode=0o20660)), \
             patch.object(os, 'access', return_value=True), \
             patch.dict(sys.modules, {'verify': verification, 'native': module, 'assets': asset_api}), \
             patch.object(subprocess, 'run', side_effect=command), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(['--check']), 0)
            self.assertEqual(delivery.native_ready({'input/termux-x11.apk': {}}),
                             (module.HOME, module.PREFIX, module.installed_packages()))
            self.assertEqual(status.call_count, 2)

    def test_unreviewed_missing_proot_candidate_is_refused_before_any_install(self):
        module = native()
        events = []
        module.sources = lambda: None
        module.installed_packages = lambda: {'python': '3.13'}
        def command(args, *, capture=True, timeout=30):
            events.append(args)
            if args[0].endswith('/apt-cache'):
                return 'proot-distro:\n  Installed: (none)\n  Candidate: 5.9.1\n'
            self.assertEqual(args[-1], 'update')
            return ''
        module.run = command
        with self.assertRaisesRegex(ValueError, 'native-proot-version-unreviewed'):
            module.apply({'python': '3.13'})
        self.assertEqual(len(events), 2)
        self.assertFalse(any('install' in args for args in events))

    def test_missing_reviewed_proot_candidate_is_pinned_for_simulation_and_install(self):
        module = native()
        state = {'python': '3.13'}
        events = []
        def command(args, *, capture=True, timeout=30):
            if args[0].endswith('/apt-cache'):
                return 'proot-distro:\n  Installed: (none)\n  Candidate: 5.9.0-1\n'
            self.assertIn('proot-distro=5.9.0-1', args)
            self.assertNotIn('proot-distro', args)
            if '--simulate' in args:
                events.append('simulate')
                return 'Inst proot-distro (5.9.0-1 repository [aarch64])\n'
            events.append('install')
            state['proot-distro'] = '5.9.0-1'
            return ''
        module.run = command
        module.installed_packages = lambda: dict(state)
        self.assertEqual(module.install_missing(['proot-distro'], dict(state)), state)
        self.assertEqual(events, ['simulate', 'install'])

    def test_plan_installs_only_missing_packages(self):
        module = native()
        installed = {name: '1.0' for name in module.PACKAGES if name not in ('mesa', 'xorg-xprop')}
        installed['proot-distro'] = '5.9.0'
        row = module.plan(installed)
        self.assertEqual(row['missingPackages'], ['mesa', 'xorg-xprop'])
        self.assertFalse(row['fullFreshInstallVerified'])

    def test_input_companion_is_handled_by_exact_delivery_assets(self):
        module = native()
        self.assertNotIn('termux-x11-nightly', module.PACKAGES)
        self.assertNotIn('bin/termux-x11', module.FILES)
        self.assertIn('xkeyboard-config', module.PACKAGES)

    def test_apt_solver_rejects_upgrades_and_removals(self):
        module = native()
        self.assertEqual(module.check_solver('Inst mesa (26.2.4 repository [aarch64])\nConf mesa (26.2.4 repository [aarch64])\n', {}), {'mesa'})
        for output, installed in (
            ('Inst libc++ [27] (28 repository [aarch64])\n', {'libc++': '27'}),
            ('Remv old-package [1.0]\n', {'old-package': '1.0'}),
            ('Inst python (3.13 repository [aarch64])\n', {'python': '3.13'}),
            ('Inst proot-distro (5.9.1 repository [aarch64])\n', {}),
        ):
            with self.subTest(output=output), self.assertRaises(ValueError):
                module.check_solver(output, installed)

    def test_apt_configuration_requires_existing_signature_trust(self):
        module = native()
        module.check_apt_sources('deb https://packages.termux.dev/apt/termux-main stable main\n')
        for content in ('deb [trusted=yes] https://packages.termux.dev/apt/termux-main stable main\n',
                        'Types: deb\nURIs: https://packages.termux.dev/apt/termux-main\nTrusted: yes\n',
                        'deb [allow-insecure=yes] https://packages.termux.dev/apt/termux-main stable main\n'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                module.check_apt_sources(content)

    def test_apply_on_host_refuses_before_home_changes(self):
        if sys.platform == 'linux' and os.uname().machine == 'aarch64':
            self.skipTest('requires an unsupported host platform')
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            (home / 'preserve').write_bytes(b'kept')
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'installer/native.py'), '--apply'],
                                    env=dict(os.environ, HOME=str(home)), capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn('Traceback', result.stderr)
            self.assertEqual(list(home.iterdir()), [home / 'preserve'])


if __name__ == '__main__':
    unittest.main()
