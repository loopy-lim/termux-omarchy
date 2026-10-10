"""Replay the unchanged existing 29 scenarios with the new helper; host only."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parents[2]
sys.path.insert(0, str(TESTS.parent))
from tooling import java_tools, lint_flags
TOOLS = java_tools()
work = tempfile.TemporaryDirectory(prefix="termux-omarchy-handoff-")
out = Path(work.name)
input_path = TESTS / "HandoffReplay.java"
inputs_path = input_path
inputs = {"stubs": {str(p.relative_to(TESTS / "stubs")): p.read_text().rstrip("\n")
                    for p in sorted((TESTS / "stubs").rglob("*.java"))},
          "replay": input_path.read_text()}
stubs = dict(inputs["stubs"])
# The old 29 scenarios never call this new leaf; only its compilation signature
# is added. All original framework/Activity stub semantics stay byte-identical.
stubs['com/termux/x11/input/TouchInputHandler.java'] = '''package com.termux.x11.input;
public class TouchInputHandler { public boolean sendKeyEvent(android.view.KeyEvent event){throw new AssertionError("old-29-must-not-use-direct-leaf");} }
'''
for name, text in stubs.items():
    path = out / 'src' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
(out / 'src/HandoffReplay.java').write_text(inputs['replay'])
production = [ROOT / 'input/src/com/termux/x11/utils/KeyBridgeHandoff.java',
              ROOT / 'input/src/com/termux/x11/utils/KeyInterceptor.java']
production_bytes = {p: p.read_bytes() for p in production}
production_hashes = {str(p): hashlib.sha256(data).hexdigest() for p, data in production_bytes.items()}
assert production_hashes[str(production[0])] == '2efc5f42701641e9f0b1bba63367b086423db39f3016e56cef47e4c1f4985304'
snapshot = out / 'production'
snapshot.mkdir()
for path, data in production_bytes.items():
    (snapshot / path.name).write_bytes(data)
compiled = subprocess.run([TOOLS['javac'], *lint_flags(TOOLS['javac']), '-d', str(out / 'classes'),
                           *map(str, sorted((out / 'src').rglob('*.java'))),
                           *map(str, sorted(snapshot.glob('*.java')))],
                          capture_output=True, text=True, timeout=30)
(out / 'compile.txt').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr
result = subprocess.run([TOOLS['java'], '-cp', str(out / 'classes'), 'HandoffReplay'],
                        capture_output=True, text=True, timeout=15)
(out / 'output.txt').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'RESULT 29 pass 0 fail' in result.stdout, result.stdout + result.stderr
assert all(path.read_bytes() == data for path, data in production_bytes.items()), 'production source changed during replay'
test_sources = [Path(__file__).resolve(), inputs_path]
receipt = dict(schema=1, mode='GREEN_EXISTING_29_UNCHANGED', status='PASS_HOST_ACCESSIBILITY_29_REGRESSION',
               exitCode=result.returncode, passed=29, failed=0,
               helperSHA256=production_hashes[str(production[0])],
               productionSHA256=production_hashes, productionSourceStable=True,
               compiledProductionSnapshot=True,
               testSourceSHA256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in test_sources},
               runnerSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               existing29InputsSHA256=hashlib.sha256(inputs_path.read_bytes()).hexdigest(),
               androidFrameworkStubbed=True, physicalInputVerified=False, jniVerified=False, deviceActions=False,
               originalReplayAndStubsUnchanged=True)
(out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(result.stdout, end='')
work.cleanup()
