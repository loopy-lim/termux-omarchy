# 2026-10-08 현재 mode4 내부 창과 Linux Chromium 검증

현재 설치 APK는 `13b421a9371848d089b85fcfd7cc5891d8e762d6f19f4d3007a45b9795ec1e65`다. 공개 Android mode4 앱의 실제 launcher alias → GTK Wayland 화면·F12·클릭·smooth scroll·resize를 통과했고, 같은 앱의 두 번째 OPEN을 거부하면서 첫 작업과 사용자 Chrome 작업을 보존했다. Linux Chromium은 같은 APK에서 네이티브 Wayland 창과 CDP GPU 경로를 확인했다. 실제 Android Chrome 자체의 내부 실행, 안전한 Linux browser sandbox, 물리 FPS와 전체 Omarchy 수락은 아직 증명하지 않았다.

이 문서는 현재13b 증거다. [이전 e6 보고서](2026-10-08-inside-chromium-current.md)의 product18/19·Chromium10 결과는 해당 APK의 역사로 유지한다.

## 설치본과 소스 결합

[고정 빌드](../../build/deliverables/LoopyDesktop-2026-10-08-android-inside-chrome-mode4-arm64/build-receipt.json)는 API36/arm64-v8a, app388,008,623B와 test `babea8da00fec936b686012e6960e2dbfd9c954d5fca06ac49fa82652c99fe64`를 기록한다. [자산 identity](../../build/deliverables/LoopyDesktop-2026-10-08-android-inside-chrome-mode4-arm64/artifact-identity.json)는 APK의 Guard `d569b2cc…`, Display `201ceab4…`와 기존 scroll/resize 자산을 고정한다. identity의 `device_verified=false`는 빌드 기록이며 실기기 증거는 아래 별도 영수증이다.

[update09](../../build/diagnostics/y900-android-inside-product-update-20261008-09/receipt.json)은 e6→13b update-only 설치를 통과했다. 설정119개+shell2개 전체121개 해시, 역할·서비스·마이크 거부를 보존했다. [host RED](../../build/diagnostics/inside-chrome-mode4-host-20261008-01/red/receipt.json)는 기존 정책의 mode4 거부로 실행 exit1, [GREEN](../../build/diagnostics/inside-chrome-mode4-host-20261008-01/green/receipt.json)은 새 정책의279 assertions 통과를 기록한다. 독립 소스 검토에서 중대한 결함은 보고되지 않았다. 이 결과를 전체 테스트 suite 통과로 확대하지 않는다.

| 영수증 | SHA-256 |
| --- | --- |
| build-receipt | `9a5700d2f850df2ac4f657d7a42f7005a08273eb2611fd6c7469719b1f8b2d8e` |
| artifact-identity | `ec0ff7f64ab43e7213609d7d221a2d12b12591e1ae225427cc91b53d89b6efb3` |
| update09 | `8aca380a581d44d1b98429991d76c6435df95cdd21651dffe25ce3cfd1c499f5` |
| host GREEN | `e4d8706e6a5be01f8164aa2775a7c39372b782df0b943457ce31a2d66398ca36` |
| product21 | `da4f559b9953228a88b816f1d1c56ec905080c540f892706f3e21be1b3be194b` |
| product23 | `29a253944d4704945aaeb61cbf1956799c586d3efa76228e85e8891dbbbdb177` |
| Chromium11 | `616155e6be00e48da5e17587be24bd72fa7da4f57b1dd5d00534dff5d07262d3` |
| Chromium11 root-cleanup | `b36d0ef9330b00dc0bef60410f6dc0c7577330bef5ff816017cd8d693fe58af1` |

## mode4 별칭의 실제 실행과 작업 보호

[product21](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product21/receipt.json)은 `dev.loopy.synthetic.insidemodefour`의 exported launcher AliasActivity를 통해 nonexported ProductActivity(mode4/doc0)를 실행했다. 새 task203/display29/UID10364의 baseIntent·origActivity는 AliasActivity, realActivity·top은 ProductActivity였다. 실제 GTK draw·F12/정적 프레임 유지·UHID 클릭 초록 draw·SCROLL1회 청록 draw와 GTK960×640/Android1920×1280/density320/epoch4/sequence7의 정확한 Cairo draw를 확인했다. 공개 픽셀은 tint gain 모델로 검증했으며 raw exact=false다. draw는 물리 presentation 증거가 아니다.

[product23](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product23/receipt.json)은 첫 소유 task205/display31/UID10366이 살아 있는 동안 별도 GTK 연결의 같은 alias OPEN을 wire code5(TARGET_UNAVAILABLE)로 거부했다. broker의 고정 실패 로그에서 원인 TASK_CONFLICT를 확인했다. 두 번째 연결에는 OPENED/FRAME이나 새 task가 없었고, 첫 작업과 사용자 Chrome task131/display0의 메타데이터가 그대로였다. 두 번째 창·scope 정리와 첫 창 재포커스를 확인한 뒤 부모의 canonical CLOSED와 task/display·공개 fixture·catalog·metadata helper·scope 정리를 확인했다. 두 실행 모두121개 해시·역할·서비스를 보존했다.

