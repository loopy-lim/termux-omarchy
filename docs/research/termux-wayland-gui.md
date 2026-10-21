# Termux native Wayland / Sway / Termux:GUI 조사

조사일: 2026-10-06. 목표는 Wayland 데스크톱의 키보드·마우스·GPU 경로다. 아래 Termux:GUI 경로는 공식 소스를 확인한 **별도 후보**이며 설치·실행·성능 수락을 하지 않았다. 이번 조사에서 APK·패키지·helper를 다운로드하거나 VM 세션을 시작·종료하지 않았다. 현재 제품 기본 경로를 교체하지 않는다.

## 결론

공식 Termux 패키지는 Bionic native Sway 1.10.1-1과 wlroots 0.18.2-1을 제공하며, wlroots에는 Android Termux:GUI용 출력·입력·버퍼 allocator가 있다. 빌드 옵션 이름은 `termuxgui`지만 **실행 값은 `WLR_BACKENDS=tgui`**, 출력 수는 `WLR_TGUI_OUTPUTS=1`이다. X11 서버 없이 별도 Android Activity에 Wayland 데스크톱을 표시할 수 있는 구현 후보다. 그러나 GPU import와 키보드·마우스·IME·종료 계약의 실사용 검증은 남아 있다. [공식 recipe][wlroots-build], [runtime backend 선택 patch][patch], [Sway recipe][sway-build]

현재 Loopy의 Android Wayland 서버는 이미 native Rust/JNI이고 Android Surface 출력은 system EGL/GLES를 사용한다. PRoot는 Alpine/Sway/Linux 앱 실행 쪽에 있다. Termux를 추가한다고 이미 native인 Android 출력 경로가 자동으로 빨라지거나 guest GL이 hardware가 되지는 않는다. 현 단계 최소 작업은 기존 Wayland 경로의 실제 앱 입력·표시·종료를 다시 수락하고, 그 위에 GPU 경로를 별도 단계로 검증하는 것이다. [현재 모듈 설명](../runtime-implementation.md), [현재 GPU 검증](../capability-fallback-validation.md)

## 재현 가능한 공식 소스 pin

GitHub API의 branch HEAD를 읽고 해당 commit URL의 원본 바이트를 확인했다. 변경 가능한 `master`의 검색 캐시 대신 아래 pin을 조사 기준으로 사용한다. 패키지 recipe pin은 설치된 `.deb`나 APK의 바이트 검증을 대신하지 않는다.

| 저장소 | 확인한 commit | 범위 |
|---|---|---|
| termux/termux-packages | `7945fdb5a62d773e98cae56f2e43438d859f9009` | Sway/wlroots/foot/Mesa/libglvnd recipe와 tgui backend |
| termux/termux-gui | `be24a5f34681096a788a6b0559caf833f87bd691` | plugin manifest, HardwareBufferSurfaceView, RawInputConnection |

| 입력 | SHA-256 |
|---|---|
| wlroots/build.sh | `8e1aca9052bb5fef62dcb07c2f4e165f183ddfae1fb7517b11e3f2d86eefa3cb` |
| sway/build.sh | `a829a4488ff0413eaa67da1eaa0af56e35607d2145d5730635676eb735fe3f90` |
| 0003-impl-termux-gui-backend.patch | `b0f0fe686ff7cb59a01c0cace93b0c1e6254137a419a0b4db6fff91d52494904` |
| termuxgui/backend.c | `6788a8fdd4382c0e38e0890731ec102c51bb11f0ff28177d1557cc3e0db4f58a` |
| termuxgui/input.c | `4ded7d74c5aa4b4dc8ea6169ea4c922c5fc523dfeb78a5589b946c957fa0c342` |
| termuxgui/output.c | `73f0b86e4559eac792ec5bef85a8cbf01c61789e78f2efac6a006cc2ee177e59` |
| termuxgui/allocator.c | `4b5e91ff250540b22d5deb1bcdb394e9df001e994b54c77aa565f83e52edbb65` |
| mesa/build.sh | `77496f62930264fe0facb2d45d09a035736137d2df2385614a797cbebd70725b` |
| libglvnd/build.sh | `c68bff4bfaa12201eb905340e744e77773f403ab9367c6d58aa201f0f290a079` |

