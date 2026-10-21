# Omarchy 수준 Wayland 데스크톱을 Android Y900에 연결하기

조사일: 2026-10-05. 이 문서는 구현 전의 조사와 실행 순서 제안을 보존한다. 이후 Sway·GTK 앱·런처·작업공간·입력·Android 연결을 구현했으며 최신 APK의 결과는 [현재 구현 증거](../runtime-implementation.md)에서 확인한다. 목표는 **실제 Linux Wayland compositor가 Linux 앱의 창 배치와 바탕 화면을 그린 뒤, 그 출력이 Android Surface에 나타나는 것**이다. 공식 Omarchy/Hyprland 실행과 Y900 실기기 성능은 별도 검증 대상이다.

## 현재 Omarchy 4의 실제 구성

공식 기본 브랜치 `quattro`의 [매뉴얼](https://github.com/omacom/omarchy/blob/65c0f3306e9b4af676f32d3b9fa187b53d9ca155/manual/01-welcome-to-omarchy.md)은 Omarchy를 **Arch Linux + Hyprland + Quickshell**로 설명한다. [기본 패키지 목록](https://github.com/omacom/omarchy/blob/65c0f3306e9b4af676f32d3b9fa187b53d9ca155/install/omarchy-base.packages)은 `hyprland`, `quickshell`, `uwsm`, `foot`, `fcitx5`, `wl-clipboard`, `xdg-desktop-portal-hyprland`, `grim`/`slurp`와 다수의 데스크톱 앱을 포함한다. [한 Quickshell 프로세스](https://github.com/omacom/omarchy/blob/65c0f3306e9b4af676f32d3b9fa187b53d9ca155/shell/README.md)가 바·패널·런처·알림·OSD·서비스 플러그인을 호스팅한다. 사용자 [Hyprland Lua 설정](https://github.com/omacom/omarchy/blob/65c0f3306e9b4af676f32d3b9fa187b53d9ca155/config/hypr/hyprland.lua)은 기본 설정을 읽고 모니터·입력·단축키·외형·자동 시작을 덮어쓴다.

사용자가 체감하는 핵심은 [키보드 중심 런처/단축키와 타일링](https://github.com/omacom/omarchy/blob/65c0f3306e9b4af676f32d3b9fa187b53d9ca155/manual/04-navigation.md), [워크스페이스/상태 바](https://github.com/omacom/omarchy/blob/65c0f3306e9b4af676f32d3b9fa187b53d9ca155/manual/05-the-top-bar.md), [통합 클립보드](https://github.com/omacom/omarchy/blob/65c0f3306e9b4af676f32d3b9fa187b53d9ca155/manual/08-unified-clipboard-history.md), [테마](https://github.com/omacom/omarchy/blob/65c0f3306e9b4af676f32d3b9fa187b53d9ca155/manual/06-themes.md), 터미널·브라우저·파일 앱을 실제로 여닫는 경험이다. 이 기능은 그림만 복제해서는 동작하지 않는다. Omarchy의 [설치 매뉴얼](https://github.com/omacom/omarchy/blob/65c0f3306e9b4af676f32d3b9fa187b53d9ca155/manual/02-getting-started.md)은 PC용 부팅 ISO와 디스크 설치를 전제한다. Android APK의 Linux rootfs로 ISO를 그대로 설치하는 경로가 아니다.

ARM64를 “Omarchy 자체가 불가능”으로 단정하면 현재 자료와 맞지 않는다. 공식 [패키지 저장소](https://github.com/omacom/omarchy-pkgs/blob/90594317f8fba86b24c300c5e2cda0aa00cf33f6/README.md)는 x86_64/aarch64 빌드 경로를 명시한다. 2026-10-05에 공식 [`stable/aarch64/omarchy.db`](https://pkgs.omarchy.org/stable/aarch64/omarchy.db)를 조회했을 때 압축된 Pacman DB가 HTTP 200으로 응답했고 `hyprland-0.56.2-4` 항목이 있었다. 당시 DB 목록에서 `omarchy` 패키지는 발견하지 못했다. 이 저장소의 가용성과 구성은 바뀔 수 있으며 **ARM64 패키지가 있다는 사실은 Android GPU/Surface 호환성을 증명하지 않는다**.

## 비root Android에서의 그래픽 경계

| compositor | Linux에서 가능한 경로 | Y900 일반 APK에서의 미해결 경계 |
| --- | --- | --- |
| **Hyprland** | 현재 소스는 [Aquamarine의 DRM·Wayland·headless 백엔드](https://github.com/hyprwm/Hyprland/blob/19fb395d45314960e6f79f17994a84094f1cd4f6/src/Compositor.cpp)를 선택하고 [GLES3](https://github.com/hyprwm/Hyprland/blob/19fb395d45314960e6f79f17994a84094f1cd4f6/CMakeLists.txt) 및 EGL 컨텍스트를 사용한다. | Android Surface는 자동으로 Linux DRM 장치나 부모 Wayland compositor가 되지 않는다. Y900 앱 UID에서 적합한 render node·EGL/GBM/dma-buf 공유 경로는 미검증. 공식 [가상 머신 안내](https://wiki.hypr.land/Getting-Started/Master-Tutorial/)도 3D 가속이 없으면 동작하지 않는다고 경고한다. **첫 CPU 전용 데스크톱 후보로 잡지 않는다.** |
| **Sway** | [wlroots 기반 타일링 compositor](https://github.com/swaywm/sway/blob/1652c54b73f67df17b7b4ab0b0f7048204aa8104/README.md). wlroots는 DRM 외에 Wayland·headless 백엔드, pixman 렌더러와 공유 메모리 할당자를 제공한다([프로젝트 설명](https://github.com/swaywm/wlroots/blob/master/README.md), [0.14 릴리스](https://github.com/swaywm/wlroots/releases/tag/0.14.0)). | Android에 부모 Wayland 서버/Surface 브리지를 제공해야 한다. Sway를 실행해도 자체적으로 Android Surface를 그리지는 않는다. 실제 ARM64/PRoot 실행·렌더 버전 조합과 지연은 별도 실험. |
| **labwc** | [wlroots 기반 스태킹 compositor](https://github.com/labwc/labwc). 공식 기여 문서는 [nested Wayland 실행과 `WLR_RENDERER=pixman`](https://github.com/labwc/labwc/blob/c2a95cfdba76776e8c51f9eef5a5ce000c93d321/CONTRIBUTING.md#L232-L247)을 디버깅 방법으로 제시한다. | 타일링/Omarchy 단축키는 별도 구성해야 한다. 부모 Wayland 서버가 필요한 점은 Sway와 같다. 가장 작은 **실제 compositor 첫 화면** 후보이지만 Android에서 성공했다는 증거는 아니다. |

“nested Wayland + pixman”은 의미가 분명하다. **labwc 또는 Sway가 실제 창 관리·합성을 하고**, 부모 Wayland 서버로 `wl_shm` 버퍼를 내보내며, Loopy Desktop 호스트가 그 버퍼를 `ANativeWindow_lock`/`unlockAndPost`로 Android Surface에 복사하는 실험 경로다. wlroots의 Wayland backend는 render node가 없을 때 `wl_shm` fallback을 추가한 기록이 있다([릴리스](https://github.com/swaywm/wlroots/releases/tag/0.14.0)); Android NDK는 CPU로 Surface 버퍼를 잠그고 게시하는 API를 제공한다([ANativeWindow](https://developer.android.com/ndk/reference/group/a-native-window)). 단, **현재 Loopy Desktop Wayland 호스트가 wlroots 부모에 필요한 프로토콜을 모두 제공하는지, 선택할 wlroots 버전의 fallback이 실제 동작하는지는 아직 검증되지 않았다.** Android 자체는 Wayland 부모가 아니므로 `WLR_BACKENDS=wayland`만 설정해서 화면이 나타나지는 않는다. headless backend도 출력이 자동 표시되지 않으며 프레임 추출·입력 주입을 위한 별도 adapter가 필요하다([wlroots 백엔드 설명](https://github.com/swaywm/wlroots/blob/master/README.md)).

프레임이 보이는 것과 데스크톱 사용 가능은 다르다. 부모 Wayland 프로토콜/출력 크기 변경, 포인터·키보드·한글 IME, 팝업·커서, 클립보드, Linux 앱 실행·종료, Xwayland, 오디오, 포털/화면 공유, 절전 복원은 각각 검증해야 한다. CPU 합성 + CPU 복사는 1920×1200 RGBA 전체 화면 한 번에 약 8.8 MiB이며 60회/초면 복사 원본 기준 약 527 MiB/s이다(계산값). 합성·추가 복사·메모리 대역폭까지 포함하면 실제 비용은 더 커질 수 있으므로 damage 기반 갱신과 프레임 제한을 먼저 측정해야 한다. Qt Quick은 소프트웨어 백엔드를 제공하나 일부 QML 항목은 렌더링되지 않을 수 있어 **Quickshell 전체 이식과 테마 동일성은 별도 게이트**다([Qt 문서](https://doc.qt.io/qt-6.5/qquickwindow.html)).

## 실행 순서 제안

1. 현 APK의 실제 Alpine rootfs·Wayland Surface 경로를 유지하고, 독립 compositor 세션용 출력 하나와 부모 Wayland 프로토콜 지원 범위를 계측한다. 단순 이미지 대신 `labwc` 또는 `sway` 프로세스·Wayland 소켓·client 연결·실제 frame commit을 증거로 남긴다.
2. labwc + pixman nested를 먼저 시도한다. Linux 터미널 두 개의 이동/포커스/재크기, 바탕 화면, 팝업을 한 Android Surface에서 확인한다. 실패 원인이 패키지·PRoot·Wayland 프로토콜·버퍼·Surface 중 어디인지 분리한다.
3. 같은 브리지에서 Sway를 시험해 키보드 중심 타일링/워크스페이스를 확인한다. 바·런처·알림·테마는 **Linux Wayland 클라이언트**로 올린다. 이 단계만으로 “Omarchy 경험 일부”라고 말할 수 있고, 공식 Omarchy/Hyprland 실행으로 부르지 않는다.
4. Y900의 실제 앱 UID에서 GPU 버퍼 경로를 확인한 뒤 Hyprland/Aquamarine과 Quickshell을 별도 단계로 평가한다. GPU 경로가 없거나 느리면 CPU compositor를 사용 가능한 제품 후보로 유지한다. 공식 Omarchy 구성 파일·패키지 복제는 기능 호환성과 라이선스·ARM64 패키지 확인 뒤 결정한다.

이는 소스 조사에 따른 설계 제안이며, Y900 실기기 구동 결과가 아니다. `WLR_RENDERER=pixman`의 실제 앱 UID 동작, Omarchy 패키지 전체 ARM64 설치, Hyprland GPU 경로는 아직 판정하지 않았다.
