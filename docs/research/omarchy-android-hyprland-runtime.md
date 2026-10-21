# Android 무루트 환경에서 실제 Hyprland 실행하기

조사일: 2026-10-06. 대상은 Lenovo TB522FU / Android 16에서 일반 APK UID로 실행하는 실제 Omarchy다. 물리 태블릿은 의도적으로 연결하지 않았다. 이번 작업은 소스·사양 조사만 수행했으며 기기 명령, 설치, 권한 변경, 개인 데이터 수집, 제품 코드 변경은 하지 않았다.

## 판단

**현재 Loopy의 SHM 전용 부모 Wayland 서버에 수정 없는 Hyprland 0.56.2 + Aquamarine 0.15.1을 연결할 수 없다.** Aquamarine은 부모의 Linux DMA-BUF와 DRM 장치에서 만든 GBM allocator를 요구하고, Hyprland 출력 renderbuffer도 DMA-BUF EGLImage를 요구한다. `headless`, `EGL_PLATFORM=surfaceless`, VirGL socket 준비만으로 이 요구가 사라지지 않는다. [Aquamarine Wayland][aq-wayland], [backend][aq-backend], [Hyprland GLRenderbuffer][hl-rbo]

DRM 없는 실제 Hyprland를 만드는 가장 작은 일관된 후보는 **부모 버전 협상 + SHM allocator + surfaceless GLES3 FBO + 출력 readback/SHM 제출**이다. 먼저 llvmpipe로 실제 compositor 기능을 검증한 뒤, 같은 EGL/FBO 경로를 VirGL 또는 Android GPU provider로 바꾸는 순서가 가능하다. 이는 아래 소스의 접점에 따른 설계 추론이며 아직 빌드·런타임 수락이 아니다. Sway에 Omarchy 외형을 얹는 것을 목표 완료로 보지 않는다.

## 조사한 버전과 증거

| 소스 | 조사 pin | 용도 |
| --- | --- | --- |
| Hyprland v0.56.2 | `efb50993780079460b0cbed1363e2166a2de1d9f` | 실제 Omarchy 계열 compositor와 renderer |
| Aquamarine v0.15.1 | `f31c47a1b9d300847d8fc3108ad959448103dfc1` | 실제 ARM64 잠금 패키지 `0.15.1-1`의 upstream tag |
| Aquamarine main | `52ea11f06dd492f34b3cc0b39a9c805beecafcff` | 2026-10-03 최신 commit에서도 SHM 한계가 남는지 확인 |
| Aquamarine v0.9.3 | `98968ac7699b70fe9c4507c56798a5fa7b1bc29c` | Hyprland의 최소 빌드 요구 버전 비교용; 런타임 대상 아님 |

공식 try-omarchy [guest spec][try-spec]은 Hyprland v0.56.2의 같은 SHA를 잠그며 [ARM64 packages lock][try-lock]에 Aquamarine `0.15.1-1`이 있다. Omarchy 최신 `quattro` 조사 pin은 `81145eb1fd41532fcae4310b26f860608e2eaf82`다. try-omarchy의 Omarchy 4.0.4 snapshot `c668141e9c42b13c80c9ca4ea108e11708c5e8a5`와 이 최신 snapshot을 섞어 한 버전이라고 표현하지 않는다. [Omarchy 최신 기본 구성][omarchy-config]

선택 소스는 `build/omarchy-sources/hyprland-runtime/`에만 저장했다. [snapshot metadata](../../build/omarchy-sources/hyprland-runtime/snapshots.json)와 [source receipt](../../build/omarchy-sources/hyprland-runtime/source-receipt.json)는 각 파일의 Git blob SHA-1을 GitHub tree와 대조하고 SHA-256도 기록한다. 이 연구 cache는 약 2 MiB 이내다. 일부 web cache는 tag URL의 과거 내용을 반환했으므로 판단·줄 번호는 오늘 직접 받은 **commit SHA URL과 Git blob 검증 파일**을 기준으로 한다.

