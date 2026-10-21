# Y900 native Termux Chromium 성능 경로 조사

조사일: 2026-10-12. 기기 변경 없이 공식 패키지와 Chromium 소스를 확인했다. 목표는 Omarchy/Notion/YouTube를 유지하면서 브라우저의 PRoot ptrace 비용을 제거하는 것이다. 현재 native 설치149, apt candidate152라는 값은 부모 작업의 기기 조회 보고이다.

## 결론

**공식 Termux Chromium152는 X11용이며 Wayland frontend와 VAAPI가 꺼져 있다.** Android native 프로세스라는 이유로 Android Chrome의 MediaCodec 디코더가 자동 포함되지는 않는다. `--ozone-platform=wayland` 또는 VAAPI flags만 추가하는 방법은 지원 기능을 만들어내지 못한다. 패키지 업데이트만으로 guest Hyprland Wayland 직접 연결이 해결된다고 볼 수 없다.

공식 소스 기준점은 `termux/termux-packages` commit `aed8f2405a392e49b487eb7ac0ed2eded4f45015`, Chromium `152.0.7977.82`, revision1이다. [패키지 recipe](https://github.com/termux/termux-packages/blob/aed8f2405a392e49b487eb7ac0ed2eded4f45015/x11-packages/chromium/build.sh).

| 항목 | 공식 빌드 증거 | 의미 |
|---|---|---|
| Ozone X11 | ozone_auto_platforms=false, ozone_platform=x11, ozone_platform_x11=true | X11 접속 가능 |
| Ozone Wayland | ozone_platform_wayland=false, TODO Enable wayland | guest Wayland socket을 알아도 이 frontend로 접속 불가 |
| ANGLE Vulkan | angle_enable_vulkan=true | Vulkan GL renderer 후보는 있음. 실제 Turnip 선택과 GPU 합성은 실행 확인 필요 |
| SwiftShader | angle_enable_swiftshader=true | fallback이 가능하므로 창이 뜨는 것만으로 GPU 성공 판정 금지 |
| VAAPI | use_vaapi=false | 기존 termux-va shared library를 붙이는 것만으로 디코더가 생기지 않음 |
| 소프트웨어 codecs | ffmpeg_branding=Chrome, proprietary_codecs=true | H.264 등 codec 가능 여부와 hardware decoder는 별개 |

`1016-chromium-ozone-wayland-memfd.patch`는 components/exo의 memfd 선언을 수정한다. 이름과 달리 Chromium Wayland 플랫폼 활성화 패치가 아니다. [해당 패치](https://github.com/termux/termux-packages/blob/aed8f2405a392e49b487eb7ac0ed2eded4f45015/x11-packages/chromium-host-tools/cr-patches/1016-chromium-ozone-wayland-memfd.patch).

## MediaCodec 지원 판정

Chromium152의 `media/gpu/BUILD.gn`은 Android MediaCodecVideoDecoder 및 NDK codec wrapper를 `if (is_android)` 안에서 빌드한다. Termux recipe는 Linux desktop custom toolchain을 사용하며 compiler target을 Android ABI로 바꾸는 패치를 적용한다. 이는 Chromium 전체를 Android 앱/JNI 빌드로 만드는 것과 다르다. 공식 `cr-patches` 전체에서 MediaCodec/AMediaCodec 브리지는 발견되지 않았다. HEVC 패치는 FFmpeg decoder 활성화이다. 따라서 이 패키지의 hardware decode 경로로 MediaCodec을 제시할 근거가 없다. [Chromium152 media build](https://github.com/chromium/chromium/blob/152.0.7977.82/media/gpu/BUILD.gn), [compiler target patch](https://github.com/termux/termux-packages/blob/aed8f2405a392e49b487eb7ac0ed2eded4f45015/x11-packages/chromium-host-tools/cr-patches/0001-compiler-use-android-target.patch), [공식 패치 목록](https://github.com/termux/termux-packages/tree/aed8f2405a392e49b487eb7ac0ed2eded4f45015/x11-packages/chromium-host-tools/cr-patches).

## 재빌드 없이 가능한 최소 비교

### 1. Native Chromium → 기존 guest Xwayland

브라우저를 Termux 앱 UID에서 native로 실행하고, guest Chromium이 사용하는 **동일 Xwayland 서버**의 DISPLAY/socket에 연결한다. Xwayland native transport 주소와 접근 권한은 현재 런타임에서 확인해야 한다. guest Hyprland가 창을 계속 관리하므로 Omarchy 통합은 유지된다. 비교 목적은 브라우저 자식 프로세스의 PRoot ptrace 비용 제거이며 Xwayland CPU 출력 제거는 아니다.

기존 X11 기준과 renderer를 맞추는 후보 flags:

```text
--ozone-platform=x11
--use-gl=angle
--use-angle=vulkan
--enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan
--disable-vulkan-surface
--disable-accelerated-video-decode
--user-data-dir=<새 native 실험 profile>
```

이는 성능 보증 명령이 아니라 기존 guest X11 기준과 비교하기 위한 조합이다. GL compositor+ANGLE Vulkan을 썼던 native Wayland 후보와 섞지 않는다. 필요한 기존 sandbox 설정과 알려진 Vulkan ICD 경로는 현재 native 런타임 기준으로 유지한다. glibc guest DRM shim·Mesa 라이브러리를 bionic 프로세스에 preload하지 않는다.

공식 launcher는 `$PREFIX/etc/chromium/*.conf`를 읽으며 CHROMIUM_USER_FLAGS가 CHROMIUM_FLAGS를 대체한다. 정확한 실험 argv를 만들려면 `$PREFIX/lib/chromium/chrome` 직접 실행 또는 새 프로세스의 실제 command line 검증이 필요하다. 패키지는 자체 ANGLE libEGL/libGLESv2 및 Vulkan loader를 포함하므로 Weston의 라이브러리 선택과 같다고 가정하지 않는다. [launcher](https://github.com/termux/termux-packages/blob/aed8f2405a392e49b487eb7ac0ed2eded4f45015/x11-packages/chromium/chromium-launcher.sh.in), [배포 파일 목록](https://github.com/termux/termux-packages/blob/aed8f2405a392e49b487eb7ac0ed2eded4f45015/x11-packages/chromium/build.sh).

Gate: Chromium/GPU/renderer PID가 PRoot tracer에 붙지 않음, Adreno830 renderer와 GPU compositing enabled, guest Hyprland에 xwayland=true 창 등록, GPU crash0, 동일 DPR/viewport/codec/영상 해상도, 정상 입력·저장·Notion 표시. 이를 통과한 뒤 동일4K1080p60+Code 편집을 비교한다. 새 profile은 Notion 로그인 상태를 상속하지 않으므로 실제 Notion 동시 사용 수락과 분리한다.

### 2. Native Chromium → Termux:X11 직접 출력

기존 native AHB Turnip WSI와 DRI3 surface를 브라우저에도 사용할 수 있는지 진단할 수 있다. guest Xwayland와 PRoot 둘 다 우회하지만 Chromium 창이 Omarchy 밖에 생긴다. 따라서 통합 완료로 채택할 경로가 아니다. 비교 시 X11 확장/renderer/픽셀/AHB GPU present를 실제 확인해야 한다. `--disable-vulkan-surface`는 direct Vulkan surface를 막으므로 이 진단에서는 기존 guest flags를 그대로 상속하면 안 된다. Chromium X11의 surface gate는 DRI3 등의 확장 존재 여부를 검사한다. [Chromium X11 Vulkan](https://github.com/chromium/chromium/blob/152.0.7977.82/ui/ozone/platform/x11/vulkan_implementation_x11.cc).

## 지원하지 않는 경로를 반복하지 않기

공식152의 Wayland=false는 기존 guest Chromium의 Wayland GL/Vulkan 문제와 별개의 빌드 경계다. 과거 guest ANGLE GLES24.9%, software compositor0.66%, DRM shim만 넣은 create_dumb ENOTTY를 native 성공 근거로 재사용하지 않는다. 향후 native Wayland 패키지를 만들려면 frontend를 활성화하고 bionic native GBM/EGL DMA-BUF 경로까지 검증해야 하며, 단순 launch flag 변경 범위를 넘는다. 실제 native X11 비교 결과를 얻기 전 대규모 Chromium 재빌드를 권장하지 않는다.

## 추가: 기존 KGSL shim으로 별도 Xwayland glamor/DRI3 시험

부모 작업의 native Chromium→guest Xwayland 시험은 Adreno830/GaneshVulkan GPU 합성에 성공했지만 4K 로컬1080p60+3회 편집30초에서3.47% drop이었다. 따라서 native 실행만으로 충분하다고 판정하지 않는다.

### 설치 버전과 실제 초기화 경로

로컬 `build/diagnostics/termux-omarchy-full-package-audit-device-20261009-01/receipt.json`의 설치 목록은 `xorg-xwayland 24.1.13-1`이다. 로컬10/7 executable receipt도24.1.13이다. 이후 변경 여부는 최신 기기 버전 조회로 확인해야 한다. 같은 버전 공식 tarball이 이미 보존되어 있어 해당 소스로 조사했다. SHA256 `173aea3d6f79609164c04528e1c8e4c9b60fcd59391c3c9dad4667297d727fb6`. [공식24.1.13 소스](https://www.x.org/releases/individual/xserver/xwayland-24.1.13.tar.xz).

이 버전의 `hw/xwayland/xwayland-glamor-gbm.c`에는 **wl_drm 없는 compositor도 지원하는 경로**가 있다. `xwl_glamor_gbm_init_main_dev`가 linux-dmabuf default feedback을 기다리고 main device의 render-node를 연다. `xwayland-dmabuf.c:466–481`은 feedback의 dev_t를 `drmGetDeviceFromDevId`로 해석한다. 이후 `drmGetDevice2`, `gbm_create_device`, EGL_PLATFORM_GBM_MESA, GL/GLES context, GL_OES_EGL_image를 검사한다. software renderer는 거절한다. 이것은 앞서 오래된 mirror 코드로 내린 일반적 DRM 장벽 설명보다 정확한 설치 버전의 경로다.

로컬 `build/termux-va-research-20261012/mesa-source/src/termux-va/tva_drm_shim_wayland.c`는 **바로 이 libdrm 함수들을 이미 감싼다**. KGSL dev_t를 `/dev/kgsl-3d0` render-node로 표현하고, drmGetDevice2/NodeType/GET_CAP을 제공한다. 따라서 이 shim과 KGSL GBM Mesa를 함께 넣으면 코드상 초기화 gate를 통과할 현실적인 후보가 있다. shim만으로는 부족하다. 같은 Mesa의 `loader.c`는 TERMUX_VA_GPU_BACKEND=kgsl일 때 KGSL fd에 driver kgsl을 선택하고, `gbm_dri.c`는 dmabuf export가 없으면 create_dumb으로 내려간다. 이전 shim-only create_dumb ENOTTY 실패가 이 조합 전체를 기각한 것은 아니다.

동기화의 한계도 명확하다. shim은 실제 DRM syncobj를 구현하지 않으며 미지원 GET_CAP은0이다. Xwayland24.1.13은 timeline syncobj 없으면 explicit-sync를 끄고 기본 DRI3 screen info(version2 callback set)를 사용한다. 이는 glamor 전체 비활성화 조건이 아니다. implicit DMA-BUF 동기화와 프레임 완성은 따로 픽셀 시험해야 한다. cap을1로 위장하거나 fence 대기를 제거하는 패치는 하면 안 된다.

### main 세션을 유지하는 격리 실험

현재 guest Hyprland의 Wayland socket을 사용하되, **새 rootful Xwayland 인스턴스**를 미사용 display 번호 또는 `-displayfd`로 실행한다. rootless와 main compositor의 wmfd는 넘기지 않는다. 기본 rootful 창 안에서 검사하고 main Xwayland는 그대로 둔다. 별도 auth cookie 또는 기존 검증된 scoped localuser 인증을 사용한다.

```text
XWAYLAND_NO_GLAMOR=0
LIBGL_DRIVERS_PATH=/opt/loopy-va-quiet-candidate/lib/dri
LD_PRELOAD=/opt/loopy-va-quiet-candidate/lib/libtva_drm_shim_wayland.so
LD_LIBRARY_PATH=/opt/loopy-va-quiet-candidate/lib
__EGL_VENDOR_LIBRARY_FILENAMES=/opt/loopy-va-quiet-candidate/share/glvnd/egl_vendor.d/50_mesa.json
TERMUX_VA_GPU_BACKEND=kgsl
TERMUX_VA_DRM_SHIM_LOG=1

/usr/bin/Xwayland :<미사용번호> -geometry 1280x800 -glamor es -nolisten tcp -auth <실험전용cookie파일>
```

환경은 이 guest 실험 프로세스와 자식에만 적용한다. 종료는 소유한 PID/세션으로 한정한다. `-glamor es`는24.1.13 man page가 지원하는 API 선택이며 빌드나 기기 성능 성공을 뜻하지 않는다. [Xwayland 매뉴얼](https://man.archlinux.org/man/Xwayland.1).

Gate 순서는 (1) feedback dev_t가 shim의 KGSL dev_t와 일치하는가, (2) GBM/EGL 초기화와 hardware GL renderer, (3) DRI3 확장 및 Open이 KGSL fd를 반환하는가, (4) 작은 Vulkan X11 surface/정상 동적 픽셀, (5) 새 Chromium profile에서 Vulkan surface 활성화 및 GPU crash0이다. source의 `xwl_dri3_open_client`는 render-node이면 fd를 그대로 전달하므로 DRM authentication은 우회된다. 그러나 client Vulkan driver가 그 KGSL fd를 해석할 수 있어야 한다.

**native Chromium에는 Weston 전용 AHB1255/1256 transport ICD를 사용하지 않는다.** 일반 Xwayland24.1.13의 `glamor_pixmap_from_fds`는 표준 GBM DMA-BUF import를 수행하며 Termux:X11의 socket/AHardwareBuffer transport를 이해하지 않는다. 일반 Turnip의 raw DMA-BUF export 경로가 필요하다. 각 process의 loaded ICD와 modifier를 기록해야 한다.

DRI3 동작 후 브라우저의 `--disable-vulkan-surface`를 제거하는 것이 비로소 의미 있다. gate 전 제거만 반복하는 시험은 권장하지 않는다. rootful nested 시험은 실제 main 세션 성능 수락이 아니라 capability 검증이다. 성공 후에만 창 관리·입력·크기 변경을 포함한 별도 통합을 설계한다. 이 시점에 Xwayland 재빌드나 새 KGSL backend patch는 필요하다고 입증되지 않았다.

## 추가: rootful 시험에서 compositor DMA-BUF global 부재 확인

부모 작업의 `glamor-rootful.json/log`는 GBM Wayland interfaces not available 후 software fallback이며 DRI3가 없었다. 이는 GBM context를 만들기 전 compositor protocol gate에서 실패한 것이다. Hyprland가 Weston으로 DMA-BUF를 **내보내는** 기능과, Hyprland가 클라이언트에게 DMA-BUF **수신 프로토콜을 광고하는** 기능은 별개다.

지정된 `build/omarchy-refresh-20261008/hyprland-source`에서 확인한 정확한 gate:

1. `src/managers/ProtocolManager.cpp:258`: renderer `getDRMFormats()`가 비어 있지 않을 때만 MesaDRM와 LinuxDMABUF 생성.
2. `src/protocols/MesaDRM.cpp:115`: compositor render-node fd 또는 drm fd로 `drmGetDevice2` 실패하면 global 제거.
3. `src/protocols/LinuxDMABUF.cpp:443`: ready 이벤트에서 같은 fd의 fstat/dev_t 실패 또는 `drmGetDeviceFromDevId` 실패면 global 제거. render-node를 다시 열거나 복제해야 한다.
4. 같은 파일 `commence():263`: 광고 후에도 각 incoming plane에 `drmPrimeFDToHandle` 및 `drmCloseBufferHandle` precheck를 실행한다. 기존 KGSL shim에는 이 두 함수의 지원이 없다. 광고만 강제로 켜면 다음 단계에서 ENOTTY로 실패할 수 있다.
5. `src/protocols/types/DMABuffer.cpp`는 실제 renderer texture/EGLImage import 성공 여부를 `m_success`로 유지한다. 따라서 KGSL에 맞는 import 검증 seam이 존재한다.

소스 receipt의 upstream commit은 `efb50993780079460b0cbed1363e2166a2de1d9f`이다. [upstream LinuxDMABUF](https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/protocols/LinuxDMABUF.cpp), [ProtocolManager](https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/managers/ProtocolManager.cpp), [MesaDRM](https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/protocols/MesaDRM.cpp). 위 line은 로컬 patched source 기준이다.

중요한 provenance 한계: 이 디렉터리에는 현재 실행환경의 `HYPRLAND_EGL_SURFACELESS`, `HYPRLAND_GL_DMABUF_EXPORT`, `HYPRLAND_ANDROID_DMABUF` 구현 문자열이 없다. 현재 실행 바이너리를 만든 최종 patch/source와 동일하다고 확인되지 않았다. 실제 컴파일 source를 찾기 전 이 디렉터리만 고쳐 배포하면 기존 출력 개선을 잃을 수 있다.

### 최소 변경 설계와 빌드 경계

먼저 현재 Hyprland EGL display의 import 확장·실제 format list·작은 exported linear RGBA DMA-BUF import를 확인한다. 로컬 `OpenGL.cpp:525`의 SHM mode는 출력용 ARGB/XRGB 형식을 `m_drmFormats`에 넣고 바로 반환한다. 주석도 이것이 DMA-BUF import 지원이 아님을 명시한다. 그러므로 nonempty 형식만 믿고 global을 강제 활성화하면 안 된다.

실제 import가 확인되면 protocol에 한정한 opt-in KGSL descriptor 경로가 가장 좁다. `/dev/kgsl-3d0`를 열고 character device 및 dev_t를 확인해 feedback main_device에 사용한다. MesaDRM의 node 광고도 같은 경로를 쓴다. renderer/aq의 기존 drm fd를 전역으로 바꾸면 surfaceless 선택, allocator, syncobj 여부까지 바뀌므로 피한다. LinuxDMABUF에서는 이 opt-in KGSL 경로에 한해 DRM PRIME ioctl precheck를 대체하고, 기존 size/plane/stride 검증과 **실제 EGLImage import 성공 검사**를 반드시 보존한다. 전역 drmPrimeFDToHandle 성공 위장은 하지 않는다. 형식과 modifier는 검증된 import 집합만 광고하고 scanout/explicit-sync 능력을 새로 주장하지 않는다.

이 단계는 Hyprland의 protocol 소수 파일에 대한 별도 후보 빌드로 가능하다. Xwayland나 Chromium 재빌드는 먼저 필요하지 않다. 다만 최종 실행 소스·의존성·현재출력 patch를 복원한 뒤 빌드해야 한다. 별도 nested Hyprland/socket에서 linux-dmabuf global과 feedback → sample import 정상 픽셀 → rootful Xwayland glamor/DRI3 → Vulkan surface 순서로 검증한다. 성공하기 전 main 세션의 XWAYLAND_NO_GLAMOR를 바꾸지 않는다.

## 확정된 v0.1.1 원인과 더 좁은 Xwayland 수정 후보

부모 작업이 실행 번들의 원본을 찾았다. `BlackFireAlex/omarchy-android` v0.1.1 commit `c189d33bf34a7a50fad3ff46bbd97e5c29b48910`, 실행 Hyprland SHA256 `c1f642c12b11e503eb3ab9e39468b1e017d36c91c736171ef04567740ca514b9`. 해당 [KGSL presentation patch](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/patches/hyprland/0001-render-carry-proven-Android-KGSL-presentation-path.patch)는 Android mode에서 **linux-dmabuf v3만 광고하고 MesaDRM을 생성하지 않도록 의도적으로 변경**한다. DRM fd가 없을 때 main_device0과 format table을 만들고 return해 PRIME precheck를 생략하되 실제 EGL import 검사를 유지한다. 따라서 앞 절의 일반적인 global 제거 설명이 현재 실행 원인은 아니다.

실제 실패와 정확히 맞는 코드는 Xwayland24.1.13 `xwayland-glamor.c:122`, `xwl_glamor_has_wl_interfaces`이다. wl_drm이 없고 dmabuf version<4이면 FALSE를 반환한다. v3 DMA-BUF import 자체가 없거나 실패했다는 증거가 아니며, 이 로그만으로 앞선 native Wayland Chromium이 전부SHM이었다고 결론 내리면 안 된다.

### 우선 후보: private Xwayland만 v3 KGSL 초기화 허용

Hyprland를 다시 빌드하지 않고, 기존24.1.13의 두 함수와 작은 opt-in helper를 변경하는 방식이 더 좁다.

1. `hw/xwayland/xwayland-glamor.c::xwl_glamor_has_wl_interfaces`: 새 환경변수(예: `XWAYLAND_KGSL_DMABUF_V3=1`)와 **실제 dmabuf 객체 존재, negotiated version==3, wl_drm 부재**가 모두 참일 때만 기존 reject를 예외 처리한다. v1/v2나 protocol 없는 서버는 허용하지 않는다. 기본 동작은 유지한다.
2. `hw/xwayland/xwayland-glamor-gbm.c::xwl_glamor_gbm_init_main_dev`: 같은 opt-in v3 조건이면 feedback_done 대기 전에 별도 KGSL 초기화를 한다. 고정 경로 `/dev/kgsl-3d0`를 O_RDWR|O_CLOEXEC로 열고 fstat/S_ISCHR 확인, 기존 shim의 drmGetDevice2와 drmGetNodeTypeFromFd==DRM_NODE_RENDER 확인 후 device_name/drm_fd/device/fd_render_node를 채운다. 성공하면 TRUE. 실패는 새로 연 fd/device/name을 정확히 해제하고 FALSE를 반환하며 **존재하지 않는 v4 feedback 대기로 떨어지면 안 된다**. 가능하면 로컬 임시값 검증 완료 후 struct에 이관해 기존 cleanup의 double close를 피한다.
3. `xwl_glamor_gbm_init_egl`은 이미 wl_drm이 없으면 위 init_main_dev를 호출하므로 기존 GBM/EGL/GLES/DRI3 로직을 그대로 사용한다. 새 shim API나 가짜 DRM kernel ioctl 성공 처리는 필요하지 않다.

피드백 의존성도 소스로 확인했다. `xwayland-dmabuf.c::xwl_glamor_get_formats`와 `get_modifiers`는 v3에서 이미 legacy `screen->formats`를 사용한다. per-drawable modifier/scanout 조회는 version<4이면 빈 결과와 scanout=false로 반환한다. version3 binding은 feedback object를 생성하지 않는다. 따라서 이 경로에 합성 v4 main_device를 추가할 필요가 없다. raw DMA-BUF GBM import와 linux-dmabuf v3 buffer 생성 경로는 기존 코드에 있다. [동일 버전 공식 전체 소스](https://www.x.org/releases/individual/xserver/xwayland-24.1.13.tar.xz).

기존 full KGSL Mesa+shim 환경을 사용해 private rootful 인스턴스로 검증한다. 성공 조건은 DRI3 extension만이 아니라 DRI3 Open, modifier 협상, Vulkan swapchain/동적 픽셀, import/release 및 창 resize 반복까지다. implicit sync 유효성과 성능은 별도 측정한다. main Xwayland 교체는 이 gate 이후이며 전역 환경·시스템 패키지 교체는 필요하지 않다.

### 후순위: Hyprland opt-in v4 feedback

v4 route도 기술적으로는 가능하다. Android fallback branch의 main_device와 renderer tranche.device를 같은 KGSL stat.st_rdev로 바꾸고, 동일한 사전검증 결과를 사용해 protocol version4를 선택한다. mainDeviceFD는 invalid로 유지하여 기존 PRIME precheck 생략과 실제 EGL import 검증을 보존한다. 기존 format table/default/surface feedback/done 구현은 이미 있다. 실패 시 v4를 광고한 채 device0을 전송하지 않는다.

다만 v4를 bind한 client에는 legacy format/modifier 이벤트가 더 이상 전송되지 않으며 feedback의 format_table, main_device, matching tranche, done 전체가 정확해야 한다. KGSL dev_t를 기존 libdrm client가 해석하려면 shim이 필요하다. 표준 DRM backend라고 주장할 수 없는 호환성 모드이고 다른 client의 allocation 선택도 바뀐다. 기존 client ABI와 프로토콜을 유지하는 private Xwayland v3 route를 먼저 시험하는 편이 범위가 작다. [공식 protocol XML](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/blob/main/stable/linux-dmabuf/linux-dmabuf-v1.xml).

## 구현된 private Xwayland 패치 독립 검토

검토 대상 `experiments/xwayland-kgsl-v3/apply.py`, 적용 소스 `build/xwayland-kgsl-20261012/source`. 부모 작업의 ARM 빌드 SHA256은 `1055fcfb8420777ff5b29c07a314e231773fd0be96f4e73811bcb00e461da522`이다. rootful 시험의 실제 DRI3 import3회(1823×1365, modifier0, plane1)와 GaneshVulkan/Adreno830은 부모 실행 receipt이며, 검토자가 기기를 변경하지 않았다.

패치의 opt-in 조건은 정확히 LOOPY_XWAYLAND_KGSL_V3=1, wl_drm 부재, dmabuf 객체 존재, negotiated v3이다. KGSL open/fstat/character-device/render-node/device metadata를 로컬 변수로 검증한 뒤 기존 소유 구조에 이관한다. 실패 시 fd/device를 해제하고 FALSE로 끝내므로 v4 feedback 대기 hang을 만들지 않는다. 기존 GBM/EGLImage import와 DRM capability probe/cleanup 코드를 유지한다. **검토한 변경에서 새 치명적 protocol/resource 결함은 발견하지 못했다.**

rootless 통합에는 별도 동기화 검증이 남는다. Xwayland24.1.13은 EGL_VENDOR가 NVIDIA가 아니면 implicit_sync=true로 간주하며 KGSL DMA-BUF reservation 지원을 검사하지 않는다. 패치가 fence 코드를 보존했다는 사실은 implicit sync가 실제로 성립한다는 증거가 아니다. rootless Present에는 direct flip 및 buffer release/reuse 경로가 있어 rootful 정상 픽셀만으로 전부 입증되지 않는다. directflip 조건 분기는 `hw/xwayland/xwayland-present.c`, implicit_sync 설정은 `xwayland-glamor-gbm.c::xwl_glamor_gbm_init_egl`에 있다. [동일 버전 공식 소스](https://www.x.org/releases/individual/xserver/xwayland-24.1.13.tar.xz).

production gate는 rootless에서 동적 frame ID/색상 픽셀 정확성, resize 반복, swapchain buffer 재사용 뒤 stale/corrupt frame 부재, 정상 release 진행과 Chromium GPU crash0이다. 3회 imported 로그는 transport 증거이며 이 gate 전체를 대체하지 않는다. 현 단계에서 fence 제거 또는 무조건 glFinish 추가를 권장하지 않는다.

## Native browser의 지속 가능한 launcher 통합 설계

부모 작업 보고: patched rootless Xwayland 세션9701cb12에서 native149+Code 로컬1080p60 30초1800frame/0drop/3회 저장. 이는 native 경로 유지의 근거이며 YouTube/Notion/장시간 수락과 패키지152 수락은 별도다.

### 권장 경계

현재 `termux/omarchy_android.py`의 소유된 native 서비스 패턴을 재사용하되 브라우저 로직은 별도 작은 모듈에 둔다. 현재 Android packet은 정확히 schema/token/nonce/action 네 필드이며 ACTIONS도 고정되어 있다. 여기에 임의 command/argv/env/cwd를 추가하지 않는다. browser용 schema/action은 엄격한 키 집합 `schema,token,nonce,action,urls,mode`만 받는 별도 검증으로 만들고, action은 browser-open, mode는 normal/app 같은 실제 사용되는 제한된 값으로 둔다. 필요 없는 옵션은 추가하지 않는다.

URL은 요청 전체4096byte 한도, 제한된 개수, 문자열/NUL/control 검사, http/https 및 명시적으로 필요한 about:blank만 허용한다. argv는 service가 고정 binary·고정 profile·검증된 graphic flags로 만들고 URL을 개별 인자로 전달한다. shell 문자열을 만들지 않는다. app mode도 단일 검증 URL을 고정 `--app=` 값으로 조립한다. guest 요청이 binary/profile/path/debug port/extension path 또는 일반 Chromium flags를 선택하게 하지 않는다. 로컬 preview는 http://127.0.0.1 형태로 동일 경계를 사용할 수 있다.

기존 서비스의 HMAC, session token, nonce replay window, same-UID SO_PEERCRED, owner PID/starttime, marker 검증을 유지한다. Android service는 현재 native X11 준비 직후이며 Hyprland 이전에 시작하므로 browser action은 Hyprland/Xwayland가 ready이고 현재 세션에 속할 때만 허용해야 한다. 요청 성공은 launch accepted로 표현하고 실제 창·GPU 성공과 구분한다.

### 소유권과 종료

bridge가 supervisor의 자식이고 browser가 bridge의 자식이면 기존 `OwnedProcesses.refresh()`가 PPID lineage로 발견할 수 있다. `OwnedProcesses.register()`는 직접 자식만 허용하므로 bridge가 낳은 browser PID를 supervisor의 register에 넣으면 안 된다. launcher는 Popen 뒤 실제 argv/UID/starttime/parent를 확인해 별도 browser 상태를 발행하고 재사용할 때도 일치시킨다. bridge는 child exit를 poll/reap하며 supervisor는 기존 subreaper/ECHILD 종료 증명을 유지한다. `run_bounded()`로 장시간 browser를 실행하면 timeout 정책과 충돌하므로 사용하지 않는다.

Chromium 재실행은 profile singleton으로 기존 browser에 요청을 전달하고 빨리 종료할 수 있다. 이미 존재하는 동일 profile 프로세스가 현재 세션 소유인지 먼저 확인해야 한다. 다른 세션의 singleton을 임의 종료하거나 채택하지 않는다. bridge 죽음·desktop stop 시 현재 세션 browser와 descendant가 정리되고, persistent profile 내용은 남아야 한다. [Chromium user data directory](https://chromium.googlesource.com/chromium/src/+/main/docs/user_data_dir.md)는 서로 다른 실행 인스턴스의 동일 profile 동시 사용과 여러 display 사용의 제한을 설명한다.

### Xwayland 인증과 native socket 경로

진단 코드의 `/proc` 전체에서 마지막 Xwayland를 고르는 방식과 고정 DISPLAY=:0을 제품 경로에 복사하지 않는다. session ownership ledger의 Xwayland PID/starttime/UID/argv 및 socket inode를 사용해 display와 auth 파일을 확정한다. native `$PREFIX/tmp/.X11-unix/Xn` mapping이 필요하면 기존 inode를 덮어쓰지 않고 정확한 현재 guest socket만 가리키는 항목을 ledger에 기록해 소유 항목만 retire한다.

현재 검증된 XAddHost ServerInterpreted localuser 방식은 **실제 Android kernel UID `os.getuid()`**로 구성한다. 진단의 #10323을 하드코딩하지 않는다. 기존 access list를 읽어 이미 있는 항목은 소유했다고 주장하지 말고, 새로 추가한 항목만 해당 Xwayland identity에 묶어 기록한다. server가 살아 있는 동안 browser 종료/서비스 종료 시 자기 추가 항목을 제거한다. xhost+ 또는 access-control disable은 필요하지 않다. 인증 helper가 guest 컨텍스트를 요구하면 supervisor의 고정 helper 호출로 처리하고 bridge가 임의 guest 명령을 받지 않게 한다. socket/peer가 바뀌면 이전 auth 상태를 재사용하지 않는다.

### Profile·152 패키지·커스텀 launcher

149에는 guest151 profile을 절대 지정하지 않는다. native 전용 persistent user-data-dir를 별도로 두며 guest profile의 기존 설정·로그인·bookmarks는 그대로 남긴다. fresh native profile의 Notion 로그인은 기존 guest 상태와 같지 않다. native152로 올려도 같은 Linux 계열이라는 이유만으로 암호화 cookies/키링을 포함한 profile 복제 호환성을 보장할 수 없다. UI 설정/확장기능은 확인된 항목만 개별 이관하고 profile downgrade/동시 쓰기를 피한다.

지속 배포는 공식 apt candidate152를 정상 package manager로 설치한 뒤 동일 workload를 재검증하는 방식을 우선한다.149의0drop은152의 성능 증거가 아니다. 새 버전이 profile을 쓴 뒤 binary만149로 되돌리는 rollback은 금지한다. 버전별 시험 profile로 먼저 검증하고, persistent profile upgrade 전에는 닫힌 상태 backup을 준비한다. 공식152는 위 조사대로 X11/ANGLE Vulkan용이며 Wayland frontend는 여전히 없다.

private152 .deb 추출은 시스템149를 유지하는 장점이 있지만 Chromium binary·ANGLE·Vulkan loader·resources·locale·helper와 native dependency closure, compiled PREFIX 경로를 함께 관리해야 한다. 단일 chrome 파일 복사나 guest library 혼합은 적합하지 않다. private package가 apt upgrade보다 작거나 단순하다고 볼 근거가 없어 기본 권장으로 삼지 않는다. 기존 공식 [recipe의 배포 파일 목록](https://github.com/termux/termux-packages/blob/aed8f2405a392e49b487eb7ac0ed2eded4f45015/x11-packages/chromium/build.sh)을 기준으로 한다.

guest에는 고정 `loopy-native-browser` client와 별도 desktop entry를 제공하고 검증된 Omarchy browser/webapp 진입점에 연결한다. 시스템 chromium binary 자체를 덮어쓰거나 기존 사용자 커스텀 launcher 파일을 일괄 치환하지 않는다. 먼저 현재 browser.desktop, MIME default, Omarchy browser/webapp wrapper와 keybind 호출 인자를 읽어 normal URL/app URL/new-window 등 실제 사용 집합을 매핑한다. 지원하지 않는 사용자 옵션은 조용히 무시하지 말고 기존 guest151 경로를 명확히 유지한다. native profile에서 필요한 사용자 확장과 URL 동작을 확인한 뒤 기본 진입점만 바꾸고 원본·변경 digest·rollback을 보존한다. 진단용 remote-debugging port는 일반 launcher에서 열지 않는다.

## 장시간 trial 종료 후 메모리 lifecycle 검토

부모 작업의180초 trial은 약16:16 같은 kernel boot에서 Termux UID 자식들이 종료됐고,16:14부터 ZuiMemoryCleaner Aggressive-SwapFreeCritical→MemFreeCritical 및 편집 지연이 관찰됐다. 따라서 앞선60초 zero-drop을 안정성 수락으로 사용하지 않는다. 아래는 원인 확정이 아니라 소스에 근거한 계측 우선순위이다.

가장 직접적인 증가 경로는 `xwayland-window-buffers.c::xwl_window_swap_pixmap`이다. available buffer가 없으면 새 window buffer와 pixmap을 할당하며 unavailable list에 개수 상한이 없다. `xwl_window_buffer_release_callback`이 buffer를 available로 돌려야 재사용되고, timeout 정리는 available buffer에 적용된다. compositor의 wl_buffer.release 누락/지연이면 새4K버퍼가 계속 늘어날 수 있다.3840×2560×4는37.5MiB이며 실제 창 크기/stride에 따른다. 새 buffer 수, release 수, destroy 수, available/unavailable 현재 개수를 같은 시간축에서 집계하는 것이 우선이다. 강제release나 fence 대기 제거로 우회하면 안 된다. [Xwayland24.1.13 공식 소스](https://www.x.org/releases/individual/xserver/xwayland-24.1.13.tar.xz).

정상 cleanup에서는 뚜렷한 per-frame 누락을 찾지 못했다. `xwl_glamor_pixmap_get_wl_buffer`는 pixmap당 wl_buffer를 캐시하고 전달용 prime fd를 close한다. `xwl_glamor_gbm_destroy_pixmap`은 마지막 pixmap reference에서 wl_buffer/EGLImage/GBM BO를 제거한다. rootless direct Present release는 idle 알림과 pixmap reference 해제를 진행한다. 이번 private patch의 KGSL device allocation은 EGL 초기화당 한 번이며 frame당 실행되지 않는다.

local termux-va Mesa의 `src/freedreno/drm/kgsl/kgsl_bo.c`는 import마다 IOCTL_KGSL_GPUOBJ_IMPORT와 dupfd를 수행하고, `kgsl_bo_close_handle`에서 dupfd close와 GPUMEM_FREE_ID를 수행한다. `fd_bo_fini_common`도 mapping 해제와 handle-table 제거를 한다. close ioctl 반환값을 현재 무시하므로 kernel handle free 성공 여부는 소스만으로 확인할 수 없다. import/free 및 duplicated-fd open/close의 차이와 KGSL mapped bytes를 프로세스별로 집계하면 좋다. 동일 DMA-BUF FD를 여러 process에서 참조한 메모리는 단순합산하면 중복될 수 있으므로 inode/size 식별과 PSS를 병행한다.

별도 오류 경로 결함은 있다. kgsl_bo_from_dmabuf는 fd_bo_from_handle이NULL일 때를 검사하지 않고 역참조하고, dupfd 실패도 검사하지 않는다. 공통 import_bo_from_handle의 생성실패 정리는 DRM_GEM_CLOSE이므로 KGSL 실패경로에 맞지 않는다. 이는 메모리 압박 시 추가 실패를 만들 수 있지만 정상 frame마다 누적되는 leak의 원인으로 확정할 수 없다. 현재메모리증가부터분리하고, 무관한대규모Mesa변경으로섞지않는다.

진단은 native browser GPU/renderer/main, guest Xwayland, Hyprland, native Weston 각각의 RSS/PSS, fd 수, DMA-BUF 참조, KGSL object bytes를 같은 간격으로 본다. Xwayland/Hyprland buffer가늘면release/import경계, browser anonymous memory만늘면browserheap/raster/swapchain쪽으로좁힌다. graphically정상인60초표본은장기resourceboundedness를증명하지않는다.

## Code 동시 실행의 메모리 압박: 다음 구현 선택

부모 작업이 native browser+local video+YouTube 약120초의 RSS/FD 안정성을 확인했고, 기존 guest Code를 추가하면 process RSS+swap 합계가 약1.5–2GB 늘며 MemAvailable800MB 미만으로 내려가 browser를 종료하는 guard가 동작했다. 이 결과는 단순 Xwayland import leak 주장보다 editor workload의 추가 메모리 비용을 우선 조사할 근거다. process RSS 합계는 공유 page를 중복 계산하므로 editor backend+browser 전체 PSS/SwapPss와 MemAvailable 추세를 함께 비교한다.

현재 `termux/loopy-vscode`는 공식 portable1.141.0, guest user-data/extensions 경로, `--ozone-platform=wayland`만 지정한다. `--use-gl=disabled`와 `--disable-gpu`는 이 wrapper에 없다. 현재 실제 renderer가 disabled GL이면 argv.json의 hardware acceleration 설정, inherited launch args 또는 Electron GPU 초기화 fallback을 확인해야 한다. GPU를 켠다는 것만으로 JS/editor heap이 줄어드는 것은 아니며4K texture memory가 늘 수도 있다.

### 실제 패키지 및 경로

- **TUR code-server**: 공식 Coder 문서가 `pkg install tur-repo` 후 `pkg install code-server`를 안내한다. 현재 TUR recipe4.141.0의 dependency는 nodejs-24, libandroid-spawn, libsecret, krb5, ripgrep이고 aarch64를 제외하지 않는다. 실제기기 apt candidate/dependency 변경은 설치전 확인해야 한다. [Coder Termux 문서](https://coder.com/docs/code-server/termux), [TUR recipe](https://github.com/termux-user-repository/tur/blob/master/tur/code-server/build.sh).
- **Native Code-OSS**: 공식 Termux `x11-packages/code-oss`에 존재한다. 현재 recipe1.132.0, electron42 의존성이다. guest1.141보다 이전 버전이며 별도 Electron runtime도 유지하므로 profile 재사용이나 큰 메모리 절감을 전제하면 안 된다. [공식 Code-OSS recipe](https://github.com/termux/termux-packages/blob/master/x11-packages/code-oss/build.sh).
- **Guest code-server + native browser UI**: guest filesystem/toolchain/terminal/extension host를 유지하고 UI만 이미 실행 중인 native Chromium으로 옮긴다. 별도 Electron main/GPU runtime을 줄이는 구조적 후보다. renderer/extension-host 메모리까지 사라지는 것은 아니므로 절감량은 측정해야 한다. Coder는 Linux arm64 standalone release 설치를 지원한다. [Coder 설치 문서](https://coder.com/docs/code-server/install).
- **공식 VS Code CLI serve-web**: Microsoft가 standalone local web server 기능을 공식 지원한다. 기존 official portable bundle의 code-tunnel/CLI에서 `serve-web --help`를 우선 확인하면 다른 editor distribution을 추가하지 않고 동일 구조를 시험할 수 있다. 서버 component 다운로드와 버전 고정은 필요할 수 있다. 인터넷 원격 tunnel 로그인과 local serve-web은 다른 모드다. [Microsoft release note](https://github.com/microsoft/vscode-docs/blob/main/remote-release-notes/v1_82.md), [CLI source](https://github.com/microsoft/vscode/tree/main/cli/src/commands).

### 권장 순서와 보존 경계

가장 작은 검증은 existing official guest CLI의 **serve-web backend + 같은 native Chromium profile의 editor window/tab**이다. 불가능하면 guest Linux ARM64 code-server backend가 다음이다. localhost의 사용 가능한 고정 포트에만 바인딩하고 session token/password를 사용한다. Electron Code를 정상 종료한 상태에서 같은 프로젝트의 편집·저장·preview·terminal·필요 extension을 비교한다. localhost backend도 command execution 권한이 있으므로 public bind/auth-none으로 바꾸지 않는다. 기존 supervisor 소유 descendant 및 stop cleanup에 포함한다.

데이터는 `/opt/loopy-vscode/1.141.0/data`를 그대로 보존하고 별도 backend data/extensions 디렉터리로 시작한다. settings.json/keybindings/snippets는 backup 후 별도경로에 복사하되 platform-specific terminal path와 browser keybinding 충돌을 확인한다. 확장은 목록·버전·native binary 의존성을 기록한 뒤 필요한 항목부터 검증한다. 원본 extensions 디렉터리를 새distribution과 공유해양쪽이동시수정하게하지않는다.

Native TUR backend는 PRoot 비용까지 줄이지만 Android와 glibc용 language server/native extension ABI가 달라 migration 범위가 커진다. 공식 Coder 문서도 Android platform의 extension 설치 제한과 native dependency 문제를 명시한다. `process.platform=linux` 위장은 bionic을 glibc로 바꾸지 못한다. Coder/OpenVSX와 Microsoft Marketplace도 동일하지 않으며 공식 Code 전용 extension이 모두호환된다고볼수없다. 따라서 guest backend를먼저시험하고nativebackend는필수확장·도구의Android호환이확인된경우에만선택한다. [Coder FAQ](https://coder.com/docs/code-server/FAQ), [Android extension 제한](https://coder.com/docs/code-server/termux).

Code GPU 시험은 UI반응 개선의 별도 후보이다. 사용자 argv.json과 원본 profile을 바꾸기 전에별도clone으로, patched Xwayland에 X11+ANGLE Vulkan을 연결해 GPU compositing 실측을 확인할 수 있다. 그러나700MB renderer와168MB GPU process라는수치만으로hardware acceleration이전체1.5–2GB를줄일것이라고추정하지않는다. 첫우선순위는중복Electronruntime제거후전체PSS·swap·입력지연을측정하는것이다. 어느경로도기존커스텀설정·확장기능·향후remote워크플로를무조건대체하지않는다.

## serve-web 1.141.0 설정·확장 이관의 정확한 저장소

실행 중인 버전과 같은 Microsoft commit `2a59476c9bfcb90b3ddc372c36762471b7dfad1c`를 확인했다. `server.main.ts`는 `--server-data-dir` 아래에 다시 `data`를 붙여 user-data-dir를 만들고, extensions는 server-data-dir 바로 아래에 둔다. 따라서 현재 인자 `/home/omarchy/.local/share/loopy-code-web/data` 기준 경로는 다음이다. [고정 소스](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/src/vs/server/node/server.main.ts#L41).

| 용도 | guest 경로 |
| --- | --- |
| Remote 설정 | `/home/omarchy/.local/share/loopy-code-web/data/data/Machine/settings.json` |
| Server User 데이터·확장 globalStorage | `/home/omarchy/.local/share/loopy-code-web/data/data/User/` |
| Server 설치 확장 | `/home/omarchy/.local/share/loopy-code-web/data/extensions/` |

브라우저 User 설정은 위의 `User/settings.json`이 아니다. Web 환경은 `vscode-userdata:/User`를 쓰고 `web.main.ts`는 기본 user-data provider로 origin별 IndexedDB `vscode-web-db`의 `vscode-userdata-store`를 등록한다. 따라서 server-data-dir/User 또는 server-data-dir/data/User에 desktop settings를 복사하는 것만으로 Web User 설정이 이관되지 않는다. localhost와127.0.0.1, 포트, Chromium profile을 바꾸면 다른 browser 저장소가 될 수 있으므로 진입 origin/profile을 고정한다. [Web 환경](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/src/vs/workbench/services/environment/browser/environmentService.ts#L110), [IndexedDB provider](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/src/vs/workbench/browser/web.main.ts#L520).

Remote 설정은 이름과 달리 MACHINE 범위만 허용하지 않는다. REMOTE_MACHINE_SCOPES는 WINDOW, RESOURCE, LANGUAGE_OVERRIDABLE, MACHINE_OVERRIDABLE 및 APPLICATION_MACHINE도 포함한다. `RemoteUserConfiguration`은 remote environment의 settingsPath를 이 범위로 파싱하며 settingsPath는 machineSettingsResource이다. 따라서 editor font/format settings 및 `workbench.colorTheme`를 Remote Machine/settings.json에 적용할 수 있다. colorTheme에는 별도scope가 없어 registry의 WINDOW 기본값을 사용한다. 해당 theme extension 설치와 실제 선택 결과는 별도 확인한다. 일반 APPLICATION 설정은 Remote 범위에서 제외된다. [범위 정의](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/src/vs/workbench/services/configuration/common/configuration.ts#L32), [Remote 파서](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/src/vs/workbench/services/configuration/browser/configuration.ts#L398), [theme schema](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/src/vs/workbench/services/themes/common/themeConfiguration.ts#L35), [scope 기본값](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/src/vs/platform/configuration/common/configurationRegistry.ts#L836).

최소 이관은 원본 설정을 보존한 상태에서 Remote로 적용 가능한 설정만 위 Machine/settings.json에 merge하고, keybindings/snippets 및 APPLICATION 설정은 Web UI의 User 설정 또는 공식 Profile import로 가져오는 것이다. 전체 desktop profile의 SQLite/IndexedDB 파일을 직접 덮어쓰지 않는다. 공식 Profiles의 export/import는 설정·키보드·snippets·확장 선택 이관을 제공한다. [Microsoft Profiles 문서](https://code.visualstudio.com/docs/configure/profiles).

동일 guest Linux arm64와 동일 VS Code commit을 쓰므로 기존 확장 payload를 **별도** server extensions 폴더에 복제하는 실험은 Android native backend보다 ABI 변화가 작다. 그러나 desktop Electron Node와 server Node의 native addon ABI, extensionKind, browser entry 지원은 따로 확인해야 한다. 단순 폴더 복제로 모든 확장이 실행된다고 판정하지 않는다. 원본 VSIX가 있으면 pinned server CLI에 VSIX를 재설치하고 list/activation을 확인하는 방식이 등록 상태까지 검증하기 쉽다. copied metadata에 원본 absolute URI가 있으면 그대로 재사용하지 않으며 original directory를 writable 공유하지 않는다.

특히 기존 설치 receipt에는 Remote SSH/Remote Explorer가 있다. Web에는 UI 측 local Node extension host가 없으므로 ui-only Node 확장은 지원되지 않을 수 있고, desktop Remote SSH 연결 UX가 이 경로에서 동일하게 동작한다고 보장할 수 없다. 기존 Electron과 해당 profile/확장은 보존한다. 이번 local 편집·preview 성공은 나중에 수행할 remote 연결 수락을 대신하지 않는다. [공식 extension host 표와 extensionKind 규칙](https://code.visualstudio.com/api/advanced-topics/extension-host).

## 최종 fast route의 지속 실행·사용자 설정 보존 검토

부모 작업의 당시 물리 RGB gate는 native Chromium149의 `--disable-vulkan-surface` 경로에서 화면 업데이트와 Web Code 키 입력281–283 저장을 확인했다. 그러나 후속 장시간 측정은 약59% video drop을 보였으며, 이전 stale 화면 판단에는 background CDP target과 실제 foreground tab의 불일치가 있었다. 따라서 이 플래그를 durable bridge에 고정하라는 당시 권고는 철회한다. 아래 최신 A/B 조건으로 presentation 경로를 다시 판정해야 한다. 현재 `loopy-vscode`와 desktop entry는 여전히 Electron용이다.

최소 지속 실행은 별도 고정 `loopy-code-web` guest launcher로 pinned code-tunnel serve-web을 시작/재사용하고, 준비된 URL만 기존 browser bridge로 전달하는 방식이다. 일반 command/argv endpoint를 bridge에 추가할 필요가 없다. 동일 supervisor descendant로 backend를 시작하고 현재 PID/starttime/command·session ownership을 확인해 재사용한다. 포트가 열린 사실만으로 기존 프로세스를 채택하지 않는다. localhost8765, 동일 commit, private connection-token-file, persistent cli/server-data/tmp 경로를 고정한다. bootstrap download를 session IPC 안에 두지 않으며 로그도 private persistent 위치와 크기 제한을 둔다. CLI는 시작 시 token을 포함한 URL을 로그에 기록하므로 원본 log를 진단 receipt에 그대로 노출하지 않는다. [고정 serve-web 구현](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/cli/src/commands/serve_web.rs#L149).

원래 `loopy-vscode`는 remote/desktop-only 확장용으로 보존한다. 현재 `%F` launcher 계약을 단일 고정 프로젝트 URL로 조용히 바꾸지 않는다. 새 launcher는 지원하는 folder/file 입력을 URL encode하여 전달하고, 지원하지 않는 CLI 옵션은 기존 desktop 경로로 명시적으로 남긴다. 사용자가 선택한 기본 local editor 진입점만 web으로 연결한다.

### 사용자 profile의 한번만 이관

`Loopy Omarchy` 같은 별도 named profile을 공식 Import Profile UI로 만들면 settings/keybindings/snippets를 실제 Web User provider에 쓸 수 있다. source desktop User 원문과 source hash, 이관 profile 이름, browser origin/profile을 작은 migration receipt에 남긴다. 매 실행 때 덮어쓰면 이후 사용자의 Web 설정 수정이 사라지므로 한 번만 이관하고 재실행은 상태를 유지한다. 불완전한 import는 완료로 표시하지 않는다. [공식 profile workflow](https://code.visualstudio.com/docs/configure/profiles).

같은 commit의 profile schema는 outer JSON의 settings/keybindings/snippets 값 각각이 **JSON 문자열**이다. settings resource는 `{settings: <원문 JSONC 문자열>}`, keybindings resource는 `{keybindings: <원문 JSONC 문자열>, platform: <원본 platform>}`, snippets resource는 `{snippets: {<상대파일명>: <원문>}}`이다. 수동 파일 구성 시 settings.json 원문을 outer settings에 바로 넣는 식으로 한 겹을 생략하면 안 된다. 가능하면 기존 공식 export를 사용하고, 파일로 구성할 경우 정확한 버전 importer가 preview/적용하는지 확인한다. globalState/secret storage/cache는 복사 대상에 포함하지 않는다. [profile template](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/src/vs/workbench/services/userDataProfile/common/userDataProfile.ts#L53), [settings resource](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/src/vs/workbench/services/userDataProfile/browser/settingsResource.ts), [keybindings resource](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/src/vs/workbench/services/userDataProfile/browser/keybindingsResource.ts), [snippets resource](https://github.com/microsoft/vscode/blob/2a59476c9bfcb90b3ddc372c36762471b7dfad1c/src/vs/workbench/services/userDataProfile/browser/snippetsResource.ts).

SettingsResource.apply는 MACHINE/APPLICATION_MACHINE/MACHINE_OVERRIDABLE 범위를 의도적으로 제외한다. 따라서 terminal executable/tool paths 등 machine 설정은 위 Remote Machine/settings.json에 별도 merge해야 한다. UI settings/keybindings/snippets와 remote machine 설정을 두 저장소에 맞게 이관한 뒤 reload/restart 후에도 유지되는지 확인한다. 브라우저가 가로채는 Ctrl+1 같은 조합은 원본 설정을 삭제하지 말고 web profile에서 필요한 충돌만 대체한다. browser UI에서 실제 키 입력으로 확인해야 하며 command 실행 성공만으로 shortcut 보존을 판정하지 않는다. [공식 web keyboard 제한](https://code.visualstudio.com/docs/remote/vscode-web).

### Native browser 로그인 보존

현재 bridge의 persistent `~/.config/loopy-native-chromium`을 계속 사용하고 editor origin도 `http://127.0.0.1:8765`로 고정한다. browser profile은 Notion cookies/local storage 및 Code IndexedDB의 지속성 경계이다. session stop은 프로세스와 소유 socket links만 정리하며 이 profile을 지우지 않는다. guest151 profile은 native149로 다운그레이드 복제하지 않는다. 이미 native의 다른 진단 profile에서 로그인한 상태라면 현재 bridge 경로와 동일한지 먼저 확인해야 한다. 로그인한 profile을 바꾸면 유지된다고 주장할 수 없다. [Chromium user data directory](https://chromium.googlesource.com/chromium/src/+/main/docs/user_data_dir.md).

정상 stop→restart 후 Code 테마·사용자 shortcut·snippet 동작 및 Notion 기존 세션이 유지되는지 확인하는 것이 최소 durable gate이다. 실제 사용자 인증이 아직 native profile에 없으면 guest 로그인 원본을 보존하고 native 로그인 필요 상태를 명확히 남긴다. 프로필 파일 존재나 Notion 공개 페이지 로드만으로 로그인 보존을 수락하지 않는다.

## 최신 정정: disable-vulkan-surface는 성능 개선으로 입증되지 않음

부모 작업의 장시간 결과는 native149 + disable-vulkan-surface + YouTube1080p60 + Web Code 실제3회 저장에서 메모리 약1.2GB가 안정적이었으나 video drop 약59%였다. 반면 앞선 no-disable zero-drop 표본은 Code CDP target이 background tab인 상황을 포함할 수 있다. 따라서 두 표본을 동등한 visible workload 성능 비교로 사용하지 않는다. background screenshot 또는 정지 화면만으로 Vulkan presentation 결함을 확정했던 추정도 철회한다.

**Chromium149.0.7827.155 소스에서 확인한 의미:** `InitializeForVulkan`은 offscreen/플랫폼 presenter 경로를 먼저 처리한다. 이후 `disable_vulkan_surface`가 false일 때만 `SkiaOutputDeviceVulkan::Create`를 호출하고, X11 fallback이 허용될 때 생성 실패 또는 flag=true이면 `SkiaOutputDeviceX11`을 선택한다. 따라서 flag를 제거해도 Vulkan surface 생성이 실패하면 CPU fallback으로 돌아갈 수 있다. renderer 문자열만으로 direct present 성공을 판정할 수 없다. [149 초기화 분기](https://github.com/chromium/chromium/blob/149.0.7827.155/components/viz/service/display_embedder/skia_output_surface_impl_on_gpu.cc#L2103).

`SkiaOutputDeviceX11::Present`는 Ganesh context에서 surface의 `readPixels`로 CPU SkPixmap을 채운 뒤 `ui::DrawPixmap`과 X11 Flush를 호출한다. 소스의 TODO는 XShmPutImage 전환이며 이 경로를 이미 zero-copy 또는 SHM-present라고 부르면 안 된다. GaneshVulkan/GPU compositing enabled 상태에서도 이 CPU readback/present가 실행될 수 있다. 4K에서 frame time을 소비할 구체적 경계이며,59%drop의 원인 확정에는 동일조건 A/B가 필요하다. [149 Present 구현](https://github.com/chromium/chromium/blob/149.0.7827.155/components/viz/service/display_embedder/skia_output_device_x11.cc#L101).

Vulkan X11 instance는 surface를 요청했더라도 X server capability gate를 통과하지 못하면 surface=false로 내리고, 이 경우 CreateViewSurface는 null을 돌려준다. gate는 DRI3/ATIFGLRXDRI/NV-CONTROL 중 지원되는 확장을 확인한다. 현재 patched Xwayland의 실제DRI3는 이 관문을 여는 근거이며 최종 swapchain/present 성공 증거는 아니다. [Vulkan X11 instance](https://github.com/chromium/chromium/blob/149.0.7827.155/ui/ozone/platform/x11/vulkan_implementation_x11.cc#L36), [X server gate](https://github.com/chromium/chromium/blob/149.0.7827.155/ui/base/x/x11_util.cc#L645).

### 최소 다음 실험

첫 비교에서는 현재 verified native Turnip ICD, ANGLE Vulkan, enabled Vulkan/VulkanFromANGLE/DefaultANGLEVulkan, DPI, decode정책, profile, 창크기를 그대로 둔다. **disable-vulkan-surface 하나만 추가/제거**한다. 새 Mesa/Chromium upgrade, GPU raster flags, fence workaround, video decoder 전환을 함께 섞지 않는다. no-disable 후보가 현재 source상 direct Vulkan present의 좁은 후보이며 최적이라고 확정된 설정은 아니다. Weston의 AHB1255/1256 전용 ICD를 guest Xwayland에 연결하지 않는다.

두 비교 모두 서로 다른 실제 top-level 창에 video와 Code를 노출하고 각 CDP target의 URL/title/document.visibilityState 및 해당 Hyprland 창을 맞춘다. 같은 browser window의 background tab에서 code를 수정하면 동시사용 수락이 아니다. Page.bringToFront가 다른 tab을 숨기지 않는지 확인하고, 물리 RGB 변화는 현재 화면에 보이는 target/좌표에 대해 bounded 횟수로 확인한다. video decoded/drop delta와 실제 native 키 입력 후 disk 저장, compositor CPU 및 memory 추세를 동일시간창에서 기록한다. 최종 direct route 수락에는 화면 변화와 resize/reuse 정합성, GPU crash0 및 장시간 동시 workload를 함께 요구한다. 현재까지 메모리 안정은 별도 긍정 증거이며59%drop을 상쇄하지 않는다.

## GPU Present 물리 freeze 확정 뒤의 좁은 진단

후속 parent A/B에서 native149 no-disable 경로는 foreground target을 명시하고 CSS RGB를3회 바꿔도 물리 출력이 초기 페이지에 머물렀다. DOM/counter가 진행하는데 physical gate가 실패했으므로 이 표본의0drop은 수락 증거가 아니다. 반대 CPU present 경로는 물리갱신하지만 약59.6%drop이었다. 이 결과는 앞선 background target 혼동을 제거한 별도 증거이다. 이후 공식 native Chromium은 signed apt metadata 갱신 뒤155.0.8059.39로 갱신되었다고 parent가 보고했다. 위149 소스 결론은149에 고정하며155의 동일 분기/실행 결과를 자동으로 가정하지 않는다.

Xwayland24.1.13 local소스에서 `xwl_glamor_gbm_init_egl`은 EGL_VENDOR가 NVIDIA가 아니면 implicit_sync=true로 간주한다. `xwl_present_check_flip`은 이 상태나 explicit sync를 요구하고, direct flip은 client pixmap의 wl_buffer를 직접 attach/damage/commit한다. `xwl_present_buffer_release`가 idle 알림과 reference 해제를 수행한다. KGSL의 실제 dma-resv fence 연동을 이 vendor 검사로 입증할 수 없다. client GPU producer fence 문제, 전달한 buffer의 stale contents/alias, Hyprland damage/import 경계, WSI idle/completion 정지 모두 아직 구별되지 않는다. 메모리 안정은 release가 완전하다는 증거도 아니며 단순 영구freeze를 일반 tearing 문제로 단정하지 않는다. [Xwayland24.1.13 원본](https://www.x.org/releases/individual/xserver/xwayland-24.1.13.tar.xz), [dma-buf/fence/reservation 의미](https://docs.kernel.org/driver-api/dma-buf.html).

허가된 실험 구현은 `experiments/xwayland-kgsl-v3/apply-present-diagnostics.py`에 추가했다. 별도 source에 기존 apply.py 다음으로 적용하며 main build/source와 기기는 수정하지 않았다. diagnostics 토글은 bounded request/flip-commit/flip-complete/release/copy 카운터를 남긴다. 추가 no-direct-flip 토글은 KGSL v3 조건에서 check_flip만FALSE로 하여 기존 Present GPU-copy 경로를 선택한다. 기본동작과 fence/ownership/release 로직은 변경하지 않는다. 사용법/판정표는 같은 폴더의 PRESENT-DIAGNOSTICS.md에 있다.

이 분리 실험에서 정상copy가 물리갱신하고 directflip만멈추면 direct client buffer passthrough 경계를 좁힐 수 있다. 양쪽이멈추면 공통 producer/WSI data path가남는다. request가끊기는지, commit만진행하고release가끊기는지, 전부진행하는데pixel만stale인지 먼저분리한다. flip-complete는timer에서도올수있으므로물리출력성공으로치환하지않는다. glFinish는현재XwaylandGL context를끝낼뿐clientVulkan producer의fence가되지않는다. CPU DMA_BUF_SYNC도 GPU 작업 완료를 자동으로 보장하지 않으므로 이를임의동기화대체재로추가하지않는다.

## 원인 확정: native/guest libxshmfence 공유 메모리 ABI 불일치

parent의 no-direct-flip 실험은 정확히3개 DRI3 import 및3개 Present request/copy 뒤 멈췄다. private native futex libxshmfence 하나만 browser LD_LIBRARY_PATH에 적용하자 같은 세션/no-flip 조건에서 물리RGB3/3(각160000pixel)이 통과하고 request/copy 카운터가128/256을 넘었다. 이 개입 결과는 swapchain image3개 소진 뒤 fence wait 정지라는 source 가설을 직접 지지한다. direct flip 및 장시간동시부하는 별도 후속 gate이다.

공식 Termux libxshmfence1.3.3-r1 recipe는 `--disable-futex`를 명시한다. upstream1.3.3에서 pthread backend의 공유 구조는 pthread_mutex_t, pthread_cond_t, value, waiting이다. futex backend는 단일 int32_t v이고 Linux FUTEX_WAIT/FUTEX_WAKE(공유형, PRIVATE가 아님)를 쓴다. configure 기본auto는 linux/futex.h 존재 시 futex를 선택한다. 따라서 동일 libxshmfence API/버전명이라도 두 backend의 shared memory layout은 호환되지 않는다. native pthread implementation과 guest futex implementation은 서로 다른 offset/의미를 읽고쓴다. 특히 guest futex word가 native mutex 영역을 건드릴 수 있으므로 단순 timeout설정으로해결할수없다. [Termux recipe](https://github.com/termux/termux-packages/blob/master/packages/libxshmfence/build.sh), [X.Org1.3.3 원본](https://www.x.org/releases/individual/lib/libxshmfence-1.3.3.tar.xz).

직접 읽은 local원본은 `build/xshmfence-futex-20261012/libxshmfence-1.3.3/src/{xshmfence_futex.h,xshmfence_futex.c,xshmfence_pthread.h,xshmfence_pthread.c}`이다. Mesa X11 acquire 경로는 image의 shm_fence를 xshmfence_await하며, client/server가해당layout에동의해야한다. guest설치binary의futex구현여부는 loadedmodule경로와 disassembly/imports로추가고정할수있다. 이번 physicalintervention만으로검증하지않은guestpackageversion까지추측하지않는다.

배포범위는 browser와 그GPU자식에만 private futex library를 우선검색하게하는것이다. native Weston↔native Termux:X11은기존pthread-pthread짝이므로시스템library교체나전체sessionLD_LIBRARY_PATH변경을하면다른경로를깨뜨릴수있다. 기존쉐어링buffer는이전layout을갖기때문에browser재시작으로새swapchain을만들고,로드된경로/hash를확인한다. glFinish나강제idle/release는필요하지않다.

작은회귀시험은 native allocator→guest waiter/trigger 및 guest allocator→native waiter/trigger의두방향을모두검증한다. 동일sharedfd를SCM_RIGHTS또는동일소유file로전달하고, signal-before-wait와wait-before-signal을각각확인한다. reset/query/await/trigger를100회이상반복하고각round는boundeddeadline을둔다. waiter가실제대기진입했는지는readyhandshake로확인한다. timeout에서는시험이소유한worker만종료한다. 마지막으로browser실제Present가3frame이후계속진행하고physicalRGB/resize/reuse정합성과동시video+Code를통과해야한다.

## 준비한 guest Web Code launcher

`termux/omarchy_code_web.py`, `loopy-code-web`, `loopy-code-web.desktop`를추가했다. 기존Electronlauncher는수정하지않았다. helper는privatepersistentdata/CLI/tmp와tokenfile,sessionlease의supervisoridentity/ancestry,PID/starttime/command검증,최대3초flock대기,authenticatedHTTPreadiness를사용한다. 다른포트listener를종료하거나채택하지않으며processgroup을새로만들지않는다. CLI가tokenURL을로그에찍으므로stdout/stderr를DEVNULL로두고browserbridgeJSON도출력하지않는다. 기기배포/installerpins는parent가담당하며아직이helper의실제guest실행검증은별도이다.

`omarchy_code_profile.py`와`loopy-code-web-export-profile`는기존User의settings/keybindings/snippets를읽어hash이름의private.code-profile로export한다. 원문JSONC를보존하고같은파일이변경되어있으면덮어쓰지않는다. 기존확장/secret/globalstate는복사하지않으며export를browserimport완료로기록하지않는다. 별도desktop-settings snapshot은Machine설정검토merge용이다. tests/test_omarchy_code_web.py의5개검증은정상token+wrongtoken거부readiness,살아있는unownedbackend거부,no-overwriteprofile/JSONC보존,symlink/publictoken거부,PID재사용불일치를다룬다. 전부통과했다.