새 정책은 direct standard/doc0 또는 제한된 mode4/doc0|3을 받는다. alias는 원래 launcher의 exported/permission 경계로 실행하며, 현재 PM의 실제 activity가 같은 APK/package/UID이고 enabled이며 alias chain이 없어야 한다. start 전 PM/전체 작업 snapshot을 다시 확인하고 모든 기존 task ID를 보존한다. 같은 UID/package의 기존 작업이 있으면 거부하며 START_SUCCESS 뒤의 새 소유 task만 채택·제거한다. 실제 시험은 mode4/doc0 공개 앱의 범위다.

[broker 메타데이터](../../build/diagnostics/inside-chrome-mode4-host-20261008-01/broker-failure-metadata.json)는 현재 APK에 묶인 UID2000/PID31423/birth76003818과 두 개의 고정 `target-TASK_CONFLICT` 실패를 기록한다. 살아 있는 broker만으로 모든 backend 기능·재부팅 복구를 증명하지 않는다.

## 실제 Chrome과 Notion의 남은 경계

현재 PM에서 Chrome alias와 실제 activity는 모두 mode4/doc0이고 같은 `com.android.chrome` APK다. 실제 class의 `org.chromium` 접두사는 APK package와 구분한다. 정책 확장은 구현됐지만 기존 사용자 Chrome task131/display0과의 충돌 때문에 실제 Chrome 자체는 실행하지 않았다. 그 작업을 옮기거나 제거하지 않았다. Notion mode2(singleTask)는 계속 거부하며, 재사용/이동 작업의 명시적 소유권 계약이 필요하다. 이는 Linux namespace/kernel 문제와 별개다.

## 현재 APK의 Linux Chromium

[Chromium11](../../build/diagnostics/y900-chromium-inside-public-20261008-11/receipt.json)은 사용자 프로필과 분리한 공개 offline/no-sandbox 프로필이다. 실제 Ozone Wayland 창1256×796, PID/SID/PGID5651·birth76054191·stableId402653193을 확인했다. host가 창을 관찰한 구간은34.47145초, 프로세스 자체 시계의 실행은40.104514초이며 두 시계를 합쳐 표시 latency를 추론하지 않는다.

offline phase의 `cdp_passed=true`에서 ANGLE→Mesa virgl Adreno830/Mesa26.2.4와 GPU compositing·canvas·rasterization·WebGL enabled를 확인했다. video decode/encode는 software, Vulkan은 off였다. 320×240 canvas의 약3초 warmup 뒤5,006.1ms에340 RAF, **67.917141 callbacks/초**를 기록했다. 물리 FPS·GPU 사용률·전체 화면60/144fps·일상 웹 성능의 증거는 아니다.

기본 sandbox phase는 SUID helper FATAL/exit-5였다. 원래 영수증의 `probe_complete=false`, `error_class=ValueError`, 상위 `gpu_verified=false`를 유지한다. 별도 phase의 CDP GPU witness와 전체 helper 완료 여부를 합치지 않는다. [root-cleanup11](../../build/diagnostics/y900-chromium-inside-public-20261008-11/root-cleanup.json)은 Android ps에서 세션5464/5651 부재와 nofollow258개 항목/4,886,916B의 소유 profile·scope·짧은 TMPDIR 제거를 확인했다. 원래 실패 영수증은 수정하지 않았다. 창·leader 부재,121개 상태·역할·서비스 보존과 focus 복귀는 Chromium11 본문 영수증에 별도로 기록돼 있다.

## 보존한 실패와 제품 목표

[product20](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product20/receipt.json)은 F12 앞에 metadata helper를 넣은 진단에서 retention safety-timeout, [product22](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product22/receipt.json)는 문자열 오류를 기다렸지만 실제 wire가 숫자5를 보낸 진단 실패다. 두 영수증은 FAIL 그대로이며 canonical CLOSED·소유 정리와 사용자 작업/121개 상태 보존을 기록한다. 이후 성공으로 이전 실패를 고치거나 일반 앱 실패 원인을 소급하지 않는다.

현재 권한 backend는 [명시적 세션 ADB bootstrap](../../dev/android-inside-host)이다. 앱 listener의 수명과 caller-visible HOST_UNAVAILABLE 처리는 존재하지만 자동 권한 획득·Shizuku·ADB 분리/재부팅 뒤 재활성화와 종단 backend readiness는 별도 제품 작업이다. broker_alive를 Binder handoff/launch/frame/input 전체 readiness로 표시하지 않는다. Linux sandbox를 보존한 실행 환경, 실제 지원 앱·장시간 입력/복구, 정확한 색과 물리 성능을 확인해야 하므로 전체 목표는 계속 진행 중이다.

[현재 closure](../../build/diagnostics/y900-chrome-mode4-current-closure-20261008-01/receipt.json)(SHA `204af4eb77d4b6818c0e4b15759f556a3002464600859054d487836b139bc2cb`)는 설치13b·현재 앱 PID/birth·UID2000 broker PID/birth를 다시 대조하고 현재 세션의 내부 display, 공개 fixture와 metadata helper 부재를 확인했다. Chrome131/display0의 현재 metadata도 보존됐다. Linux 공개 Chromium의 소유 정리는 별도 root-cleanup11에 결합하며 일반 웹 sandbox·물리 FPS·재부팅 backend·전체 Omarchy 수락은 false로 유지한다.
