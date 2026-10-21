# 실제 Omarchy의 Y900 지원

사용자 목표: “그러면 태블릿 뗄테니깐 모두 omarchy를 지원해줘.” 이 목표는 기존 Wayland·GPU·태블릿 입력·Mac/KeyBridge 설정·실사용 요구를 포함한다. 태블릿이 분리돼 있어도 구현과 격리된 실행 검증을 계속하며, 연결 부재를 구현 중단 이유로 삼지 않는다. 사용자 요청은 구현을 승인한 범위이며 추가적인 일상 설계 승인 단계로 작업을 멈추지 않는다.

## 결과와 범위

실제 Arch Linux ARM64, Hyprland, Quickshell 및 Omarchy 원본의 앱·스크립트·테마·설정을 실행한다. 기본 소스는 조사 시점 공식 quattro commit `81145eb1fd41532fcae4310b26f860608e2eaf82`이다. 원본 version 파일은 `4.0.0.alpha`이다. 공식 Try Omarchy의 4.0.4 reference는 별도 commit `61d86ed1e691de44f3e50fdef4c78500abcfbf57`이며 원본 Omarchy `c668141e9c42b13c80c9ca4ea108e11708c5e8a5`를 사용한다. 두 소스의 버전·패키지·동작을 혼동하지 않는다.

158개 원본 기본 패키지, 51개 매뉴얼 장과 119개 QML 파일의 기능을 추적한다. 패키지 부재·서비스 부재·하드웨어 요구를 자동으로 제외하지 않는다. ARM64 패키지가 없는 항목은 소스 빌드·공식 ARM 공급·아키텍처 호환 실행 경로를 구현하고 검증해야 한다. 유료 서비스의 인증 자체는 사용자의 계정이 필요하지만, 설치·인증 UI·연결·오류·복구 능력은 테스트용 서버나 계정 없는 경계 검사로 검증한다.

기존 Sway와 실제 Omarchy는 다른 실행 경로이다. Sway·유사 테마·호환 메뉴 또는 VM 한 화면을 Omarchy의 태블릿 지원 완료로 취급하지 않는다. VM은 원본 동작·패키지·서비스와 Android 경로의 차이를 비교하는 검증 환경이다. Android 앱의 권한으로 구현할 수 없는 OS 기능은 실제 Linux/시스템 통합 경로가 필요하며, 동작하지 않는 기능을 완료 항목으로 바꾸지 않는다.

## 구조

1. 고정 소스·패키지 계층: Git commit·각 blob·archive SHA256, Pacman desc와 depends, ARM64/any 아키텍처, 의존성과 providers, package SHA256·서명·라이선스를 확인한다. 무작위 설치 스크립트를 macOS에서 실행하지 않는다.
2. Arch 런타임: 분리된 rootfs/데이터 경로와 명시적 세션 타입을 사용한다. Linux 앱은 일반 Android 앱 UID로 실행하고 기존 HOME·Mac 프로필·KeyBridge·Android 설정을 보존한다. 기존 API는 Alpine 경로를 계속 지원한다.
3. 그래픽: Aquamarine 0.15.1과 Hyprland 0.56.2의 실제 백엔드를 연결한다. 부모 Wayland 버전 협상, allocator, EGL, renderbuffer, swapchain, 출력 및 커서를 검증한다. 최초 SHM/surfaceless 경로와 실제 Adreno 가속 경로를 구분한다. CPU로 한 번 표시된 결과를 GPU/실사용 성능으로 확대하지 않는다.
4. Omarchy 세션: 원본 Hyprland Lua 설정과 Quickshell을 초기화하고 사용자 입력·모니터 설정을 별도 override로 적용한다. 원본 CLI·테마·런처·알림·클립보드·OSD·서비스 기능이 실제 세션과 연결돼야 한다.
5. Android 기기 통합: 오디오·마이크·카메라·배터리·밝기·네트워크·Bluetooth·알림·파일·입력 반납을 목적별 채널로 연결한다. 임의 shell/전역 권한 부여 채널을 만들지 않는다. Linux OS 기능과 Android 호스트 기능의 소유권을 명시한다.
6. 네이티브 OS 경로: 직접 KMS/DRM·evdev/libinput·systemd·스토리지·절전이 필요한 기능의 실제 실행 경로를 준비한다. Y900의 커널·DTB·GPU·패널·입력·네트워크·충전·복구 증거 없이 부팅 이미지 또는 OS 지원 완료를 주장하지 않는다. 무단 flash/unlock/wipe를 하지 않는다.

## 입력·성능 계약

- 물리 Meta+1…9/0은 작업공간 1…9/10, Meta+Shift+숫자는 현재 창 이동 후 현재 작업공간 유지.
- 물리 Alt+1…9/0은 tmux 창 1…9/10, Alt+C/V는 복사·붙여넣기.
- 현재 KeyBridge Caps 레이어와 물리 Alt/Meta Mac 배열 설정을 보존한다. Omarchy의 compose:caps가 사용자 Caps 기능을 덮어쓰지 않는다.
- 터미널 문자 입력, 물리 클릭·드래그·해제, 탭, 두 손가락 스크롤·우클릭, 장치 연결·해제와 포커스 전환을 실제 입력 경로에서 확인한다.
- 균형 framebuffer·읽을 수 있는 폰트·33px 모서리 안전 영역·적절한 하단 여백을 유지하고 실제 13인치 화면에서 확인한다.
- 소켓 입력 대기, guest 앱 처리, GPU 출력, 실제 key-to-photon, 부하·전력·절전 복원을 서로 다른 측정으로 기록한다. 기준을 충족하지 못한 결과는 그대로 실패/미완료로 남긴다.

## 완료 증거

원본 51개 매뉴얼 장별 기능과 CLI·QML·패키지 요구를 빠짐없이 식별하고, 각 항목에 소스·구현·실행 증거를 연결한다. 설치·부팅·원본 프로세스·소켓·실제 화면·사용자 동작·실패 복구를 해당 범위로 검증한다. 소스 번들·패키지 manifest·빌드·VM 성공·APK 설치·물리 수락을 별도 증거로 취급한다. 어떤 필수 항목이 미구현·실패·미측정·불명확해도 전체 목표는 활성 상태로 유지한다.

검증에서는 앱 UID와 `run-as` staging을 구분한다. 실제 사용자 클립보드·셸 기록·비밀·편집 내용은 수집하지 않는다. 테스트 fixture는 소유한 프로세스·창·서버만 생성/정리한다. 코드 모듈은 500줄 이하를 유지한다. Git repository가 없는 현재 workspace에서는 임의 git init·commit·push를 하지 않는다.
