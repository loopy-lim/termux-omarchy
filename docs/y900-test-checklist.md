# Lenovo Y900 13인치 실기기 점검

상태: 2026-10-08 **현재 설치본 `0589092c…`의 prod01 업데이트·설정116+2·UID·접근성/서비스 보존 통과, 전체 수락 미완료**. 마이크 권한은 거부 상태를 유지했다. 일반 빌드의 새 기본 runtime과 입력 캡처 수정이 포함됐으며 새 제품 input10a의 합성 입력·정리는 통과했으나 포커스 복원 실패로 전체 FAIL이다. [현재 제품](../build/deliverables/LoopyDesktop-2026-10-08-native-input-runtime-arm64/README.md), [정확한 실제 기록과 범위](validation/2026-10-08-tablet-stage-progress.md)를 따른다.

이전 `7c14004c…`의 기본 PDF·SSH·Android 연결·소리 출력·합성 Esc/Alt+Tab/클릭 통과는 그 APK의 기록이다. 숫자 조합30개 기능 성공과 포커스 복원 실패, 클립보드 전체 FAIL, Timing11 ON 전체 FAIL을 새 제품의 통과로 바꾸지 않는다. 기존 GPU 장면은 약17fps로 최소60/목표144fps에 미달했으며 `0589092c…`의 새 측정은 없다. 새 runtime의 격리 커널3개 PASS는 UID2000 시험이다. 물리 장치·실제 권한 상실·새 제품 SSH/클립보드·Android 앱 내부 호스팅과 장시간 안정성은 별도 수락 대상이다. 실제 연결은 **TB522FU · Android16 · Adreno830**, 물리 패널2560×3840이다. [native OS 경로](research/loopy-os-paths.md). 이전 TB570 계열의 설정 쓰기는 적용하지 않는다.

별도 shell broker의 [inside07](../build/diagnostics/y900-android-inside-runs-20261008-01/inside07/receipt.json)은 공개 Android 시험 앱의 VD 픽셀·실제 클릭/F12·프레임3개 독립 검사·정리를 통과했다. 01–06 실패는 보존했다. 후속08은 UID가 다른 소스 hash 조회,09는 GdkWayland GI namespace 부재로 실패했고 두 소유 폴더는 별도 정리됐다. [inside10](../build/diagnostics/y900-android-inside-runs-20261008-01/inside10/receipt.json)은 관리된 GTK 창·검증된 첫 프레임 전송 뒤 phase0 timeout·원래 포커스 창 소실로 전체 FAIL이다. 당시 GUI 이벤트 로그가 없어 paint 대기와 클릭 중 정확한 실패 위치는 미확정이다.

[inside11](../build/diagnostics/y900-android-inside-runs-20261008-01/inside11/receipt.json)은 공개 Android 앱 첫 프레임의 독립 전체 픽셀 검사와 실제 관리된 GTK Wayland 창의 draw ACK를 확인했다. 클릭/F12·relay 명령은0이고 phase0 세부 실패 원인은 미기록이며 전체 FAIL이다. 소유 task/display·GTK 창/프로세스·폴더·target 정리, 원래 포커스 상태 복원 및118·서비스·역할·제품0589·기본 Loopy 포커스 보존은 통과했다. 이 유한한 첫 프레임 prototype을 물리 presentation·완전한 상호작용·일반 내부 앱/Notion/Chrome 호스팅이나 생산 성능 수락으로 바꾸지 않는다.

현재 시험 대상은 **원본 Omarchy의 Hyprland·Quickshell·Wayland 세션**이다. Sway는 기존 프로필과 설정 보존을 위한 별도 회귀 대상이다. 정확한 APK·실기·정책 복구 결과는 [재연결 체크포인트](validation/2026-10-06-omarchy/checkpoint-y900-reconnect.json)에서 대조한다. 합성 입력 VM, 일반 앱 UID의 실행, 물리 장치 입력·GPU 성능은 서로 다른 증거다. 구현·VM 통과만으로 Y900을 수락하지 않는다.

