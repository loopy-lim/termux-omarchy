# 현재 태블릿의 내부 Linux 브라우저 후보

2026-10-08, Y900/TB522FU의 현재 설치 APK는 `ae2c3c281f2d8133ed14260bd26044a4e6c5c8f70d6fc642bbeb30d8a6be40fc`다. [388,070,645 B ARM64 빌드 receipt](../../build/deliverables/LoopyDesktop-2026-10-08-chromium-inside-default-arm64/build-receipt.json)와 [update14](../../build/diagnostics/y900-android-inside-product-update-20261008-14/receipt.json)를 확인했다. 현재 ae2의 [Android Chromium 공개11](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-11/receipt.json)과 [일반 menu·Apps 경로01](../../build/diagnostics/y900-chromium-normal-routes-20261008-01/receipt.json)이 제한된 실제 내부 기능·정리를 통과했다. 일반 Linux Chromium·Firefox 사용 가능이나 입력 성능·물리 FPS 합격은 아니다. 아래 f010 및 [Notion 검증](2026-10-08-notion-inside-current.md)은 당시 APK 범위로 유지한다.

## 이전 f010 Linux Chromium 실패와 공개 재현

사용자 실행 뒤 [읽기 전용 확인](../../build/diagnostics/y900-user-chromium-failure-20261008-01/receipt.json)에서는 Chromium 프로세스·브라우저 창·target task가 없었다. [HTTP·HTTPS·HTML MIME handler](../../build/diagnostics/y900-user-chromium-failure-20261008-01/route.json)는 모두 `chromium.desktop`이다. 별도 Android `org.chromium.chrome` 내부 창의 공개 기능 시험09를 이 Linux 경로의 성공으로 옮기지 않는다.

[f010 공개 재현03](../../build/diagnostics/y900-browser-native-public-20261008-03/receipt.json)은 sandbox 해제 없이 native startup 안내 창에서 `PENDING` → `SUID_SANDBOX` 오류를 관찰했다. 영수증의 `passed=true`는 오류 안내와 소유 프로세스·창·scope 정리 및 환경 보존의 합격이며 **Linux Chromium 웹 사용 합격이 아니다**. 창1256×796은 startup 안내 창이고 물리 입력·presentation은 미검증이다. 작업공간 복귀는 확인했으며 `focus_restored=false`/`screensaver_dismissed`를 별도로 유지한다.

[설정 drift](../../build/diagnostics/y900-user-chromium-failure-20261008-01/configuration-drift.json)는 기존119개가 byte 동일한 상태에서 BrowserMetrics1개와 Crash Reports2개만 추가된122개다. 이3개의 내용은 읽지 않고 보존했다. 재현03은 현재122개 설정과 shell2개, 총124개 해시·역할·입력 서비스·f010 APK를 보존했다. 아래 Firefox 및 Android 시험의121개는 과거 영수증 기준이다.

## ae2에 포함한 경로와 검증 상태

새 [plain Chromium route](../../android/assets/omarchy-bridge/browser_inside_route.py)는 빈 기본 Chromium 호출만 현재 catalog의 Android Chromium 내부 창으로 연결한다. 정확한 stock [gtk-launch chromium.desktop](../../android/assets/omarchy-bridge/browser_desktop_launch.py) 경로도 같은 조건을 사용한다. URL·추가 인자·사용자 지정 프로필 또는 Linux sandbox 해결을 포함하지 않는다. View의 초기 실제 geometry 대기와 [SendGuard](../../build/diagnostics/android-inside-send-guard-source-20261008-01/source-receipt.json)를 포함한 ae2는 빌드·update-only 설치를 마쳤다. [ROOT 호스트121 tests](../../build/diagnostics/browser-route-final-host-tests-20261008-01/receipt.json)는 실패·오류·skip0이며 ROOT ZIP 확인에서 assets5개 일치·native7개 불변을 확인했다. [guard GREEN](../../build/diagnostics/android-inside-send-guard-green-20261008-01/receipt.json)의106 assertions는 pure 동작 검증으로, 입력 지연·전송 FPS 합격이 아니다.

