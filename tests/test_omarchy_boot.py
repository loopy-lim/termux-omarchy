"""Cold-boot ownership seam; ROOT alone runs the real module/temporary filesystem.

No reboot, guest process, permission change, or signal is exercised. Kernel PID
lookups are boundary doubles; Runtime.state/clear_runtime/start and capture are
the actual production bodies. Missing new feature is an assertion, not import RED.
Proposed API: current_boot_id(path), prepare_start(runtime, boot_path) -> UUID.
"""
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

REPO = Path(__file__).resolve().parents[1]
BOOT_SOURCE = REPO / 'termux/omarchy_boot.py'
OLD_BOOT = 'aaaaaaaa-1111-4111-8111-111111111111'
CURRENT_BOOT = 'bbbbbbbb-2222-4222-8222-222222222222'
TOKEN = '33333333-3333-4333-8333-333333333333'


def load(path, name):
    sys.path.insert(0, str(REPO / 'termux'))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class OmarchyBootTests(unittest.TestCase):
    def boot_module(self):
        self.assertTrue(BOOT_SOURCE.is_file(), 'owned cold-boot recovery feature is missing')
        return load(BOOT_SOURCE, 'owned_omarchy_boot_test')

    @contextmanager
    def fixture(self):
        # Short socket paths and resolved macOS /tmp prevent host alias false RED.
        with tempfile.TemporaryDirectory(prefix='ob-', dir='/tmp') as temporary:
            base = Path(temporary).resolve()
            home, prefix = base / 'h', base / 'u'
            home.mkdir(); prefix.mkdir()
            module = load(REPO / 'termux/omarchy_runtime.py', 'owned_omarchy_boot_runtime')
            runtime = module.Runtime(home, prefix)
            runtime.short = base / 'r'
            runtime.short.mkdir(mode=0o700)
            session = runtime.root / 'sessions' / TOKEN
            session.mkdir(parents=True, mode=0o700)
            boot_path = base / 'boot-id'
            boot_path.write_text(CURRENT_BOOT + '\n')
            record = {'pid': 314151, 'ppid': 314150, 'pgid': 314151, 'uid': os.getuid(),
                      'tty_nr': 0, 'starttime': '987654321', 'command': [
                          str(runtime.prefix / 'bin/python3'), str(runtime.root / 'omarchy_runtime.py'),
                          '_supervise', TOKEN, ':20']}
            value = {'schema': 1, 'uid': os.getuid(), 'root': module.stamp(runtime.root),
                     'token': TOKEN, 'session': module.stamp(session),
                     'runtime': module.stamp(runtime.short), 'display': ':20',
                     'phase': 'ready', 'processes': [record], 'terminationConfirmed': False,
                     'bootId': OLD_BOOT, 'resources': {}, 'regularResources': {},
                     'directories': {'.': module.stamp(runtime.short)}}
            # Peer stamps that supervise cleanup clears; boot recovery must too.
            value['audioProcess'] = {'pid': 314160, 'ppid': 314151, 'pgid': 314151,
                                     'uid': os.getuid(), 'tty_nr': 0, 'starttime': '987654330',
                                     'command': module.audio_command(runtime, value)[0]}
            value['androidProcess'] = {'pid': 314161, 'ppid': 314151, 'pgid': 314151,
                                       'uid': os.getuid(), 'tty_nr': 0, 'starttime': '987654331',
                                       'command': module.android_command(runtime, value)}
            marker = {'schema': 1, 'token': TOKEN, 'uid': os.getuid(),
                      'root': value['root'], 'runtime': value['runtime']}
            (runtime.short / 'owner.json').write_text(json.dumps(marker))
            runtime.installed = Mock(return_value={'phase': 'INSTALLED'})
            runtime.publish(value)
            yield base, module, runtime, value, boot_path

    def save(self, runtime, value):
        runtime.publish(value)
        return runtime.path.read_bytes()

    def dead(self, boot, module):
        return patch.multiple(boot, identity=lambda *a, **k: None), \
            patch.dict(module.__dict__, {'identity': lambda *a, **k: None,
                       'signal_process': Mock(side_effect=AssertionError('recovery must not signal'))})

    def test_boot_id_is_bounded_canonical_uuid_and_nofollow(self):
        boot = self.boot_module()
        with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
            path = Path(temporary).resolve() / 'boot-id'
            path.write_text(CURRENT_BOOT + '\n')
            self.assertEqual(boot.current_boot_id(path), CURRENT_BOOT)
            for bad in (CURRENT_BOOT.upper(), ' ' + CURRENT_BOOT, CURRENT_BOOT + '\nextra',
                        CURRENT_BOOT + '\n\n', '', 'x' * 256):
                with self.subTest(value=bad[:40]):
                    path.write_text(bad)
                    with self.assertRaises(ValueError):
                        boot.current_boot_id(path)
            target = path.with_name('target')
            target.write_text(CURRENT_BOOT)
            path.unlink(); path.symlink_to(target)
            with self.assertRaises(ValueError):
                boot.current_boot_id(path)

    def test_no_journal_needs_no_cleanup(self):
        boot = self.boot_module()
        with self.fixture() as (_, module, runtime, value, boot_path):
            runtime.path.unlink()
            original = (runtime.short / 'owner.json').read_bytes()
            runtime.clear_runtime = Mock(side_effect=AssertionError('no journal cleanup'))
            self.assertEqual(boot.prepare_start(runtime, boot_path), CURRENT_BOOT)
            self.assertEqual((runtime.short / 'owner.json').read_bytes(), original)
            self.assertFalse(runtime.path.exists())

    def test_same_boot_lost_supervisor_keeps_actual_start_refusal(self):
        boot = self.boot_module()
        with self.fixture() as (_, module, runtime, value, boot_path):
            value['bootId'] = CURRENT_BOOT
            before = self.save(runtime, value)
            runtime.clear_runtime = Mock(side_effect=AssertionError('same-boot cleanup'))
            guards = self.dead(boot, module)
            with guards[0], guards[1]:
                self.assertEqual(boot.prepare_start(runtime, boot_path), CURRENT_BOOT)
                with patch.dict(module.__dict__, {'prepare_start': lambda r: boot.prepare_start(r, boot_path)}):
                    with self.assertRaisesRegex(ValueError, 'previous-cleanup-unconfirmed'):
                        runtime.start('44444444-4444-4444-8444-444444444444')
            self.assertEqual(runtime.path.read_bytes(), before)

    def test_different_boot_removes_exact_recorded_socket_link_and_regular(self):
        boot = self.boot_module()
        with self.fixture() as (base, module, runtime, value, boot_path):
            target = base / 'user-file'
            target.write_bytes(b'preserve-user-data')
            link = runtime.short / 'guest-link'
            link.symlink_to(target)
            regular = runtime.short / 'owned-guest-lock'
            regular.write_bytes(b'public-owned-lock')
            path = runtime.short / 'wayland-omarchy'
            with socket.socket(socket.AF_UNIX) as endpoint:
                endpoint.bind(str(path))
                module.capture(runtime.short, runtime.prefix, value, [])
            self.assertIn('owned-guest-lock', value['regularResources'])
            self.save(runtime, value)
            guards = self.dead(boot, module)
            with guards[0], guards[1]:
                self.assertEqual(boot.prepare_start(runtime, boot_path), CURRENT_BOOT)
            self.assertFalse(os.path.lexists(path))
            self.assertFalse(os.path.lexists(link))
            self.assertFalse(regular.exists())
            self.assertEqual(target.read_bytes(), b'preserve-user-data')
            self.assertEqual({p.name for p in runtime.short.iterdir()}, {'owner.json'})
            result = runtime.state()
            self.assertEqual(result['phase'], 'stopped')
            self.assertTrue(result['terminationConfirmed'])
            self.assertEqual(result['bootId'], CURRENT_BOOT)
            self.assertEqual(result['terminationEvidence'], 'previous-boot')
            self.assertEqual(result['processes'], [])
            self.assertIsNone(result.get('audioProcess'))
            self.assertIsNone(result.get('androidProcess'))
            runtime.installed.assert_called()

    def test_legacy_unclean_refused_but_clean_stopped_journal_migrates(self):
        boot = self.boot_module()
        with self.fixture() as (_, module, runtime, value, boot_path):
            del value['bootId']
            before = self.save(runtime, value)
            guards = self.dead(boot, module)
            with guards[0], guards[1]:
                with self.assertRaises(ValueError):
                    boot.prepare_start(runtime, boot_path)
            self.assertEqual(runtime.path.read_bytes(), before)
            value.update(phase='stopped', terminationConfirmed=True)
            self.save(runtime, value)
            guards = self.dead(boot, module)
            with guards[0], guards[1]:
                self.assertEqual(boot.prepare_start(runtime, boot_path), CURRENT_BOOT)
            self.assertEqual(runtime.state()['bootId'], CURRENT_BOOT)
            self.assertTrue(runtime.state()['terminationConfirmed'])

    def test_invalid_prior_or_current_boot_refuses_before_mutation(self):
        boot = self.boot_module()
        with self.fixture() as (_, module, runtime, value, boot_path):
            for bad in ('', 'not-a-uuid', OLD_BOOT.upper()):
                value['bootId'] = bad
                before = self.save(runtime, value)
                with self.assertRaises(ValueError):
                    boot.prepare_start(runtime, boot_path)
                self.assertEqual(runtime.path.read_bytes(), before)
            value['bootId'] = OLD_BOOT
            before = self.save(runtime, value)
            boot_path.write_text('unknown')
            with self.assertRaises(ValueError):
                boot.prepare_start(runtime, boot_path)
            self.assertEqual(runtime.path.read_bytes(), before)

    def test_root_session_runtime_and_marker_mismatch_preserve_all(self):
        boot = self.boot_module()
        for field in ('root', 'session', 'runtime', 'marker'):
            with self.subTest(field=field), self.fixture() as (_, module, runtime, value, boot_path):
                if field == 'marker':
                    marker = runtime.short / 'owner.json'
                    data = json.loads(marker.read_text()); data['token'] = CURRENT_BOOT
                    marker.write_text(json.dumps(data))
                else:
                    value[field][1] += 1
                before = self.save(runtime, value)
                runtime.clear_runtime = Mock(side_effect=AssertionError('unverified cleanup'))
                with self.assertRaises(ValueError):
                    boot.prepare_start(runtime, boot_path)
                self.assertEqual(runtime.path.read_bytes(), before)

    def test_unknown_regular_or_socket_preserved_before_any_known_removal(self):
        boot = self.boot_module()
        for kind in ('regular', 'socket'):
            with self.subTest(kind=kind), self.fixture() as (_, module, runtime, value, boot_path):
                known = runtime.short / 'known'
                known.write_bytes(b'known')
                module.capture(runtime.short, runtime.prefix, value, [])
                before = self.save(runtime, value)
                foreign = runtime.short / 'foreign'
                with socket.socket(socket.AF_UNIX) as endpoint:
                    if kind == 'socket':
                        endpoint.bind(str(foreign))
                    else:
                        foreign.write_bytes(b'foreign')
                    guards = self.dead(boot, module)
                    with guards[0], guards[1]:
                        with self.assertRaises(ValueError):
                            boot.prepare_start(runtime, boot_path)
                    self.assertTrue(os.path.lexists(foreign))
                    self.assertEqual(known.read_bytes(), b'known')
                    self.assertEqual(runtime.path.read_bytes(), before)

    def test_recorded_regular_replacement_is_preserved(self):
        boot = self.boot_module()
        with self.fixture() as (_, module, runtime, value, boot_path):
            path = runtime.short / 'lock'
            path.write_bytes(b'old')
            module.capture(runtime.short, runtime.prefix, value, [])
            before = self.save(runtime, value)
            path.rename(runtime.short / 'old-retained')
            path.write_bytes(b'new-user-data')
            guards = self.dead(boot, module)
            with guards[0], guards[1]:
                with self.assertRaises(ValueError):
                    boot.prepare_start(runtime, boot_path)
            self.assertEqual(path.read_bytes(), b'new-user-data')
            self.assertEqual(runtime.path.read_bytes(), before)

    def test_regular_replacement_after_boot_preflight_is_not_adopted_by_cleanup(self):
        boot = self.boot_module()
        with self.fixture() as (base, module, runtime, value, boot_path):
            path = runtime.short / 'lock'
            path.write_bytes(b'old')
            module.capture(runtime.short, runtime.prefix, value, [])
            before = self.save(runtime, value)
            original = boot.regular_witness
            def replace_after_preflight(runtime_, value_):
                original(runtime_, value_)
                path.rename(base / 'old-preserved')
                path.write_bytes(b'new-user-data')
            guards = self.dead(boot, module)
            with guards[0], guards[1], patch.object(boot, 'regular_witness', side_effect=replace_after_preflight):
                with self.assertRaises(ValueError):
                    boot.prepare_start(runtime, boot_path)
            self.assertEqual(path.read_bytes(), b'new-user-data')
            self.assertEqual(runtime.path.read_bytes(), before)

    def test_foreign_uid_journal_and_live_identity_collision_refuse(self):
        boot = self.boot_module()
        with self.fixture() as (_, module, runtime, value, boot_path):
            value['uid'] = os.getuid() + 1
            before = self.save(runtime, value)
            with self.assertRaises(ValueError):
                boot.prepare_start(runtime, boot_path)
            self.assertEqual(runtime.path.read_bytes(), before)
            value['uid'] = os.getuid()
            before = self.save(runtime, value)
            current = value['processes'][0]
            with patch.object(boot, 'identity', return_value=current):
                with self.assertRaises(ValueError):
                    boot.prepare_start(runtime, boot_path)
            self.assertEqual(runtime.path.read_bytes(), before)

    def test_failed_cleanup_never_publishes_clean_or_sends_signal(self):
        boot = self.boot_module()
        with self.fixture() as (_, module, runtime, value, boot_path):
            before = self.save(runtime, value)
            runtime.clear_runtime = Mock(side_effect=ValueError('public-cleanup-boundary'))
            guards = self.dead(boot, module)
            with guards[0], guards[1]:
                with self.assertRaises(ValueError):
                    boot.prepare_start(runtime, boot_path)
            self.assertEqual(runtime.path.read_bytes(), before)
            self.assertFalse(runtime.state()['terminationConfirmed'])

    def test_actual_capture_records_regular_metadata_without_content(self):
        # This behavior RED exercises existing capture even before module creation.
        with self.fixture() as (_, module, runtime, value, boot_path):
            path = runtime.short / 'public-lock'
            path.write_bytes(b'never-retain-file-content')
            module.capture(runtime.short, runtime.prefix, value, [])
            info = path.lstat()
            self.assertEqual(value.get('regularResources', {}).get('public-lock'),
                             [info.st_dev, info.st_ino, info.st_uid, info.st_mode])
            self.assertNotIn('owner.json', value.get('regularResources', {}))

    def test_actual_capture_refuses_regular_ledger_over_256_entries(self):
        with self.fixture() as (_, module, runtime, value, boot_path):
            for index in range(257):
                (runtime.short / f'public-{index}').write_bytes(b'fixture')
            with self.assertRaises(ValueError):
                module.capture(runtime.short, runtime.prefix, value, [])

    def test_actual_start_records_boot_before_fixed_child_launch(self):
        boot = self.boot_module()
        class FixedChildBoundary(Exception):
            pass
        with self.fixture() as (_, module, runtime, value, boot_path):
            runtime.path.unlink()
            (runtime.short / 'owner.json').unlink()
            runtime.short.rmdir()
            runtime.choose_display = lambda: ':20'
            with patch.dict(module.__dict__, {'prepare_start': lambda r: boot.prepare_start(r, boot_path)}), \
                    patch.object(module.subprocess, 'Popen', side_effect=FixedChildBoundary):
                with self.assertRaises(FixedChildBoundary):
                    runtime.start('44444444-4444-4444-8444-444444444444')
            started = json.loads(runtime.path.read_text())
            self.assertEqual(started['bootId'], CURRENT_BOOT)
            self.assertEqual(started['phase'], 'starting')
            self.assertFalse(started['terminationConfirmed'])


if __name__ == '__main__':
    unittest.main()
