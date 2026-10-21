"""Pinned runtime migration against actual files, locks, guard and journals."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'termux/omarchy_runtime_update.py'
FIXTURE = Path(__file__).resolve().parents[1] / 'tests/fixtures/omarchy-terminal-cccb8ac0.py'
NAMES = ('omarchy.py', 'processes.py', 'omarchy_runtime.py', 'omarchy_resources.py',
         'omarchy_boot.py', 'omarchy_input.py', 'omarchy_audio.py', 'omarchy_android.py',
         'omarchy_android_client.py', 'omarchy_commands.py', 'omarchy_proot.py')
HEAL_NAMES = ('omarchy.py', 'omarchy_audio.py', 'omarchy_commands.py',
              'omarchy_input.py', 'omarchy_proot.py', 'omarchy_runtime.py')
VIDEO_NAMES = ('omarchy_android.py', 'omarchy_android_client.py')
DIRECT_NAMES = ('omarchy_android.py',)
FREEZE_NAMES = ('omarchy_android.py',)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class RuntimeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'pinned runtime migration is missing')
        sys.path.insert(0, str(SOURCE.parent))
        self.addCleanup(sys.path.remove, str(SOURCE.parent))
        spec = importlib.util.spec_from_file_location('tested_runtime_update', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name).resolve()
        self.home, self.prefix = self.folder / 'home', self.folder / 'prefix'
        self.home.mkdir(mode=0o700); self.prefix.mkdir(mode=0o700)
        self.root = self.home / '.local/share/loopy-omarchy'
        self.root.mkdir(parents=True, mode=0o700)
        self.rootfs = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy/rootfs'
        self.rootfs.mkdir(parents=True, mode=0o700)
        self.sources = self.folder / 'sources'; self.sources.mkdir(mode=0o700)
        self.new = {name: ('VALUE = 1\n# ' + name + '\n').encode() for name in NAMES}
        self.old = {name: data for name, data in self.new.items() if name not in NAMES[-2:]}
        self.old['omarchy_runtime.py'] = b'VALUE = 0\n# previous reviewed runtime\n'
        self.pins = {name: sha(data) for name, data in self.new.items()}
        for name, data in self.new.items(): self.write(self.sources / name, data)
        for name, data in self.old.items(): self.write(self.root / name, data)
        backend = self.root / 'weston/x11-backend.so'
        backend.parent.mkdir(mode=0o700); self.write(backend, b'public backend')
        for target in ('install.lock', 'runtime-control.lock'): self.write(self.root / target, b'')
        for target, data in (('private-user', b'public preserved user content'),):
            self.write(self.rootfs / target, data)
        self.installed = {'schema': 1, 'phase': 'INSTALLED', 'uid': os.getuid(),
            'root': self.identity(self.root), 'home': str(self.home), 'prefix': str(self.prefix),
            'container': 'loopy-omarchy', 'bundle_sha256': self.m.base.OUTER_SHA,
            'container_identity': self.identity(self.rootfs.parent),
            'rootfs_identity': self.identity(self.rootfs),
            'managed_files': {'weston/x11-backend.so': sha(b'public backend')},
            'runtime_files': {name: sha(data) for name, data in self.old.items()}}
        self.write_json(self.root / 'install.json', self.installed)
        self.original_install = (self.root / 'install.json').read_bytes()
        self.state = {'schema': 1, 'uid': os.getuid(), 'root': self.identity(self.root),
                      'phase': 'stopped', 'terminationConfirmed': True}
        self.write_json(self.root / 'runtime-state.json', self.state)
        guard = self.root / 'proot-guard'; guard.mkdir(mode=0o700)
        guard_files = {'proot': b'public guard', 'loader': b'public loader',
                       'libandroid-shmem.so': b'public shmem'}
        for name, data in guard_files.items():
            self.write(guard / name, data, 0o600 if name.endswith('.so') else 0o700)
        guard_pins = {name: sha(data) for name, data in guard_files.items()}
        self.write_json(self.root / 'proot-guard.json', dict(schema=1, phase='INSTALLED',
            uid=os.getuid(), root=self.identity(self.root), directory=self.identity(guard), files=guard_pins))
        for patch in (mock.patch.multiple(self.m.base, RUNTIME_SHA=self.pins,
                HOST_FILES={'weston/x11-backend.so': 'fixture'}, FILE_SHA={'fixture': sha(b'public backend')}),
                mock.patch.object(self.m, 'OLD_RUNTIME_SHA', sha(self.old['omarchy_runtime.py'])),
                mock.patch.object(self.m, 'INVENTORY_COMMANDS_SHA', self.pins['omarchy_commands.py'], create=True),
                mock.patch.object(self.m, 'OLD_RESOURCES_SHA', sha(self.old['omarchy_resources.py']), create=True),
                mock.patch.object(self.m, 'PREVIOUS_RUNTIME_SHA', self.pins, create=True),
                mock.patch.object(self.m.proot_guard, 'FILES', guard_pins)):
            patch.start(); self.addCleanup(patch.stop)

    @staticmethod
    def identity(path):
        value = path.lstat(); return [value.st_dev, value.st_ino, value.st_uid]

    @staticmethod
    def write(path, data, mode=0o600):
        path.write_bytes(data); path.chmod(mode)

    def write_json(self, path, value):
        self.write(path, json.dumps(value, sort_keys=True).encode())

    def update(self):
        return self.m.update(self.sources, self.home, self.prefix)

    def inventory(self):
        return {str(p.relative_to(self.root)): (p.lstat().st_ino, p.lstat().st_mode,
                p.lstat().st_mtime_ns, os.readlink(p) if p.is_symlink() else p.read_bytes())
                for p in self.root.rglob('*') if p.is_file() or p.is_symlink()}

    def assert_refused_without_writes(self):
        before = self.inventory()
        with self.assertRaises((ValueError, OSError)): self.update()
        self.assertEqual(before, self.inventory())
        self.assertFalse(list(self.root.glob('.runtime-update-*')))

    def test_known_migration_backs_up_originals_and_publishes_all_eleven_pins(self):
        # Catches missing backups, replacing unrelated modules, or stale install.json.
        unrelated = {n: self.identity(self.root / n) for n in self.old if n != 'omarchy_runtime.py'}
        result = self.update()
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(json.loads((self.root / 'install.json').read_bytes())['runtime_files'], self.pins)
        for name, data in self.new.items(): self.assertEqual((self.root / name).read_bytes(), data)
        self.assertEqual(unrelated, {n: self.identity(self.root / n) for n in unrelated})
        backup = self.root / result['backupDirectory']
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        self.assertEqual((backup / 'omarchy_runtime.py').read_bytes(), self.old['omarchy_runtime.py'])
        self.assertEqual((backup / 'install.json').read_bytes(), self.original_install)
        self.assertEqual((self.rootfs / 'private-user').read_bytes(), b'public preserved user content')
        self.assertEqual(json.loads((self.root / 'runtime-state.json').read_bytes()), self.state)

    def test_completed_update_is_idempotent_without_file_or_journal_writes(self):
        self.update(); before = self.inventory()
        self.assertEqual(self.update()['phase'], 'INSTALLED')
        self.assertEqual(before, self.inventory())

    def test_complete_current_install_without_migration_journal_is_no_write(self):
        for name, data in self.new.items(): self.write(self.root / name, data)
        self.write_json(self.root / 'install.json', dict(self.installed, runtime_files=self.pins))
        before = self.inventory()
        self.assertEqual(self.update()['phase'], 'INSTALLED')
        self.assertEqual(before, self.inventory())
        self.assertFalse((self.root / 'runtime-update.json').exists())

    def test_source_hash_and_syntax_are_checked_before_installation_writes(self):
        target = self.sources / 'omarchy_commands.py'
        self.write(target, b'VALUE = 2\n'); self.assert_refused_without_writes()
        invalid = b'invalid python {\n'; self.write(target, invalid)
        with mock.patch.dict(self.pins, {'omarchy_commands.py': sha(invalid)}):
            with self.assertRaises(SyntaxError): self.update()
        self.assertEqual((self.root / 'install.json').read_bytes(), self.original_install)

    def test_unknown_previous_runtime_is_preserved(self):
        self.write(self.root / 'omarchy_runtime.py', b'public user runtime')
        self.assert_refused_without_writes()

    def test_modified_unchanged_module_is_preserved(self):
        self.write(self.root / 'omarchy_audio.py', b'public user audio')
        self.assert_refused_without_writes()

    def test_preexisting_new_file_refuses_even_when_its_hash_is_current(self):
        for content in (b'public unknown file', self.new['omarchy_commands.py']):
            self.write(self.root / 'omarchy_commands.py', content)
            self.assert_refused_without_writes()

    def test_unknown_or_partially_changed_install_record_is_preserved(self):
        changed = dict(self.installed, runtime_files=dict(self.installed['runtime_files']))
        changed['runtime_files']['omarchy_runtime.py'] = self.pins['omarchy_runtime.py']
        self.write_json(self.root / 'install.json', changed)
        self.assert_refused_without_writes()

    def test_missing_or_unconfirmed_or_running_state_prevents_migration(self):
        state = self.root / 'runtime-state.json'; state.unlink()
        self.assert_refused_without_writes()
        for value in ({'phase': 'ready', 'terminationConfirmed': False},
                      {'phase': 'stopped', 'terminationConfirmed': False}):
            self.write_json(state, dict(self.state, **value)); self.assert_refused_without_writes()

    def test_guard_is_required_and_corruption_is_not_a_legacy_fallback(self):
        self.write(self.root / 'proot-guard/proot', b'corrupt guard', 0o700)
        self.assert_refused_without_writes()
        (self.root / 'proot-guard/proot').unlink()
        self.assert_refused_without_writes()

    def test_replaced_installation_or_state_identity_is_refused(self):
        for field in ('root', 'container_identity', 'rootfs_identity'):
            value = dict(self.installed); value[field] = [0, 0, os.getuid()]
            self.write_json(self.root / 'install.json', value); self.assert_refused_without_writes()
        self.write_json(self.root / 'install.json', self.installed)
        self.write_json(self.root / 'runtime-state.json', dict(self.state, root=[0, 0, os.getuid()]))
        self.assert_refused_without_writes()

    def test_both_existing_locks_block_before_backup_or_target_changes(self):
        for name in ('install.lock', 'runtime-control.lock'):
            with (self.root / name).open('rb+') as locked:
                fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assert_refused_without_writes()

    def test_target_symlink_or_hardlink_is_not_overwritten(self):
        path = self.root / 'omarchy_runtime.py'; path.unlink()
        other = self.home / 'original'; self.write(other, self.old['omarchy_runtime.py'])
        path.symlink_to(other); self.assert_refused_without_writes()
        path.unlink(); os.link(other, path); self.assert_refused_without_writes()
        self.assertEqual(other.read_bytes(), self.old['omarchy_runtime.py'])

    def test_mid_update_failure_preserves_exact_backup_and_refuses_retry(self):
        # Catches automatic retry over partially installed files after process failure.
        replace = os.replace
        def interrupted(source, destination, **kwargs):
            if destination == 'omarchy_runtime.py': raise OSError('public interruption')
            return replace(source, destination, **kwargs)
        with mock.patch.object(self.m.os, 'replace', interrupted):
            with self.assertRaises(ValueError): self.update()
        row = json.loads((self.root / 'runtime-update.json').read_bytes())
        self.assertEqual(row['phase'], 'UPDATE_UNKNOWN')
        backup = self.root / row['backupDirectory']
        self.assertEqual((backup / 'omarchy_runtime.py').read_bytes(), self.old['omarchy_runtime.py'])
        self.assertEqual((backup / 'install.json').read_bytes(), self.original_install)
        self.assertEqual((self.root / 'install.json').read_bytes(), self.original_install)
        before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())

    def test_install_journal_failure_does_not_claim_migration_complete(self):
        replace = os.replace
        def interrupted(source, destination, **kwargs):
            if destination == 'install.json': raise OSError('public journal failure')
            return replace(source, destination, **kwargs)
        with mock.patch.object(self.m.os, 'replace', interrupted):
            with self.assertRaises(ValueError): self.update()
        row = json.loads((self.root / 'runtime-update.json').read_bytes())
        self.assertEqual(row['phase'], 'UPDATE_UNKNOWN')
        self.assertEqual((self.root / 'install.json').read_bytes(), self.original_install)
        for name, data in self.new.items(): self.assertEqual((self.root / name).read_bytes(), data)

    def test_unknown_transaction_is_preserved_before_any_backup(self):
        self.write_json(self.root / 'runtime-update.json', {'schema': 1, 'phase': 'UPDATE_UNKNOWN'})
        self.assert_refused_without_writes()

    def guarded_fixture(self):
        self.first_row = self.update()
        self.first_journal = (self.root / 'runtime-update.json').read_bytes()
        self.first_identity = self.identity(self.root / 'runtime-update.json')
        self.guarded_install = (self.root / 'install.json').read_bytes()
        self.guarded_commands = self.new['omarchy_commands.py']
        patch = mock.patch.object(self.m, 'OLD_COMMANDS_SHA', sha(self.guarded_commands), create=True)
        patch.start(); self.addCleanup(patch.stop)
        self.new['omarchy_commands.py'] = b'VALUE = 2\n# session-owned TMPDIR\n'
        self.pins['omarchy_commands.py'] = sha(self.new['omarchy_commands.py'])
        self.m.INVENTORY_COMMANDS_SHA = self.pins['omarchy_commands.py']
        self.write(self.sources / 'omarchy_commands.py', self.new['omarchy_commands.py'])

    def test_guarded_eleven_file_update_changes_only_commands_and_preserves_history(self):
        # Catches rejecting the exact installed guard version or overwriting its receipt.
        self.guarded_fixture()
        unchanged = {n: self.identity(self.root / n) for n in NAMES if n != 'omarchy_commands.py'}
        first_backup = {p.name: p.read_bytes() for p in (self.root / self.first_row['backupDirectory']).iterdir()}
        try:
            result = self.update()
        except ValueError as error:
            self.fail('Exact guarded runtime must support the one-file TMPDIR update: ' + str(error))
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(result['applied'], ['omarchy_commands.py'])
        self.assertEqual(unchanged, {n: self.identity(self.root / n) for n in unchanged})
        self.assertEqual((self.root / 'runtime-update.json').read_bytes(), self.first_journal)
        self.assertEqual(self.identity(self.root / 'runtime-update.json'), self.first_identity)
        self.assertEqual(json.loads((self.root / 'runtime-update-tmpdir.json').read_bytes()), result)
        backup = self.root / result['backupDirectory']
        self.assertEqual((backup / 'omarchy_commands.py').read_bytes(), self.guarded_commands)
        self.assertEqual((backup / 'install.json').read_bytes(), self.guarded_install)
        self.assertEqual((backup / 'runtime-update.json').read_bytes(), self.first_journal)
        self.assertEqual(first_backup, {p.name: p.read_bytes() for p in (self.root / self.first_row['backupDirectory']).iterdir()})
        self.assertEqual(result['previousJournal']['path'], 'runtime-update.json')
        self.assertEqual(result['previousJournal']['sha256'], sha(self.first_journal))
        self.assertEqual(json.loads((self.root / 'install.json').read_bytes())['runtime_files'], self.pins)
        before = self.inventory(); self.update(); self.assertEqual(before, self.inventory())

    def test_guarded_update_refuses_modified_other_module_or_unknown_commands(self):
        self.guarded_fixture()
        for name in ('omarchy_runtime.py', 'omarchy_commands.py'):
            path = self.root / name; original = path.read_bytes()
            self.write(path, b'VALUE = 99\n# user edit\n'); before = self.inventory()
            with self.assertRaises(ValueError): self.update()
            self.assertEqual(before, self.inventory()); self.write(path, original)

    def test_guarded_update_requires_its_exact_installed_predecessor_journal(self):
        self.guarded_fixture()
        path = self.root / 'runtime-update.json'
        row = json.loads(path.read_bytes()); row['runtime_files']['omarchy_commands.py'] = '0' * 64
        self.write_json(path, row); before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())
        path.unlink(); before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())

    def test_guarded_install_record_failure_keeps_both_journals_and_rollback_bytes(self):
        self.guarded_fixture()
        replace = os.replace
        def interrupted(source, destination, **kwargs):
            if destination == 'install.json': raise OSError('public chained journal failure')
            return replace(source, destination, **kwargs)
        with mock.patch.object(self.m.os, 'replace', interrupted):
            with self.assertRaises(ValueError): self.update()
        path = self.root / 'runtime-update-tmpdir.json'
        self.assertTrue(path.exists(), 'Second transaction must have its own durable journal')
        row = json.loads(path.read_bytes())
        self.assertEqual(row['phase'], 'UPDATE_UNKNOWN')
        self.assertEqual((self.root / 'runtime-update.json').read_bytes(), self.first_journal)
        self.assertEqual((self.root / 'install.json').read_bytes(), self.guarded_install)
        self.assertEqual((self.root / row['backupDirectory'] / 'omarchy_commands.py').read_bytes(), self.guarded_commands)
        self.assertEqual((self.root / row['backupDirectory'] / 'runtime-update.json').read_bytes(), self.first_journal)
        before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())

    def test_final_bytes_without_completed_second_journal_are_not_adopted(self):
        self.guarded_fixture()
        self.write(self.root / 'omarchy_commands.py', self.new['omarchy_commands.py'])
        row = json.loads((self.root / 'install.json').read_bytes()); row['runtime_files'] = self.pins
        self.write_json(self.root / 'install.json', row); before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())

    def test_null_journal_is_not_treated_as_absent_on_current_runtime(self):
        for name, data in self.new.items(): self.write(self.root / name, data)
        self.write_json(self.root / 'install.json', dict(self.installed, runtime_files=self.pins))
        for name in ('runtime-update.json', 'runtime-update-tmpdir.json', 'runtime-update-inventory.json',
                     'runtime-update-proot-temp.json'):
            path = self.root / name; self.write(path, b'null')
            before = self.inventory()
            with self.assertRaises(ValueError): self.update()
            self.assertEqual(before, self.inventory()); path.unlink()

    def next_resources(self):
        self.previous_resources = self.new['omarchy_resources.py']
        self.new['omarchy_resources.py'] = b'VALUE = 3\n# tolerate disappearing inventory entries\n'
        self.pins['omarchy_resources.py'] = sha(self.new['omarchy_resources.py'])
        self.write(self.sources / 'omarchy_resources.py', self.new['omarchy_resources.py'])

    def inventory_fixture(self):
        self.guarded_fixture(); self.second_row = self.update()
        self.history_bytes = {name: (self.root / name).read_bytes()
            for name in ('runtime-update.json', 'runtime-update-tmpdir.json')}
        self.history_identities = {name: self.identity(self.root / name) for name in self.history_bytes}
        self.before_inventory_install = (self.root / 'install.json').read_bytes()
        self.next_resources()

    def test_inventory_update_changes_one_file_and_backs_up_both_exact_history_journals(self):
        self.inventory_fixture()
        unchanged = {n: self.identity(self.root / n) for n in NAMES if n != 'omarchy_resources.py'}
        result = self.update()
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(result['applied'], ['omarchy_resources.py'])
        self.assertEqual(result['previousJournals'], {n: sha(b) for n, b in self.history_bytes.items()})
        self.assertEqual(unchanged, {n: self.identity(self.root / n) for n in unchanged})
        self.assertEqual(json.loads((self.root / 'runtime-update-inventory.json').read_bytes()), result)
        backup = self.root / result['backupDirectory']
        self.assertEqual(set(p.name for p in backup.iterdir()),
            {'omarchy_resources.py', 'install.json', *self.history_bytes})
        self.assertEqual((backup / 'omarchy_resources.py').read_bytes(), self.previous_resources)
        self.assertEqual((backup / 'install.json').read_bytes(), self.before_inventory_install)
        for name, data in self.history_bytes.items():
            self.assertEqual((backup / name).read_bytes(), data)
            self.assertEqual((self.root / name).read_bytes(), data)
            self.assertEqual(self.identity(self.root / name), self.history_identities[name])
        self.assertEqual(json.loads((self.root / 'install.json').read_bytes())['runtime_files'], self.pins)
        before = self.inventory(); self.update(); self.assertEqual(before, self.inventory())

    def test_legacy_nine_to_latest_still_works_after_resources_pin_changes(self):
        self.next_resources(); result = self.update()
        self.assertEqual(set(result['applied']), {'omarchy_runtime.py', 'omarchy_commands.py',
            'omarchy_proot.py', 'omarchy_resources.py'})
        self.assertEqual((self.root / result['backupDirectory'] / 'omarchy_resources.py').read_bytes(),
            self.previous_resources)
        before = self.inventory(); self.update(); self.assertEqual(before, self.inventory())

    def test_guarded_eleven_to_latest_preserves_old_resources_pin(self):
        self.guarded_fixture(); self.next_resources(); result = self.update()
        self.assertEqual(set(result['applied']), {'omarchy_commands.py', 'omarchy_resources.py'})
        self.assertEqual((self.root / 'runtime-update.json').read_bytes(), self.first_journal)
        before = self.inventory(); self.update(); self.assertEqual(before, self.inventory())

    def test_inventory_migration_refuses_missing_changed_or_uncertain_history(self):
        self.inventory_fixture()
        for name in self.history_bytes:
            path = self.root / name; data = path.read_bytes()
            path.unlink(); before = self.inventory()
            with self.assertRaises(ValueError): self.update()
            self.assertEqual(before, self.inventory())
            self.write(path, data)
            row = json.loads(data); row['phase'] = 'UPDATE_UNKNOWN'; self.write_json(path, row)
            before = self.inventory()
            with self.assertRaises(ValueError): self.update()
            self.assertEqual(before, self.inventory()); self.write(path, data)
        # A valid-looking first journal with changed bytes invalidates the second journal's SHA link.
        self.write(self.root / 'runtime-update.json', self.history_bytes['runtime-update.json'] + b'\n')
        before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())

    def test_inventory_install_failure_keeps_old_history_and_exact_rollback_bytes(self):
        self.inventory_fixture(); replace = os.replace
        def interrupted(source, destination, **kwargs):
            if destination == 'install.json': raise OSError('public inventory journal failure')
            return replace(source, destination, **kwargs)
        with mock.patch.object(self.m.os, 'replace', interrupted):
            with self.assertRaises(ValueError): self.update()
        row = json.loads((self.root / 'runtime-update-inventory.json').read_bytes())
        self.assertEqual(row['phase'], 'UPDATE_UNKNOWN')
        self.assertEqual((self.root / 'install.json').read_bytes(), self.before_inventory_install)
        self.assertEqual((self.root / row['backupDirectory'] / 'omarchy_resources.py').read_bytes(),
            self.previous_resources)
        for name, data in self.history_bytes.items(): self.assertEqual((self.root / name).read_bytes(), data)
        before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())

    def test_inventory_final_bytes_without_completed_third_journal_are_not_adopted(self):
        self.inventory_fixture()
        self.write(self.root / 'omarchy_resources.py', self.new['omarchy_resources.py'])
        row = json.loads((self.root / 'install.json').read_bytes()); row['runtime_files'] = self.pins
        self.write_json(self.root / 'install.json', row); before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())

    def test_inventory_chain_hash_and_nonresource_files_remain_fail_closed(self):
        self.inventory_fixture()
        for name in ('omarchy_resources.py', 'omarchy_commands.py'):
            path = self.root / name; data = path.read_bytes()
            self.write(path, b'VALUE = 99\n# unrelated edit\n'); before = self.inventory()
            with self.assertRaises(ValueError): self.update()
            self.assertEqual(before, self.inventory()); self.write(path, data)
        self.update()
        path = self.root / 'runtime-update-tmpdir.json'; self.write(path, path.read_bytes() + b'\n')
        before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())

    def next_proot_temp(self):
        self.previous_commands = self.new['omarchy_commands.py']
        self.new['omarchy_commands.py'] = b'VALUE = 4\n# explicit native PROOT_TMP_DIR\n'
        self.pins['omarchy_commands.py'] = sha(self.new['omarchy_commands.py'])
        self.write(self.sources / 'omarchy_commands.py', self.new['omarchy_commands.py'])

    def proot_temp_fixture(self):
        self.inventory_fixture(); self.third_row = self.update()
        self.prior_history = {name: (self.root / name).read_bytes() for name in
            ('runtime-update.json', 'runtime-update-tmpdir.json', 'runtime-update-inventory.json')}
        self.prior_identities = {name: self.identity(self.root / name) for name in self.prior_history}
        self.before_proot_install = (self.root / 'install.json').read_bytes()
        self.before_proot_inventory = self.inventory()
        self.next_proot_temp()

    def test_proot_temp_update_changes_one_file_and_preserves_three_stage_history(self):
        self.proot_temp_fixture()
        unchanged = {n: self.identity(self.root / n) for n in NAMES if n != 'omarchy_commands.py'}
        result = self.update()
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(result['applied'], ['omarchy_commands.py'])
        self.assertEqual(result['previousJournals'], {n: sha(b) for n, b in self.prior_history.items()})
        self.assertEqual(unchanged, {n: self.identity(self.root / n) for n in unchanged})
        self.assertEqual(json.loads((self.root / 'runtime-update-proot-temp.json').read_bytes()), result)
        backup = self.root / result['backupDirectory']
        self.assertEqual(set(p.name for p in backup.iterdir()),
                         {'omarchy_commands.py', 'install.json', *self.prior_history})
        self.assertEqual((backup / 'omarchy_commands.py').read_bytes(), self.previous_commands)
        self.assertEqual((backup / 'install.json').read_bytes(), self.before_proot_install)
        for name, data in self.prior_history.items():
            self.assertEqual((backup / name).read_bytes(), data)
            self.assertEqual((self.root / name).read_bytes(), data)
            self.assertEqual(self.identity(self.root / name), self.prior_identities[name])
        # Existing backup trees, state, user content and every unrelated runtime file remain exact.
        after = self.inventory()
        for name, value in self.before_proot_inventory.items():
            if name not in ('install.json', 'omarchy_commands.py'): self.assertEqual(after[name], value)
        self.assertEqual(json.loads((self.root / 'install.json').read_bytes())['runtime_files'], self.pins)
        for name, data in self.new.items(): self.assertEqual((self.root / name).read_bytes(), data)
        self.update(); self.assertEqual(after, self.inventory())

    def test_proot_temp_migration_rejects_missing_unknown_or_relinked_history(self):
        self.proot_temp_fixture()
        for name, data in self.prior_history.items():
            path = self.root / name; path.unlink(); before = self.inventory()
            with self.assertRaises(ValueError): self.update()
            self.assertEqual(before, self.inventory())
            row = json.loads(data); row['phase'] = 'UPDATE_UNKNOWN'; self.write_json(path, row)
            before = self.inventory()
            with self.assertRaises(ValueError): self.update()
            self.assertEqual(before, self.inventory()); self.write(path, data)
        path = self.root / 'runtime-update-inventory.json'
        row = json.loads(path.read_bytes()); row['previousJournals']['runtime-update.json'] = '0' * 64
        self.write_json(path, row); before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())

    def test_proot_temp_fourth_journal_binds_all_three_previous_journal_bytes(self):
        self.proot_temp_fixture(); self.update()
        for name, data in self.prior_history.items():
            path = self.root / name; self.write(path, data + b'\n'); before = self.inventory()
            with self.assertRaises(ValueError): self.update()
            self.assertEqual(before, self.inventory()); self.write(path, data)

    def test_proot_temp_unknown_fourth_journal_is_not_adopted(self):
        self.proot_temp_fixture()
        path = self.root / 'runtime-update-proot-temp.json'
        for record in (None, {'schema': 1, 'phase': 'UPDATE_UNKNOWN'}):
            self.write_json(path, record); before = self.inventory()
            with self.assertRaises(ValueError): self.update()
            self.assertEqual(before, self.inventory())

    def test_proot_temp_install_failure_keeps_three_journals_and_rollback_bytes(self):
        self.proot_temp_fixture(); replace = os.replace
        def interrupted(source, destination, **kwargs):
            if destination == 'install.json': raise OSError('public proot-temp journal failure')
            return replace(source, destination, **kwargs)
        with mock.patch.object(self.m.os, 'replace', interrupted):
            with self.assertRaises(ValueError): self.update()
        row = json.loads((self.root / 'runtime-update-proot-temp.json').read_bytes())
        self.assertEqual(row['phase'], 'UPDATE_UNKNOWN')
        self.assertEqual((self.root / 'install.json').read_bytes(), self.before_proot_install)
        self.assertEqual((self.root / 'omarchy_commands.py').read_bytes(), self.new['omarchy_commands.py'])
        backup = self.root / row['backupDirectory']
        self.assertEqual((backup / 'omarchy_commands.py').read_bytes(), self.previous_commands)
        for name, data in self.prior_history.items():
            self.assertEqual((self.root / name).read_bytes(), data)
            self.assertEqual((backup / name).read_bytes(), data)
        before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())

    def test_proot_temp_final_bytes_without_fourth_journal_are_not_adopted(self):
        self.proot_temp_fixture()
        self.write(self.root / 'omarchy_commands.py', self.new['omarchy_commands.py'])
        row = json.loads((self.root / 'install.json').read_bytes()); row['runtime_files'] = self.pins
        self.write_json(self.root / 'install.json', row); before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())

    def test_proot_temp_source_update_retains_all_three_direct_latest_paths(self):
        for stage in ('legacy', 'guarded', 'tmpdir'):
            with self.subTest(stage=stage):
                fixture = RuntimeUpdateTests()
                fixture.setUp()
                try:
                    if stage == 'guarded': fixture.guarded_fixture()
                    if stage == 'tmpdir': fixture.guarded_fixture(); fixture.update()
                    fixture.next_resources(); fixture.next_proot_temp()
                    result = fixture.update()
                    self.assertEqual(result['phase'], 'INSTALLED')
                    for name, data in fixture.new.items():
                        self.assertEqual((fixture.root / name).read_bytes(), data)
                    before = fixture.inventory(); fixture.update(); self.assertEqual(before, fixture.inventory())
                finally: fixture.doCleanups()

    def resources_fix_fixture(self, fresh=False):
        if fresh:
            for name, data in self.new.items(): self.write(self.root / name, data)
            self.write_json(self.root / 'install.json', dict(self.installed, runtime_files=dict(self.pins)))
        else:
            self.proot_temp_fixture(); self.update()
        self.fifth_before = self.inventory()
        self.previous_pins = dict(self.pins)
        self.m.PREVIOUS_RUNTIME_SHA = self.previous_pins
        self.previous_resource = self.new['omarchy_resources.py']
        self.previous_runtime = self.new['omarchy_runtime.py']
        self.previous_processes = self.new['processes.py']
        for name in ('omarchy_resources.py', 'omarchy_runtime.py', 'processes.py'):
            self.new[name] = b'VALUE = 5\n# bounded resources fix ' + name.encode() + b'\n'
            self.pins[name] = sha(self.new[name]); self.write(self.sources / name, self.new[name])
        self.m.RESOURCES_RUNTIME_SHA = dict(self.pins)

    def test_resources_fix_fifth_journal_preserves_four_stage_history_and_changes_only_three_files(self):
        self.resources_fix_fixture()
        histories = ('runtime-update.json', 'runtime-update-tmpdir.json',
                     'runtime-update-inventory.json', 'runtime-update-proot-temp.json')
        try: result = self.update()
        except ValueError as error: self.fail('Exact setup08 runtime needs its additive fifth migration: ' + str(error))
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(set(result['applied']), {'omarchy_runtime.py', 'omarchy_resources.py', 'processes.py'})
        self.assertEqual(result['previous_runtime_files'], self.previous_pins)
        self.assertEqual(result['previousJournals'], {n: sha(self.fifth_before[n][3]) for n in histories})
        self.assertEqual(json.loads((self.root / 'runtime-update-resources.json').read_bytes()), result)
        after = self.inventory()
        for name, before in self.fifth_before.items():
            if name not in ('install.json', 'omarchy_runtime.py', 'omarchy_resources.py', 'processes.py'):
                self.assertEqual(after[name], before, name)
        backup = self.root / result['backupDirectory']
        self.assertEqual((backup / 'omarchy_runtime.py').read_bytes(), self.previous_runtime)
        self.assertEqual((backup / 'omarchy_resources.py').read_bytes(), self.previous_resource)
        self.assertEqual((backup / 'processes.py').read_bytes(), self.previous_processes)
        for name in histories: self.assertEqual((backup / name).read_bytes(), self.fifth_before[name][3])
        self.assertEqual(json.loads((self.root / 'install.json').read_bytes())['runtime_files'], self.pins)
        self.update(); self.assertEqual(self.inventory(), after)

    def test_resources_fix_supports_exact_fresh_setup08_without_legacy_journals(self):
        self.resources_fix_fixture(fresh=True)
        try: result = self.update()
        except ValueError as error: self.fail('Exact fresh setup08 must support the resources update: ' + str(error))
        self.assertEqual(result['previousJournals'], {})
        self.assertEqual(result['previous_runtime_files'], self.previous_pins)
        self.assertEqual(set(result['applied']), {'omarchy_runtime.py', 'omarchy_resources.py', 'processes.py'})
        before = self.inventory(); self.update(); self.assertEqual(self.inventory(), before)

    def test_inventory_direct_latest_remains_idempotent_after_predecessor_pins_are_frozen(self):
        # A three-journal install may take the existing direct path to the new runtime.
        self.proot_temp_fixture()
        self.m.PREVIOUS_RUNTIME_SHA = dict(self.pins)
        for name in ('omarchy_resources.py', 'omarchy_runtime.py', 'processes.py'):
            self.new[name] = b'VALUE = 5\n# direct latest ' + name.encode() + b'\n'
            self.pins[name] = sha(self.new[name]); self.write(self.sources / name, self.new[name])
        self.m.RESOURCES_RUNTIME_SHA = dict(self.pins)
        result = self.update()
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(json.loads((self.root / 'runtime-update-proot-temp.json').read_bytes()), result)
        before = self.inventory()
        self.update(); self.assertEqual(self.inventory(), before)

    def test_resources_fix_refuses_failed_state_unknown_old_file_or_changed_history_without_writes(self):
        self.resources_fix_fixture()
        self.write_json(self.root / 'runtime-state.json', dict(self.state, phase='failed', terminationConfirmed=False))
        before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(self.inventory(), before)
        self.write_json(self.root / 'runtime-state.json', self.state)
        for name in ('omarchy_resources.py', 'omarchy_audio.py', 'runtime-update-proot-temp.json'):
            target = self.root / name; original = target.read_bytes()
            self.write(target, original + b'\n# changed\n'); before = self.inventory()
            with self.assertRaises(ValueError): self.update()
            self.assertEqual(self.inventory(), before); self.write(target, original)

    def test_resources_fix_partial_publication_keeps_backup_and_unknown_fifth_journal(self):
        self.resources_fix_fixture(); replace = os.replace
        def interrupted(source, destination, **kwargs):
            if destination == 'install.json': raise OSError('public fifth journal failure')
            return replace(source, destination, **kwargs)
        with mock.patch.object(self.m.os, 'replace', interrupted):
            with self.assertRaises(ValueError): self.update()
        self.assertTrue((self.root / 'runtime-update-resources.json').exists(), 'fifth transaction journal missing')
        result = json.loads((self.root / 'runtime-update-resources.json').read_bytes())
        self.assertEqual(result['phase'], 'UPDATE_UNKNOWN')
        backup = self.root / result['backupDirectory']
        self.assertEqual((backup / 'omarchy_resources.py').read_bytes(), self.previous_resource)
        self.assertEqual((backup / 'install.json').read_bytes(), self.fifth_before['install.json'][3])
        before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(self.inventory(), before)

    def test_resources_fix_final_pins_without_fifth_journal_are_not_adopted(self):
        self.resources_fix_fixture()
        for name in ('omarchy_resources.py', 'omarchy_runtime.py', 'processes.py'): self.write(self.root / name, self.new[name])
        row = json.loads((self.root / 'install.json').read_bytes()); row['runtime_files'] = self.pins
        self.write_json(self.root / 'install.json', row)
        before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(self.inventory(), before)

    def heal_fixture(self):
        self.resources_fix_fixture()
        self.update()
        self.heal_before = self.inventory()
        self.resources_pins = dict(self.m.RESOURCES_RUNTIME_SHA)
        self.m.DEVICE_RUNTIME_SHA = dict(self.pins)
        for name in HEAL_NAMES:
            self.new[name] = b'VALUE = 6\n# session heal ' + name.encode() + b'\n'
            self.pins[name] = sha(self.new[name]); self.write(self.sources / name, self.new[name])
        self.m.HEAL_RUNTIME_SHA = dict(self.pins)

    def test_journal_identities_tolerate_cross_boot_device_drift_only(self):
        # /data st_dev drifts across boots; owned identity is inode+uid.
        installed = {'root': [999, 838079, os.getuid()], 'rootfs_identity': [999, 839553, os.getuid()]}
        row = {'schema': 1, 'phase': 'INSTALLED', 'uid': os.getuid(),
               'root': [65096, 838079, os.getuid()], 'rootfs': [65096, 839553, os.getuid()]}
        self.assertTrue(self.m.completed_record(dict(row, runtime_files={'k': 'v'}), installed, {'k': 'v'}))
        self.assertFalse(self.m.completed_record(
            dict(row, root=[65096, 838080, os.getuid()], runtime_files={'k': 'v'}), installed, {'k': 'v'}))
        self.assertFalse(self.m.completed_record(
            dict(row, root=[65096, 838079, os.getuid() + 1], runtime_files={'k': 'v'}), installed, {'k': 'v'}))

    def video_fixture(self):
        self.heal_fixture()
        self.update()
        self.video_before = self.inventory()
        self.m.HEAL_RUNTIME_SHA = dict(self.pins)
        for name in VIDEO_NAMES:
            self.new[name] = b'VALUE = 7\n# video direct ' + name.encode() + b'\n'
            self.pins[name] = sha(self.new[name]); self.write(self.sources / name, self.new[name])
        self.m.VIDEO_RUNTIME_SHA = dict(self.pins)

    def test_video_seventh_journal_changes_exactly_the_scoped_files_and_preserves_history(self):
        self.video_fixture()
        histories = ('runtime-update.json', 'runtime-update-tmpdir.json',
                     'runtime-update-inventory.json', 'runtime-update-proot-temp.json',
                     'runtime-update-resources.json', 'runtime-update-heal.json')
        try: result = self.update()
        except ValueError as error: self.fail('Exact heal runtime needs its additive video migration: ' + str(error))
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(set(result['applied']), set(VIDEO_NAMES))
        self.assertEqual(result['previous_runtime_files'], self.m.HEAL_RUNTIME_SHA)
        self.assertEqual(result['previousJournals'], {n: sha(self.video_before[n][3]) for n in histories})
        self.assertEqual(json.loads((self.root / 'runtime-update-video.json').read_bytes()), result)
        after = self.inventory()
        for name, before in self.video_before.items():
            if name not in (*VIDEO_NAMES, 'install.json'):
                self.assertEqual(after[name], before, name)
        backup = self.root / result['backupDirectory']
        for name in VIDEO_NAMES: self.assertEqual((backup / name).read_bytes(), self.video_before[name][3])
        self.assertEqual(json.loads((self.root / 'install.json').read_bytes())['runtime_files'], self.pins)
        self.update(); self.assertEqual(self.inventory(), after)

    def direct_fixture(self):
        self.video_fixture()
        self.update()
        self.direct_before = self.inventory()
        self.m.VIDEO_RUNTIME_SHA = dict(self.pins)
        for name in DIRECT_NAMES:
            self.new[name] = b'VALUE = 8\n# direct fix ' + name.encode() + b'\n'
            self.pins[name] = sha(self.new[name]); self.write(self.sources / name, self.new[name])
        self.m.DIRECT_RUNTIME_SHA = dict(self.pins)

    def test_direct_eighth_journal_changes_exactly_the_scoped_files(self):
        self.direct_fixture()
        histories = ('runtime-update.json', 'runtime-update-tmpdir.json',
                     'runtime-update-inventory.json', 'runtime-update-proot-temp.json',
                     'runtime-update-resources.json', 'runtime-update-heal.json',
                     'runtime-update-video.json')
        try: result = self.update()
        except ValueError as error: self.fail('Exact video runtime needs its additive direct migration: ' + str(error))
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(set(result['applied']), set(DIRECT_NAMES))
        self.assertEqual(result['previous_runtime_files'], self.m.VIDEO_RUNTIME_SHA)
        self.assertEqual(result['previousJournals'], {n: sha(self.direct_before[n][3]) for n in histories})
        self.assertEqual(json.loads((self.root / 'runtime-update-direct.json').read_bytes()), result)
        after = self.inventory()
        for name, before in self.direct_before.items():
            if name not in (*DIRECT_NAMES, 'install.json'):
                self.assertEqual(after[name], before, name)
        self.assertEqual(json.loads((self.root / 'install.json').read_bytes())['runtime_files'], self.pins)
        self.update(); self.assertEqual(self.inventory(), after)

    def test_video_refuses_unknown_previous_generation_without_writes(self):
        self.video_fixture()
        self.m.HEAL_RUNTIME_SHA['omarchy_android.py'] = '0' * 64
        before = self.inventory()
        backups = list(self.root.glob('.runtime-update-*'))
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())
        self.assertEqual(list(self.root.glob('.runtime-update-*')), backups)

    def freeze_fixture(self):
        self.direct_fixture()
        self.update()
        self.freeze_before = self.inventory()
        self.m.DIRECT_RUNTIME_SHA = dict(self.pins)
        for name in FREEZE_NAMES:
            self.new[name] = b'VALUE = 9\n# video freeze ' + name.encode() + b'\n'
            self.pins[name] = sha(self.new[name]); self.write(self.sources / name, self.new[name])

    def test_freeze_ninth_journal_changes_exactly_the_scoped_files(self):
        self.freeze_fixture()
        histories = ('runtime-update.json', 'runtime-update-tmpdir.json',
                     'runtime-update-inventory.json', 'runtime-update-proot-temp.json',
                     'runtime-update-resources.json', 'runtime-update-heal.json',
                     'runtime-update-video.json', 'runtime-update-direct.json')
        try: result = self.update()
        except ValueError as error: self.fail('Exact direct runtime needs its additive freeze migration: ' + str(error))
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(set(result['applied']), set(FREEZE_NAMES))
        self.assertEqual(result['previous_runtime_files'], self.m.DIRECT_RUNTIME_SHA)
        self.assertEqual(result['previousJournals'], {n: sha(self.freeze_before[n][3]) for n in histories})
        self.assertEqual(json.loads((self.root / 'runtime-update-freeze.json').read_bytes()), result)
        after = self.inventory()
        for name, before in self.freeze_before.items():
            if name not in (*FREEZE_NAMES, 'install.json'):
                self.assertEqual(after[name], before, name)
        self.assertEqual(json.loads((self.root / 'install.json').read_bytes())['runtime_files'], self.pins)
        self.update(); self.assertEqual(self.inventory(), after)

    def test_freeze_refuses_direct_generation_drift_without_writes(self):
        self.freeze_fixture()
        self.m.DIRECT_RUNTIME_SHA['omarchy_android.py'] = '0' * 64
        before = self.inventory()
        backups = list(self.root.glob('.runtime-update-*'))
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())
        self.assertEqual(list(self.root.glob('.runtime-update-*')), backups)

    def test_heal_predecessor_constants_match_their_reviewed_sources(self):
        source = SOURCE.read_text()
        def constant(name):
            block = re.search(name + r' = \{(.*?)\}', source, re.S).group(1)
            return dict(re.findall(r"'([^']+)': '([a-f0-9]{64})'", block))
        fixture = dict(re.findall(r"'([^']+)': '([a-f0-9]{64})'",
            re.search(r'RUNTIME_SHA = \{(.*?)\}', FIXTURE.read_text(), re.S).group(1)))
        self.assertEqual(constant('DEVICE_RUNTIME_SHA'), fixture,
                         'heal predecessor must stay the exact cccb8ac0 terminal generation')
        previous, resources = constant('PREVIOUS_RUNTIME_SHA'), constant('RESOURCES_RUNTIME_SHA')
        self.assertEqual({name for name in previous if previous[name] != resources.get(name)},
                         {'omarchy_runtime.py', 'omarchy_resources.py', 'processes.py'},
                         'resources generation must differ from setup08 only in its reviewed scope')
        # The heal scope check only runs on the device; pin the real-map shape here.
        fresh_spec = importlib.util.spec_from_file_location('fresh_runtime_update', SOURCE)
        fresh = importlib.util.module_from_spec(fresh_spec); fresh_spec.loader.exec_module(fresh)
        # A fresh omarchy_install too: setUp patches the sys.modules-cached one.
        install_spec = importlib.util.spec_from_file_location(
            'fresh_omarchy_install', SOURCE.with_name('omarchy_install.py'))
        fresh_base = importlib.util.module_from_spec(install_spec); install_spec.loader.exec_module(fresh_base)
        self.assertEqual({name for name in fresh_base.RUNTIME_SHA
                          if fresh_base.RUNTIME_SHA[name] != fresh.DEVICE_RUNTIME_SHA[name]},
                         set(fresh.HEAL_SCOPE) | set(fresh.VIDEO_SCOPE))
        self.assertEqual({name for name in fresh.HEAL_RUNTIME_SHA
                          if fresh.HEAL_RUNTIME_SHA[name] != fresh.DEVICE_RUNTIME_SHA[name]},
                         set(fresh.HEAL_SCOPE))
        self.assertEqual({name for name in fresh_base.RUNTIME_SHA
                          if fresh_base.RUNTIME_SHA[name] != fresh.HEAL_RUNTIME_SHA[name]},
                         set(fresh.VIDEO_SCOPE))
        self.assertEqual({name for name in fresh_base.RUNTIME_SHA
                          if fresh_base.RUNTIME_SHA[name] != fresh.VIDEO_RUNTIME_SHA[name]},
                         set(fresh.DIRECT_SCOPE))

    def test_heal_sixth_journal_changes_exactly_the_scoped_files_and_preserves_resources_history(self):
        self.heal_fixture()
        histories = ('runtime-update.json', 'runtime-update-tmpdir.json',
                     'runtime-update-inventory.json', 'runtime-update-proot-temp.json',
                     'runtime-update-resources.json')
        try: result = self.update()
        except ValueError as error: self.fail('Exact resources runtime needs its additive heal migration: ' + str(error))
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(set(result['applied']), set(HEAL_NAMES))
        self.assertEqual(result['previous_runtime_files'], self.resources_pins)
        self.assertEqual(result['previousJournals'], {n: sha(self.heal_before[n][3]) for n in histories})
        self.assertEqual(json.loads((self.root / 'runtime-update-heal.json').read_bytes()), result)
        after = self.inventory()
        for name, before in self.heal_before.items():
            if name not in (*HEAL_NAMES, 'install.json'):
                self.assertEqual(after[name], before, name)
        backup = self.root / result['backupDirectory']
        for name in HEAL_NAMES: self.assertEqual((backup / name).read_bytes(), self.heal_before[name][3])
        self.assertEqual(json.loads((self.root / 'install.json').read_bytes())['runtime_files'], self.pins)
        self.update(); self.assertEqual(self.inventory(), after)

    def test_heal_supports_exact_resources_install_without_legacy_journals(self):
        self.resources_fix_fixture(fresh=True)
        self.update()
        for name in ('runtime-update.json', 'runtime-update-tmpdir.json', 'runtime-update-inventory.json',
                     'runtime-update-proot-temp.json', 'runtime-update-resources.json'):
            if (self.root / name).exists(): (self.root / name).unlink()
        self.m.DEVICE_RUNTIME_SHA = dict(self.pins)
        for name in HEAL_NAMES:
            self.new[name] = b'VALUE = 6\n# fresh heal ' + name.encode() + b'\n'
            self.pins[name] = sha(self.new[name]); self.write(self.sources / name, self.new[name])
        self.m.HEAL_RUNTIME_SHA = dict(self.pins)
        try: result = self.update()
        except ValueError as error: self.fail('Fresh resources install must take the heal path: ' + str(error))
        self.assertEqual(result['phase'], 'INSTALLED')
        self.assertEqual(result['previousJournals'], {})
        self.assertEqual(set(result['applied']), set(HEAL_NAMES))
        before = self.inventory(); self.update(); self.assertEqual(self.inventory(), before)

    def test_heal_refuses_unknown_previous_generation_without_writes(self):
        self.heal_fixture()
        self.m.DEVICE_RUNTIME_SHA['omarchy_boot.py'] = '0' * 64
        before = self.inventory()
        backups = list(self.root.glob('.runtime-update-*'))
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(before, self.inventory())
        self.assertEqual(list(self.root.glob('.runtime-update-*')), backups)

    def test_heal_final_pins_without_sixth_journal_are_not_adopted(self):
        self.heal_fixture()
        for name in HEAL_NAMES: self.write(self.root / name, self.new[name])
        row = json.loads((self.root / 'install.json').read_bytes()); row['runtime_files'] = self.pins
        self.write_json(self.root / 'install.json', row)
        before = self.inventory()
        with self.assertRaises(ValueError): self.update()
        self.assertEqual(self.inventory(), before)


if __name__ == '__main__':
    unittest.main()
