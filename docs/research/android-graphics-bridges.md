# Android 위 Linux 창 연결 선례 조사

조사일: 2026-10-05. 목표는 **Android를 호스트로 유지**하고 ARM64 Linux 앱의 Wayland 창을 각각 Android 창과 Surface에 연결하는 것이다. 아래의 “동작”은 해당 프로젝트의 소스·문서가 구현하거나 주장하는 범위다. Loopy Desktop의 실행 검증을 뜻하지 않는다. 현재 이 저장소에는 제품 앱이 없고 VM에서 확인한 것은 네이티브 실행과 공유 메모리·파일 디스크립터 전달까지다([프로젝트 README](../../README.md)).

## 가장 직접적인 선례: Anland 6.x

[Anland `851e1bd`](https://github.com/SuperTurtleDev/anland/tree/851e1bdd2896af94214b1be7f3b3f9595b903da2)는 `xdg_toplevel` 하나를 Android Activity·Surface 하나로 대응시키고 Android SurfaceFlinger에 표시한다. 앱 전환 화면의 독립 작업, 창별 입력·IME·클립보드도 설계에 포함된다([README](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/README.md#L27-L48), [`AwlWindowActivity`](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/app/libawl/src/main/java/com/anlandnext/awl/AwlWindowActivity.java#L41-L64)). 이는 “Linux 앱별 Android 창”이라는 최종 형태와 맞닿아 있다.

| 필요한 경계 | Anland의 실제 위치 | Loopy Desktop에 주는 단서 |
| --- | --- | --- |
| Wayland 창 생성·크기 협상 | [`awl_xdg.c`](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/services/waylandbridge/awl_xdg.c) | Android Activity의 Surface 크기를 Wayland configure에 반영하는 흐름 참고 |
| Surface 수명·태스크 | [`AwlWindowActivity.java`](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/app/libawl/src/main/java/com/anlandnext/awl/AwlWindowActivity.java#L481-L504) | 창 생성·재크기·종료 시 Surface 재연결과 작업 정리 참고 |
| `wl_shm` 프레임 | [`awl_surface.c`](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/services/waylandbridge/awl_surface.c#L1147-L1205), [`awl_renderer.cpp`](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/services/waylandbridge/awl_renderer.cpp#L303-L321) | 공유 메모리 소스·damage·release 시점 참고 |
| 입력·클립보드 | [`awl_input.c`](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/services/waylandbridge/awl_input.c), [`awl_data_device.c`](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/services/waylandbridge/awl_data_device.c#L558-L697) | Android가 포커스·터치·키 이벤트의 권위가 되고, 텍스트 클립보드는 포커스된 Activity가 읽는 방식 참고 |

주의: Anland의 **Stage 1 `wl_shm` 경로는 목표인 CPU 복사와 동일하지 않다**. 해당 소스는 클라이언트 풀을 프레임 시점에 읽고 GL 텍스처에 업로드한 뒤 EGL로 Surface에 출력한다. 다른 경로는 dma-buf/AHardwareBuffer 및 SurfaceControl 또는 EGL을 사용한다([버퍼 수명](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/services/waylandbridge/awl_surface.c#L9-L20), [렌더링 방식](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/README.md#L80-L95)). 따라서 `wl_shm` 프로토콜 처리와 창 수명은 강한 참고 자료지만, **우리의 CPU copy → Android Surface 출력은 별도 구현·실험이 필요**하다. Anland은 루트·SukiSU/KernelSU 모듈·SELinux 도메인·Droidspaces 컨테이너를 요구하므로 초기 무수정 Android 앱에 바로 이식할 부품으로 분류하지 않는다([요구사항](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/README.md#L97-L114)). `main`의 6.x는 작성자가 5.x보다 기능 완성도가 낮다고 명시한다([상태](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/README.md#L9-L24)). 라이선스는 [GPL-3.0](https://github.com/SuperTurtleDev/anland/blob/851e1bdd2896af94214b1be7f3b3f9595b903da2/LICENSE); 코드 복제 전 배포 조건 검토가 필요하다.

## 화면·IPC 경계의 부분 선례

| 프로젝트 | 확인한 해법 | 적용 범위와 간극 |
| --- | --- | --- |
| [Termux:X11 `0e1ebb4`](https://github.com/termux/termux-x11/tree/0e1ebb4c180f4e8e7a14a80f7cd0db8301791b6d) | X 서버의 [버퍼 구현](https://github.com/termux/termux-x11/blob/0e1ebb4c180f4e8e7a14a80f7cd0db8301791b6d/lorie/src/main/cpp/lorie/buffer.c)은 ashmem/AHardwareBuffer, CPU lock, Unix socket의 핸들·`SCM_RIGHTS` 전달을 다룬다. Android [`LorieView`](https://github.com/termux/termux-x11/blob/0e1ebb4c180f4e8e7a14a80f7cd0db8301791b6d/lorie/src/main/java/com/termux/x11/LorieView.java)는 SurfaceView 수명과 양방향 텍스트 클립보드를 다룬다. | 버퍼 전송·Surface 재생성·클립보드의 참고 자료. **X11 서버**이므로 Wayland `wl_surface`/`xdg_toplevel` 구현이나 Linux 앱별 Android 태스크의 증거가 아니다. [GPL-3.0](https://github.com/termux/termux-x11/blob/0e1ebb4c180f4e8e7a14a80f7cd0db8301791b6d/LICENSE). |
| [Termux:GUI `be24a5f`](https://github.com/termux/termux-gui/tree/be24a5f34681096a788a6b0559caf833f87bd691) | CLI 프로그램과 플러그인이 [추상 Unix 소켓 두 개로 명령·이벤트를 교환](https://github.com/termux/termux-gui/blob/be24a5f34681096a788a6b0559caf833f87bd691/Protocol.md#connection). [공유 HardwareBuffer를 그리는 SurfaceView](https://github.com/termux/termux-gui/blob/be24a5f34681096a788a6b0559caf833f87bd691/app/src/main/java/com/termux/gui/views/HardwareBufferSurfaceView.kt)가 있고, [Manifest](https://github.com/termux/termux-gui/blob/be24a5f34681096a788a6b0559caf833f87bd691/app/src/main/AndroidManifest.xml)는 여러 Activity 유형을 선언한다. | Android 네이티브 UI/IPC의 참고 자료. 임의의 기존 Wayland 앱을 연결하는 서버가 아니며, 여러 Activity 유형만으로 **Wayland 창마다 독립 태스크**를 보장하지 않는다. 오버레이·백그라운드 창은 별도 “Display over other apps” 설정을 요구한다([README](https://github.com/termux/termux-gui/blob/be24a5f34681096a788a6b0559caf833f87bd691/README.md#L9-L24)). [GPL-3.0](https://github.com/termux/termux-gui/blob/be24a5f34681096a788a6b0559caf833f87bd691/LICENSE). |
| [wlroots-android-bridge `52178bb`](https://github.com/Xtr126/wlroots-android-bridge/tree/52178bb20b1672a63a765c9a2666cb04163cdfee) | [서비스→Activity→AIDL Surface 연결](https://github.com/Xtr126/wlroots-android-bridge/blob/52178bb20b1672a63a765c9a2666cb04163cdfee/README.md#L171-L188)과 창별 GPU AHardwareBuffer/SurfaceTransaction 출력. [`SurfaceViewActivity.kt`](https://github.com/Xtr126/wlroots-android-bridge/blob/52178bb20b1672a63a765c9a2666cb04163cdfee/app/src/main/java/com/xtr/tinywl/SurfaceViewActivity.kt)·[`ITinywlSurface.aidl`](https://github.com/Xtr126/wlroots-android-bridge/blob/52178bb20b1672a63a765c9a2666cb04163cdfee/tinywl/src/main/aidl/com/xtr/tinywl/ITinywlSurface.aidl)가 직접 경계다. | 창별 Android 표면 설계는 유용하지만 버퍼는 **GPU 경로**다. README의 [로드맵](https://github.com/Xtr126/wlroots-android-bridge/blob/52178bb20b1672a63a765c9a2666cb04163cdfee/README.md#L189-L200)은 개별 크기 조정 창·입력을 미완 항목으로 적는다. 따라서 완성된 창/입력 증거로 쓰지 않는다. [GPL-3.0](https://github.com/Xtr126/wlroots-android-bridge/blob/52178bb20b1672a63a765c9a2666cb04163cdfee/LICENSE). |

## 다른 구현을 선택할 때의 경계

[WLDroid `9560e76`](https://github.com/Shelnutt2/wldroid/tree/9560e767bb3e31f3d9b72d280e051c47cda35cf1)는 wlroots 기반 Android compositor를 라이브러리로 제공하고 `CompositorSurface`로 **전체 compositor 출력을 앱 안에 삽입**한다([구조·사용법](https://github.com/Shelnutt2/wldroid/blob/9560e767bb3e31f3d9b72d280e051c47cda35cf1/README.md#L187-L288)). Linux 환경·GPU shim까지 패키지화했지만 최종 목표의 앱별 Android 태스크 모델과는 다르다. 입력/IME 및 Android Surface 연동의 비교 대상으로 두고, Stage 1에서 통째로 채택하지 않는다. 라이선스는 [MIT](https://github.com/Shelnutt2/wldroid/blob/9560e767bb3e31f3d9b72d280e051c47cda35cf1/LICENSE).

[Lindroid](https://github.com/Linux-on-droid/vendor_lindroid)는 LXC·libhybris·Android HWComposer 연결과 **AOSP 패치**를 명시한다([공식 README](https://github.com/Linux-on-droid/vendor_lindroid/blob/eadbb70f13209133d96a5355464388db8c6578de/README.md)). KWin 같은 compositor의 화면을 Android에 전달하는 방식이어서 창별 태스크 목표 및 “초기 AOSP 수정 없음” 조건에는 맞지 않는다. 비교 대상으로만 남긴다.

Wayland 프로토콜 구현을 새로 크게 쓰지 않으려면 [Smithay](https://github.com/Smithay/smithay)의 compositor 구성 요소 또는 [`libweston`](https://wayland.pages.freedesktop.org/weston/toc/libweston/compositor.html)을 좁은 실험 대상으로 검토할 수 있다. 두 프로젝트는 Wayland 쪽 기반을 제공하지만 Android Activity/Surface 브리지를 완제품으로 제공한다는 근거는 없다([Smithay 설명](https://github.com/Smithay/smithay), [libweston API](https://wayland.pages.freedesktop.org/weston/toc/libweston/compositor.html)). Loopy Desktop의 Android ARM64 빌드·패키징 가능성도 아직 확인하지 않았다.

## 이 저장소에 옮길 설계 결론

1. 첫 세로 단면은 **Wayland 앱 1개 → `xdg_toplevel` 1개 → Android Activity 1개/Surface 1개**로 고정한다. Anland의 `awl_xdg.c`와 Activity 수명 처리에서 상태 경계를 참고하되 독립된 짧은 모듈로 구현한다.
2. Stage 1은 `wl_shm`의 ARGB/XRGB 버퍼, stride, damage, release를 처리하고 **CPU copy로 Android Surface에 출력**한다. Anland·Termux:X11의 프로토콜·버퍼 수명 예를 참고하지만 둘의 GPU 경로를 Stage 1 성공 증거로 삼지 않는다.
3. Android 입력·IME·텍스트 클립보드는 해당 Activity의 포커스와 생명주기에 묶어 별도 어댑터로 만든다. 앱 창을 2개로 늘리는 검증에서 태스크 분리·독립 크기 조정·포커스 이동·닫기/재시작을 확인한다.
4. 현 단계의 권한 경계는 **ADB 셸에서 되는 것 ≠ 일반 Android 앱에서 되는 것**이다. 패키지/권한/Surface 런타임을 VM에서 확인한 다음 Y900 실기기에서 별도로 재검증한다. 루트 데몬·커스텀 GPU 드라이버·AOSP 재빌드는 초기 구현의 전제가 아니다.

이 문서는 외부 프로젝트의 코드나 실행 파일을 복사하지 않았다. 모든 후보의 실제 빌드·기기 동작·라이선스 적합성은 통합 전에 별도 검증이 필요하다.
