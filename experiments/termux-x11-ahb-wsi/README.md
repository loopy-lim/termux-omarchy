# Native Termux:X11 AHardwareBuffer transport

This is an opt-in Turnip X11 WSI patch for the Y900's native Weston process.
It allocates a real Android HardwareBuffer, verifies its linear stride, imports
its DMA-BUF into Vulkan, and sends the AHB to Termux:X11 using its existing
modifier 1255 socket protocol. Vulkan fences and image ownership remain active.
Guest Hyprland continues exporting DMA-BUF; this does not enable SHM readback.

Source snapshot: Mesa bridge commit `8c095276f525605c67c5212aabd8e42ef588790a`,
under `build/termux-va-research-20261012/mesa-source`. Run `apply.py` against a
fresh copy. The helper is compiled into `wsi_common_x11.c`.

Native build: NDK 27.1.12297006, API 29, Meson cross build; configuration and
Termux headers/libraries are in `build/x11-copy-20261012/{cross.ini,native.ini,sysroot}`.
Meson options:

```
-Dplatforms=x11 -Dvulkan-drivers=freedreno -Dfreedreno-kmds=msm,kgsl
-Dgallium-drivers= -Dglx=disabled -Degl=disabled -Dopengl=false
-Dgbm=disabled -Dllvm=disabled -Dshared-llvm=disabled
-Dzstd=disabled -Dexpat=disabled -Dvideo-codecs=
-Dlibunwind=disabled -Dbuild-tests=false -Dvalgrind=disabled
-Ddisplay-info=disabled
```

The `msm` build option retains X11 DRM WSI support; runtime still uses KGSL.
The native build restores `VK_KHR_external_semaphore_fd`: binary SYNC_FD is
implemented by KGSL and required by Zink's dma-buf fence import. The separate
VA experiment disabled it to avoid FFmpeg's unsupported OPAQUE_FD timeline
path. Reusing that setting caused a real null function-pointer crash when
Hyprland began presenting. Do not copy native driver settings into the VA build.

Runtime selection is `graphics-ahb/selection.json` under the owned installation,
with SHA256 of `libvulkan_freedreno.so` and `icd.json`. Only native Weston gets:

```
LOOPY_X11_AHB=1
VK_ICD_FILENAMES=<private absolute ICD path>
LD_PRELOAD=/system/lib64/libbinder_ndk.so:/system/lib64/libnativewindow.so
```

Keep Mesa first in LD_LIBRARY_PATH. Moving all system libraries first selects
Android EGL, which cannot import the guest's DMA-BUF. Termux's stub binder and
android libraries also cannot supply the AHB API; the scoped preload resolves
only those real system dependencies. No NDK libc++ copy is shipped.

Device evidence is in `build/diagnostics/termux-omarchy-performance-20261012`:
`x11-ahb-colors5.json`, `x11-ahb-motion1.json`, `x11-ahb-start3.json`.
Dynamic 640x480, 1919x800 (stride 1920), and 1920x1280 frame/color tests passed.
Actual Omarchy logs show all Present copies offloaded to GPU. This proves the
copy boundary changed; it does not by itself prove smooth YouTube decoding.
The later desktop crash and failed decoding comparisons are retained alongside
successful results, rather than treated as acceptance.
