# Loopy Desktop — Android 위의 Linux Wayland 데스크톱

**2026-10-19 저장소 재구성:** 이 프로젝트는 이제 Termux 경로만 유지한다. 예전 APK 방식의 Android 앱(`android/src`·`res`·manifest와 그 전용 빌드·프로브·VM 도구와 테스트)은 삭제했고, `android/assets`는 현재 Termux 설치가 쓰는 페이로드 저장소로 남긴다. 아래의 APK 시절 기록은 검증 이력 문서로만 남는다.

**최신 설치 확인:** [4K120 HiDPI 실제 휠 스크롤 개선과 검증 범위](docs/validation/2026-10-12-scroll-responsiveness.md). 기기에 반영된 소스 해시와 실행 상태는 [최종 설치 기록](docs/validation/2026-10-12-installed-scroll-health.json)에 있습니다.

**현재 Y900 사용 경로(2026-10-12):** Termux 기반 Arch ARM64·Hyprland·원본 Omarchy입니다. Chromium·VS Code 실행과 실제 Tailscale Remote-SSH 연결을 확인했습니다. 아래 APK 및 이전 날짜의 시험은 개발 이력이며 현재 Termux 설치본과 구분합니다. [10월 12일 성능 개선](docs/validation/2026-10-12-termux-performance.md)에서는 연결 감시 누수·좀비 회수·유튜브 코덱 선택을 수정했습니다. 실제 원격 편집은 SSH 인증 후 추가 검증이 필요합니다.

**2026-10-08 Y900 검증 진행:** 제품 `1148c45e…`에서 복구 후 입력 유지·Esc·Alt+Tab·숫자 조합 30개와 실제 Linux SSH 접속·서버 키 거부·연결 실패·재접속을 확인했습니다. GPU를 새로 시작한 같은 제품의 전체 출력은 약 17.57 FPS로 60/144 FPS 목표에 미달했습니다. 임시 진단 APK에서 Linux stderr 수집을 연결해 공통 구간의 6단계를 모두 측정했으며 약 16.79 FPS였습니다. 기존 구간 밖의 GTK 처리와 컴포지터 업로드를 추가 조사합니다. 현재 태블릿에는 [GTK 아이콘 경로 수정본 `7c14004c…`](build/deliverables/LoopyDesktop-2026-10-08-gtk-icon-data-arm64/README.md)을 설치했고 기본 PDF 실행·정리·복원을 확인했습니다. 같은 APK에서 Wi-Fi 설정 열기·Notion 앱/웹 실행·Linux 복귀와 DNS·HTTPS 6개 검사를 통과했습니다. Wi-Fi 재접속과 Notion 문서 편집은 별도입니다. 이전 제품에서는 실제 앱 권한의 셸 반복 실행 8회에서 미회수 자식이 모두 0개였고, 새 제품의 SSH 연결·오류·재접속도 통과했습니다. [이번 실제 측정과 남은 작업](docs/validation/2026-10-08-tablet-stage-progress.md), [전체 검증 범위](docs/y900-tablet-final.md), [제품 APK와 기록](build/deliverables/LoopyDesktop-2026-10-08-recovery-input-arm64/README.md). 아래 후보 설명과 이전 설치본 시험은 당시의 이력입니다. 전체 Omarchy 지원은 개발 중입니다.

Y900 13에서 실제 Arch ARM64·Hyprland·Quickshell을 실행하고 **원본 Omarchy 전체 기능**과 Wayland·GPU·물리 키보드·마우스를 지원하는 프로젝트입니다. [전체 설계와 검증 조건](docs/superpowers/specs/2026-10-06-omarchy-full-design.md)을 기준으로 개발 중입니다. 현재 Y900 설치본은 **Arch ARM64·Hyprland·Omarchy** 세션이며, 기존 Alpine·Sway 경로도 별도로 남아 있습니다. Android는 화면 출력과 입력·클립보드·파일·Android 앱 연결을 맡습니다. 터미널만 보이는 초기 구현과 [첫 데스크톱 후보](docs/desktop-experiment-status.md)는 개발 이력입니다.


