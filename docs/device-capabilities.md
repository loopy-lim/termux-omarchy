# Loopy Desktop 기기 기능 감사

조사 날짜: 2026-10-05 (Asia/Seoul).

사용자가 제공한 자료는 실행 스크립트가 아니라 제품 명세이며, 조사 시작 시 작업 폴더는 비어 있었습니다.
요청에 따라 Android VM에서 플랫폼 기능과 제약을 확인했습니다.
Lenovo Y900 13인치 실기기는 현재 연결할 수 없어 검증을 보류했습니다.

## 조사 환경

- 호스트: macOS ARM64, Hypervisor.Framework 가속 사용 가능.
- VM: 임시 AVD `Loopy_Feasibility`, serial `emulator-5580`.
- 이미지: 설치된 Android 36.1 Google Play ARM64, 게스트 Android 16 / API 36.
- 게스트 커널: Linux `6.12.38-android16-5-gbb9513914902-ab13996879-4k`, `aarch64`.
- 화면: 1920×1200, 240 dpi. GPU는 SwiftShader 소프트웨어 렌더러.
- 권한: `uid=2000(shell)`, SELinux `Enforcing`, 컨텍스트 `u:r:shell:s0`, `user` 빌드.
- 기존 가상 기기의 사용자 데이터를 사용하지 않는 별도 저장소에서 조사했습니다.

## 직접 확인한 결과

| 항목 | 관찰 | 증거와 한계 |
| --- | --- | --- |
| ARM64 실행 | 네이티브 진단기가 ARM64 VM에서 실행됨 | Android/Bionic 프로그램이며 Linux/glibc 배포판은 미실행 |
| 키보드 기능 열거 | `qwerty2`, `KeyboardType: 2`, Caps·Meta 키 기능 확인 | VM 장치이며 `IsExternal: false`; 물리 키보드 연결 감지와 한글 전환 미검증 |
| 가상 트랙패드 | ABS 멀티터치 슬롯·좌표를 제공하며 Android에서 `MOUSE/STYLUS`, `DeviceType: POINTER`로 분류 | 실제 Y900 트랙패드의 원시 이벤트·스크롤·제스처 미검증 |
| 공유 메모리 | `memfd_create`, 공유 `mmap`, 자식 변경을 부모에서 관찰 | Android 셸의 부모·자식 프로세스 간 검사 |
| 버퍼 전달 기반 | Unix socket `SCM_RIGHTS`로 FD 전달 후 자식의 독립 매핑 확인 | Wayland `wl_shm` 클라이언트, Android Surface 출력은 미검증 |
| ptrace | 자식 `PTRACE_TRACEME`, 정지·재개 성공 | PRoot의 한 가지 전제만 확인; PRoot 실행·호환성·성능 미검증 |
| 입력 장치 생성 | `/dev/uinput` 열기, 임시 장치 CREATE→DESTROY 성공 | ADB 셸에서만 확인. 실제 키 이벤트를 생성하지 않았으며 일반 앱 권한 미검증 |
| namespace/chroot | `unshare(CLONE_NEWNS)`와 `chroot('/')` 모두 `EPERM` | 해당 VM의 ADB 셸에서 직접 실행한 결과 |
| Android 창 | 초기 freeform 실행 요청은 fullscreen; ADB 디스플레이 모드 전환 후 freeform 확인 | `am`의 종료 코드 대신 실제 Task와 Configuration 확인 |
| 창 크기 변경 | Settings Activity를 `Rect(100,100–1200,800)`으로 변경한 실제 Configuration 확인 | Linux 창 매핑·Wayland configure/ack 미검증 |
| localhost | Android 셸의 TCP 서버·클라이언트 간 고유 문자열 수신 성공 | Linux guest→Android Chrome 경로는 미검증 |
| 정지·재개 | 자체 생성한 sleep 프로세스가 `T (stopped)`→`S (sleeping)`으로 전환 | 단일 프로세스 신호 검사; guest 전체 freeze·Android suspend·배터리 미검증 |

