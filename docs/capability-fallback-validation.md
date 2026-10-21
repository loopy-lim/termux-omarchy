# GPU·입력 대체 경로 구현과 검증

2026-10-06 추가 요청에 따라 지원되지 않는 기능을 종료 지점으로 두지 않고, 실제 검사 결과와 다음 경로를 연결했다. 이 문서는 이전 [입력·권한·GLES 전달물](daily-use-gpu-validation.md)의 후속 기록이다.

## 현재 전달물과 최종 결과

[설치 APK](../build/deliverables/LoopyDesktop-2026-10-06-capability-fallbacks-arm64.apk)는 ARM64, Android 9/API28 이상, target SDK36이며 325,547,274바이트(약 326MB)다. 전체 검사를 통과한 빌드와 전달 APK의 크기·SHA256이 같다. 이전 APK는 보존했다. [전달 영수증](../build/deliverables/LoopyDesktop-2026-10-06-capability-fallbacks-arm64.apk.receipt.json), [해시 파일](../build/deliverables/LoopyDesktop-2026-10-06-capability-fallbacks-arm64.apk.sha256), [사용 안내](desktop-quickstart-ko.md)를 함께 제공한다.

```text
APK SHA-256: 157be08ca2c70cacdcd0d0f25c0c57de893a88745b26a75d1c254105aff6c3b7
Test APK:    e9e7c4b0187bbd579ab889b5b676c29f9514c68e4990291ca405ab2bab447139
Rootfs:      82e4fa6349932b2122493816e2b17961d8f809c5e4c4641fa22e0586b92edc6c
VirGL:       88ce087d1dadcbc7ffee33b26a1771d215942b5bc617cec1b29fdc76edba4eb3
```

이미지는 고정 패키지 258개와 Linux 파일 823,326,602바이트를 포함한다. VirGL 서버는 virglrenderer1.3.0·libepoxy1.5.10·NDK27.1.12297006/API28로 빌드했고 라이선스를 APK에 포함했다. [Rootfs 영수증](validation/2026-10-06-capability-fallback-final-vm/rootfs-receipt.json), [VirGL 빌드 영수증](validation/2026-10-06-capability-fallback-final-vm/virgl-build-receipt.json)의 빌드 성공은 렌더링 성공과 구분한다.

| 검사 | 결과 | 증거 |
| --- | --- | --- |
| 호스트 정책·프로세스·도구·회귀 | **196개 통과**, ResourceWarning 오류 처리 | [호스트 로그](validation/2026-10-06-capability-fallback-final-vm/host-tests.txt) |
| Rust Wayland | **40개 통과** | [네이티브 로그](validation/2026-10-06-capability-fallback-final-vm/native-tests.txt) |
| 최종 APK 전체 Android VM | **32/32 통과**, API36·앱 UID10224·SELinux untrusted_app | [최종 영수증](validation/2026-10-06-capability-fallback-final-vm/receipt.json), [계측 출력](validation/2026-10-06-capability-fallback-final-vm/instrumentation.txt) |
| 소스·APK 입력 | 입력87개·네이티브 소스27개·guest 설정35개·payload7개 일치, 불일치0개. 전체 VM 후 재대조 | [입력 대조](validation/2026-10-06-capability-fallback-final-vm/source-input-integrity.json), [빌드 영수증](validation/2026-10-06-capability-fallback-final-vm/build-receipt.json) |
| 코드 크기 | 239개 확인, 최대499줄 | [크기 검사](validation/2026-10-06-capability-fallback-final-vm/code-size.txt) |

최종 VM은 `llvmpipe (LLVM 20.1.8, 128 bits)`의 실제 RGBA `[51,102,153,255]`와 GTK 창의 Android Surface 픽셀 `ff336699`를 확인했다. GTK 프로세스 UID도 앱과 같았다. 다른 UID·오래된 session token의 보고서는 거부했다. GL을 실제로 비활성화한 GTK 초기화 실패에서는 Cairo 설명 창으로 전환하고 같은 Linux 세션을 유지했다. llvmpipe가 성공해 softpipe child는 실행하지 않았으므로 이 VM에서 softpipe 픽셀 성공은 주장하지 않는다.

VirGL 서버·소켓은 같은 앱 UID로 준비됐다. 실제 virpipe client는 exit `-6`과 연결 종료, 서버는 `Missing EGL_KHR_surfaceless_context or EGL_KHR_create_context`와 renderer 초기화 실패를 기록했다. **이 VM의 VirGL 렌더링은 미통과**다. `virglServerProbeAndShutdown`의 PASS는 실제 시도·llvmpipe 선택·소유 서버 종료 확인의 실패 계약을 검증한다. EGL version/vendor/extensions를 수집하지 않았으므로 이 오류만으로 EGL1.5 core 기능이나 실기기 지원 여부를 판정하지 않는다.