이전 Y900 설치본 `8843feae…`는 Android 16의 파일 API 오류로 준비가 멈추던 문제와 기본 그림 누락으로 화면 보호기가 오류를 반복하던 문제를 수정했습니다. 원본 Omarchy 이미지 설치·Hyprland·Quickshell 바·Wayland Foot·원본 화면 보호기 표시 및 ADB Esc 종료를 실기기에서 확인했습니다. **기본 프로세스 한도 32에서는 Android가 세션을 종료했고, GUI 검증은 임시 한도 128 조건입니다.** 테스트 세션을 종료하고 한도 32·기존 한글 입력 설정을 복구했습니다. 물리 클릭·실제 키보드 단축키·전체 서비스·GPU 성능 수락은 남아 있습니다. [최신 실기 범위](docs/y900-tablet-final.md), [정확한 APK](build/deliverables/LoopyDesktop-2026-10-07-omarchy-branding-native-arm64/README.md).

이전 내부 후보 `21db516d…`는 전달에 성공한 첫 환영·Wi-Fi·업데이트 안내를 항목별로 기억해 재시작 때 중복하지 않습니다. 실패한 전달은 재시도하며, 전체 Linux 설정을 완료로 위장하지 않습니다. 관련 호스트 검사 9개와 SDK 빌드, 원본 알림 서버의 반복 호출 및 재시작 하위 검증을 통과했습니다. 원본 이미지·HOME·설정을 보존했습니다. **알림이 없는 재시작 화면에서도 메뉴가 희미해 표시·성능 문제는 남아 있습니다.** 현재 APK의 메뉴 선택·Writer 실행, 전체 원본 서비스·Y900/GPU 수락은 완료하지 않았습니다. [정확한 성공·실패 범위](docs/validation/2026-10-06-omarchy/checkpoint-omarchy-first-run-notices.json), [내부 후보 설명](build/deliverables/LoopyDesktop-2026-10-07-first-run-notices-arm64/README.md). 이전 [첫 요청 후보 기록](docs/validation/2026-10-06-omarchy/checkpoint-omarchy-plugin-startup.json)은 별도로 보존합니다.

이전 [Linux 진입 APK](build/deliverables/LoopyDesktop-2026-10-07-native-desktop-entry-arm64.apk)는 메뉴를 닫은 뒤 키 입력이 Android 버튼에 남던 문제, Omarchy에서 Sway로 전환한 뒤 새 화면이 연결되지 않던 문제, 첫 프롬프트의 Git 초기화 오류를 수정했습니다. 정확한 `f2230c97…` APK의 일반 Android 앱 UID 10224에서 실제 제품 메뉴로 Omarchy 진입·Foot 합성 키 명령 실행·Sway 복귀·두 HOME 보존과 긴급 입력 해제 뒤 화면 재생성을 검증했습니다. 기본 프로세스 한도 32에서 45초 관찰도 통과했지만 장시간 안정성이나 Y900 성능 수락은 아닙니다. 사용자 `.zshrc`·tmux·KeyBridge 설정을 유지하며 빠른 Linux 프롬프트와 Mac 전체 외형을 선택할 수 있습니다. [현재 산출물·검증·남은 작업](build/deliverables/LoopyDesktop-2026-10-07-native-desktop-entry-arm64/README.md), [체크포인트](docs/validation/2026-10-06-omarchy/checkpoint-product-omarchy-entry.json).

클립보드 개선 후보 `ebf0e9fd…`는 원본 Hyprland에서 선택 내용을 비울 때 WLR/ext 구독자에게 알림을 보내지 않던 문제를 수정했습니다. 검증된 실행 파일만 별도로 연결해 기존 전체 이미지와 HOME을 보존합니다. 호스트 39개 검사, 실제 ARM64 컴포지터의 12개 프로토콜 검사와 정확한 제품 APK의 Android↔Foot 한글·이모지·반복 복사·양방향 비우기가 통과했습니다. 기본 프로세스 한도 32에서 45초 세션 관찰, Sway 복귀 및 기존 UID·13개 파일 해시 보존도 확인했습니다. [클립보드 실행 기록](docs/validation/2026-10-06-omarchy/checkpoint-omarchy-clipboard.json).

