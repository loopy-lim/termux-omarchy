# Y900 Weston → Termux:X11 CPU Present copy 제거 구현안

조사일: 2026-10-12. 최초 소스 조사 뒤 native AHB WSI를 구현하고 기기에 적용했다. 현재 결과와 남은 검증은 아래 구현 기록을 참조한다. 별도 실행 담당자가 확인한 `0/290 Present copies offloaded to GPU`는 현재 마지막 표시 경계에 CPU copy가 남는다는 출발 증거다.

## 결론과 실행 순서

현재 native Android EGL에는 `EGL_EXT_image_dma_buf_import`가 없다는 실probe 결과를 전달받았다. 따라서 raw DMA-BUF를 `eglCreateImageKHR(EGL_LINUX_DMA_BUF_EXT)`로 받도록 X11만 고치는 경로는 이 기기에서 바로 쓸 수 없다. `GL_EXT_memory_object_fd` probe도 SIGSEGV여서 채택할 수 없다.

**가장 예측 가능한 다음 구현은 native Turnip의 X11 WSI swapchain을 AHardwareBuffer로 할당하고, Termux:X11이 이미 지원하는 modifier1255로 전달하는 것이다.** Weston·guest Hyprland·Omarchy는 유지하고 Weston 프로세스가 읽는 private native Turnip ICD만 바꾼다. 변경 주점은 `src/vulkan/wsi/wsi_common_x11.c`다. guest VAAPI Mesa와 native X11 WSI Mesa는 서로 다른 빌드·설치 경로로 취급한다.

빠른 비교군으로 Weston만 system Vulkan+xMeM WSI layer를 쓰는 후보는 가능하지만, 그 경우 guest Hyprland의 raw DMA-BUF를 Weston이 import할 수 있는지가 선행 gate다. 출력 AHB가 성공해도 입력을 SHM readback으로 퇴행시키면 목표 달성으로 볼 수 없다.

## 기존 코드가 이미 제공하는 것

Termux:X11 commit `fa3a8b430e2896a19f44c99a9cb056254615ae06`:

- `loriePixmapFromFds()`는 modifier1255/1256에서 전달된 socket에1byte 요청을 보내고 `AHardwareBuffer_recvHandleFromUnixSocket()`으로 수신한다. RGBA/RGBX/BGRA AHB를 허용한다.1256은 수직 반전 경로다.
- raw LINEAR/INVALID/1274 fd는 `LORIEBUFFER_FD`로 받는다. imported FD의 flip은 기본 거부된다.
- AHB는 `LorieBuffer_attachToGL()`에서 Android EGLImage로 import된다. AHB source/destination은 기존 GPU Present copy queue를 사용할 수 있다. 크기·창 상태가 맞으면 flip 후보도 된다.