에뮬레이터 콘솔의 Caps 이벤트 전송은 숫자 SYN 코드로 `OK`를 반환했지만, 지정 evdev 장치에서 DOWN/UP을 수집하지 못했습니다.
따라서 키 입력 경로 성공으로 판정하지 않았습니다. 최초 SYN 문자열 별칭 오류와 재시도 결과를 모두 보존했습니다.
localhost 최초 파이프 방식은 문자열을 수신하지 못했고, 연결 시 명령을 실행하는 서버 방식에서 수신했습니다.

## 명세에 반영할 조건

1. **입력 권한은 기능별로 결정해야 합니다.** 자체 창의 키 처리, 전역 키 필터, 원시 evdev 접근,
   원래 이벤트 억제, Android 입력 주입은 서로 다른 기능입니다.
   공개 `InputManager`의 장치 목록·변경 listener로 연결 감지를 시작할 수 있습니다.
   이번 조사에서는 앱 구현으로 이 API를 호출하지 않았으므로 실제 모드 감지 성공은 미검증입니다.
   일반 창 콜백은 해당 창의 이벤트를 처리합니다. 사용자 활성화가 필요한 AccessibilityService의 키 필터·제스처 경로도
   임의의 시스템 입력 제어와 구분해야 합니다.
   근거: [InputManager](https://developer.android.com/reference/android/hardware/input/InputManager),
   [Window.Callback](https://developer.android.com/reference/android/view/Window.Callback),
   [접근성 키 필터](https://developer.android.com/reference/android/accessibilityservice/AccessibilityServiceInfo#FLAG_REQUEST_FILTER_KEY_EVENTS),
   [접근성 제스처 주입](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#dispatchGesture(android.accessibilityservice.GestureDescription,android.accessibilityservice.AccessibilityService.GestureResultCallback,android.os.Handler)).

2. **클립보드는 포커스·IME 정책이 필요합니다.** Android 10 이상은 기본 IME 또는 포커스된 앱이 아니면
   클립보드 데이터를 읽을 수 없습니다. 포그라운드 서비스만으로 상시 동기화를 보장한다고 가정하면 안 됩니다.
   MVP에서는 Linux 창이 포커스를 얻을 때 동기화하는 방식 등을 별도 검증해야 합니다.
   근거: [Android 클립보드 접근 제한](https://developer.android.com/about/versions/10/privacy/changes#limited-access-to-clipboard-data).

3. **창 통합은 제조사 설정에 의존합니다.** Freeform은 Desktop Windowing의 전제이며 관련 기능은 장치 구성에 의존합니다.
   이번 VM의 ADB 성공을 Y900의 APK 권한이나 Lenovo 창 관리 성공으로 확대할 수 없습니다.
   근거: [AOSP multi-window](https://source.android.com/docs/core/display/multi-window).

4. **PRoot의 freeze와 격리는 별도로 정의해야 합니다.** PRoot는 ptrace로 파일 경로·권한 동작을 흉내 내며
   실제 root, PID/network 격리, cgroup 제어를 제공하지 않습니다.
   `freeze()`가 프로세스 신호 기반 일시 정지인지 실제 cgroup 정지인지, 어떤 자식 프로세스를 포함하는지
   백엔드별로 명시해야 합니다. Android 앱 생명주기와 절전도 별도로 검증해야 합니다.
   근거: [PRoot](https://proot-me.github.io/), [proot-distro 제한](https://github.com/termux/proot-distro/blob/master/README.md#proot-limitations),
   [Android cached app freezer](https://source.android.com/docs/core/perf/cached-apps-freezer).

5. **Wayland 브리지는 제한된 디스플레이 서버 역할이 필요합니다.** 완전한 Linux 데스크톱을 만드는 범위는 피할 수 있지만,
   클라이언트 연결, surface/buffer 수명, configure, 입력 포커스, 클립보드를 담당할 구성 요소는 필요합니다.
   기존 구현을 포함할지 작은 서버 역할을 직접 구현할지 정한 뒤 Android 창과 연결해야 합니다.
   근거: [Wayland 아키텍처](https://wayland.freedesktop.org/architecture.html),
   [Wayland 프로토콜](https://wayland.freedesktop.org/docs/html/apa.html).

추가로 자동 모드 감지는 `SOURCE_KEYBOARD`만 사용하면 스타일러스 버튼·시스템 키까지 키보드로 오판할 수 있습니다.
이번 VM에서도 비문자 입력 장치가 `KEYBOARD` source를 가집니다. 문자 키보드 여부, 가상/외부 분류와 실제 기기 정보를 함께 확인해야 합니다.

## 다음 검증과 판정

Android를 유지하고 ARM64 런타임을 분리하는 방향의 기본 조사 환경은 확보했습니다.
공유 메모리와 IPC는 이 VM의 ADB 셸에서 검증됐습니다.
이 초기 감사 이후 별도 APK에서 Linux 배포판, Wayland 터미널, Android Surface,
포커스·키 입력·스크롤과 양방향 클립보드를 구현·검증했습니다. [앱 UID 구현 증거](runtime-implementation.md).
전체 MVP 0.1의 실기기 판정과 완성된 자동 모드 정책은 남아 있습니다.
한국어 IME 조합은 MVP 0.1 이후 입력 확장 검증 대상으로 남습니다.

Y900 연결 시 정확한 모델·펌웨어·커널을 읽고, 키보드 분리/연결 전후 입력 장치와 창 관리 상태를 비교해야 합니다.
원시 트랙패드 데이터, OEM 단축키, GPU 버퍼 호환성, 지연 시간, 배터리·절전 결과는 실기기에서 확인합니다.
구체적 순서는 [Y900 점검 안내](y900-test-checklist.md)에 있습니다.

## 기존 구현 조사로 보완한 해결 경로

추가 조사에서 Local Desktop의 일반 APK PRoot/Wayland 결합과 Anland의 창별 Activity/Surface 선례를 찾았습니다.
Key Mapper·Shizuku는 입력 정책과 권한 작업을 분리하는 참고 구현입니다.
프로젝트별 조건·소스·라이선스는 [기존 프로젝트 비교](existing-projects.md),
현재 명세에 반영할 순서는 [해결안](solution-proposal.md)에 정리했습니다.
이 추가 조사는 외부 소스 확인이며 위 VM 관찰을 Linux 실행·Surface 표시 성공으로 변경하지 않습니다.
일반 앱 UID의 PRoot 실행과 한 개 Wayland 터미널 표시 증거는 위 ADB 셸 감사와 별도 기록으로 연결했습니다.

## 증거 파일

모든 경로는 `docs/validation/2026-10-05-android-vm/` 아래에 있습니다.

- `baseline/receipt.json`: 36개 항목의 수집 상태, UTC·한국 시각, ADB 셸 컨텍스트.
- `baseline/input_capabilities.stdout.txt`, `baseline/input_service.stdout.txt`: 입력 기능과 Android 분류.
- `native-probe.txt`: 실제 ARM64 네이티브 검사 결과.
- `freeform-launch.txt`, `freeform-state.txt`: 기본 창 요청의 실제 fullscreen 상태.
- `freeform-experiment.json`: ADB 디스플레이 모드 변경 후 실제 freeform Task.
- `resize-after-display-mode.json`: 실제 창 좌표 변경과 디스플레이 모드 복원 요청.
- `loopback-command-server.json`: TCP 문자열 수신 검사.
- `self-process-stop-resume.txt`: 자체 프로세스 정지·재개 상태.
- `keyboard-injection*.json`: 성공 판정을 하지 않은 원시 Caps 이벤트 전송 시도.
- `session.json`, `vm-config.ini`, `emulator.log`: VM 실행 조건과 로그.
- `launcher-verification.json`: 정리한 VM 실행 도구로 별도 새 VM이 부팅된 결과.
- `tool-verification.json`: 잘못된 기기·제조사 거부, 코드 파일 길이와 소스 해시.

수집 도구의 종료 코드 0이나 `receipt.status=complete`는 플랫폼 기능 전체의 성공을 의미하지 않습니다.
표의 각 관찰과 실행 컨텍스트를 함께 읽어야 합니다.
감사 후 두 테스트 VM을 종료하고 임시 가상 디스크를 제거했습니다. 설정과 실행 증거는 위 경로에 보존했습니다.