[연속 입력 개선 후보](build/deliverables/LoopyDesktop-2026-10-07-native-input-burst-arm64/app.apk) `58926891…`는 Android에서 한꺼번에 들어온 키 이벤트가 256개 큐를 넘쳐 버려지던 문제를 수정했습니다. 최대 4,096개로 용량을 늘리고 기존 넘침 시 입력 해제 처리는 유지했습니다. 정확한 제품 APK에서 이전에 실패한 366개 이벤트와 2,050개 이벤트 입력이 통과했고, 실제 Foot에서 1,025바이트가 정확히 기록됐습니다. 누적 4,616개 입력의 큐 누락·넘침은 0이었으며 클립보드 왕복, 기본 한도 32의 45초 관찰과 Sway 복귀도 통과했습니다. 과거 혼합 IME 실패는 앞선 `ebf0e9fd…` 클립보드 후보의 두 비교 실행에서 재현되지 않았지만 원인은 아직 확정하지 않았습니다. 장시간 안정성·원본 앱과 서비스 전체·Y900 GPU 및 물리 입력 성능은 남아 있습니다. [정확한 산출물과 검증 범위](build/deliverables/LoopyDesktop-2026-10-07-native-input-burst-arm64/README.md), [입력 검증 기록](docs/validation/2026-10-06-omarchy/checkpoint-omarchy-key-burst.json).

이전 복구 검증 후보 `920f4d67…`는 화면 처리기 종료 시 이전 입력 처리기와 준비 표시를 회수하고, 재시작 전 입력이 새 창으로 넘어가지 않도록 합니다. 호스트 53개 검사와 실제 ARM 재시작·화면 연결 교체 검증을 통과했습니다. Android에서도 이전 처리기 종료, 원본 복구 창 표시, 전체 화면 유지를 확인했습니다. 다만 **Load config 이후 새 입력 처리기 시작에 실패했습니다.** 기본 프로세스 한도에서 Linux 부모가 정리된 별도 실행도 보존했습니다. [이전 후보의 정확한 결과](docs/validation/2026-10-06-omarchy/checkpoint-omarchy-worker-generation.json).

후속 [복구 시작 수정 후보](build/deliverables/LoopyDesktop-2026-10-07-safe-mode-start-arm64/README.md) `b9b9d0c5…`는 원본 복구 창의 Load config 뒤 사용자 설정의 시작 이벤트가 누락되던 문제를 실제 ARM 환경에서 재현하고 수정했습니다. 일반 설정 새로고침에서는 시작 이벤트가 중복되지 않습니다. Android 전용 에뮬레이터의 **임시 프로세스 한도 128** 조건에서 원본 복구 창 클릭, 새 입력 처리기 시작, 복구 후 Foot 명령과 Sway 전환이 통과했습니다. 기본 한도 32의 비교 실행은 Linux 부모가 강제 종료되어 실패했습니다. 시험 후 원래 정책·UID·16개 HOME/이미지 파일 해시를 확인하고 소유한 Linux 프로세스를 회수했습니다. 기본 정책 안정성과 Y900 실기·GPU·전체 Omarchy 수락은 남아 있습니다. [정확한 두 비교 실행과 소스](docs/validation/2026-10-06-omarchy/checkpoint-omarchy-safe-mode-start.json).