기존 Sway 이미지의 262개 패키지와 전체 Omarchy 이미지는 별도 구성이다. 이전 APK·브라우저 구성 이력은 [대체 경로 기록](capability-fallback-validation.md), [구성 기록](research/linux-browser-code-editor.md)에 보존한다. 기존 프로필·Linux 설정·프로젝트가 업데이트 뒤에도 유지되는지 확인한다.

## 읽기 전용 기초 조사

Y900에서 USB 디버깅과 이 Mac을 허용한 뒤 목록에서 **정확한 serial**을 확인한다. 도구는 설치·설정 변경·root 실행 없이 수집하고 기존 결과 디렉터리를 덮어쓰지 않는다.

```sh
adb devices -l
./dev/device-check --serial <ADB_SERIAL> --expect-manufacturer lenovo --expect-model TB522FU \
  --output docs/validation/y900-01-tablet
```

순서대로 주변 기기 분리, 키보드·트랙패드 연결, 다시 분리한 상태를 각각 새 경로에 저장한다.

```sh
./dev/device-check --serial <ADB_SERIAL> --expect-manufacturer lenovo --expect-model TB522FU \
  --output docs/validation/y900-02-keyboard-trackpad
./dev/device-check --serial <ADB_SERIAL> --expect-manufacturer lenovo --expect-model TB522FU \
  --output docs/validation/y900-03-detached
```

각 명령 전에 실제 연결 상태를 맞춘다. `offline`·`unauthorized`이면 연결과 화면의 디버깅 승인을 확인한다. `receipt.json`의 `complete`는 수집 완료일 뿐 제품 기능 통과가 아니다. 모델·fingerprint·API·ARM64 ABI·커널, 입력 장치 source/keyboardType, `EV_REL`·`EV_ABS`·멀티터치 슬롯, 창 관리·SELinux·권한 경계를 비교한다. ADB 셸에서 보이는 evdev/uinput/namespace 능력을 일반 앱 UID 능력으로 바꾸어 말하지 않는다.

## 실사용 준비와 Android 설정

설치 전에는 검증 기록의 APK 해시를 대조하고, 업데이트는 기존 데이터를 보존한다. 초기 권한·배터리 최적화 예외·기본 홈 상태를 기록한다. 아래 선택 설정은 사용자가 Android UI에서 직접 결정하며 시험 도구가 자동으로 부여하지 않는다.

1. 물리 입력 장치 없이 앱을 연 뒤 키보드 또는 마우스·트랙패드를 연결해 **실사용 준비 · 권한/진단**이 한 번 표시되는지 확인한다. 이미 연결한 채 첫 실행하는 경우도 확인한다. **완료**로 닫은 뒤 재연결·앱 재진입·화면 재생성으로 반복 안내하지 않아야 한다. 기존 사용 상태를 지워 이 경로를 시험하지 않는다.
2. Android 뒤로 가기 또는 **Ctrl+Alt+Esc** → **메뉴 → 설정** → **실사용 준비 · 권한/진단**으로 다시 연다. 준비 화면과 설정이 작은 창에서도 스크롤되고, 준비 화면의 **완료**를 눌렀을 때 이전 설정 창이 남지 않아야 한다. 연결·분리 때 물리 키보드와 포인터 개수가 갱신되는지 본다.
3. **입력 우선권 설정**에서 사용자가 **Loopy 입력 우선권**을 켠다. **사용 설정됨 · 서비스 연결 대기**와 **키보드 우선권 연결됨**을 구분하고, 설정에서 돌아온 뒤 표시가 갱신되는지 확인한다. Android 13 이상에서 사용 설정이 제한되면 **Loopy Desktop 앱 정보**의 **제한된 설정 허용** 경로를 확인한다.
4. 사용자 선택에 따라 **세션 알림 허용**을 누르고 허용·거부 경로를 각각 확인한다. 거부해도 같은 Linux 세션을 사용할 수 있고, 이후 **알림 설정**에서 변경할 수 있어야 한다. 알림 허용 상태에서는 복귀 버튼과 **Linux 세션 종료** 동작을 확인한다. 앱 전체 알림뿐 아니라 세션 채널을 끈 경우의 상태도 구분한다.
5. **배터리 최적화 설정**은 선택 항목이다. 원래 예외 상태를 기록하고, 사용자가 선택한 경우에만 변경한 뒤 패널 표시를 확인한다. 화면을 끈 상태의 생존·네트워크 동작을 별도로 측정하며 예외 설정을 강제 종료·메모리 회수 뒤 상태 복원으로 해석하지 않는다.
6. **기본 홈 선택**은 선택 항목이다. 후보로 표시되는 것과 실제 기본 홈 역할 부여를 구분한다. 사용자가 Loopy Desktop을 선택한 경우 Android 홈 버튼의 복귀, 패널의 역할 상태 갱신, **메뉴 → Android로 돌아가기**로 기존 Android 홈 열기, **기본 홈 변경**에서 원래 홈 복원을 확인한다. 설정 화면을 열 수 없는 OEM에서는 패널 안내를 확인하고 Linux 세션이 계속 실행되는지 본다.

