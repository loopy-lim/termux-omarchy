#!/data/data/com.termux/files/usr/bin/python3 -I
"""Stop desktop, install hand-off aquamarine+Hyprland candidates, enable PROFILE+HANDOFF, start at 120Hz."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

HOME = Path(os.environ['HOME'])
PREFIX = Path(os.environ['PREFIX'])
ROOT = HOME / '.local/share/loopy-omarchy'
RF = PREFIX / 'var/lib/proot-distro/containers/loopy-omarchy/rootfs'
STOCK_HL = RF / 'opt/omarchy-android/hyprland'
BASELINE_HL = RF / 'opt/omarchy-android/hyprland.baseline-pre-export-fence'
CAND_HL = RF / 'opt/omarchy-android/hyprland-export-fence'
STOCK_AQ = RF / 'opt/omarchy-android/aquamarine'
BASELINE_AQ = RF / 'opt/omarchy-android/aquamarine.baseline-pre-export-fence'
CAND_AQ = RF / 'opt/omarchy-android/aquamarine-export-fence'


def swap_tree(stock: Path, baseline: Path, cand: Path) -> None:
    if not cand.exists():
        raise SystemExit(f'candidate missing: {cand}')
    if not baseline.exists():
        stock.rename(baseline)
    if stock.exists():
        shutil.rmtree(stock)
    shutil.copytree(cand, stock, symlinks=True)


def main() -> None:
    if not (CAND_HL / 'bin/Hyprland').is_file():
        raise SystemExit('hyprland candidate missing')
    if not (CAND_AQ / 'lib/libaquamarine.so.13').exists() and not list(CAND_AQ.glob('lib/libaquamarine.so*')):
        raise SystemExit('aquamarine candidate missing')
    subprocess.run(['loopy-omarchy', 'stop'], check=True)
    swap_tree(STOCK_AQ, BASELINE_AQ, CAND_AQ)
    swap_tree(STOCK_HL, BASELINE_HL, CAND_HL)
    (ROOT / 'display-refresh.json').write_text('{"schema": 1, "refreshMhz": 120000}\n')
    path = ROOT / 'omarchy_commands.py'
    text = path.read_text()

    def set_env(src: str, key: str, value: str) -> str:
        if key in src:
            out, n = re.subn(
                rf'(["\']{key}["\']\s*:\s*)["\'][^"\']*["\']',
                rf"\1'{value}'", src, count=1)
            if n != 1:
                raise SystemExit(f'{key} replace failed')
            return out
        out, n = re.subn(
            r'(["\']HYPRLAND_SHM_PROFILE["\']\s*:\s*["\'][^"\']*["\']\s*,)',
            rf"\1 '{key}': '{value}',", src, count=1)
        if n != 1:
            raise SystemExit(f'{key} insert failed')
        return out

    text2 = set_env(text, 'HYPRLAND_GL_EXPORT_PROFILE', '1')
    text2 = set_env(text2, 'HYPRLAND_GL_EXPORT_HANDOFF', '1')
    # Probe-only path is superseded by hand-off; force off if present.
    if 'HYPRLAND_GL_NATIVE_FENCE_PROBE' in text2:
        text2 = set_env(text2, 'HYPRLAND_GL_NATIVE_FENCE_PROBE', '0')
    old = path.read_bytes()
    new = text2.encode()
    tmp = path.with_name(path.name + '.tmp-ef')
    tmp.write_bytes(new)
    tmp.replace(path)
    os.chmod(path, 0o600)
    old_sha = hashlib.sha256(old).hexdigest()
    new_sha = hashlib.sha256(new).hexdigest()
    install_path = ROOT / 'install.json'
    install = json.loads(install_path.read_text())
    install['runtime_files']['omarchy_commands.py'] = new_sha
    install_path.write_text(json.dumps(install, separators=(',', ':'), sort_keys=True) + '\n')
    wrapper = PREFIX / 'bin/loopy-omarchy'
    wt = wrapper.read_text()
    if old_sha in wt:
        wrapper.write_text(wt.replace(old_sha, new_sha))
        os.chmod(wrapper, 0o700)
    out = subprocess.check_output(['loopy-omarchy', 'start'], text=True)
    print(json.dumps({
        'HYPRLAND_GL_EXPORT_PROFILE': '1',
        'HYPRLAND_GL_EXPORT_HANDOFF': '1',
        'refreshMhz': 120000,
        'aquamarine': str(STOCK_AQ),
        'hyprland': str(STOCK_HL),
        'commandsSha': new_sha,
        'start': json.loads(out),
    }, indent=2))


if __name__ == '__main__':
    main()