[X11 시작 수정 후보](build/deliverables/LoopyDesktop-2026-10-07-x11-identity-arm64/README.md) `afb61a35…`는 Xwayland가 키보드 컴파일러를 실행하기 전에 현재 UID/GID를 다시 설정하다 실패하던 문제를 수정했습니다. 실제 커널 ID 네 값이 모두 요청한 값과 같은 경우만 처리하며, root·다른 ID 요청은 거부합니다. 정확한 APK에서 ID 보존·변경 거부·기존 SIGSYS 검사와 원본 Hyprland의 실제 X11 연결이 통과했습니다. 임시 한도 128 조건에서 장애 복구 후 Foot 입력과 Sway 전환도 유지됐고, 종료 후 한도 32와 기존 데이터·권한을 확인했습니다. 원본 X11 앱의 창·입력 전체, 기본 정책 안정성, Y900 GPU·물리 입력은 후속 검증 대상입니다. [정확한 실패·수정·실행 증거](docs/validation/2026-10-06-omarchy/checkpoint-omarchy-x11-identity.json).

[원본 앱 시작 호환 후보](build/deliverables/LoopyDesktop-2026-10-07-kernel-version-arm64/README.md) `ec687259…`는 Android의 `/proc/version` 제한 때문에 LibreOffice 원본 실행 도우미가 중단되던 문제를 수정했습니다. 실제 커널 정보를 그 한 경로에 제공하며 원본 이미지와 HOME을 보존합니다. 전용 에뮬레이터에서 Qt 6/X11과 **Qt 6/Wayland 직접 연결** 모두 원본 Writer의 문서 클릭·Alt+A·입력·Alt+S 저장 및 ODT 내용 대조를 통과했습니다. 시험에서 Qt 백엔드와 Mac 배열을 선택했고 임시 프로세스 한도 128을 사용했으며, 종료 후 기존 설정·한도 32로 복구했습니다. GTK 이미지 로더 실패, 일반 앱 실행의 기본 백엔드 반영, 기본 정책 안정성과 실기 GPU·물리 입력은 남아 있습니다. [정확한 비교·보존 기록](docs/validation/2026-10-06-omarchy/checkpoint-omarchy-kernel-version.json).

[일반 앱 실행 후보](build/deliverables/LoopyDesktop-2026-10-07-app-launch-arm64/README.md) `e9718501…`는 원본 호출부 32개의 Android 세션용 사본과 기본 Qt 6/Wayland 실행 설정을 연결했습니다. 원본 이미지·UWSM·사용자 설정을 보존하며, 호스트 8개 검사와 SDK 빌드가 통과했습니다. 전용 에뮬레이터에서 실제 데스크톱 항목으로 연 Writer의 입력·ODT 저장, 원본 앱 메뉴의 검색·실행·Ctrl+Q 정상 종료를 확인했습니다. 메뉴 검증은 플러그인 등록을 기다린 조건이며, 시작 직후 요청 누락·중복 초기 안내·Cmd+Q의 창 단위 종료는 남아 있습니다. 임시 한도 128과 Mac 배열을 사용한 뒤 원래 설정·한도 32로 복구했습니다. 전체 서비스·기본 정책 안정성·Y900 GPU/물리 입력 수락은 별도입니다. [정확한 성공·실패와 보존 기록](docs/validation/2026-10-06-omarchy/checkpoint-omarchy-app-launch.json).

아래는 이전 단계별 검증 이력입니다. 각 기록의 APK·이미지·조건을 현재 APK의 전체 기능·물리 입력·GPU 검증으로 합치지 않습니다.

별도 Omarchy 이미지의 신뢰된 카탈로그·Android 설치 화면·서비스·JNI 추출을 연결했습니다. 전용 Android VM에서 실제 문서 선택기로 전체 2.6GB 이미지와 921개 패키지를 설치하고 Arch zsh·tmux·Neovim을 앱 UID로 실행했습니다. 최신 시험은 원본 Hyprland Lua 전체와 원본 Quickshell 자동 시작을 실행해 Android Surface의 실제 화면, 물리 클릭 형태의 합성 이벤트, 숫자 키 10개 전환·창 이동, 바·메뉴·OSD와 입력 복귀를 확인했습니다. 원본 키코드와 추가 키 이름의 중복 등록을 수정해 Meta+Shift 창 이동이 작업공간을 따라가지 않습니다. 이 실행은 소프트웨어 렌더링과 VM의 임시 자식 프로세스 한도 128 조건이며, 끝난 뒤 기존 한도 32로 복구했습니다. 기본 한도에서 Android가 Linux 프로세스를 종료하는 문제, 제품의 Omarchy 활성화·되돌리기 UI, 전체 앱·서비스, Adreno와 Y900 물리 입력·성능 검증은 계속 진행 중입니다. [현재 실행과 정확한 APK](docs/validation/2026-10-06-omarchy/checkpoint-original-session-tablet-input.json), [설치 경로](docs/omarchy-android-installation.md).

