# Android 앱의 실제 화면을 Omarchy 창에 연결하기

사용자의 전체 Omarchy 지원 요청과 실제 앱을 내부 창에 표시하려는 요청을 구현한다. 이전0589는 외부 Android task를 여는 제품이며, 별도 inside16은 공개 시험 앱의 실제 픽셀·고정 클릭/F12·3개의 draw ACK와 시험 터미널 복귀를 통과했다. 지속 프레임·일반 입력·Notion/Chrome 제품 지원의 증거는 아니다.

현재 설치본은 `13b421a9371848d089b85fcfd7cc5891d8e762d6f19f4d3007a45b9795ec1e65`다. mode4/doc0 공개 앱의 실제 launcher alias → GTK Wayland draw·F12·클릭·smooth scroll·엄격 resize와 소유 정리를 통과했고, 같은 앱의 두 번째 OPEN은 wire5(TARGET_UNAVAILABLE)로 거부했다. broker의 TASK_CONFLICT 로그와 첫 작업·사용자 Chrome task131/display0 보존을 확인했다. Linux Chromium의 네이티브 Wayland/CDP GPU 경로도 같은 APK에서 확인했으나 offline no-sandbox 진단이며 전체 helper는 완료되지 않았다. 실제 Android Chrome 자체·Notion·일상 browser sandbox·정확한 원색·물리60/144fps·일반 앱 전체 지원은 남아 있다. [현재 mode4 검증 보고서](../../validation/2026-10-08-chrome-mode4-current.md). 이전e6의 [검증 보고서](../../validation/2026-10-08-inside-chromium-current.md)는 역사로 보존한다.

제품 경로는 설치 앱의 현재 PM component/UID catalog → 실제 GTK Wayland 창 → 같은 appUID의 연결 허브 → Binder로 전달한 연결 FD → 승인된 UID2000 shell broker → 창이 소유한 Android VirtualDisplay/task다. 일반 앱 권한만으로 임의 앱을 호스팅할 수 있다고 표시하지 않는다. 이번 연결은 ADB로 시작하며 재부팅 후 연결 복구와 Shizuku 통합은 별도 요구다.

broker는 실제 SO_PEERCRED와 PID/birth로 현재 appUID 클라이언트를 확인하고, 현재 session/stamp와 순차 명령만 받는다. component는 shell의 현재 PM에서 exported/enabled MAIN/LAUNCHER와 host가 받을 수 있는 activity permission을 대조한다. 자기 앱·Shell·다른 사용자·현재 task/display와 다른 입력은 거부한다. display0 입력이나 전역 fallback은 없다.

태블릿 실측에서 appUID는 shell의 `/proc/PID/stat`과 디렉터리를 읽을 수 없었다. viewer는 연결된 같은 소켓 FD의 커널 SO_PEERCRED appUID/현재 appPID와 fstat identity를 확인한다. HELLO의 양수 shell birth/generation은 Binder 인증 GRANT에 묶인 연결 메타데이터이며, viewer가 `/proc`에서 독립 확인한 증거로 표시하지 않는다. 새 연결은 새 FD/peer/GRANT/HELLO/task lease를 요구하며 이전 프레임이나 입력을 재생하지 않는다.

후속 실측에서 untrusted_app→shell(transport02), shell→untrusted_app(reverse02) 모두 connect 권한 오류가 확인됐다. 최종 viewer는 같은 UID의 실제 Android 앱 PID(LOOPY_ANDROID_PID)와 소켓 FD를 확인한다. 앱 허브는 ContentProvider의 실제 Binder calling UID2000/PID를 검증한 뒤 GRANT를 그 연결에 먼저 쓰고, accepted FD를 shell에 전달한다. HELLO는 이 GRANT의 shell PID/birth/generation과 일치해야 한다. 소켓 peer가 shell UID라는 이전 설계는 이 경로에 적용하지 않는다. FD 반환은 원본 close만 사용하며 shared endpoint shutdown으로 전달한 연결을 끊지 않는다. 과거723426 APK의 공개 시험은 실제 untrusted_app GTK → AppHub → Binder FD → UID2000 broker → 전용 display/task의 OPENED까지 통과했으나 화면 포커스 판정 실패로 프레임 표시에는 도달하지 못했다. 그 실패 이력은 보존하며 현재e6의 실제 화면 검증과 합치지 않는다.