기존 브라우저·Geany 공유 파일 저장·HTTPS·클립보드·터치패드·입력 반납·세션 복구도 같은 APK에서 재검증했다. 대체 방법 패널에서 알림 준비로 돌아와도 같은 Linux 세션을 유지하고 입력 캡처를 반납했다. 설정 Intent 실패·일반 설정 fallback·두 경로 모두 불가한 경우는 실행 가능한 Java 호스트 정책 검사로 검증했다. OEM별 실제 설정 화면 부재는 실기기 확인 항목이다.

## 구현한 경로

새 세션에서 Android API28 ARM64 VirGL 서버를 같은 앱 UID로 실행하고 전용 소켓을 만든다. Mesa 게스트는 실제 vtest 연결·EGL/GLES 픽셀·renderer를 검사한다. transport 존재만으로 GPU가 준비됐다고 판정하지 않는다. 실패 또는 미지원은 `llvmpipe → softpipe → Cairo`로 이어진다. 기본 앱은 검증된 CPU GL 경로와 Sway pixman/wl_shm 출력을 사용한다. VirGL은 픽셀·현재 세션·살아 있는 소켓이 검증된 경우 사용자가 선택한 창 검사에만 연결된다.

- 누락된 `mesa-dri-gallium 25.1.9-r0`를 기존 Mesa와 같은 source commit으로 고정했다. 공식 APK SHA256·APKINDEX control·datahash·dependency closure를 검증한다.
- child마다 5초 제한, stdout/stderr 크기 제한, 실제 UID·JSON·renderer·픽셀 검증을 적용한다. 잘못된 보고서와 다른 세션의 증거는 Cairo 또는 검사 대기로 처리한다.
- `loopy-gl <명령>`은 현재 세션에서 확인된 software GL을 적용한다. `loopy-gl --virgl <명령>`은 검증된 proxy와 소켓을 추가로 요구한다. 게스트 EGL/GL 버전 override·loader 환경은 검사와 일치하도록 제거한다.
- 데스크톱 앱 메뉴 **GPU alternatives / check**에서 현재 상태, CPU GL 창 검사, VirGL 창 검사, 재검사, Android 설정·브라우저 이동을 제공한다. 재검사는 실행 중인 앱이나 세션을 재시작하지 않는다.
- GL 창 초기화 실패는 GTK Cairo 설명 창으로 내려가며 세션을 유지한다. 진단 창은 실제 GL readback과 계속되는 재그리기를 사용한다.
- **설정 → 실사용 준비 · 권한/진단 → 대체 방법**에서 기본 입력, 접근성 연결, 일반 pointer 입력, 키보드 설정·IME 선택, 고급 경로의 조건을 안내한다. Android 설정 화면이 없으면 일반 설정으로 이어지며 Linux를 유지한다.
- VirGL 서버는 `--no-fork`로 한 client씩 검사한다. 세션 종료·전환·취소에서 소유 프로세스만 종료하고 확인한다. 종료 미확인 owner는 재수거할 수 있으며 종료된 Linux를 실행 중으로 표시하지 않는다.

## 가능한 GPU 방법

| 방법 | 현재 연결 / 다음 조건 |
| --- | --- |
| Android GLES → CPU 합성 | 기존 화면 출력 자동 fallback 구현 |
| llvmpipe → softpipe → Cairo | 실제 픽셀 검사와 새 세션 자동 선택 구현 |
| Android VirGL + guest virpipe | API28 서버 빌드·APK·앱 UID probe·선택 창 검사 구현. 일반 다중 창 GPU 기본 경로는 미수락 |
| Venus/vtest Vulkan | Venus host/guest 구성, Vulkan 외부 메모리·동기화·표시 WSI를 추가해야 함 |
| Zink / ANGLE | 지원 Vulkan backend와 guest transport·표시 경로를 먼저 준비 |
| Turnip/Freedreno KGSL | 실제 지원 Adreno, KGSL 접근·ioctl·맞는 Mesa build·실제 렌더 필요 |
| Panfrost/PanVK/Lima | 지원 Mali와 해당 DRM kernel/render node 필요 |
| Android OEM EGL/Vulkan ABI bridge | OEM ABI/gralloc/서비스 연동 필요. libhybris의 musl 지원 가능성과 실기기 호환은 별개 |
| Termux:X11 + VirGL/Turnip | 별도 Termux/X11 환경과 기기별 driver 설정 필요 |
| root chroot / custom kernel | 별도 장치 관리·맞는 UAPI/driver 필요. root만으로 driver 호환이 생기지 않음 |
| 원격 GPU 데스크톱 / 렌더 서비스 | GPU PC와 인증·네트워크를 준비해 브라우저/터미널로 연결 |
| Android 네이티브 앱 | 현재 Android 앱 메뉴·브라우저로 이동 가능 |

