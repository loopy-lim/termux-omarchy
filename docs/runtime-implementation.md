# 구현 구조와 검증 범위

2026-10-06 현재 소스의 기본 제품 경로는 Android 일반 앱 안의 **Alpine ARM64 + Sway Wayland 데스크톱**이다. GPU 합성·입력 소유권·실사용 권한 안내에 Mesa GL 검사·선택과 조건부 VirGL probe·대체 방법 이동을 추가했다. 현재 APK와 검증 결과는 [대체 경로 검증](capability-fallback-validation.md)에 기록한다. 이전 GLES 전달물은 [입력·권한·GPU 검증](daily-use-gpu-validation.md), 이전 앱 전달물은 [앱 확장 검증](desktop-app-extension-validation.md)에 보존한다. Lenovo Y900 실기기 검증은 별도다.

## 실행 경로

`MainActivity` → `DesktopSessionService` → 앱 소유 PRoot/loader → Alpine 3.22.6 ARM64 → Sway 1.10.1/wlroots 0.18.2 → Rust Wayland host → Android EGL/GLES → Surface. Sway는 실제 Linux 창을 소프트웨어로 합성한다. 호스트는 원본 공유 메모리 표면을 순서대로 GPU 텍스처에 올리고 BGRA 변환·알파 합성·클리핑을 처리한다. EGL 실패는 CPU로 복귀한다. fragment highp가 없는 장치의 1024픽셀 초과 출력·텍스처도 CPU로 복귀한다. guest DMA-BUF와 하드웨어 3D 가속은 미수락이다. CPU OpenGL과 조건부 VirGL 검사는 아래 경로를 사용한다. Omarchy 원본 Arch/Hyprland 설치는 제공하지 않는다. guest는 실제 Android UID/GID를 사용하며 D-Bus 시작 전에 passwd/group 항목을 안전하게 등록한다.

`TerminalController`는 새 desktop 작업 스레드에서 optional `NativeGraphicsServer`를 실행한다. 고정 API28 NDK VirGL+libepoxy PIE를 APK nativeLibraryDir에서 실행하고 전용 vtest 소켓만 소유한다. guest `graphics_probe.collect()`는 현재 socket의 실제 client EGL 픽셀과 renderer를 검사하지만 기본 선택은 검증된 `llvmpipe → softpipe → cairo`다. `graphics_session.py`는 현재 token/UID 보고서를 저장하고 미리 정한 환경만 적용한다. GTK GL 창 검사는 offscreen 결과와 실제 Android 표시를 구분한다. VirGL 하나의 성공을 모든 창·브라우저 GPU 수락으로 확장하지 않는다.

| 모듈 | 현재 역할 |
| --- | --- |
| `DesktopSessionService`, `TerminalController`, `RuntimeSession` | 장기 Linux 세션·네이티브 host 소유, 시작/재시작/명시적 종료, 게스트 프로세스 정리 |
| `DesktopSurface`, `MainActivity`, `DesktopChrome` | Surface 부착·해제와 재연결, Android 전체 화면, 화면 포커스·입력 전달 |
| `RootfsInstaller`, `TarArchive`, `HomeDirectory` | 고정 해시 rootfs 안전 추출, 설치 용량 상한, 영속 HOME·공유 디렉터리 |
| `RuntimeDns` | Android 활성 네트워크의 DNS 주소를 private resolver 파일로 전달·갱신, PRoot 빈 표식을 구분하며 기존 guest 설정 보존 |
| `native/wayland-host/src/` | Wayland shm/xdg/입력/selection, Surface detach 중 세션 유지와 재부착 |
| `InputDevices`, `ModePolicy`, `AutoDockPolicy`, `DesktopPreferences` | 상대 마우스를 포함한 물리 입력 능력 관찰, 수동 모드와 실제 dock 상태 전환에만 반응하는 AUTO, 장치 갱신 중 비상 반납 유지 |
| `DesktopPermissions`, `DesktopPermissionPolicy` | 처음 연결 시 한 번 안내, 접근성·알림·배터리·기본 홈 승인 진입, 현재 렌더러 표시 |
| `InputOwnershipPolicy`, `EmergencyExitPolicy` | 마우스 캡처 요청/취소·늦은 허용 반납, Ctrl+Alt+Esc의 장치별 균형 |
| `InputPriorityService`, `KeyCapturePolicy` | 사용자가 켜는 접근성 서비스의 사전 키 필터와 Android 14+ mouse/touchpad 모션 소유권 |
| `TerminalInput`, `KeyboardRouter`, `PointerRouter`, `GestureRecognizer` | 장치별 key down/up 균형, 단축키, 포인터·휠·전달된 접점 제스처 |
| `HangulComposer`, `DesktopInputConnection` | 두벌식 조합 및 Android IME의 commit/composing 텍스트를 데스크톱 입력으로 전송 |
| `DesktopCommands`, `AndroidApps`, `DesktopMenus` | 세션 UUID로 구분한 명령, Android 앱 목록/실행, Android 설정·빠른 메뉴 |
| `DesktopClipboardBridge`, `SharedFilesProvider` | Sway 내부 selection↔Android 텍스트 클립보드, 공유 파일의 문서 제공자 |
| `guest/desktop/` | Sway 설정·상단 바·wmenu 앱/창 메뉴·테마·클립보드/명령 worker |

