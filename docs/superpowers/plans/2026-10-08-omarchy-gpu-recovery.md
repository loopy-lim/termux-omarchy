# Omarchy GPU recovery implementation plan

> **For agentic workers:** Execute inline under the approved parent task. Use test-driven-development and verification-before-completion. Root owns ADB, native build, installation, NativeGraphicsServer.java, and final artifacts.

**Goal:** Keep production Omarchy usable on software while GUI GPU acceptance is pending; provide a separately guarded native watchdog candidate with one GPU-to-software recovery.

**Architecture:** Production Java selection returns the prepared software environment and never treats the existing offscreen probe as compositor acceptance. A separate diagnostic selection method preserves that probe. A source-pinned patch changes only the existing native watchdog abnormal-exit branch; the candidate remains separate from shipped native assets.

**Tech Stack:** Java, Python unittest, C++20-compatible recovery policy, pinned Hyprland watchdog source.

**Spec:** The approved task and `build/diagnostics/gpu-gui-failure-20261008/diagnosis.md`.

## Global constraints

- No ADB actions, rootfs edits, canonical native asset changes, baseline overwrites, or commits.
- Do not edit `NativeGraphicsServer.java`.
- Preserve the original successful/intentional watchdog exit branch and the restart behavior of initial software sessions.
- Production tiny-probe success must never promote the compositor.
- Native candidate recovery retries software once and returns failure on another abnormal exit.
- Keep modules below 500 lines and reject source/input drift before publishing a candidate.

## Task 1: Production selection boundary

**Files:** `android/src/dev/loopy/desktop/OmarchyGraphics.java`, `tests/test_omarchy_gpu.py`.

- [x] Add a test whose probe result reports perfect Adreno pixels but whose production selection must return BASE and call the guest zero times; run it and record the promotion failure.
- [x] Keep `select(session, environment, socket)` as the production entry point returning a fresh BASE copy. Move the previous guarded probe into `selectDiagnostic(session, environment, socket)`.
- [x] Run `python3 -m unittest tests.test_omarchy_gpu -v`; require production and diagnostic boundary cases to pass.

## Task 2: Guarded watchdog candidate

**Files:** `native/omarchy/watchdog/LoopyGpuRecovery.hpp`, `native/omarchy/patches/hyprland-gpu-recovery.{patch,json}`, `tools/prepare_omarchy_watchdog.py`, `tests/test_omarchy_watchdog.py`.

- [x] Compile and run pinned native `main.cpp` and `Instance.cpp` with host adapters for logging/memory/file-descriptor dependencies, using real child processes and watchdog pipes. First GPU failure must result in a software child; another abnormal exit must stop at two launches. Run the baseline and record the failed environment assertion.
- [x] Add the small recovery policy and guarded patch. Capture only the exact current-session `virpipe` socket route. On the first abnormal exit clear driver/socket/EGL overrides, set the prepared software variables, and latch recovery. On the next abnormal exit return failure. Leave the existing RET=true branch intact.
- [x] Prepare a separate candidate from the pinned archive after verifying all wrapper source preimages, metadata, patch, and added policy hashes. Refuse overwrite and symlinks. Record the complete candidate source inventory and producer identity; do not package it.
- [x] Test foreign/stale routes, normal exits, startup failure, initial software restarts, cancellation, exact environment preservation, source drift, and repeated preparation.
- [x] Run `python3 -m unittest tests.test_omarchy_gpu tests.test_omarchy_watchdog tests.test_omarchy_session -v` and deliver the source-only candidate boundary to root.

## Execution ledger

Ruling: Native wrapper is embedded in the immutable rootfs, while the shipped native component currently packages Hyprland only. This task prepares a separate watchdog candidate and leaves native asset integration to root; the Java production change is usable independently.

Ruling: The newest GUI case failed GL context creation with a live server. Preserve that distinct result while the older transport-loss crash remains intermittent. Host recovery tests prove the failure-handling branch; physical-device acceptance remains root work.

Validation: 19 targeted tests passed on the final source. Baseline Java selection failed `tiny probe must not promote production compositor`; the unpatched native watchdog leaked `GALLIUM_DRIVER` into its second child and launched three children. Final guarded sources passed real-process recovery, repeated failure, signal, clean exit, startup failure, initial software/foreign route, cancellation, and all source/producer/redirect guards.

Final source candidate: `build/diagnostics/gpu-gui-failure-20261008/watchdog-source-v3`. Earlier v1/v2 receipts remain preserved and are superseded because producer/metadata identity changed. Verify before building with `python3 tools/prepare_omarchy_watchdog.py --verify build/diagnostics/gpu-gui-failure-20261008/watchdog-source-v3`. Compiled, packaged, and Android GUI accepted remain false.

Canonical protection: The policy was moved outside the frozen Hyprland module namespace to `native/omarchy/watchdog/LoopyGpuRecovery.hpp`; the existing shared patch helper is unchanged. The frozen parent-refresh gate passed with 1993 checked inputs and the same AQ `47e20a15` / HL `f9bef874` binary identities. Production Java selection is frozen after this validation; root owns subsequent builds/install and readiness wording.
