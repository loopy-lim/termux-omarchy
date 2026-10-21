"""Exercise the user command through real, bounded subprocess boundaries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'termux/omarchy.py'


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home, self.prefix = self.base / 'home', self.base / 'usr'
        self.home.mkdir(mode=0o700); self.prefix.mkdir(mode=0o700)
        self.managed = self.home / '.local/share/loopy-omarchy'
        self.managed.mkdir(mode=0o700, parents=True)
        for name in ('omarchy_runtime.py', 'omarchy_resources.py', 'processes.py',
                     'omarchy_input.py', 'omarchy_boot.py', 'install.json'):
            (self.managed / name).write_text('{}')
            (self.managed / name).chmod(0o600)
        self.events = self.base / 'events.jsonl'
        self.fail = self.base / 'fail-input'
        binary = self.prefix / 'bin'; binary.mkdir()
        # Actual executable shims record the ordering and return public fixed results.
        executable = '#!' + sys.executable + '\n' + f'''
import json,os,sys,uuid
from pathlib import Path
args=sys.argv[1:]
with Path({str(self.events)!r}).open('a') as out:out.write(json.dumps(args)+'\\n')
if args[:2]==['start','-n']:
    base=Path({str(self.base)!r})
    prior=sum(1 for line in Path({str(self.events)!r}).read_text().splitlines()
              if line.startswith('["start"'))
    if (base/'am-fail-always').exists(): raise SystemExit(1)
    if (base/'am-fail-once').exists() and prior<=1: raise SystemExit(1)
    raise SystemExit(0)
if len(args)==3 and args[0].endswith('omarchy_input.py'):
    assert args[1]=='ensure' and str(uuid.UUID(args[2]))==args[2]
    failed=Path({str(self.fail)!r}).exists()
    print(json.dumps({{'schema':1,'uid':os.getuid(),'action':'ensure','request':args[2],
                      'status':'failed' if failed else 'ensured','reason':'public-test'}}))
elif len(args)==3 and args[0].endswith('omarchy_runtime.py'):
    print(json.dumps({{'status':'ready','action':args[1]}}))
'''
        for name in ('python3', 'am'):
            (binary / name).write_text(executable); (binary / name).chmod(0o700)
        self.runner = self.base / 'run.py'
        self.runner.write_text(f'''import importlib.util,sys
from pathlib import Path
sys.path.insert(0,{str(SOURCE.parent)!r})
spec=importlib.util.spec_from_file_location('launcher',{str(SOURCE)!r})
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.ACTIVITY_BACKOFF=0.01
m.HOME=Path({str(self.home)!r});m.PREFIX=Path({str(self.prefix)!r})
try:m.main()
except m.Failure as e:
    import json
    print(json.dumps({{'status':'failed','reason':str(e)}}))
    raise SystemExit(1)
''')

    def run_launcher(self, action):
        result = subprocess.run([sys.executable, str(self.runner), action],
                                capture_output=True, text=True, timeout=5)
        events = [json.loads(line) for line in self.events.read_text().splitlines()] \
            if self.events.exists() else []
        return result, events

    def test_start_opens_android_then_ensures_input_before_runtime(self):
        result, events = self.run_launcher('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events[0], ['start', '-n', 'com.termux.x11/com.termux.x11.MainActivity'])
        self.assertEqual(len(events), 3, 'start skipped the input ownership/permission reconciliation')
        self.assertEqual(events[1][1], 'ensure')
        self.assertTrue(events[1][0].endswith('/omarchy_input.py'))
        self.assertTrue(events[2][0].endswith('/omarchy_runtime.py'))
        lines = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(lines[0].get('status'), 'phases', 're-entry phases must be attributable')
        self.assertEqual(set(lines[0]), {'schema', 'status', 'activityStartMs', 'ensureMs', 'totalMs'})
        for key in ('activityStartMs', 'ensureMs', 'totalMs'):
            self.assertIsInstance(lines[0][key], int)
        self.assertEqual(lines[-1], {'status': 'ready', 'action': 'start'},
                         'runtime status JSON must stay the final line for reentry measurement')

    def test_failed_input_does_not_start_desktop(self):
        self.fail.touch()
        result, events = self.run_launcher('start')
        self.assertNotEqual(result.returncode, 0, 'failed input was silently accepted')
        self.assertFalse(any(row[0].endswith('omarchy_runtime.py') for row in events))

    def test_start_retries_one_transient_activity_refusal_then_opens(self):
        (self.base / 'am-fail-once').touch()
        result, events = self.run_launcher('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        am_calls = [row for row in events if row[:2] == ['start', '-n']]
        self.assertEqual(len(am_calls), 2, 'a transient first refusal was not retried exactly once')
        self.assertEqual(len(events), 4, 'the retried start skipped input or runtime')

    def test_persistent_activity_refusal_is_bounded_and_never_ensures(self):
        (self.base / 'am-fail-always').touch()
        result, events = self.run_launcher('start')
        self.assertNotEqual(result.returncode, 0, 'a persistent activity refusal was retried forever')
        am_calls = [row for row in events if row[:2] == ['start', '-n']]
        self.assertEqual(len(am_calls), 2)
        self.assertFalse(any(row[0].endswith('omarchy_input.py') or row[0].endswith('omarchy_runtime.py')
                             for row in events))

    def test_status_keeps_activity_and_input_preferences_untouched(self):
        result, events = self.run_launcher('status')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0][0].endswith('/omarchy_runtime.py'))
        self.assertEqual(events[0][1], 'status')


if __name__ == '__main__':
    unittest.main()
