#!/bin/bash
# Run inside guest (loopy-omarchy). Builds aquamarine + Hyprland with acquire-fence hand-off.
set -Eeuo pipefail
cd /home/omarchy/export-fence-build
exec > >(tee -a handoff-build.log) 2>&1
echo HANDOFF_START "$(date -Is)"
export PATH=/usr/bin:/bin
export PKG_CONFIG_PATH=/opt/omarchy-android/mesa/root/usr/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}
export LD_LIBRARY_PATH=/opt/omarchy-android/mesa/root/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

AQ=/home/omarchy/export-fence-build/aquamarine
HL=/home/omarchy/export-fence-build/Hyprland
AQ_PREFIX=/opt/omarchy-android/aquamarine-export-fence
HL_PREFIX=/opt/omarchy-android/hyprland-export-fence

test -d "$AQ"
test -d "$HL"
test -f /home/omarchy/export-fence-build/apply-aquamarine-handoff.py
test -f /home/omarchy/export-fence-build/apply.py

# --- Aquamarine ---
python3 /home/omarchy/export-fence-build/apply-aquamarine-handoff.py "$AQ"
rm -rf /home/omarchy/export-fence-build/aq-build /home/omarchy/export-fence-build/aq-destdir
cmake -S "$AQ" -B /home/omarchy/export-fence-build/aq-build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$AQ_PREFIX"
cmake --build /home/omarchy/export-fence-build/aq-build --parallel 2
DESTDIR=/home/omarchy/export-fence-build/aq-destdir cmake --install /home/omarchy/export-fence-build/aq-build
rm -rf "$AQ_PREFIX"
mkdir -p "$AQ_PREFIX"
cp -a /home/omarchy/export-fence-build/aq-destdir"$AQ_PREFIX"/. "$AQ_PREFIX"/
test -e "$AQ_PREFIX/lib/libaquamarine.so.13"
strings "$AQ_PREFIX/lib/libaquamarine.so.13" | grep -E 'set_acquire_fence|zwp_linux_surface_synchronization' | head || true
nm -D "$AQ_PREFIX/lib/libaquamarine.so.13" | grep -i PresentationAcquire || true

# --- Hyprland (against handoff aquamarine) ---
export PKG_CONFIG_PATH="$AQ_PREFIX/lib/pkgconfig:/opt/omarchy-android/mesa/root/usr/lib/pkgconfig"
export LD_LIBRARY_PATH="$AQ_PREFIX/lib:/opt/omarchy-android/mesa/root/usr/lib"
git -C "$HL" checkout HEAD -- src/render/gl/GLRenderbuffer.cpp
python3 /home/omarchy/export-fence-build/apply.py "$HL"
rm -rf /home/omarchy/export-fence-build/build /home/omarchy/export-fence-build/destdir
cmake -S "$HL" -B /home/omarchy/export-fence-build/build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_DISABLE_FIND_PACKAGE_glaze=TRUE \
  -DCMAKE_PREFIX_PATH="$AQ_PREFIX" \
  -DCMAKE_INSTALL_PREFIX="$HL_PREFIX"
cmake --build /home/omarchy/export-fence-build/build --parallel 2
DESTDIR=/home/omarchy/export-fence-build/destdir cmake --install /home/omarchy/export-fence-build/build
rm -rf "$HL_PREFIX"
mkdir -p "$HL_PREFIX"
cp -a /home/omarchy/export-fence-build/destdir"$HL_PREFIX"/. "$HL_PREFIX"/
test -x "$HL_PREFIX/bin/Hyprland"
strings "$HL_PREFIX/bin/Hyprland" | grep -E 'HYPRLAND_GL_EXPORT_HANDOFF|export fence-handoff' | head
echo HANDOFF_DONE "$(date -Is)"