명시적인 Omarchy 실행 API에 기존 Linux HOME과 분리된 영구 HOME을 연결했습니다. 실제 Android 앱 권한에서 원본 설정 10,077항목·약 58.6MB의 모든 파일 해시, 링크, 기존 HOME과 새 설정의 재시작 보존을 확인했습니다. [HOME 검증 기록](docs/validation/2026-10-06-omarchy/checkpoint-separate-omarchy-home.json)을 보존하고, [새 후보](build/deliverables/LoopyDesktop-2026-10-07-omarchy-tablet-input-bridge-arm64.apk)에 원본 감독 스크립트의 Android 파일 로그와 최종 태블릿 입력 설정을 추가했습니다. 데스크톱 활성화 UI 연결은 계속 진행 중입니다.

기본 실행 경로는 **Loopy Desktop → Wayland 호스트 → Sway**입니다. Termux:X11/i3는 Wayland 세션이 아닌 [중단된 별도 실험](docs/native-termux-validation.md)이며 일반 앱 메뉴·설정·별도 홈 런처에서 제외했습니다. Termux 설치는 기본 데스크톱 사용에 필요하지 않습니다.

원본 Omarchy 세션에서 Android `KeyboardRouter`와 실제 명령 큐를 거쳐 Meta+1…0 작업공간 전환·Meta+Shift+1…0 창 이동을 추가로 검증했습니다. 원본 Hyprland 소켓에 직접 연결하는 작업자는 세션별 순서·용량·응답 시간을 제한하고, 명령마다 별도 프로세스를 만들지 않습니다. [작업자 실행 기록](docs/validation/2026-10-06-omarchy/checkpoint-production-omarchy-actions.json)은 정확한 별도 검증 APK에 해당합니다. 현재 제품 후보에는 해당 구현을 포함하지만 제품 프로필 선택·전환 복구, 전체 앱 실행과 실사용 성능 검증은 진행 중입니다.

실제 Qt Wayland 입력창에서 Alt+C/V, 잘라내기, 실행 취소·다시 실행, 한글·emoji 입력과 문자 교체를 확인한 [기존 실행 기록](docs/validation/2026-10-06-omarchy/checkpoint-original-omarchy-editing.json)을 보존했습니다. 이 검증은 원본 설정을 읽은 별도 래퍼와 모니터 배율 1의 조건입니다. 후속 제품 세션 준비·실행 경로와 원본 자동 배율 2를 그대로 사용한 시험은 Qt 창 포커스에서 실패했고, 전체 화면 패널과 SHM 출력의 상하 반전을 발견했습니다. 행 순서를 수정한 새 Hyprland는 실제 Linux 출력 비교와 Android Surface의 위쪽 빨강·아래쪽 초록 검사를 통과했습니다. Android 비교는 기존 설치 이미지에 별도 바이너리를 사용한 조건입니다. 작은 시험 화면에서 첫 클릭과 Escape 뒤 클릭은 실패했지만, 원본 알림을 정상적으로 닫은 뒤 같은 지점을 클릭하면 Qt 포커스·Alt+C/V·잘라내기·실행 취소·한글·emoji 입력 및 foot 입력 복귀가 통과했습니다. [정확한 비교 결과](docs/validation/2026-10-06-omarchy/checkpoint-production-omarchy-launch.json)를 보존했습니다. 이후 전체 이미지 설치·제품 Omarchy 활성화·Android↔Linux 클립보드 교환은 위 제품 체크포인트에서 별도로 검증했습니다. 모든 앱의 편집 동작, GPU와 물리 태블릿 검증은 남아 있습니다.

