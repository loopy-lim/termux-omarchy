#!/usr/bin/env python3
"""Run the actual isolated ARM wrapper through bounded child process contracts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CHILD = r'''import json,os,resource,signal,sys,time
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
fd=int(sys.argv[sys.argv.index('--watchdog-fd')+1])
path=os.environ['LOOPY_TEST_LOG']
try:
 with open(path) as f: number=len(f.readlines())+1
except FileNotFoundError: number=1
with open(path,'a') as f:
 f.write(json.dumps({'pid':os.getpid(),'args':sys.argv[1:],'env':dict(os.environ)})+'\n');f.flush()
mode=os.environ['LOOPY_TEST_MODE']
if mode=='startup':sys.exit(7)
os.write(fd,b'vax\n')
if mode=='cancel':time.sleep(30)
if mode=='repeat' and number<3:sys.exit(9)
if mode=='signal' and number==1:os.kill(os.getpid(),signal.SIGABRT)
if mode in ('recover','software') and number==1:sys.exit(9)
os.write(fd,b'end\n')
sys.exit(0)
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(candidate):
    if ROOT != Path('/workspace') or os.getuid() != 501 or os.uname().machine != 'aarch64' \
            or Path('/etc/hostname').read_text().strip() != 'loopy-omarchy-build':
        raise ValueError('Named ordinary-user ARM VM required')
    binary = candidate / 'components/start-hyprland'
    receipt = candidate / 'build-receipt.json'
    build = json.loads(receipt.read_text())
    if sha(binary) != build['binaries']['candidate']['sha256'] or build['packaged'] is not False:
        raise ValueError('Exact isolated ARM wrapper required')
    result = candidate / 'process-config-regression.json'
    if result.exists() or result.is_symlink():
        raise ValueError('Preserve completed process regression')
    cases = []
    for mode, route, expected_code, count in (
            ('normal', 'owned', 0, 1), ('startup', 'owned', 0, 1),
            ('recover', 'owned', 0, 2), ('repeat', 'owned', 1, 2),
            ('signal', 'owned', 0, 2), ('software', 'software', 0, 2),
            ('software', 'foreign', 0, 2), ('cancel', 'owned', 0, 1)):
        with tempfile.TemporaryDirectory(prefix='lwd-arm-') as folder:
            private = Path(folder)
            child = private / 'child'
            child.write_text('#!' + sys.executable + '\n' + CHILD)
            child.chmod(0o700)
            log = private / 'launches.jsonl'
            env = dict(PATH='/usr/bin:/bin', HOME=folder, XDG_RUNTIME_DIR=folder,
                       LOOPY_SESSION='watchdog-arm-1', LOOPY_TEST_LOG=str(log), LOOPY_TEST_MODE=mode,
                       LIBGL_ALWAYS_SOFTWARE='1', QT_QUICK_BACKEND='software', AQ_SHM_ONLY='1',
                       PYTHONDONTWRITEBYTECODE='1')
            if route != 'software':
                env.update(GALLIUM_DRIVER='virpipe', EGL_PLATFORM='surfaceless',
                           VTEST_SOCKET_NAME='/run/loopy/virgl-' + ('watchdog-arm-1' if route == 'owned' else 'foreign') + '.sock')
            process = subprocess.Popen([str(binary), '--no-nixgl', '--path', str(child), '--', '--config', '/run/loopy/private/hyprland.lua'], env=env,
                                       cwd=private, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, start_new_session=True)
            started = time.monotonic()
            try:
                if mode == 'cancel':
                    deadline = started + 3
                    while not log.exists() and time.monotonic() < deadline:
                        time.sleep(.01)
                    if not log.exists():
                        raise AssertionError('Actual wrapper child was not started')
                    process.terminate()
                _, errors = process.communicate(timeout=6)
                launches = [json.loads(line) for line in log.read_text().splitlines()]
                if process.returncode != expected_code or len(launches) != count:
                    raise AssertionError('Actual ARM wrapper contract failed: ' + mode + '\n' + errors)
                if route == 'owned' and count == 2:
                    software = launches[1]
                    if any(name in software['env'] for name in ('GALLIUM_DRIVER', 'VTEST_SOCKET_NAME', 'EGL_PLATFORM')) \
                            or software['env'].get('LIBGL_ALWAYS_SOFTWARE') != '1' \
                            or software['env'].get('QT_QUICK_BACKEND') != 'software' \
                            or software['env'].get('AQ_SHM_ONLY') != '1' \
                            or '--safe-mode' in software['args']:
                        raise AssertionError('GPU route survived actual ARM software retry')
                elif count == 2:
                    if launches[0]['env'] != launches[1]['env'] or '--safe-mode' not in launches[1]['args']:
                        raise AssertionError('Original software/foreign route environment or safe mode changed')
                for launch in launches:
                    if '--config' not in launch['args'] or launch['args'][launch['args'].index('--config') + 1] != '/run/loopy/private/hyprland.lua':
                        raise AssertionError('Actual ARM wrapper lost the private config argument')
                    try:
                        os.kill(launch['pid'], 0)
                    except ProcessLookupError:
                        continue
                    raise AssertionError('Owned watchdog child remained alive')
                cases.append({'mode': mode, 'route': route, 'exit': process.returncode,
                              'launch_count': len(launches), 'elapsed_ms': round((time.monotonic() - started) * 1000),
                              'software_retry': route == 'owned' and count == 2,
                              'stderr_sha256': hashlib.sha256(errors.encode()).hexdigest(), 'passed': True})
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
    if sha(binary) != build['binaries']['candidate']['sha256']:
        raise ValueError('ARM component changed during process regression')
    record = {'schema_version': 1, 'status': 'passed', 'cases': cases, 'passed': len(cases),
              'producer_sha256': sha(__file__), 'binary_sha256': sha(binary), 'build_receipt_sha256': sha(receipt),
              'child_source_sha256': hashlib.sha256(CHILD.encode()).hexdigest(), 'uid': os.getuid(),
              'architecture': 'aarch64', 'physical_device': False, 'hardware_gpu': False,
              'evidence_boundary': 'Actual real-source ARM wrapper and real child processes/pipes; children simulate watchdog events, not Hyprland GPU context failure.'}
    result.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'status': record['status'], 'passed': record['passed'], 'binary_sha256': record['binary_sha256']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    main(args.candidate.absolute())
