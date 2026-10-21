# Android 내부 창과 Linux Chromium 현재 검증 — 2026-10-08

현재 설치본은 `e6c1337e2e6af540d746e92f458c650fd15baabf736c6ddc7492191a9859a8df`이다.
이 설치본에서 공개 Android 앱의 실제 내부 draw·F12·클릭·스크롤·엄격 resize와 Linux Chromium의 네이티브 Wayland/CDP 검사를 통과했다.
product10–12와 Chromium07–08은 이전 ceffa, product14와 Chromium09는 이전9e의 결과다. 현재 결과에 물려주지 않는다.
공개 합성 Android 앱의 실제 프레임을 Omarchy의 GTK Wayland 창까지 전달한 경로와,
Linux Chromium 자체가 같은 Hyprland 안에 창을 만든 경로를 각각 기록한다.
일반 Android 앱 전체 지원, 정확한 원색, 물리 입력·표시, 60/144fps 수락은 아직 아니다.

## 제품과 보호 상태

새 APK는 arm64/API36, 388,008,623바이트이며 [resize 빌드 영수증](../../build/deliverables/LoopyDesktop-2026-10-08-android-inside-resize-arm64/build-receipt.json)과 [artifact identity](../../build/deliverables/LoopyDesktop-2026-10-08-android-inside-resize-arm64/artifact-identity.json)에 소스·자산·네이티브 선택이 고정돼 있다.
[update08 PASS](../../build/diagnostics/y900-android-inside-product-update-20261008-08/receipt.json)는 데이터 초기화 없는 업데이트와 설치 SHA 일치를 확인했다.
이전 ceffa의 [빌드 영수증](../../build/deliverables/LoopyDesktop-2026-10-08-android-inside-frame-retention-arm64/build-receipt.json)과 [update06](../../build/diagnostics/y900-android-inside-product-update-20261008-06/receipt.json)은 별도 이력으로 유지한다.
현재 설정119개와 zsh/tmux 2개, 총121개의 모든 해시를 보존했다. 기존118개도 그대로다.
서비스·역할·접근성 연결과 마이크 거부 상태를 보존했으며 Chromium의 추가 crash/metrics 파일을 지우거나 검사에서 제외하지 않았다.
[최종 closure](../../build/diagnostics/y900-inside-chromium-current-closure-20261008-01/receipt.json)는 현재 영수증 SHA와 정리 결과를 묶는다. 종료 시점 broker는 UID2000/PID21393/birth75820488로 살아 있고 시험 task/display·fixture·전용 폴더는 모두 제거됐다.

## 실제 Android 프레임의 Wayland 표시

[현재 product18 엄격 resize PASS](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product18/receipt.json)는 실제 GTK960×640/Android1920×1280/density320/epoch4/sequence5와 **같은 geometry/sequence의 Cairo source draw**를 확인했다.
[현재 product19 전체 PASS](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product19/receipt.json)는 GTK appUID10330 → Binder FD → shell21393 → targetUID10362/task200/display27 경로다.
F12 왕복·첫 release 지연 중 정적 프레임 유지, 소유 UHID 클릭1회의 초록 draw, smooth scroll1회의 청록 draw를 통과했다. 실제 trace는 direction FALSE/UP, deltas TRUE/dy=-1.5와 canonical SCROLL1개다.
resize 뒤 GTK960×640/Android1920×1280/density320/epoch4/sequence7의 **해당 sequence7 draw**를 확인했다. 이전 누적 draw 횟수로 대신 판정하지 않았다.
본문 FRAME7개/최종8개와 CLOSED, UHID·target·카탈로그·폴더 정리,121개 상태·서비스·역할·제품 보존을 확인했다. guarded 시험67.409초는 입력 latency가 아니다.
`resize_replay_callbacks=0`이므로 실제 FRAME-before-ACK 순서를 밟은 증거는 없으며 그 순서의 host 모델 검사와 구분한다. 공개 palette 모델 판정이고 물리 presentation/60·144fps는 미검증이다.

아래는 이전 ceffa의 색상 검증 이력이다.
[product10](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product10/receipt.json)은 실제 target task191/display20의 FRAME2개를 받았지만 공개 색상 검사에서 **FAIL**했다.
F12 입력 ACK와 대상 focus/running/visible, CLOSED 및 소유 자원 정리는 확인했으며 실패 원본은 변경하지 않았다.