기본 화면에는 검색 가능한 앱 메뉴와 왼쪽 작업공간 바가 있고, WebKit 기반 Loopy Browser·Geany 코드 편집기·Mousepad·Thunar·foot·개발 도구를 엽니다. 오른쪽 위 상태 표시와 트레이는 제거했습니다. 설치된 Linux `.desktop` 앱도 안전하게 해석할 수 있는 명령에 한해 검색합니다. Firefox의 GUI 시작 실패를 보존하고 브라우저를 교체하고 주소창·탭·단축키를 관리하는 GTK 화면을 연결했습니다. Android 앱은 앱 목록에서 선택하면 원래 Android 창으로 열리며 Linux 세션은 서비스에서 유지됩니다. Android EGL/GLES로 공유 메모리 표면의 합성과 출력을 처리하고, 실패하면 CPU로 복귀합니다. Linux Sway·브라우저 자체 렌더링은 소프트웨어 경로입니다.

- [한국어 빠른 시작](docs/desktop-quickstart-ko.md)
- [구현·검증 범위](docs/runtime-implementation.md)
- [GPU·입력 대체 방법과 최종 검증](docs/capability-fallback-validation.md)
- [데스크톱 개발 이력](docs/desktop-experiment-status.md)
- [Y900 실기기 점검](docs/y900-test-checklist.md)
- [Y900 실기기 결과·현재 업데이트·남은 검증](docs/y900-tablet-final.md)
- [기존 프로젝트 비교](docs/existing-projects.md), [Deskweft 재사용 조사](docs/research/deskweft-reuse.md)
- [Y900 13 대상 Wayland·원격 화면 APK](build/deliverables/LoopyDesktop-2026-10-06-y90013-wayland-remote-arm64.apk)
- [이번 입력·태블릿 검증](docs/wayland-native-validation.md)
- [TB522FU OS 경로와 확보 조건](docs/research/loopy-os-paths.md)

대상은 사용자가 지정한 **Y900 13 (TB522FU · Snapdragon 8 Elite · Android 16 · 3840×2560)**입니다. 실기기에서 Wayland 데스크톱, 물리 키보드, Alt+C/V, zsh·tmux와 AstroNvim 시작을 확인했습니다. 이후 보고된 물리 클릭·숫자 단축키·문자 입력 지연의 수정과 남은 실기기 검사는 [현재 Y900 기록](docs/y900-tablet-final.md)에 구분합니다. 최신 후보의 APK 빌드·호스트 검사와 기존 설치 APK의 실기기 성공은 별개입니다. 이전 APK 결과는 [대체 경로 이력](docs/capability-fallback-validation.md)과 [앱 확장 이력](docs/desktop-app-extension-validation.md)에 보존합니다.

## 실행 경험

앱 시작 시 데스크톱 화면으로 들어갑니다. 기본 창 관리 키는 `Ctrl+Alt`이며 설정에서 Meta 또는 Alt로 바꿀 수 있습니다. `Ctrl+Alt+Space`는 Sway 앱 메뉴, `Ctrl+Alt+Enter`는 foot, `Ctrl+Alt+E`는 파일 관리자, `Ctrl+Alt+Shift+E`는 GUI 편집기, `Ctrl+Alt+Shift+C`는 Geany, `Ctrl+Alt+1…9`는 작업공간입니다. [전체 키 목록](guest/desktop/root/Keyboard.md)을 참고하세요. Caps를 짧게 탭하면 한/영을 전환하고, Caps를 누른 채 H/J/K/L로 방향키를 보냅니다. 길게 누르기만 한 Caps는 언어를 바꾸지 않습니다.