update14는 현재124개 설정·shell 해시와 입력 서비스·HOME/ASSISTANT/BROWSER 역할·microphone 거부 및 업데이트 동안 global Shizuku14779의 lifetime을 보존했다. [ae2 공개10](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-10/receipt.json)은 GRANT0·OPENED0·FRAME0·Session OPEN 미관찰 상태에서 timeout으로 실패했다. 당시 native panel은 BIND_TIMEOUT/소유 backend 부재였고 원래 정리 오류도 실패로 남겼다. [별도 retirement](../../build/diagnostics/y900-android-chromium-public10-retirement-20261008-01/receipt.json)는 소유 PID 부재와 scope 제거만 통과했다. OPEN/CLOSED나 기능 성공을 증명하지 않는다.

[후속 broker-start01](../../build/diagnostics/y900-chromium-broker-start-20261008-01/receipt.json)은 UserService32375/child32396 RUNNING을 확인했다. global Shizuku는 이후 관찰에서31382로 교체됐고 원인은 미확인이다. ROOT의 global 재시작은 없었다. 후속 공개11의 성공을 이전 공개10의 원인 확정이나 영수증 변경에 사용하지 않는다.

[ae2 공개11](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-11/receipt.json)은 org UID10372 task235/display48의 처음 보낸 OPEN·OPENED부터 기능 본문·종료까지2512×1592/density320/epoch1이었다. loaded·ready·click·key 각1회, 고정 HTTPS opaque fetch, ANGLE/Qualcomm Vulkan/Adreno830 WebGL을 확인했다. rAF303회/5016.6ms는 JS callback 표본으로 물리 FPS가 아니다. 최종 CLOSED1개·task/display/input 정리3개와 actor/scope/jar/reverse/HTTP 종료·124개 파일 및 역할·서비스·APK 보존을 통과했다. 공개 nonce 문서의 release ACK와 about:blank 전환만 수행했으며 일반 탭·URL을 지우지 않았다.

합성 NAVIGATE56 ACK는59.341초, 클릭2 ACK는2.152초, 키2 ACK는1.710초였다. 이전 f010 시험09의63.260/1.311/1.490초와 비교해 명확한 개선을 주장하지 않는다. 물리 GTK 입력과 장치를 거치지 않은 진단 명령 완료 시간이며, Cairo 관찰은 source-selected로 paint/물리 presentation 합격이 아니다.

[일반 경로01](../../build/diagnostics/y900-chromium-normal-routes-20261008-01/receipt.json)도 menu wrapper3.292초/task236/display49와 Apps `loopy-app-launch` → `gtk-launch chromium.desktop`3.268초/task237/display50에 실제 native GTK 소유 창·ChromeTabbedActivity 내부 task를 확인했다. 양쪽 소유 창/task를 제거하고124개 파일·역할·서비스·APK·기존 task와 source/binary를 보존했다. fixture 없는 일상 브라우징·로그인·일반 사이트·물리60/144fps를 검증한 결과는 아니다. [상세 현재 결과](2026-10-08-android-chromium-inside-current.md).

추가 [일반 사용자 창01](../../build/diagnostics/y900-chromium-user-ready-20261008-01/receipt.json)은 현재 ae2의 normal Omarchy wrapper로 진단 marker·환경·workspace 없이 실제 내부 창을 열고 사용자용으로 의도적으로 유지했으며, metadata jar만 제거하고124개 해시·서비스·역할·APK를 보존했다.

## f010의 실제 Firefox 157.0.1 시험