wlroots upstream tar SHA는 `a28061f7778f28f7be377fd4d6f0ebd58cb2a63b52460e9fde28e2ab43e80cab`, Sway tar SHA는 `b2fbf3a2f94c8926efa18d6af59bb9f5f1eafa6d46491284b1610c57bef2d105`다. recipe는 `-Dsession=disabled`, `-Dbackends=x11,termuxgui`, `-Drenderers=gles2,vulkan`을 지정하고 `termux-gui-c`를 의존한다. `x11-packages`는 repository channel 이름이며 tgui 실행에 X 서버를 반드시 쓴다는 뜻이 아니다. [wlroots recipe][wlroots-build], [Sway recipe][sway-build]

## 출력과 GPU의 실제 경계

| 경로 | 확인한 구현 | 필요한 조건 / 남은 검사 |
|---|---|---|
| 현재 Loopy Android 출력 | Rust Wayland host → system EGL/GLES2 → Android Surface; CPU fallback | 기존 VM에서 GLES 색상/Surface 재생성 수락. VM renderer는 ANGLE/SwiftShader라 Y900 hardware 성능 증거가 아님 |
| 현재 Sway/Linux 앱 | nested Wayland backend, `WLR_RENDERER=pixman`; GTK 기본 cairo; `wl_shm`로 host 전달 | guest hardware GL·DMA-BUF import·zero copy 없음. CPU GL은 실제 픽셀 및 선택된 GTK demo 표시를 별도 수락 |
| 현재 VirGL | Loopy UID의 Android vtest server와 guest virpipe probe | socket 준비와 renderer 준비는 별개. 최근 후보도 EGL capability gate에서 실패, llvmpipe 유지 |
| Termux tgui compositor | Sway/wlroots native Bionic; tgui AHardwareBuffer allocator → DMA-BUF → compositor GLES2/Vulkan | GLES/Vulkan provider의 실제 DMA-BUF import, format/stride/linear modifier, pixel render 확인 필요. `libdrm` 패키지 의존만으로 DRM 장치 권한이 생기지 않음 |
| Termux:GUI Android 표시 | shared HardwareBuffer → EGL native-buffer image → external texture → SurfaceView | 별도 plugin/동일 서명·shared UID, Android EGL native-buffer extensions, Surface 수명 확인 필요 |

tgui allocator는 RGBA8888 AHardwareBuffer를 만들고 native handle의 FD 중 `lseek` 크기가 stride×height×4 이상인 하나를 선택해 단일 plane, linear modifier의 DMA-BUF로 내보낸다. Android native handle 내부를 이 조건으로 해석할 수 있는지는 gralloc/driver/VM별 검사 대상이다. 잘못된 FD나 modifier에 성공을 선언하면 안 된다. [allocator.c][allocator]

공식 patch는 Termux에서 일반 DRM render-node 탐색 일부를 생략하고 tgui allocator를 우선한다. GLES EGL 초기화 및 import 조건은 여전히 남고, Vulkan 후보는 `VK_EXT_external_memory_dma_buf`와 `VK_EXT_image_drm_format_modifier`를 검사한다. Android system Vulkan이 있다는 사실만으로 이 확장이나 native Sway render 성공을 보장하지 않는다. [EGL/Vulkan patch][patch]

Termux Mesa recipe는 x11/wayland platform, llvmpipe/softpipe/virgl/zink, ARM Freedreno의 msm/kgsl 선택을 포함한다. libglvnd는 Mesa를 권장하고 system EGL과 충돌하지 않도록 SONAME을 구분한다. 그러므로 tgui의 Android 표시가 system GLES여도 **Sway compositor가 쓰는 Termux EGL/Mesa가 같은 hardware provider라는 결론은 성립하지 않는다**. 먼저 compositor의 실제 EGL vendor/version, GL renderer, import 확장과 rendered pixel을 기록해야 한다. [Mesa recipe][mesa-build], [libglvnd recipe][glvnd-build]

