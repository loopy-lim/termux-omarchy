#!/data/data/com.termux/files/usr/bin/python3
"""Read-only per-hop GPU/CPU verdict for the owned Omarchy session.

The acceleration pipeline has four independently verifiable hops: Termux:X11
present offload, the native Weston renderer, the guest Hyprland export/fence
path and the installed graphics-ahb transport. Session logs are the evidence;
this tool only reads them and never mutates the runtime.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

TOKEN = re.compile(r'[A-Za-z0-9-]{1,64}\Z')
DISPLAY = re.compile(r':[2-9][0-9]\Z')
PRESENT = re.compile(r'(\d+)/(\d+) present copies offloaded to GPU')
FRAMES = re.compile(r'(\d+) frames in ([0-9.]+) seconds = ([0-9.]+) FPS')
HANDOFF = re.compile(r'export fence-handoff: ok=(\d+) finish_fallback=(\d+) avg_finish_us=([0-9.]+)')
WESTON_GPU = re.compile(r'renderer[:\s].*(Adreno|Turnip|Zink)', re.I)
WESTON_CPU = re.compile(r'renderer[:\s].*(llvmpipe|softpipe|swrast)', re.I)
EXPLICIT_SYNC = re.compile(r'explicit sync: (yes|no)', re.I)
LOG_BYTES = 2 * 1024 * 1024  # StartupLog retains the first 1MiB; a larger file is drift.
STATE_BYTES = 131072
DRIVER_BYTES = 32 * 1024 * 1024
NEXT = {
    'gpu': 'none; collect frame-drop evidence separately before calling this a performance acceptance',
    'degraded': 'compare with the measured baselines in docs/validation/2026-10-12-termux-performance.md',
    'cpu': 'docs/research/2026-10-19-y900-graphics-acceleration-next.md lists the fallback and its measurements',
    'unknown': 'check that the owned desktop is running; a stopped session has no fresh logs',
    'installed': 'none; the private ICD drives Weston present offload',
    'not-installed': 'stock Turnip ICD is in use; present copies may fall back to CPU (0/294 was measured)',
    'integrity-error': 'graphics-ahb digest drifted; reinstall with omarchy_graphics_install.py or remove the directory',
}


def read(path, maximum):
    """Bounded regular-file read with the shared ownership and symlink rules.

    The stat runs on the open descriptor (graphics_install convention) so a
    same-uid swap between stat and open cannot bypass the checks.
    """
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('gpu-status-symlink')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as handle:
        row = os.fstat(handle.fileno())
        if not stat.S_ISREG(row.st_mode) or row.st_uid != os.getuid() \
                or row.st_mode & 0o022 or row.st_size > maximum:
            raise ValueError('gpu-status-file')
        return handle.read(maximum)


def verdict(state, evidence):
    return {'state': state, 'evidence': evidence, 'next': NEXT[state]}


def hop_present(text):
    matches = list(PRESENT.finditer(text))
    if not matches:
        return verdict('unknown', 'no present-offload line in x11.log')
    offloaded, total = (int(value) for value in matches[-1].groups())
    line = matches[-1].group(0)
    if not total:
        result = verdict('unknown', line)
    else:
        ratio = offloaded / total
        state = 'gpu' if ratio >= 0.95 else ('degraded' if ratio >= 0.5 else 'cpu')
        result = verdict(state, line)
    frames = list(FRAMES.finditer(text))
    if frames:
        result['frames'] = int(frames[-1].group(1))
        result['fps'] = float(frames[-1].group(3))
    return result


def hop_weston(text):
    line = next((row.strip() for row in reversed(text.splitlines()) if WESTON_CPU.search(row)
                 or WESTON_GPU.search(row)), '')
    if not line:
        return verdict('unknown', 'no renderer line in weston.log')
    if WESTON_CPU.search(line):
        return verdict('cpu', line[:200])
    result = verdict('gpu', line[:200])
    sync = EXPLICIT_SYNC.search(text)
    if sync:
        result['explicitSync'] = sync.group(1).lower()
    return result


def hop_hyprland(hyprland_text, fence_texts):
    for text in fence_texts:
        match = None
        for match in HANDOFF.finditer(text):
            pass  # Keep only the newest aggregate line.
        if match is None:
            continue
        ok, fallback = int(match.group(1)), int(match.group(2))
        # Zero frames prove nothing; only observed frames with a fallback count
        # re-adding the per-frame glFinish justify degraded.
        state = 'gpu' if ok and not fallback else ('degraded' if ok and fallback else 'unknown')
        result = verdict(state, match.group(0))
        result['avgFinishUs'] = float(match.group(3))
        return result
    if 'GPU presentation export ready' in hyprland_text:
        return verdict('gpu', 'GPU presentation export ready')
    if 'retaining SHM' in hyprland_text:
        return verdict('cpu', 'export unavailable; retaining SHM')
    return verdict('unknown', 'no export/fence evidence in hyprland.log and no fence profile log found')


def hop_ahb(root):
    directory = root / 'graphics-ahb'
    manifest = directory / 'selection.json'
    if not manifest.exists():
        return verdict('not-installed', 'graphics-ahb/selection.json is absent')
    try:
        value = json.loads(read(manifest, 4096).decode('utf-8', 'replace'))
        if value.get('schema') != 1:
            raise ValueError('gpu-status-ahb-schema')
        for name in ('libvulkan_freedreno.so', 'icd.json'):
            digest = hashlib.sha256(read(directory / name, DRIVER_BYTES)).hexdigest()
            if digest != value.get('sha256', {}).get(name):
                raise ValueError('gpu-status-ahb-digest')
    except (OSError, ValueError) as error:
        return verdict('integrity-error', str(error)[:160])
    return verdict('installed', 'selection.json and both files match the recorded digests')


def session(root):
    """Return the owned session context or a refusal reason; never adopt foreign state."""
    try:
        value = json.loads(read(root / 'runtime-state.json', STATE_BYTES).decode('utf-8', 'replace'))
    except (OSError, ValueError) as error:
        return None, f'runtime-state unreadable: {error}'
    if not isinstance(value, dict) or value.get('schema') != 1 or value.get('uid') != os.getuid():
        return None, 'runtime-state identity refused'
    token, display = value.get('token', ''), str(value.get('display', ''))
    if not TOKEN.fullmatch(token) or not DISPLAY.fullmatch(display):
        return None, 'runtime-state token or display malformed'
    return value, ''


def fence_paths(root):
    """Optional fence-profile log locations; absence only downgrades that hop to unknown.

    Standard Termux layout: the container rootfs lives under $PREFIX
    (…/files/usr, omarchy_runtime.py:91) and the shared runtime short path is
    …/com.termux/lr (omarchy_runtime.py:89).
    """
    try:
        files, termux = root.parents[3], root.parents[4]
    except IndexError:
        return []
    return [files / 'usr/var/lib/proot-distro/containers/loopy-omarchy/rootfs/tmp/loopy-export-profile.log',
            termux / 'lr/loopy-export-profile.log']


def collect(root, fence_override=None):
    root = Path(root)
    state, reason = session(root)
    result = {'schema': 1, 'tool': 'gpu-status', 'uid': os.getuid(), 'root': str(root),
              'exitIsToolSuccessOnly': True, 'session': None, 'hops': {}, 'summary': 'unknown'}
    if state is None:
        result['refusal'] = reason
        return result
    result['session'] = {'token': state['token'], 'display': state['display'],
                         'phase': state.get('phase', 'unknown'), 'width': state.get('width'),
                         'height': state.get('height'),
                         'requestedRefreshMhz': state.get('requestedRefreshMhz')}
    token = state['token']
    logs = {}
    for name in ('x11.log', 'weston.log', 'hyprland.log'):
        try:
            logs[name] = read(root / 'sessions' / token / name, LOG_BYTES).decode('utf-8', 'replace')
        except (OSError, ValueError) as error:
            logs[name] = ''
            result['hops'].setdefault('logReadErrors', {})[name] = str(error)[:120]
    texts = []
    for path in fence_override if fence_override is not None else fence_paths(root):
        try:
            texts.append(read(Path(path), LOG_BYTES).decode('utf-8', 'replace'))
        except (OSError, ValueError):
            continue
    result['hops']['present'] = hop_present(logs['x11.log'])
    result['hops']['weston'] = hop_weston(logs['weston.log'])
    result['hops']['hyprland'] = hop_hyprland(logs['hyprland.log'], texts)
    result['hops']['ahb'] = hop_ahb(root)
    order = {'cpu': 0, 'degraded': 1, 'unknown': 2, 'gpu': 3}
    states = [result['hops'][name]['state'] for name in ('present', 'weston', 'hyprland')]
    result['summary'] = min(states, key=lambda value: order.get(value, 2))
    return result


def human(result):
    session = result['session']
    if session is None:
        lines = [f"session: unavailable ({result.get('refusal', 'unknown')})"]
    else:
        lines = [f"session: {session['display']} phase={session['phase']} token={session['token']}"]
    for name, value in result['hops'].items():
        if name != 'logReadErrors':
            lines.append(f"{name}: {value['state']} — {value['evidence']}")
    for name, reason in result['hops'].get('logReadErrors', {}).items():
        lines.append(f'log {name}: unreadable ({reason})')
    lines.append(f"summary: {result['summary']}")
    lines.append('note: exit 0 means the tool ran; it is not a performance acceptance.')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/data/data/com.termux/files/home/.local/share/loopy-omarchy')
    parser.add_argument('--human', action='store_true')
    parser.add_argument('--fence-log', action='append', default=[], metavar='PATH')
    arguments = parser.parse_args(argv)
    root = Path(arguments.root)
    if not root.is_dir():
        print(json.dumps({'schema': 1, 'tool': 'gpu-status', 'status': 'failed',
                          'reason': 'runtime root directory not found'}), file=sys.stderr)
        return 2
    result = collect(root, arguments.fence_log or None)
    output = json.dumps(result, separators=(',', ':'))
    if len(output.encode()) > 16384:
        print(json.dumps({'schema': 1, 'tool': 'gpu-status', 'status': 'failed',
                          'reason': 'report exceeded bounds'}), file=sys.stderr)
        return 2
    print(human(result) if arguments.human else output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
