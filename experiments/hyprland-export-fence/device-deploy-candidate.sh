#!/data/data/com.termux/files/usr/bin/bash
# Run inside Termux (run-as / loopy user). Swaps Hyprland to export-fence candidate.
set -Eeuo pipefail
ROOT="${HOME}/.local/share/loopy-omarchy"
RF="${PREFIX}/var/lib/proot-distro/containers/loopy-omarchy/rootfs"
STOCK="${RF}/opt/omarchy-android/hyprland"
CAND="${RF}/opt/omarchy-android/hyprland-export-fence"
test -x "${CAND}/bin/Hyprland"
loopy-omarchy stop
if [[ ! -e "${STOCK}.baseline-pre-export-fence" ]]; then
  mv "${STOCK}" "${STOCK}.baseline-pre-export-fence"
fi
rm -rf "${STOCK}"
cp -a "${CAND}" "${STOCK}"
# Opt-in profile for first trial (restore via unset after measure)
python3 - <<'PY'
from pathlib import Path
import re, hashlib, json, os
root = Path(os.environ['HOME']) / '.local/share/loopy-omarchy'
path = root / 'omarchy_commands.py'
text = path.read_text()
# Ensure EXPORT_PROFILE can be enabled via env file if present; do not rewrite hash pins here.
print('candidate installed; set HYPRLAND_GL_EXPORT_PROFILE=1 in a trial wrapper if needed')
PY
loopy-omarchy start
echo "candidate deployed; measure with measure-session.py and check export glFinish logs"
