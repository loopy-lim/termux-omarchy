# 상태 정정 · 2026-10-06

사용자는 Wayland와 네이티브 키보드·마우스 경험을 원한다고 명확히 정정했다. 이 문서의 Termux:X11/i3 방향은 요청을 잘못 해석한 실험이며 현재 제품 설계나 완료 기준으로 사용하지 않는다. 실험 소스와 실패 기록은 보존한다. 제품의 기본 경로는 Android 네이티브 Wayland 호스트와 Sway이고, 현재 검증은 [Wayland 입력 검증](../../wayland-native-validation.md)에 기록한다. Termux를 사용할 경우에도 Wayland를 유지하는 별도 backend의 지원 조건부터 확인한다.

---

# Native Termux desktop and input performance

User authorization: finish development, investigate alternatives, Termux is acceptable; native feel, performance, keyboard and mouse are the priorities. Existing implementation authorization covers source, artifacts and disposable-VM testing. No physical device changes, root, publication or unrelated repositories.

## Runtime choices

Keep the existing Alpine/Sway runtime and its saved user files. Add an explicitly selected native Termux desktop: native Bionic packages, i3, terminal/editor/file manager, Termux:X11 Android Surface. No PRoot in this path. Termux:X11 owns its focused keyboard, pointer capture, IME and presentation. Loopy releases its input before handoff. Public RUN_COMMAND connects the apps; the external X11 Activity is not described as an embedded Loopy Surface.

Preparation and execution must have distinct states: packages absent, permission absent, setup required, command pending, failure, X display/session verified. Start request alone is not success. Current request nonce and a private PendingIntent receiver validate result identity and bounds; a stale result cannot promote a new command. Loopy reads only the structured result of its own helper, not Termux private files. Start/stop/doctor run only the fixed owned helper and actions. User must explicitly allow the Termux command permission and external-app property. Missing settings/companions leave built-in Linux usable.

## Native environment

Deliver one installer with embedded runtime/config. Use official signed package repositories, preserve user configuration, write only under the owned Loopy native prefix. Pin companion APK bytes and upstream source references. Provide native start, stop, doctor and optional input-preset/restore actions. Own only new X11 display and process groups; validate ownership before reaping; never broad pkill or killall. Probe display readiness with a real X client and record process UID, runtime versions and rendering evidence. Installation is not rendering acceptance.

Default native desktop is keyboard-driven i3 with Ctrl+Alt shortcuts, lightweight bar and no extra compositing. Native terminal, editor and files open as real X11 windows. Termux:X11 input preferences apply only by explicit user selection, with bounded helper calls and snapshots of owned keys; restore must preserve subsequent user edits. Keyboard interception/accessibility remains opt-in. No automatic OEM/root settings.

## Graphics and latency

Investigate the current VirGL EGL failure using real initialized EGL/GL diagnostics. EGL1.5 core support must not be rejected solely for absent KHR extension strings. Bootstrap makeCurrent failure remains a real failure, with existing CPU fallback. Source overlays must be guarded, hashed and included in builder/packager receipts. Do not bypass shared-memory capability checks. Any pbuffer path must cover all current/context/cleanup paths before it can ship.

Improve the existing output loop only where code and a regression/measurement show reduced work or latency. Preserve event ordering, release events, Surface replacement, explicit recovery and stop semantics. Actual native/input/GPU performance on physical hardware remains separate from VM acceptance.

## Acceptance

Meaningful host failure-first tests cover command/result/state validation, native process ownership, installer preservation and bounds, EGL capability behavior and any scheduling change. Build pinned ARM64/API28 artifacts. On one final APK run current full native/host/Android regressions and native Termux companion tests on an owned disposable VM. A native X11 GUI must actually appear and receive synthetic keyboard/mouse input; receipt records installed APK/package bytes/versions and CPU/GPU scope. Deliver unique APK, native setup kit and exact receipts. Physical keyboard/trackpad/driver/battery acceptance remains an explicit device checklist.
