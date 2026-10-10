"""Native PRoot temporary storage stays separate from the guest's short socket path."""
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime'))
import omarchy_commands as commands


class ProotTempTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        folder = Path(self.temporary.name)
        self.home, self.prefix, self.root, self.host = [folder / name for name in ('home', 'prefix', 'root', 'host')]
        for path in (self.home, self.prefix, self.root, self.host): path.mkdir(mode=0o700)

    def test_native_environment_overrides_absent_empty_and_foreign_proot_tmp(self):
        for injected in (None, '', '/foreign/unwritable/tmp', '/run/user/1000'):
            with self.subTest(injected=injected):
                external = {'KEEP_PUBLIC_FIXTURE': 'unchanged'}
                if injected is not None: external['PROOT_TMP_DIR'] = injected
                with mock.patch.dict(os.environ, external, clear=True):
                    before = dict(os.environ)
                    result = commands.environment(self.home, self.prefix, self.host)
                    self.assertEqual(result.get('PROOT_TMP_DIR'), str(self.prefix / 'tmp'))
                    self.assertEqual(result['TMPDIR'], str(self.prefix / 'tmp'))
                    self.assertEqual(dict(os.environ), before)
                    self.assertEqual(result['KEEP_PUBLIC_FIXTURE'], 'unchanged')

    def test_generated_native_proot_keeps_corrected_path_while_guest_uses_short_bind(self):
        with mock.patch.dict(os.environ, {'PROOT_TMP_DIR': '/foreign/unwritable/tmp'}, clear=True):
            env = commands.environment(self.home, self.prefix, self.host)
        runtime = SimpleNamespace(env=env, prefix=self.prefix, root=self.root, host=self.host,
                                  short=self.home / 'short')
        result = commands.commands(runtime, {'display': ':11', 'token': 'public-session'})
        args, native = result[2]
        guest = dict(args[index + 1].split('=', 1) for index, value in enumerate(args) if value == '-e')
        self.assertEqual(native.get('PROOT_TMP_DIR'), str(self.prefix / 'tmp'))
        self.assertEqual(native['TMPDIR'], str(self.prefix / 'tmp'))
        self.assertEqual(guest['TMPDIR'], '/run/user/1000')
        self.assertEqual(guest['XDG_RUNTIME_DIR'], '/run/user/1000')
        # proot-distro reconstructs the environment passed to native PRoot from -e.
        self.assertEqual(guest.get('PROOT_TMP_DIR'), str(self.prefix / 'tmp'))
        self.assertEqual(args.count('PROOT_TMP_DIR=' + str(self.prefix / 'tmp')), 1)
        self.assertEqual(args[args.index('PROOT_TMP_DIR=' + str(self.prefix / 'tmp')) - 1], '-e')
        self.assertIn(str(runtime.short) + ':/run/user/1000', args)
        self.assertEqual(env['PROOT_TMP_DIR'], str(self.prefix / 'tmp'))


if __name__ == '__main__': unittest.main()
