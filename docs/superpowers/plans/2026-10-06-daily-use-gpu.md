# 실사용 입력 권한과 GPU 구현 계획

> **For agentic workers:** Use subagent-driven-development for independent implementation tasks. User has requested completion including GPU; proceed through implementation and verification in this session.

**Goal:** 연결 장치에 따른 입력 소유권, 권한 안내와 GPU 화면 합성을 실행 가능한 APK로 제공한다.

**Architecture:** Android가 입력·권한·Surface를 관리하고 세션 서비스가 Linux 프로세스를 유지한다. Rust Wayland 호스트는 표면 장면을 전달하고 Android EGL/GLES가 합성하며 CPU 출력을 복구 경로로 제공한다.

**Tech Stack:** Android Java API 28–36, Rust Wayland server, C EGL/GLES, Python/JDK 호스트 시험.

**Spec:** `docs/superpowers/specs/2026-10-06-daily-use-gpu-design.md`

## Global Constraints

- Android 28 이상, target SDK 36과 기존 Java/Rust/C 빌드를 유지한다.
- 각 코드 파일은 500줄 이하로 유지한다.
- 루트나 OEM 비공개 API를 사용하지 않는다.
- GPU 경로는 Android 호스트의 합성과 출력이다.
- Linux Sway·브라우저·앱은 현재 pixman/wl_shm 경로이므로 게스트 3D 가속이나 DMA-BUF를 주장하지 않는다.

## 작업

- [x] GPU 담당: native Target/State/Window에 순서가 보존된 장면 인터페이스와 GLES 합성을 추가한다. 픽셀·클리핑·알파와 Surface 교체를 시험하고 `renderer=gles` 및 실제 GL 장치 문자열을 진단한다.
- [x] 입력 담당: DesktopSurface가 `updatePointerOwnership(boolean active, boolean hardwareMouse)`로 캡처를 요청·반납하도록 한다. 접근성 중단 때 입력을 해제하고 중복 모션을 차단한다. 기존 입력 정책 시험과 새 소유권 시험을 실행한다.
- [x] 권한 담당: DesktopPermissions의 `offer(snapshot)`, `show()`, `resumed()`, `close()`와 설정 진입점을 만든다. 반복 안내·거부·설정 복귀 정책을 검증한다.
- [x] 통합 담당: MainActivity에 위 수명·장치·포커스 경로와 Ctrl+Alt+Esc 반납을 연결한다. GPU·권한·긴급 반납의 Android instrumentation을 추가한다.
- [x] `python3 -m unittest discover -s tests -v`, native 시험, `python3 tools/check_code_size.py`를 실행한다.
- [x] `./dev/native-build`, `./dev/build --rootfs build/desktop/rootfs.tar.gz`를 실행하고 APK 입력 영수증을 확인한다.
- [x] 새 VM에서 `./dev/app-test --serial emulator-5580 --suite desktop --output docs/validation/<새 경로>`를 실행한다. 실패 원인을 수정한 최종 APK로 전체 시험을 완료한다. [최종 27/27 영수증](../../validation/2026-10-06-gpu-input-delivery-final-vm/receipt.json).
- [x] 새 전달 파일을 `build/deliverables/`에 보존하고 해시를 대조한다. README·빠른 시작·검증 문서에 현재 결과와 물리 기기 한계를 기록한다. [전달물과 검증](../../daily-use-gpu-validation.md).

이 작업 디렉터리에는 Git 저장소가 없으므로 커밋·푸시를 수행하지 않는다.