드라이버별 실제 요구 조건과 공식 출처는 [GPU 경로 조사](research/guest-gpu-alternatives.md)에 있다.

VirGL의 EGL gate 실패에는 세 가지 다음 경로가 있다. 먼저 서버가 사용하는 EGL version/vendor/extensions와 GLES3 context를 조사한다. EGL1.5 core 기능을 KHR 문자열 부재 때문에 거부한 경우에는 version-aware 검사와 실제 makeCurrent·픽셀 검증을 추가한다. 진짜 surfaceless 미지원이면 bootstrap·render current·정리 경로 전체에 pbuffer surface를 구현해야 한다. GLES3/caps 자체가 부족하면 CPU를 유지하거나 다른 Android GLES/ANGLE backend 또는 지원 기기로 이동한다. 현재 CLI flag만 바꾸는 것은 pbuffer 구현을 대신하지 않는다. 이 추가 bridge 후보는 현재 APK에 구현된 경로로 표시하지 않는다. [EGL1.5 규격](https://registry.khronos.org/EGL/specs/eglspec.1.5.pdf).

## 가능한 입력·권한 방법

| 방법 | 현재 연결 / 다음 조건 |
| --- | --- |
| Activity 입력·pointer capture | 포커스 및 OS가 제공한 키·마우스·터치의 기본 경로 구현 |
| 사용자 접근성 | live 연결과 Android14+ motion 소유 상태에 따라 적용, 설정 이동 구현 |
| modifier 변경·화면 버튼 | Meta 예약 키가 막히면 Ctrl+Alt/다른 modifier 또는 메뉴·작업공간 버튼 |
| 물리 키보드 설정·Android IME | 공개 설정/입력기 picker 연결. 전용 전역 IME backend는 미구현 |
| OEM 설정 | 지원 모델별 읽기 전용 검사·snapshot/원복 도구 안내. 새 모델을 지원한다고 표시하지 않음 |
| ADB shell | 별도 PC/무선 디버깅 필요. 입력 주입과 전체 입력 관찰 권한은 다름 |
| Shizuku | 사용자 grant·binder 수명·shell/root UID 및 backend 구현 필요. 현재 안내 이동만 제공 |
| root / `/dev/input` reader | 실제 장치 접근·SELinux·소스별 reader 필요. 현재 기본 앱 backend에 없음 |
| Device Owner / system/OEM 통합 | 관리 기기 provisioning 또는 OS signature/privileged 통합 필요. 홈 역할과 다른 권한 |

접근성을 거부하거나 모션 API/원시 접점이 없는 기기는 앱에 도착한 기본 이동·클릭·스크롤·문자 입력으로 계속 사용한다. 알림·배터리 예외·HOME은 선택 사항이다. 세부 권한 범위와 공식 출처는 [입력·권한 조사](research/android-authority-alternatives.md)에 있다.

## 증거의 경계

VM의 Android GLES 제공자는 ANGLE/SwiftShader이며 물리 GPU 성능 증거가 아니다. software GL 픽셀과 GTK 창 전달도 hardware 3D 합격으로 표시하지 않는다. Vulkan/Venus/직접 KGSL·Mali·libhybris·원격 backend는 위 조건을 실제로 준비해야 하며 APK에서 자동 설치·루팅·권한 부여를 수행하지 않는다. 실기기 Y900은 연결·변경하지 않았다.

게스트 보고서의 `presentationVerified:false`와 `context`의 presentation 제한은 offscreen probe 및 직접 GPU 공유 경로의 검사 범위를 뜻한다. 전체 GUI 표시 불가를 의미하지 않는다. 별도 GTK 검사에서 CPU OpenGL 표시를 확인했다. `mesa-default:blocked`도 미연결 직접 하드웨어 표시 경로의 상태이며, llvmpipe 소프트웨어 경로와 구분한다.

개발 이력의 첫 새 이미지 단독 GL 시험은 desktop 준비 실패, 다음 후보는 GL readback 성공 후 화면 재그리기 실패였다. [초기 준비 실패](validation/2026-10-06-graphics-initial-vm/receipt.json), [재그리기 실패](validation/2026-10-06-graphics-warm-gl-vm/receipt.json), [수정 후보의 실제 색상 전달](validation/2026-10-06-virgl-candidate-gl-vm/receipt.json)를 각각 보존한다. 후보 결과는 최종 전달 APK의 수락을 대신하지 않는다.
