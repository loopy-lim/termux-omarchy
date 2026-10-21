# Android 위의 Loopy Desktop

사용자는 터미널 시연을 완료로 취급하지 말고 Omarchy 수준의 실제 화면과 키보드·트랙패드 사용 경험까지 구현하라고 명시했다. 2026-10-05 최종 지시에 따라 이전 확장 중단을 취소하고 제품 구현을 재개한다. Y900 실기기 수락은 사용자가 추후 수행한다.

실행 화면은 Sway가 합성한 실제 Wayland 데스크톱이다. 앱을 켜면 전체 화면, 타일링 창, 작업공간 1–9, 앱 런처와 창 선택기를 제공한다. Linux GUI 파일 관리자와 편집기, 터미널, 개발 도구, Android 앱을 같은 런처에서 연다. Android 앱은 원래 Android 창에서 실행하며 돌아왔을 때 Linux 창과 작업을 유지한다.

## 입력 소유권

앱의 Surface 이벤트 처리와 Android 시스템 우선권 처리를 분리한다. 선택 가능한 접근성 서비스는 데스크톱이 보이고 포커스를 가진 동안만 키를 시스템 정책·IME·앱 이전에 받아 전달한다. Android 14+에서는 mouse/touchpad motion sources도 요청해 해당 입력을 시스템 대신 처리한다. 포커스 해제, 태블릿 전환, Surface 분리, 종료에는 입력 소유권을 즉시 반납한다. Android 기본 Back/Home/전원 키는 유지한다. Android 13 이하에는 이 motion API가 없으며 숨겨진 원시 접점을 만들어 지원한다고 표시하지 않는다.

키보드: 물리 장치별 held/release, Caps 탭 한/영 전환, Caps+HJKL 이동, Ctrl+Alt/Super/Alt 설정, 창 열기·포커스·이동·작업공간·전체 화면·크기 변경. 한국어 두벌식 조합을 순수 모듈에서 처리하고 실제 inner Sway에 Unicode를 전달한다. Android IME InputConnection의 조합·commit도 별도 지원한다.

Android 앱으로 이동해도 실행 중인 데스크톱으로 돌아오는 선택된 단축키는 유지한다. 접근성 서비스가 켜져 있고 모드가 태블릿이 아닐 때 설정한 조합의 Space(런처), Tab(창 목록), 쉼표(설정), 1–9(작업공간)가 데스크톱을 앞으로 가져온다. Meta를 선택하면 Meta 키도 이 경로가 소유해 Android의 예약 동작과 충돌을 줄인다. 이 예외는 일반 타이핑이나 배경 포인터를 데스크톱에 전달하지 않는다. 태블릿 모드·세션 종료·서비스 비활성화는 이 전역 경로도 해제한다. OEM 예약 키와 배경 Activity 실행 제한은 연결한 운영체제에서 확인한다.

포인터: 마우스/트랙패드 이동, 클릭, 가로·세로 스크롤, 속도와 자연스러운 스크롤, 상대 포인터 캡처, 전달된 다중 접점의 두 손가락 스크롤·관성·세 손가락 작업공간/창 선택. 시스템에서 접점을 변환한 경우 중복 처리하지 않는다. 접근성 우선권과 실제 raw 접점 수신 상태는 다른 capability다.

모드: 수동 태블릿/데스크톱과 자동 전환. 자동은 키보드 **또는** 포인터 연결을 기준으로 한다. 분리 때 해당 장치의 held 입력을 해제하고 Android 태블릿으로 복귀한다. 세션을 명시적으로 종료하지 않으면 unsaved Linux 앱을 보존한다.

## 세션과 데이터

Foreground service가 Linux 프로세스 트리와 Wayland host를 소유한다. Activity는 Surface attachment만 소유한다. Native host는 headless detach 중 socket, 클라이언트, 창과 크기를 유지하고 재연결하면 같은 클라이언트에 resize/repaint를 보낸다. 강제 프로세스 종료와 OEM 메모리 회수는 메모리를 보존할 수 없으므로 재개를 가장하지 않는다.

영속 HOME과 공유 폴더를 rootfs 버전과 분리한다. Android 문서 제공자와 Linux `/mnt/shared`가 같은 파일을 열며 광범위 저장소 권한을 요구하지 않는다. session UUID로 clipboard·런처·명령 IPC를 분리한다. UTF-8/파일 크기·큐·경로와 action allowlist를 제한하며 셸 문자열을 평가하지 않는다.

## 제품 모듈

- Android: MainActivity, DesktopMenus, ModePolicy, InputPriorityService, KeyboardRouter, PointerRouter, GestureRecognizer, HangulComposer, DesktopInputConnection.
- 세션: DesktopSessionService, RuntimeSession, HomeDirectory, DesktopSurface, NativeBridge.
- 연동: DesktopCommands, AndroidApps, DesktopClipboardBridge, SharedFilesProvider.
- Guest: Sway 설정, launcher/overview, GUI/TUI 앱, 3개 테마, clipboard/action workers.
- 패키징: 공식 ARM64 고정 패키지와 검증·제한된 안전 추출. 코드 파일은 500줄 이하.

## 증거와 한계

빌드와 자동 검사는 구현이 실행 가능한지 확인한다. 물리 키보드·트랙패드, OEM 예약 키, Y900 운영체제와 GPU/배터리 성능은 아직 실기기 수락이 아니다. 이 배포는 Omarchy의 사용 경험을 목표로 하는 Sway 기반 Android 제품이며, Omarchy 원본 Arch/Hyprland 배포를 설치했다는 주장을 하지 않는다. CPU shm 렌더러이며 GPU 가속을 주장하지 않는다.