`third_party/runtime.lock.json`, `third_party/desktop.lock.json`은 실행 파일과 Alpine 패키지의 출처·해시를 고정한다. 현재 이미지에는 패키지 258개를 포함한다. `tools/prepare_desktop.py`가 데스크톱 이미지를 만들고 기본 `dev/build`가 이를 APK에 넣는다. 패키지 설치 스크립트·트리거는 실행하지 않고 기반 APK 데이터베이스를 보존한다. PRoot의 tagged SIGSYS 전달과 ARM64 x7 복원을 수정했고 **같은 빌드의 loader**를 함께 사용한다. 대응 소스·정적 라이브러리·오브젝트·패치는 [고지](../third_party/NOTICE.md)에 명시한 별도 번들에 보존한다. 이 수정의 probe 합격은 Firefox GUI 성공을 뜻하지 않는다.

실제 브라우저의 외부 HTTPS 접속을 막던 DNS 설정 오인을 수정했다. PRoot가 만드는 빈 권한-000 파일만 바인드 표식으로 구분하며 기존 사용자 DNS 파일은 보존한다. [회귀·HTTPS 기록](validation/2026-10-06-dns-placeholder-https-vm/dns-regression.json)에 원인과 일반 앱 재시험을 기록했다.

## 화면·수명주기

시작 화면은 Sway의 왼쪽 작업공간 바와 wmenu 메뉴다. 오른쪽 상태 표시와 트레이는 제거했고 Android 전체 화면 표시를 포커스 복귀 시 다시 적용한다. WebKitGTK 2.48.1-r1과 PyGObject 3.52.3-r1을 사용하는 Loopy Browser, Geany 2.0-r0, foot, Mousepad, Thunar, nvim, btop, yazi 등을 포함한다. Firefox 후보의 GUI 시작 실패를 보존하고 브라우저를 교체했다. 브라우저는 별도 실행 스크립트에서 CPU Wayland 설정을 적용하고 GTK 창에서 주소창·탭·단축키를 관리한다. HOME·XDG 아래 loopy-browser 프로필과 쿠키를 저장하며 기존 Firefox·MiniBrowser 데이터는 보존한다. WebKit context의 Linux sandbox를 명시적으로 끄며 추가 Linux 브라우저 격리는 제공하지 않고 Android 앱 UID·SELinux·상속 프로세스 정책에 의존한다. `.desktop` 검색은 개수·파일 크기를 제한하고 shell 실행 없이 안전한 argv만 허용한다. Linux 런처에서 Android 앱을 고르면 원래 Android 창을 열고, 돌아올 때 서비스 안의 Sway·Linux 창을 유지한다.

Activity 또는 Surface를 다시 만들면 화면 host를 재부착한다. 세션을 명시적으로 종료하지 않으면 Linux 프로세스·미저장 창 상태를 유지하도록 설계했다. 강제 프로세스 종료와 OEM 메모리 회수 후의 메모리 복구는 제공하지 않는다. 태블릿 모드에서는 Linux 화면·입력 소유권을 반납한다.

