#!/bin/bash
set -Eeuo pipefail
cd /home/omarchy/export-fence-build
exec > >(tee -a build.log) 2>&1
echo START "$(date -Is)"
export PATH=/usr/bin:/bin
export PKG_CONFIG_PATH=/opt/omarchy-android/aquamarine/lib/pkgconfig:/opt/omarchy-android/mesa/root/usr/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}
export LD_LIBRARY_PATH=/opt/omarchy-android/aquamarine/lib:/opt/omarchy-android/mesa/root/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
PIN=5c9377c15f85c50648f35ca5a213754f95b93ca0
if [[ ! -d Hyprland/.git ]]; then
  git clone https://github.com/hyprwm/Hyprland.git Hyprland
fi
cd Hyprland
git fetch --depth 1 origin "$PIN" || git fetch origin "$PIN"
git checkout --force "$PIN"
git submodule update --init --recursive
git config user.name 'Loopy Export Fence'
git config user.email 'builder@loopy.invalid'
git reset --hard "$PIN"
git am --abort 2>/dev/null || true
git am --committer-date-is-author-date /home/omarchy/export-fence-build/patches/*.patch
python3 /home/omarchy/export-fence-build/apply.py /home/omarchy/export-fence-build/Hyprland
rm -rf /home/omarchy/export-fence-build/build /home/omarchy/export-fence-build/destdir
cmake -S /home/omarchy/export-fence-build/Hyprland -B /home/omarchy/export-fence-build/build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_DISABLE_FIND_PACKAGE_glaze=TRUE \
  -DCMAKE_PREFIX_PATH=/opt/omarchy-android/aquamarine \
  -DCMAKE_INSTALL_PREFIX=/opt/omarchy-android/hyprland-export-fence
cmake --build /home/omarchy/export-fence-build/build --parallel 2
DESTDIR=/home/omarchy/export-fence-build/destdir cmake --install /home/omarchy/export-fence-build/build
mkdir -p /opt/omarchy-android/hyprland-export-fence
cp -a /home/omarchy/export-fence-build/destdir/opt/omarchy-android/hyprland-export-fence/. /opt/omarchy-android/hyprland-export-fence/
test -x /opt/omarchy-android/hyprland-export-fence/bin/Hyprland
strings /opt/omarchy-android/hyprland-export-fence/bin/Hyprland | grep -E 'HYPRLAND_GL_EXPORT_PROFILE|export glFinish' | head
echo DONE "$(date -Is)"