Termux:GUI SurfaceView는 Android 8+ HardwareBuffer와 EGL native-buffer image 확장, GLES external-image 확장을 요구하며 context/surface를 다시 만든다. `setBuffer`/frame callback이 있다는 사실과 특정 frame의 화면 표시 완료는 구분해야 한다. wlroots tgui의 `present_complete`는 내부 queue 알림으로 `presented=true`를 보내므로 실제 Android frame의 pixel witness도 필요하다. [HardwareBufferSurfaceView][surface], [output.c][output]

## 입력·수명 계약: 그대로 교체할 수 없는 이유

| 항목 | pinned tgui backend가 하는 일 | gap / 필요한 검증 |
|---|---|---|
| keyboard | Android keycode를 작은 Linux key table로 바꿔 wlroots keyboard에 전달; Shift/Ctrl/Alt modifier 처리 | Tab/Escape/방향/F키/Meta/keypad/NumLock 항목이 table에 없음. key.codePoint도 일반 Unicode commit으로 처리하지 않음 |
| scancode / device | backend 생성 때 단일 `tgui-keyboard`와 `tgui-pointer`를 등록 | input.c가 scanCode/deviceId별 상태를 사용하지 않음. per-device hotplug·held key 해제 계약 없음 |
| IME | SurfaceView가 TYPE_NULL RawInputConnection을 반환 | commitText/setComposingText/deleteSurroundingText가 false. 한국어 조합/emoji 입력을 현재 Loopy InputConnection 수준으로 수락하지 못함 |
| mouse | touch를 trackpad처럼 cursor 이동/탭/두 손가락 우클릭·세로 scroll로 해석 | output 이벤트 switch에 generic mouse hover/wheel/captured-relative 처리 없음. 물리 5-button/horizontal wheel 및 focus capture 계약 필요 |
| pointer capture | tgui SurfaceView 생성·focus 요청 | 조사한 output/input/SurfaceView에는 requestPointerCapture/onCapturedPointerEvent가 없음. Android cursor 경계 없는 relative mouse 수락 필요 |
| pause / resume | output.foreground flag를 바꾸고 background presentation을 잠시 쉼 | pause에서 keyboard/buttons clear를 하지 않음. focus loss의 balanced release, 화면 재생성, 재연결 회귀 필요 |
| destroy / stop | Activity destroy→output destroy; queue/thread/allocator/connection 해제 | compositor/session/process 전체의 bounded normal stop·descendant reap는 별도 실행기 계약. 기존 X11 helper stop 실패를 tgui 성공 근거로 사용할 수 없음 |

근거는 [input.c][input], [backend.c][backend], [output.c][output], [RawInputConnection][ime], [SurfaceView][surface]의 해당 분기다. 현재 Loopy의 keyboard/mouse 우선권·비상 Ctrl+Alt+Esc·device loss 처리까지 이 후보에 자동 승계되지 않는다.

## 권한과 실행 조건

