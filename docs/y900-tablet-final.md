# Y900 13 현재 구현과 검증

대상은 Lenovo TB522FU, ADB serial `Y900`, Android 패키지 `dev.loopy.desktop`입니다. 현재 실제 세션은 Android Surface → Loopy Wayland 호스트 → PRoot의 Arch ARM64·Hyprland·Omarchy입니다. Termux 설치 없이 실행하며, Android OS를 교체한 결과는 아닙니다. 아래 날짜별 기록은 당시 APK의 이력입니다. 최신 상태는 먼저 나오는 기록을 기준으로 봅니다.

## 2026-10-08 · 전체 출력 GPU·셸·SSH 후속 검증

[후속 실제 기록](validation/2026-10-08-tablet-stage-progress.md)을 기준으로 진행 중입니다. 제품 `1148c45e…`를 GPU로 새로 시작한 출력은 1920×1269·150%에서 약 17.57fps였고 SSH 접속·잘못된 서버 키 거부·서버 종료 및 재접속을 통과했습니다. 임시 APK `ccb742d9…`에서 Linux stderr 수집을 연결해 공통 구간의 6단계를 모두 측정했으며 약 16.79fps였습니다. 계측 범위가 표시 간격 전체를 설명하지 못해 GTK 처리와 컴포지터 업로드를 추가 조사합니다. 현재는 [GTK 아이콘 경로 수정본 `7c14004c…`](../build/deliverables/LoopyDesktop-2026-10-08-gtk-icon-data-arm64/README.md)으로 교체해 기본 PDF 실행·정리·복원을 확인했습니다. 같은 APK에서 Wi-Fi 설정 열기·Notion 앱/웹 실행·Linux 복귀와 DNS·HTTPS 6개 검사를 통과했습니다. Wi-Fi 재접속과 Notion 문서 편집은 별도입니다. 이전 제품에서 실제 앱 권한의 셸 반복 실행 8회에서 미회수 자식 0개와 SSH 네 단계를 확인했습니다. 기본/Mac 셸의 별도 공개 HOME 비교도 통과했지만 실제 사용자 rc와 화면 지연 시험은 아닙니다. 아래 소프트웨어 복구 상태는 당시 기록입니다. 60/144fps와 전체 기능 수락은 미완료입니다.

## 이전 기록 · 2026-10-08 GPU 복구 후 입력 유지

당시 설치본은 `1148c45ed672e0a04904bc48463045528ed9bde20c1d8f4700f93b311ed0798c`입니다. [정확한 APK·보존한 입력·실기기 기록](../build/deliverables/LoopyDesktop-2026-10-08-recovery-input-arm64/README.md)에 연결했습니다. 이전 `92de…`와 달라진 빌드 입력은 `session_actions.py` 하나이며 JNI·VirGL·watchdog 후보는 같습니다. UID 10330·HOME·115개 설정·기존 접근성 서비스·한도 1024를 보존했고, 마이크 권한은 거부 상태를 유지했습니다.

실제 앱의 GPU 서버를 종료한 시험에서 컴포지터와 입력 worker가 같은 세션 토큰, 1920×1269·150%·120Hz로 복구됐습니다. 이전 세대의 유효한 명령은 실행하지 않고 폐기했으며, 오류 화면을 열지 않아 전체 화면과 입력 우선권을 유지했습니다. 새 명령은 처리됐습니다. 이 시험 뒤의 현재 세션은 소프트웨어 복구 상태입니다.

복구 후 합성 UHID→Foot 입력 30/30이 도착했고 p50 1.505ms·p95 4.099ms였습니다. 일반/Lenovo 식별 UHID Esc와 Alt+Tab·Alt+Shift+Tab은 Linux에 전달되며 Android 전체 화면과 입력 활성 상태를 유지했습니다. 물리 스위치부터 화면 표시까지의 측정이나 사람이 누른 최종 Lenovo 키 확인과는 구분합니다. [당시 APK의 숫자 조합 30개](../build/diagnostics/y900-gpu-desktop-20261008/numeric-full30-1148-02.json)는 합성 UHID로 Meta+1…0 작업공간 전환·Meta+Shift+1…0 창 보내기·Alt+1…0 tmux 전환을 모두 통과했습니다. 원래 작업공간·포커스·tmux 설정을 보존했고 입력 장치를 회수했습니다. 종료된 tmux PID는 Z 상태로 남아 있어 런타임의 자식 프로세스 정리를 별도로 수정합니다. 장시간 안정성은 후속 검증 중입니다.

이전 [92de GPU 기본 경로 후보](../build/deliverables/LoopyDesktop-2026-10-08-gpu-desktop-arm64/README.md)는 실제 앱 ManagedServer와 Adreno GPU 앱·컴포지터를 함께 실행했고 9개 기능 검사를 통과했습니다. 전체 화면에서 변화하는 GPU 장면의 Android 표시율은 12초 약 16.90 FPS였습니다. 작은 출력의 비교는 약 55.04/59.08 FPS이며 사용자 배율·원래 출력은 복원했습니다. 지속 60 FPS·144 FPS 수락 결과가 아니고, 해당 9개 검사를 현재 1148 설치본의 검사로 합치지 않습니다.

