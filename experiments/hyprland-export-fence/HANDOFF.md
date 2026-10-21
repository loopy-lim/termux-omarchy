# GPU hand-off (not CPU%)

## Why CPU% was the wrong success metric

Present copies were already offloaded to GPU (AHB N/N). Lowering `termux-x11` CPU
after a rebuild does **not** mean more GPU acceleration. The remaining GPU-path
blocker is Hyprland's per-frame `glFinish()` before Weston samples the exported
DMA-BUF.

## Measured (2026-10-19, HiDPI 120Hz)

Source: `build/diagnostics/hyprland-export-fence-gpu-path-profile-20261019.json`

| Metric | Value |
| --- | --- |
| Weston explicit sync | **yes** |
| Present GPU offload | N/N @ ~120 FPS |
| native-fence create/dup | **ok / fail = 3240 / 0** |
| export `glFinish` avg | **~1.3–2.3 ms/frame** (~16% of 8.33ms budget) |

## Required change

1. Hyprland export unbind: create→flush→dup fence FD; **omit `glFinish` only when FD is queued for parent**
2. Aquamarine `CWaylandOutput::commit`: bind `zwp_linux_explicit_synchronization_v1`, `get_synchronization(surface)`, `set_acquire_fence(fd)` before attach/commit
3. Weston (stock): `eglWaitSync` on acquire fence (already capable when explicit sync advertised)
4. Fallback: if protocol missing or dup fails → keep `glFinish`

## Implementation (in tree)

| Piece | Path |
| --- | --- |
| Aquamarine apply | [`apply-aquamarine-handoff.py`](apply-aquamarine-handoff.py) |
| Hyprland apply | [`apply.py`](apply.py) (`HYPRLAND_GL_EXPORT_HANDOFF`) |
| Guest build | [`device-build-handoff.sh`](device-build-handoff.sh) → `aquamarine-export-fence` + `hyprland-export-fence` |
| Aqua-only rebuild | [`rebuild-aqua.sh`](rebuild-aqua.sh) |
| Activate | [`device-activate-candidate.py`](device-activate-candidate.py) swaps both + sets `HANDOFF=1` / `PROFILE=1` |
| Success log | `/tmp/loopy-export-profile.log` → `export fence-handoff: ok=N finish_fallback=N avg_finish_us=…` |

## FD ownership contract (learned the hard way)

This libwayland build does **not** close request FDs for us, and closing before
`wl_display_flush` freezes the pipeline (weston reads a recycled fd). Correct
sequence in `CWaylandOutput::commit`:

1. `fcntl(fenceFd, F_DUPFD_CLOEXEC)` → send the **dup** via `set_acquire_fence`
2. attach/damage/frame/commit as usual
3. after the stock `wl_display_flush`: `close(sentFd)` + `close(fenceFd)`

Verification: `fd_count` steady ~80–90, `finish_fallback=0`, 113–120 FPS under
window-cycling stress with live terminal damage + VSCode.

## Non-goals

- 60Hz / performance scale as “GPU win”
- Accepting termux-x11 CPU% alone
