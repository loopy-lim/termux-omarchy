# Linux 앱·터치패드 확장 검증

이 문서는 2026-10-05~06의 브라우저·코드 편집기·입력 확장을 기존 데스크톱 납품과 구분한다. 이전 APK·14/14 및 추가 raw 탭 실패 영수증은 그대로 보존한다.

현재 새 후보는 WebKitGTK 2.48.1-r1의 GTK3 Loopy Browser, Geany 2.0-r0, 기존 Mousepad·Thunar·foot·개발 도구를 포함한다. Firefox 후보는 아래에 별도 보존한다. `Other Linux apps`는 안전한 argv로 실행할 수 있는 시스템 `.desktop` 목록을 검색한다. 기존 HOME의 수정된 설정과 프로젝트는 보존한다. [앱 선택·고정 출처](research/linux-browser-code-editor.md).

## 최종 납품 APK

현재 APK는 WebKitGTK 2.48.1-r1·PyGObject 3.52.3-r1로 실제 HTML·JavaScript·네트워크·저장 기능을 실행한다. 제품 화면은 [browser.py](../guest/desktop/usr/local/lib/loopy/browser.py)의 188행 GTK 창이며 주소·검색, 뒤/앞 이동, 새로고침, 탭과 단축키를 관리한다. `Ctrl+L/T/W/R`, `Ctrl+Tab`, `Alt+Left/Right`를 GTK 기본 WebView 처리보다 먼저 다룬다. 주소를 확정하면 페이지로 포커스를 옮기고 탭 변경 후 주소·제목을 갱신한다. 탭 제목은 최소 14글자 폭으로 표시해 `…`만 남던 화면을 수정했다. 쿠키·웹 데이터는 HOME/XDG의 `loopy-browser` 경로에 저장하고 기존 Firefox·MiniBrowser 프로필을 삭제하지 않는다.

호스트 시험 **140/140**, 코드 파일 **195개·최대 499행**이다. 네이티브 시험 36개는 변경하지 않은 동일 컴포넌트의 결과이며 현재 APK의 포함 해시도 대조했다. DNS 수정 직후 9605 APK의 [HTTPS 단독 시험](validation/2026-10-06-dns-placeholder-https-vm/receipt.json) **1/1**은 보존하며, [최종 81d5 APK 전체 VM 시험](validation/2026-10-06-desktop-apps-ui-delivery-vm/receipt.json)은 **19/19**다. 이전 d318 APK 전체 시험은 **18/19**였고 HTTPS만 실패했다. 이 기록은 [이전 WebKit 영수증](validation/2026-10-06-webkit-desktop-final-vm/receipt.json)에 보존한다.

| 현재 빌드 입력 | SHA-256 |
| --- | --- |
| 앱 APK | `81d5e4d50e870c825a581c08c3e34df8b8a6ccde542f2c4af954c2b94488bccd` |
| 테스트 APK | `eebd89d0a8e78f828f9b3eb389ef7ef0fe54e1d4126ab8e03fe0fa4fb3135006` |
| rootfs | `541b34426b87c526f9b4795bc7aec6f7450844bb78951fb58f3f615d6ce9e552` |
| 수정 PRoot | `e026656c33fe7fb3734fa2a9bac8a34f5acba7528328374a8c3e216df60a5077` |
| 짝 loader | `0738d73bc8e3c0b22f9b59a019a29087195453dcb0b73ced979b00fafe1caefe` |

앱은 325,051,509바이트, rootfs는 324,279,867바이트·257패키지이며 설치 파일 총량은 823,159,749바이트·11,207개 항목이다. [빌드 입력 68개와 포함 파일 5개 대조](validation/2026-10-06-desktop-apps-ui-delivery-vm/build-integrity.json)는 통과했다.

HTTPS 실패는 PRoot가 파일 바인드 대상에 생성한 빈 `mode 0000` 파일을 사용자 DNS 설정으로 오인한 문제였다. 그 표식만 자동 DNS 대상으로 구분하고 Android 활성 네트워크의 DNS를 연결한다. 파일 삭제·수정, 공개 DNS fallback, TLS 검증 해제는 추가하지 않았다. 읽을 수 있는 빈 파일·내용 있는 제한 파일·symlink 등 사용자 설정은 보존한다. [회귀 진단](validation/2026-10-06-dns-placeholder-https-vm/dns-regression.json)과 호스트 RED→GREEN·실제 HTTPS 재시험을 기록했다.

원본 MiniBrowser의 [일반 앱 진단](validation/2026-10-06-webkit-browser-key-delivery-vm/receipt.json)에서는 HTTP·JavaScript·폼 제출이 실행됐지만 첫 `l`의 keydown이 DOM에 도달하지 않았다. Android 라우터는 실제 evdev down/up을 모두 출력했고 DOM에는 keyup만 나타났으며, DOM 포커스 완료도 확인했다. WebKit GTK3의 비동기 미처리 키 재전달 flag와 주소창 포커스 변경을 가능한 원인으로 좁혔고, 이를 확정된 내부 원인으로 표현하지 않는다. 새 GTK 창은 주소창 단축키를 페이지로 넘기기 전에 처리한다. 실제 회귀 시험은 처음 글자부터 완전한 제출값·Surface 변화·탭 닫은 뒤 기존 페이지 보존을 확인한다.