자동 모드는 물리 키보드 **또는** 포인터가 있는지로 dock 상태를 정한다. `AutoDockPolicy`는 실제 dock 상태 전환에만 진입·복귀를 요청한다. 장치 정보 갱신과 캡처 source 변경은 비상 반납 상태를 덮어쓰지 않는다. `SOURCE_MOUSE_RELATIVE`도 물리 마우스로 분류하며 raw 터치패드는 별도로 처리한다. 같은 복합 키보드의 source만 바뀌고 키보드 능력이 유지되면 held key를 보존한다. 장치 비활성화·능력 상실·제거에서는 눌린 입력을 해제한다.

SHM snapshot 업로드·GPU 합성·주기적 화면 작업의 전력/성능 예산은 실기기 측정이 필요하다. 60/120/144Hz, 키 입력 16ms, 모드 전환 2초/1초 및 배터리 +5% 목표를 달성했다고 주장하지 않는다. Surface 분리 때 GLES context를 해제하지만 세션 소유의 Wayland 연결은 유지한다.

## 입력·클립보드·파일의 경계

기본 창 단축키는 `Ctrl+Alt`이며 Linux [키 안내](../guest/desktop/root/Keyboard.md)와 Android 설정에서 Meta/Alt로 바꿀 수 있다. 짧은 Caps 탭은 한/영 전환, Caps+H/J/K/L은 방향키다. 물리 키보드의 반복/해제와 포커스 상실·장치 제거 시 해제는 별도로 관리한다. 두벌식 조합과 Android IME commit은 구현했지만, 모든 Android IME 후보 창·dead key·OEM 키가 실기기에서 동작한다는 증거는 없다.

화면에 전달된 마우스·터치패드 이벤트로 포인터, 좌우 스크롤, 자연 스크롤·속도, 짧은 탭/드래그, 전달된 두 손가락 스크롤·세 손가락 작업공간/창 목록을 처리한다. raw `SOURCE_TOUCHPAD`의 generic/captured 접점과 `SOURCE_MOUSE_RELATIVE`의 AXIS_X/Y 이동을 별도로 처리한다. 화면 밖 누적 이동을 제한하고 zero-delta 버튼 이벤트는 커서 위치를 유지한다. Android가 이미 마우스/스크롤로 바꾼 이벤트는 접점 제스처로 중복 처리하지 않는다. 자연 스크롤은 Android에서 한 번 적용하고 Sway에서는 끈다. 접근성 서비스는 키를 정책·IME·앱보다 먼저 필터링하며, API 34+에서는 `setMotionEventSources`로 mouse/touchpad를 요청한다. 실제 원시 다중 접점이 전달되는지는 기기·OS에 달렸고 Android 13 이하에는 이 모션 소스 API가 없다. 서비스 사용은 사용자가 Android 접근성 설정에서 선택한다. 선택한 전역 데스크톱 복귀 단축키는 외부 Android 앱에서도 사용할 수 있으나, 기본 화면 입력 소유권은 데스크톱 포커스에 묶는다. Y900 OEM 예약 Meta 조합 회수 여부는 아직 검증하지 않았다.

데스크톱 클립보드는 `clip-android-$UUID`/`clip-guest-$UUID`를 원자적으로 교체하고 파일 이벤트로 감시한다. 포커스 있는 Android 창에서만 ClipboardManager에 접근하며 64KiB UTF-8 텍스트와 비움(clear)을 구분한다. 지원하지 않는 URI 클립보드와 초기 값 없음(nil)은 지우기로 해석하지 않는다. guest는 `wl-paste`/`wl-copy`로 Sway selection을 연결한다. Android IME와 클립보드는 서로 다른 텍스트 경로다. 공유 파일은 Android 문서 제공자와 Linux `/mnt/shared`를 연결하며 광범위 저장소 권한을 요구하지 않는다.

Deskweft에서는 접근성 키 사전 필터, 장치 제거 시 held-key 정리와 OEM 설정의 분리 필요성을 확인해 설계에 참고했다. [원본 조사](research/deskweft-reuse.md)처럼 Deskweft는 Wayland host가 아니며, Lenovo OEM 설정 변경은 Shizuku/ADB shell 권한이 필요한 별도 선택 기능이다. Loopy Desktop의 일반 앱 실행 전제에 그 설정 쓰기를 넣지 않았고 코드도 복사하지 않았다.

## 빌드와 시험

```sh
./dev/build --check-tools
python3 tools/fetch_runtime.py
python3 tools/prepare_desktop.py
./dev/native-build
ANDROID_NDK_HOME="$HOME/Library/Android/sdk/ndk/27.1.12297006" ./dev/build --rootfs build/desktop/rootfs.tar.gz
```

