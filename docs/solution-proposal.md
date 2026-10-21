# Loopy Desktop에 반영할 해결안

상태: 2026-10-05, 외부 구현 조사에 기반한 설계를 실제 APK 초기 구현으로 연결했다.
일반 앱 UID에서 PRoot/Alpine/foot → Wayland → Android Surface와 키·스크롤·텍스트 clipboard를 VM에서 확인했다.
현재 코드·수정 내용·한계는 [구현과 VM 검증](runtime-implementation.md)에 정리했다.
Y900의 앱 권한·입력·창 관리가 확인되면 선택을 갱신한다.
[프로젝트 비교](existing-projects.md)와 [직접 실행한 VM 결과](device-capabilities.md)가 근거다.

## 선택할 첫 경로

**일반 Android APK → 앱 내부 ARM64 rootfs/PRoot → Wayland 앱 하나 → Android Surface 하나**를 먼저 검증한다.
Local Desktop은 앞부분의 결합 선례이며 Anland는 창별 Android Activity 연결의 선례다.
Anland의 root/cgroup/SELinux 서비스는 초기 경로에 포함하지 않는다.
근거: [Local Desktop 구조](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/README.md#how-it-works),
[Anland 구조·요구사항](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/README.md).

| 선택지 | 얻는 것 | 초기 판단 |
| --- | --- | --- |
| PRoot + 우리 Activity/Surface 연결 | stock Android 실행 후보, 앱별 창 구조를 단계적으로 확인 | 첫 실험 대상 |
| Anland/Droidspaces root 경로 | 공개된 창별 브리지와 실제 namespace 기반 런타임 | root·커널 조건이 확인된 기기의 후속 후보 |
| Lindroid/AOSP 통합 | Android 그래픽 스택과 깊은 연결 | 초기 ROM 재빌드 제외 조건 때문에 보류 |

Wayland wire protocol 파싱은 고정된 `wayland-server`의 Rust backend를 사용했다.
Android ARM64 빌드에서는 libwayland/libffi를 추가하지 않고 필요한 프로토콜의 작은 호스트를 구현했다.
Smithay/libweston을 포함한 더 큰 기반은 빌드·의존성·필요 기능을 비교한 뒤 선택한다.
이들은 Android Activity 브리지를 자동 제공하지 않는다([그래픽 조사](research/android-graphics-bridges.md)).

## 1. 런타임: 권한 거부를 root 없이 다루기

PRoot bootstrap은 앱 전용 저장소에 rootfs·작업 디렉터리·소켓 경로를 구성한다.
먼저 `/bin/sh`와 동적 링커를 실행하고, 필요한 라이브러리와 Wayland 터미널 하나만 늘린다.
Android 실행 파일과 Linux/glibc 실행 파일을 별도 산출물로 구분한다.
호스트 파일 전체를 bind하지 않고 공유 경로를 명시한다.
근거: [PRoot-Distro 원리·제약](https://github.com/termux/proot-distro/blob/c76286a2fb57884dae11bc2ea469949bbcdec135/README.md),
[Local Desktop 앱 내부 rootfs](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/README.md#how-it-works).

**실행 파일의 패키징을 먼저 검증한다.** Android 10/API 29 이상을 target하는 일반 앱은
쓰기 가능한 앱 홈의 파일을 직접 `execve`할 수 없다.
따라서 rootfs를 풀고 실행 권한만 주는 방식으로 통과를 가정하지 않는다.
PRoot/loader의 APK native library 배치와 guest ELF 실행 경로를 앱 UID에서 확인해야 한다.
Local Desktop은 target SDK 33과 `extract_native_libs: true`를 명시하지만,
이 설정만으로 우리 guest의 실행 가능성이 입증되지는 않는다.
근거: [Android 실행 제한](https://developer.android.com/about/versions/10/behavior-changes-10#execute-permission),
[Local Desktop manifest](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/manifest.yaml#L13-L18).

구체적인 참고 경로는 `nativeLibraryDir/libproot.so` 실행과
`PROOT_LOADER=nativeLibraryDir/libproot_loader.so` 설정이다.
Local Desktop의 PRoot 코드는 guest exec 요청을 loader 실행으로 바꾼다.
우리 APK도 실행 파일 포장과 loader 경로를 함께 검증하며, target SDK를 낮추는 방법을 전제로 삼지 않는다.
근거: [process.rs](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/src/android/proot/process.rs#L44-L51),
[APK builder](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/src/bin/build_apk.rs#L531-L550).

일반 앱 UID에서 tracer 실행·자식 생성·경로 변환이 실패하면 오류와 실행 컨텍스트를 남긴다.
ADB 셸 성공으로 통과 처리하지 않는다. `EPERM/EACCES`, 잘못된 ELF/링커, ptrace 실패,
Linux 앱 종료를 구분해야 다음 선택이 가능하다.
PRoot를 격리된 보안 컨테이너로 표기하지 않는다.

런타임 모듈의 작은 인터페이스는 `start`, `launch`, `stop`, `status`와 실제 지원 능력 조회다.
첫 어댑터는 PRoot만 구현한다. root/namespace 어댑터는 지금 빈 코드로 만들지 않는다.
`freeze`는 지원 종류와 적용 범위가 확인된 후 추가한다.

## 2. 창과 버퍼: Android가 표시를 소유하기

Wayland 호스트는 연결·`wl_surface`·`xdg_toplevel`·configure/ack·버퍼 수명을 처리한다.
Android 창 모듈은 Activity/Task·Surface 생성/파괴·실제 크기·포커스를 처리한다.
둘은 안정된 `WindowId`와 이벤트로 연결하고 Android Surface의 실제 크기를 configure에 반영한다.
Anland의 [xdg 처리](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/services/waylandbridge/awl_xdg.c)와
[Activity 수명](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/app/libawl/src/main/java/com/anlandnext/awl/AwlWindowActivity.java)을 참고한다.

초기 출력은 `wl_shm` ARGB/XRGB를 CPU로 Android `ANativeWindow` 버퍼에 복사하는 실험이다.
buffer 크기·stride·offset·format을 검사하고 복사가 끝난 뒤 client buffer를 release한다.
Android 출력 버퍼의 stride는 독립적으로 처리한다.
Surface 파괴 이후의 프레임은 폐기하고 새 Surface 세대에만 출력한다.
Anland의 `wl_shm`은 GPU 업로드를 거치므로 이 CPU 경로의 구현 증거가 아니다([그래픽 조사](research/android-graphics-bridges.md)).

팝업·커서·서브서피스도 선택한 터미널이 요구하는 범위를 확인한다.
지원하지 않는 프로토콜을 광고하지 않는다. 전체 데스크톱 셸·DRM 소유·GPU 드라이버는 초기 호스트 책임이 아니다.
일반 APK가 임의의 freeform 좌표를 설정할 수 있다고 가정하지 않는다.
Y900에서 가능한 fullscreen/split-screen/freeform 형태를 실제 Task로 확인한다.
근거: [VM 창 관찰](device-capabilities.md), [AOSP multi-window](https://source.android.com/docs/core/display/multi-window).

## 3. 입력: 자체 창부터, 전역 제어는 기능별로

Activity의 공개 키/포인터/스크롤 이벤트를 의미 입력으로 바꿔 Wayland seat에 전달한다.
장치 ID·문자 키보드·외부/가상 분류를 함께 사용한다. `SOURCE_KEYBOARD`만으로 Laptop 모드를 선택하지 않는다.
한국어 IME는 Android `InputConnection`의 composition/commit과 Wayland text-input 경로를 연결한다.
물리 key event와 IME text commit을 구분해 같은 글자를 두 번 보내지 않는다.
근거: [VM 입력 감사](device-capabilities.md), [Anland 입력·IME 선례](research/android-graphics-bridges.md).

키 상태·tap/hold·장치 분리 정책은 플랫폼 독립 모듈에 둔다.
포커스 상실·장치 제거·IPC 연결 종료 시 눌린 키/버튼과 gesture 상태를 정리한다.
입력의 소유 경로를 하나로 선택해 원래 이벤트와 재주입 이벤트가 중복되지 않게 한다.
Caps 전역 정책과 raw trackpad는 MVP 0.1 이후, 실제 이벤트와 억제 권한이 확인된 뒤 추가한다.

선택적 권한 모듈은 좁은 명령만 처리하고 권한 상실을 명시적으로 반환한다.
Shizuku가 없으면 자체 창 입력 경로로 동작하며, root만 가능한 작업을 성공이라고 보고하지 않는다.
Key Mapper의 정책/`sysbridge` 분리와 Shizuku UserService가 참고다([입력 조사](research/android-input-and-windowing.md)).

## 4. 클립보드: 포커스에 맞춘 텍스트 동기화

초기에는 UTF-8 텍스트만 Android↔Wayland로 전달한다.
Android 읽기는 포커스된 Linux Activity에서 수행하며 포그라운드 서비스만으로 접근 제한을 우회한다고 가정하지 않는다.
이벤트에 origin과 bridge-local sequence를 붙여 자신의 쓰기 이벤트가 반복 왕복하지 않게 한다.
전송 크기와 읽기 시간을 제한하고 거부/빈 값/지원하지 않는 MIME을 구분한다.
근거: [Android clipboard 제한](https://developer.android.com/about/versions/10/privacy/changes#limited-access-to-clipboard-data),
[Anland·Termux의 처리 위치](research/android-graphics-bridges.md).

포커스 복귀, Linux 앱 간 이동, Android 앱 복사 후 Linux 붙여넣기, 반대 방향을 각각 검증한다.
백그라운드에서 새 클립보드를 즉시 읽지 못하는 경우에는 포커스 복귀 시 갱신한다.

## 5. 수명과 전력: 요청 상태와 실제 상태 구분

태블릿 모드와 런타임 상태는 별개다. 키보드 분리가 곧 guest 전체 freeze 성공을 뜻하지 않는다.
관찰 상태는 `STOPPED`, `RUNNING`, `FAILED`부터 시작하고,
백그라운드/일시 정지 기능은 프로세스 범위를 확인한 뒤 상태를 늘린다.
일반 앱에서 cgroup freezer를 쓸 수 있다고 가정하지 않는다.
PRoot tracer와 guest 자식 트리의 정지/재개·새 자식 경쟁을 따로 검증한다.
근거: [현재 freeze 경계](device-capabilities.md), [PRoot 제약](research/android-linux-runtimes.md).

키보드 분리 시 입력 상태를 해제하고 Android 터치 화면으로 복귀한다.
Linux 작업은 정해진 정책에 따라 background/stop 처리하며 저장되지 않은 작업을 자동 폐기하지 않는다.
MVP 실험용 터미널은 명시적으로 종료하고 tracer·자식·소켓 잔류가 없는지 확인한다.
사용자에게 실행 유지가 표시되는 foreground service는 후보이며 상시 wake lock은 기본값으로 두지 않는다.
화면 꺼짐·Android 프로세스 종료 후 회복·Y900 전력은 별도 측정한다([런타임 조사](research/android-linux-runtimes.md)).

## 읽기 쉽고 확장 가능한 모듈 구성

아래는 장기 책임 구분이다. 현재 초기 구현의 실제 파일 구조는 [구현 문서](runtime-implementation.md)에 정리했다.
500줄 이하의 파일을 유지하되 단순히 줄 수를 줄이기 위한 전달 전용 모듈은 만들지 않는다.
각 모듈의 호출자가 알아야 할 상태·순서·실패 조건을 인터페이스에 명시한다.

| 예정 모듈 | 책임 | 변경이 모이는 위치 |
| --- | --- | --- |
| `core/mode-controller` | 장치 변화와 Tablet/Laptop 상태 정책 | 모드 규칙 |
| `core/input-normalizer` | 키 상태·modifier·gesture의 의미 변환 | 입력 정책 |
| `runtime/manager` | PRoot 실행/종료·자식 상태·실패 보고 | Linux 실행 |
| `bridge/wayland-host` | protocol 객체·seat·configure·client 종료 | Wayland 규칙 |
| `bridge/buffer-bridge` | 검증된 프레임·복사·release | 메모리/출력 방식 |
| `android/window-host` | Activity/Surface/Task·실제 크기·포커스 | Android 창 처리 |
| `bridge/clipboard-bridge` | 텍스트·origin/sequence·포커스 동기화 | 클립보드 정책 |
| `android/privilege-adapter` | 선택적 접근성/IME/Shizuku 기능 | 권한 차이 |
| `platform/android-generic` | 장치 capability 수집 | 일반 Android 관찰 |

Lenovo 예외는 실제 증거가 생긴 경우 `platform/lenovo-y900`에 국한한다.
모델 문자열·GPU 가정을 일반 입력/런타임/버퍼 코드에 넣지 않는다.
실패 로그는 실행 UID·모듈·WindowId·오류·실제 상태를 남기고 클립보드/타이핑 내용은 기록하지 않는다.

## 다음 실행 순서와 통과 조건

| 단계 | 검증할 실행 | 통과 증거 | 실패할 때의 다음 판단 |
| --- | --- | --- | --- |
| A | APK native executable/loader 패키징 후 일반 앱 UID에서 PRoot + ARM64 `/bin/sh` | APK/바이너리 SHA·target SDK·실행 위치·UID·ELF/링커·명령 출력·정리 결과 | `EACCES` 실행 위치/정책·ptrace·링커/패키징 오류 구분 |
| B | Wayland 터미널 하나 → CPU copy → Surface | 실제 앱 프레임·버퍼 release·Surface 재생성·키/스크롤 | protocol 지원과 renderer 실패 분리 |
| C | 물리 키 입력·스크롤·텍스트 클립보드·키보드 분리 | 양방향 붙여넣기·키 상태 해제·Tablet 복귀 | 입력/포커스/권한별 수정 |
| D | Y900에서 A–C와 실제 입력 재검증 | 정확한 모델/펌웨어·앱 UID·물리 장치·Task 상태 | 기기 예외만 별도 어댑터로 기록 |
| E | MVP 0.2의 두 Linux 창 | 독립 Task·크기·포커스·닫기/재시작 | Activity 매핑/Wayland configure 수정 |
| F | Y900 화면 꺼짐·종료·재개·stock 비교 | 자식 잔류·wakeups·동일 조건 전력 기록 | runtime 정책 조정; 목표 충족 여부 별도 판정 |

A–D가 MVP 0.1의 첫 검증 범위다. 데스크톱 셸은 MVP 0.3, GPU zero-copy는 MVP 0.4에 둔다.
한국어 IME composition/commit은 초기 입력 설계에 반영하되 MVP 0.1 통과 후 별도 확장 검증으로 둔다.
VM SwiftShader 결과를 Y900 GPU·60/120/144 Hz·입력 지연·배터리 목표의 증거로 쓰지 않는다.
실기기 연결 후 시작점은 [Y900 점검 절차](y900-test-checklist.md)다.