브라우저 CPU 정책은 래퍼의 Wayland 선택과 WebKit compositing·DMA-buf 비활성, `HardwareAccelerationPolicy.NEVER`다. 추가 Linux 브라우저 sandbox는 PRoot 아래에서 제공하지 않으며 WebKit context에 이를 명시한다. Android 앱 UID·SELinux·상속 seccomp가 격리 경계다. `run-as`의 필터 없는 진단을 일반 앱 보안·실기기 합격으로 대신하지 않는다. 최종 일반 앱 검사에서 UID 네 값은 10224이고 브라우저 parent·WebKit worker는 같은 `untrusted_app` label이었다. worker의 `Seccomp=2`·필터 1개는 parent와 동일하며 추가 Linux 필터는 없고 `NoNewPrivs=0`이었다. 해당 worker label은 실제로 읽혔으며, 다른 진단에서 읽기가 거부된 값은 null로 남긴다.

실제 GUI 회귀 시험은 HTTP·JavaScript·첫 글자부터 완전한 폼 제출·Surface 변화·Ctrl+T/Ctrl+W 뒤 기존 페이지 보존, 외부 HTTPS의 Example Domain 창, Geany 공유 파일 수정·저장·Linux Python 실행을 확인했다. 입력 시험은 raw POSITION generic 탭으로 Thunar 폴더를 이동하고 captured 상대 이동·두 손가락 접점으로 실제 브라우저를 스크롤했다. 이는 합성 VM 입력이며 실제 HID나 pointer-capture grant의 증거가 아니다.

[최종 설치 APK](../build/deliverables/LoopyDesktop-2026-10-06-desktop-apps-arm64.apk)는 위 앱 SHA·바이트와 동일하다. [전달 기록](validation/2026-10-06-desktop-apps-ui-delivery-vm/delivery.json), [서명 확인](validation/2026-10-06-desktop-apps-ui-delivery-vm/signature.txt), [호스트 시험](validation/2026-10-06-desktop-apps-ui-delivery-vm/host-tests.txt)을 함께 보존한다.

오른쪽 위 상태 표시·트레이는 제거했고 왼쪽 작업공간만 남겼다. 전체 화면 포커스 복귀 시 Android 시스템 바를 다시 숨긴다. 기존 수정한 Sway 설정은 보존하고 알려진 기본 설정 해시만 갱신한다.

![최종 APK의 실제 Linux 브라우저·Geany·Thunar](validation/2026-10-06-desktop-apps-ui-delivery-vm/desktop-apps-screen.png)

[최종 화면의 창·PID·UID·SELinux 확인](validation/2026-10-06-desktop-apps-ui-delivery-vm/gui-receipt.json)은 실제 GUI를 기록한다. Android 일반 앱의 Sway가 자식 앱을 실행했으며, 진단 IPC 요청을 보낸 run-as 프로세스 자체를 일반 앱 수락으로 계산하지 않는다. 화면용 Geany는 `--no-session`으로 삭제한 시험 파일 복원 경고를 피했고 HOME·프로필을 지우지 않았다. 실제 저장·실행 시험은 기본 제품 런처를 사용했다.

탭 제목 폭을 수정하기 전 9605 APK의 [19/19](validation/2026-10-06-desktop-apps-delivery-vm/receipt.json)도 별도 보존한다. 해당 APK와 화면을 최신 납품본으로 대신 쓰지 않는다.

## 이전 Firefox 후보

아래 SHA·16/19는 이전 후보의 기록이다. 당시 호스트 시험 126개가 통과했고 변경하지 않은 Wayland host의 네이티브 시험 36개가 통과했다. 코드 파일 188개는 모두 500행 이하이며 최대 489행이다. 서명과 APK에 포함한 rootfs·네이티브 파일 해시를 확인했다.

| 이전 Firefox 빌드 입력 | SHA-256 |
| --- | --- |
| 앱 APK | `e1b02c3a3d67047d1f97216608cc3115af127be4645afe35ede1fea3bec73c29` |
| 테스트 APK | `a40c71c1197789ba41c1a5a288429e55832163407c9b36c620ed713365cf9f9c` |
| rootfs | `404c3e7f6a0830019ce682321acdb959b54b7343b656190b5c661bfa72e5c228` |
| 수정 PRoot | `e026656c33fe7fb3734fa2a9bac8a34f5acba7528328374a8c3e216df60a5077` |
| 같은 빌드의 loader | `0738d73bc8e3c0b22f9b59a019a29087195453dcb0b73ced979b00fafe1caefe` |

