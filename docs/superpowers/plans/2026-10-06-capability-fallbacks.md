# Capability Fallbacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Work is already authorized in this session.

**Goal:** 지원되지 않는 GPU·입력 기능을 진단하고 검증된 대체 경로 또는 준비 방법으로 연결한다.

**Architecture:** 게스트 Python probe가 child EGL 렌더와 장치 권한을 조사한다. 새 세션 launcher는 보고서에서 검증된 software GL을 선택하며 Android UI는 현재 token의 결과만 읽는다. 입력 대체 패널은 실제 설정 이동과 미연결 고권한 경로를 구분한다.

**Tech Stack:** Python ctypes/subprocess, Alpine Mesa, Android Java, NDK VirGL/EGL.

**Spec:** [graphics-alternatives-spec.md](../../graphics-alternatives-spec.md)

## Global Constraints

API28+, ARM64, 일반 앱 UID. 파일당 500줄 이하. 기존 세션/설정 보존. 자동 root/권한 부여 없음. 호스트 출력과 게스트 렌더 증거 분리. 물리기기 변경·커밋·푸시 없음.

### Task 1: Mesa loader and bounded guest probe

**Files:** `third_party/desktop.lock.json`, `guest/desktop/usr/local/lib/loopy/graphics_probe.py`, `graphics_egl.py`, `tests/test_graphics_probe.py`, `tests/test_graphics_packaging.py`.

**Interface:** `collect() -> dict` returns schema1/UID/devices/providers/selected; each candidate reports renderer and actual RGBA verification.

- [x] Write/run failure tests: missing DRI package, software masquerading as hardware, timeout, malformed output, pixel mismatch.
- [x] Add only same-version/same-source `mesa-dri-gallium`; verify APK SHA256/control/data hashes and dependency closure.
- [x] Implement isolated child probes, bounded JSON, `llvmpipe → softpipe → cairo`, no unsupported presentation claim.
- [x] Run `python3 -m unittest discover -s tests` and prepare pinned rootfs.

### Task 2: Session selection, diagnostics, and visible GL check

**Files:** `graphics_session.py`, `graphics_demo.py`, `guest/desktop/usr/local/bin/loopy-desktop`, `loopy-gl`, `loopy-graphics`, `desktop_ui.py`, `android/src/dev/loopy/desktop/GuestGraphicsStatus.java`, new host/VM graphics tests.

**Interface:** Session record `graphics-<token>.json`, UID/current token required. Launcher `graphics_session.py <token>` sets only predefined GL variables and execs Sway. `loopy-gl <argv>` uses the current session software route.

- [x] Test token/UID validation, unknown selection fallback, environment sanitization, stale reports.
- [x] Persist bounded atomic report and apply validated route at next session start, preserving pixman/cairo defaults.
- [x] Add user-visible GPU alternatives entry, explicit software GL window and settings diagnostics.
- [x] In VM require app UID EGL readback and visible GTK GL pixels; distinguish any context or presentation failure.

### Task 3: Input and privilege alternatives

**Files:** `DesktopAlternatives.java`, `DesktopPermissions.java`, `docs/research/android-authority-alternatives.md`.

- [x] Enumerate View/capture, accessibility, keyboard/IME, OEM, ADB, Shizuku, root, Device Owner/system paths and limitations using primary sources.
- [x] Add accessible scroll panel/actions without false grants or changing user settings.
- [x] Verify panel lifecycle and emergency/session regression in VM; execute unavailable-intent and fallback policy on host. OEM settings absence remains a physical-device check.

### Task 4: VirGL bridge feasibility and delivery

**Files:** `tools/build_virgl_android.py`, `third_party/virgl.lock.json`, `docs/research/guest-gpu-alternatives.md`, validation receipts.

- [x] Pin upstream sources/Termux patches and compile minimal Android API28 GLES vtest server if dependencies permit.
- [x] Record exact build blockers or test server app UID and Mesa client before integration.
- [x] Run all host/native/Android regressions on one final APK; validate source/package hashes and deliver unique APK plus receipt.
- [x] Update user guide with implemented automatic routes and conditional VirGL/Venus/Turnip/Termux/root/remote/native Android alternatives.

This directory has no Git repository; the plan's delivery artifact replaces a commit checkpoint.

## Completion evidence

Final APK `157be08c…`: host196, native40, Android VM32/32, source/package mismatch0. [Delivery and conditional alternatives](../../capability-fallback-validation.md) record exact hashes and acceptance boundaries. VirGL app UID/socket/CPU fallback/termination passed; actual proxy rendering failed at the VM EGL gate and remains unaccepted. The implemented guarded route and remaining methods are documented separately.
