"""Test the Activity listener seam and real helper; no Android/ADB execution."""
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
BASELINE = '--baseline' in sys.argv
work = tempfile.TemporaryDirectory(prefix="termux-omarchy-handoff-")
out = Path(work.name)
input_path = TESTS / "HandoffReplay.java"
inputs_path = input_path
inputs = {"stubs": {str(p.relative_to(TESTS / "stubs")): p.read_text().rstrip("\n")
                    for p in sorted((TESTS / "stubs").rglob("*.java"))},
          "replay": input_path.read_text()}
stubs = dict(inputs["stubs"])

# This Activity stub reproduces the reviewed listener call seam, preserving the
# original return and virtual extra-key cleanup. DEX preservation is separate.
main = stubs['com/termux/x11/MainActivity.java']
main = main.replace('public class MainActivity extends Context', 'public final class MainActivity extends Context')
main = main.replace('public int forwarded;',
                    'public int forwarded; public boolean nativeAccept=true,handlerAccept=true; '
                    'public boolean useTermuxEKBarBehaviour; public int extraKeysUnset; '
                    'public final com.termux.x11.input.TouchInputHandler input='
                    'new com.termux.x11.input.TouchInputHandler(this);')
before = 'public boolean handleKey(KeyEvent e){forwarded++;forwardedEvents.add(e);return true;}'
after = ('public boolean handleKey(KeyEvent e){return listener(e);} '
         'public boolean listener(KeyEvent e){InputDevice dev=e.getDevice();'
         'boolean result=ListenerRoute.send(this,input,e);'
         'if(useTermuxEKBarBehaviour&&(dev==null||dev.isVirtual()))extraKeysUnset++;return result;}')
assert main.count(before) == 1
main = main.replace(before, after)
main = main.replace('nativeKeys.add(scan+":"+code+":"+down);return true;',
                    'nativeKeys.add(scan+":"+code+":"+down);return nativeAccept;')
stubs['com/termux/x11/MainActivity.java'] = main
stubs['com/termux/x11/input/TouchInputHandler.java'] = '''package com.termux.x11.input;
import android.view.KeyEvent; import com.termux.x11.MainActivity;
public class TouchInputHandler { private final MainActivity activity;
 public TouchInputHandler(MainActivity owner){activity=owner;}
 public boolean sendKeyEvent(KeyEvent event){activity.forwarded++;activity.forwardedEvents.add(event);return activity.handlerAccept;}
}'''
route = ('handler.sendKeyEvent(event)' if BASELINE
         else 'com.termux.x11.utils.KeyBridgeHandoff.sendKeyEvent(activity,handler,event)')
stubs['com/termux/x11/ListenerRoute.java'] = '''package com.termux.x11;
import android.view.KeyEvent;import com.termux.x11.input.TouchInputHandler;
public final class ListenerRoute {
 public static boolean send(MainActivity activity,TouchInputHandler handler,KeyEvent event){return ''' + route + ''';}
}'''
key = stubs['android/view/KeyEvent.java']
key = key.replace('final int code,action,device,scan,flags,meta,repeat;',
                  'final int code,action,device,scan,flags,meta,repeat; int source=InputDevice.SOURCE_KEYBOARD;')
key = key.replace('public int getKeyCode()',
                  'public KeyEvent(int c,int a,int d,int s,int f,long t,int m,int r,int src){'
                  'this(c,a,d,s,f,t,m,r);source=src;} public int getKeyCode()')
key = key.replace('return s==InputDevice.SOURCE_KEYBOARD;', 'return (source&s)==s;')
stubs['android/view/KeyEvent.java'] = key
for name, text in stubs.items():
    path = out / 'src' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
replay_path = TESTS / 'DirectListenerReplay.java'
(out / 'src/DirectListenerReplay.java').write_bytes(replay_path.read_bytes())
helper = (ROOT / 'input/history/handoff-accessibility-only/KeyBridgeHandoff.java' if BASELINE else ROOT / 'input/src/com/termux/x11/utils/KeyBridgeHandoff.java')
interceptor = ROOT / 'input/src/com/termux/x11/utils/KeyInterceptor.java'
assert helper.is_file() and interceptor.is_file()
if BASELINE:
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == '8ccface178d083ba909e7968ed8f5a80de42e52d877e5eb6f81f117f6bf01ab7'
production = [helper, interceptor]
production_bytes = {p: p.read_bytes() for p in production}
production_hashes = {str(p): hashlib.sha256(data).hexdigest() for p, data in production_bytes.items()}
if not BASELINE:
    assert production_hashes[str(helper)] == '2efc5f42701641e9f0b1bba63367b086423db39f3016e56cef47e4c1f4985304'
snapshot = out / 'production'
snapshot.mkdir()
for path, data in production_bytes.items():
    (snapshot / path.name).write_bytes(data)
compile_result = subprocess.run([TOOLS['javac'], *lint_flags(TOOLS['javac']), '-d', str(out / 'classes'),
                                 *map(str, sorted((out / 'src').rglob('*.java'))),
                                 *map(str, sorted(snapshot.glob('*.java')))],
                                capture_output=True, text=True, timeout=30)
(out / 'compile.txt').write_text(compile_result.stdout + compile_result.stderr)
assert compile_result.returncode == 0, compile_result.stderr
result = subprocess.run([TOOLS['java'], '-cp', str(out / 'classes'), 'DirectListenerReplay'],
                        capture_output=True, text=True, timeout=15)
(out / 'output.txt').write_text(result.stdout + result.stderr)
summary = re.search(r'^RESULT ([0-9]+) pass ([0-9]+) fail$', result.stdout, re.MULTILINE)
assert summary is not None
passed, failed = map(int, summary.groups())
assert result.returncode == (1 if BASELINE else 0)
assert failed > 0 if BASELINE else failed == 0
if BASELINE:
    assert 'FAIL direct-listener-legacy-183-native-pair' in result.stdout
    assert 'FAIL direct-listener-legacy-184-native-pair' in result.stdout
    assert 'PASS accessibility-legacy-183-native-pair' in result.stdout
    assert 'PASS accessibility-legacy-184-native-pair' in result.stdout
assert all(path.read_bytes() == data for path, data in production_bytes.items()), 'production source changed during replay'
test_sources = [Path(__file__).resolve(), replay_path, input_path]
receipt = dict(schema=1, mode='RED_ACCESSIBILITY_ONLY_LISTENER' if BASELINE else 'GREEN_COMMON_LISTENER_HOOK',
               status='EXPECTED_RED_HOST_DIRECT_LISTENER_BYPASS' if BASELINE else 'PASS_HOST_DIRECT_LISTENER_REPLAY',
               exitCode=result.returncode, passed=passed, failed=failed,
               helperSHA256=production_hashes[str(helper)],
               productionSHA256=production_hashes, productionSourceStable=True,
               compiledProductionSnapshot=True,
               testSourceSHA256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in test_sources},
               runnerSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               replaySHA256=hashlib.sha256(replay_path.read_bytes()).hexdigest(),
               existing29InputsSHA256=hashlib.sha256(input_path.read_bytes()).hexdigest(),
               androidFrameworkStubbed=True, activityListenerBoundaryStubbed=True,
               physicalInputVerified=False, jniVerified=False, deviceActions=False,
               limitation='Real helper/interceptor with public event fixtures; Android callback routing, packaged DEX seam and JNI require separate proof.')
(out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(result.stdout, end='')
work.cleanup()