현재 GPU readback·복사·프레임 전송·Android 업로드/표시의 구간별 측정, Linux Chromium 샌드박스, 종료된 자식 프로세스 누적 문제를 조사하고 있습니다. 전체 원본 앱·서비스·마이크·카메라·Bluetooth·외부 원격 서버 인증·네이티브 OS 검증도 미완료입니다.

## 이전 기록 · 2026-10-08 입력 접수와 원격 앱 안정화

당시 설치본은 `22e57dc33b83652bf1c2f8610ab1f9ff12a971957ee71566fdc00077fc7e9c8f`입니다. [APK·보존한 빌드 입력](../build/deliverables/LoopyDesktop-2026-10-08-input-remote-stable-arm64/README.md), [현재 체크포인트](../build/diagnostics/y900-performance-20261007/tablet-input-remote-stable-checkpoint.json), [9개 실기기 시험](../build/diagnostics/y900-performance-20261007/input-remote-stable-device-suite.json)에 연결했습니다. 이전 APK 결과와 합치지 않습니다.

키보드·마우스 이벤트 접수가 화면 출력의 `eglSwapBuffers`와 같은 잠금을 기다리던 경로를 수정했습니다. 연결 토큰은 atomic으로 읽고, 출력 실패나 화면 교체 전의 대기 입력은 새 연결에 재생되지 않도록 연결 세대를 확인합니다. 출력이 막힌 상태의 동시 접수, 실패 후 화면 교체, 오래된 detach, headless, 큐 넘침·마우스 이동 합치기를 검증했습니다. 호스트 통합 110개·패키징 12개와 격리한 ARM JNI 후보의 회귀 6개가 통과했습니다. 별도 전체 Rust 66개와 Android 입력 경계 26개도 통과했으며 기존 범위 밖 Clippy 경고 9개는 남겼습니다. 실제 화면 표시 지연 전체가 해결됐다는 뜻은 아닙니다.

원격 Remmina는 GTK 이미지 로더가 Android에서 생성할 수 없는 namespace를 요구해 아이콘 표시 중 종료됐습니다. 서명된 공개 아이콘 원본 826개로 검증한 GTK 원시 캐시를 생성해 원격 자식 프로세스에만 제공합니다. 사용자 테마·HOME와 일반 이미지 디코더 정책을 보존합니다. 현재 APK에 설치된 캐시만으로 실제 VNC 클라이언트가 RFB 3.8 연결과 공개 화면 307,200바이트 수신을 완료했고 계속 실행됐습니다. GTK 아이콘 abort와 Glycin/bwrap 오류는 재현되지 않았습니다. 일부 비치명적 GTK/GDK·secret plugin 경고는 남으며, 생성한 프로필은 비밀번호 저장을 끕니다. 외부 서버 인증·실제 원격 지연을 수락한 결과는 아닙니다.

| 현재 설치본에서 확인한 항목 | 결과와 범위 |
| --- | --- |
| 터미널 입력 | 소유한 UHID 테스트 입력 30/30 도착. 중앙값 1.479ms, p95 2.194ms, 최대 17.093ms. 커널 주입부터 Foot PTY 수신까지이며 물리 스위치·화면 표시 제외 |
| 마우스 | 소유한 HID 이동·버튼 누름/해제 모두 수신. Android 포인터 TYPE_NULL, Linux 커서 픽셀 표시 확인 |
| Esc·Alt+Tab | 일반/Lenovo 식별 HID Esc 전달, Android 컨트롤이 열리지 않음. Alt+Tab·Alt+Shift+Tab은 Linux 창 전환 |
| 소리 | 실제 PipeWire/Pulse `paplay`부터 Android AudioTrack 스피커 route·재생 프레임 확인. 사람이 들은 확인·마이크·Bluetooth 출력은 별도 |
| Wi-Fi·DNS | 원본 메뉴 세 경로에서 Android Wi-Fi 설정 열기. Linux DNS/TLS 통과, example.com 200·Notion Python 요청 403 |
| Notion·Android 앱 | Notion Android 앱·Android Chrome 웹 경로 실행 후 같은 Linux 세션으로 복귀. 로그인·문서 편집은 미검증 |
| 클립보드 | Android↔wl-paste/wl-copy 테스트 왕복, 원래 ClipData를 기기 메모리에서 복원 |
| 원격 | 설치된 Remmina와 캐시로 실제 로컬 VNC 연결·화면 데이터 수신. 외부 SSH/RDP/VNC 인증은 미검증 |
| 화면 | 실제 모니터 보고 1920×1269·150%·120Hz. 정적 Foot 위 독립 커서 출력 약 112.13fps. 전체 Linux 지속 FPS 결과가 아님 |

