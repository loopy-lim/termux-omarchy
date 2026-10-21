# Android VirGL EGL 호환성 경계

확인일: 2026-10-06. 범위는 일반 Android 앱 UID에서 실행하는 현재 ARM64/API28 VirGL helper와 공식 Termux 패키지의 EGL 경로다. 물리 기기는 연결하지 않았고, root·ADB 권한 부여·OEM 설정 변경은 실행하지 않았다.

## 실패 원인과 확인할 조건

기존 [VM 기록](../validation/2026-10-06-virgl-native-probe-vm/receipt.json)은 서버 소켓 준비 뒤 guest `virpipe` 연결이 실패하고, 서버가 KHR context 확장 부족을 보고했다. 해당 기록에는 초기화된 EGL major/minor가 없으므로, 그 실패를 EGL 1.5 문자열 검사 오류로 단정할 수 없다.

EGL 1.5에는 KHR create-context와 surfaceless-context 기능이 코어로 편입됐다. 따라서 성공한 `eglInitialize`가 반환한 버전이 1.5 이상이면 두 KHR 문자열의 부재만으로 context 경로를 거절해서는 안 된다. 1.4 경로는 display의 정확한 두 확장 토큰이 필요하다. 근거: [EGL 1.5 사양, 부록 F](https://registry.khronos.org/EGL/specs/eglspec.1.5.pdf).

이 조건을 통과해도 GLES context가 surface 없이 current가 될 수 있다는 보장은 없다. 특히 GLES 1.x/2.x의 surfaceless 동작은 해당 client context의 `GL_OES_surfaceless_context` 지원에 의존하고, 지원하지 않으면 `eglMakeCurrent`가 실패한다. 실제 호출 결과를 검사해야 한다. 근거: [KHR surfaceless-context 사양](https://registry.khronos.org/EGL/extensions/KHR/EGL_KHR_surfaceless_context.txt).

## 구현한 제한적 overlay

[overlay](../../tools/virgl_egl_overlay.py)는 잠긴 VirGL 1.3.0 소스의 각 교체 지점이 정확히 한 번 존재하는지 모두 확인한 후 적용한다. 기존 source archive·Termux patch lock은 유지한다.

- 내부 display는 실제 `eglInitialize` major/minor를 보관한다. 외부 initialized display는 `EGL_VERSION`을 읽으며 다시 initialize하지 않는다.
- 항상 길이를 제한해 EGL initialized version, vendor, client APIs, core/KHR capability를 기록한다. 전체 extension 목록은 새 진단에 출력하지 않는다.
- ES2 bootstrap의 실제 `eglMakeCurrent` 실패는 초기화 실패다. 실패 뒤 GL identity를 조회하지 않는다. 성공한 bootstrap만 GL version/vendor/renderer를 기록한다.
- 일반 context 전환의 binding 실패는 `-1`로 전달한다. renderer 초기화는 callback binding 성공과 실제 GL/GLES 3.0 이상을 요구한다. 실패하면 만든 renderer context를 한 번 파괴하고 중단한다.
- 초기화 실패 시 생성한 context, 현재 binding, 초기화한 display를 정리한다. initialize 자체가 실패한 display에는 terminate를 호출하지 않는다.
- pbuffer backend는 추가하지 않았다. 하나의 전역 pbuffer를 붙이는 접근은 renderer와 threaded-fence context의 surface/current/소유권을 모두 처리하지 못한다. 별도 구현은 context별 surface와 모든 bind·unbind·destroy·실패 정리를 함께 검증해야 한다. EGL의 surface/context/thread 조건은 [EGL 1.5 사양 3.5 및 3.7](https://registry.khronos.org/EGL/specs/eglspec.1.5.pdf)에 따른다.

빌더 입력 해시에 overlay 모듈을 추가했다. receipt는 수정된 EGL C, renderer C, 생성 guard header를 기존 Meson/winsys와 함께 기록한다. APK 입력 검사도 overlay가 누락됐거나 빌드 뒤 변경됐으면 서버를 거절한다.

## 현재 빌드 증거와 다음 실제 검사

관련 host 검사는 22개 통과했다. [실행형 C regression](../../tests/test_virgl_egl_overlay.py)은 core 1.5/KHR 1.4, 실제 initialize 버전 우선, binding 실패 후 GL 조회 금지, 정리 순서, renderer 최소 버전과 소스 drift를 검사한다. [입력 검사](../../tests/test_virgl_inputs.py)는 실제 임시 파일/receipt에서 overlay 변경·누락·미기록을 거절한다. 이는 실제 GPU driver 검사가 아니다.

현재 재빌드된 [helper](../../build/virgl/arm64-v8a/libvirgl_server.so)는 1,662,536바이트, SHA-256 `5416909fa333d6aecf099153a4fe35e062b591127f5657131c4d2adbb6ee4270`이다. [빌드 receipt](../../build/virgl/arm64-v8a/libvirgl_server.receipt.json), [로그](../../build/virgl/build.log)는 ARM64 PIE/API28, Android linker64, 16KiB LOAD 정렬과 libc/libdl/libm 의존성, 현재 입력·생성 소스 해시 일치를 뒷받침한다. 이 문서는 최종 APK 또는 새 VM 렌더링 성공을 선언하지 않는다.

다음 app-UID 검사는 서버의 initialized EGL 값과 bootstrap GL identity, guest Mesa renderer/version, 실제 readback 픽셀, 실제 GUI 표시를 각각 기록해야 한다. 서버 소켓, bootstrap ES2, guest renderer 문자열만으로 guest 3D나 물리 GPU 성능을 승격하지 않는다. `virpipe` 실패는 기록하고 검증된 llvmpipe/softpipe 또는 기본 화면 표시 경로를 유지한다. VM의 SwiftShader/ANGLE 결과는 물리 GPU 증거가 아니다.

## Termux 서버를 선택할 때

공식 Termux의 현재 [VirGL 패키지](https://raw.githubusercontent.com/termux/termux-packages/master/packages/virglrenderer-android/build.sh)와 [CLI patch](https://raw.githubusercontent.com/termux/termux-packages/master/packages/virglrenderer-android/0007-Ensure-EGL-GLES-ANGLE-help-and-socket-path.patch.beforehostbuild)는 기본 EGL surfaceless/GLES 경로를 강제한다. 그래서 해당 패키지의 실제 `--help`를 확인해야 한다. Loopy가 잠근 helper는 이 patch를 적용하지 않으며 기존 `--no-fork --use-egl-surfaceless --use-gles --socket-path=…` 계약을 유지한다.

| 조건별 경로 | 실제로 필요한 확인 | 실패하면 |
|---|---|---|
| Termux 기본 Android EGL/GLES | initialized EGL, GLES 3 이상 context 생성·binding, guest renderer 및 픽셀 | 검증된 software GL을 유지 |
| `--angle-gl` | 해당 ANGLE GL 라이브러리와 Android driver가 실제 current/context·픽셀을 제공 | 기본 GLES 또는 software 경로 |
| `--angle-vulkan` | 실제 ANGLE Vulkan build, 사용 가능한 Vulkan driver, renderer/version 및 픽셀 | GL backend 또는 software 경로 |
| `--angle-null` | offscreen Vulkan-display build에서 실제 renderer·픽셀 확인; X11/Wayland 표시 검사는 별도 | 다른 backend 또는 software 경로 |

Termux의 `--angle-null`은 Vulkan surface/swapchain을 쓰지 않는 offscreen-display build다. ANGLE의 별도 no-op NULL renderer와 혼동하지 않는다. 근거: [Termux ANGLE build](https://raw.githubusercontent.com/termux/termux-packages/master/packages/angle-android/build.sh), [빌드 인자](https://raw.githubusercontent.com/termux/termux-packages/master/packages/angle-android/args.gn.in), [ANGLE Vulkan null-display 옵션](https://chromium.googlesource.com/angle/angle/+/main/gni/angle.gni). 어느 옵션도 실제 provider/version·픽셀 검사를 대신하거나 장치의 하드웨어 가속을 보장하지 않는다.