실제 앱 화면은 ImageReader의 최신 RGBA를 메모리와 socket으로 전달한다. 내용·일반 키 입력·스크린샷은 진단 파일에 저장하지 않는다. 프레임은 창/task/display/generation/geometry/sequence에 묶이며 한 payload만 in-flight로 유지한다. viewer가 자기 저장소에 복사하거나 실제 buffer를 반환한 뒤에만 retirement ACK를 보낸다. draw callback은 물리 presentation이나60/144fps 증거가 아니다.

전체 키 중 안전하게 Android에 매핑한 evdev 키만 광고하고, repeat·modifier·5개 버튼·포인터·스크롤을 처리한다. focus·resize·close·EOF에서 held 입력과 payload 수명을 보존한다. 다른 UID의 Android chooser 등은 명시적 제한으로 남기며 일반 앱 전체 지원으로 확대하지 않는다.

런처의 주 Android 항목은 inside_window이며 별도 화면 경로를 명시적으로 유지한다. native Android 제어 메뉴도 Omarchy에서는 내부 창을 요청하고, 화면 고정 중에도 내부 실행은 가능해야 한다. 오류 시 내부 창에서 복구 상태를 표시하며 자동 외부 전환은 없다. 사용자 HOME·KeyBridge·역할·마이크 거부·기존 세션은 보존한다.

검증은 실제 source/host tests, SDK compile/APK package, 실제 AppUID Wayland +UID2000broker 공개 target 왕복, EOF/resize/focus/cleanup, ADB 분리 지속성, 실제 지원 앱과 물리 입력·성능을 각각 구분한다. 모든 Omarchy 지원이라는 전체 목표는 이 연결만으로 완료되지 않는다.


## 2026-10-08 포커스와 기존 작업 보호 보강

Y900 공개 시험 product04/05에서 전용 display의 실제 mCurrentFocus는 시험 앱인데 TaskInfo.isFocused는 false였다. product07(1575779 APK)은 Binder의 OPENED까지 통과했으나 UiAutomation observer로 포커스를 확인하지 못해 프레임을 전달하지 않았다. Android16 AccessibilityManagerService는 SystemUI 소유가 아닌 private virtual display를 접근성 display 목록에서 제외한다. 이 observer는 실제 제품 경로에서 제거했다. [Android16 기본 구현](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android16-release/services/accessibility/java/com/android/server/accessibility/AccessibilityManagerService.java)

새 shell observer는 WindowInfosListener에서 자기 display에 속한 실제 IWindow token/UID/PID/type/geometry 메타데이터만 보존한다. 실제 Loopy 앱의 기존 WindowSession을 통해 해당 IWindowId의 focused boolean을 확인한다. 앱 target36에서 두 내부 메서드의 reflection 제한이 있으므로, 공개 IBinder/Parcel과 실제 기기에서 확인한 transaction24/3을 사용한다. descriptor, 타입, 남은 응답 바이트를 검증하고 Binder identity를 복구한다. 실제 FD ACK에서 생성된 capability/session/UID/PID/birth/generation/token을 확인하며 최대8개, 만료, 명시적 해제를 적용한다. shell의 실제 Stub 코드가24/3과 다르면 거부한다. 전역 hidden_api_policy는 변경하지 않았다. 이 경로의 동기 Binder 호출 전체에는 로컬 강제 취소 보장이 없다.

관찰 전후로 실제 task 소유권과 display/UID를 다시 확인한다. token·snapshot·geometry가 달라지면 포커스를 인정하지 않는다. default display·외부 UID·시스템 창·중복 토큰·여러 포커스 창은 거부한다. 노드·텍스트·일반 접근성 이벤트·스크린샷은 읽지 않는다. ca6080 APK는 소스·SDK·패키징과 업데이트 보존 검증을 통과했으며, 실제 화면·입력은 product08 이후의 별도 영수증으로 판단한다.

단일 작업 재사용·document·alias·task reparenting launch는 기존 Android 작업을 이동시키거나 종료할 수 있다. 현재 내부 실행은 direct standard/doc0 또는 제한된 mode4/doc0|3을 허용한다. mode4 alias는 원래 launcher의 exported/permission 경계와 Intent를 유지하고, 현재 PM의 실제 activity가 같은 APK/package/UID·enabled·alias chain 없음인지 대조한다. 실제 activity의 class 접두사를 APK package로 오인하지 않는다. shell의 REAL_GET_TASKS 권한과 전체 display snapshot을 먼저 확인하고 같은 UID/package의 기존 작업은 모두 거부한다. start 바로 전에 PM/작업을 재검사하고 두 snapshot의 기존 task ID를 보존한다. START_SUCCESS 이후의 새 task에만 소유권을 부여하며 alias의 baseIntent·origActivity와 실제 realActivity를 계속 대조한다. cleanup이 소유권을 새로 얻거나 사용자 작업을 이동·제거하지 않는다. 조건이 맞지 않으면 내부 창에 복구 오류를 표시하고 외부 실행으로 자동 전환하지 않는다.