업데이트와 이후 시험에서 UID 10330, 기존 HOME·환경 설정, Omarchy 설정 113개와 zsh/tmux 두 파일, 한도 1024를 보존했습니다. 다른 접근성 서비스도 유지했고 이미 허용된 Loopy 입력 서비스만 재연결했습니다. 최종 전체 화면·입력 연결·구성 오류 없음과 진단 포워드 회수를 [마지막 상태](../build/diagnostics/y900-performance-20261007/input-remote-stable-final-state.json)에서 확인했습니다. 1024개 동시 부하나 장시간 안정성 시험은 아닙니다.

GPU는 Android 출력과 Linux 게스트를 구분합니다. Android 출력은 실제 Adreno 830 GLES입니다. 이전 `f144…`의 두 동시 GLES3 픽셀 시험도 Adreno를 확인했지만, 실제 Wayland Gtk.GLArea는 GL context 생성에 실패했고 별도 실행에서는 VTEST 연결 상실로 컴포지터가 반복 종료됐습니다. 따라서 현재 제품의 Linux 게스트 기본 세션은 소프트웨어를 유지하며 작은 픽셀 시험만으로 GPU에 승격하지 않습니다. GPU 실패 시 한 번만 소프트웨어로 재시도하는 별도 watchdog 소스 후보는 호스트 검사까지 통과했으나 ARM 빌드·패키징 전이고, 현재 rootfs watchdog은 바꾸지 않았습니다.

남은 작업은 실제 Linux GPU 앱 창·지속 60/144fps·물리 입력부터 화면까지의 지연, Linux Chromium의 정상 샌드박스, 외부 원격 서버 인증, 마이크·카메라·Bluetooth·절전/회전/물리 장치 재연결입니다. 기존 JNI refresh/detach/shutdown은 렌더링이나 worker 종료를 기다릴 수 있습니다. 입력 접수 수정이 이 수명 관리 대기까지 없앤 것은 아닙니다. 전체 Omarchy 지원은 계속 진행 중입니다.

## 이전 기록 · 2026-10-08 Android 연동과 입력 재검증

해당 시험 설치본은 `8a3236e436d20037e3d32aaedfaf0b2a298ed574f11cfbffab1d9e672f0bd721`입니다. [검증 체크포인트](../build/diagnostics/y900-performance-20261007/tablet-integration-checkpoint.json)에 정확한 설치본과 증거를 기록했습니다. 관련 호스트 검사 49개, SDK 빌드, 데이터 보존 업데이트가 통과했습니다. UID·두 HOME 설정·Omarchy 설정 108개·프로세스 한도 1024를 유지했습니다.

- **입력 연결:** 업데이트 후 접근성이 설정에만 켜져 있고 실제로는 연결되지 않는 문제를 확인했습니다. 앱을 먼저 실행한 뒤, 이미 허용된 Loopy 서비스만 다시 연결하고 실제 연결을 확인하는 업데이트 절차로 바꿨습니다. 다른 접근성 서비스의 설정은 보존했습니다. 앱 자체에 새 시스템 권한을 부여하지 않았습니다.
- **Esc와 Alt+Tab:** 실제 USB HID 경로로 일반/Lenovo 식별 Esc와 Alt+Tab·Alt+Shift+Tab을 검증했습니다. Esc는 Linux로 전달되고 상단 Android 컨트롤을 띄우지 않았으며 창 전환은 Linux 안에 머물렀습니다. 입력 서비스를 잠시 끈 시험에서도 Lenovo 식별 Esc가 전달됐고 일반 Android Back은 컨트롤을 열었습니다. 별도 KeyBridge가 활성화된 상태의 일반 USB Esc는 서비스가 꺼졌을 때 전달되지 않아, 이 경우까지 보장하지 않습니다. 실제 Lenovo 키보드의 Esc는 이전 `49a8…` 설치본에서 사용자가 확인했습니다.
- **커서:** Linux 화면의 Android 포인터를 숨겼습니다. 일반 마우스는 View로, 원시 트랙패드 접점은 접근성으로 전달해 커서 모양 갱신과 입력을 함께 유지합니다. 소유한 HID 마우스 시험에서 이동·클릭 누름/해제와 시스템 포인터 TYPE_NULL을 확인했습니다. 현재 APK의 전용 빈 창에서 Linux 커서 픽셀 425개도 확인했습니다. 정적 화면 위 합성 커서만 약 118fps였으며 전체 Linux 화면의 성능 수치는 아닙니다. 물리 트랙패드의 최종 사용자 수락은 별도입니다.
- **Wi-Fi와 DNS:** Omarchy 상단 패널의 open/toggle 및 shell summon 세 경로가 실제 Android Wi-Fi 설정을 열었습니다. Linux에서 example.com·www.notion.so DNS 조회와 TLS 연결이 됐습니다. example.com은 HTTP 200, Notion의 Python 요청은 HTTP 403이므로 후자를 웹앱 로그인 성공으로 해석하지 않습니다. Wi-Fi·Private DNS 정책의 주체는 Android이며 Linux NetworkManager를 실행한 결과가 아닙니다.
- **Notion·Android 앱:** Omarchy 앱 검색에 설치된 Android 앱과 `Notion Web · Android browser`를 게시했습니다. 앱 항목은 Notion Android 앱으로, 웹 항목은 Android Chrome으로 열립니다. Lenovo의 해당 앱 실행 확인을 허용했습니다. 각 앱에서 돌아와도 같은 Hyprland 프로세스와 전체 화면·입력 연결을 유지했습니다. Chrome의 공개 Notion 페이지가 로드 완료 상태인 것까지 확인했으며 로그인된 워크스페이스 사용은 확인하지 않았습니다. Linux Chromium으로 웹앱을 실행한 결과는 아닙니다.
- **클립보드:** 현재 설치본에서 테스트 문자열을 Android → 실제 wl-paste, 실제 wl-copy → Android로 왕복 검증했습니다. 이전 ClipData는 기기 메모리에만 유지하고 시험 후 복원했습니다. 초기 진단 스크립트의 wl-copy 출력 파이프 대기가 시간 초과의 원인이었고 앱 구현 오류는 아니었습니다.

