# Rootless Android Runtime Implementation Plan

> **For agentic workers:** Use executing-plans inline with independent artifact/build/native work delegated in this session. Track the steps below; do not commit or push.

**Goal:** 일반 APK UID의 Linux ARM64 실행을 구현·검증하고 실제 Wayland 터미널/Android Surface 연결까지 확장한다.

**Architecture:** PRoot와 loader는 APK native library 디렉터리에서 실행한다. 앱 전용 rootfs의 guest ELF는 loader를 통해 실행한다. Android Activity는 실행 제어·입력·Surface를 소유하고 Linux 실행과 Wayland 호스트는 분리한다.

**Tech Stack:** Java Android API, NDK/Rust Wayland 호스트, pinned PRoot, Alpine ARM64 minirootfs, Python 표준 라이브러리 빌드/검증 도구.

**Spec:** [초기 해결안](../../solution-proposal.md), 사용자 첨부 Loopy Desktop 명세의 MVP 0.1.

## Global Constraints

- Host OS remains Android; no root, AOSP rebuild, SELinux disable, or custom GPU driver.
- Code files stay at or below 500 lines; separate runtime, Android lifecycle, Wayland objects, rendering and tests.
- Never use ADB shell success as app UID execution proof.
- Use only a disposable VM for automatic install/launch tests; require explicit serial and `ro.kernel.qemu=1`.
- Preserve existing AVD and physical-device user data. No Y900 success claim without physical-device receipts.
- No commit/push requested; workspace is not a Git checkout.
- Tests assert actual behavior, not implementation text. Rootfs/artifact hashes and APK SHA accompany runtime receipts.

## Task 1: Reproducible dependencies and APK build

Files: `third_party/runtime.lock.json`, `third_party/NOTICE.md`, `tools/fetch_runtime.py`, `tools/build_android.py`, `tests/test_runtime_artifacts.py`, `tests/test_android_build.py`, `dev/build`.

Interface: downloader populates `build/runtime/arm64-v8a/libproot.so`, `libproot_loader.so`, `build/runtime/rootfs.tar.gz`; build consumes `android/AndroidManifest.xml`, `android/src/`, assets and native libraries, outputs `build/loopy-desktop-debug.apk` and build receipt.

- [x] Write and run failing integrity tests for missing artifact, checksum mismatch and preserved cache on failure.
- [x] Implement pinned official-source fetch with SHA verification and atomic writes; retain upstream licensing provenance.
- [x] Write and run failing build tests for SDK/JDK discovery and missing build inputs.
- [x] Build using installed SDK tools and a discovered JDK without global environment changes.

## Task 2: App-owned Linux execution and termination

Files: `android/AndroidManifest.xml`, `android/src/dev/loopy/desktop/{MainActivity,RuntimeSession,RootfsInstaller,RuntimeResult}.java`, `android/test/dev/loopy/desktop/RuntimeTests.java`.

Interface: `RuntimeSession.run(List<String>, long)` returns exit/output/context; `close()` terminates only its own processes. RootfsInstaller validates paths and materializes the app-owned filesystem. UI shows real command output and status, preserving errors.

```java
RuntimeResult result = session.run(Arrays.asList("/bin/sh", "-c", "printf loopy-runtime; uname -m"), 10000);
assertEquals(0, result.exitCode);
assertTrue(result.stdout.contains("loopy-runtime"));
assertTrue(result.stdout.contains("aarch64"));
```

- [x] Run app instrumentation first and observe failure for unavailable runtime.
- [x] Implement safe extraction, native-library executable/loader paths, bounded process IO and explicit stop.
- [x] Install the exact APK on the disposable VM and assert Linux output from app UID.
- [x] Assert timeout/stop, nonzero exit, second launch and no owned guest leftovers.

## Task 3: Wayland terminal displayed by Android

Files: `native/wayland-host/`, `android/src/dev/loopy/desktop/{NativeBridge,DesktopSurface}.java`, terminal dependency lock entries and app assets.

Interface: host receives an Android Surface, owns a private Unix socket, accepts guest Wayland clients; shm frames are validated, copied and released. Android input supplies focus/key/scroll events. Runtime session launches one real terminal.

- [x] Write/run buffer validation tests: offset/stride overflow, truncated pool, unsupported format, correct channel copy.
- [x] Implement minimum supported globals and xdg configure/ack needed by the selected terminal; never advertise unsupported protocols.
- [x] Build ARM64 JNI library and connect the real Linux terminal in the APK.
- [x] Verify actual frames, Surface recreation, terminal key input and scroll in VM; keep clipboard and mode detection acceptance separate.

## Task 4: Runtime receipts and independent review

Files: `tools/test_android_vm.py`, `dev/app-test`, `docs/runtime-implementation.md`, README and current solution status.

- [x] Write/run refusal tests for missing serial, physical device and disconnected device before installation.
- [x] Save exact APK/source/artifact hashes, Android/UID context, instrumentation output and cleanup evidence in a fresh validation directory.
- [x] Review actual source and test evidence independently; fix material findings and rerun covering tests.
- [x] Document implemented features and remaining MVP/Y900 gaps separately. Stop the disposable VM and retain receipts.