즉 CPU copy를 제거하려고 새로운 Android 창 시스템이나 compositor를 만드는 작업은 필요 없다. **생산자가 진짜 AHB를 보내는 것**이 기존 수신 경로에 연결되는 좁은 seam이다. raw DMA-BUF fd에 숫자1255만 붙이면 socket검사에서 실패하며 올바른 해결이 아니다. [Termux:X11 InitOutput.c](https://github.com/termux/termux-x11/blob/fa3a8b430e2896a19f44c99a9cb056254615ae06/lorie/src/main/cpp/lorie/InitOutput.c), [buffer.c](https://github.com/termux/termux-x11/blob/fa3a8b430e2896a19f44c99a9cb056254615ae06/lorie/src/main/cpp/lorie/buffer.c)

## 그대로 재사용할 수 있는 것과 없는 것

| 선행 소스 | 실제 구현 | 활용 범위 |
|---|---|---|
| 공식 Termux Mesa24.0.4 DRI3 patch, commit15348144 | rawFD modifier1274; 일부 fence 대기 제거 | AHB 구현이 아님.26.0.6에 그대로 재적용하지 않는다 |
| xMeM/vulkan-wsi-layer `d5624d42` `wsi/x11/swapchain.cpp` | Vulkan AHB export→socketpair→DRI3 modifier1255; server1byte 요청 후 handle전달 | X11 transport와 resource lifecycle 참고. driver가 Android AHB Vulkan extension을 제공해야 함 |
| leegao/bionic-vulkan-wrapper `c8baafbd` `wsi_common_x11.c` | `image->base.ahardware_buffer`가 있으면 AHB socket전송과1255 사용 | 기존 Mesa WSI branch에 AHB전송을 넣는 위치 참고. driver wrapper 전체교체는 불필요 |
| Banners-Turnip `3d82e747` `patches/wayland/banner_ahb_wsi.py` | Linux-style bionic build에서 libnativewindow를 dlopen, AHB할당 후 그 DMA-BUF를 explicit layout으로 Turnip에 import | native Turnip에서 Android Vulkan extension 없이 AHB-backed image를 만드는 가장 가까운 실제 빌드 선행 구현. Wayland protocol부분은 가져오지 않는다 |

[공식 과거 rawFD patch](https://github.com/termux/termux-packages/blob/153481441aa6b15178baf434b2088b55c7679eb3/packages/mesa-vulkan-icd-freedreno-dri3/wsi-termux-x11.patch), [xMeM X11 swapchain](https://github.com/xMeM/vulkan-wsi-layer/blob/d5624d42d8b2debbd910ad25662a05c751eb38b7/wsi/x11/swapchain.cpp), [wrapper X11 WSI](https://github.com/leegao/bionic-vulkan-wrapper/blob/c8baafbd4f4835ca103acb55ec3ac13642b6b7e3/src/vulkan/wsi/wsi_common_x11.c), [Banners AHB implementation](https://github.com/The412Banner/Banners-Turnip/blob/3d82e747a6ac00d88de921aa2969cdaa08ac78d4/patches/wayland/banner_ahb_wsi.py)

위 자료는 각 구현자가 제공한 일차 소스이며 Y900 동작 보장은 아니다. 특히 xMeM은 image format을 RGBA로 고정하는 부분이 있다. Weston/Zink가 요청한 format을 무시하고 이식하면 색이 달라질 수 있으므로 전체 코드를 검토 없이 채택하지 않는다.

## native Turnip X11 WSI AHB 경로: 최소 변경 설계

### 1. 빌드 환경 유지

공식 Termux26.0.6 recipe commit `cc8bf9d492d59ca9ede9a77b3801b0928c0ec484`를 기준으로 한다. Mesa tarball SHA256은 `1d3c3b8a8363b8cc354175bb4a684ad8b035211cc1d6fa17aeb9b9623c513f89`다. 기존 recipe의 Android-detection 보정, Zink EGL보정, native bionic dependencies를 유지한다. 바꿀 산출물은 native `libvulkan_freedreno.so`와 private ICD JSON이다. [공식26.0.6 recipe](https://github.com/termux/termux-packages/blob/cc8bf9d492d59ca9ede9a77b3801b0928c0ec484/packages/mesa/build.sh)

`-Dplatforms=x11,wayland,android`로 간단히 추가하는 방법은 안 된다. Mesa `meson.build`는 Android와 다른platform의 동시 선택을 거부한다. Linux-style Termux build에서 일반 `VK_ANDROID_external_memory_android_hardware_buffer`를 켜는 것은 별도 driver/runtime port가 된다. 대신 stable NDK AHB API를 libnativewindow에서 동적으로 로드하고 Vulkan에는 DMA-BUF import를 사용한다. Banners의 native bionic 빌드가 이 방식이다. [Banners 빌드 스크립트](https://github.com/The412Banner/Banners-Turnip/blob/3d82e747a6ac00d88de921aa2969cdaa08ac78d4/build_turnip_wayland.sh)

공식 package build환경을 사용하면 dependency sysroot 준비를 재구현할 필요가 없다. 기존 준비된 NDK/sysroot로 선택적 빌드를 한다면 XCB·X11·libdrm·xshmfence의 **Android arm64** headers/libs 및 host Python/Mako·Meson/Ninja가 필요하다. Linux guest glibc 라이브러리를 native 링크에 섞으면 안 된다. 최종 native target은 `ninja -C <native-build> src/freedreno/vulkan/libvulkan_freedreno.so`다. 이는 실행했다고 주장하는 명령이 아니라 목표 target이다.

### 2. opt-in AHB image 할당

`struct x11_image`에 AHB 소유권을 추가한다. 기능은 `LOOPY_X11_AHB=1`일 때만 켠다. swapchain 생성 시 먼저 대표 AHB를 할당하여 모든 image에 사용할 format/stride/layout를 정한다.

- AHBallocate/describe/getNativeHandle/send/release를 로드한다. 공개 NDK함수와 실제 native bionic process를 사용한다.
- 첫 후보는8bit RGB의 **검증한 linear layout**만 허용한다. UBWC와10bit는 범위 밖으로 둔다. CPU usage가 linear를 유도한다는 선행 구현의 QTI 가정만으로 모든기기에 일반화하지 않는다. 알려진gralloc layout 또는 실제 stride·pixel검증이 필요하다.
- format은 요청된 VkFormat과 일치시킨다. RGBA요청에RGBA AHB, BGRA요청은 실제 gralloc BGRA지원 또는 별도허용한변환만 쓴다. hardcode로RGBA로 바꾸지 않는다.
- `VkImageDrmFormatModifierExplicitCreateInfoEXT`에LINEAR, plane1, offset/rowPitch를 넣어image를생성한다. `VkExternalMemoryImageCreateInfo`에는DMA_BUF_BIT_EXT를 지정한다.
- `vkGetMemoryFdPropertiesKHR()`의memoryTypeBits와image requirements의교집합을선택한다. fd는dup하여 `VkImportMemoryFdInfoKHR`로넘긴다. allocationSize는 실제object크기와requirements를확인한다. 작은object를단순warning만내고import하지않는다.
- vkAllocateMemory 성공시fd소유권이Vulkan으로이전되므로실패에서만그dup을닫는다. AHB와WSI용dmabuf dup은image파괴까지유지한다. 메모리 destroy, fdclose, AHBrelease 순서를명확히한다.

이 경로는 `VK_ANDROID_external_memory_android_hardware_buffer`가 없는 Turnip에서도DMA-BUF+modifierimport capability가 있으면 구현할 수 있다. native AHBlayout를알아내는부분은별도probe가필요하다. [AHB 공개API](https://developer.android.com/ndk/reference/group/a-hardware-buffer), [Vulkan external-memory fd ownership](https://docs.vulkan.org/refpages/latest/refpages/source/VkImportMemoryFdInfoKHR.html)

### 3. x11_image_init()의 transport만 분기

AHB image에한해 socketpair를만들고server쪽socket fd를 `xcb_dri3_pixmap_from_buffers_checked()`에modifier1255와함께보낸다. `xcb_flush()` 후server1byte요청을읽고handle을보낸다. 기존 ordinary DMA-BUF 필드를socket fd로덮어쓰지않는다. Vulkanmemory동기화에서사용할진짜DMA-BUF와transport socket은별도수명이다.

server가customprotocol을지원하지않으면read가영원히멈추지않도록bounded poll/errorhandling을둔다. NDKsend의성공/실패, XCBerror, socketEOF를구분하고전체image정리후원래경로로실패를전달한다. custom1255는표준DRMmodifier가아니므로explicit opt-in과대상Termux:X11만허용한다.1256은실제수직반전필요가증명될때만쓴다.

### 4. 동기화는 기존 계약을 유지

AHB 전달은buffer생성시한번이며렌더완료신호가아니다. 기존WSI render submit fence/PresentIdleNotify/reacquire흐름을유지한다. consumer GPU읽기완료전image재사용을금지한다. 초기진단에서producer fence wait를보수적으로둘수있지만동기화제거로성능을만들지않는다. X11의기존AHB GPUcopy completion ack와pixmap수명도유지한다. CPU readback으로색을확인하는검증은비교trial외부에서수행한다.

## Weston-only system Vulkan + WSI layer 후보의 gate

이 후보는X11 AHB출력을이미구현한layer를재사용하므로개발량이더작을수있다. 그러나xMeM layer는`VK_KHR_swapchain`등WSI를제공할뿐, vendor Vulkan이없는DMA-BUF imageimport를만들어주지않는다. 다음이모두통과할때만현구성의대체후보다.

1. vendorICD에AHB external-memory지원. layer가AHBexport를호출해socket1255로출력하는것까지확인.
2. WestonZink에필요한Vulkan기능과Zink실행확인.
3. **guestHyprland에서오는실제DMA-BUF를WestonEGLImage로import하고색/stride/반복frame확인.** 보통필요한Vulkan경계는external-memory-fd, external-memory-dma-buf, image-drm-format-modifier다. extension이름만으로format별import지원까지확정하지않는다.
4. compositorSHMfallback카운터0유지. 입력경로readback이생기면출력CPUcopy제거만으로채택하지않는다.

OPAQUE_FD 지원만으로다른driver의arbitrary DMA-BUF를대신받을수있다고가정하면안된다. 검증대상은실제producer출력이다. nativeAndroidEGL에DMA-BUFimport가없다는것은이미부정신호지만Vulkancapability와는별도확인사항이다. [Zink resource import 소스](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-26.0.6/src/gallium/drivers/zink/zink_resource.c), [xMeM X11extension 요구](https://github.com/xMeM/vulkan-wsi-layer/blob/d5624d42d8b2debbd910ad25662a05c751eb38b7/wsi/x11/surface_properties.cpp)

공식 `termux/termux-packages` 현재tree(aed8f240)와해당path history에서는 `vulkan-wrapper-android`/`vulkan-wsi-layer` recipe를찾지못했다. 현재공식loader는Android/generic분리이며서로충돌관계다. 기기에해당이름package가있다면repository origin·version·source를확인하고,그package가공식Termux배포라고단정하지않는다. global loader교체는이실험에불필요하다. Weston만private loader/ICD/layer환경으로실행한다. [공식 Androidloader recipe](https://github.com/termux/termux-packages/blob/aed8f2405a392e49b487eb7ac0ed2eded4f45015/packages/vulkan-loader-android/build.sh), [공식 genericloader recipe](https://github.com/termux/termux-packages/blob/aed8f2405a392e49b487eb7ac0ed2eded4f45015/packages/vulkan-loader-generic/build.sh)

## 채택을 결정할 최소 증거

AHBimport log와GPUcopy/flip증가, CPUcopy/textureupload감소를같은fixture로확인한다. 여러stride/해상도, full-frame번호·색패턴,창resize,최소화·복귀,회전,세션종료를검증한다. 동영상+편집trial에서낮아진CPU와drop율·framegap를함께본다. APK의JNI lifetime·기존입력수정은유지한다. 새driver는private경로에두며기존Mesa파일을덮어쓰지않는다.


## 14:32 구현 및 실제 데스크톱 적용

`experiments/termux-x11-ahb-wsi`에 helper, 적용 스크립트, 정확한 native 소스 diff를 보존했다. 실제 드라이버 SHA256은 `7f05d872e36f32fc130477fb2d6c01da88715dd97b22155bbbca4945092c14d1`이다. 전역 Vulkan/Mesa 패키지를 교체하지 않고 native Weston만 이 파일을 읽는다. guest의 DMA-BUF 설정과 사용자 Hyprland/Code 설정은 유지했다.

- 동적 색상/프레임 번호: 640×480, 1919×800(stride1920), 1920×1280에서 각 3회 readback의 모든 표본 일치. 프레임 번호는 약60/s로 증가했다.
- 실제 Omarchy 세션 `896f1a10-5e4b-4b9c-a0ae-726fafcd9e0e`: X11 로그가 `297/297 present copies offloaded to GPU`를 보고한다. 기존 `0/N` CPU copy 경계를 제거한 직접 증거다.
- 최초 실제 guest 연결에서 Zink가 NULL ImportSemaphoreFd를 호출해 충돌했다. VA 실험 소스가 꺼 둔 `KHR_external_semaphore_fd`를 native 빌드에서 복원했다. KGSL binary SYNC_FD 구현은 존재한다. guest VA용 OPAQUE_FD timeline 우회 정책과 혼합하면 안 된다.
- Android nativewindow를 로드하려면 Termux의 stub binder 대신 system binder가 필요했다. Weston에만 두 system library를 preload한다. 시스템 전체 LD_LIBRARY_PATH를 앞세우지 않는다.
- startup에서 Popen 직후 일시적인 빈 command line을 상태 파일에 저장하던 경쟁을 수정했다. 실제 exec argv와 세션 PGID를 확인한 뒤 상태를 발행한다.

화면 복사를 개선했다고 영상 성능까지 성공으로 판정하지 않았다. 출력 개선 후 기본 XWayland Chromium의 YouTube1080p60+Code 5회 저장은 3653frame/66drop(1.81%)이었다. 이 첫 재시작 표본에는 Notion 복원이 누락되어 Notion 동시 사용 수락으로 세지 않는다. 이후 Notion을 열고 PRoot 고성능 코어 지정 실험은3658/71(1.94%)이어서 affinity를0–7로 복원했다. VAAPI native Wayland trial은1808/64(3.54%)로 불합격이라 기본 디코더를 바꾸지 않았다.

Chromium151 native Wayland+ANGLE Vulkan은0.66%였으나 GPU compositing이 software로 떨어져 채택하지 않았다. Wayland+ANGLE GLES+KGSL DRM shim은 GPU compositing/rasterization enabled, Adreno830 renderer를 유지하며30초 로컬1080p60에서1803/17(0.94%)이었다. 실제 YouTube+편집과 입력 호환성 검증은 별도 필요하다.

## 4K HiDPI 후 남은 Chromium → Xwayland 경계와 다음 단일 시험

2026-10-12 추가 조사. native AHB 출력의 GPU copy 성공과 브라우저 출력 경로는 별개다. 3840×2560/scale2.5에서 부모 작업이 측정한 YouTube1080p60+15회 편집은 4.293% drop, VFR=true도3.864%로 불합격이며 false로 복원했다. 이는 측정 보고이며 아래 소스 분석만으로 원인별 시간을 확정하지 않는다.

### 소스에서 확인한 경계

- Chromium의 Vulkan compositor 초기화는 `disable_vulkan_surface`가 참이면 `SkiaOutputDeviceVulkan::Create`를 건너뛴다. X11 fallback이 허용되면 `SkiaOutputDeviceX11`을 선택한다. [Skia output surface](https://github.com/chromium/chromium/blob/main/components/viz/service/display_embedder/skia_output_surface_impl_on_gpu.cc).
- 그 X11 output device의 `Present`는 Skia surface에서 `readPixels` 후 `ui::DrawPixmap`으로 X11에 CPU 픽셀을 전달한다. Graphite도 CPU 동기화와 CopyPlane을 쓴다. 갱신 사각형이 없으면 전체 surface이다. 따라서 4K에서 이 경계의 비용이 커질 수 있다. 다만 ANGLE의 Vulkan renderer 문자열만으로 Skia Vulkan compositor까지 확정하면 안 된다. [SkiaOutputDeviceX11](https://github.com/chromium/chromium/blob/main/components/viz/service/display_embedder/skia_output_device_x11.cc).
- `XWAYLAND_NO_GLAMOR=1`은 glamor와 DRI3를 함께 끈다. Chromium은 DRI3/ATIFGLRXDRI/NV-CONTROL이 없는 X11에서 Vulkan surface를 거절한다. flag 하나를 제거하는 것으로 해결되지 않는다. [Xwayland glamor](https://github.com/mirror/xserver/blob/master/hw/xwayland/xwayland-glamor.c), [Chromium IsVulkanSurfaceSupported](https://github.com/chromium/chromium/blob/main/ui/base/x/x11_util.cc), [VulkanImplementationX11](https://github.com/chromium/chromium/blob/main/ui/ozone/platform/x11/vulkan_implementation_x11.cc).
- 조사한 Xwayland GBM backend는 DRM device fd, render-node/authentication, `gbm_create_device`, EGL GBM을 요구한다. KGSL와 기존 guest DMA-BUF import가 있다는 사실만으로 이 초기화가 성립하지 않는다. 환경변수 해제만으로 가속 Xwayland가 된다고 볼 근거가 없다. 이 미러의 GBM 소스에는 구형 경로도 있으므로 설치된 정확한 Xwayland 버전의 capability 확인은 별도 필요하다. [Xwayland GBM backend](https://github.com/mirror/xserver/blob/master/hw/xwayland/xwayland-glamor-gbm.c).

### 재빌드 없이 차이가 있는 후보: Wayland + GL compositor + ANGLE Vulkan

직접 실행 바이너리 `/usr/lib/chromium/chromium`, 새 실험 profile에 아래 조합만 추가한다. 기존 필수 sandbox/권한 설정은 유지하되 wrapper가 기존 Chromium flags를 덧붙이지 않게 한다.

```text
--ozone-platform=wayland
--use-gl=angle
--use-angle=vulkan
--disable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan
--disable-accelerated-video-decode
```

의도는 **Skia GL compositor를 ANGLE Vulkan으로 실행**하는 것이다. Chromium 자체의 Vulkan compositor는 끈다. Chromium Wayland factory는 ANGLE Vulkan을 허용하며, 하드웨어 EGL은 native Wayland GLSurface 경로가 있다. 반면 Chromium 자체 `VulkanImplementationWayland::CreateViewSurface`는 현재도 NOTIMPLEMENTED이다. ANGLE에는 별도 `vkCreateWaylandSurfaceKHR` 구현이 있다. [Wayland surface factory](https://github.com/chromium/chromium/blob/main/ui/ozone/platform/wayland/gpu/wayland_surface_factory.cc), [Chromium Wayland Vulkan](https://github.com/chromium/chromium/blob/main/ui/ozone/platform/wayland/gpu/vulkan_implementation_wayland.cc), [ANGLE Wayland Vulkan surface](https://github.com/google/angle/blob/main/src/libANGLE/renderer/vulkan/linux/wayland/WindowSurfaceVkWayland.cpp).

이는 앞선 두 시험과 다르다. `gpu-research-gpu2-measure.json`은 Vulkan compositor enabled 및 inherited `--disable-vulkan-surface`와 함께 GPU compositing이 `disabled_software`였다. `gpu-research-gpu3-measure.json`은 ANGLE GLES/Mesa26.3이고, 이후 실제 YouTube+편집24.90%로 기각되었다. 기존 24.90% 조합을 그대로 다시 추천하지 않는다.

시험 gate: 실제 commandLine 중복/override 확인 → CDP `glImplementationParts`의 angle=vulkan 및 Turnip830 → `gpu_compositing=enabled`, Chromium `vulkan=disabled_off`, software renderer 아님 → Hyprland client `xwayland=false` → 정상 픽셀과 창 이동/크기 변경/타이핑 확인. gate 실패면 장시간 성능 측정을 하지 않는다. 성공 시 동일 화면 크기·영상 viewport·1080p60·15회 실제 저장·Notion 상태로 비교한다. `WAYLAND_DEBUG`의 linux-dmabuf buffer 사용 또는 출력 경로 trace가 있어야 CPU SHM 우회까지 입증된다. GPU 문자열만으로 zero-copy를 주장하지 않는다.

제약: 빌드가 native Wayland EGL 접속 대신 GBM surfaceless 경로만 제공하면 KGSL DRM/GBM 조건에서 다시 실패할 수 있다. ANGLE의 Wayland 지원이 해당 Chromium 바이너리에 빠졌을 수도 있다. 이 후보는 이 capability를 먼저 확인하는 제한된 시험이며 성능 개선 완료가 아니다. Xwayland의 KGSL glamor/DRI3 backend 신설은 이 시험보다 범위가 큰 별도 구현이다.

### 후속 후보 실제 판정

4K에서 bare ANGLE Vulkan/GL 후보는 software compositor였다. DRM shim만 추가하면 GBM CREATE_DUMB가실패했다. 별도 KGSL GBM 라이브러리와 EGL 환경까지 사용하면 GPU compositing enabled/GaneshGL/ANGLE Vulkan/native Wayland gate는통과했지만 실제영상9.945% drop과색상오류가생겼다. `--disable-gpu-memory-buffer-video-frames`로심한녹색/자홍색혼합은사라졌으나5.751% drop과기준색차이로채택하지않았다. 자세한 receipts와최종복원은[4K 검증](../validation/2026-10-12-y900-hidpi.md)에기록했다. native AHB 최종출력성공을브라우저영상성공으로확장하지않는다.