실제 세션의 간단한 Foot 창 표시가 이전 `8ed…` 비교에서 0.517초 → 0.213초로 줄었습니다. 이 수치는 이번 설치본의 새 입력 지연 측정이 아닙니다. 전체 Linux GPU 활성화, 지속 60/144fps, Linux Chromium 샌드박스, Android 실제 소리 출력은 남아 있습니다. 원격 연결·실물 장치 분리/재연결·Notion 로그인과 문서 편집·업로드는 이번 짧은 시험에 포함하지 않았습니다.

### 사용과 업데이트

Omarchy 앱 검색에서 `Notion · Android` 또는 `Notion Web · Android browser`를 선택합니다. Linux 세션은 Android 앱을 사용하는 동안 유지되며 Loopy 아이콘/세션 알림으로 돌아올 수 있습니다. 생성한 Android 앱 목록은 앱 내부 `wayland/android-apps/applications`에 있으므로 사용자 HOME의 `.desktop` 파일을 덮어쓰지 않습니다.

ADB 업데이트 시에는 저장을 확인하고 `install -r`을 사용합니다. 현재 검증된 [업데이트 스크립트](../build/diagnostics/y900-performance-20261007/update-single-cursor.py)는 해당 APK와 직전 설치본에만 적용되는 기록입니다. 후속 업데이트도 **Activity 실행 후** 이미 허용된 입력 서비스의 실제 연결을 확인해야 합니다. 단순히 enabled_accessibility_services에 이름이 있다는 이유로 연결 완료로 판정하지 않습니다.

## 2026-10-07 후속 · 마우스 지연과 60/144fps 목표

사용자는 프레임 자체보다 포인터 추종과 클릭 후 반응이 모두 느리다고 정정했고, 최소 60fps·목표 144fps를 요청했습니다. 실제 Y900의 지원 모드는 30/60/90/120/144Hz이며 관찰 당시 Android는 120Hz, 기존 Wayland 출력은 60Hz였습니다.

기존 설치본 `8843feae…`에서 소유한 60Hz 터미널 작업을 SurfaceFlinger의 실제 표시 시각으로 관찰하니 23.51fps·프레임 간격 p95 50.00ms, Hyprland CPU 376.9%(한 코어=100%)였습니다. 이는 그 시험의 결과이며 일반 화면 전체의 fps로 일반화하지 않습니다. 애니메이션을 끈 비교는 개선을 입증하지 못했고 원래 설정으로 복원했습니다. NativeBridge로 넣은 합성 포인터가 Hyprland 상태 조회에 나타난 시간의 중앙값은 52.73ms였습니다. 이 수치는 JDWP·상태 조회 대기가 포함된 상한이며 물리 마우스→픽셀 지연 측정은 아닙니다. [원자료](../build/diagnostics/y900-performance-20261007/progress.json).

새 후보는 부모 Wayland 호스트에 커서 surface 합성을 구현해, Linux가 새 데스크톱 프레임을 보내지 않아도 커서가 움직입니다. 초점·enter serial·surface role·핫스폿·숨김·파괴를 처리합니다. 입력 대기를 condition variable로 깨우고 Android의 입력 묶음을 줄이며, 앱 창에서 최대 144Hz를 요청한 후 **실제로 선택된** 주사율을 Wayland 출력과 나노초 단위 프레임 간격에 전달합니다. 기존 Omarchy 태블릿 프로필의 소프트웨어 커서 강제값 1은 이 후보에서 자동값 2로 바뀝니다.

네이티브 60개 검사, 관련 Java/Lua 9개 검사와 ARM64 NDK·Android SDK 빌드가 통과했습니다. 사용자가 저장과 재시작을 승인한 뒤 새 APK `9b3d0b676e229a4f9faf7d2adfb2e8928d59825936dfd2cb8141e3e98daa039d`를 물리 기기에 업데이트했습니다. UID·기존 HOME와 환경설정·Omarchy 설정 99개·프로세스 한도 1024가 유지됐습니다. 같은 합성 입력 조회 시험의 중앙값은 6.56ms로 줄었지만 물리 입력부터 픽셀까지의 지연은 아닙니다. 정지한 전용 Foot 위에서 합성 포인터를 움직일 때 SurfaceFlinger 표시 속도는 117.43fps였습니다. 다만 커서 영역 픽셀 검증이 실패했고 실제 커서 이미지가 비어 있어 표시 문제는 아직 해결되지 않았습니다. Hyprland의 커서 전용 offscreen 렌더가 SHM 복사를 건너뛰는 경로를 찾아 수정 후보를 빌드 중입니다. Linux GPU 렌더링 오류, 실제 포인터·클릭 지연, 전체 Linux 화면의 지속 60/144fps 달성은 미완료입니다.