현재 host는 `wl_compositor v4`, `wl_shm v1`, `xdg_wm_base v1`, `wl_output v2`, `wl_seat v5`, `wl_subcompositor v1`, `wl_data_device_manager v3`만 광고한다. Android system EGL/GLES 합성과 guest 하드웨어 GL은 분리된 경로다. [현재 host 계약](../../native/wayland-host/README.md), [global 생성](../../native/wayland-host/src/server.rs)

## 수정 없는 경로가 막히는 위치

| 순서 | 현재 upstream 동작 | 현재 host에 미치는 영향 |
| --- | --- | --- |
| 1. 부모 protocol bind | Aquamarine `Wayland.cpp:114–140`은 registry의 `version`을 무시하고 seat 9, xdg 6, compositor 6을 bind한다. | host의 5/1/4보다 높다. DMA-BUF 문제 이전에 protocol error가 날 수 있다. [소스][aq-wayland] |
| 2. 부모 DMA-BUF | `start():147`은 dmabuf 존재·초기화 성공을 필수 조건으로 본다. `initDmabuf():370`은 v4 feedback으로 DRM device를 찾고 render/primary node를 연다. | SHM-only parent가 `Missing protocols`로 실패한다. AHardwareBuffer를 만들어도 자동으로 DRM `dev_t`가 생기지 않는다. [소스][aq-wayland] |
| 3. allocator | `Backend.cpp:162–179`는 유효 DRM FD를 reopen한 뒤 `CGBMAllocator`를 만들고, allocator가 없으면 실패한다. | headless 구현이 살아 있어도 SHM allocator가 없다. [소스][aq-backend] |
| 4. headless/null | Headless의 `drmFD():133`은 -1이고 출력 swapchain은 backend의 `primaryAllocator`를 쓴다. Null은 allocator 없는 시작을 허용받지만 `createOutput()`이 false이고 Hyprland가 요청하는 기본 backend 목록에도 없다. | headless/null은 완성된 DRM-free 데스크톱 렌더러가 아니다. [Headless][aq-headless], [Null][aq-null], [Hyprland backend 선택][hl-compositor] |
| 5. EGL display | `OpenGL.cpp:152–228,289–358`은 DRM FD에 일치하는 EGL device 또는 DRM FD로 만든 GBM display만 고른다. GLES 3.2 실패 시 3.0을 시도한다. | surfaceless context를 쓰는 코드여도 display 선택 자체는 DRM과 결합돼 있다. 명시적 platform 호출을 `EGL_PLATFORM` 환경변수가 다른 경로로 바꾸지 않는다. [소스][hl-egl], [Mesa EGL][mesa-egl] |
| 6. 출력 renderbuffer | `GLRenderbuffer.cpp:34–58`은 `buffer->dmabuf()`로 EGLImage를 만들고 RBO에 붙인다. | memfd SHM allocator를 추가하는 것만으로 렌더 대상이 생기지 않는다. [소스][hl-rbo] |
| 7. 부모 출력 제출 | `CWaylandBuffer::CWaylandBuffer`는 항상 `linux_buffer_params`를 만들고 plane FD·stride·modifier로 wl_buffer를 만든다. SHM 처리는 현재 커서 분기에 있다. | 일반 데스크톱 출력용 SHM 분기가 별도로 필요하다. [소스][aq-wayland] |

DRM dumb allocator도 무루트 대안이 아니다. `DRMDumb.cpp`는 `drmModeCreateDumbBuffer`와 `drmPrimeHandleToFD`를 호출한다. CPU map이 가능하다는 것과 DRM 없이 할당할 수 있다는 것은 다르다. [DRM dumb 소스][aq-dumb]

## DRM-free SHM 경로의 구체적인 접점

아래는 실제 Hyprland 소스를 보존하며 Android에 필요한 backend 계약을 추가하는 후보다. 환경변수 이름을 임의의 기존 upstream 옵션으로 소개하지 않는다. 새 옵션을 만들면 별도 namespace와 receipt에 패치 해시를 명시한다.