공개 색상의 기대값과 받은 RGBA 바이트는 다음과 같다.

| 공개 샘플 | 기대 RGB | 수신 RGBA |
|---|---|---|
| nonce | 185,75,100 | 185,67,79,255 |
| 빨강 | 224,32,48 | 224,29,38,255 |
| 노랑 | 224,208,32 | 224,187,25,255 |
| 흰색 | 238,238,238 | 238,214,188,255 |

Java FRAME 작성과 Python decode/copy는 payload를 그대로 복사한다. 공개 샘플 검사는 Pixbuf에서 읽은 색이 아닌 수신 payload 바이트를 읽는다.
따라서 이후 GTK 표시만으로 이 G/B 감소를 설명할 수 없다. 채널별 gain 형태는 의심되지만 캡처·색 공간의 원인이나 Android Nightlight는 확정하지 않았다.
[Java wire](../../android/src/dev/loopy/desktop/AndroidInsideWire.java), [Python wire](../../android/assets/omarchy-bridge/inside_wire.py), [샘플 검사 v3](../../build/diagnostics/android-inside-product-test-source-20261008-01/consumer_probe_v3.py).

후속 [product11](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product11/receipt.json)은 **전체 PASS**다.
실제 공개 앱 task192/display21 → 관리된 GTK 창 → Cairo draw, F12 왕복과 FRAME2개 중 검증된 두 번째 draw1개를 확인했다.
첫 프레임 release를 늦춘 동안 새 정적 프레임을 유지했으며, 최종 CLOSED·대상/폴더 제거·121개 해시·서비스·역할·제품 보존도 통과했다.
이 PASS는 고정 공개 palette 모델(R/G/B gain 약 1/.899/.790)의 판정이다. `public_samples_exact=false`이며 초기 alpha 검사 실패1개도 남아 있다.
진단 모델은 제품 색상 보정이 아니다. 실제 물리 입력과 물리 presentation 검증 필드는 모두 false다.
원래 화면 보호기는 사라졌으므로 `focus_restored=false`, `screensaver_dismissed` 조건 충족을 따로 기록했다.