`build/loopy-desktop-debug.apk`, 테스트 APK, `build/build-receipt.json`이 생긴다. 이전 납품 `LoopyDesktop-2026-10-05-desktop-arm64.apk`는 보존하며 현재 빌드와 동일한 파일로 표현하지 않는다. 각 시험 폴더의 복사된 빌드 영수증이 해당 실행의 입력을 고정한다.

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'
CARGO_HOME="$PWD/build/cargo-home" CARGO_TARGET_DIR="$PWD/build/native-target" cargo test --locked --manifest-path native/wayland-host/Cargo.toml
python3 tools/check_code_size.py
./dev/app-test --serial emulator-5580 --suite desktop --output docs/validation/new-desktop-run
```

마지막 명령은 부팅된 Android VM에서만 설치·실행한다. `--suite desktop`은 실제 Sway 화면, 패키지, 창/작업공간/런처, 세션 재연결, 내부 클립보드/Unicode, 입력 정책을 시험하도록 등록돼 있다. 시험 케이스의 실행 결과는 새 영수증에서 확인해야 한다. 입력 정책·두벌식·클립보드 코덱의 host fixture는 Java 로직 증거이며 물리 키보드/트랙패드 증거가 아니다. 코드 파일은 500줄 이하로 유지한다.

## 이전 결함과 증거 수준

Android 앱 데이터 실행 제한에는 APK native-library의 PRoot/loader를 사용한다. PRoot `getcwd`/seccomp 신호 순서, foot의 큰 sparse shm pool, Wayland 프로토콜 오류 panic, 분리된 자식 프로세스 정리, stale APK 영수증 오판을 초기 터미널 단계에서 수정했다. 그 단계의 자세한 실행 증거는 [이전 영수증](validation/2026-10-05-terminal-final/receipt.json)에 보존한다. 첫 Sway 후보의 **17/20** 및 Super 전달 실패는 [개발 이력](desktop-experiment-status.md)에 남긴다. 현재 데스크톱 빌드·VM 결과는 [대체 경로 기록](capability-fallback-validation.md)에 구분했고 Y900 실기기 수락은 아직 없다.

PRoot는 root/namespace 보안 컨테이너가 아니다. 네이티브 리소스 크기에는 상한이 있지만 악성 Wayland client에 대한 완전한 CPU 격리나 Linux guest GPU 접근은 제공하지 않는다.

## 원래 명세와의 차이

현재 납품 범위는 하나의 Android Surface에 표시하는 실제 Sway 데스크톱이다. Linux 앱마다 Android 최상위 창을 만드는 브리지는 없으며 Android 앱은 원래 Android 창으로 열린다. Omarchy 원본과 모든 기능이 동등한 제품으로 표현하지 않는다.

| 명세의 기능 | 현재 상태 |
| --- | --- |
| Wayland 창·타일링·작업공간·키보드 중심 사용 | Sway와 실제 Linux 앱으로 구현 |
| Linux GUI 앱 | Loopy Browser(WebKit)·Geany·Mousepad·Thunar 포함. 일반 앱 실행 검증은 앱 확장 기록 참조. VS Code 미포함 |
| X11 전용 Linux 앱 | Xwayland 비활성. 현재 Wayland 앱만 지원 |
| 런처·창 목록 | 고정 Linux 목록과 제한된 `.desktop` 검색, 동적 Android 목록. 시각적 overview/dock 미구현 |
| Linux 알림·오디오 → Android | 미구현. Android 알림은 Linux 세션 상태만 표시 |
| 절전 freeze/thaw·대체 chroot/namespace backend | 미구현. 현재 PRoot와 세션 유지/종료 경로 |
| GPU·프레임률·입력 지연·배터리 목표 | Android 호스트 GLES 합성·CPU 복귀와 CPU OpenGL 구현·VM 검증. VirGL 조건부 검사 연결, 하드웨어 3D·물리 성능 미수락 |
| 개발 도구 | Bash·Git·Python·Neovim 포함. Bun과 Android Chrome localhost 작업 흐름은 미검증 |

이 표의 미구현 기능과 Y900 실기기 수락은 VM 시험 합격으로 대체되지 않는다.
