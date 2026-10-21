"""Add a terminal command without changing installed runtime or user entries."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / 'termux/omarchy_terminal.py'
INSTALLER = REPO / 'termux/omarchy_terminal_install.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def identity(path):
    row = path.lstat()
    return [row.st_dev, row.st_ino, row.st_uid]


def snapshot(root):
    return {str(path.relative_to(root)): (path.lstat().st_ino, path.lstat().st_mode,
            path.lstat().st_mtime_ns, os.readlink(path) if path.is_symlink() else
            path.read_bytes() if path.is_file() else None)
            for path in [root, *root.rglob('*')]}


class TerminalCommandTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'short terminal command missing')
        self.assertTrue(INSTALLER.is_file(), 'additive terminal command installer missing')
        self.launcher = load(SOURCE, 'tested_terminal_launcher')
        self.installer = load(INSTALLER, 'tested_terminal_installer')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name).resolve()
        self.home, self.prefix = self.path / 'home', self.path / 'usr'
        self.home.mkdir(mode=0o700); self.prefix.mkdir(mode=0o700)
        (self.prefix / 'bin').mkdir(mode=0o700)
        self.interpreter = self.prefix / 'bin/python3'
        self.interpreter.write_bytes(b'public interpreter'); self.interpreter.chmod(0o700)
        self.root = self.home / '.local/share/loopy-omarchy'
        self.root.mkdir(parents=True, mode=0o700)
        for name, expected in self.launcher.RUNTIME_SHA.items():
            candidates = (REPO / 'termux' / name,
                REPO / 'build/deliverables/LoopyOmarchy-Termux-native-setup-20261009-08' / name)
            data = next(path.read_bytes() for path in candidates
                        if hashlib.sha256(path.read_bytes()).hexdigest() == expected)
            (self.root / name).write_bytes(data)
            (self.root / name).chmod(0o600)
        self.container = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy'
        self.rootfs = self.container / 'rootfs'; self.rootfs.mkdir(parents=True, mode=0o700)
        self.record = dict(schema=1, phase='INSTALLED', uid=os.getuid(), root=identity(self.root),
            home=str(self.home), prefix=str(self.prefix), container='loopy-omarchy',
            bundle_sha256=self.launcher.BUNDLE_SHA, container_identity=identity(self.container),
            rootfs_identity=identity(self.rootfs), runtime_files=self.launcher.RUNTIME_SHA)
        self.write_record()
        (self.root / 'runtime-state.json').write_text('{"phase":"ready","token":"public-live"}')
        (self.root / 'runtime-state.json').chmod(0o600)
        for name in ('install.lock', 'runtime-control.lock'):
            (self.root / name).write_bytes(b''); (self.root / name).chmod(0o600)
        (self.home / '.zshrc').write_bytes(b'public personal rc')
        self.proc = self.path / 'proc-status'
        self.proc.write_text('Name:\tpython\nUid:\t' + '\t'.join([str(os.getuid())] * 4) + '\n')
        self.launcher.PROC_STATUS = self.proc
        self.launcher.HOME, self.launcher.PREFIX = self.home, self.prefix
        self.command = self.prefix / 'bin/loopy-omarchy'
        self.source = self.path / 'omarchy_terminal.py'
        shutil.copyfile(SOURCE, self.source); self.source.chmod(0o600)

    def write_record(self):
        target = self.root / 'install.json'
        target.write_text(json.dumps(self.record)); target.chmod(0o600)

    def install(self):
        # Host macOS lacks /proc. All UID parsing, owned files and root checks are real.
        original = self.installer.load_source
        def host_source(path):
            module, data = original(path)
            module.PROC_STATUS = self.proc
            return module, data
        with mock.patch.object(self.installer, 'load_source', side_effect=host_source):
            return self.installer.install(self.source, self.home, self.prefix)

    def rejected(self):
        before = snapshot(self.home), snapshot(self.prefix)
        with self.assertRaises((ValueError, OSError)):
            self.install()
        self.assertEqual((snapshot(self.home), snapshot(self.prefix)), before)

    def test_installs_one_command_preserves_live_runtime_and_repeat_is_no_write(self):
        before = snapshot(self.home)
        result = self.install()
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(self.command.read_bytes(), SOURCE.read_bytes())
        self.assertEqual(self.command.stat().st_mode & 0o777, 0o700)
        self.assertEqual(snapshot(self.home), before)
        installed = snapshot(self.path)
        self.assertEqual(self.install()['status'], 'unchanged')
        self.assertEqual(snapshot(self.path), installed)

    def test_all_actions_forward_exactly_to_existing_launcher_with_clean_environment(self):
        for args, action in [([], 'start'), (['start'], 'start'), (['stop'], 'stop'),
                             (['status'], 'status'), (['doctor'], 'doctor')]:
            with self.subTest(action=action), mock.patch.object(self.launcher.os, 'execve') as execute:
                with mock.patch.dict(os.environ, PYTHONPATH='/public/untrusted', PYTHONHOME='/public/untrusted'):
                    self.launcher.main(args)
                executable, argv, env = execute.call_args.args
                self.assertEqual(executable, str(self.interpreter))
                self.assertEqual(argv, [str(self.interpreter), str(self.root / 'omarchy.py'), action])
                self.assertNotIn('PYTHONPATH', env); self.assertNotIn('PYTHONHOME', env)
                self.assertEqual(env['HOME'], str(self.home)); self.assertEqual(env['PREFIX'], str(self.prefix))

    def test_unsupported_arguments_do_not_execute_runtime(self):
        for args in (['shell'], ['start', 'extra'], ['; touch /public/file']):
            with mock.patch.object(self.launcher.os, 'execve') as execute:
                with self.assertRaises(ValueError): self.launcher.main(args)
                execute.assert_not_called()

    def test_existing_conflicting_regular_symlink_hardlink_or_mode_is_preserved(self):
        self.command.write_bytes(b'public personal command'); self.command.chmod(0o700)
        self.rejected(); self.command.unlink()
        self.command.symlink_to(self.source); self.rejected(); self.command.unlink()
        os.link(self.source, self.command); self.rejected(); self.command.unlink()
        self.command.write_bytes(SOURCE.read_bytes()); self.command.chmod(0o600)
        self.rejected()

    def test_changed_source_or_installed_runtime_is_refused_without_output(self):
        self.source.write_bytes(SOURCE.read_bytes() + b'\n# changed\n'); self.rejected()
        self.source.write_bytes(SOURCE.read_bytes())
        for name in self.launcher.RUNTIME_SHA:
            target = self.root / name; previous = target.read_bytes()
            target.write_bytes(previous + b'\n# changed\n'); self.rejected(); target.write_bytes(previous)

    def test_simulated_root_or_mismatched_native_uid_is_refused(self):
        self.proc.write_text('Uid:\t0\t0\t0\t0\n'); self.rejected()
        self.proc.write_text('Uid:\t' + '\t'.join([str(os.getuid() + 1)] * 4) + '\n'); self.rejected()
        self.proc.write_text('Uid:\t' + '\t'.join(map(str, [os.getuid(), os.getuid() + 1, os.getuid(), os.getuid()])) + '\n')
        self.rejected()

    def test_wrong_journal_or_replaced_rootfs_refuses_before_command_creation(self):
        original = dict(self.record)
        for key, value in [('uid', os.getuid() + 1), ('root', [0, 0, 0]), ('phase', 'INSTALLING'),
                           ('home', '/public/other'), ('bundle_sha256', '0' * 64), ('runtime_files', {})]:
            self.record = dict(original, **{key: value}); self.write_record(); self.rejected()
        self.record = original; self.write_record()
        self.rootfs.rename(self.container / 'previous-rootfs'); self.rootfs.mkdir(mode=0o700)
        self.rejected()

    def test_symlink_managed_parent_and_writable_bin_are_refused(self):
        parent = self.home / '.local/share'
        parent.rename(self.home / '.local/original-share'); parent.symlink_to(self.home / '.local/original-share')
        self.rejected(); parent.unlink(); (self.home / '.local/original-share').rename(parent)
        (self.prefix / 'bin').chmod(0o777); self.rejected()

    def test_publication_race_never_overwrites_concurrent_command(self):
        publish = self.installer.publish
        def conflict(fd, source, target):
            self.command.write_bytes(b'public concurrent command'); self.command.chmod(0o700)
            return publish(fd, source, target)
        with mock.patch.object(self.installer, 'publish', side_effect=conflict):
            with self.assertRaises(OSError): self.install()
        self.assertEqual(self.command.read_bytes(), b'public concurrent command')
        self.assertFalse(any(p.name.startswith('.loopy-omarchy-') for p in self.command.parent.iterdir()))

    def test_replaced_bin_directory_is_refused_without_publishing_to_detached_directory(self):
        original = self.installer.load_source
        def host_source(path):
            module, data = original(path)
            module.PROC_STATUS = self.proc
            context, calls = module.context, 0
            def replace_after_recheck(home, prefix):
                nonlocal calls
                result = context(home, prefix); calls += 1
                if calls == 2:
                    (self.prefix / 'bin').rename(self.prefix / 'previous-bin')
                    (self.prefix / 'bin').mkdir(mode=0o700)
                    shutil.copyfile(self.prefix / 'previous-bin/python3', self.interpreter)
                    self.interpreter.chmod(0o700)
                return result
            module.context = replace_after_recheck
            return module, data
        with mock.patch.object(self.installer, 'load_source', side_effect=host_source):
            with self.assertRaises(ValueError):
                self.installer.install(self.source, self.home, self.prefix)
        self.assertFalse(self.command.exists())
        self.assertFalse((self.prefix / 'previous-bin/loopy-omarchy').exists())

    def test_real_exec_boundary_forwards_status_and_removes_python_overrides(self):
        self.interpreter.write_text('#!' + sys.executable + '\n' +
            'import json,os,sys\nprint(json.dumps({"args":sys.argv[1:],"home":os.environ["HOME"],'
            '"pythonpath":os.environ.get("PYTHONPATH"),"pythonhome":os.environ.get("PYTHONHOME")}))\n')
        runner = self.path / 'run.py'
        runner.write_text('import importlib.util\nfrom pathlib import Path\n' +
            f'spec=importlib.util.spec_from_file_location("command",{str(SOURCE)!r})\n' +
            'm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n' +
            f'm.HOME=Path({str(self.home)!r});m.PREFIX=Path({str(self.prefix)!r});m.PROC_STATUS=Path({str(self.proc)!r})\n' +
            'm.main(["status"])\n')
        result = subprocess.run([sys.executable, '-I', str(runner)], capture_output=True, text=True,
            timeout=5, env=dict(os.environ, PYTHONPATH='/public/untrusted', PYTHONHOME='/public/untrusted'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), dict(args=[str(self.root / 'omarchy.py'), 'status'],
            home=str(self.home), pythonpath=None, pythonhome=None))

    def test_existing_command_changed_during_read_is_not_adopted(self):
        self.command.write_bytes(SOURCE.read_bytes()); self.command.chmod(0o700)
        original = self.installer.load_source
        def host_source(path):
            module, data = original(path); module.PROC_STATUS = self.proc
            read = module.read
            def changed_mode(path, maximum, dir_fd=None):
                result = read(path, maximum, dir_fd)
                if path == 'loopy-omarchy': self.command.chmod(0o600)
                return result
            module.read = changed_mode
            return module, data
        with mock.patch.object(self.installer, 'load_source', side_effect=host_source):
            with self.assertRaises(ValueError):
                self.installer.install(self.source, self.home, self.prefix)
        self.assertEqual(self.command.stat().st_mode & 0o777, 0o600)

    def test_android_rename_publication_succeeds_when_temporary_name_was_consumed(self):
        def rename(fd, source, target):
            # Android Python lacks os.link; renameat2 consumes the source name.
            self.assertFalse(self.command.exists())
            os.rename(source, target, src_dir_fd=fd, dst_dir_fd=fd)
        with mock.patch.object(self.installer, 'publish', side_effect=rename):
            try: result = self.install()
            except FileNotFoundError: self.fail('successful Android rename was reported as an installation failure')
            self.assertEqual(result['status'], 'installed')
        self.assertEqual(self.command.read_bytes(), SOURCE.read_bytes())
        self.assertEqual(self.command.stat().st_nlink, 1)

    def migration_fixture(self):
        previous = REPO / 'tests/fixtures/omarchy-terminal-684c2365.py'
        self.assertEqual(hashlib.sha256(previous.read_bytes()).hexdigest(),
                         self.installer.PREVIOUS_SOURCE_SHA,
                         'migration fixture must be the exact reviewed predecessor')
        self.old_command = previous.read_bytes()
        self.command.write_bytes(self.old_command); self.command.chmod(0o700)
        # Exercise a distinct reviewed successor without relying on future resource hashes.
        self.new_command = SOURCE.read_bytes() + b'\n# public successor fixture\n'
        self.source.write_bytes(self.new_command)
        patch = mock.patch.object(self.installer, 'SOURCE_SHA', hashlib.sha256(self.new_command).hexdigest())
        patch.start(); self.addCleanup(patch.stop)

    def test_exact_previous_command_migration_retains_original_backup_and_journal(self):
        self.migration_fixture(); runtime_before = snapshot(self.home)
        try: result = self.install()
        except ValueError as error: self.fail('Exact previous command needs a backed-up migration: ' + str(error))
        self.assertEqual(result['status'], 'updated')
        self.assertEqual(self.command.read_bytes(), self.new_command)
        journal = json.loads((self.root / 'terminal-command-update.json').read_bytes())
        self.assertEqual(journal['phase'], 'INSTALLED')
        self.assertEqual(journal['previousLauncherSHA256'], hashlib.sha256(self.old_command).hexdigest())
        backup = self.root / journal['backupDirectory']
        self.assertEqual((backup / 'loopy-omarchy').read_bytes(), self.old_command)
        self.assertEqual((backup / 'loopy-omarchy').stat().st_mode & 0o777, 0o600)
        after = snapshot(self.home)
        for name, value in runtime_before.items():
            if name != '.local/share/loopy-omarchy': self.assertEqual(after[name], value, name)
        before = snapshot(self.path)
        self.assertEqual(self.install()['status'], 'unchanged')
        self.assertEqual(snapshot(self.path), before)

    def test_command_migration_failure_keeps_backup_and_unknown_journal(self):
        self.migration_fixture(); replace = os.replace
        def interrupted(source, destination, **kwargs):
            if destination == 'loopy-omarchy': raise OSError('public command migration interruption')
            return replace(source, destination, **kwargs)
        with mock.patch.object(self.installer.os, 'replace', side_effect=interrupted):
            with self.assertRaises((ValueError, OSError)): self.install()
        path = self.root / 'terminal-command-update.json'
        self.assertTrue(path.exists(), 'command migration journal missing')
        journal = json.loads(path.read_bytes())
        self.assertEqual(journal['phase'], 'UPDATE_UNKNOWN')
        self.assertEqual((self.root / journal['backupDirectory'] / 'loopy-omarchy').read_bytes(), self.old_command)
        self.assertEqual(self.command.read_bytes(), self.old_command)
        self.rejected()

    def test_command_migration_rejects_changed_old_entry_and_tampered_backup(self):
        self.migration_fixture()
        self.command.write_bytes(self.old_command + b'\n# personal edit\n'); self.rejected()
        self.command.write_bytes(self.old_command)
        try: self.install()
        except ValueError as error: self.fail('Exact command migration unavailable: ' + str(error))
        journal = json.loads((self.root / 'terminal-command-update.json').read_bytes())
        (self.root / journal['backupDirectory'] / 'loopy-omarchy').write_bytes(b'public changed backup')
        self.rejected()

    def test_successor_migration_replaces_stale_predecessor_journal(self):
        self.migration_fixture()
        # A journal left by an unjournalled later replacement: its launcher claim is
        # stale, but the bytes on disk are the exact reviewed predecessor.
        prior = dict(schema=1, phase='INSTALLED', uid=os.getuid(), root=identity(self.root),
                     prefix=str(self.prefix), previousLauncherSHA256='a' * 64,
                     launcherSHA256='c' * 64,
                     backupDirectory='.terminal-command-backup-' + 'b' * 32)
        (self.root / 'terminal-command-update.json').write_text(json.dumps(prior))
        (self.root / 'terminal-command-update.json').chmod(0o600)
        try: result = self.install()
        except ValueError as error: self.fail('Successor migration unavailable: ' + str(error))
        self.assertEqual(result['status'], 'updated')
        self.assertEqual(self.command.read_bytes(), self.new_command)
        journal = json.loads((self.root / 'terminal-command-update.json').read_bytes())
        self.assertEqual(journal['previousLauncherSHA256'], self.installer.PREVIOUS_SOURCE_SHA)
        self.assertEqual(journal['launcherSHA256'], self.installer.SOURCE_SHA)
        backup = self.root / journal['backupDirectory']
        self.assertEqual((backup / 'loopy-omarchy').read_bytes(), self.old_command)

    def test_modified_predecessor_bytes_still_refuse_under_prior_journal(self):
        self.migration_fixture()
        prior = dict(schema=1, phase='INSTALLED', uid=os.getuid(), root=identity(self.root),
                     prefix=str(self.prefix), previousLauncherSHA256='a' * 64,
                     launcherSHA256='c' * 64)
        (self.root / 'terminal-command-update.json').write_text(json.dumps(prior))
        (self.root / 'terminal-command-update.json').chmod(0o600)
        self.command.write_bytes(self.old_command + b'\n# personal edit\n')
        self.rejected()


if __name__ == '__main__': unittest.main()