| 접점 | 필요한 변경 | 첫 acceptance |
| --- | --- | --- |
| 부모 버전 | Aquamarine Wayland registry bind를 `min(advertised, supported)`로 제한하고 버전별 이벤트/요청을 audit한다. host가 구현하지 않은 높은 버전을 광고해 우회하지 않는다. 현재 출력의 `damage_buffer`는 v4이므로 host compositor v4에서 가능하다. [AQ Wayland][aq-wayland], [Wayland 사양][wayland] | 4/1/5 부모에 오류 없이 bind, xdg configure/ack, keyboard/pointer frame 수신 |
| SHM allocator | `IAllocator`에 memfd/shared-file 기반 allocator를 추가한다. `IBuffer::shm`, `beginDataPtr`, `isSynchronous`, release/pin 계약을 구현하고 fd=-1 allocator를 backend가 선택하도록 한다. `AQ_ALLOCATOR_TYPE`는 현재 GBM/DRM_DUMB만 있다. [allocator 인터페이스][aq-allocator], [buffer 인터페이스][aq-buffer] | 크기·stride·offset·overflow·실패 cleanup, FD lifetime, parent release 전에 reuse 금지 |
| swapchain 형식 | `Swapchain.cpp:55`의 기본 format 결정과 trace에서 무조건 `dmabuf()`를 읽는 부분을 SHM-aware하게 바꾼다. 처음에는 host가 실제 광고하는 XRGB8888/ARGB8888 8-bit만 쓴다. [swapchain][aq-swapchain] | 2/3 buffer rotate, resize, allocation failure rollback, 제한된 메모리 사용 |
| 출력 형식/monitor | 부모 `wl_shm.format`을 수집하고 `getRenderFormats`를 SHM 후보로 제공한다. Monitor의 buffer-present 검사, format 선택, scanout 플래그를 audit한다. SHM 경로에는 direct scanout·multi-GPU·DRM syncobj를 적용하지 않는다. [AQ Wayland][aq-wayland], [Monitor][hl-monitor] | monitor 생성·mode test·commit·재크기에서 DMA-BUF attrs 읽기 없이 성공 |
| EGL display | `CHyprOpenGLImpl`에 `EGL_PLATFORM_SURFACELESS_MESA` display 선택을 명시적으로 추가한다. EGL device를 쓰려면 DRM 매칭 없이 사용할 수 있는 실제 device 선택을 별도 검증한다. configless context와 GLES3 실제 `eglMakeCurrent`·shader 지원을 검사한다. `eglDupNativeFenceFDANDROID` 등의 현재 무조건 proc assert도 CPU/implicit 경로와 함께 audit한다. [Hyprland EGL][hl-egl], [surfaceless platform 사양][egl-platform] | DRM FD -1, GLES 3 이상, FBO completeness, shader/texture·알파 pixel readback |
| SHM renderbuffer | `CGLRenderbuffer`의 SHM branch에서 일반 texture/RBO-backed FBO를 만들고 render pass를 유지한다. Hyprland의 `CGLFramebuffer::internalAlloc`은 이미 일반 texture FBO를 만든다. [GLRenderbuffer][hl-rbo], [GLFramebuffer][hl-fbo] | 실제 Hyprland rendering pass가 DMA-BUF EGLImage 없이 같은 FBO에 그려짐 |
| 출력 readback | `CHyprGLRenderer::endRender`의 완성된 출력 FBO에서 SHM으로 readback한 뒤 commit한다. 기존 `CGLFramebuffer::readPixels`의 format/stride/size 검사와 로직은 재사용 후보지만 인자가 Hyprland client-buffer 타입이므로 Aquamarine `IBuffer`로 바로 호출할 수 있는 API는 아니다. [GL renderer][hl-renderer], [GLFramebuffer][hl-fbo] | BGRA/RGBA, alpha, Y 방향, padding, damage 영역, sync 후 실제 parent pixel 일치 |
| wl_buffer 제출 | `CWaylandBuffer`에 SHM pool/create_buffer branch를 추가한다. pool/FD·mapping·pendingRelease·backend pin을 한 lifecycle로 유지한다. 현재 커서용 복사 코드를 출력 프레임마다 그대로 복제하면 불필요한 복사가 늘어난다. [AQ Wayland][aq-wayland], [Wayland SHM/release 사양][wayland] | frame request가 commit보다 앞섬, release 후에만 write/reuse, resize 중 old buffer 안전 해제 |
| 커서/입력 | parent host의 `set_cursor`가 표시되지 않으므로 Hyprland의 software cursor 정책을 사용하거나 host에 정식 cursor surface 합성을 구현한다. `WLR_NO_HARDWARE_CURSORS`는 Aquamarine 설정이 아니다. 내측 Hyprland input-method·clipboard는 parent seat만으로 완성되지 않는다. [pointer manager][hl-pointer], [host 계약](../../native/wayland-host/README.md) | 커서 1개, modifier/NumLock, wheel/버튼, focus, 한글 IME, clipboard 왕복 |

