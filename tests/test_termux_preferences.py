"""Real CLI transactions for the explicit, reversible keyboard-first preset."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = {'fullscreen': 'false', 'pointerCapture': 'false', 'preferScancodes': 'true',
            'hardwareKbdScancodesWorkaround': 'true', 'showAdditionalKbd': 'true',
            'showIMEWhileExternalConnected': 'true', 'pauseKeyInterceptingWithEsc': 'false'}
KEYBOARD_FIRST = {'fullscreen': 'true', 'pointerCapture': 'true', 'preferScancodes': 'false',
                  'hardwareKbdScancodesWorkaround': 'false', 'showAdditionalKbd': 'false',
                  'showIMEWhileExternalConnected': 'false', 'pauseKeyInterceptingWithEsc': 'true'}
UNOWNED = {'clipboardEnable': 'true', 'touchMode': '1',
           'storeSecondaryDisplayPreferencesSeparately': 'false'}


class NativePreferenceTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / 'termux'))
        self.addCleanup(sys.path.remove, str(ROOT / 'termux'))
        spec = importlib.util.spec_from_file_location('native_preferences', ROOT / 'termux/preferences.py')
        self.prefs = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.prefs)
        self.temp = tempfile.TemporaryDirectory(prefix='loopy-native-prefs-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / 'values.json'
        self.state.write_text(json.dumps({**ORIGINAL, **UNOWNED}))
        self.command = self.base / 'termux-x11-preference'
        self.command.write_text('#!' + sys.executable + '\n' + '''import json,sys
from pathlib import Path
root=Path(__file__).parent; state=root/'values.json'
values=json.loads(state.read_text()); args=sys.argv[1:]
if args == ['list']:
    for key,value in values.items(): print(f'"{key}"="{value}"')
else:
    if not args: raise SystemExit(1)
    changes={}
    for item in args:
        key,value=item.split(':',1)
        if key not in values or value not in ('true','false'): raise SystemExit(2)
        changes[key]=value
    with (root/'writes.jsonl').open('a') as out: out.write(json.dumps(changes)+'\\n')
    if (root/'ignore-workaround').exists(): changes.pop('hardwareKbdScancodesWorkaround',None)
    values.update(changes); state.write_text(json.dumps(values))
''')
        self.command.chmod(0o700)
        self.env = os.environ.copy()

    def values(self):
        return json.loads(self.state.read_text())

    def test_snapshot_missing_keyboard_route_key_rejects_before_any_mutation(self):
        values = self.values(); values.pop('hardwareKbdScancodesWorkaround')
        self.state.write_text(json.dumps(values))
        with self.assertRaisesRegex(ValueError, 'snapshot is incomplete'):
            self.prefs.apply(self.command, self.base, self.env)
        self.assertEqual(self.values(), values)
        self.assertFalse((self.base / 'input.json').exists())
        self.assertFalse((self.base / 'writes.jsonl').exists())

    def test_apply_sets_all_seven_keys_and_saves_original_owned_values(self):
        response = self.prefs.apply(self.command, self.base, self.env)
        self.assertEqual(self.values(), {**KEYBOARD_FIRST, **UNOWNED})
        snapshot = json.loads((self.base / 'input.json').read_text())
        self.assertEqual(snapshot['before'], ORIGINAL)
        self.assertEqual(snapshot['applied'], KEYBOARD_FIRST)
        self.assertEqual(set(response['changedKeys']), set(KEYBOARD_FIRST))
        self.assertFalse(response['accessibilityGranted'])

    def test_cli_ignoring_keyboard_route_cannot_claim_applied_and_retains_restore_snapshot(self):
        (self.base / 'ignore-workaround').touch()
        with self.assertRaisesRegex(ValueError, 'did not accept'):
            self.prefs.apply(self.command, self.base, self.env)
        self.assertTrue((self.base / 'input.json').exists())
        self.assertEqual(self.values()['hardwareKbdScancodesWorkaround'], 'true')
        (self.base / 'ignore-workaround').unlink()
        self.prefs.restore(self.command, self.base, self.env)
        self.assertEqual(self.values(), {**ORIGINAL, **UNOWNED})
        self.assertFalse((self.base / 'input.json').exists())

    def test_restore_round_trip_restores_all_seven_and_preserves_unowned_preferences(self):
        self.prefs.apply(self.command, self.base, self.env)
        values = self.values(); values['clipboardEnable'] = 'false'
        self.state.write_text(json.dumps(values))
        response = self.prefs.restore(self.command, self.base, self.env)
        self.assertEqual(self.values(), {**ORIGINAL, **UNOWNED, 'clipboardEnable': 'false'})
        self.assertEqual(set(response['changedKeys']), set(ORIGINAL))
        self.assertTrue(response['preservedUserEdits'])
        self.assertFalse((self.base / 'input.json').exists())

    def test_restore_uses_compare_and_swap_for_keyboard_route_and_layout_user_edits(self):
        self.prefs.apply(self.command, self.base, self.env)
        values = self.values()
        values.update(hardwareKbdScancodesWorkaround='true', preferScancodes='true', clipboardEnable='false')
        self.state.write_text(json.dumps(values))
        response = self.prefs.restore(self.command, self.base, self.env)
        self.assertEqual(self.values(), {**ORIGINAL, **UNOWNED, 'clipboardEnable': 'false'})
        restored = json.loads((self.base / 'writes.jsonl').read_text().splitlines()[-1])
        expected = {'fullscreen': 'false', 'pointerCapture': 'false', 'showAdditionalKbd': 'true',
                    'showIMEWhileExternalConnected': 'true', 'pauseKeyInterceptingWithEsc': 'false'}
        self.assertEqual(restored, expected, 'restore rewrote values edited after the owned preset')
        self.assertEqual(set(response['changedKeys']), set(expected))
        self.assertFalse((self.base / 'input.json').exists())


if __name__ == '__main__':
    unittest.main()