권한 준비 화면의 성공은 모든 시스템 키나 raw 트랙패드 접점의 소유권을 증명하지 않는다. 접근성 서비스 비활성·중단과 설정 앱 전환 때 눌린 입력이 해제되고 Android가 입력을 받는지는 아래 물리 시험으로 확인한다.

## 제품 화면과 앱 수명주기

1. 검증된 동일 APK를 사용자 데이터 보존 방식으로 설치한다. 실제 SHA, 앱 UID·target SDK, SELinux 컨텍스트를 기록한다. VM 전용 `dev/app-test`와 `dev/runtime-check`는 실기기에 실행하지 않는다.
2. 앱 첫 화면에 Sway 작업공간 상단 바·검색 앱 메뉴·배경이 실제 Android Surface에 나오는지 확인한다. 오른쪽 위 상태 표시와 트레이는 없어야 한다. 첫 후보의 사진 또는 터미널 출력만으로 통과시키지 않는다.
3. foot 창 둘 이상, 작업공간 1–9, 창 포커스/이동/resize/전체 화면, wmenu 런처에서 Mousepad·Thunar를 실행한다. 편집한 미저장 Linux 창을 남긴 채 Android 홈/다른 앱으로 이동했다가 돌아와 **같은 세션 UUID와 Linux PID**인지 확인한다.
4. 화면 회전, 분할 화면 또는 크기 변경, Surface 파괴/재생성, 태블릿 모드 전환 뒤 기존 Linux 창이 재표시되는지 본다. 출력 Surface 분리와 Linux 세션 종료를 구분하고, 복귀 뒤 실제 GUI 화면과 입력을 확인한다. 오류가 발생하면 숨겨진 빈 전체 화면에 남지 않고 상태와 복구 제어가 보여야 한다. 명시적인 **세션 종료** 후에는 게스트 자식이 남지 않아야 한다. Android 강제 종료/OEM 메모리 회수 뒤의 메모리 복원은 요구하지 않는다.
5. 자동 모드에서 키보드 또는 포인터 연결로 데스크톱 진입, 분리로 태블릿 복귀, 분리 순간 눌린 키·버튼 해제를 확인한다. Android 앱으로 열린 브라우저/설정/설치 앱은 원래 Android 창에서 작동하고 Linux 창은 뒤에 남아야 한다.
6. **Loopy Browser · WebKit**를 메뉴와 단축키로 열어 자체 GTK3 UI의 실제 Sway 창·`browser.py` 프로세스·Android Surface 픽셀을 확인한다. 원본 MiniBrowser 창을 제품 UI로 대신 확인하지 않는다. Ctrl+L/T/W/R, Ctrl+Tab·Ctrl+Shift+Tab, 뒤로/앞으로 버튼과 Alt+Left/Right를 검사한다. 주소창에서 기기 안의 HTTP 페이지를 열고 JavaScript 응답·첫 글자를 포함한 키보드 폼 입력·클릭·스크롤을 확인한다. 이는 아래 외부 HTTPS나 DRM·동영상 검증과 구분한다. 브라우저와 실제 WebKit worker의 UID 네 값·상속된 Android seccomp/filter 수·SELinux 확인 가능 여부를 각각 기록한다. `attr/current`가 거부되면 미수집으로 남긴다. 별도 `run-as` 진단의 `runas_app`·seccomp 필터 0개를 일반 앱 결과로 대신 쓰지 않는다. HOME/XDG의 별도 `loopy-browser` 데이터·캐시 경로와 `cookies.sqlite` 유지도 확인한다.
7. Geany 2.0에서 `/root/Projects/hello.py`를 열어 수정·저장하고 Linux Python으로 실행한다. 이는 GUI 코드 편집기 확인이며 VS Code 제품·확장 지원 시험은 아니다. `/mnt/shared`에도 새 코드 파일을 저장해 Android 문서 제공자에서 같은 바이트를 확인한다. 메뉴의 **Other Linux apps**에서 설치된 Linux 앱을 검색하고 실행한다. 안전하게 해석할 수 없는 `.desktop` 실행 항목은 표시하지 않는 정책도 확인한다. Android 측 빠른 메뉴의 Geany 항목도 확인한다.