## 2026-10-07 후속 · 편집기 종료와 프로세스 한도

최신 상태는 [편집기·정책 검증 기록](validation/2026-10-06-omarchy/checkpoint-y900-editor-policy.json)에 있습니다. 설치 APK는 아래 `8843feae…` 그대로이며 Omarchy 세션이 실행 중입니다. 사용자 요청에 따라 기기 공통 자식 프로세스 한도를 32 → 128 → **1024**로 조정하고 `device_config`와 ActivityManager 양쪽의 반영을 확인했습니다. 1024개 동시 실행 부하를 검증했다는 뜻은 아닙니다. 기본값 복구 명령은 기록에 보존했습니다.

실제 `vi` 시작 뒤 Android가 `Trimming phantom processes`로 PRoot·Hyprland·Quickshell·Foot을 함께 종료한 로그를 확보했습니다. 기존 Neovim 설정을 백업하고 Lazy 설치·업데이트 확인, Mason 도구 설치, Treesitter 문법 분석기 설치의 동시 작업 수를 각각 1로 제한했습니다. 모든 플러그인 사양은 유지했습니다. 원본 LazyVim 설정으로 두 편집기를 열어 시험 파일의 수정·저장을 확인했고, 두 번째 실행에서 네 제한의 적용과 Hyprland 생존을 확인했습니다. 전체 언어 서버·문법 분석기 설치 완료나 장시간 안정성 수락은 별도입니다.

포인터는 사용자 확인상 이동·클릭이 전달되지만 보이지 않는 문제입니다. Android 부모 compositor가 별도 커서 surface를 그리지 않아 `cursor.no_hardware_cursors=1`을 당시 기기 설정과 태블릿 프로필에 반영했습니다. 새 커서 분리 후보에서는 부모 호스트가 커서를 처리하도록 변경했습니다. 현재 세션에서 옵션 1을 확인했으나 반복 화면 비교는 아직 통과하지 않아 **표시 문제 해결로 판정하지 않았습니다**. 일시적인 렌더링 진단 설정과 JDWP 포워드는 복구·제거했습니다.

화면은 저장값 150%와 실제 Hyprland 1.5배가 일치합니다. Arch의 GLES2·GLES3 시험은 `virgl (Adreno (TM) 830)`과 실제 픽셀 값을 확인했지만, 실제 Hyprland 창 그리기는 VirGL 셰이더 링크 실패로 종료됐습니다. 제품 세션은 소프트웨어 렌더링을 유지합니다. 아래 재연결 종료 상태와 이전 APK 검증은 각각 당시의 이력입니다.

## 2026-10-07 재연결 · 실제 Omarchy

현재 설치본은 [Omarchy 그림 초기화 수정 후보](../build/deliverables/LoopyDesktop-2026-10-07-omarchy-branding-native-arm64/README.md) `8843feaeaf1c61c1f074fa9071a6deedab91b8fb46fe82a7c1c070a4cfbcc960`입니다. 아래 Android API 수정도 포함합니다. 전체 [재연결 검증 기록](validation/2026-10-06-omarchy/checkpoint-y900-reconnect.json)은 성공·실패와 최종 기기 상태를 함께 기록합니다.

새 [Android 코어 API 호환 후보](../build/deliverables/LoopyDesktop-2026-10-07-android-core-api-arm64/README.md) `f2f80292…`를 Y900 `Y900`에 업데이트했습니다. `Files.writeString`의 실기 NoSuchMethodError와 준비 상태 고정을 재현·수정했고, 호스트 검사 20개와 SDK 빌드를 통과했습니다. 설치 전후 UID 10330과 설정 파일 해시를 확인했습니다. 이후 기존 배포 기본 Sway config 하나만 새 배포 기본값으로 이전됐음을 이전·새 rootfs 해시와 대조했습니다. 사용자가 수정한 user.conf·zsh·tmux·Neovim·Yazi 설정은 그대로입니다.

앱의 실제 문서 선택기로 전체 Omarchy 이미지 `7dcc1b53…`를 설치했고 아카이브 SHA-256 및 핵심 실행 파일 9개를 대조했습니다. 원본 Hyprland·Quickshell은 시작됐으나 기본 한도 32에서 Android가 `Trimming phantom processes`로 부모 프로세스를 종료했습니다. 한도 128 비교에서는 원본 바와 실제 Wayland Foot 화면을 확인했습니다. 이는 완전한 서비스·GPU 수락을 뜻하지 않습니다.

