# Android 위 Linux 실행 선례와 Loopy Desktop에 대한 적용

이 문서는 앱 구현 전의 외부 조사 기록입니다. 이후 일반 APK에서 Linux/foot/Wayland 실행을 구현하고
VM에서 확인했습니다. 현재 상태는 [구현·검증 문서](../runtime-implementation.md)를 기준으로 봅니다.

조사일: 2026-10-05. 대상은 Android를 호스트로 유지하면서 ARM64 Linux 프로그램을 실행하는 방법이다.
아래의 “구현”은 각 프로젝트가 공개한 코드·문서의 범위이며, Lenovo Y900에서의 작동 확인은 아니다.
현재 저장소의 [VM 감사](../device-capabilities.md)는 ADB 셸에서 `ptrace`를 확인했지만, PRoot·glibc 앱 실행에는 이르지 않았다.

소스 스냅샷: PRoot-Distro [`c76286a`](https://github.com/termux/proot-distro/tree/c76286a2fb57884dae11bc2ea469949bbcdec135)(커밋 2026-09-23 UTC), Local Desktop [`e6a8b58`](https://github.com/localdesktop/localdesktop.github.io/tree/e6a8b580a3376e842cca2e44327a99498d7fb6dc)(2026-09-08 UTC).
두 날짜와 SHA는 조사일에 공개 GitHub [PRoot-Distro 커밋 API](https://api.github.com/repos/termux/proot-distro/commits/master), [Local Desktop 커밋 API](https://api.github.com/repos/localdesktop/localdesktop.github.io/commits/main)로 확인했다.

## 기존 프로젝트가 실제로 푼 문제

| 프로젝트 | 실행 방식과 공개된 성과 | 필수 조건·우리에게 남는 차이 |
| --- | --- | --- |
| [Termux PRoot-Distro](https://github.com/termux/proot-distro/tree/c76286a2fb57884dae11bc2ea469949bbcdec135) / [Termux PRoot](https://github.com/termux/proot) | `ptrace`로 경로를 바꿔 root 없이 배포판 rootfs를 실행한다. ARM64(`aarch64`) 이미지를 지원한다. | 실제 root·namespace·cgroup·init 격리는 없다. 파일 작업에 추적 오버헤드가 있다. 화면·Android 창 통합은 담당하지 않는다. |
| [Local Desktop](https://github.com/localdesktop/localdesktop.github.io/tree/e6a8b580a3376e842cca2e44327a99498d7fb6dc) | 앱 내부 Arch Linux ARM64 rootfs + PRoot + Android NDK 안의 최소 Wayland compositor로 XFCE 세션을 **한 Android Activity**에 표시한 PoC를 공개했다. | 이 프로젝트의 자료만으로는 Linux 앱별 Android 창을 입증하지 못한다. 전체 XFCE 세션을 담는 화면 모델이다. |
| [Anland](https://github.com/SuperTurtleDev/anland/tree/851e1bdd2896af94214b1be7f3b3f9595b903da2) | `xdg_toplevel`을 각각 Android Activity·Surface에 연결하는 구현 선례다. | root·모듈·SELinux 도메인·Droidspaces 컨테이너를 요구하며, 초기 일반 APK 경로에 그대로 적용할 수 없다. [화면 브리지 조사](android-graphics-bridges.md)에 소스별 근거가 있다. |
| [Termux:X11](https://github.com/termux/termux-x11) + [TermuxService](https://github.com/termux/termux-app/blob/master/app/src/main/java/com/termux/app/TermuxService.java) | Android 앱과 Termux 패키지로 X11 서버를 제공한다. PRoot와 공유 `/tmp`를 통해 연결한다. Termux 서비스는 화면 Activity와 독립된 세션·명시적 wake/Wi-Fi lock을 관리한다. | X11이며 기본 사용법은 데스크톱 세션을 한 화면에 표시한다. chroot/unshare 안내에는 root와 `setenforce 0`가 등장하므로 그 경로는 본 제품의 보안 조건에 맞지 않는다. |
| [Lindroid](https://lindroid.org/) / [소스](https://github.com/Linux-on-droid/vendor_lindroid) | LXC와 AOSP 패치, 앱의 HWComposer 연결로 Linux Wayland compositor의 버퍼를 Android 표시 스택에 넘긴다. | AOSP 빌드·플래시와 커널 설정을 요구한다. 일반 APK만으로 제공되는 기능이 아니며, Linux 전체 데스크톱 중심이다. |
| [Droidspaces](https://github.com/MGHazz/Droidspaces) / [설치 안내](https://www.droidspaces.org/docs/installation-android.html) | root와 커널 namespace를 이용해 PID 1을 갖는 Linux 컨테이너를 실행한다. ARM64 바이너리와 cgroup·정리 기능을 제공한다. | Android 기기 root 및 맞는 커널 구성이 필수다. SELinux permissive 전환을 선택지로 제공하므로 이를 그대로 도입하지 않는다. 별도 그래픽 서버도 필요하다. |

### 근거와 적용 범위

- **PRoot-Distro:** [작동 원리와 ARM64](https://github.com/termux/proot-distro/blob/c76286a2fb57884dae11bc2ea469949bbcdec135/README.md#how-proot-distro-works), [PRoot 제약](https://github.com/termux/proot-distro/blob/c76286a2fb57884dae11bc2ea469949bbcdec135/README.md#proot-limitations), [런처 소스](https://github.com/termux/proot-distro/blob/c76286a2fb57884dae11bc2ea469949bbcdec135/proot-distro.py), [Termux용 PRoot 패치](https://github.com/termux/proot).
  namespace/chroot 거부를 사용자 공간에서 우회하는 **가장 가까운 참고 구현**이다. 격리·권한 상승으로 취급할 수 없으므로 호스트 파일 바인딩을 최소화해야 한다. `--kill-on-exit`, `ps`, `kill` 같은 프로세스 관리 동작은 수명주기 연구 자료가 된다. [저장소 라이선스](https://github.com/termux/proot-distro/blob/c76286a2fb57884dae11bc2ea469949bbcdec135/LICENSE)는 GPL-3.0-only이며 PRoot의 라이선스는 [COPYING](https://github.com/termux/proot/blob/master/COPYING)을 별도로 검토해야 한다.
- **Local Desktop:** [공식 README의 구성과 Pixel Tablet PoC](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/README.md#how-it-works), [소스 구조](https://github.com/localdesktop/localdesktop.github.io/tree/e6a8b580a3376e842cca2e44327a99498d7fb6dc/src), [GPL-3.0](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/LICENSE).
  Android APK 안에서 PRoot와 Wayland를 잇는 결합 지점을 읽기에 좋다. 공개 설명에서 Android 개별 Task/Activity와 Wayland `xdg_toplevel`의 일대일 대응을 확인하지 못했으므로 그것을 구현 완료로 간주하지 않는다.
- **Local Desktop의 앱 데이터 실행 제한 대응:** [Manifest](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/manifest.yaml#L8-L18)는 `targetSdkVersion=33`과 `extractNativeLibs=true`를 지정한다. [APK 빌더](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/src/bin/build_apk.rs#L531-L550)는 `assets/libs/arm64-v8a/*.so`를 native libraries로 넣는다.
  [실행 코드](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/src/android/proot/process.rs#L44-L51)는 `nativeLibraryDir/libproot.so`를 시작하고 `PROOT_LOADER`를 같은 디렉터리의 `libproot_loader.so`로 지정한다. [내장 PRoot](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/patches/build-proot-android/build/proot/src/execve/enter.c#L708-L715)는 guest 파일의 실행 요청을 loader 경로로 바꾼다. 즉 targetSdk 28로 제한을 피하는 설계가 아니라 native-library 실행 경로와 PRoot loader를 사용한다.
  [Android 10 정책](https://developer.android.com/about/versions/10/behavior-changes-10#execute-permission)은 target 29 이상 일반 앱이 쓰기 가능한 app home 파일을 직접 `execve()`하지 못하게 한다. Local Desktop도 [rootfs를 앱 데이터에 풀고](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/src/android/proot/setup.rs#L74-L85) [loader를 통한 지원 검사](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/src/android/proot/process.rs#L83-L100)를 한다. 이 구조는 이식할 후보 경로의 근거이지, 모든 Android 버전·OEM에서 guest ELF 실행을 보장하지 않는다.
- **Anland:** [창별 브리지의 확인한 소스·조건](android-graphics-bridges.md#가장-직접적인-선례-anland-6x).
  `xdg_toplevel`별 Android Activity·Surface 대응의 직접 선례다. 다만 root·모듈·컨테이너 전제와 GPU 렌더링 경로를 분리해서 참고해야 한다. Loopy Desktop의 무root 초기 경로와 CPU 복사 출력에는 별도 구현·검증이 필요하다.
- **Termux:X11:** [PRoot 연결](https://github.com/termux/termux-x11#using-with-proot-environment), [chroot 안내와 SELinux 주의](https://github.com/termux/termux-x11#using-with-chroot-environment), [GPLv3](https://github.com/termux/termux-x11/blob/master/LICENSE). [TermuxService 코드](https://github.com/termux/termux-app/blob/master/app/src/main/java/com/termux/app/TermuxService.java)는 foreground notification과 사용자가 켜고 끄는 wake lock의 실제 예다. 이는 화면 밖 실행 가능성을 보여줄 뿐, Android 절전 중 Linux 프로세스의 지속 실행이나 배터리 목표를 보장하지 않는다. [Android cached app freezer](https://source.android.com/docs/core/perf/cached-apps-freezer)도 별도 고려해야 한다.
- **Lindroid:** [프로젝트 공식 설명·설치 조건](https://lindroid.org/), [AOSP 통합 소스](https://github.com/Linux-on-droid/vendor_lindroid). compositor와 Android 그래픽 버퍼 연결은 중요한 기술 선례다. 하지만 AOSP 패치·전용 커널을 전제하므로 일반 Y900 APK 경로의 구현 재료로 바로 사용할 수 없다. 직접 코드 재사용 전 각 구성요소 라이선스를 따로 확인해야 한다.
- **Droidspaces:** [root와 커널 전제](https://github.com/MGHazz/Droidspaces#rooting-requirements), [Android 설치 안내](https://www.droidspaces.org/docs/installation-android.html), [SELinux 옵션](https://github.com/MGHazz/Droidspaces#features), [GPL-3.0](https://github.com/MGHazz/Droidspaces/blob/main/LICENSE). root 사용자가 선택한 경우의 별도 backend 선례다. root만 있다고 모든 Y900 커널에 필요한 namespace/cgroup이 생기지는 않는다.

## Loopy Desktop에 추가할 판단

초기 실행 경로의 기준점은 **Android 앱 내부 ARM64 rootfs + PRoot**다. 이는 root·mount namespace·`chroot` 권한에 의존하지 않는 선례가 있고, 이번 VM의 `EPERM` 결과와도 맞는다.
다만 VM에서 확인한 것은 ADB 셸 `ptrace`까지다. 설치 APK의 앱 UID와 해당 기기의 SELinux 정책에서 **native-library 경로의 PRoot·loader와 앱 데이터 rootfs**로 배포판의 동적 링커·패키지 관리자·한 개 GUI 앱을 실제 실행하는 시험이 먼저 필요하다.
[PRoot-Distro](https://github.com/termux/proot-distro/blob/c76286a2fb57884dae11bc2ea469949bbcdec135/README.md#proot-limitations), [현재 감사](../device-capabilities.md).

런타임 인터페이스는 PRoot에 고정하지 않고, 권한과 커널 능력이 **실제로 확인된 기기**에서만 RootChroot/Namespace 구현으로 교체할 수 있게 둔다. [Droidspaces의 요구 조건](https://github.com/MGHazz/Droidspaces#requirements)과 [Lindroid 설치 조건](https://lindroid.org/)은 root 백엔드를 “보편 APK 기능”으로 표기하면 안 되는 근거다. SELinux 전역 permissive 전환은 채택하지 않는다.

화면은 Local Desktop의 Android 내부 Wayland 연결 방식과 **Anland의 `xdg_toplevel`별 Android Activity·Surface 구현**을 함께 참고한다. Anland는 개별 창 매핑의 직접 선례지만 root·모듈·컨테이너가 전제다. Loopy Desktop의 무root PRoot 경로에서 같은 창 동작을 재현했거나 Y900에서 실행했다는 증거는 없다. [화면 브리지 조사](android-graphics-bridges.md), [Local Desktop 구성](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/README.md#how-it-works).

첫 검증 범위는 Wayland 앱 한 개의 `xdg_toplevel` → Android Activity·Surface 하나다. surface 생성·버퍼·포커스·키/스크롤·클립보드를 확인한다. resize/ack의 수명 규칙은 초기 설계에 포함하고 여러 창은 MVP 0.2에서 검증한다. 한국어 IME 조합은 MVP 0.1 이후 별도 입력 확장 검사다. [Wayland 아키텍처](https://wayland.freedesktop.org/architecture.html), [AOSP multi-window](https://source.android.com/docs/core/display/multi-window).

수명주기는 앱 화면과 Linux 자식 프로세스를 분리하되, 표시 중 실행·명시적 백그라운드 실행·화면 꺼짐·사용자 종료를 각각 정의한다. Termux의 foreground service/wake lock은 참고 구현이며, 계속 깨워 두는 방식을 기본값으로 삼으면 배터리 목표와 충돌한다. 앱별 종료 후 남는 프로세스, Android 프로세스 제한, suspend/resume을 실기기에서 측정해야 한다. [TermuxService](https://github.com/termux/termux-app/blob/master/app/src/main/java/com/termux/app/TermuxService.java), [Android 백그라운드 제한](https://developer.android.com/about/versions/oreo/background), [cached app freezer](https://source.android.com/docs/core/perf/cached-apps-freezer).

현재 선택은 **PRoot를 첫 실험 대상**, Lindroid·Droidspaces를 권한이 있는 기기의 참고 대상으로 두는 것이다. 이것은 제품 구현이나 Y900 호환성 판정이 아니다. 추가 실기기 증거가 필요한 항목은 PRoot 앱 UID 실행, 그래픽 버퍼/Surface 표시, 개별 Android 창, 물리 키보드·트랙패드, 한국어 IME, 절전과 배터리다. [실기기 점검 목록](../y900-test-checklist.md).