## 고해상도·터치·Linux 화면 고정·원격

- 가로/세로·분할 화면에서 **메뉴**와 **데스크톱**이 잘리지 않고 전체 화면의 터치 메뉴가 도달 가능한지 확인한다. 메뉴를 연 뒤 취소·재개·오류 복구를 모두 확인한다.
- 화면 배율 100/125/150/175/200%에서 글자·터치 목표 크기·논리 화면 크기·포인터 좌표를 비교한다. 같은 Linux PID와 미저장 작업을 유지하고 재실행 뒤 저장한 배율이 반영되어야 한다. 실제 3840×2560 출력 성능을 VM 해상도 결과로 대신하지 않는다.
- 한 손가락 클릭·드래그, 두 손가락 스크롤·우클릭과 gesture cancel을 실제 화면에서 확인한다. 화면 키보드를 터치 메뉴로 열고 닫고, 조합·확정·삭제·Enter·한글/emoji 붙여넣기의 순서와 실제 전달 성공·속도를 측정한다. **총 64KiB**는 Android 입력 정책의 크기 상한이다. 활성 Wayland 입력 필드의 직접 문자열 경로는 UTF-8 요청당 4,000바이트를 문자 경계에서 내부 분할하며 실제 브라우저 내용·terminal 출력으로 완료를 확인한다. 이 기능을 지원하지 않는 앱의 가상 키보드 대체 경로에는 세션 전체에서 서로 다른 문자 기호를 **최대 4,073개** 추가할 수 있다. 해당 용량 초과·과대 입력·잘못된 Unicode를 포함한 작업은 삭제·문자 전송 전에 오류로 돌아와야 한다. 분할 입력의 앞선 작업은 이미 적용됐을 수 있으므로 현재 창을 확인하며 자동 재전송하지 않아야 한다. GTK 입력 모듈 변경과 다른 Linux IME의 점유 오류도 검사한다. 이 조건 안의 실제 Unicode 범위·속도를 별도로 기록한다. 물리 키 이벤트·클립보드 시험은 별도 경로다.
- Linux 화면 고정의 시스템 허용·취소, Home/최근 앱 제한, Ctrl+Alt+Esc와 터치 해제, USB/BT 모두 분리 뒤 해제를 확인한다. 시스템 자체 unpin 후 자동 재고정하지 않아야 한다. Android 앱이나 권한 설정을 열기 전 해제 안내가 있어야 한다. 전원/OEM/잠금화면과 관리 기기 Lock task는 별도이며 일반 pin 결과로 대신 수락하지 않는다.
- 실제 소유 SSH 서버에 새 호스트 키 확인, 비밀번호·키 인증, 연결 실패, Wi-Fi 변경·절전 뒤 keepalive·재접속, scp/sftp 전송을 확인한다. 최근 연결 화면에 비밀번호/개인 키 내용이 저장되지 않아야 한다. VM loopback 시험은 실제 네트워크·인증·장시간 원격 수락과 구분한다.
- Android 앱 실행 후 Home으로 복귀했을 때 Android 앱이 Loopy task 안에 쌓이지 않고 같은 Linux 세션으로 돌아오는지 확인한다.
- Android 문서 제공자에서 공유 root·한글 이름의 파일 생성/읽기/쓰기/rename/delete를 확인한다. `/mnt/shared`의 같은 바이트를 대조하고 root삭제·상위경로·symlink외부 접근이 거절되어야 한다. 이전 잘못된 document URI를 수동으로 저장한 앱은 공유 문서를 다시 선택한다. 파일 자체는 보존한다.

