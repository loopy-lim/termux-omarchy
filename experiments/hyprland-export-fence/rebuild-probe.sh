#!/bin/bash
set -Eeuo pipefail
cd /home/omarchy/export-fence-build
exec > >(tee -a rebuild-probe.log) 2>&1
echo REBUILD_START "$(date -Is)"
HL=/home/omarchy/export-fence-build/Hyprland
# Restore presentation-patched file (discard broken probe edits)
git -C "$HL" checkout HEAD -- src/render/gl/GLRenderbuffer.cpp
python3 /home/omarchy/export-fence-build/apply.py "$HL"
export PKG_CONFIG_PATH=/opt/omarchy-android/aquamarine/lib/pkgconfig:/opt/omarchy-android/mesa/root/usr/lib/pkgconfig
export LD_LIBRARY_PATH=/opt/omarchy-android/aquamarine/lib:/opt/omarchy-android/mesa/root/usr/lib
cmake --build /home/omarchy/export-fence-build/build --parallel 2 --target Hyprland
rm -rf /home/omarchy/export-fence-build/destdir2
DESTDIR=/home/omarchy/export-fence-build/destdir2 cmake --install /home/omarchy/export-fence-build/build
rm -rf /opt/omarchy-android/hyprland-export-fence
mkdir -p /opt/omarchy-android/hyprland-export-fence
cp -a /home/omarchy/export-fence-build/destdir2/opt/omarchy-android/hyprland-export-fence/. /opt/omarchy-android/hyprland-export-fence/
strings /opt/omarchy-android/hyprland-export-fence/bin/Hyprland | grep loopy-export-profile | head
echo REBUILD_DONE "$(date -Is)"
