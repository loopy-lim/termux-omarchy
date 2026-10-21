# Remaining Wayland Desktop Implementation Plan

> 실행 방식: 이 세션에서 순차 구현하고 각 작업의 테스트와 결과를 확인한다.

**Goal:** Wayland 원격 화면을 통합하고 Android EGL VirGL의 pbuffer 호환 경로를 검증한다.

**Architecture:** Remmina는 고정 Alpine 네이티브 클라이언트를 사용한다. VirGL은 context별 surface를 관리하는 작은 C guard와 정확한 source overlay로 구성한다.

**Tech Stack:** Python, GTK3/Wayland, Remmina/FreeRDP/libvncclient, Android EGL/GLES, virglrenderer 1.3.0.

**Spec:** [승인된 범위](../specs/2026-10-06-remaining-desktop.md)

## 원격 화면

- [x] `tests/test_remote_desktop.py`: 주소·프로토콜·사용자 검증, 비밀 필드 거절, 실제 파일 모드·설정, symlink 거절과 자식 실행 실패 정리를 먼저 검사한다.
- [x] `guest/desktop/usr/local/lib/loopy/remote_desktop.py`: `profile(protocol, host, user, port)`, `connection_text(endpoint)`, `connect(endpoint)`를 구현한다. argv는 고정 실행 파일과 전용 파일 경로만 포함한다.
- [x] SSH 화면과 메뉴에 네이티브 화면 연결을 추가한다. Remmina의 비밀번호 저장 금지, clipboard/share 기본 비활성, TLS 확인을 유지한다.
- [x] `tools/extend_remote_lock.py`: 두 기존 index의 SHA/크기를 검증하고 `remmina` 의존성을 잠근다. 모든 APK Q1과 datahash 검증 뒤 atomic lock을 갱신한다.
- [x] rootfs·APK를 빌드하고 VM에서 실제 Remmina 창·원격 화면·입력 왕복을 확인한다.

## GPU

- [x] 실행형 C 테스트로 서로 다른 context의 독립 pbuffer, 실패 정리와 unbind 순서를 먼저 검사한다.
- [x] 500줄 이내인 `tools/virgl_egl_overlay.py` 내부 C guard에 surface 소유권을 구현하고 동일 overlay에서 잠긴 소스의 생성·current·destroy 지점에 연결한다.
- [x] overlay의 모든 입력과 생성 파일을 기존 build receipt에 기록한다.
- [x] helper와 APK를 빌드하고 app UID VM에서 initialized EGL, 실제 renderer, guest 픽셀과 종료를 검사한다. 실패하면 software fallback을 보존하고 실제 원인을 기록한다.

## 최종 검증

- [x] host 전체 검사, APK 입력·payload 검증, VM 해당 변경 검사와 필요한 회귀 검사를 실행한다.
- [x] README·빠른 시작·실기기 점검과 새 전달 영수증을 갱신한다. 신규·기존 APK를 구분하고 기기/OS 조건을 명시한다.
- [x] 소유한 VM·시험 서버를 종료한다. 실제 기기가 연결되면 읽기 전용 수집부터 진행한다.


완료 기록: RDP/VNC 구현·고정 패키지·실제 VNC 화면/키/포인터 왕복을 완료했다. EGL pbuffer와 잘못된 GLES 버전 거절 후 virpipe offscreen 픽셀이 통과했다. 기본 GTK proxy 창의 GL context 실패는 공식 GTK의 GLES 프로필 대조로 원인을 확인했고, 제품 wrapper에 반영해 최종 APK에서 실제 GTK readback과 Android Surface 표시를 다시 확인했다. 최종 호스트504·네이티브49·같은 APK의 VM49/49와 실제 제품 VirGL 창/VNC 왕복이 통과했다. 전달·정리 영수증은 최종 검증 문서에 연결했다. native TB522FU OS·물리 장치 수락은 별도 남은 조건이며 완료되지 않았다.
