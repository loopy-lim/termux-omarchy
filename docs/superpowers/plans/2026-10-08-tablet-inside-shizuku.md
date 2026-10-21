# Tablet-owned inside connection Implementation Plan

> **For agentic workers:** Use subagent-driven-development for the independent source tasks. Root executes all host compilation, builds and device verification. No Git repository or commit authorization exists here.

**Goal:** Start and retire the real Android inside broker from the tablet through Shizuku.

**Architecture:** DesktopSessionService owns a session-scoped client and typed UserService. The service supervises a single fixed app_process child, preserving the existing shell context and FD/window/input protocol. Hub admission quiesces before cooperative cleanup, and Linux retires only after exact clean ACK and reap.

**Tech Stack:** Java8 Android36, Shizuku13.1.5 API, custom javac/D8 builder, Python GTK3 Wayland bridge.

**Spec:** [2026-10-08-tablet-inside-shizuku.md](../specs/2026-10-08-tablet-inside-shizuku.md)

## Global Constraints

- Actual privileged UID2000 only; UID0 refused.
- Typed START/STATUS/STOP only; no arbitrary shell or external-app fallback.
- Modules at or below500 lines; root alone compiler/build/ADB on Y900.
- Preserve HOME/config/KeyBridge/roles/microphone denial and Chrome task131/display0.
- Missing readiness or cleanup proof stays unavailable/pending; no false completion.

### Task1: Child lifetime and typed service

**Files:** New AndroidInsideChildProtocol, AndroidInsideOwnedChild, AndroidInsideHostRpc, AndroidInsideUserService, AndroidInsideSupervisor and retirement helper; modify AndroidInsideShell and AndroidInsideAppHub. Tests under tests/java.

**Interfaces:** Child stdout READY(PID,birth,generation), STOPPED(clean,generation); stdin STOP orEOF. RPC START(session,appUID,appPID,appBirth,sourceDir,buildID,generation,ownerBinder), STATUS(generation), STOP(generation). Reply state,pid,birth,generation,cleanup.

- [ ] Write parser/tracker and retirement tests against inert refusing baselines. Core assertions:
```java
tracker.spawned(123,456);
tracker.ready(parse("READY\t123\t456\t789\n"),true);
assertEquals("RUNNING",tracker.state());
tracker.stopping(); tracker.stopped(parse("STOPPED\ttrue\t789\n"));
assertNotEquals("STOPPED",tracker.state());
tracker.reaped(); assertEquals("STOPPED",tracker.state());
```
- [ ] Root javac--release8 and Java harness: witness behavioral assertion failure before implementation; reject compile-only errors as RED.
- [ ] Implement bounded parser, exact owner/child verification and typed service; use ProcessBuilder with fixed argv and env.clear(). Add cooperative Shell ready/stop/cleanup delegation and Hub quiesce that retains active focus grants.
- [ ] Root reruns harnesses; check stale generation, wrong PID/birth, EOF, false ACK, reap without ACK and cleanup timeout all refuse replacement.

### Task2: Reproducible API packaging

**Files:** third_party/shizuku.lock.json, third_party/shizuku artifacts/license, tools/shizuku_inputs.py, tools/build_android.py, AndroidManifest.xml, tests/test_shizuku_inputs.py.

**Interfaces:** verified input list; extracted classes.jar list; generated AndroidInsideBuild.ID and VERSION. App DEX contains runtime dependencies; test DEX does not duplicate them.

- [ ] Write fixture tests for missing/changed/linked artifact and changed source build identity; root witnesses RED.
- [ ] Root downloads exact Maven bytes/license and verifies size/SHA; helper includes all artifacts/lock/license as build inputs.
- [ ] Generate build identity from sorted source names/content and manifest/lock/dependencies; VERSION=max(1,first7hex integer). Add provider, permissions, metadata and package visibility from pinned official manifest.
- [ ] Root host tests and whole APK build; inspect DEX for Shizuku presence and hidden-stub absence and verify unchanged native/runtime assets.

### Task3: Session-owned client and controls

**Files:** AndroidInsideHostController, DesktopInsideControls, DesktopSessionService, MainActivity, DesktopMenus, DesktopAlternatives, AndroidApps, platform_action.py, inside_window.py; behavioral tests.

**Interfaces:** controller reconcile(session), state, start, stop(cleanCallback), close. UserServiceArgs daemon(false), fixed tag/process suffix, compiled VERSION. Fixed payloadless `inside-backend` platform request opens only the current-session native panel.

- [ ] Write policy tests for permission/root rejection, stale callbacks, duplicate starts, owner/session change and cleanup gating; write fixed platform-request tests. Root witnesses RED.
- [ ] Implement listeners and worker RPC, preserve session while Shizuku opens, quiesce before STOP, delay Linux retirement until clean, display fixed status/actions and GTK connection-settings button.
- [ ] Root verifies host suites and compiles exact candidate. Freeze no-clobber APK/receipt, inspect fresh editors, stop the exact ADB-owned broker and wait for completion, update only.
- [ ] Root verifies exact installed APK, preserved121configs/roles/services/mic denial; start through real Shizuku permission/service path, public target inside draw/key/click/scroll/resize/CLOSED, death/recovery and cleanup. Record connected-ADB versus USB-free evidence separately.
- [ ] Independent source review and focused repairs; publish a local validation report with exact receipts and remaining Chromium sandbox/physicalFPS/complete Omarchy gaps.