[product12](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product12/receipt.json)는 실제 공개 클릭 → 초록 프레임 → draw를 통과했으나 스크롤 대기 timeout으로 **전체 FAIL**이다.
최종 accepted actions에 `SCROLL`이 없었고 후속 resize 시험은 실행하지 않았다. 클릭 당시 InputPriority7개 필드는 모두 유효했다.
소유 UHID·임시 파일 제거, canonical CLOSED, 작업공간·포커스 복원 및121개 해시·서비스·역할 보존은 통과했다.
새 APK의 두 GTK 자산은 유효한 scroll deltas를 먼저 정규화한다. GTK3.24.52는 smooth event의 direction 조회에 FALSE/기본 UP, delta 조회에 TRUE를 반환하므로 두 성공값을 구분한다. [고정 GTK 원본](https://raw.githubusercontent.com/GNOME/gtk/3.24.52/gdk/gdkevents.c).
현재 resize 자산은 ACK 전 소유 future frame을 보존해 현재 geometry ACK 뒤 복사한다. 정확한 소스 SHA는 위 artifact identity에 묶여 있다.
[product14 post-review](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product14/post-review.json)는 원래 PASS receipt를 보존하되 draw4/resized sample5 불일치로 엄격 resize draw 미증명을 기록했다.
현재e6의 [15](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product15/receipt.json)/[16](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product16/receipt.json)/[17](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product17/receipt.json) 실패는 각각 public-pointer 단계 AssertionError(세부 원인 미확정), 잘못된 timeout 인자, root Lua resize API 오류다. 일반 앱 실패로 해석하지 않는다.16의 [별도 정리](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product16/root-cleanup.json)도 보존했다.

## Chrome·Notion 지원 경계

[실제 설치된 launcher 메타데이터](../../build/diagnostics/android-inside-installed-target-metadata-20261008-01/receipt.json)에 따르면 Android Chrome은 alias이고 `LAUNCH_SINGLE_INSTANCE_PER_TASK`다.
Notion은 `LAUNCH_SINGLE_TASK`다. 두 앱 모두 현재 직접 standard/no-alias 정책에서 **미지원**이며 이 검사에서 실행하거나 계정 데이터를 읽지 않았다.
기존 기본 화면의 사용자 task를 재사용·이동·캡처·제거하지 않도록 지원 거부를 유지한다. 이 판정은 upstream manifest 추정이 아니다.
Chrome은 alias/실제 target·permission 대조와 새 mode4 task만 소유하는 보수적 확장을 조사할 수 있으나 **미구현·미시험**이다. 기존 task 채택/이동/제거 허용이 아니다.
Notion mode2는 기존 task 재사용·이동의 명시적 소유권 계약이 먼저 필요하며 Linux kernel 제한과 별개다. [Android launch mode 문서](https://developer.android.com/guide/topics/manifest/activity-element#lmode).

## Linux Chromium은 기존 Hyprland에서 실행

[현재 Chromium10](../../build/diagnostics/y900-chromium-inside-public-20261008-10/receipt.json)은 같은e6의 네이티브 Wayland1256×796/PID8131/birth75866710/SID·PGID8131/stableId402653191과 약40초 생존을 확인했다.
새 HOME/XDG/profile·짧은 전용 TMPDIR·공개 offline data HTML만 사용하고 외부 hostname resolver를 NOTFOUND로 제한했다. 기존 계정·extensions·사용자 프로필은 사용하지 않았다.
localhost CDP renderer는 ANGLE → Mesa virgl Adreno830이고 compositing·canvas·WebGL·rasterization은 enabled, video decode/encode는 software, Vulkan은 off였다.
320×240 공개 canvas를3초 warmup 뒤 같은 browser clock으로5.0075초 측정해344 RAF, **68.6969 callbacks/초**를 얻었다. 물리 표시 FPS·GPU 사용률·전체1920×1269 데스크톱60fps 수락이 아니다.
기본 sandbox는 SUID helper FATAL/signal5다. offline `--no-sandbox` phase만 종료 후 exit0/세션 부재를 확인했고 helper는 Singleton link/socket 정리 경계의 `probe_complete=false`/ValueError를 유지했다.
[root cleanup10 PASS](../../build/diagnostics/y900-chromium-inside-public-20261008-10/root-cleanup.json)는 이후 소유 short TMPDIR/profile258개·4,886,872바이트를 no-follow로 제거하고 실제 SID7892/8131 부재를 확인했다. 창·leader 부재와121개 상태·서비스·역할·제품·작업공간/포커스 보존도 확인했다.
CDP 초기 target readiness2회/최종1회 성공을 이전09의 실패 원인으로 소급하지 않는다. 일반 `gpu_verified`·physical presentation 필드는 false로 남으며 CDP 식별과 구분한다.

아래07–08은 이전 ceffa의 별도 결과다.
[Chromium07](../../build/diagnostics/y900-chromium-inside-public-20261008-07/receipt.json)은 `/usr/lib/chromium/chromium`을 직접 실행했다.
ELF SHA는 `8dee915b6acdd643cdb4198666c29c96e5ffec0ba39bd3338be3d49884eddf13`, 크기는325,782,488바이트다.
각 phase의 새 HOME/XDG/profile과 짧은 전용 TMPDIR를 사용했고 기존 사용자 프로필·전역 flags는 사용하지 않았다.
기존 Wayland/GPU 환경을 상속하고 `--ozone-platform=wayland`로 공개 offline data HTML만 열었다. 별도 Android Chrome 실행 경로가 아니다.
기본 sandbox phase는 SUID helper 오류로 signal5 종료했다. offline `--no-sandbox` phase는 약40초 생존했다.
그 phase의 실제 네이티브 Wayland 창은1256×796, PID17191/birth75655284/SID·PGID17191, stableId402653191로 식별됐다.
제목의 정확한 공개 nonce와 ` - Chromium` suffix를 확인했다. 종료 뒤 소유한 창·leader·세션 부재와121개 상태 보존을 확인했다.
프로브 자체는 Singleton 정리 경계에서 `probe_complete=false`/ValueError였다. 이후 [별도 root 정리](../../build/diagnostics/y900-chromium-inside-public-20261008-07/root-cleanup.json)가 세션 부재와 no-follow 소유 폴더 제거를 확인했다.
`gpu_verified=false`, `physical_presentation_verified=false`이며 FPS 결과가 없다. 호스트와 게스트 monotonic clock을 빼서 시작 지연을 계산하지 않는다.

같은 ceffa의 [Chromium08](../../build/diagnostics/y900-chromium-inside-public-20261008-08/receipt.json)은 공개 nonce/localhost CDP 검사를 **통과**했다.
renderer는 `ANGLE (Mesa, virgl (Adreno (TM) 830), OpenGL ES 3.2 Mesa 26.2.4-arch1.1)`이며 GPU compositing·canvas·WebGL은 enabled, video decode/encode는 software였다.
320×240 공개 canvas의 RAF56개/1009.5ms는55.473회/초다. 짧은 JavaScript callback 결과이며 실제 표시 FPS·최소60fps 수락이 아니다.
네이티브 Wayland 창1256×796/PID27818/birth75728067/SID·PGID27818과 약40초 생존,121개 상태 보존을 확인했다.
기본 sandbox abort와 helper `probe_complete=false`는 남아 있다. [root cleanup08](../../build/diagnostics/y900-chromium-inside-public-20261008-08/root-cleanup.json)은 이후 세션 부재와 no-follow 소유 폴더 제거를 확인했다.
이전9e의 [Chromium09](../../build/diagnostics/y900-chromium-inside-public-20261008-09/receipt.json)는 창이 있었으나 CDP target metadata 판정이 실패해 새 RAF/GPU 결과가 없다. 정상40초 process.wait timeout과 구분하며 [root cleanup09](../../build/diagnostics/y900-chromium-inside-public-20261008-09/root-cleanup.json)는 통과했다.

## Sandbox와 대안의 한계

Ozone은 빌드에 포함된 Wayland backend를 런타임 flag로 선택한다. [Chromium Ozone 문서](https://chromium.googlesource.com/chromium/src/+/main/docs/ozone_overview.md).
`--no-sandbox`는 Chromium의 sandbox를 끄는 시험용 옵션이므로 Chromium07–10을 안전한 일상 웹브라우저 수락으로 승격하지 않는다. [Linux sandbox 문서](https://chromium.googlesource.com/chromium/src/+/0b6120702e8f69ce43b34b02903a1d32a0be07d3/docs/linux/sandboxing.md).
이 Y900의 [이전 namespace 실제 대조12개](../../build/diagnostics/y900-namespace-app-20261008-04/receipt.json)는 직접 App UID/기본 PRoot/가속 없는 PRoot 모두 USER namespace에 EINVAL22를 기록했다.
현재 공식 Termux Chromium recipe는 Wayland=false/X11=true이고, Termux 코드 패치는 `--no-sandbox`를 강제로 추가한다. bionic 전환만으로 sandbox 보존·현재 Wayland 호환·성능 개선이 증명되지 않는다.
[공식 build recipe](https://raw.githubusercontent.com/termux/termux-packages/master/x11-packages/chromium/build.sh), [sandbox 패치](https://raw.githubusercontent.com/termux/termux-packages/master/x11-packages/chromium-host-tools/cr-patches/1001-chromium-disable-sandbox.patch).
안전한 Linux 경로는 실제 namespace/권한 helper/seccomp가 가능한 kernel·실행 환경 또는 별도 Linux VM 후보를 검증해야 한다. root/chroot만으로 빠진 kernel 기능을 만들 수 없고 VM 권한·가속·성능도 미검증이다. [chroot의 범위](https://man7.org/linux/man-pages/man2/chroot.2.html).

## 대기 중인 검증과 테스트 범위

현재e6의 product18/19와 Chromium10 결과로 위 공개 범위를 수락한다. 기존 실패와 이전 APK의 성공을 현재 판정으로 바꾸지 않는다.
root 실행에서 현재 canonical inside43개, 진단 resize6개, compile stubs6개가 통과했다. Chromium helper08의 [headless20개](../../build/diagnostics/chromium-inside-public-source-20261008-08/host-verification.json)도 통과했다.
전체 빌드 fixture의 기존 실패는 별개로 남아 있다. 이 문서는 전체 suite GREEN이나 모든 Android 앱·일상 Chromium·60/144fps 완료를 주장하지 않는다.
