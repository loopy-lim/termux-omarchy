# 중단된 X11 · Termux 실험 기록

상태: **2026-10-06 실험 중단**. Termux:X11/i3는 **Wayland 세션 아님**이며 현재 제품·전달 목표가 아니다. 기본 경로는 [Loopy Desktop의 Wayland/Sway 데스크톱](desktop-quickstart-ko.md)이다. X11의 별도 홈 런처와 일반 앱 메뉴·설정의 실행 버튼을 제거했고 내부 Activity만 실험 코드로 보존한다. 새 X11 키트 생성·배포 승격과 추가 실행은 진행하지 않는다.

아래 내용은 중단 전 **네이티브 i3/X11 + Termux Bionic 앱·UTF-8 XFCE Terminal** 실험의 절차와 한계를 보존한 기록이다. 내장 PRoot/Sway와 별도 실행 경로였으며, 소스·설치 준비·부분 성공·실패 결과를 현재 Wayland APK나 실기기 수락으로 대신 쓰지 않는다. 기존 Termux 데이터와 설정을 변경하는 현재 사용 안내가 아니다.

## 중단 전 실험 절차 · 현재 설치 안내 아님

1. 당시 후보 APK는 홈의 **Loopy Native**와 앱 메뉴·설정·대체 방법의 **네이티브 실행 · Termux**에서 별도 제어 화면을 열었다. 이 진입점들은 Wayland 주경로를 복원하면서 제거했다.
2. 현재 Termux가 있으면 설치 출처와 데이터를 보존한다. 새 환경은 제공된 고정 GitHub Termux 0.118.3 ARM64와 Termux:X11 20261005 검증본을 사용할 수 있다. 서로 다른 서명의 Termux를 덮어쓰기 위해 삭제하지 않는다. [공식 설치 정책](https://github.com/termux/termux-app#installation)을 확인한다.
3. Termux를 한 번 열어 기본 환경을 준비한다. Loopy Native의 **설치 명령 복사**를 Termux에 붙여 넣거나, 저장한 `loopy-termux-setup.sh`를 Termux에서 `bash`로 실행한다. 네트워크와 패키지 저장 공간이 필요하다. 설치기 자체는 고정 포함 파일이며 외부의 움직이는 shell installer를 실행하지 않는다. Termux 패키지 저장소 버전은 설치 시점에 따라 달라져 `상태 검사`의 실제 버전을 기록한다.
4. Loopy의 **Termux 명령 권한 요청**을 승인하고 **외부 앱 연결 명령 복사**를 Termux에서 실행한다. 기존 `termux.properties`를 백업하고 `allow-external-apps=true`를 선택하는 단계다. 이 권한과 설정은 Loopy가 Termux 안에서 명령을 실행하게 한다. [공식 RUN_COMMAND 요구 조건](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent).
5. **네이티브 시작**은 Termux UID의 실제 X 서버·WM 준비 결과를 확인한 뒤 소유 X11 창을 연다. 첫 실행에서 X11의 Android 알림 권한 창이 나오면 먼저 응답하고 실제 데스크톱이 연결될 때까지 기다린다. **X11 화면 열기**도 새 상태 검사를 한다. 준비 실패는 앱의 설명을 보고 설치·권한·외부 앱 설정을 수정한다.
6. 선택적 **X11 입력 설정 적용**은 X11을 한 번 연 뒤 돌아와 실행한다. fullscreen·pointerCapture·preferScancodes·외부 키보드 IME·추가 키 바·Esc 반납을 조정한다. **적용한 입력 설정 복원**은 해당 값이 아직 Loopy가 적용한 값일 때만 이전 값으로 되돌리며 사용자의 후속 수정을 유지한다. 별도 X11 화면별 설정을 사용하는 경우 적용을 거부하고 수동 설정을 안내한다.
7. 화면 끄기·백그라운드에서 세션이 회수되면 **Termux 절전·앱 정보**에서 사용하는 기기의 배터리 정책을 직접 확인한다. Loopy의 배터리 예외만으로 Termux 프로세스를 유지하지는 않는다.
8. 종료할 때 작업을 저장하고 **네이티브 세션 종료**를 누른다. 내장 Linux 세션 종료와는 별개다. 저메모리 기기에서 내장 세션도 켜져 있으면 먼저 저장·종료한 뒤 네이티브 환경을 사용한다.

## 당시 준비 실패와 복구 절차

권한·외부 앱 연결·패키지가 빠졌으면 제어 화면에서 해당 준비 단계를 완료하고 다시 시작한다. 이전 세션의 소유 프로세스가 사라졌는데 자식 종료를 확인하지 못했으면 시작·상태 검사는 실패를 유지하고 기존 기록을 덮어쓰지 않는다. **내장 데스크톱으로 돌아가기**로 다른 실행 경로를 사용할 수 있다.

미확인 종료 기록을 직접 복구하려면 먼저 모든 Termux 작업을 저장하고, Android의 Termux 앱 정보에서 **강제 종료**한 뒤 Termux를 다시 연다. 이 작업은 다른 Termux 세션도 종료한다. 그 다음 자신의 `~/.local/share/loopy-native/state.json`을 날짜가 다른 파일로 백업·이동하고 네이티브 시작을 재시도한다. 실행 중인 Termux를 둔 채 이 기록을 지우지 않는다. 설치기를 다시 실행해도 기존 사용자 데이터와 세션 기록은 자동 삭제하지 않는다. VM에서 사용한 준비 복구와 helper의 정상 종료 검증은 별도 증거로 남긴다.

## 당시 키보드와 마우스 계약

| 네이티브 i3 키 | 동작 |
| --- | --- |
| Ctrl+Alt+Enter | XFCE Terminal |
| Ctrl+Alt+Space | dmenu 앱 메뉴 |
| Ctrl+Alt+E / F | Mousepad / PCManFM |
| Ctrl+Alt+1…9 | 작업공간 |
| Ctrl+Alt+Shift+1…9 | 현재 창을 작업공간으로 이동 |
| Ctrl+Alt+H/J/K/L | 포커스 이동 |
| Ctrl+Alt+Shift+H/J/K/L | 창 이동 |
| Ctrl+Alt+Tab | floating/tiling 포커스 전환 |
| Ctrl+Alt+Shift+Space | floating 전환 |
| Ctrl+Alt+M | 현재 창 전체 화면 |
| Ctrl+Alt+Shift+Q | 현재 창 닫기 |
| Esc | Termux:X11 포인터 캡처 반납 |
| Ctrl+Alt+Esc | Loopy 입력 우선권을 켠 경우 네이티브 제어 화면으로 복귀 |

X11 창이 입력을 소유하는 동안 Loopy 접근성 서비스는 일반 키·modifier·마우스를 X11에 전달한다. 키보드·마우스 연결 갱신으로 내장 화면을 자동으로 열지 않는다. 내장 Activity로 명시적으로 돌아오면 내장 입력 소유권을 복구한다. Termux:X11 접근성 키 가로채기는 별도 선택이며 Android·OEM 예약 키의 전체 회수를 보장하지 않는다. [Termux:X11 입력·설정 계약](https://github.com/termux/termux-x11).

기본 키보드 설정은 Termux:X11/X 서버의 레이아웃을 사용한다. Loopy 내장 Linux의 Caps 한영·HJKL 변환은 네이티브 X11 경로에 자동 적용하지 않는다. 한국어는 사용 중 Android IME 또는 별도로 설치·구성한 native Linux IME를 확인한다. XFCE Terminal·Mousepad·PCManFM·dmenu를 기본 설치하며 browser/code IDE 등은 Termux의 실제 지원 패키지를 추가한다.

## 실험의 성능과 GPU 경계

네이티브 경로는 PRoot의 syscall 변환을 제거하는 구조다. 처리 지연·FPS·전력 개선 정도는 실제 기기에서 측정해야 한다. Termux:X11은 별도 Android Activity이며 Loopy Surface 안에 끼워 넣지 않는다. Android 호스트의 GLES 출력, 네이티브 앱의 CPU GL, 실제 vendor GPU의 3D 렌더링은 각각 확인한다. 이 구현이 모든 네이티브 앱을 hardware GPU로 자동 전환하지는 않는다.

내장 VirGL은 EGL1.5 core 또는 실제 KHR 지원을 구분하고 bootstrap/renderer `makeCurrent` 실패를 검사하도록 개선했다. 실패하면 software GL/Cairo 경로로 이어진다. 실제 version/vendor/API/capability 진단으로 실패 이유를 남긴다. 네이티브 Termux의 공식 `virglrenderer-android` + Mesa virpipe/ANGLE 후보, `glxinfo` 검증 명령과 driver 조건은 [공식 소스 조사](research/termux-native-runtime.md)에 있다. 직접 Turnip/KGSL·Mali·Vulkan·원격 GPU 등은 [전체 대안과 요구 조건](capability-fallback-validation.md)을 따른다. GPU 모델·동작을 장치명이나 서버 소켓만으로 판정하지 않는다.

내장 입력도 개선했다. 상대 마우스의 Android historical batch를 순서대로 반영하고 가장자리에서 각 샘플을 보정한다. Rust 큐는 연속 absolute motion만 합치고 키·버튼·스크롤·reset 경계를 보존해 이동 폭주로 modifier 해제를 잃는 것을 막는다.

## 검증 기록

실험은 최종 제품 수락 전에 중단했다. [초기 최종 후보 실패](validation/2026-10-06-native-termux-final-vm/receipt.json), [후속 후보 실패](validation/2026-10-06-native-termux-current-vm/receipt.json), [키보드 경로·마우스 후보 실패](validation/2026-10-06-native-termux-preime-mouse-vm/receipt.json)를 해당 APK 해시와 함께 보존한다. 준비·호스트 검사나 개별 START/STOP·문자 입력 성공이 전체 X11 입력·종료 수락을 대신하지 않는다. 추가 성공 기록이나 새 전달 해시를 예정된 현재 결과로 표시하지 않는다.

Wayland의 검증 완료 APK(`157be08c…`, VM **32/32**)는 [별도 검증 기록](capability-fallback-validation.md)에 있다. 진입점 정정 소스의 새 Wayland APK는 별도 재검증 대상이다. VM 합성 입력과 물리 키보드·마우스·vendor GPU·절전/장시간 사용 수락은 별개이며 실기기는 수정하지 않았다.
