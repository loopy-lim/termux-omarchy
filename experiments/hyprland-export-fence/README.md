# Hyprland export-path `glFinish` / native-fence probe

Opt-in instrumentation on the Omarchy Android KGSL **presentation export**
path. It does **not** remove `glFinish` and does **not** change default
launcher env. Goal: measure whether export-path `glFinish` is worth replacing
with `EGL_ANDROID_native_fence_sync` → `sync_file` hand-off, while keeping
HiDPI (3840×2560 / scale 2.5).


## Status (2026-10-19/20): acquire-fence hand-off

Hand-off is implemented and verified on device:

- `HYPRLAND_GL_EXPORT_HANDOFF=1` → create/dup fence → `IBuffer::setPresentationAcquireFence` → Aquamarine `set_acquire_fence` → skip `glFinish`
- PROFILE: `export fence-handoff: ok=N finish_fallback=0 avg_finish_us=0`
- Present GPU offload ratio 1.0 @ ~118 FPS (see `build/diagnostics/hyprland-export-fence-handoff-verified-20261019.json`)
- Build: `device-build-handoff.sh`; activate: `device-activate-candidate.py` (swaps aquamarine + Hyprland)

## Why this exists

Live Y900 facts (2026-10-19):

- Termux:X11 AHB Present: GPU offload N/N @ ~120 FPS
- `HYPRLAND_GL_DMABUF_EXPORT=1` active (`/dmabuf:` + `sync_file` FDs)
- `HYPRLAND_SHM_PROFILE` never logs on the hot path — export early-return skips SHM readback
- Remaining compositor cost includes per-frame `glFinish()` before Weston samples

Base contract: BlackFireAlex omarchy-android v0.1.1
[`0001-render-carry-proven-Android-KGSL-presentation-path.patch`](../../build/omarchy-v011-source/patches/hyprland/0001-render-carry-proven-Android-KGSL-presentation-path.patch)
(`CGLRenderbuffer::unbind` export branch). Research context:
[2026-10-19 next steps](../../docs/research/2026-10-19-y900-graphics-acceleration-next.md) §7;
fence design notes (primary sources):
[export native fence](../../docs/research/2026-10-19-hyprland-export-native-fence.md).

## What the probe adds

Apply [`apply.py`](apply.py) to a Hyprland tree that **already** has the v0.1.1
presentation patch. It replaces only the export early-return body.

| Env | Default | Effect |
| --- | --- | --- |
| `HYPRLAND_GL_EXPORT_PROFILE` | off | Every 120 export frames, log avg µs spent in `glFinish` |
| `HYPRLAND_GL_NATIVE_FENCE_PROBE` | off | `eglCreateSyncKHR(EGL_SYNC_NATIVE_FENCE_ANDROID)` → `glFlush` → `eglDupNativeFenceFDANDROID`; count ok/fail; **still** call `glFinish`; close the FD (no hand-off). Hand-off needs Aquamarine `set_acquire_fence` + Weston wait — see research note. |

`glFinish` remains the synchronization barrier. Probe failure must not change
presentation correctness.

## Build

Guest rebuild path (Arch ARM builder), same as stock Omarchy graphics:

```bash
# 1. Local forks with v0.1.1 patches applied (mesa, aquamarine, hyprland)
# 2. On the hyprland fork, after git am of the presentation patch:
python3 experiments/hyprland-export-fence/apply.py /path/to/hyprland-fork

# 3. Rebuild (do not overwrite an existing artifact root)
./build/omarchy-v011-source/builder/host/build-guest-graphics.sh \
  /abs/path/to/omarchy-android-forks \
  /abs/path/to/guest-artifacts/graphics-export-fence
```

Prefer a Hyprland-only rebuild if your fork workflow allows; the host script
builds mesa+aquamarine+hyprland together.

## Deploy (candidate only)

1. On device, rename stock `/opt/omarchy-android/hyprland` → `hyprland-baseline-<sha>`
   or install the candidate beside it as `hyprland-export-fence/`.
2. Point the trial session `PATH` / binary at the candidate **only** for that
   trial (do not change `termux/omarchy_commands.py` defaults until A/B passes).
3. Short trial with HiDPI:
   - `HYPRLAND_GL_EXPORT_PROFILE=1`
   - optionally `HYPRLAND_GL_NATIVE_FENCE_PROBE=1`
4. Collect from guest Hyprland log (`…/lr/hypr/<instance>/hyprland.log`):
   - `export glFinish: avg … us over … frames`
   - `export native-fence probe: ok=… fail=…`
5. Restore stock binary + unset probe envs; restart.

## Measuring “did it get faster?”

Research alone is not acceptance. Compare receipts before/after a candidate:

```bash
# Host, device on adb, desktop ready + Termux:X11 foreground
python3 experiments/hyprland-export-fence/measure-session.py --label baseline-hidpi --seconds 20
# After candidate deploy + HYPRLAND_GL_EXPORT_PROFILE=1 trial:
python3 experiments/hyprland-export-fence/measure-session.py --label probe-hidpi --seconds 20
```

Also collect guest log lines `export glFinish: avg … us` and `export native-fence probe: ok=…`.
Speedup claims need: Present offload not regressed, and either lower `termux-x11`/`Hyprland` CPU under the same fixture, or lower export `glFinish` µs with no stale frames. Hand-off (Finish removed) is a later A/B.

**2026-10-19 measurements (HiDPI):**

| Label | Binary | refresh | termux-x11 CPU | Present offload | receipt |
| --- | --- | --- | --- | --- | --- |
| baseline | stock `c1f642c1…` | 120Hz | ≈79.5% | 1.0 | `…baseline-hidpi-20261019T124142Z.json` |
| 60Hz trial | stock | 60Hz | ≈55–58% | 1.0 | `…120vs60-20261019.json` |
| candidate | device-built export-fence probe | 120Hz | ≈64–68% | 1.0 | `…stock-vs-candidate-120hz-20261019.json` |

On-device build: `device-build.sh` inside guest. Activate: `device-activate-candidate.py`. Rollback: restore `hyprland.baseline-pre-export-fence` → `hyprland`, set `HYPRLAND_GL_EXPORT_PROFILE=0`, stop/start. PROFILE log lines were not observed (0-byte hyprland.log) — fix logger sink before trusting µs.

## Acceptance for this experiment (probe stage)

1. AHB Present GPU offload stays ≥95% on HiDPI idle+scroll (≥5s samples).
2. Candidate starts; no stale/corrupt frames vs baseline in a short visual check.
3. PROFILE lines appear under load (not only idle damage-empty frames).
4. NATIVE_FENCE_PROBE reports either ok>0 or a stable fail reason — never crash.
5. Rollback to baseline binary succeeds in one stop/start.

Hand-off (remove `glFinish`, attach FD for parent wait) is **out of scope**
until PROFILE numbers show `glFinish` dominates the export path and the
research note names who waits on the FD (Aquamarine vs Weston).

## Non-goals

- `loopy-display performance` / scale compromise packaged as “GPU accel”
- `AQ_ANDROID_DMABUF_HEAP/VULKAN=1` in the same trial
- Changing Termux:X11 AHB / `graphics-ahb` selection
- Touching Loopy SHM-only `native/omarchy/patches/hyprland-shm-renderer.patch`