`f2f80292…`에서 현재 프로필의 private PTY zsh 문자 처리 20개 표본은 중앙값 1.884ms·p95 2.067ms, 준비 시간 481.042ms입니다. 빈 프로필 기준 실행은 시간 초과라 비교 개선율을 산출하지 않습니다. 이 측정은 ZLE 내부이며 물리 키→화면 표시 지연이 아닙니다. ADB 가상 Meta+0는 앱에 Meta가 빠진 형태로 도달해 실제 키보드 수락으로 사용할 수 없었습니다. 전용 Foot 관찰은 480초 뒤 종료됐고 물리 마우스 이벤트와 입력 확인 문구가 기록되지 않았습니다. 따라서 물리 클릭·드래그·키보드 단축키는 미확인입니다.

유휴 화면 보호기는 `.config/omarchy/branding/screensaver.txt`가 없어 오류를 반복했습니다. 새·기존 HOME의 누락된 screensaver/about 그림만 원본 logo/icon으로 초기화하고 사용자 파일·심볼릭 링크는 보존하도록 수정했습니다. 중간 후보 `4c4f2927…`의 하드 링크 방식은 실제 Android에서 거부됐고, 최종 후보는 앱에서 쓰는 제한된 native no-replace 이동으로 교체했습니다. 최종 관련 호스트 검사 10개·NDK·SDK 빌드를 통과했고, 실제 앱 UID에서 기존 Omarchy 파일 94개 유지·그림 두 개 추가를 확인했습니다. 원본 ttfx 화면이 표시되고 ADB Esc로 닫히면서 Hyprland와 터미널이 유지됐습니다. 이 종료 확인은 실제 물리 키보드 수락과 구분합니다.

이 재연결 검증 종료 당시 테스트 세션은 제품 메뉴로 종료했습니다. 기기 공통 `max_phantom_processes` 임시 값을 삭제해 원래 유효 한도 32로 복구했고, 한글 입력 설정도 원래 `true`로 복구했습니다. UID 10330과 설치 APK 해시를 다시 대조했으며 진단 파일 세 개는 호스트에 보존한 뒤 기기에서 제거했습니다. 당시 Omarchy 프로필과 설치 이미지·HOME는 유지되고 Linux 앱은 정지 상태였습니다. 이후 사용자가 한도 상향을 승인한 최신 상태는 위 후속 기록을 따릅니다.

실행 자료: [업데이트](../build/diagnostics/y900-reconnect-20261007/core-update.json), [이미지 설치](../build/diagnostics/y900-reconnect-20261007/image-install.json), [기본 정책 종료 원인](../build/diagnostics/y900-reconnect-20261007/omarchy-default-policy-kill.log), [실제 화면](../build/diagnostics/y900-reconnect-20261007/omarchy-128-terminal.png). 아래 이전 날짜별 내용은 당시 APK의 이력입니다.

## 2026-10-07 물리 클릭 후속 수정

사용자가 말한 클릭은 트랙패드를 눌러 딸깍하는 물리 버튼입니다. 원시 손가락 접촉과 마우스 버튼 이벤트를 함께 제품 `TerminalInput`에 전달한 호스트 재현에서, 한 번의 물리 클릭 뒤 손가락을 떼면 탭 클릭이 추가되는 문제가 확인됐습니다. 탭 드래그 중 물리 버튼을 누른 뒤 손가락을 먼저 떼는 경우에도 버튼이 너무 일찍 풀렸습니다. 두 실패 로그를 보존하고 버튼 상태를 수정했습니다.

