#!/usr/bin/env python3
"""Capture a comparable HiDPI desktop graphics sample via adb (host-side).

Records Present FPS/offload, process CPU, display scale, and Hyprland SHA.
Does not claim speedup — compare two receipts after a candidate binary trial.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def adb(*args: str, timeout: int = 30) -> str:
    return subprocess.check_output(['adb', *args], text=True, timeout=timeout, stderr=subprocess.STDOUT)


def adb_shell(script: str, timeout: int = 60) -> str:
    return adb('shell', script, timeout=timeout)


def parse_lorie(lines: list[str]) -> list[dict]:
    out = []
    pat = re.compile(
        r'(\d+) frames in ([\d.]+) seconds = ([\d.]+) FPS, '
        r'(\d+)/(\d+) present copies offloaded to GPU')
    for line in lines:
        m = pat.search(line)
        if not m:
            continue
        frames, secs, fps, ok, total = m.groups()
        out.append({
            'frames': int(frames), 'seconds': float(secs), 'fps': float(fps),
            'presentOk': int(ok), 'presentTotal': int(total),
        })
    return out


def sample_cpu() -> list[dict]:
    text = adb_shell(
        'run-as com.termux sh -c '
        '\'ps -A -o pid,pcpu,rss,args | grep -E "termux-x11 |weston |Hyprland " | grep -v grep\'')
    rows = []
    for line in text.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, pcpu, rss, args = parts
        name = 'termux-x11' if 'termux-x11' in args else (
            'weston' if 'weston' in args else (
                'Hyprland' if 'Hyprland' in args else 'other'))
        if name == 'other':
            continue
        rows.append({'name': name, 'pid': int(pid), 'pcpu': float(pcpu), 'rssKiB': int(rss)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', default='baseline', help='receipt label')
    parser.add_argument('--seconds', type=int, default=20, help='logcat window after clear')
    parser.add_argument('--out', type=Path, default=None)
    args = parser.parse_args()

    adb_shell('am start -n com.termux.x11/.MainActivity', timeout=15)
    time.sleep(2)

    scale = adb_shell(
        'run-as com.termux grep omarchy_monitor_scale '
        '/data/data/com.termux/files/usr/var/lib/proot-distro/containers/'
        'loopy-omarchy/rootfs/home/omarchy/.config/hypr/monitors.lua | head -1').strip()
    sha = adb_shell(
        'run-as com.termux sha256sum '
        '/data/data/com.termux/files/usr/var/lib/proot-distro/containers/'
        'loopy-omarchy/rootfs/opt/omarchy-android/hyprland/bin/Hyprland').split()[0]
    state = adb_shell(
        'run-as com.termux cat '
        '/data/data/com.termux/files/home/.local/share/loopy-omarchy/runtime-state.json')
    token = width = height = None
    try:
        st = json.loads(state)
        token, width, height = st.get('token'), st.get('width'), st.get('height')
    except json.JSONDecodeError:
        pass

    cpu_before = sample_cpu()
    adb('logcat', '-c')
    time.sleep(args.seconds)
    log = adb('logcat', '-d')
    presents = parse_lorie(log.splitlines())
    cpu_after = sample_cpu()

    def avg(name: str, rows: list[dict]) -> float | None:
        vals = [r['pcpu'] for r in rows if r['name'] == name]
        return round(sum(vals) / len(vals), 2) if vals else None

    receipt = {
        'schema': 1,
        'label': args.label,
        'capturedAt': datetime.now(timezone.utc).isoformat(),
        'fixture': 'HiDPI Omarchy idle foreground Termux:X11',
        'display': {'width': width, 'height': height, 'monitorScaleLine': scale},
        'sessionToken': token,
        'hyprlandSha256': sha,
        'presentSamples': presents,
        'presentSummary': {
            'n': len(presents),
            'fpsAvg': round(sum(p['fps'] for p in presents) / len(presents), 2) if presents else None,
            'offloadRatio': (
                round(sum(p['presentOk'] for p in presents) / sum(p['presentTotal'] for p in presents), 4)
                if presents and sum(p['presentTotal'] for p in presents) else None),
        },
        'cpu': {
            'before': cpu_before,
            'after': cpu_after,
            'termuxX11Pcpu': avg('termux-x11', cpu_after),
            'westonPcpu': avg('weston', cpu_after),
            'hyprlandPcpu': avg('Hyprland', cpu_after),
        },
        'notes': [
            'Speedup is NOT claimed by this receipt alone.',
            'Compare after deploying experiments/hyprland-export-fence candidate + PROFILE logs.',
            'glFinish µs requires HYPRLAND_GL_EXPORT_PROFILE=1 on the candidate binary.',
        ],
    }

    out = args.out or Path(
        f'build/diagnostics/hyprland-export-fence-{args.label}-'
        f'{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'wrote': str(out), 'presentSummary': receipt['presentSummary'],
                      'cpu': {k: receipt['cpu'][k] for k in (
                          'termuxX11Pcpu', 'westonPcpu', 'hyprlandPcpu')}}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
