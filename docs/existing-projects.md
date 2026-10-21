# 기존 프로젝트가 푼 문제와 재사용 판단

조사일: 2026-10-05. Android를 호스트로 유지한다는 원래 명세를 기준으로 조사했다.
**가장 가까운 조합은 Local Desktop의 PRoot 실행 방식 + Anland의 창 매핑 방식이다.**
첫 구현은 이를 참고한 일반 APK로 연결했고 [앱 UID VM 검증](runtime-implementation.md)을 수행했다.
Anland의 루트 데몬은 채택하지 않았다.

아래는 공식 소스·문서에서 확인한 선례다. 이 프로젝트에서 빌드하거나 VM/Y900에서 실행한 결과와 구분한다.
현재 직접 실행한 증거는 [기존 VM 감사](device-capabilities.md)에 있다.
이를 반영한 [Loopy Desktop 해결안](solution-proposal.md)에는 모듈 책임과 다음 검증 순서를 적었다.

## 비교

| 프로젝트 | 이미 푼 부분 | 우리 프로젝트에서 사용할 방식 | 남는 제약 |
| --- | --- | --- | --- |
| [Local Desktop](https://github.com/localdesktop/localdesktop.github.io/tree/e6a8b580a3376e842cca2e44327a99498d7fb6dc) | 앱 내부 ARM64 rootfs·PRoot·NDK Wayland 연결 | 일반 APK 안의 Linux 실행/패키징 선례 | 전체 XFCE를 한 Activity에 표시; 앱별 Android 창은 별도 |
| [PRoot-Distro](https://github.com/termux/proot-distro/tree/c76286a2fb57884dae11bc2ea469949bbcdec135) | root 없는 배포판 구성·실행 | 첫 런타임 후보와 bootstrap 참고 | 실제 namespace/cgroup 격리 없음; 앱 UID에서 실행 검증 필요 |
| [Anland 6.x](https://github.com/SuperTurtleDev/anland/tree/851e1bdd2896af94214b1be7f3b3f9595b903da2) | `xdg_toplevel`별 Activity/Surface, 입력·IME 연결 | 창 ID·Surface 수명·resize·입력 전달 설계 참고 | root/KernelSU 계열·Droidspaces 필요; 6.x 미완 명시; 초기 CPU 출력과 다름 |
| [Termux:X11](https://github.com/termux/termux-x11/tree/0e1ebb4c180f4e8e7a14a80f7cd0db8301791b6d) | Android Surface와 X11 버퍼·텍스트 클립보드 연결 | FD 전달·버퍼 수명·Surface 재생성 참고 | X11이며 Wayland 창별 Task 연결을 대신하지 않음 |
| [Termux:GUI](https://github.com/termux/termux-gui/tree/be24a5f34681096a788a6b0559caf833f87bd691) | Linux 명령행과 Android GUI 간 IPC | 명령/이벤트 채널과 Android 표면 연결 참고 | 기존 Wayland 앱을 실행하는 서버가 아님 |
| [Key Mapper](https://github.com/keymapperorg/KeyMapper/tree/dc70a64bdb17769d7a2632c381596d77dfb2d919) | 키 정책·장치 제어·권한 프로세스 분리 | Caps 상태와 입력 어댑터 구조 참고 | 전역 입력 권한·OEM 단축키·raw MT는 별도 확인 |
| [Shizuku API](https://github.com/RikkaApps/Shizuku-API/tree/a27f6e4151ba7b39965ca47edb2bf0aeed7102e5) | 별도 ADB/root 프로세스와 Binder 연결 | 선택적 최소 권한 어댑터의 라이브러리 후보 | ADB 방식은 root가 아니며 namespace 거부를 해결하지 않음 |
| [Taskbar](https://github.com/farmerbb/Taskbar/tree/e2a00b9a3f3adda069059abb9aebcb8b4e18954f) | Android 런처·조건부 freeform/데스크톱 모드 | MVP 0.3의 셸 참고 | 기기/설정 의존; Linux 창 브리지 아님 |

표의 근거·구현 파일·라이선스는 [런타임 조사](research/android-linux-runtimes.md),
[그래픽 조사](research/android-graphics-bridges.md), [입력 조사](research/android-input-and-windowing.md)에 연결했다.
초기 실행과 직접 맞닿는 7개 저장소의 SHA·최종 커밋 시각은 [조회 기록](research/upstream-snapshot.json)에 보존했다.
이 기록은 안정성 인증이나 릴리스 버전 선택을 의미하지 않는다.

## 조건이 달라지는 후보

[Droidspaces](https://github.com/MGHazz/Droidspaces)는 root·커널 namespace를 쓰는 런타임 선례다.
[Lindroid](https://github.com/Linux-on-droid/vendor_lindroid)는 LXC와 AOSP/HWComposer 통합 경로다.
둘은 권한·ROM을 변경할 수 있는 후속 경로이며, stock Y900에 APK만 설치하는 초기 전제로 채택하지 않는다.
요구 조건은 [런타임 조사](research/android-linux-runtimes.md)에 있다.

[wlroots-android-bridge](https://github.com/Xtr126/wlroots-android-bridge)는 창별 GPU Surface 연결 선례지만
개별 창 resize·입력은 공개 로드맵의 미완 항목이다.
[WLDroid](https://github.com/Shelnutt2/wldroid)는 compositor 전체 출력을 앱에 넣는 다른 형태다.
두 방식의 차이와 프로토콜 기반 후보인 Smithay/libweston은 [그래픽 조사](research/android-graphics-bridges.md)에 기록했다.
[libinput](https://wayland.freedesktop.org/libinput/doc/latest/what-is-libinput.html)은 raw MT와 FD 권한이 확인된 뒤 검토한다.

## 재사용 수준

- **설계 참고:** Local Desktop, Anland, Termux:X11/GUI, Key Mapper의 책임 분리와 실패 처리.
- **의존성 후보:** PRoot 실행 파일, Wayland 프로토콜 라이브러리, 선택적 Shizuku API. Android 빌드와 라이선스 조건 확인 후 결정.
- **후속 비교:** root/ROM 경로, GPU zero-copy, 데스크톱 셸과 raw 트랙패드 처리.

외부 코드·APK·rootfs를 이 저장소에 복사하지 않았다. 주요 참고 구현에는 GPL-3.0이 있으므로
설계 참고와 소스 편입을 구분한다. 현재 프로젝트의 배포 라이선스도 아직 결정하지 않았다.
개별 구성 요소와 rootfs 패키지의 배포 조건은 실제 의존성을 선택할 때 확인한다.

로컬 KeyBridge·Andra는 지정 경로에 없어 현재 소스로 평가하지 못했다.
과거 기능 이름을 재사용 가능한 코드로 취급하지 않았다([확인 기록](research/local-input-reuse.md)).

## 감사와 플랫폼 정책의 제약에 대한 답

| 기존 감사의 제약 | 찾은 해결 경로 | Loopy에서 필요한 다음 증거 |
| --- | --- | --- |
| shell `chroot/unshare`가 `EPERM` | PRoot 사용자 공간 경로 변환 | 일반 앱 UID에서 ARM64 Linux 프로그램 실행 |
| 일반 앱의 writable home 직접 실행 제한 | Local Desktop의 APK `libproot`/loader 패키징 | 실제 target SDK·실행 위치·guest ELF 경로 확인 |
| 공유 메모리/FD만 확인됨 | Anland·Termux의 프로토콜/버퍼 수명 선례 | 실제 `wl_shm` 프레임을 Android Surface에 표시 |
| Linux 창과 Android Task 연결 없음 | Anland의 창별 Activity/Surface | 우리의 일반 APK에서 두 창 분리·resize·종료 |
| 전역 키 제어 권한 미확인 | Key Mapper·Shizuku의 기능별 어댑터 | Y900 실제 이벤트와 권한별 주입/억제 검사 |
| 클립보드 백그라운드 접근 제한 | 포커스된 Activity 중심의 동기화 | Android↔Linux 텍스트와 포커스 전환 검사 |
| guest 전체 freeze·절전 미확인 | 런타임 정책과 실제 지원 능력 분리 | 자식 프로세스 잔류·화면 꺼짐·Y900 전력 검사 |

PRoot는 실행 문제를 푸는 후보이며 보안 격리를 제공하는 해결책은 아니다.
창·입력·전력도 각 선례가 필요한 조건과 함께 검증해야 한다.