Termux:GUI manifest는 `sharedUserId="com.termux"`를 선언한다. 사용자는 Termux와 같은 배포 서명의 plugin을 골라야 하며 현재 표준 Termux:X11 APK 설치를 Termux:GUI 설치 완료로 간주하면 안 된다. 이번에는 plugin APK의 version/hash/certificate나 installed UID를 검증하지 않았다. [manifest][manifest], [공식 설치 안내](https://github.com/termux/termux-app#installation)

Termux:GUI protocol은 abstract Unix socket 두 개와 명시적 receiver broadcast를 사용한다. 같은 UID peer 검사를 권장한다. 기존 Loopy UID의 app-private Wayland socket에 다른 Termux UID가 임의로 접근할 수 있다고 가정하지 않는다. 기존 host에 Termux native Sway를 nest하려면 명시적 FD/IPC 계약 또는 Termux 안에 host를 함께 실행하는 별도 구조가 필요하다. [protocol][protocol], [Android app sandbox](https://source.android.com/docs/security/app-sandbox)

일반 foreground Activity 출력과 background/overlay 창은 다르다. Termux:GUI 공식 README는 background/overlay 창에 사용자가 Display over other apps를 선택하도록 안내한다. foreground에서 시작하는 최소 실험에 overlay를 자동 부여하지 않는다. Loopy가 Termux RUN_COMMAND로 실행한다면 그 custom permission, allow-external-apps, service UID/context와 callback/stop 수명도 별도 검사한다. [Termux:GUI README][gui-readme], [Termux RUN_COMMAND 공식 안내](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent)

현재 Loopy 입력은 focused View의 public keyboard/mouse + pointer capture가 기본이다. API34 Accessibility generic-motion 경로는 선택한 source를 Android의 나머지 시스템에 보내지 않으므로 Linux가 실제 입력을 소유하는 동안만 요청해야 한다. touch exploration·다른 서비스·OEM reserved keys의 제약은 남는다. raw `/dev/input`, system-wide injection이나 Home/Recents 전체 탈취를 일반 앱/Termux 권한으로 해결한다고 주장하지 않는다. [pointer capture](https://developer.android.com/develop/ui/views/touch-and-input/gestures/movement#pointer-capture), [AccessibilityService.onMotionEvent](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#onMotionEvent(android.view.MotionEvent)), [권한 대안 조사](android-authority-alternatives.md)

## 실행하지 않은 bootstrap 초안

아래는 별도 승인된 실험 환경에 Termux:GUI가 같은 서명으로 이미 설치되고, package/source·UID 검사가 끝난 뒤 사용할 초안이다. 설치 명령과 launch는 이번 조사에서 실행하지 않았다. 기존 사용자 config와 실패 marker를 재사용하거나 덮어쓰지 않는다.

```sh
# package channel만 활성화; X 서버 launch 아님
pkg install x11-repo
pkg install sway foot mesa
dpkg-query -W sway wlroots foot termux-gui-c mesa libglvnd

# 별도 실험 디렉터리: 소유 UID, chmod 0700, 기존 경로 부재를 먼저 검사
export XDG_RUNTIME_DIR="$PREFIX/tmp/loopy-wayland-trial"
mkdir -m 700 "$XDG_RUNTIME_DIR"
unset DISPLAY WAYLAND_DISPLAY
export WLR_BACKENDS=tgui WLR_TGUI_OUTPUTS=1 WLR_RENDERER=gles2
# 임의 GPU/driver override 없이 먼저 실패와 실제 provider를 수집
sway -d -c "$HOME/loopy-wayland-trial.config"
```

config 초안은 `xwayland disable`, Ctrl+Alt 기반 단축키, native `foot` 한 창, 로컬 shell/UTF-8 witness만 포함한다. 다만 현재 tgui key table에서 Alt/Ctrl chord의 key와 modifier 일부가 누락되므로 **실사용 키맵 수락 전 먼저 table 보완이 필요**하다. `foot`도 실제 PTY와 한글 glyph/IME 입력을 검사해야 한다. `WLR_RENDERER_ALLOW_SOFTWARE=1`로 실패를 넘기는 실험은 CPU renderer로 표시하며 hardware 통과로 기록하지 않는다. [foot 공식 recipe][foot-build], [input.c][input]

GPU 기기가 있으면 renderer를 문자열로 선택하는 데서 끝내지 않고 native provider 검사→buffer allocation/import→색상 pixel→Wayland GTK/foot 표시→resize/suspend/stop 순서로 진행한다. Turnip/Zink/Venus는 실제 GPU/API/ICD/import 조건이 맞을 때 별도 후보로 기록하며 임의로 ready로 승격하지 않는다.

## 현재 Wayland 경로의 최소 변경·수락 추천

1. 기존 Android host/Sway 경로를 유지하고 public launcher→실제 foot PTY→오직 키 입력으로 witness 파일 생성→한국어 IME commit→물리 mouse focus/wheel/5buttons→정상 stop를 같은 APK로 확인한다. 숫자 키패드·NumLock·device detach 시 다른 keyboard modifier 보존을 추가한다.
2. GPU UI에서 Android Surface composition과 Linux renderer를 계속 분리한다. VirGL socket ready, offscreen GL readback, GTK demo 화면 pixel을 서로 다른 단계로 보여준다. 현재 failed EGL gate를 hardware 승격으로 바꾸지 않는다.
3. 성능 우선 최소 seam은 host의 damage/immutable SHM snapshot/texture cache/frame pacing이다. 현재 `wl_surface.damage` rectangle을 저장하지 않고 dirty buffer 전체를 snapshot한 뒤 GPU upload하므로 작은 변경도 full upload한다. 동일 크기 texture 캐시와 damage 전달을 실제 측정하며 buffer release·Surface replacement·CPU fallback을 보존한다. [core_protocol.rs](../../native/wayland-host/src/core_protocol.rs), [state.rs](../../native/wayland-host/src/state.rs), [gles.c](../../native/wayland-host/src/gles.c)
4. full guest GPU에는 Linux DMA-BUF global/format/modifier/sync/import 또는 Android HardwareBuffer 기반 명시적 buffer transport가 필요하다. 현재 host globals는 `wl_shm`뿐이므로 `WLR_RENDERER=gles2`만 바꾸는 것을 해결책으로 제시하지 않는다. [server.rs](../../native/wayland-host/src/server.rs)
5. Termux tgui는 위 기본 경로와 별도 source/installer/permission/process contract를 가진 후속 실험으로 둔다. Android-facing 입력 table·IME·mouse capture를 보완하고 actual provider/pixel/stop까지 검사해야 default 전환을 논의할 수 있다.

## 증거와 아직 하지 않은 검사

기존 [capability-fallback-final-vm receipt](../validation/2026-10-06-capability-fallback-final-vm/receipt.json)의 32/32는 해당 전달 APK만의 기록이다. Android renderer는 emulator ANGLE/SwiftShader, Linux GL은 llvmpipe이며 VirGL 실패 fallback/owned shutdown이 검사됐다. 이후 [native-egl-candidate-vm](../validation/2026-10-06-native-egl-candidate-vm/receipt.json)의 단일 PASS는 EGL 실패 처리·llvmpipe 유지·서버 종료 계약 통과다. VirGL pixel/GUI hardware 성공이 아니다. 이번 문서는 최신 전체 VM suite나 35/35 완료를 새로 선언하지 않는다.

물리 Y900/USB·Bluetooth keyboard/mouse가 연결되지 않았으므로 실제 capture/hotplug/NumLock LED/한글 IME, OEM reserved keys, Adreno driver/import, 장시간 battery/thermal/refresh/input latency는 미검증이다. API35와 API36의 차이도 동일 앱 UID의 별도 VM 실행으로 확인해야 한다. VM synthetic 이벤트나 ADB/run-as를 물리·일반 앱 권한 수락으로 합치지 않는다.

VM 실험의 `hardwareKbdScancodesWorkaround`만 이전 true로 복원했고 다른 51개 preference·installed helper/source·properties 및 미확정 failed owner marker를 그대로 확인했다. 이는 [VM setup rollback receipt](../validation/2026-10-06-native-termux-preime-restore-Atkn7Q/receipt.json)이며 Wayland나 native stop 수락이 아니다.

[wlroots-build]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/wlroots/build.sh
[sway-build]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/sway/build.sh
[patch]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/wlroots/0003-impl-termux-gui-backend.patch
[backend]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/wlroots/src/backend/termuxgui/backend.c
[input]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/wlroots/src/backend/termuxgui/input.c
[output]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/wlroots/src/backend/termuxgui/output.c
[allocator]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/wlroots/src/backend/termuxgui/allocator.c
[mesa-build]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/mesa/build.sh
[glvnd-build]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/libglvnd/build.sh
[foot-build]: https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/foot/build.sh
[surface]: https://github.com/termux/termux-gui/blob/be24a5f34681096a788a6b0559caf833f87bd691/app/src/main/java/com/termux/gui/views/HardwareBufferSurfaceView.kt
[ime]: https://github.com/termux/termux-gui/blob/be24a5f34681096a788a6b0559caf833f87bd691/app/src/main/java/com/termux/gui/protocol/shared/v0/RawInputConnection.kt
[manifest]: https://github.com/termux/termux-gui/blob/be24a5f34681096a788a6b0559caf833f87bd691/app/src/main/AndroidManifest.xml
[protocol]: https://github.com/termux/termux-gui/blob/be24a5f34681096a788a6b0559caf833f87bd691/Protocol.md
[gui-readme]: https://github.com/termux/termux-gui/blob/be24a5f34681096a788a6b0559caf833f87bd691/README.md