## 원격 화면과 새로운 GPU 경로

- RDP3389 또는 VNC의 실제 포트로 사용자 소유 서버에 접속해 인증·서버 인증서·연결 오류·종료·재연결을 확인한다. 원격 화면 안의 물리 키 조합, 마우스 이동·좌/우 클릭·휠과 Ctrl+Alt+Esc 입력 반납을 각각 확인한다. Linux 전용 화면 고정 중에도 반납이 먼저 작동해야 한다.
- Wi-Fi 변경·VPN·절전 복귀 이후 연결 상태와 서버의 기존 세션 정책을 확인한다. Remmina 연결 파일에 비밀번호가 저장되지 않고 클립보드·폴더 공유가 기본으로 꺼져 있는지 확인한다. VM의 인증 없는 RFB loopback 결과는 RDP·TLS·인터넷·물리 입력 수락을 대신하지 않는다.
- EGL 초기화 버전·KHR create/surfaceless 토큰과 실제 GL renderer를 기록한다. surfaceless가 없으면 context별 pbuffer 경로를 확인한다. VirGL offscreen 색상 검사와 선택한 GTK GL 창의 표시를 각각 검사하며, 실제 Adreno830 사용·shader/texture/depth·연속 frame/resize·동시 창·열/전력을 추가 수락한다. VM SwiftShader 프록시 성공은 태블릿 하드웨어 증거가 아니다.

## 외부 HTTPS와 Android DNS

- Linux Loopy Browser에서 `https://example.com`을 열어 주소·페이지 표시·실제 네트워크 응답을 확인한다. 검색어의 DuckDuckGo HTTPS 연결도 주소 입력과 구분한다. 로컬 HTTP·JavaScript 성공을 외부 HTTPS 성공으로 대신 기록하지 않는다. 오류가 나면 DNS 조회와 HTTPS 연결 실패를 구분한다.
- 활성 Android 네트워크의 DNS가 Linux에 반영되는지 확인한다. Wi-Fi 연결 변경, 연결 해제와 복구, 사용 가능한 경우 모바일 네트워크 전환 뒤 기존 세션에서 갱신되는지 본다. DNS 주소 외의 개인 네트워크 정보를 영수증에 담지 않는다.
- 별도 사용자 Linux 환경의 기존 `/etc/resolv.conf`를 보존하는지 확인한다. PRoot가 남긴 **권한 0000·0바이트 일반 파일**만 자동 DNS bind 대상으로 구분하며 삭제·수정하지 않아야 한다. symlink·읽을 수 있는 빈 파일·내용 있는 권한 제한 파일과 메타데이터 확인 실패 경로는 보존해야 한다. 활성 네트워크·DNS가 없는 상태에서도 데스크톱과 로컬 파일 작업이 열리고, 외부 조회 실패가 앱 시작을 막지 않아야 한다. 임의 공개 DNS로 우회하지 않는다.
- Android **Private DNS·VPN** 사용 여부와 해당 상태의 외부 HTTPS 결과를 각각 기록한다. 테스트를 위해 기존 기기 설정을 임의로 변경하지 않는다. Android가 알려 준 DNS 주소를 받았다는 사실만으로 Private DNS·VPN 정책과 경로가 보존됐다고 판정하지 않는다. 이 항목은 VM 결과와 별개인 실기기 미검증 항목이다.

## 물리 키보드와 트랙패드