EGL의 surfaceless **platform**과 surfaceless **context**는 별개다. 앞의 것은 display를 window system 없이 얻는 API이고 뒤의 것은 context를 `EGL_NO_SURFACE`로 current하는 계약이다. 실제 API 호출 결과와 GLES context version을 검사해야 하며, 확장 문자열만으로 성공 판정하지 않는다. [MESA platform][egl-platform], [KHR context][egl-context]

## 하드웨어 가속 후보와 VM·native OS 구분

| 경로 | 실제 Hyprland 가능성 | 필요한 검증 / 목표와의 관계 |
| --- | --- | --- |
| Arch PRoot + SHM/surfaceless patch + llvmpipe | DRM-free baseline 후보 | actual compositor·Quickshell 동작을 검증할 수 있으나 tablet 성능 최종 수락은 아니다. [Mesa software fallback][mesa-egl] |
| 위 patch + guest `virpipe` → app-UID native VirGL helper → Android EGL/GLES | rootless GPU 후보 | VirGL은 GL 명령을 host로 전달하는 렌더링 경로다. Aquamarine allocator/parent protocol 문제를 해결하지 않는다. GLES3 compositor의 모든 shader·FBO·readback이 필요하고 SHM 출력 readback 비용은 남는다. [vtest source][vtest], [현재 helper 조사](virgl-egl-compatibility.md) |
| guest Mesa Freedreno KGSL / Turnip+Zink + SHM patch | 조건부 rootless GPU 후보 | app UID의 KGSL UAPI·해당 GPU·정확한 Mesa build·GLES3 extensions를 확인해야 한다. system Vulkan 또는 native offscreen readback 성공만으로 guest EGL을 수락하지 않는다. [현재 GPU 조사](guest-gpu-alternatives.md), [Android Vulkan 구조](https://source.android.com/docs/core/graphics/implement-vulkan) |
| Bionic native Hyprland + Android EGL/AHardwareBuffer allocator/output adapter | readback를 줄일 수 있는 후보 | 실제 Hyprland를 포팅하는 큰 작업이다. renderer/allocator를 AHB EGLImage로 연결하면 DRM가 필수인 현재 경로를 대체할 수 있다. Arch/glibc 앱과의 Wayland FD·launch 계약, C++26/전체 native 의존성 빌드, EGL image/fence provider를 각각 검증해야 한다. [AHardwareBuffer 공식 API][ahb], [Hyprland 빌드][hl-build] |
| Android host에 Linux DMA-BUF import를 추가 | 그 자체로는 불충분 | Aquamarine v4 feedback이 DRM device/node를 찾아야 하고 GBM이 그 FD를 써야 한다. import global만 광고하는 우회는 FD·format·modifier·sync·device 식별 계약을 충족하지 않는다. [AQ feedback 구현][aq-wayland] |
| Linux VM + virtio-gpu/virgl | reference에서 unmodified 경로 확인 가능 | VM에는 Linux DRM/GBM 장치를 제공할 수 있다. 일반 Android rootless PRoot에 동일 장치가 있다는 증거가 아니다. Android QEMU의 hardware GL/virtualization 권한도 별도다. [QEMU virtio-gpu 공식 문서][qemu] |
| Linux native OS/커스텀 kernel | DRM 드라이버·세션 조건이 맞으면 upstream 경로 후보 | 부트로더·kernel/display/input/GPU 지원이 다른 목표다. TB522FU Android APK 완성으로 대체하지 않는다. [Aquamarine 의존성·DRM backend][aq-build] |

AHardwareBuffer는 Android가 제공하는 shared hardware-memory API이고 Android EGLImage/Vulkan external memory에 연결할 수 있다. 그러나 Android EGL native-buffer handle과 Linux DMA-BUF/GBM ABI를 같은 것으로 취급하면 안 된다. AHB의 공용 프로세스 전달 API나 명시적 adapter를 사용해야 한다. glibc guest에서 Bionic vendor 라이브러리를 바로 로딩하는 것도 별도 ABI/namespace 문제다. [AHB 공식 API][ahb], [Android linker namespace](https://source.android.com/docs/core/architecture/vndk/linker-namespace)

내측 Hyprland client용 Linux DMA-BUF는 DRM FD로 device를 식별하지 못하면 upstream도 ready callback에서 global을 제거한다. 초기 SHM-only bring-up은 이를 유지하고 GTK/Qt가 제공하는 실제 SHM/software client path를 검사할 수 있다. GPU client가 Linux DMA-BUF import를 요구하면 그것은 출력 backend 성공 이후의 별도 guest-3D gate다. [Hyprland LinuxDMABUF.cpp][hl-dmabuf]

## 기존 patch의 재사용 범위

Upstream [Aquamarine issue #228][aq-issue]은 Android Smithay 부모 + PRoot에서 Hyprland를 실행하려다 같은 SHM-only 문제를 만난 개발자가 제기했다. 조회 시 Open이고 연결된 branch/PR가 없었다. 이는 현재 한계와 일치하는 독립 보고이며 DRM-free patch가 이미 수락됐다는 증거는 아니다. 최신 main도 필수 DMA-BUF와 GBM allocator 경로를 유지한다. [main Wayland][aq-main-wayland], [main Backend][aq-main-backend]

공식 Termux wlroots의 [Termux:GUI patch][tgui-patch]와 [AHardwareBuffer allocator][tgui-allocator]는 Android allocator/출력 adapter의 참고 구현이다. wlroots/Sway 전용 코드이므로 Aquamarine에 바로 적용하는 patch가 아니다. Hyprland를 오래된 wlroots 버전으로 내리면 Omarchy의 현재 Lua 설정·Hypr ecosystem ABI와 별개의 호환 작업이 된다. [Termux 조사](termux-wayland-gui.md), [현재 Hyprland 의존성][hl-build]

VirGL EGL compatibility overlay는 native helper의 EGL version/context 조건만 수정한다. guest GLES probe·GUI가 실패하거나 Aquamarine allocator가 없으면 Hyprland ready로 승격할 수 없다. [현재 overlay 범위](virgl-egl-compatibility.md)

## 실행 가능한 probe 순서

다음 항목은 향후 구현에서 실행할 acceptance 계약이다. 이번 조사에서 실행하지 않았다. 모두 disposable output directory와 owned process에 한정하고 태블릿 연결·기본 제품 전환과 분리한다.

1. **build provenance**: Hyprland/Aquamarine pin과 patch 입력 SHA, ARM64 ELF interpreter·DT_NEEDED·architecture를 기록한다. Hyprland v0.56.2는 CMake 3.30, C++26, GLES3, Lua 5.5 및 ecosystem 의존성을 요구한다. Aquamarine v0.15.1은 C++23이며 libseat/libinput/udev/DRM/GBM가 기본 빌드 의존성이다. 단지 nested로 실행한다고 그 링크 의존성이 없어지지 않는다. [Hyprland CMake][hl-build], [Aquamarine CMake][aq-build]
2. **config**: 실제 전달 바이너리에서 `Hyprland --version-json`, `Hyprland --verify-config --config <isolated-config>`로 실제 Lua 설정 parser와 version을 확인한다. PRoot가 `getuid()`를 0으로 보이게 하면 upstream root guard의 영향도 기록한다. `--i-am-really-stupid`는 guest의 유저 표시 문제를 다루는 flag이며 Android 권한을 올리지 않는다. [main.cpp][hl-main]
3. **EGL provider**: 같은 guest ABI·UID·environment에서 GLES3 context를 실제 current한 뒤 texture/FBO·간단한 shader·premultiplied alpha·readback을 확인한다. renderer/vendor/API, elapsed time, exact expected pixels를 receipt로 남긴다. llvmpipe와 virpipe를 각각 독립 probe한다. 현재 GLES2 단색 probe만 재사용해 통과로 보지 않는다.
4. **SHM-only nested fixture**: 실제 Loopy 또는 같은 globals/versions의 작은 host에 actual patched Hyprland를 연결한다. `/dev/dri` 없이 시작, advertised format 선택, top-level mapping, framebuffer→SHM pixels, configure/ack·resize·buffer release·owned stop를 확인한다. DMA-BUF mode의 기존 코드가 깨지지 않았는지도 reference host에서 한 번 확인한다.
5. **actual desktop**: 내측 Hyprland socket에 foot 두 개와 실제 Quickshell을 연결한다. tiling/move/workspaces/keybind·focus·popup·launcher·notification·clipboard·IME를 실제 client 동작으로 확인한다. official config/theme가 실제로 로드됐는지 로그와 client 상태를 함께 기록한다.
6. **performance**: 같은 build에서 출력 해상도·target Hz·실제 present Hz·CPU time·frame latency·damage·readback bytes·memory·GPU identity를 측정한다. 예를 들어 2560×1600×4×60은 출력 readback 한 번만으로 약 **0.983 GB/s**이며 parent texture upload/복사/합성은 추가다(산술 계산). software compositor 첫 화면과 성능 최종 수락을 분리한다.
7. **tablet acceptance**: 사용자가 TB522FU를 연결한 뒤 일반 앱 UID의 native provider·guest provider·전체 데스크톱 pixel/입력·resize·detach/reattach·suspend·장시간 성능을 같은 APK/hash로 확인한다. 현재 기기가 없으므로 여기까지는 미검증이다.

샘플은 임시 guest session 안에서만 실행할 형태이며 새 backend mode의 환경변수는 구현 후 확정한다.

```sh
Hyprland --version-json
Hyprland --verify-config --config "$PROBE_CONFIG"
env XDG_RUNTIME_DIR="$PROBE_RUNTIME" \
    WAYLAND_DISPLAY="$PARENT_WAYLAND_SOCKET" \
    LIBGL_ALWAYS_SOFTWARE=1 \
    Hyprland --config "$PROBE_CONFIG"
```

`LIBGL_ALWAYS_SOFTWARE`는 patched DRM-free EGL 경로의 provider 비교용이다. 수정 없는 upstream을 이 명령으로 실행하면 위 protocol/allocator/display gate가 남는다. 최종 full Omarchy 완료에는 그래픽뿐 아니라 실제 Arch 패키지·Quickshell·포털·오디오·services의 동작도 필요하다. 이 문서는 그래픽 접점과 그 검증 순서를 제공하며, 구현 또는 제품 완료 receipt가 아니다.

[hl-build]: https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/CMakeLists.txt
[hl-compositor]: https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/Compositor.cpp#L303
[hl-egl]: https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/render/OpenGL.cpp#L152
[hl-rbo]: https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/render/gl/GLRenderbuffer.cpp#L34
[hl-fbo]: https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/render/gl/GLFramebuffer.cpp
[hl-renderer]: https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/render/GLRenderer.cpp#L84
[hl-monitor]: https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/output/Monitor.cpp#L2640
[hl-pointer]: https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/pointer/PointerManager.cpp
[hl-main]: https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/main.cpp
[hl-dmabuf]: https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/protocols/LinuxDMABUF.cpp#L443
[aq-wayland]: https://github.com/hyprwm/aquamarine/blob/f31c47a1b9d300847d8fc3108ad959448103dfc1/src/backend/Wayland.cpp
[aq-backend]: https://github.com/hyprwm/aquamarine/blob/f31c47a1b9d300847d8fc3108ad959448103dfc1/src/backend/Backend.cpp#L162
[aq-headless]: https://github.com/hyprwm/aquamarine/blob/f31c47a1b9d300847d8fc3108ad959448103dfc1/src/backend/Headless.cpp
[aq-null]: https://github.com/hyprwm/aquamarine/blob/f31c47a1b9d300847d8fc3108ad959448103dfc1/src/backend/Null.cpp
[aq-allocator]: https://github.com/hyprwm/aquamarine/blob/f31c47a1b9d300847d8fc3108ad959448103dfc1/include/aquamarine/allocator/Allocator.hpp
[aq-buffer]: https://github.com/hyprwm/aquamarine/blob/f31c47a1b9d300847d8fc3108ad959448103dfc1/include/aquamarine/buffer/Buffer.hpp
[aq-swapchain]: https://github.com/hyprwm/aquamarine/blob/f31c47a1b9d300847d8fc3108ad959448103dfc1/src/allocator/Swapchain.cpp
[aq-dumb]: https://github.com/hyprwm/aquamarine/blob/f31c47a1b9d300847d8fc3108ad959448103dfc1/src/allocator/DRMDumb.cpp
[aq-build]: https://github.com/hyprwm/aquamarine/blob/f31c47a1b9d300847d8fc3108ad959448103dfc1/CMakeLists.txt
[aq-issue]: https://github.com/hyprwm/aquamarine/issues/228
[aq-main-wayland]: https://github.com/hyprwm/aquamarine/blob/52ea11f06dd492f34b3cc0b39a9c805beecafcff/src/backend/Wayland.cpp
[aq-main-backend]: https://github.com/hyprwm/aquamarine/blob/52ea11f06dd492f34b3cc0b39a9c805beecafcff/src/backend/Backend.cpp
[try-spec]: https://github.com/omacom/try-omarchy/blob/61d86ed1e691de44f3e50fdef4c78500abcfbf57/guest/spec.json
[try-lock]: https://github.com/omacom/try-omarchy/blob/61d86ed1e691de44f3e50fdef4c78500abcfbf57/guest/packages.lock.json
[omarchy-config]: https://github.com/omacom/omarchy/blob/81145eb1fd41532fcae4310b26f860608e2eaf82/config/hypr/hyprland.lua
[mesa-egl]: https://docs.mesa3d.org/egl.html
[egl-platform]: https://registry.khronos.org/EGL/extensions/MESA/EGL_MESA_platform_surfaceless.txt
[egl-context]: https://registry.khronos.org/EGL/extensions/KHR/EGL_KHR_surfaceless_context.txt
[wayland]: https://wayland.freedesktop.org/docs/html/apa.html
[vtest]: https://android.googlesource.com/platform/external/virglrenderer/+/68429e8e1106d0861d9f9f180583bd8381b8bf96/vtest/vtest_renderer.c
[ahb]: https://developer.android.com/ndk/reference/group/a-hardware-buffer
[qemu]: https://www.qemu.org/docs/master/system/devices/virtio/virtio-gpu.html
[tgui-patch]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/wlroots/0003-impl-termux-gui-backend.patch
[tgui-allocator]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/wlroots/src/backend/termuxgui/allocator.c