터치·마우스·트랙패드와 Android IME 텍스트 입력을 연결합니다. 물리 장치의 첫 연결에 **실사용 준비 · 권한/진단**을 안내하며 설정에서 다시 열 수 있습니다. 접근성 입력 우선권·세션 알림·선택적 배터리 예외와 기본 홈 역할을 Android 승인 화면에 연결합니다. 전체 화면의 활성 데스크톱에서는 물리 마우스 캡처를 요청하고, **Ctrl+Alt+Esc**로 Linux 세션을 유지하면서 입력을 반납합니다. 선택적 **Loopy 입력 우선권**은 전달된 물리 키를 먼저 처리하며, OEM 예약 키 회수와 Android 14+ 원시 트랙패드 접점은 기기마다 다릅니다. Y900 기본 입력과 클립보드는 실기기에서 확인했고, 최신 물리 클릭 수정·숫자 단축키·예약 키 전체 회수는 추가 검증이 필요합니다.

**메뉴 → 앱**은 Android 측 빠른 메뉴이고 `Ctrl+Alt+Space`는 Linux Sway 안의 앱 메뉴입니다. **메뉴 → Android로 돌아가기** 또는 자동 분리 전환에서는 화면과 입력 소유권을 반납하지만 실행 중 Linux 앱은 유지합니다. **세션 종료**는 Linux 프로세스를 명시적으로 종료합니다. Android의 프로세스 강제 종료나 메모리 회수 뒤까지 실행 메모리를 복구한다고 주장하지 않습니다.

전체 화면 오른쪽 아래 **메뉴**로 키보드 표시·창 조작·설정·Android 복귀·세션 종료를 사용할 수 있다. 터치 탭/드래그·두 손가락 스크롤/우클릭, 한글/emoji IME 순서, 저장되는 100~200% 배율을 제공한다. IME의 **총 64KiB**는 Android 입력 정책의 크기 상한이다. 활성 Wayland 입력 필드에는 확정 문자열을 직접 전달하며, 요청당 UTF-8 4,000바이트 한계는 문자 경계를 지켜 내부 분할한다. 이 경로를 지원하지 않는 앱에서 사용하는 가상 키보드 대체 경로는 Linux 세션 동안 서로 다른 문자 기호를 **최대 4,073개** 추가할 수 있다. 용량을 넘는 작업은 삭제·문자 전송 전에 거절한다. 일부 입력이 이미 적용된 오류에서는 현재 창을 확인해야 하며 자동 재전송하지 않는다. 실제 전달 성공·속도·Unicode 범위는 앱과 기기에서 별도로 검증하며, 물리 키 이벤트는 별도 경로다. Android 앱은 독립 task로 열며 공유 문서 제공자는 Linux `/mnt/shared`와 같은 파일을 사용한다.

**Linux 전용 · 화면 고정**은 사용자가 Android 확인을 허용하면 Home/최근 앱 전환을 제한한다. Ctrl+Alt+Esc와 터치 메뉴로 고정을 해제하며 같은 Linux 세션을 유지한다. 관리 기기 Lock task와 일반 화면 고정은 구분한다. 전원/OEM 키와 시스템의 고정 해제 경로는 남는다.

**원격 연결 · SSH**는 실제 OpenSSH를 foot에서 열고 서버 지문·인증을 터미널에서 확인한다. 최근 주소·사용자·포트만 저장하며 ssh/scp/sftp/ssh-keygen이 포함된다. 연결 실패 메시지는 터미널에 남긴다. **원격 화면 · RDP/VNC**는 고정 Remmina를 Wayland 창으로 열어 다른 컴퓨터의 데스크톱에 접속한다. 주소·사용자만 저장하며 비밀번호 저장, 클립보드와 폴더 공유는 기본으로 끈다. 인증은 Remmina에서 진행한다. 태블릿을 원격 서버로 공개하는 기능은 포함하지 않는다. [원격 화면 사용법과 검증 범위](docs/remote-desktop.md).

GPU나 입력 기능이 제한되면 **GPU alternatives / check** 또는 **실사용 준비 → 대체 방법**에서 현재 검사 결과와 다음 경로를 확인합니다. CPU GL은 `llvmpipe → softpipe → Cairo` 순서로 새 세션에서 선택하며, 준비된 VirGL은 사용자가 선택한 창 검사에만 적용합니다. [전체 방법과 필요한 조건](docs/capability-fallback-validation.md)을 구현 여부와 함께 제공합니다.

