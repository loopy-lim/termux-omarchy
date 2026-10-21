# 데스크톱 검증 상태와 증거 경계

2026-10-05 납품 APK가 Android VM의 **전체 14/14 검사**를 통과했다. Y900 실기기 수락은 아직 없다.
검증 대상은 실제 Linux GUI 앱의 실행·조작·Android Surface 렌더링이다.

이 문서는 **2026-10-05 APK의 보존 기록**이다. 2026-10-06 Firefox·Geany·raw/captured 터치패드·오른쪽 상태 표시 제거·실제 UID·DNS·PRoot 수정은 [앱 확장 검증](desktop-app-extension-validation.md)을 기준으로 한다. 아래의 mutable `build/` 파일은 이후 빌드로 바뀔 수 있으므로 이 실행의 입력은 [복사된 빌드 영수증](validation/2026-10-05-desktop-delivery-vm/build-receipt.json)에서 확인한다.

## 후보와 결과 연결

| 항목 | 기록 |
| --- | --- |
| 앱 APK | `build/loopy-desktop-debug.apk` |
| 빌드 범위 | ARM64, min API 28, target API 36, Alpine 3.22.6 + Sway 1.10.1 |
| 직전 후보 전체 VM 실행 | [desktop-session-scoped](validation/2026-10-05-desktop-session-scoped/receipt.json) — 14/14 |
| 설정 수정 후 VM | [desktop-validated](validation/2026-10-05-desktop-validated/receipt.json) — 14/14 |
| 최종 APK | 마우스 DOWN/UP 클릭 경로 보강. [desktop-delivery-vm](validation/2026-10-05-desktop-delivery-vm/receipt.json) — 14/14 |
| APK SHA-256 | `9a9aa44d25b0f7dfcb62202e720aaaed3b0b2b8a03413467a4a008275f88f4e9` |

해시와 입력은 [빌드 영수증](../build/build-receipt.json), rootfs 구성은 [준비 영수증](../build/desktop/receipt.json)에 기록돼 있다.
VM 결과의 APK·테스트 APK 해시는 각 실행 폴더의 영수증을 기준으로 한다. [무결성 확인](validation/2026-10-05-desktop-delivery-vm/build-integrity.json)에서 빌드 입력 57개·네이티브 소스 25개·APK에 포함된 파일을 대조했고, APK 서명도 확인했다.
납품 파일은 [LoopyDesktop-2026-10-05-desktop-arm64.apk](../build/deliverables/LoopyDesktop-2026-10-05-desktop-arm64.apk)다. 빌드 APK와 복사본의 크기·SHA-256이 같다.

## 확인한 증거와 아직 말할 수 없는 것

| 증거 | 확인 내용 | 경계 |
| --- | --- | --- |
| 호스트 시험 | 111개 통과. 설정 동기화와 마우스 클릭·중복 제거·취소 해제 포함 | Java/Python 정책·파일·무결성 로직 증거이며 실제 기기 입력 증거가 아니다. |
| 네이티브 시험 | 36개 통과 | Wayland 리소스·입력·렌더링 로직 증거이며 물리 GPU 성능 증거가 아니다. |
| 코드 크기 | 코드 168개, 최대 466행 | 유지보수 제약 확인이며 기능 합격 수가 아니다. |
| [이전 전체 VM](validation/2026-10-05-desktop-release-vm/receipt.json) | 13/14, wmenu 렌더 준비 단계 실패 | 해당 영수증에 기록된 후보의 결과다. 최종 후보의 전체 합격으로 바꾸어 읽지 않는다. |
| [편집기 단독 VM](validation/2026-10-05-desktop-editor-location-ready/receipt.json) | 1/1, Mousepad의 Open File 창과 `Welcome.md` 렌더 확인 | 동일 생산 입력의 별도 단독 실행이며 전체 시험의 간헐 실패를 지우지 않는다. |
| 최종 전체 VM | 14/14, Mousepad 파일 열기·타일링·작업공간·resize·세션 유지·종료·양방향 클립보드·한글 IME | 읽기 전용 Sway IPC 재시도는 이번 실행에서 0회. 입력 지연·물리 성능 수락 시험은 아니다. |

이전 전체 VM과 편집기 단독 VM은 동일 생산 입력을 사용했다. 각 VM 결과는 기록된 APK·테스트 APK 쌍에 귀속되며, 이후 생산 변경을 검증한 것으로 읽지 않는다.
이전 VM은 Android 16/API 36, `emulator-5580`, 일반 앱 UID 10224와 `untrusted_app` SELinux 컨텍스트에서 수행했다.

