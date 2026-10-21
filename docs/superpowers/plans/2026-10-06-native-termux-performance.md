# 중단된 실험 계획 · 2026-10-06

사용자의 Wayland 요구 정정에 따라 Termux:X11/i3 개발·전달 계획을 중단했다. 아래 항목은 당시 실험 이력이며 현재 진행할 작업 목록이 아니다. 미완료 항목과 실패 영수증을 완료로 바꾸지 않는다. 현재 제품은 [원래 Wayland 설계](../specs/2026-10-05-wayland-desktop-design.md)를 유지하고 [Wayland 입력 검증](../../wayland-native-validation.md) 기준으로 마무리한다.

---

# Native Termux Performance Implementation Plan

> **For agentic workers:** Use subagent-driven-development for independent modules. Implementation is authorized in the current session; this workspace has no Git repository.

**Goal:** Offer a usable native Termux desktop and improve verified graphics/input behavior while preserving the built-in runtime.

**Architecture:** Fixed RUN_COMMAND protocol + private result receiver connects Loopy to an owned native Termux i3/X11 session. Python/shell helpers own only their display/processes; Android owns handoff and preparation UI. Guarded native graphics changes retain CPU fallback.

**Tech Stack:** Android Java, Bash/Python native Termux, i3/X11, NDK EGL/VirGL, Rust Wayland.

**Spec:** [native-termux-performance-design.md](../specs/2026-10-06-native-termux-performance-design.md)

## Global Constraints

ARM64/API28+ Loopy. Ordinary app UID. Code modules <=500 lines. Existing user settings/files retained. No physical installation, root, OEM writes, commit/push. Only owned disposable VM changes. Diagnostics must distinguish command submission, display readiness, shown pixels and hardware GPU.

### Task 1: Native environment and pinned companions

**Owner:** daily_use_audit. **Files:** `termux/`, `tools/fetch_termux.py`, `third_party/termux.lock.json`, `tests/test_termux_native.py`; packaged self-contained script `android/assets/loopy-termux-setup.sh`.

**Interfaces:** Fixed helper `/data/data/com.termux/files/home/.local/share/loopy-native/runtime.py`, invoked by `/data/data/com.termux/files/usr/bin/python3` with arguments `[helper, action, requestUUID]`, action `start|stop|doctor|input|restore`. Each action emits one schema1 JSON object, <=16KiB: `schema`, `action`, `request`, `status`, `uid`, `display` plus bounded evidence/reason; start success additionally requires real `xReady:true` and `wmReady:true`. Runtime files live under `$HOME/.local/share/loopy-native`. Installer runs manually inside Termux; it does not grant Android permissions or enable external apps without explicit selection.

- [ ] Write/run failure-first executable tests for ownership, duplicate start/stop, failed X server, bounded child/prefs calls, configuration preservation and result schema.
- [ ] Implement native package setup and embedded helper/i3 config; no PRoot, moving shell installers or broad process kills.
- [ ] Pin official companion APK hashes/source references, verify downloads and preserve existing installed-source choice.
- [ ] Record native X11/API/input/graphics prerequisites in the research document and manual setup flow.

### Task 2: Android handoff and observable result state

**Owner:** root. **Files:** `NativeTermuxProtocol.java`, `NativeTermuxBridge.java`, `NativeTermuxResults.java`, `NativeTermuxPanel.java`, `DesktopMenus.java`, manifest, focused host/VM tests.

**Interfaces:** Fixed Termux package/service/action. `NativeTermuxBridge.run(activity, action)` releases current input and sends a bounded fixed argv, uses a fresh nonce/private receiver, only opens X11 after a successful verified start result. `NativeTermuxPanel.show()` offers setup script copy/export, companion install links, permission settings, start/stop/doctor and input preset/restore. Pending/result state is persisted with timestamp; unknown/malformed/stale/truncated results remain failure.

- [ ] Execute Java tests for exact command contract, current identity/result bounds, missing permission/companions, timeout and unavailable settings recovery.
- [ ] Add manifest visibility/permission/private receiver and native controls using existing styles; preserve Linux when switching apps.
- [ ] Verify absent/unprepared routes and actual RUN_COMMAND native X11 handoff in VM; test same built-in session/input release on returning.

### Task 3: Graphics compatibility and bounded latency improvements

**Owners:** permission_audit for VirGL; input_audit for output/input. **Files:** guarded EGL overlay/builder/input verifier tests; focused native host modules/tests as justified by audit.

- [ ] Reproduce EGL core/KHR and bootstrap failures in executable tests, then add diagnostics/version-aware guarded overlay and actual makeCurrent checks.
- [ ] Implement only safe bounded scheduling improvements with behavior/measurement evidence; retain release/ordering/idle/stop invariants.
- [ ] Rebuild changed native artifacts, run relevant native tests and app-UID pixel probes; hardware-render failure is recorded as fallback, not completion.

### Task 4: Exact delivery

**Owner:** root with independent reviewers. **Files:** build/delivery receipts and `docs/native-termux-validation.md`, README/quickstart/device checklist.

- [ ] Run full host/native tests, code-size checks, final APK full Android suite and real native companion GUI/input checks.
- [ ] Compare source/packaged/installed/artifact hashes, preserve all failures and establish concrete scope.
- [ ] Deliver no-clobber APK/setup kit, update actual use instructions and clean up only owned disposable VM.