[공식 Arch Linux ARM Firefox](https://archlinuxarm.org/packages/aarch64/firefox) `157.0.1-1`의 71,849,756 B 패키지는 [다운로드 영수증](../../build/diagnostics/firefox-stock-sandbox-candidate-20261008-02/download-receipt.json)에서 SHA-256 `d142fdb8a339a65eca7cea6a2bba5b29202386166abd9d59851d6757c9eb2163`과 서명을 확인했다. 제품에 설치하거나 기본 브라우저를 변경하지 않았다.

[실제 Firefox01](../../build/diagnostics/y900-firefox-native-public-20261008-01/receipt.json)은 현재 production Hyprland/PRoot의 앱 UID10330에서 새 임시 HOME·프로필·캐시와 공개 오프라인 파일을 사용했다. sandbox 해제 flag·환경·preference를 추가하지 않았다. 창 제목은 이 공개 파일의 nonce만 사용하며 사용자 브라우저 프로필·탭·내용은 기록하지 않았다.

| 확인 | 결과 |
| --- | --- |
| 실행 파일 및 의존성의 첫 gate | `--version`이 종료 코드0과 `Mozilla Firefox 157.0.1`을 반환했다. |
| 실제 GUI 시험 | 30초 동안 browser 프로세스는 살아 있었으나 공개 페이지 제목의 native Wayland 창은 관찰하지 못했다. 정상 웹 사용 합격이 아니다. |
| 실제 오류 | [분류한 공개 진단](../../build/diagnostics/y900-firefox-failure-metadata-20261008-01/stderr-classification.json)에 `Shared memory PlatformHandle is not safe to map` 및 `/dev` sandbox 접근 오류가 반복됐다. shared-memory 생성·전달·자식 filter 중 정확한 원인은 아직 미확인이다. |
| 자식 격리 | browser와 probe는 `Seccomp_filters=2`, 관찰한 socket 프로세스는3이었다. 정상 content 역할의 추가 filter는 확인하지 못했다. `sandbox_policy_verified=false`를 유지한다. 상속한 Android filter를 Firefox content 보호 합격으로 인정하지 않는다. |
| 소유 프로세스 종료 | retained Process wait, 실제 version/gui SID 부재, 모든 관찰 child PID/birth 부재, 실제 root probe 부재를 확인했다. |
| 임시 파일 정리 | 첫 root 정리 호출은 guest UID를0으로 잘못 가정해 거부됐다. [읽기 전용 inventory](../../build/diagnostics/y900-firefox-failure-metadata-20261008-01/tree-inventory.json)는 실제 guest UID10330을 확인했다. [별도 복구 영수증](../../build/diagnostics/y900-firefox-cleanup-recovery-20261008-01/receipt.json)은 같은 봉인 helper에 정확한 UID를 전달해154 entries·389,141,108 B를 nofollow로 제거했다. 원래 실패 영수증은 보존했다. |
| 사용자 환경 | 두 영수증은 현재121개 설정·shell 파일, Android 역할·입력 서비스·설치 APK 보존을 확인했다. 처음 시험은 기존 작업공간도 복구했다. production 소스 변경 및 Linux 재시작은 없었다. |

`complete=true`는 제한된 실행·소유 프로세스 종료 절차 완료를 의미한다. 첫 root receipt의 `passed=false`는 임시 파일 정리 실패를 포함한다. 별도 recovery의 `passed=true`는 그 정리와 환경 보존의 합격이며, Firefox 창·sandbox·GPU·60/144fps 합격은 아니다. 같은 브라우저 시험을 다시 돌려 합격 숫자로 바꾸지 않았다.

## Chromium과 다음 구현 경계

Linux Chromium의 default sandbox 종료와 제한된 오프라인 출력 진단은 [이전 e76 보고](2026-10-08-inside-browser-startup-current.md)에 묶여 있다. 그 native Wayland/GPU callback 결과를 현재 f010의 실측 GPU·화면 FPS 합격으로 옮기지 않는다. 현재 커널 namespace/SUID 제약에서 일반 웹 실행 경로는 여전히 남아 있다. [Chromium Linux sandbox](https://chromium.googlesource.com/chromium/src/+/main/sandbox/linux/README.md)

Firefox는 새로운 구체 실패 조건이 확인됐으므로 다음 gate를 공유 메모리로 좁힌다. 실제 앱 컨텍스트의 native와 같은 PRoot에서 공개4KiB FD의 sealing·SCM_RIGHTS 전달·읽기 매핑·축소 거부를 비교하고, Mozilla의 정확한 자식 filter를 적용한 차이를 구분해야 한다. 기본 memfd 매핑이나 socket 프로세스의 filter 증가만으로 이를 대체하지 않는다. Firefox 성공이 나와도 Chromium의 sandbox 해결 증거는 아니다.

Android Chrome을 Omarchy 내부 창에 실행하는 경로는 Android task 생성과 Chrome의 browser-instance 배정을 함께 처리해야 한다. 초기 실행 시험에서는 기존 Chrome task131을 보존했고 시작하지 않았다. [현재 공개 API 메타데이터](../../build/diagnostics/android-chromium-target-metadata-compiled-20261008-01/receipt.json)는 기존 Chrome `154.0.8037.126`과 실제 `SDK_INT_FULL=3600000`, `BAKLAVA_FULL=3600000`을 확인했다. 따라서 해당 Chrome 소스의 `SDK_INT_FULL > BAKLAVA_FULL` 자동 새 인스턴스 조건은 충족하지 않는다. 기존 창 재선택과 allocator의 기존 task 정리 조건을 해결하기 전에는 기존 Chrome의 충돌 거부를 풀지 않는다.

별도 package/UID의 공식 Android Desktop ARM64 Chromium `157.0.8093.0`을 설치했고, 당시 f010 안에서 [실제 내부 창 시험](../../build/diagnostics/y900-android-chromium-inside-canonical-20261008-01/receipt.json)이 통과했다. 새 `org.chromium.chrome` UID10372만 사용했다. task218/display39의 실제 Android 프레임 → 기존 canonical GTK Wayland 창 → 동일 Pixbuf/sequence의 Cairo source 선택과 포커스, CLOSED의 task/display/input 정리 및 실제 observer 프로세스 종료를 확인했다. Cairo hook은 `Gdk.cairo_set_source_pixbuf()` 반환 뒤, `cr.paint()` 전에 기록하므로 source-selected만 증명하며 paint 완료·GTK commit·물리 표시는 증명하지 않는다. 기존 Google Chrome task131, 현재121개 설정, Android HOME·ASSISTANT·BROWSER 역할과 입력 서비스를 보존했다.

처음 확인한 내부 화면은 `FirstRunActivity`다. 이후 [회복04](../../build/diagnostics/y900-android-chromium-recovery-20261008-04/receipt.json)는 기본 display의 소유 task226에서 `ChromeTabbedActivity`를 확인하고 task 제거·기존 Loopy213 복귀를 완료했다. 이 회복은 시작부터 Google UID10313의 RunningTasks와 완전한 RecentTasks가 모두 빈 기준 상태를 보존했으며, 초기 시험 당시 Google task131 보존을 현재 상태로 승격하지 않는다. 부재의 원인·프로필·탭 삭제는 추론하지 않는다.

[공개 기능 시험04](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-04/receipt.json)는 FRAME0·포커스 준비 실패로 `passed=false`다. received.ERROR1은 오류 수신 횟수이며 payload code는 미보존이다. 공개 페이지·reverse·입력 시험을 시작하지 않았고, CLOSED0 및 own-window/own-scope 정리 오류도 실패로 남아 있다. [별도 retirement](../../build/diagnostics/y900-android-chromium-public04-retirement-20261008-01/receipt.json)는 소유 PID·org task·display43 부재 확인 뒤 scope를 제거했으며 public04의 실패를 바꾸지 않는다. [standalone shadow](../../build/diagnostics/y900-android-chromium-own-display-20261008-01/receipt.json)의 shell WindowSession relay UNKNOWN도 canonical 실패 원인으로 승격하지 않는다.

이후 [공개 기능 시험09](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-09/receipt.json)는 `passed=true`/`cleanup_errors=[]`다. 새 task231/display47의 ChromeTabbedActivity에서 공개 localhost 페이지와 고정 HTTPS fetch, 합성 클릭·x 키의 DOM event, canonical CLOSED1개와 task/display/input 정리3개를 확인했다.121개 설정·shell 파일, Android 역할·입력 서비스·f010 APK와 현재 기존 task 기준 상태를 보존했다. 공개 WebGL renderer는 ANGLE/Qualcomm Vulkan/Adreno830이고 rAF303회/5008.4ms였으며, 각각 브라우저 WebGL renderer와 JavaScript callback 표본이다. Cairo 관찰은 source-selected이고 물리60/144fps나 전체 표시 경로의 GPU 합격은 아니다.

직접 InputState를 호출한 합성 진단의 NAVIGATE56 ACK/63.260초, 클릭2 ACK/1.311초, 키2 ACK/1.490초를 기록했다. GTK 이벤트와 물리 장치를 거치지 않은 명령 완료 시간이며 실제 사용자 입력 지연이 아니다. 시험08의 `//event` fixture 오류는09의 고정 `/event`로 수정했고 기기 DNS 실패로 해석하지 않는다. 사용자 로그인·일반 사이트·물리 키보드/마우스 반응·패널 FPS 검증은 남아 있다.

이 Chromium은 공식 snapshot의 별도 시험 빌드이며 자동 업데이트가 연결된 정식 Google Chrome 배포가 아니다. [상세 검증](2026-10-08-android-chromium-inside-current.md)에 APK 출처·서명·설치와 시험 범위를 기록했다. 실제 Android Chromium 내부 창은 Linux Chromium 실행과 구분한다. [전체 경로 조사](../research/2026-10-08-chromium-internal-options.md)의 Bionic·Linux/AVF·원격 경로는 조건과 미검증 항목을 그대로 유지한다.
