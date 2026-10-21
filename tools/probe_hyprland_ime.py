#!/usr/bin/env python3
"""Bounded repeated IMv2/native key delivery through actual private Hyprland and Foot.

Only public fixture text is traced, in the owned ARM VM. No Android or physical
input claims; each operation requires a PTY consumer witness and is never replayed.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT), str(ROOT / 'android/assets/omarchy-bridge')]
import loopy_input
from tools.probe_hyprland_clipboard import PARENT, LIBRARY, digest
from tools.probe_hyprland_rootless import stop

BINARY = Path('/var/tmp/loopy-hyprland-reproduced-build/Hyprland')
SHA = 'a9065af56d3c202166cb327970cc09961cc2a5e8f8bc636ae229021e75b47990'


def wait(condition, owned, timeout=4):
    end = time.monotonic() + timeout
    while not condition():
        assert all(p.poll() is None for p in owned), 'owned process exited'
        if time.monotonic() >= end: return False
        time.sleep(.005)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=12)
    args = parser.parse_args()
    assert ROOT == Path('/workspace') and os.getuid() == 501 and os.uname().machine == 'aarch64'
    assert Path('/etc/hostname').read_text().strip() == 'loopy-omarchy-build'
    assert args.output.parent == ROOT / 'docs/validation/2026-10-06-omarchy'
    assert args.output.name.startswith('ime-native-') and 1 <= args.rounds <= 40
    assert digest(BINARY) == SHA
    args.output.mkdir(); resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    receipt = {'status': 'running', 'uid': os.getuid(), 'physical_device': False, 'android': False,
        'hardware_gpu': False, 'hyprland_sha256': SHA, 'producer_sha256': digest(Path(__file__)),
        'parent_sha256': digest(PARENT), 'foot_sha256': digest(Path('/usr/bin/foot')),
        'foot_version': subprocess.check_output(['foot', '--version'], text=True).strip(),
        'input_sources': {n: digest(ROOT / 'android/assets/omarchy-bridge' / n)
                          for n in ('loopy_input.py', 'loopy_ime.py', 'loopy_input_trace.py')}, 'operations': []}
    parent = compositor = foot = temporary = None
    try:
        temporary = tempfile.TemporaryDirectory(prefix='loopy-ime-')
        with contextlib.nullcontext(temporary.name) as directory:
            runtime = Path(directory); runtime.chmod(0o700)
            config = runtime / 'hyprland.lua'
            config.write_text('hl.config({animations={enabled=false},debug={disable_logs=false,enable_stdout_logs=true}})\n')
            foot_config = runtime / 'foot.ini'; foot_config.write_text('[main]\nfont=JetBrainsMono Nerd Font Mono:size=14\n')
            fonts = runtime / 'fonts.conf'
            fonts.write_text('<fontconfig><dir>/workspace/guest/desktop/usr/share/fonts/truetype</dir>'
                             '<cachedir>' + directory + '/fontcache</cachedir></fontconfig>\n')
            witness = runtime / 'received.json'
            consumer = runtime / 'consumer.py'
            consumer.write_text('import sys,json,os\nfrom pathlib import Path\np=Path(sys.argv[1]);rows=[]\n'
                'for line in sys.stdin:\n rows.append(line);t=p.with_suffix(".new");t.write_text(json.dumps(rows));os.replace(t,p)\n'
                ' print("ACK " + str(len(rows)),flush=True)\n')
            env = dict(PATH='/usr/bin:/bin', HOME=directory, USER='loopy', LOGNAME='loopy', LANG='C.UTF-8',
                XDG_RUNTIME_DIR=directory, XDG_CONFIG_HOME=directory + '/config', XDG_CACHE_HOME=directory + '/cache',
                XDG_DATA_HOME=directory + '/data', XDG_STATE_HOME=directory + '/state', LD_LIBRARY_PATH=str(LIBRARY),
                FONTCONFIG_FILE=str(fonts), WAYLAND_DISPLAY='loopy-parent', AQ_SHM_ONLY='1', LIBGL_ALWAYS_SOFTWARE='1',
                HYPRLAND_NO_SD_NOTIFY='1', HYPRLAND_NO_SD_VARS='1', LOOPY_SESSION='owned-ime-reference')
            with (args.output / 'parent.log').open('x') as plog, (args.output / 'hyprland.log').open('x') as hlog, \
                    (args.output / 'foot-protocol.log').open('x') as flog:
                parent = subprocess.Popen([str(PARENT), str(runtime / 'loopy-parent'), '60', 'scene-fixture'],
                    stdin=subprocess.PIPE, stdout=plog, stderr=subprocess.STDOUT, text=True, start_new_session=True)
                assert wait(lambda: (runtime / 'loopy-parent').is_socket(), [parent])
                compositor = subprocess.Popen([str(BINARY), '--config', str(config)], env=env,
                    stdout=hlog, stderr=subprocess.STDOUT, start_new_session=True)
                assert wait(lambda: any(p.is_socket() for p in runtime.glob('wayland-*')), [parent, compositor])
                displays = [p for p in runtime.glob('wayland-*') if p.is_socket()]; assert len(displays) == 1
                env['WAYLAND_DISPLAY'] = displays[0].name
                control = BINARY.parent / 'hyprctl/hyprctl'
                assert wait(lambda: bool(list(runtime.glob('hypr/*/.socket.sock'))), [parent, compositor])
                signature = list(runtime.glob('hypr/*/.socket.sock'))[0].parent.name
                def active():
                    data = subprocess.check_output([str(control), '-i', signature, '-j', 'activewindow'], env=env, timeout=2)
                    return json.loads(data).get('class') == 'loopy-owned-ime'
                foot = subprocess.Popen(['foot', '--config', str(foot_config), '--app-id', 'loopy-owned-ime',
                    '/usr/bin/python', '-u', str(consumer), str(witness)], env=dict(env, WAYLAND_DEBUG='client'),
                    stdout=flog, stderr=subprocess.STDOUT, start_new_session=True)
                assert wait(active, [parent, compositor, foot]), 'Foot did not gain native initial focus'
                os.environ.update({k: env[k] for k in ('LOOPY_SESSION', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR')})
                loopy_input.IPC_ROOT = runtime
                (runtime / 'display-owned-ime-reference').write_text(displays[0].name + '\n')
                expected = []
                def matches():
                    try: return json.loads(witness.read_text()) == expected
                    except (OSError, ValueError): return False
                for index in range(args.rounds):
                    value = 'IME-' + str(index) + '-한글🙂\n'; expected.append(value); started = time.monotonic()
                    loopy_input.inject(value, timeout=5)
                    passed = wait(matches, [parent, compositor, foot])
                    receipt['operations'].append({'round': index, 'kind': 'atomic', 'delivered': passed,
                        'elapsed_ms': round((time.monotonic() - started) * 1000)})
                    assert passed, 'atomic input missing at round ' + str(index)
                    expected.append('loopy\n'); started = time.monotonic()
                    parent.stdin.write('type\n'); parent.stdin.flush()
                    passed = wait(matches, [parent, compositor, foot])
                    receipt['operations'].append({'round': index, 'kind': 'native', 'delivered': passed,
                        'elapsed_ms': round((time.monotonic() - started) * 1000)})
                    assert passed, 'native input missing at round ' + str(index)
                receipt['status'] = 'passed'
    except BaseException as error:
        receipt.update(status='failed', error=str(error))
    finally:
        if temporary is not None:
            for name in ('received.json', 'input-trace-owned-ime-reference.json'):
                source = Path(temporary.name) / name
                if source.is_file(): (args.output / name).write_bytes(source.read_bytes())
        loopy_input.close(); stop(foot); stop(compositor); stop(parent)
        if temporary is not None: temporary.cleanup()
        receipt['owned_children_stopped'] = all(p is None or p.poll() is not None for p in (foot, compositor, parent))
        (args.output / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ('status', 'error', 'operations') if k in receipt}, ensure_ascii=False), flush=True)
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__': raise SystemExit(main())
