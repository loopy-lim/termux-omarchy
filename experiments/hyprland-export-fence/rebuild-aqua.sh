#!/bin/bash
# Aquamarine-only rebuild for the hand-off fix (close fence FD after flush).
set -Eeuo pipefail
cd /home/omarchy/export-fence-build
exec > >(tee -a aqua-fix.log) 2>&1
echo AQUA_FIX_START "$(date -Is)"
export PATH=/usr/bin:/bin
export PKG_CONFIG_PATH=/opt/omarchy-android/mesa/root/usr/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}
export LD_LIBRARY_PATH=/opt/omarchy-android/mesa/root/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

AQ=/home/omarchy/export-fence-build/aquamarine
AQ_PREFIX=/opt/omarchy-android/aquamarine-export-fence

cmake --build /home/omarchy/export-fence-build/aq-build --parallel 2
rm -rf /home/omarchy/export-fence-build/aq-destdir
DESTDIR=/home/omarchy/export-fence-build/aq-destdir cmake --install /home/omarchy/export-fence-build/aq-build
rm -rf "$AQ_PREFIX"
mkdir -p "$AQ_PREFIX"
cp -a /home/omarchy/export-fence-build/aq-destdir"$AQ_PREFIX"/. "$AQ_PREFIX"/
test -e "$AQ_PREFIX/lib/libaquamarine.so.13"
echo AQUA_FIX_DONE "$(date -Is)"