PM/작업 조회와 start는 Android의 원자적 작업이 아니다. 임의 대상 앱이 이후 다른 앱을 자체 실행하는 동작까지 일반 host가 제약할 수 있다는 뜻도 아니다. Notion/Chrome의 기존 사용자 작업을 옮기는 시험은 하지 않았다. 새 source 테스트 통과는 새 APK의 실제 화면·입력 통과와 별개다.

## 이전 e6 제품의 scroll·resize 수락

이전e6의 [resize 빌드](../../../build/deliverables/LoopyDesktop-2026-10-08-android-inside-resize-arm64/build-receipt.json)와 [자산 identity](../../../build/deliverables/LoopyDesktop-2026-10-08-android-inside-resize-arm64/artifact-identity.json)는 inside_window `068d925f…`와 inside_input `1cd6b008…`를 고정한다. [update08](../../../build/diagnostics/y900-android-inside-product-update-20261008-08/receipt.json)은 당시 update-only 설치와 설정119+shell2 전체121개 해시·서비스·역할·마이크 거부를 보존했다.

smooth scroll은 direction 조회의 FALSE/기본 UP을 방향 성공으로 취급하지 않고 성공한 deltas를 먼저 정규화한다. resize에서는 미래 geometry의 소유 프레임을 ACK까지 보존하고, ACK가 그 geometry를 확정한 뒤 복사한다. 프레임 retirement는 원래 lease/geometry/sequence에 묶으며 다른 세대의 ACK로 해제하지 않는다. [GTK3.24.52 원본](https://raw.githubusercontent.com/GNOME/gtk/3.24.52/gdk/gdkevents.c).

[product18](../../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product18/receipt.json)은 GTK960×640/Android1920×1280/density320/epoch4/sequence5의 정확한 새 Cairo source draw를 통과했다. [product19](../../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product19/receipt.json)는 같은 제품에서 F12/정적 프레임 유지·UHID 클릭1회 초록 draw·smooth SCROLL1회 청록 draw·새 epoch4/sequence7 resize draw를 통과했다. 최종 FRAME8개/CLOSED와 UHID·task/display·fixture·카탈로그·전용 폴더 정리 및121개 상태 보존을 확인했다.

두 실행의 `resize_replay_callbacks=0`은 실제 FRAME-before-ACK replay 순서를 증명하지 않는다. 해당 순서는 host 모델 검사와 구분한다. product19의67.409초는 전체 보호 검사 시간이며 입력 latency가 아니다. 공개 palette는 고정 gain 모델이고 raw exact=false다. 실제 source-bound draw와 물리 presentation·장시간 하드웨어 입력·60/144fps를 구분한다. [최종 closure](../../../build/diagnostics/y900-inside-chromium-current-closure-20261008-01/receipt.json).

product14의 원래 PASS는 [후속 검토](../../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product14/post-review.json)에서 새 resize sequence draw 미증명으로 제한됐다. product15의 public-pointer AssertionError는 세부 원인이 미확정이며16/17의 잘못된 인자·Lua API 진단 실패와 정리 기록도 보존한다. 새18/19의 성공으로 이전 영수증을 고치거나 일반 앱 실패 원인을 소급하지 않는다.

## 일반 앱과 브라우저의 다음 경계

[현재 mode4 빌드](../../../build/deliverables/LoopyDesktop-2026-10-08-android-inside-chrome-mode4-arm64/build-receipt.json)(SHA`9a5700d2f850df2ac4f657d7a42f7005a08273eb2611fd6c7469719b1f8b2d8e`)와 [identity](../../../build/deliverables/LoopyDesktop-2026-10-08-android-inside-chrome-mode4-arm64/artifact-identity.json)는 Guard `d569b2cc…`/Display `201ceab4…`를 고정한다. [host RED](../../../build/diagnostics/inside-chrome-mode4-host-20261008-01/red/receipt.json)→[GREEN279](../../../build/diagnostics/inside-chrome-mode4-host-20261008-01/green/receipt.json), 독립 소스 검토와 [update09](../../../build/diagnostics/y900-android-inside-product-update-20261008-09/receipt.json)의121개 해시·역할·서비스·마이크 거부 보존을 구분해 기록한다.

[product21](../../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product21/receipt.json)은 nonexported real activity의 mode4/doc0 공개 launcher alias를 통해 새 task203/display29를 소유했다. 실제 baseIntent/orig은 alias, real/top은 실제 target이었고 F12·클릭·SCROLL·GTK960×640/Android1920×1280/epoch4/sequence7 Cairo draw와 CLOSED 정리를 통과했다. [product23](../../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product23/receipt.json)은 살아 있는 첫 task205/display31과 같은 앱의 두 번째 OPEN을 numeric5로 OPENED/FRAME 전에 거부했다. 두 번째 자원 부재·첫 창 재포커스·부모 CLOSED·fixture/catalog/helper/scope 정리와121개 상태를 확인했다. 원색 exact나 물리 presentation 수락으로 확대하지 않는다.

실제 Chrome alias와 실제 activity는 mode4/doc0, 같은 `com.android.chrome` APK이며 real class는 `org.chromium` 접두사다. 확장은 구현됐으나 사용자 Chrome task131/display0과 충돌하므로 실제 Chrome 자체는 실행하지 않았고 해당 작업은 보존했다. Notion mode2(singleTask)는 계속 거부하며 재사용/이동 작업의 명시적 소유권 계약이 필요하다. 이 제한은 Linux kernel과 별개다. [현재 PM/작업 증거](../../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product21/receipt.json).

Linux Chromium은 Android 앱 호스팅과 독립적으로 기존 Hyprland/Ozone Wayland에서 실행된다. [현재13b Chromium11](../../../build/diagnostics/y900-chromium-inside-public-20261008-11/receipt.json)은 공개 offline/no-sandbox 창1256×796·프로세스40.104514초와 CDP ANGLE→Mesa virgl Adreno830/Mesa26.2.4를 확인했다. canvas/compositing/rasterization/WebGL은 enabled, video는 software, Vulkan은 off다. 약3초 warmup 뒤5,006.1ms의340 RAF는67.917141 callbacks/초이며 물리 FPS·GPU 사용률이 아니다. 원래 상위 gpu_verified=false/probe_complete=false와 기본 SUID sandbox FATAL/exit-5를 유지한다. [별도 root-cleanup11](../../../build/diagnostics/y900-chromium-inside-public-20261008-11/root-cleanup.json)은 실제 세션5464/5651 부재와 nofollow258개 항목/4,886,916B 정리를 확인했다. 과거e6 Chromium10의 GPU/RAF 결과는 해당 역사에 남긴다.

[product20](../../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product20/receipt.json)의 metadata 진단 삽입 뒤 retention safety-timeout과 [product22](../../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product22/receipt.json)의 문자열 기대/실제 numeric5 불일치는 FAIL 및 성공한 소유 정리 그대로 보존한다. 실제 앱의 일반 실패로 소급하지 않는다. [broker 고정 실패 메타데이터](../../../build/diagnostics/inside-chrome-mode4-host-20261008-01/broker-failure-metadata.json)는 현재 UID2000/PID31423/birth76003818과 TASK_CONFLICT 두 건을 기록한다.

권한 backend는 현재 [명시적 세션 ADB bootstrap](../../../dev/android-inside-host)이며 [현재 closure](../../../build/diagnostics/y900-chrome-mode4-current-closure-20261008-01/receipt.json)는 broker의 실제 UID/PID/birth와 현재 설치본·앱을 다시 대조했다. 자동 권한 backend·Shizuku·ADB 분리/재부팅 복구·종단 readiness는 별도 제품 작업이고, broker 생존을 Binder handoff/launch/frame/input 성공으로 표시하지 않는다. 안전한 Linux 브라우저는 실제 namespace/helper/seccomp 지원 환경 또는 Linux VM의 권한·가속·화면 연결을 검증해야 한다. root/chroot만으로 빠진 kernel 기능을 만들 수 없다. 과거 조사한 Termux 패키지를 현재 sandbox/Wayland 수락으로 승격하지 않는다. 실제 지원 앱·장시간 복구/입력·색·물리 성능과 전체 Omarchy 목표는 계속 진행 중이다.

변경 없는 canonical inside43개·진단 resize6개·compile stubs6개와 [Chromium helper08 headless20개](../../../build/diagnostics/chromium-inside-public-source-20261008-08/host-verification.json)는 이전 root 실행에서 통과했다. 이번 변경의 새 host 검증은 위 GREEN279다. 각 소스/host 검사를 전체 build fixture GREEN이나 모든 Omarchy 완료로 확대하지 않는다.