## 실제 GUI와 입력의 구분

Sway 창 트리의 앱 ID·PID·표시 상태와 Android Surface의 픽셀 변화를 함께 확인한다.
foot은 실제 게스트 명령 출력과 창·작업공간 조작을, Mousepad는 실제 파일 열기 흐름을 확인했다.
Thunar도 포함된 Linux GUI 앱이지만, 패키지 존재만으로 모든 파일 관리 동작이 검증됐다고 해석하지 않는다.

[실제 실행 화면](validation/2026-10-05-desktop-delivery-vm/desktop-screen.png)에는 Mousepad의 `Welcome.md`와 Thunar 공유 폴더가 함께 보인다. 두 GUI 프로세스의 Android UID 10224, 창 PID·표시 상태를 [GUI 기록](validation/2026-10-05-desktop-delivery-vm/gui-receipt.json)에 대조했다. 마우스로 홈 버튼을 눌러 같은 Thunar PID에서 `shared`→`root` 폴더 이동을 확인했다.

접근성 입력 우선권 서비스를 VM에서 켠 상태에서도 같은 마우스 클릭은 통과했다. 추가 `SOURCE_TOUCHPAD` 단일 탭 주입은 폴더 이동을 확인하지 못했다([별도 기록](validation/2026-10-05-desktop-delivery-vm/pointer-priority-receipt.json)). 이것을 합격으로 처리하거나 Y900 raw 트랙패드 동작으로 확대하지 않는다. VM 접근성 설정은 시험 전 값으로 복원했다. Android의 공개 [모션 구독 API](https://developer.android.com/reference/android/accessibilityservice/AccessibilityServiceInfo#setMotionEventSources(int))만으로 실제 기기의 접점 제공을 보장하지 않는다.

화면의 guest root 경고는 PRoot 안의 UID 0 표시다. 실제 Android 프로세스는 일반 앱 UID로 실행됐으며 Android root 권한을 얻은 것이 아니다.

시험의 Android 키·포인터 주입은 앱 창에서 Linux까지 전달되는 경로의 증거다.
물리 Y900 키보드·트랙패드, OEM 예약 Meta/Super, 접근성 서비스의 실제 사전 키 전달을 대신하지 않는다.
접근성 서비스는 사용자가 직접 켜며 전달된 키를 정책에 따라 처리한다. 모든 시스템 예약 키를 회수한다고 보장하지 않는다.
Android 13 이하에는 접근성 모션 소스 API가 없고, Android 14 이상에서도 raw 다중 접점 수신은 기기마다 다르다.
Y900 성능·배터리·절전 복귀와 Lenovo OEM 설정 변경/복원은 [실기기 점검](y900-test-checklist.md)의 별도 수락 항목이다.

## Omarchy 원본과의 차이

현재 구현은 Alpine/Sway를 하나의 Android Surface에 표시한다. Omarchy 원본 Arch/Hyprland와 기능이 모두 동등한 제품은 아니다.
Android 앱은 원래 Android 창에서 열리며 Linux 앱마다 별도 Android 최상위 창을 만드는 브리지는 없다.

| 남은 범위 | 현재 상태 |
| --- | --- |
| Linux 앱 호환성 | Mousepad·Thunar·foot 등 Wayland 앱. Linux GUI 브라우저·VS Code 미포함, Xwayland 비활성 |
| 런처·overview | 고정 Linux 목록·동적 Android 목록. `.desktop` 자동 검색·시각적 overview/dock 미구현 |
| Android 연결 | Linux 알림·오디오 브리지 미구현. Android 알림은 세션 상태만 표시 |
| 실행·복구 | PRoot 사용. 대체 namespace backend·절전 freeze/thaw·프로세스 종료 후 메모리 복원 미구현 |
| 성능 | CPU shm 복사. GPU 경로와 물리 프레임률·입력 지연·전력 목표 미검증 |
| 개발 환경 | Bash·Git·Python·Neovim 포함. Bun·Android Chrome localhost 흐름 미검증 |

전체 VM 시험이 통과하더라도 위 미구현 기능과 Y900 실기기 수락을 대체하지 않는다.
상세 구조는 [구현 범위](runtime-implementation.md), 실제 사용 순서는 [빠른 시작](desktop-quickstart-ko.md)을 참고한다.