브라우저 래퍼는 `GDK_BACKEND=wayland`, `WEBKIT_DISABLE_COMPOSITING_MODE=1`, `WEBKIT_DISABLE_DMABUF_RENDERER=1`을 설정한다. GDK 값은 데스크톱에도 있고 두 WebKit 값은 브라우저 경로에 한정한다. 각 WebView의 acceleration 정책도 `NEVER`다. 자체 UI는 worker 생성 전에 `context.set_sandbox_enabled(False)`를 명시하며 bypass 환경변수는 넣지 않는다. 기본 경계는 Android 앱 UID·SELinux·상속 정책이고 PRoot는 보안 경계가 아니다. [공식 패키지·고정 2.48.1 소스와 진단 근거](research/linux-browser-code-editor.md#webkit-프로세스-샌드박스와-진단-경계)를 참고한다. 실행 성공을 추가 namespace 격리 지원으로 판정하지 않는다.

- 기본 Ctrl+Alt+Enter/Space/Tab/1…9와 Sway 창 관리 키를 **실제 물리 장치**에서 확인한다. Caps 짧은 탭 한/영, Caps+H/J/K/L 방향키, Caps 장시간 단독 누름의 무동작, Shift·Ctrl·Alt key-up 균형을 검사한다. 한국어 두벌식, Android IME commit/composing, 한글·이모지 입력을 각각 구분해 기록한다.
- 숫자 키패드 0–9·소수점·사칙연산·등호·Enter와 NumLock/Shift 조합의 숫자·내비게이션 동작을 확인한다. guest NumLock은 처음에 꺼져 있고 전달된 NumLock 키로 토글한다. 연결 전부터 켜져 있는 Android NumLock meta/외부 LED의 초기 자동 동기화는 구현되지 않았으므로 실제 상태 차이를 별도로 기록한다.
- Ctrl/Shift를 누른 채 마우스를 분리하거나 캡처만 해제해도 해당 키가 유지되어야 한다. 키보드 두 대에서 같은 Ctrl을 누른 뒤 한 대만 분리하면 남은 키보드의 Ctrl은 유지되어야 한다. 실제 포커스 상실·태블릿 전환·Surface 해제는 전체 입력 반납으로 확인한다.
- 5버튼 마우스의 왼쪽·오른쪽·가운데·뒤로·앞으로 press/release를 일반 입력과 상대 캡처 양쪽에서 확인한다. 보조 버튼의 합성 Android Back/Forward 키가 Linux 버튼과 중복되거나 Android로 빠져나가지 않아야 한다. 키보드의 Android 뒤로 가기는 별도로 정상 동작해야 한다.
- Android 설정에서 **Loopy 입력 우선권** 접근성 서비스를 사용자가 켠 뒤 물리 Meta/Super, OEM 예약 단축키, Android 앱 복귀 단축키를 확인한다. 서비스 비활성/앱 포커스 해제/태블릿 전환 뒤의 소유권 반환도 확인한다. 자동화의 synthetic key 주입이 접근성 경로를 우회할 수 있으므로 실제 키보드 시험을 대신하지 않는다.
- **Ctrl+Alt+Esc**를 실제 키보드에서 눌러 눌린 키·버튼과 포인터 캡처가 해제되고 Android 제어 메뉴가 보이는지 확인한다. 단축키 설정을 Super·Alt로 변경해도 같은 비상 키가 작동해야 한다. key-up·반복 입력과 늦은 캡처 승인 뒤 자동으로 입력을 다시 가져가지 않아야 하며, 사용자가 **데스크톱**을 눌렀을 때 다시 진입해야 한다. Android 뒤로 가기 경로도 확인한다.
- AUTO에서 비상 반납 뒤 장치 정보 갱신·`SOURCE_MOUSE`↔`SOURCE_MOUSE_RELATIVE` 변경으로 전체 화면이나 캡처를 다시 가져오지 않는지 확인한다. 모든 물리 키보드·포인터를 분리한 뒤 재연결한 경우에만 새 dock 전환으로 진입해야 한다. 복합 키보드의 source-only 갱신에서는 held key를 유지하고, 장치 비활성화·키보드/포인터 능력 상실·제거에서는 눌린 입력을 해제하는지 구분한다.
- 트랙패드의 이동·좌우 클릭·드래그·가로/세로 스크롤·자연 스크롤과 속도 설정을 본다. 자연 스크롤은 Loopy의 Android 입력 설정에서 방향을 한 번 바꾸고 Sway에서는 다시 뒤집지 않아야 한다. Android가 전달한 경우에만 두 손가락 스크롤·관성·세 손가락 작업공간/창 목록을 확인한다. 시스템이 마우스로 변환한 이벤트와 raw 접점을 중복 처리하지 않는지도 기록한다.
- 같은 작업을 세 전달 경로로 구분해 확인한다: Android가 만든 마우스 이벤트, `SOURCE_TOUCHPAD`의 raw/generic 접점, 포인터 캡처의 `SOURCE_MOUSE_RELATIVE` 이동. 각 경로에서 클릭·스크롤이 Linux GUI에 실제 반영되는지 확인하고, 캡처가 허용되지 않았거나 Android가 접점을 제공하지 않으면 해당 경로를 미검증으로 남긴다.
- 전체 데스크톱 화면의 실제 마우스에서 포인터 캡처 요청·승인·상대 이동과 Linux 포인터를 확인한다. raw 트랙패드는 마우스로 취급해 캡처하지 않아야 한다. Android 14+ 접근성 모션 전달과 포인터 캡처가 같은 마우스 이벤트를 중복 주입하지 않는지, 설정·준비 화면에서는 Android 버튼과 스크롤이 작동하는지 본다.
- 화면 네 가장자리와 모서리까지 이동한 뒤 클릭·드래그·버튼 해제를 확인한다. 캡처 상태에서 화면 밖으로 계속 움직인 뒤 반대 방향으로 돌아올 때 포인터가 즉시 움직이는지, 일반 이동과 캡처를 전환할 때 위치가 튀거나 버튼이 눌린 채 남지 않는지 본다. 가장자리 보정 코드가 있다는 사실만으로 이 실기기 시험을 통과시키지 않는다.
- Android 14/API 34 이상에서는 접근성 mouse/touchpad 모션 소스 전달 여부를 보고, Android 13 이하에서는 공개 모션 소스 API 부재를 명시한다. API가 있어도 raw 다중 접점·모든 시스템 제스처 회수를 보장하지 않는다. 장치별 SOURCE, 분류(classification), action, 축 값을 개인정보 없이 짧게 남긴다.

펜 입력은 현재 전용 pressure/tilt·stylus 버튼 경로를 구현하지 않았다. 펜을 마우스/터치 성공 결과로 대신 수락하지 않는다.

## GLES 출력과 Linux 앱 렌더링

- 준비 화면의 **화면 렌더러**에서 현재 GLES/CPU/화면 연결 대기 상태를 확인하고 GL 제공자·렌더러 이름을 기록한다. OpenGL ES API 경로와 실제 하드웨어 GPU 사용을 구분한다. VM의 SwiftShader 등 소프트웨어 GL 결과를 Y900 GPU 수락으로 옮겨 쓰지 않는다.
- 실제 GLES 출력에서 브라우저·Geany·Thunar 창, 텍스트·색·투명도·스크롤·창 이동과 크기 변경을 확인한다. 화면 회전·Surface 재생성·Android 앱 전환 후 기존 세션과 출력 경로가 복구되는지도 확인한다. 준비 화면의 상태 문자열만으로 픽셀 출력 성공을 판정하지 않는다.
- GPU 출력이 자연스럽게 실패한 경우 CPU fallback의 화면·입력과 상태를 기록한다. 실패하지 않은 기기에서 오류를 만들기 위해 사용자 설정을 임의로 바꾸지 않는다. 화면 분리는 headless 세션 유지로 구분하며 CPU fallback이나 Linux 세션 종료로 기록하지 않는다.
- **GPU alternatives / check**에서 현재 UID·세션의 선택 경로와 실패 이유를 확인한다. CPU GL 창의 renderer·RGBA와 실제 화면을 대조하고, VirGL 서버·소켓 준비와 실제 virpipe 픽셀 성공을 구분한다. GL 실패 시 Cairo 설명 창과 같은 Linux 세션 유지도 확인한다. 재검사는 기존 앱을 다시 시작하지 않아야 한다. EGL gate 실패만으로 실기기 GPU를 미지원으로 판정하지 않고 EGL version/vendor/extensions·GLES3 지원을 별도로 기록한다.
- GLES는 Linux가 만든 화면의 Android 출력에 사용한다. Linux 앱·Sway·WebKit의 기본 렌더링은 소프트웨어다. CPU GL 또는 VirGL 한 창 검사 성공을 브라우저 동영상 가속·일반 다중 창·GPU 게스트 공유의 수락으로 확대하지 않는다. TB522FU의 Adreno/KGSL·root·Shizuku·원격 경로를 시험하려면 [각 방법의 조건](capability-fallback-validation.md)을 먼저 준비한다.

## 클립보드·파일·자원

Android→Sway와 Sway→Android 각각 한국어·이모지, 64KiB 한계, 비움(clear), URI 등 지원하지 않는 형식, 앱 포커스 밖에서의 접근 금지를 검사한다. 양쪽에서 과거 값을 다시 복사하는 A→B→A와 포커스 복귀도 확인한다. ClipboardManager 실제 내용은 영수증에 기록하지 않는다. `/mnt/shared`의 Linux 파일과 Android 문서 제공자가 같은 내용을 보고 쓰는지, 광범위 저장소 권한 없이 열리는지 확인한다.

화면이 켜진 상태와 꺼진 상태에서 stock 대비 같은 조건·기간으로 프레임 지연, 메모리, 발열, 배터리, suspend/resume을 측정한다. Android 출력 렌더러와 실제 GL 장치를 함께 기록하고, CPU나 소프트웨어 GL의 성능을 하드웨어 GPU 결과로 표현하지 않는다. Omarchy 원본 Arch/Hyprland 전체 기능·VS Code 확장·Linux 오디오와 알림 브리지도 수락 범위가 아니다. Deskweft에서 보인 Lenovo OEM 설정 helper는 Shizuku/ADB shell 권한이 필요한 별도 경로다. 기본 제품 성공의 전제 조건으로 설정을 쓰거나 복원하지 않는다. OEM 키가 시스템에 선점되면 사용자가 승인한 별도 실험으로 원인·변경·복원 절차를 기록한다.

## 중단된 X11 실험의 경계

Termux:X11/i3는 **Wayland 세션이 아닌 중단된 별도 실험**이다. 일반 앱 메뉴·설정과 별도 홈 런처에서 제외했으며 이 Wayland 실기기 점검의 준비·통과 조건이 아니다. 기존 소스·준비 기록·실패·부분 검증은 [X11 실험 기록](native-termux-validation.md)에 보존한다. 실험의 시작·입력·종료 결과를 Wayland 세션이나 Y900 물리 수락으로 대신 쓰지 않는다. 기존 Termux 설치·데이터·권한·입력 설정을 변경할 필요가 없다.


## 2026-10-08 내부 Android 창 후속15

[실제 inside15](../build/diagnostics/y900-android-inside-runs-20261008-01/inside15/receipt.json)에서 공개 Android 앱의 원래 프레임을 관리된 GTK Wayland 창에 표시하고 고정 클릭/F12를 왕복한 본문은 통과했다. 전체는 원래 포커스 창 소실로 FAIL이다. Notion/Chrome 제품 지원·임의 입력·물리 presentation·성능 수락은 아니다. 설정118/서비스/역할/제품0589 보존과 소유 task/display/GTK/파일 정리는 통과했다.

호스트 session/protocol의 [실제 Java93개 검증](../build/diagnostics/android-inside-host-java-20261008-01/receipt.json)은 통과했지만 현재 APK의 AndroidApps.launch에는 아직 연결하지 않았다. resize/focus/close/reconnect·지원 앱·권한 backend/adapter와 원래 창 소실 원인 확인이 남아 있다. 상세 기록은 [내부 표시 조사](research/android-app-inside-wayland-20261008.md)에 있다.

## 2026-10-08 내부 Android 창 후속16

[inside16](../build/diagnostics/y900-android-inside-runs-20261008-01/inside16/receipt.json)은 공개 Android 앱의 원래 화면·고정 클릭/F12·3프레임의 Wayland draw ACK·소유 시험 터미널로의 포커스 복귀·정리를 전체 통과했다. 설정118·서비스·역할·제품0589를 보존했다. 지속 프레임, 임의 좌표와 키, resize/reconnect, 실제 Notion/Chrome 및 물리 장치 입력·성능은 별도 검사로 남긴다.

[외곽 anchor 기록](../build/diagnostics/y900-android-inside-runs-20261008-01/inside16-anchor/receipt.json)은 원래 창이 `org.omarchy.screensaver`였음을 보존했다. 해당 고정 원본 스크립트는 포커스를 잃으면 종료하며 설치본 SHA도 일치했다. 외곽 검사와 이전 class 미기록 실행의 FAIL을 소급 변경하지 않는다.