마우스 이벤트의 물리 버튼 상태를 원시 접촉 상태와 함께 확인해 중복 탭을 억제합니다. 버튼을 누른 채 손가락을 떼거나 다시 접촉해도 누른 상태를 유지하며, 실제 버튼 해제·포커스 반납·장치 분리 때 해제합니다. 클릭·드래그·좌표 유지·입력 캡처·배치 이동·5개 마우스 버튼·장치 분리 관련 호스트 검사 **22개가 통과**했습니다. Android의 [InputDevice 문서](https://developer.android.com/reference/android/view/InputDevice#SOURCE_TOUCHPAD)는 트랙패드 이벤트가 보통 `SOURCE_MOUSE`로 전달된다고 설명합니다. 이번 혼합 이벤트 재현이 Y900의 실제 OEM 이벤트 순서와 같은지는 아직 확인하지 못했습니다.

[새 물리 클릭 APK](../build/deliverables/LoopyDesktop-2026-10-07-y90013-physical-click-arm64.apk)를 SDK Java·DEX 컴파일, 서명·정렬 검사까지 완료했습니다. 정확한 APK, 빌드 입력 보존본, 실패·성공 로그는 [후속 검증 영수증](validation/2026-10-06-y900-tablet-fit/mixed-source-mechanical-input-receipt.json)에 연결됩니다. Y900 `Y900`가 현재 ADB에 없어 **설치와 실제 물리 클릭·드래그·입력 지연 확인은 대기 중**입니다. 아래 2026-10-06 결과와 이전 Omarchy VM 결과는 각각의 APK에 대한 이력입니다.

## 이번 업데이트

[업데이트 APK](../build/deliverables/LoopyDesktop-2026-10-06-y90013-meta-tmux-trackpad-arm64.apk)는 현재 설치된 클립보드·zsh 버전에 다음 수정을 추가합니다. 정확한 해시와 설치 여부는 [이번 영수증](validation/2026-10-06-y900-tablet-fit/final-mechanical-input-receipt.json)을 기준으로 확인합니다.

| 실제 키 | 동작 |
| --- | --- |
| Meta + 1…9 / 0 | Sway 작업공간 1…9 / 10 |
| Meta + Shift + 1…9 / 0 | 현재 창을 작업공간 1…9 / 10으로 이동, 현재 작업공간 유지 |
| Alt + 1…9 / 0 | tmux 창 1…9 / 10 |
| Alt + C / V | 복사 / 붙여넣기, 터미널에서는 Ctrl+Shift+C/V 전달 |
| Caps + H/J/K/L | 방향키, Shift 병용 시 선택 이동 |
| Caps + 숫자 | 기존 KeyBridge 기능 키 |
| Ctrl + Alt + Esc | Linux 세션을 유지하고 Android 입력 우선권 반납 |

Mac 배열 옵션은 물리 Alt와 Meta를 교환합니다. 숫자는 위의 사용자 지정 동작을 우선합니다. Fn은 키보드 펌웨어가 Android로 전달하는 경우에만 처리할 수 있습니다.

물리 트랙패드 버튼과 손가락 접촉을 함께 재생하는 테스트에서 커서가 트랙패드 내부 좌표로 이동하고 클릭이 중복되는 문제가 재현됐습니다. 원시 접촉 좌표는 상대 이동에만 사용하고 버튼 클릭은 현재 커서 위치를 유지하도록 수정했습니다. 물리 클릭 이후 탭·두 손가락 우클릭 중복을 막으며, 접촉 종료와 버튼 해제의 순서가 달라도 버튼 상태를 균형 있게 유지합니다. 일반 마우스, 캡처된 상대 마우스, 탭·탭 드래그, 화면 터치의 기존 검사를 함께 통과했습니다. Y900 실제 버튼 이벤트와의 일치는 아직 확인하지 못했습니다.

Wayland 소켓 검사에서는 화면 출력이 기다리는 동안 키 이벤트도 전달되지 않는 경로가 재현됐습니다. 렌더링 전에 입력을 flush하고 렌더링 뒤 프레임 완료 이벤트를 전달합니다. 이 검사는 출력 대기 때문에 생기는 지연 성분을 검증하며, 실제 키를 누른 시점부터 화면에 글자가 보이는 시간은 측정하지 않았습니다.

Sway의 `floating_modifier`가 조합 수정자 `Ctrl+Mod1`을 거부하는 실제 시작 오류도 확인했습니다. 기본값을 단일 `Mod1`로 수정했습니다. Sway의 [명령 구현](https://raw.githubusercontent.com/swaywm/sway/master/sway/commands/floating_modifier.c)도 단일 수정자 이름을 검사합니다. 업데이트는 해시가 알려진 배포 기본 설정만 교체하며 사용자 수정 파일은 보존합니다.

## 실기기에서 확인한 범위

아래 실기기 성공은 **기존 설치 APK `2bc4ac6d939678d822fb1a5da50541eb208c89ef4dbe6dd738e20021c119bfa7`**에 해당합니다. 새 업데이트 APK의 물리 검증으로 간주하지 않습니다.

| 항목 | 현재 증거 |
| --- | --- |
| 키보드 입력·터미널·트랙패드 클릭 기본 동작 | 사용자 확인 통과, 간헐적 물리 클릭 문제는 이후 보고됨 |
| 글자 크기·균형 화면 크기·반응 | 사용자가 이전보다 개선됐다고 확인 |
| Alt+C/V 복사·붙여넣기 | 실제 키 입력과 소유한 GTK 테스트의 복사·붙여넣기 신호 확인, 사용자 통과 |
| zsh | 실제 앱 UID 10330의 PTY에서 Powerlevel10k, fzf, 제안·구문 강조·별칭 확인, 경고 없음 |
| zsh 시작 | 첫 compinit 약 13.396초, 이후 PTY 약 1.347–1.467초. 글자 입력 지연 측정과는 별개 |
| tmux | 앱 UID의 전용 서버에서 Ctrl+A, mouse, base-index 1, zsh 기본 셸, M-1 바인딩 확인 |
| AstroNvim | 앱 UID에서 시작 성공, AstroCore/UI/LSP 및 Telescope 모듈·사용자 키맵 확인 |
| Neovim 실제 파일 편집 | 검사 25초 시간 초과, 이후 Linux 세션 exit 137. 원인·인과관계 미확인 |
| Yazi | 25.5.31 실행·설정 파싱 확인 |
| 사용자 설정 보존 | 사용자 Sway 설정 및 Keyboard.md의 이전·이후 해시 동일 |
| 하단 설정 여백 | Android 설정 창이 콘텐츠 높이를 따르고 버튼 영역과 분리됨을 접근성 bounds로 확인 |

기존 클립보드 fixture는 전용 PID·창 ID·app_id를 확인해 종료했습니다. 사용자 창을 종료하거나 셸 기록·실제 클립보드·편집 내용·인증 정보를 수집하지 않았습니다. 진단을 Linux 앱 UID로 실행한 결과와 `run-as`로 파일을 준비한 작업은 구분했습니다.

## Mac 설정 이식

[이식본 설명](../profiles/mac-tablet/README.md)과 [설치 도구](../profiles/mac-tablet/install.py)를 보존했습니다. zsh·tmux 기본 설정은 APK에 포함하고 AstroNvim·Yazi 이식본 및 플러그인 81개의 추적 소스는 이 Y900의 Linux HOME에 설치했습니다. 기존 설정과 내용이 다르면 덮어쓰지 않으며, 원래 배포된 init.vim만 정확한 해시를 확인해 백업했습니다. Mac 원본 파일은 수정하지 않았습니다.

Linux fnm/Bun/Flutter/JDK/Rust 도구 체인, LSP·DAP 서버, Markdown 구문 파서는 아직 설치하지 않았습니다. 관련 다운로드·자동 설치를 시작 시 실행하지 않으며, 없는 CLI·이미지·Discord·tinymist 연동은 비활성화했습니다. Mac .zshenv, 셸 기록, SSH 키, 인증 정보, Homebrew 경로와 Darwin 라이브러리는 복사하지 않았습니다. 기본 편집 시작 성공을 모든 개발 도구·파일 편집 성공으로 확대하지 않습니다.

## 이번 호스트 검증

- [Python·Java 전체 검사](validation/2026-10-06-y900-tablet-fit/host-tests-final-mechanical-input.log): 530개 통과, 실패 0.
- [네이티브 Wayland 검사](validation/2026-10-06-y900-tablet-fit/native-final-input.log): 50개 통과, 실패 0.
- 물리 클릭 좌표·중복과 렌더링 중 키 전달은 수정 전 실패, 수정 후 통과를 확인했습니다.
- [rootfs 빌드](validation/2026-10-06-y900-tablet-fit/final-mechanical-rootfs-build.log), [네이티브 빌드](validation/2026-10-06-y900-tablet-fit/final-mechanical-native-build.log), [APK 빌드](validation/2026-10-06-y900-tablet-fit/final-mechanical-apk-build.log)는 해시가 기록된 입력을 사용합니다. APK 성공 여부는 영수증을 기준으로 합니다.
- [zsh 지연 측정 도구](../tools/probe_zsh_latency.py)는 격리한 PTY에서 알려진 20글자의 redraw 시간만 수집하고 사용자 셸 기록을 읽지 않습니다. macOS의 빈 테스트 설정에서 실행·정리를 확인했으며 Y900 측정은 대기 중입니다.

## 연결 복구 후 남은 확인

ADB 연결이 끊겨 새 APK를 설치하지 않았습니다. 마지막 확인 시 기존 Linux 세션은 exit 137로 종료됐습니다. 재연결하면 model·serial·설치 해시를 다시 확인하고, 새로 열린 작업이 있으면 미저장 데이터부터 보호해야 합니다.

1. UID 10330에 한정해 Android 강제 종료·메모리 회수·phantom process 로그를 확인하고 exit 137의 원인을 분리합니다. 원인 확인 전에 기기 전체 프로세스 제한 설정을 변경하지 않습니다.
2. HOME를 보존하는 업데이트 설치 후 정확한 APK 해시를 대조합니다. 테스트 APK는 실기기에 설치하지 않습니다.
3. 소유한 GTK 창에서 실제 물리 클릭·누른 채 드래그·버튼 해제·탭·두 손가락 우클릭을 확인하고 Alt+C/V를 재검사합니다.
4. 소유한 창과 전용 tmux 서버로 Meta+1/0, Meta+Shift+1/0, Alt+1/0을 확인합니다. 사용자 tmux 서버와 창은 건드리지 않습니다.
5. 새 private PTY로 zsh 기본 설정과 이식한 설정의 문자 입력 시간을 비교하고, 실제 화면 표시 지연을 별도로 측정합니다.
6. 소유한 Lua·Markdown·TypeScript 파일을 각각 열고 저장해 Neovim 편집 검사를 완료합니다. 자동 서버 설치·프로세스 증가·Android 종료 여부를 함께 확인합니다.

Linux GUI 전체 GPU 가속은 완료하지 않았습니다. Android 출력 합성 경로와 Adreno 오프스크린 검사는 별도 증거이며, 이전 GTK GL 창은 실패했고 기본 Sway 렌더러는 pixman입니다. 실제 외부 SSH/RDP/VNC 서버에 대한 종단 검증, OEM 예약 키 전체 회수, 장시간 절전·재연결 검증도 남아 있습니다. [GPU·입력 대체 방법](capability-fallback-validation.md), [OS 경로와 조건](research/loopy-os-paths.md)에 구현 여부와 제한을 구분했습니다.
