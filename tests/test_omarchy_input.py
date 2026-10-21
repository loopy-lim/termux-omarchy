"""Bounded real CLI transactions for the independent Omarchy input profile."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
DESIRED = {'fullscreen': 'true', 'pointerCapture': 'true', 'preferScancodes': 'true',
           'hardwareKbdScancodesWorkaround': 'false', 'showAdditionalKbd': 'false',
           'showIMEWhileExternalConnected': 'false', 'pauseKeyInterceptingWithEsc': 'false',
           'filterOutWinkey': 'false', 'enforceCharBasedInput': 'false',
           'enableAccessibilityServiceAutomatically': 'true'}
AUTO_SERVICE = 'enableAccessibilityServiceAutomatically'
LEGACY_DESIRED = {key: value for key, value in DESIRED.items() if key != AUTO_SERVICE}
ORIGINAL = {key: ('false' if value == 'true' else 'true') for key, value in DESIRED.items()}
UNOWNED = {'clipboardEnable': 'true', 'touchMode': '1',
           'storeSecondaryDisplayPreferencesSeparately': 'false'}


class OmarchyInputTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(REPO / 'termux'))
        self.addCleanup(sys.path.remove, str(REPO / 'termux'))
        new = REPO / 'termux/omarchy_input.py'
        self.new_profile = new.exists()
        # RED exercises the shipped preset, including its actual CLI behavior.
        source = new if self.new_profile else REPO / 'termux/preferences.py'
        spec = importlib.util.spec_from_file_location('omarchy_input_test', source)
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory(prefix='loopy-omarchy-input-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.values_path = self.base / 'values.json'
        self.values_path.write_text(json.dumps({**ORIGINAL, **UNOWNED}))
        self.command = self.base / 'termux-x11-preference'
        self.command.write_text('#!' + sys.executable + '\n' + '''import json,sys
from pathlib import Path
root=Path(__file__).parent; path=root/'values.json'
values=json.loads(path.read_text()); args=sys.argv[1:]
if args == ['list']:
    for key,value in values.items(): print(f'"{key}"="{value}"')
else:
    changes={}
    for item in args:
        key,value=item.split(':',1)
        if key not in values or value not in ('true','false'): raise SystemExit(2)
        changes[key]=value
    checkpoint=root/'omarchy-input.json'
    if checkpoint.exists():
        with (root/'checkpoints.jsonl').open('a') as out: out.write(checkpoint.read_text()+'\\n')
    with (root/'writes.jsonl').open('a') as out: out.write(json.dumps(changes)+'\\n')
    if (root/'ignore-escape').exists(): changes.pop('pauseKeyInterceptingWithEsc',None)
    values.update(changes); path.write_text(json.dumps(values))
''')
        self.command.chmod(0o700)
        self.env = os.environ.copy()

    def values(self):
        return json.loads(self.values_path.read_text())

    def snapshot(self):
        return self.base / ('omarchy-input.json' if self.new_profile else 'input.json')

    def saved(self, applied, before):
        value = {'schema': 1, 'uid': os.getuid(), 'profile': 'omarchy-wayland',
                 'before': before, 'applied': applied}
        self.snapshot().write_text(json.dumps(value))
        self.snapshot().chmod(0o600)
        return value

    def ensure(self):
        # Current production has no ensure yet: exercise its real existing-snapshot
        # admission rather than fail on a missing Python attribute.
        operation = getattr(self.module, 'ensure', self.module.apply)
        try:
            return operation(self.command, self.base, self.env)
        except ValueError as error:
            raise AssertionError('owned unchanged input profile must be ensure-able') from error

    def writes(self):
        path = self.base / 'writes.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_apply_routes_escape_scancodes_meta_and_auto_service_with_all_ten_values(self):
        self.module.apply(self.command, self.base, self.env)
        self.assertEqual(self.values(), {**DESIRED, **UNOWNED})
        data = json.loads(self.snapshot().read_text())
        self.assertEqual(data['before'], ORIGINAL)
        self.assertEqual(data['applied'], DESIRED)

    def test_ensure_legacy_snapshot_preserves_nine_originals_before_auto_service_write(self):
        before = {key: ORIGINAL[key] for key in LEGACY_DESIRED}
        old = self.saved(LEGACY_DESIRED, before)
        self.values_path.write_text(json.dumps({**LEGACY_DESIRED, **UNOWNED, AUTO_SERVICE: 'false'}))
        self.ensure()
        upgraded = json.loads(self.snapshot().read_text())
        self.assertEqual(upgraded['before'], {**old['before'], AUTO_SERVICE: 'false'})
        self.assertEqual(upgraded['applied'], DESIRED)
        self.assertEqual(self.values(), {**DESIRED, **UNOWNED})
        self.assertEqual(self.writes(), [{AUTO_SERVICE: 'true'}], 'migration rewrote already-owned keys')
        checkpoints = [json.loads(line) for line in (self.base / 'checkpoints.jsonl').read_text().splitlines()]
        self.assertEqual(checkpoints[0], upgraded, 'tenth original was not checkpointed before mutation')

    def test_ensure_complete_owned_profile_is_idempotent_without_writes_or_snapshot_replacement(self):
        self.saved(DESIRED, ORIGINAL)
        self.values_path.write_text(json.dumps({**DESIRED, **UNOWNED}))
        before = self.snapshot().read_bytes()
        self.ensure()
        self.ensure()
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.snapshot().read_bytes(), before)
        self.assertEqual(self.values(), {**DESIRED, **UNOWNED})

    def test_ensure_refuses_observed_user_edit_before_migration_or_write(self):
        self.saved(LEGACY_DESIRED, {key: ORIGINAL[key] for key in LEGACY_DESIRED})
        current = {**LEGACY_DESIRED, **UNOWNED, AUTO_SERVICE: 'false', 'preferScancodes': 'false'}
        self.values_path.write_text(json.dumps(current))
        before = self.snapshot().read_bytes()
        operation = getattr(self.module, 'ensure', self.module.apply)
        with self.assertRaises(ValueError):
            operation(self.command, self.base, self.env)
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.snapshot().read_bytes(), before)
        self.assertEqual(self.values(), current)

    def test_ensure_migration_then_restore_round_trips_all_ten_originals(self):
        before = {key: ORIGINAL[key] for key in LEGACY_DESIRED}
        self.saved(LEGACY_DESIRED, before)
        self.values_path.write_text(json.dumps({**LEGACY_DESIRED, **UNOWNED, AUTO_SERVICE: 'false'}))
        self.ensure()
        self.module.restore(self.command, self.base, self.env)
        self.assertEqual(self.values(), {**ORIGINAL, **UNOWNED})
        self.assertFalse(self.snapshot().exists())

    def test_restore_unmigrated_legacy_snapshot_changes_only_nine_owned_keys(self):
        before = {key: ORIGINAL[key] for key in LEGACY_DESIRED}
        self.saved(LEGACY_DESIRED, before)
        current = {**LEGACY_DESIRED, **UNOWNED, AUTO_SERVICE: 'true'}
        self.values_path.write_text(json.dumps(current))
        self.module.restore(self.command, self.base, self.env)
        self.assertEqual(self.values(), {**before, **UNOWNED, AUTO_SERVICE: 'true'})
        self.assertNotIn(AUTO_SERVICE, self.writes()[-1])
        self.assertFalse(self.snapshot().exists())

    def test_apply_still_refuses_an_existing_owned_snapshot_without_mutation(self):
        self.saved(LEGACY_DESIRED, {key: ORIGINAL[key] for key in LEGACY_DESIRED})
        before = self.snapshot().read_bytes()
        current = self.values()
        with self.assertRaises(ValueError):
            self.module.apply(self.command, self.base, self.env)
        self.assertEqual(self.snapshot().read_bytes(), before)
        self.assertEqual(self.values(), current)
        self.assertEqual(self.writes(), [])

    def test_own_snapshot_is_separate_from_existing_native_i3_profile(self):
        old = self.base / 'input.json'
        old.write_bytes(b'{"native-i3-sentinel":true}')
        try:
            self.module.apply(self.command, self.base, self.env)
        except ValueError as error:
            raise AssertionError('existing i3 snapshot blocked independent Omarchy profile') from error
        self.assertEqual(old.read_bytes(), b'{"native-i3-sentinel":true}')
        self.assertTrue((self.base / 'omarchy-input.json').is_file())

    def test_missing_meta_route_key_refuses_before_snapshot_or_mutation(self):
        before = self.values(); before.pop('filterOutWinkey')
        self.values_path.write_text(json.dumps(before))
        with self.assertRaises(ValueError):
            self.module.apply(self.command, self.base, self.env)
        self.assertFalse(self.snapshot().exists())
        self.assertFalse((self.base / 'writes.jsonl').exists())
        self.assertEqual(self.values(), before)

    def test_restore_round_trip_preserves_unowned_preferences(self):
        self.module.apply(self.command, self.base, self.env)
        self.assertEqual(self.values()[AUTO_SERVICE], 'true', 'round trip did not first own the tenth key')
        values = self.values(); values['clipboardEnable'] = 'false'
        self.values_path.write_text(json.dumps(values))
        self.module.restore(self.command, self.base, self.env)
        self.assertEqual(self.values(), {**ORIGINAL, **UNOWNED, 'clipboardEnable': 'false'})
        self.assertFalse(self.snapshot().exists())

    def test_restore_compares_and_preserves_user_scancode_and_meta_edits(self):
        self.module.apply(self.command, self.base, self.env)
        values = self.values(); values.update(preferScancodes='false', filterOutWinkey='true')
        self.values_path.write_text(json.dumps(values))
        self.module.restore(self.command, self.base, self.env)
        restored = json.loads((self.base / 'writes.jsonl').read_text().splitlines()[-1])
        self.assertNotIn('preferScancodes', restored, 'restore rewrote a user edit')
        self.assertNotIn('filterOutWinkey', restored, 'restore rewrote a user edit')
        self.assertEqual(self.values(), {**ORIGINAL, **UNOWNED})

    def test_secondary_display_separate_preferences_refuse_before_write(self):
        values = self.values(); values['storeSecondaryDisplayPreferencesSeparately'] = 'true'
        self.values_path.write_text(json.dumps(values))
        with self.assertRaises(ValueError):
            self.module.apply(self.command, self.base, self.env)
        self.assertFalse(self.snapshot().exists())
        self.assertFalse((self.base / 'writes.jsonl').exists())

    def cold_command(self, fail_times):
        """A real CLI whose list query refuses the first cold starts, then answers."""
        command = self.base / 'cold-termux-x11-preference'
        command.write_text('#!' + sys.executable + '\n' + '''import json,sys
from pathlib import Path
root=Path(__file__).parent; counts=root/'lists.jsonl'
with counts.open('a') as out: out.write('list\\n')
if len(counts.read_text().splitlines()) <= ''' + str(fail_times) + ''': raise SystemExit(1)
values=json.loads((root/'values.json').read_text()); args=sys.argv[1:]
if args == ['list']:
    for key,value in values.items(): print(f'"{key}"="{value}"')
else: raise SystemExit(2)
''')
        command.chmod(0o700)
        return command

    def test_first_cold_query_retry_still_ensures_without_writes(self):
        self.saved(DESIRED, ORIGINAL)
        self.values_path.write_text(json.dumps({**DESIRED, **UNOWNED}))
        before = self.snapshot().read_bytes()
        backoff = mock.patch.object(self.module, 'QUERY_BACKOFF', 0.01)
        backoff.start(); self.addCleanup(backoff.stop)
        self.module.ensure(self.cold_command(fail_times=1), self.base, self.env)
        lists = len((self.base / 'lists.jsonl').read_text().splitlines())
        self.assertEqual(lists, 2, 'ensure did not retry the refused cold query exactly once')
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.snapshot().read_bytes(), before)

    def test_persistent_cold_query_refusal_is_bounded_and_reported(self):
        self.saved(DESIRED, ORIGINAL)
        backoff = mock.patch.object(self.module, 'QUERY_BACKOFF', 0.01)
        backoff.start(); self.addCleanup(backoff.stop)
        with self.assertRaises(ValueError) as raised:
            self.module.ensure(self.cold_command(fail_times=99), self.base, self.env)
        self.assertEqual(str(raised.exception), 'input-query-unavailable')
        lists = len((self.base / 'lists.jsonl').read_text().splitlines())
        self.assertEqual(lists, self.module.QUERY_ATTEMPTS)
        self.assertFalse((self.base / 'writes.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
