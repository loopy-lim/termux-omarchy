# Android Linux guest GPU 대안과 전환 조건

조사일: 2026-10-06. Mesa·virglrenderer·Termux·Android/AOSP·Linux kernel의 공식 문서와 소스를 조회했다. Y900 실기기를 연결하지 않았으므로 모델명만으로 GPU, 커널 UAPI, 앱 UID의 장치 접근 가능성을 결정하지 않는다. 이 문서는 구현 상태, 빌드 가능성, 실제 렌더링 수락을 구분한다.

## 현재 경계

현재 [guest 런처](../../guest/desktop/usr/local/bin/loopy-desktop)는 Alpine ARM64 **musl** PRoot에서 Sway를 `WLR_RENDERER=pixman`으로 실행한다. Android의 [native host](../../native/wayland-host/src/gles.c)는 **bionic** EGL/GLES로 guest `wl_shm` surface를 합성하고 오류 시 CPU로 돌아간다. 이것은 Android 출력 합성 가속이며 Linux 프로그램의 OpenGL/Vulkan 실행을 GPU로 바꾸지는 않는다. `renderer=gles`도 물리 GPU의 증거는 아니다. VM의 ANGLE/SwiftShader는 소프트웨어일 수 있다.

PRoot의 `/dev` bind는 기존 파일을 보이게 할 뿐 커널 UID, DAC, SELinux 권한을 바꾸지 않는다. [RuntimeSession](../../android/src/dev/loopy/desktop/RuntimeSession.java)은 `env -i`를 사용하므로 아래 backend 환경변수를 선택한 probe/프로그램에 명시적으로 전달해야 한다. Android private bionic vendor 라이브러리를 musl guest에서 직접 `dlopen`하는 것은 ABI·loader namespace 문제가 있는 별도 경로다. [Android Vulkan loader 구조](https://source.android.com/docs/core/graphics/implement-vulkan), [PRoot 설명](https://proot-me.github.io/), [Android SELinux](https://source.android.com/docs/security/features/selinux).

현재 rootfs에는 Mesa `25.1.9-r0`의 EGL/GLES/libgallium과 **같은 Alpine source commit의 `mesa-dri-gallium` frontend**가 포함된다. [guest EGL probe](../../guest/desktop/usr/local/lib/loopy/graphics_egl.py)는 실제 GLES2 context·RGBA `[51,102,153,255]` readback·renderer를 확인한다. [probe controller](../../guest/desktop/usr/local/lib/loopy/graphics_probe.py)는 이를 별도 child에서 실행하며 timeout·출력 제한·종료 상태·JSON schema·UID·provider identity를 검사한다. shader/texture/depth의 일반 3D 기능이나 모든 프로그램의 GPU 호환성 수락까지 의미하지 않는다. [고정 Alpine Mesa 빌드 정의](https://gitlab.alpinelinux.org/alpine/aports/-/blob/dd9d35b82a5100ea5a3440943a74ab3bf71db4e5/main/mesa/APKBUILD), [현재 package lock](../../third_party/desktop.lock.json).

기본 선택은 검증된 **llvmpipe → softpipe → Cairo**다. VirGL은 session별 Android server와 guest offscreen probe까지 연결되어 있지만 일반 desktop의 hardware 기본값으로 고르지 않는다. 사용자는 `GPU alternatives / check` 메뉴에서 조건을 확인하고, 현재 session의 실제 socket과 pixel 증거가 유효할 때만 **VirGL 창 검사**를 명시적으로 실행할 수 있다. 이전 capability-fallback APK의 VM 시험은 **32/32 통과**했다. guest llvmpipe의 실제 GL pixel이 desktop에 도달했고, VirGL은 소켓 준비 후 EGL 초기화 gate에서 렌더링에 실패하여 CPU로 돌아갔으며 서버 종료가 확인됐다. 이 결과와 물리 GPU의 경계는 [capability/fallback 검증 기록](../capability-fallback-validation.md)과 [정확한 이전 capability-fallback VM 영수증](../validation/2026-10-06-capability-fallback-final-vm/receipt.json)에서 구분한다.

## 가능한 경로 비교

| 경로 | 실제로 필요한 것 | 무루트 APK에서의 범위 | 실패 시 전환 / 현재 상태 |
| --- | --- | --- | --- |
| Android EGL/GLES host 합성 | NDK EGL/GLES, Android Surface, texture 업로드 | 공용 Android API로 가능 | **구현됨**. 초기화·출력 오류 시 CPU 합성. guest 3D는 별개 |
| Android VirGL/vtest + guest Mesa `virpipe` | bionic EGL/GLES server, musl Mesa virgl frontend, UNIX socket, FD 공유, host GLES ≥3.0, 표시 WSI | **APK・server lifecycle・guest proxy probe 통합됨**. DRM·root 없이 Android API 사용 | VM 소켓 준비·CPU fallback·종료 확인 통과; VirGL pixel은 EGL gate 실패. 유효한 socket/pixel 증거가 있을 때만 수동 창 검사 허용; 실기기 미검증 |
| Venus/vtest + guest Vulkan | bionic virglrenderer Venus, Vulkan driver·메모리 import, musl Venus ICD, socket | 커널 virtio 없이 vtest 후보가 있으나 driver·memory 조건이 강함 | VirGL 또는 software GL. 별도 구현·검증 필요 |
| Android Vulkan + Zink | Vulkan을 guest에 제공하는 ABI/프로토콜 경로, Zink Mesa, 요구 feature·WSI | bionic renderer 내부 또는 Venus 위 Zink 후보. Android loader만 guest에 노출하면 되지 않음 | plain GLES VirGL 또는 software. 별도 구현 필요 |
| ANGLE host backend | bionic ANGLE EGL/GLES libraries, Vulkan/GL backend, VirGL 같은 guest bridge | Android native bridge의 선택 backend로 가능 | stock Android EGL/GLES. ANGLE만 넣어 guest desktop GL이 되지는 않음 |
| libhybris | Android driver ABI adaptation, 맞는 headers/TLS/gralloc/HWC·서비스 integration | musl 자체를 이유로 배제할 수는 없지만 stock APK의 일반적 drop-in 해법은 아님 | 프로토콜 bridge 우선. OEM별 큰 추가 작업 |
| Adreno Turnip/Freedreno KGSL | **실제 Adreno**, 지원 chip·KGSL build, `/dev/kgsl-3d0`와 메모리 ioctl 허용 | OEM 앱 UID가 필요한 접근을 허용하면 무루트 후보; Mali에는 적용 불가 | Android host VirGL/Venus. 기기 판정·직접 probe 전 |
| Mali Panfrost/PanVK | 실제 지원 Mali, kernel `panfrost`/`panthor` DRM UAPI·render node, Mesa driver | stock proprietary `/dev/mali0`만으로 upstream Mesa가 작동하지 않음 | Android vendor GLES/Vulkan bridge. kernel 변경은 별도 기기 작업 |
| root + chroot / custom kernel | root 권한, 맞는 kernel driver·DT·firmware·Mesa·display integration | 현재 무루트 APK와 다른 배포·권한 경로 | root만으로 없는 GPU UAPI/ABI가 생기지 않음 |
| Termux:X11 | X11 Android APK + companion package, 공유 socket, X11 desktop integration | 외부 Termux 연동 또는 자체 backend 이식 후보 | 현재 Sway/Wayland 유지. X11 출력 자체는 guest 3D 가속 증거가 아님 |
| remote GPU desktop/render service | 실제 GPU 서버, 인증·network·encoder·client | Android client는 무루트로 가능 | 로컬 software desktop. 렌더링 장소는 원격 서버 |
| llvmpipe / softpipe / Cairo | 같은 빌드의 Mesa loader·software driver, 또는 기존 GTK Cairo | **isolated EGL probe와 자동 fallback 구현됨** | 검증된 CPU GL을 기본 선택, 모두 실패하면 Cairo. hardware로 표시하지 않음 |

표의 기술 근거는 다음 각 경로의 공식 링크와 probe 계약에 연결한다.

## 1. VirGL/vtest: 통합한 guest proxy 경로

VirGL은 guest Gallium 명령을 host renderer로 전달한다. host는 충분한 OpenGL/GLES 기능이 필요하며 장치 passthrough와 다르다. [Mesa VirGL](https://docs.mesa3d.org/drivers/virgl.html). 현재 공식 Termux의 `virglrenderer-android`는 NDK EGL/GLES와 libepoxy를 사용하므로 Android native server를 만드는 구체적 선례다. [고정 build.sh](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/virglrenderer-android/build.sh).

ABI 경계는 `musl Mesa → vtest protocol/FD → bionic virglrenderer → Android EGL/GLES`다. ELF를 서로 직접 link하지 않는다. [NativeGraphicsServer](../../android/src/dev/loopy/desktop/NativeGraphicsServer.java)는 APK `nativeLibraryDir`의 executable을 session worker에서 실행하고, 같은 APK UID의 private `files/wayland/virgl-TOKEN.sock`을 guest `/run/loopy/virgl-TOKEN.sock`에 연결한다. token·canonical parent·107바이트 UTF-8 path·소유 marker를 확인한다. 소유한 child와 IPC만 수거하며 종료 확인 실패는 handle을 남겨 재시도한다. [TerminalController](../../android/src/dev/loopy/desktop/TerminalController.java)는 guest 생존과 cleanup owner를 구분하고 UI thread 밖에서 수거한다.

서버는 **`--no-fork`**로 실행한다. 기본 vtest의 per-client fork 자식을 Java owner 밖에 남기지 않고 한 client씩 진단하려는 선택이다. 여러 창/프로그램의 동시 hardware session은 활성화하지 않는다. 이 확장은 client 격리·동시 GL context·오류/취소·resource lifetime을 별도로 구현·검증해야 한다. [pinned vtest server 소스](https://gitlab.freedesktop.org/virgl/virglrenderer/-/blob/virglrenderer-1.3.0/vtest/vtest_server.c).

guest Mesa의 변수는 `VTEST_SOCKET_NAME`, upstream 서버 환경변수는 `VTEST_RENDERER_SOCKET_NAME`이며 현재 관리 server는 명시적 `--socket-path`를 사용한다. [Mesa vtest socket 소스](https://android.googlesource.com/platform/external/mesa3d/+/refs/heads/main/src/gallium/winsys/virgl/vtest/virgl_vtest_socket.c), [virglrenderer server 소스](https://android.googlesource.com/platform/external/virglrenderer/+/refs/heads/main/vtest/vtest_server.c).

`LIBGL_ALWAYS_SOFTWARE=true`와 `GALLIUM_DRIVER=virpipe`는 guest의 software-loader frontend에서 vtest proxy를 고른다. host `--use-gles`와 충돌하지 않으며 host GPU 여부를 결정하는 변수도 아니다. host는 실제 **GLES context ≥3.0**이 필요하다. 기존 Android host의 GLES2 합성 성공을 VirGL caps 수락으로 재사용하지 않는다. [Mesa virpipe 생성 경로](https://android.googlesource.com/platform/external/mesa3d/+/refs/heads/main/src/gallium/auxiliary/target-helpers/inline_sw_helper.h), [Mesa 환경변수](https://docs.mesa3d.org/envvars.html), [pinned host context 요구](https://gitlab.freedesktop.org/virgl/virglrenderer/-/blob/virglrenderer-1.3.0/src/vrend/vrend_renderer.c).

이전 capability-fallback VM에서 서버는 `Missing EGL_KHR_surfaceless_context or EGL_KHR_create_context`로 종료했고 guest `virpipe` child는 연결 종료로 실패했다. pinned winsys는 `eglInitialize` 후 두 extension 문자열을 요구하며 EGL core version을 고려하지 않는다. **이 gate 실패만으로 해당 기기 GPU의 미지원이 증명되지는 않는다.** EGL 1.5는 두 기능을 core에 포함하지만 context의 실제 surfaceless 수용과 GLES ≥3.0·pixel 검사는 여전히 필요하다. 이전 capability-fallback 영수증에는 EGL version/extension 목록이 없어 어떤 기능이 실제로 없었는지 판정할 수 없다. 다음 후보는 이 진단을 기록하고 core/KHR 조건을 구분해 실제 context·`eglMakeCurrent`·pixel을 검증하는 것이다. 진짜 surfaceless 미지원이면 pbuffer 생성·모든 context 바인딩·수명 관리가 필요하다. 현재 CLI에는 `--use-egl`이 없고 surfaceless flag를 제거해도 extension 검사와 `EGL_NO_SURFACE` 바인딩이 남으므로 flag 변경만으로 pbuffer fallback은 구현되지 않는다. [pinned EGL winsys](https://gitlab.freedesktop.org/virgl/virglrenderer/-/blob/virglrenderer-1.3.0/src/vrend/vrend_winsys_egl.c), [EGL 1.5 기능·context 규칙](https://registry.khronos.org/EGL/specs/eglspec.1.5.pdf).

[session report](../../guest/desktop/usr/local/lib/loopy/graphics_session.py)는 JSON에 UID와 token을 묶고, 현재 token의 socket·`virpipe` provider·`virgl` renderer·실제 pixel 통과를 수동 경로의 조건으로 사용한다. socket inode 존재만으로 성공하지 않고 guest에서 socket type과 EGL readback을 검사한다. proxy 증거가 없거나 오래됐거나 socket이 사라지면 `loopy-gl --virgl`은 실행을 거부하고 기존 CPU desktop을 유지한다. [Android 표시](../../android/src/dev/loopy/desktop/GuestGraphicsStatus.java)는 proxy 픽셀 통과와 GUI/물리 GPU 미확인을 함께 표시한다.

현재 구현의 offscreen 검사는 GLES2 clear/readback이다. 일반 guest 3D 또는 hardware 기본값으로 확대할 때 필요한 수락 계약은 다음과 같다.

1. 일반 **앱 UID**에서 EGL context 생성, host `GL_VENDOR`/`GL_RENDERER`/version/caps 기록. shell UID 성공을 앱 수락으로 사용하지 않는다.
2. guest가 session socket에 연결하고 capset·resource 생성·FD 전송/`mmap`을 실제 완료한다. `/dev/ashmem` 또는 `memfd` 존재만 검사하지 않는다.
3. guest EGL surfaceless context에서 shader와 texture/depth를 사용해 알려진 pixel을 그리고 `glReadPixels`로 정확히 확인한다. `eglInitialize` 성공만으로 GL 수락하지 않는다.
4. host renderer가 llvmpipe/softpipe/SwiftShader/Lavapipe이면 `software`로 기록한다. VM에서는 프로토콜 경로 검증만 인정한다.
5. guest window에 연속 frame·resize·클립·alpha·surface 교체를 표시하고 renderer와 readback/copy 비용을 별도 측정한다.
6. bridge 종료·접속 timeout·지원하지 않는 GL feature는 명시적 reason으로 software 경로를 고른다. Linux session/HOME는 보존한다. 살아 있는 GL context를 다른 driver로 투명하게 옮긴다고 약속하지 않고 해당 프로그램을 명시적으로 다시 시작한다.

**표시 경계:** 현재 host는 `wl_shm`, Sway는 pixman이다. surfaceless VirGL probe가 통과해도 모든 native Wayland 앱의 EGL WSI가 곧바로 호환된다는 뜻은 아니다. GPU readback → shared-memory 표시, X11 software WSI, 또는 별도 dma-buf/import/동기화 경로를 실제 구현·검증해야 한다. [Mesa EGL 플랫폼/driver 경계](https://docs.mesa3d.org/egl.html), [현재 host protocol](../../native/wayland-host/src/state.rs). 브라우저 WebGL·video decode·Sway 자체 GPU 합성도 각각 독립된 수락 항목이다.

### 고정 Termux 소스와 최소 API 28 빌드

조회한 Termux master commit은 `7945fdb5a62d773e98cae56f2e43438d859f9009`다. 이 commit은 virglrenderer `1.3.0`, libepoxy `1.5.10`을 지정하고 libepoxy를 `egl=yes`, `glx=no`, `x11=false`, renderer를 `platforms=egl`로 빌드한다. Termux 전체 패키지는 ANGLE와 Venus도 포함하지만 첫 Loopy proof는 **Venus=false / ANGLE 제외 / GBM·GLX·X11 제외**로 줄인다. [build.sh](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/virglrenderer-android/build.sh).

| 입력 | 고정 SHA-256 / 의미 |
| --- | --- |
| virglrenderer 1.3.0 source archive | `56170f8caa1bb642a2624b649e3bcca095ec2834814e5c308efc8a85a709e4ce` |
| libepoxy 1.5.10 source archive | `a7ced37f4102b745ac86d6a70a9da399cc139ff168ba6b8002b4d8d43c900c15` |
| Termux build.sh | `571c639aaa0d4f16e48c8ad2eb529c753e6e1e5acdc11a592e4c6b1c86c2cc8f` |

필수로 검토할 pinned 패치:

- [0001](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/virglrenderer-android/0001-do-not-use-gbm.patch.beforehostbuild): GBM 경로 제외. stock Android EGL로 context를 만드는 출발점이다.
- [0004](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/virglrenderer-android/0004-Fallback-to-ashmem.patch.beforehostbuild): legacy `/dev/ashmem`을 직접 open/ioctl한다. 최신 Android에서 접근 가능하다고 가정하면 안 된다. Android에서 shared-memory 사전 검사를 우회하는 부분도 있으므로 실제 allocation/FD transfer probe가 필수다.
- [0007](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/virglrenderer-android/0007-Ensure-EGL-GLES-ANGLE-help-and-socket-path.patch.beforehostbuild): 기본 EGL surfaceless/GLES를 강제하고 `--use-egl-surfaceless`, `--use-gles`를 제거한다. 이 variant에 옛 tutorial의 flags를 섞지 않는다. `--socket-path=<app-private path>`는 남는다. Termux 고정 prefix는 Loopy에 이식하지 않는다.
- [0010](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/virglrenderer-android/0010-disable-memfd_create-timespec_get.patch.beforehostbuild): NDK 최소 API에 없는 libc 함수 자동 탐지를 막는다. API 28에는 직접 `memfd_create` link보다 kernel syscall 또는 public shared-memory API의 계약 확인이 필요하다.
- [0011](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/virglrenderer-android/0011-use-Android-Vulkan.patch.beforehostbuild): Venus Android Vulkan/HardwareBuffer adaptation이다. 최소 GLES build에는 포함하지 않는다.

구현한 [빌드 도구](../../tools/build_virgl_android.py)는 [source/patch lock](../../third_party/virgl.lock.json) SHA를 검증하고 NDK `27.1.12297006`의 `aarch64-linux-android28-clang`으로 bionic PIE executable `libvirgl_server.so`를 만든다. libepoxy와 virglrenderer는 static이고 EGL/GLES는 Android system library를 런타임에 연다. 실행 파일은 기존 native-library 실행 방식에 맞춰 package한다. 앱이 쓰기 가능한 데이터 디렉터리의 임의 ELF 직접 실행에 의존하지 않는다. [Android 10 실행 제한](https://developer.android.com/about/versions/10/behavior-changes-10#execute-permission), [기존 native build](../../tools/build_native.py).

최소 build는 Termux 0001/0002/0009/0010만 채택한다. 0001의 Meson host 선언 hunk는 1.3.0에서 위치·문맥이 달라 그대로 적용되지 않아 동일 Android EGL 조건을 guarded replacement로 맞춘다. winsys diff는 원문을 fuzz 없이 적용한다. upstream vtest의 kernel `memfd_create` syscall과 실제 shared-memory 사전 검사를 유지하며 **0004의 ashmem 검사 우회와 0007의 CLI 변경은 적용하지 않는다**. 따라서 이 artifact는 `--use-egl-surfaceless --use-gles --socket-path=...`를 사용한다. full Termux package와 최소 Loopy variant의 호출 규칙을 구분한다.

workspace 안에 host 생성기만 설치한다. GPU runtime 바이너리는 위 고정 source에서 cross-build한다.

```sh
python3 -m venv build/virgl/venv
build/virgl/venv/bin/pip install --no-cache-dir meson==1.9.1 PyYAML==6.0.3
python3 tools/build_virgl_android.py
python3 -m unittest discover -s tests -p test_virgl_build.py -v
```

빌드는 AArch64 PIE/interpreter/NEEDED를 확인하고 원본 license 전문·patch notices·build log·artifact SHA receipt를 남긴다. [APK input verifier](../../tools/virgl_inputs.py)는 executable bytes/SHA, source와 lock hash, Android ELF header·`linker64`·16KiB LOAD alignment를 검사한다. [APK builder](../../tools/build_android.py)는 검증된 선택적 artifact를 포함하고 verifier identity와 build 중 입력 변경을 추적한다. 이는 구현·package provenance이며 receipt의 서명이나 실제 렌더링 성공을 대신하지 않는다. 앱 UID proxy/visible-window 수락은 [capability/fallback 검증 기록](../capability-fallback-validation.md)의 정확한 APK·phase 결과로 확인한다.

## 2. Venus/Vulkan 및 Zink

Venus는 Vulkan 명령을 직렬화하며 vtest가 있으면 virtio kernel 경로 없이 시험할 수 있다. upstream Android host 요구는 Vulkan 1.1과 `VK_EXT_external_memory_dma_buf`, `VK_EXT_image_drm_format_modifier`, `VK_EXT_queue_family_foreign`이다. 조건을 만족해도 모든 driver가 동작하는 것은 아니며 메모리 의미에 대한 추가 가정이 있다. 공식 테스트 목록에 Mali proprietary driver 등이 있다는 사실은 특정 Y900의 지원 증거가 아니다. [Mesa Venus requirements](https://docs.mesa3d.org/drivers/venus.html).

Termux는 upstream 조건을 그대로 쓰는 대신 Android HardwareBuffer memory adaptation을 포함한다. 따라서 정확한 pinned adapter에서 memory allocation/import/export와 synchronization·pixel readback을 확인해야 한다. extension 이름 치환만으로 호환성을 주장하지 않는다. [Termux Android Vulkan patch](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/virglrenderer-android/0011-use-Android-Vulkan.patch.beforehostbuild).

guest의 Linux Vulkan loader에서 `VK_DRIVER_FILES=<설치된 ARM64 Venus ICD JSON>`과 `VN_DEBUG=vtest`를 지정한다. host renderer도 Venus 지원으로 빌드·실행해야 한다. `vulkaninfo` enumeration 뒤 실제 render/readback 검사를 한다. JSON의 library path와 musl ABI가 맞아야 하며 Android system loader에는 Linux ICD JSON 선택을 그대로 적용하지 않는다. [Venus vtest 절차](https://docs.mesa3d.org/drivers/venus.html), [Android Vulkan implementation](https://source.android.com/docs/core/graphics/implement-vulkan).

Zink는 OpenGL을 Vulkan으로 구현하므로 먼저 실제 Vulkan transport/ICD가 필요하다. `GALLIUM_DRIVER=zink`는 그 부품을 만들지 않는다. 필요한 Vulkan feature/extension과 `VP_ZINK_requirements.json`을 probe하고 앱이 요구하는 GL 수준을 확인한다. GL version override는 없는 기능의 구현이 아니다. [Mesa Zink requirements](https://docs.mesa3d.org/drivers/zink.html). 첫 GLES VirGL 경로가 안정된 뒤 Venus → Zink를 선택적 단계로 추가하는 순서가 실용적이라는 판단이다.

## 3. ANGLE·libhybris

ANGLE은 OpenGL **ES**를 Vulkan/GL/GLES 등으로 변환한다. Android host가 stock GLES driver 문제를 만났을 때 bionic ANGLE backend를 선택할 수 있다. guest의 desktop OpenGL API/ABI/WSI transport를 ANGLE 하나로 대신하지는 않는다. [ANGLE README](https://chromium.googlesource.com/angle/angle/+/main/README.md), [Termux angle-android build](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/angle-android/build.sh). ANGLE Vulkan이 SwiftShader를 사용하면 software로 분류한다.

libhybris의 현재 설명은 glibc뿐 아니라 musl 등의 환경에서 Android bionic driver를 사용하는 경로도 명시한다. 따라서 “musl라서 불가능”이라는 결론은 맞지 않는다. 다만 TLS·headers·Android 버전·gralloc/HWC·서비스 integration을 맞춰야 하는 platform adaptation이며 현재 APK에 자동 적용되는 ABI bridge가 아니다. [libhybris 공식 README와 build 절차](https://github.com/libhybris/libhybris). OEM별 driver 사용이 꼭 필요한 조건에서 별도 prototype을 평가하고, 일반 APK 우선순위는 protocol bridge에 둔다.

## 4. 직접 kernel driver 경로

### Adreno: Freedreno/Turnip KGSL

Freedreno/Turnip은 Qualcomm Adreno 계열이다. 지원 chip 목록과 kernel backend를 실제 확인한다. Termux Mesa는 `freedreno-kmds=msm,kgsl`을 지정하고 AOSP Turnip KGSL 소스는 KGSL ioctl과 메모리 allocation을 사용한다. **Mali에 적용하지 않는다.** [Mesa Freedreno](https://docs.mesa3d.org/drivers/freedreno.html), [Termux Mesa build](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/mesa/build.sh), [Turnip KGSL source](https://android.googlesource.com/platform/external/mesa3d/+/refs/heads/main/src/freedreno/vulkan/tu_knl_kgsl.cc).

`/dev/kgsl-3d0`와 필요한 dma-heap/ION 경로를 **앱 UID**에서 open/ioctl할 수 있고 chip·driver build가 맞으면 무루트도 후보가 된다. OEM 정책이 막으면 PRoot나 bind로 해결하지 못한다. 먼저 read-only hardware/driver inventory와 제한된 allocation/render probe로 판정하고, 접근 불가 시 Android public API bridge로 돌아간다. 전역 chmod·SELinux 해제를 자동 fallback으로 쓰지 않는다. [Android SELinux 적용 범위](https://source.android.com/docs/security/features/selinux).

### Mali: Panfrost/PanVK

Mesa의 Mali 지원은 GPU generation·driver별로 다르다. PanVK의 conformance도 모든 Mali의 공통 속성이 아니다. [Panfrost/PanVK 지원 표](https://docs.mesa3d.org/drivers/panfrost.html). 현재 PanVK source는 `panfrost`/`panthor` DRM driver를 확인한다. proprietary Arm kbase `/dev/mali0`가 존재한다는 사실은 upstream PanVK kernel UAPI를 제공한다는 뜻이 아니다. [PanVK device source](https://android.googlesource.com/platform/external/mesa3d/+/refs/heads/main/src/panfrost/vulkan/panvk_physical_device.c), [Panfrost kmod source](https://android.googlesource.com/platform/external/mesa3d/+/refs/heads/main/src/panfrost/lib/kmod/pan_kmod.c), [Panthor kernel docs](https://docs.kernel.org/gpu/panthor.html).

맞는 DRM render node는 DRM master 없이 GPU rendering을 허용하지만 파일 권한과 Android SELinux는 여전히 적용된다. stock kernel에 UAPI가 없으면 root/chroot만으로 추가되지 않는다. custom kernel·DT·firmware·전력 관리·display integration이 필요한 별도 기기 프로젝트가 된다. [Linux DRM render nodes](https://docs.kernel.org/gpu/drm-uapi.html#render-nodes). experimental override로 driver를 강제로 켠 결과를 안정 지원으로 기록하지 않는다.

## 5. Termux:X11·remote GPU

Termux:X11은 Android APK와 companion Termux package가 둘 다 필요하며 PRoot에서는 `--shared-tmp`/일치하는 TMPDIR와 DISPLAY socket을 연결한다. Loopy UID가 별도 Termux UID의 private 파일에 자동 접근할 수는 없다. 외부 앱 연동인지 같은 APK backend 이식인지 먼저 정한다. X11 desktop/session/input/clipboard를 추가 통합해야 하고 `-legacy-drawing`, `-force-bgra`는 출력 호환 옵션이지 guest 3D 구현이 아니다. [Termux:X11 공식 설치·PRoot·troubleshooting](https://github.com/termux/termux-x11).

원격 GPU 서버를 사용할 수 있다면 VirtualGL+VNC류는 서버에서 3D를 렌더링하고 frame을 client에 보낸다. 서버 GPU 접근 권한·인증·network·encoding과 실제 renderer 검증이 필요하다. 이 경로는 로컬 Alpine 프로그램을 자동 가속하는 대신 원격 프로그램/desktop을 제공한다. Android client의 무루트 가능성과 서버 권한을 구분한다. [VirtualGL Project 공식 User’s Guide](https://rawcdn.githack.com/VirtualGL/virtualgl/main/doc/index.html#hd003), [공식 문서 입구](https://virtualgl.org/Documentation/Documentation).

## 조건별 선택과 software 복구

1. 현재 화면은 host EGL/GLES로 합성한다. context/Surface 실패 시 현재 구현의 CPU 합성과 명시적 화면 복구를 사용한다.
2. desktop 시작 시 관리 VirGL socket이 있으면 bounded guest `virpipe` offscreen probe를 실행한다. 성공해도 proxy 항목만 기록하며 hardware 기본값으로 고르지 않는다. 임의 Mesa 기본 driver의 desktop GPU 경로도 지원 완료로 취급하지 않는다.
3. 기본 guest GL은 `LIBGL_ALWAYS_SOFTWARE=true`, `GALLIUM_DRIVER=llvmpipe`로 실제 context·known-pixel·renderer를 검사한다. 실패하면 `softpipe`, 둘 다 실패하면 기존 `GDK_GL=disable`, `GSK_RENDERER=cairo`, Sway pixman으로 간다. malformed JSON·다른 UID·timeout·비정상 child 종료·renderer 불일치는 해당 provider 실패다. [구현된 probe 정책](../../guest/desktop/usr/local/lib/loopy/graphics_probe.py), [Mesa software 환경변수](https://docs.mesa3d.org/envvars.html).
4. 사용자가 메뉴의 **CPU OpenGL 창 검사** 또는 **VirGL 창 검사**를 선택하면 [GTK GLArea 검사 창](../../guest/desktop/usr/local/lib/loopy/graphics_demo.py)을 연다. VirGL은 현재 UID/token/pixel/socket 조건이 모두 맞을 때만 실행된다. GL context/readback 실패 시 Cairo 설명 창으로 전환하고 Linux session을 유지한다. socket·offscreen 통과와 실제 화면에 도달한 pixel은 서로 다른 검사다. [수동 선택 UI](../../guest/desktop/usr/local/lib/loopy/graphics_ui.py), [실행 guard](../../guest/desktop/usr/local/lib/loopy/graphics_session.py).
5. backend 전환 시 이전 `MESA_LOADER_DRIVER_OVERRIDE`, `GALLIUM_DRIVER`, `VTEST_SOCKET_NAME`, `VN_DEBUG`, `VK_DRIVER_FILES`, `VK_ICD_FILENAMES`를 지우고 다음 profile을 새로 만든다. Vulkan software는 실제 Lavapipe ICD가 있을 때 별도로 시험한다. Vulkan loader 존재만으로 Lavapipe를 가정하지 않는다.

아래 명령은 현재 구현한 user/probe 진입점이다. 명령의 존재와 특정 APK의 runtime 통과는 별도로 판정한다. 관리 server가 이미 실행 중이면 같은 token으로 두 번째 server를 직접 시작하지 않는다.

```sh
# guest terminal: 조건/실패 이유와 명시적 검사 메뉴
loopy-graphics

# 현재 session에서 검증된 CPU GL로 창 검사
loopy-gl /usr/bin/python3 /usr/local/lib/loopy/graphics_demo.py

# 현재 session의 VirGL 픽셀 증거·실제 socket이 유효한 경우만 실행
loopy-gl --virgl /usr/bin/python3 /usr/local/lib/loopy/graphics_demo.py

# 별도 bounded offscreen 진단. default desktop 선택을 바꾸지 않는다.
python3 /usr/local/lib/loopy/graphics_probe.py \
  --virgl-socket=/run/loopy/virgl-TOKEN.sock
```

probe는 제한 시간·exit code·stderr·host와 guest renderer·expected/actual pixel·선택/거부 이유를 기록한다. unsupported backend를 조용히 hardware로 표시하거나 무한 retry하지 않는다. 실제 app context가 device loss를 겪으면 기존 desktop을 유지하고 해당 app을 명시적으로 software profile에서 재시작한다.

## 대안별 조건과 사용자의 다음 동작

| 조건 / 원하는 경로 | 다음 동작 | 성공 판단 / 대체 경로 |
| --- | --- | --- |
| 현재 CPU GL 또는 VirGL 상태 확인 | desktop 메뉴 `GPU alternatives / check` → provider reason 읽기 → CPU 창 검사 또는 VirGL 창 검사 한 개씩 실행 | UID/token/offscreen와 표시 pixel을 구분. VirGL 실행 거부/창 오류면 CPU GL·Cairo 유지 |
| vendor GLES 또는 bridge 오류 | 메뉴 `다시 검사`로 bounded 진단, 결과 reason 확인. socket/GL 수락 후 다음 session에서 다시 확인 | 현재 앱을 자동 재시작하지 않음. Android settings/browser 또는 CPU desktop 계속 사용 |
| Venus Vulkan 필요 | host Vulkan/HardwareBuffer adapter와 guest Venus ICD를 추가하는 별도 구현에서 extension·FD/memory/sync·render probe | 메모리/동기화 실패면 VirGL 또는 CPU. 환경변수만으로 실행하지 않음 |
| Zink desktop GL 필요 | 실제 Vulkan transport/ICD를 먼저 확보하고 Zink feature/profile·WSI·앱 요구 GL 기능 검증 | 요구 feature가 없으면 GLES VirGL/CPU 또는 해당 Android native 앱 |
| ANGLE / libhybris 필요 | ANGLE는 별도 bionic backend package+probe; libhybris는 OEM driver/ABI/service adaptation prototype | stock EGL과 비교해 실제 pixel/renderer 검증. 실패하면 현재 stock EGL bridge 또는 CPU |
| 실제 Adreno이며 직접 KGSL 희망 | 실제 chip·app UID device/ioctl 권한·KGSL build의 Turnip render 확인 | 지원 chip/권한 불일치면 현재 Android VirGL 또는 CPU |
| 실제 Mali이며 Panfrost/PanVK 희망 | generation·kernel `panfrost`/`panthor`·DRM render node 접근 확인 | proprietary kbase만 있으면 vendor Android bridge. kernel 변경은 별도 기기 작업 |
| root/chroot/custom kernel 또는 Termux:X11 희망 | 별도 권한/환경의 driver·UID·socket·input/session 구성 확인 후 명시적으로 환경 전환 | root만으로 없는 UAPI를 해결하지 않음. 현재 APK/session과 수락을 분리 |
| GPU PC에 접근 가능 | 메뉴 Android browser 또는 guest terminal SSH로 실제 remote desktop/render service에 접속 | 서버 renderer·frame·network 검증. 로컬 guest GPU라고 표시하지 않음 |

## 구현 상태와 남은 수락

현재 loader·software probe·native server build/APK wiring·managed lifetime·guest proxy probe·수동 창 검사까지 구현했다. 이전 capability-fallback APK SHA-256 `157be08ca2c70cacdcd0d0f25c0c57de893a88745b26a75d1c254105aff6c3b7`은 `emulator-5580`, Android API 36, **앱 UID 10224에서 32/32 통과**했다. [이전 capability-fallback VM 영수증](../validation/2026-10-06-capability-fallback-final-vm/receipt.json). 남은 우선순위는 **VirGL EGL gate의 정확한 진단과 조건별 context 경로 → 실기기 host renderer/caps와 VirGL 표시 수락 → 일반 앱의 shader/texture/depth·여러 창·성능 → 필요한 Venus/Zink/ANGLE 또는 기기별 직접 driver/외부 backend**다. VM의 소프트웨어 렌더링 및 안전한 실패 수락을 물리 GPU 수락으로 확대하지 않는다.

- host EGL/GLES scene composition: 구현됨. 이전 capability-fallback VM에서 합성·Surface 교체 검사가 통과했다. 기록된 renderer는 Android Emulator ANGLE/SwiftShader이므로 물리 GPU 가속 증거는 아니다. 이전 검증과의 경계는 [daily-use GPU 검증](../daily-use-gpu-validation.md)에서 구분한다.
- guest software EGL probe/DRI loader: **이전 capability-fallback VM 수락됨**. same-build frontend와 isolated bounded JSON probe가 llvmpipe `LLVM 20.1.8`의 offscreen pixel을 확인했고, GTK GLArea의 RGBA `[51,102,153,255]`가 실제 desktop PixelCopy `ff336699`와 일치했다. 다른 UID·오래된 token 거부와 GL 실패 시 동일 Linux session의 Cairo 설명 창 전환도 통과했다. softpipe는 llvmpipe 성공으로 실행하지 않았으므로 이 영수증에서 별도 pixel 수락을 주장하지 않는다. [capability/fallback 검증 기록](../capability-fallback-validation.md).
- Android VirGL GLES server: **cross-build·APK input 검증·managed server/guest proxy 통합됨**. API 28 AArch64 PIE, `/system/bin/linker64`, 16KiB LOAD alignment, NEEDED `libc.so`/`libdl.so`/`libm.so`. `--no-fork`로 한 client씩 검사하고 현재 session socket과 offscreen 증거를 수동 창 검사 guard로 사용한다. [artifact receipt](../../build/virgl/arm64-v8a/libvirgl_server.receipt.json), [build log](../../build/virgl/build.log), [license 전문·notices](../../build/virgl/notices/NOTICE.md). 정확한 SHA는 receipt로 확인한다.
- Android VirGL의 **앱 UID 실행·session 소켓 준비·렌더러 실패 시 CPU 선택·소유 서버 종료 확인은 이전 capability-fallback VM 통과**했다. `virglServerProbeAndShutdown`의 PASS는 이 안전한 실패 계약이며 VirGL 렌더 성공이 아니다. `virpipe`는 child exit `-6`/연결 종료, 서버는 위 EGL gate 실패를 기록했고 proxy pixel은 미통과였다. VirGL 표시·host hardware·실기기 수락은 남아 있다. [이전 capability-fallback VM 영수증](../validation/2026-10-06-capability-fallback-final-vm/receipt.json).
- Venus/Zink/ANGLE/libhybris/직접 kernel GPU/외부 Termux:X11·remote GPU의 추가 부품은 위 조건표와 공식 근거에 따른 선택적 후속 경로다. 일반 multi-window hardware 기본값은 활성화하지 않았다.

현재 태블릿 APK의 결과·EGL gate 진단은 [Wayland 검증](../wayland-native-validation.md)의 해당 해시·영수증을 기준으로 한다.

## 2026-10-06 추가 구현과 Adreno830 조사

EGL core/KHR의 실제 초기화 버전을 기록하고, surfaceless가 없는 EGL1.4에서는 bootstrap·renderer·fence context마다1×1 pbuffer를 소유하도록 구현했다. binding 실패는 전달하고 자신의 context/surface만 정리한다. Android 자체 native crash reporter를 유지해 에뮬레이터 EGL의 잘못된 GLES4.x 요청 충돌을 확인했으며 GLES3.2를 초과하는 요청을 호출 전에 거절한다. 별도의16KiB LOAD와 RELRO 정렬 검사를 helper 빌드·패키징에서 수행한다. 현재 수락 결과는 [최신 검증 문서](../remaining-work-validation.md)에 기록한다.

Adreno830 대안으로 [mesa-for-android-container의 병합 PR54](https://github.com/lfdevs/mesa-for-android-container/pull/54)를 확인했다. 작성자는 REDMI K80 Pro에서 KGSL `VK_KHR_display` 관련 검사를 조정한 vkcube 결과를 보고한다. 이것은 TB522FU의 검증 결과가 아니다. 해당 배포는 glibc Linux 컨테이너용이며 현재 고정 Alpine은 musl이므로 배포 ICD를 그대로 복사해 해결할 수 없다. 직접 KGSL 접근·정확한 Mesa 빌드와 loader ABI·Wayland 표시를 같은 일반 앱 UID 및 실기기에서 검사해야 한다. 표의 Turnip/Zink 항목은 이 조건을 확보하는 후보이며 이 APK의 기본 가속으로 표시하지 않는다.


기본 GTK GL 공유 context에서 실패한 후보와 `GDK_GL=gles`로 성공한 후보를 같은 일반 APK UID에서 대조했다. 제품 wrapper는 검증된 VirGL 실행에만 GLES 프로필을 유지한다. [GTK 공식 선택 구현](https://github.com/GNOME/gtk/blob/3.24.49/gdk/wayland/gdkglcontext-wayland.c), [대조 영수증](../validation/2026-10-06-remaining-virgl-gdk-es-vm/receipt.json). 실제 알려진 RGBA를 읽고 Android Surface 색상을 대조했으며 임의 GL version override를 적용하지 않는다. 이는 해당 GTK 창의 프록시 표시이지 실제 Adreno·일반 다중 앱·DMA-BUF·연속 frame 성능 수락이 아니다.