## 빌드와 VM 시험

충돌 복구 개발 후보 `b66b68b2…`에는 원본 Hyprtoolkit의 공유 메모리 출력과 버퍼 반환 처리가 추가됐습니다. ARM Linux에서 원본 복구창, 실제 클릭·키 입력, 상하 방향·색상·버퍼 재사용 검증을 통과했습니다. 일반 Android에는 기존 이미지와 설정 16개 해시를 보존하며 별도 라이브러리로 연결했고, 정상 진입·터미널 입력·기본 프로세스 제한 관찰을 통과했습니다. 충돌 뒤 이전 입력 프로세스가 남아 전체 화면이 풀리는 문제는 미해결입니다. 별도 PRoot 경로에서 복구창을 조회하는 검사도 연결에 실패해 Android 복구창은 아직 미검증이며, 완성본으로 승격하지 않았습니다. [정확한 진행·실패·보존 기록](docs/validation/2026-10-06-omarchy/checkpoint-omarchy-toolkit.json).

macOS ARM64, Python 3.11 이상, JDK, Android SDK/NDK 27.1.12297006, Rust의 `aarch64-linux-android` target이 필요합니다. 고정된 Alpine 패키지·해시는 `third_party/` 잠금 파일에 있습니다. 도구 확인은 `./dev/build --check-tools`입니다.

```sh
python3 tools/fetch_runtime.py
python3 tools/prepare_desktop.py
./dev/native-build
# 선택적 Android VirGL 서버를 포함하려면 실행
python3 tools/build_virgl_android.py
ANDROID_NDK_HOME="$HOME/Library/Android/sdk/ndk/27.1.12297006" ./dev/build --rootfs build/desktop/rootfs.tar.gz
```

빌드 출력은 `build/loopy-desktop-debug.apk`, `build/loopy-desktop-test.apk`, `build/build-receipt.json`입니다. `dev/build`의 기본 rootfs도 `build/desktop/rootfs.tar.gz`이며, 옵션은 사용할 이미지를 명확히 기록하기 위해 표시했습니다. 패키지 payload를 구성할 때 guest 설치 스크립트·트리거를 실행하지 않습니다.

VM 시험은 명시한 serial에서 `ro.kernel.qemu=1`을 확인하고 빌드 영수증의 APK 해시를 대조한 뒤 설치합니다. 실기기 설치에 이 도구를 사용하지 않습니다.

```sh
./dev/vm-start
# 별도 터미널에서 부팅 완료와 serial을 확인한 다음
python3 tools/prepare_ssh_fixture.py
./dev/app-test --serial emulator-5580 --suite desktop \
  --output docs/validation/new-desktop-run
```

전체 desktop suite는 workspace의 loopback SSH 시험 counterpart를 시작하고 해당 VM의 정확한 포트만 전달·정리한다. 임의 호스트 shell을 실행하지 않는다. 준비 방법과 인증 시험의 경계는 [SSH 문서](docs/remote-ssh.md)에 있다.

`--output` 경로가 이미 있으면 덮어쓰지 않습니다. 최종 실행 전 새 결과 경로를 고르거나 기존 경로의 상태를 확인하세요. VM·앱 시험은 물리 주변 기기의 입력, OEM 단축키, 배터리, 절전 성능의 증거가 아닙니다. 호스트 시험 명령과 책임별 모듈은 [구현 문서](docs/runtime-implementation.md)에 있습니다.

## 기기 정보 수집

Python 3.9 이상과 ADB가 필요합니다. serial을 명시하고 수집 결과를 기기별로 분리합니다.

```sh
adb devices -l
./dev/device-check --serial <ADB_SERIAL> --expect-manufacturer lenovo --expect-model TB522FU
```

이 명령은 읽기 전용이며 설치·권한 변경·root 실행을 하지 않습니다. `receipt.json`의 `complete`는 수집 완료이지 제품 기능 성공이 아닙니다. [Y900 점검](docs/y900-test-checklist.md)에서 연결 전·후·분리 상태를 비교합니다.