[이전 Firefox 브라우저 단독 VM](validation/2026-10-06-desktop-browser-register-fix/receipt.json)은 실패했다. 일반 앱 UID 10224·`untrusted_app`에서 정상 Firefox 창이 90초 안에 나타나지 않았다. 별도 headless 진단에서는 실제 HTML·JavaScript·폰트가 PNG로 출력됐지만 이것은 GUI 브라우저 합격이 아니다. Safe Mode 초기 창·빈 브라우저 chrome 표시도 웹페이지 조작 성공으로 처리하지 않는다.

[이전 Firefox 전체 VM](validation/2026-10-06-desktop-apps-current-vm/receipt.json)은 **16/19**다. 데스크톱 기본 14개, Geany 공유 파일 저장·Linux Python 실행, raw 터치패드 탭의 Thunar 폴더 이동이 통과했다. Firefox 로컬 웹페이지 입력·외부 HTTPS·브라우저 터치패드 스크롤 세 검사는 정상 창이 나타나지 않아 실패했다. 모두 일반 앱 UID 10224·`untrusted_app`에서 실행했다. 이 후보에서는 합성 captured 콜백의 실제 브라우저 스크롤 성공이 없었다.

이 빌드는 [부분 검증 APK](../build/deliverables/LoopyDesktop-2026-10-06-apps-preview-arm64.apk)로 별도 보존한다. 크기는 355,542,133바이트이며 위 앱 해시와 동일하다. [전달 기록](validation/2026-10-06-desktop-apps-current-vm/delivery.json), [입력·포함 파일 확인](validation/2026-10-06-desktop-apps-current-vm/build-integrity.json), [서명 확인](validation/2026-10-06-desktop-apps-current-vm/signature.txt)을 함께 보존한다.

PRoot의 tagged SIGSYS 인자 전달·짝 loader·ARM64 x7 보존을 수정했다. [레지스터 A/B probe](validation/2026-10-06-proot-register-return-o2fhz9b8/receipt.json)는 원본 1/4, 이전 수정 3/4, 현재 수정 4/4다. 이 probe는 `run-as` 진단이고 일반 앱 브라우저 GUI의 성공 증거는 아니다. 대응 소스와 재링크 자료는 `build/deliverables/LoopyDesktop-2026-10-06-proot-source-registers.tar.gz`에 보존한다.

오른쪽 위 상태 표시·트레이는 제거했고 왼쪽 작업공간만 남겼다. 전체 화면 포커스 복귀 시 Android 시스템 바를 다시 숨긴다. 기존 수정한 Sway 설정은 보존하고 알려진 기본 설정 해시만 갱신한다.

![이전 부분 검증 APK의 실제 Geany와 Thunar](validation/2026-10-06-desktop-apps-current-vm/desktop-code-files-screen.png)

이 화면은 부분 검증 APK의 실제 앱이다. [창·프로세스 확인](validation/2026-10-06-desktop-apps-current-vm/gui-receipt.json)에서 각 PID의 Android UID 네 값과 `ps -AZ`의 `untrusted_app`을 대조했다. `run-as`에서는 peer의 `attr/current` 읽기가 거부되어 이를 성공으로 기록하지 않았다.

## 실행 시험의 의미

- 브라우저: 실제 Linux HTTP 서버가 전달한 HTML·JavaScript의 ready 요청, 키보드 입력·폼 제출, Loopy Browser Wayland 창/PID/Android UID와 Surface 픽셀 변화.
- 코드: Geany GUI에서 공유 파일을 열고 수정·저장한 실제 내용, Linux Python으로 저장 코드 실행, Wayland 창/PID/Android UID와 픽셀 변화.
- 입력: Android가 generic motion으로 전달하는 raw POSITION 접점의 탭과 실제 Thunar 폴더 이동. 캡처 callback의 SOURCE_MOUSE_RELATIVE/AXIS_X/Y, 원시 두 손가락 접점 → 실제 Linux 브라우저 scroll·Surface 변화.
- 정책: 분류된 스크롤과 원시 접점 중복 방지, 마우스 down/up·버튼 이벤트 균형, 취소·포커스 상실과 기기 분리 시 해제, 키보드 소유권과 세션 유지.

캡처 callback 직접 시험은 Android의 실제 pointer-capture grant를 증명하지 않는다. VM framework 주입도 실제 Y900 입력이 아니다. 접근성 서비스 API 지원과 실제 기기의 원시 접점·예약 키 제공도 다른 증거다. Y900 물리 키보드·터치패드, 성능과 절전 복귀는 [별도 실기기 점검](y900-test-checklist.md)에 남긴다.

## 남은 경계

Sway를 하나의 Android Surface로 출력하는 CPU shm 경로다. GPU, X11 전용 앱, Linux 오디오·알림 브리지와 Omarchy 원본 Arch/Hyprland의 모든 기능은 구현 완료로 표현하지 않는다. Geany는 GUI 코드 편집기이며 VS Code의 확장 생태계를 제공하지 않는다. 로컬 HTTP 브라우저 시험은 외부 인터넷, 미디어·DRM·모든 사이트 호환성의 합격이 아니다. 브라우저 보안 격리 상태는 실제 실행 결과와 별도로 확인한다.
