# 현재 태블릿의 Android Chromium 내부 창

현재 설치 APK는 `1790152c9593ce835b2aaf4adbe18cd8a240a2870a8f1d52a03541f64c79f611`다. [설치20](../../build/diagnostics/y900-android-inside-product-update-20261008-20/receipt.json)은 설정132개·서비스·역할 보존을 통과했다. partial writer의 호스트 증거, 제한된 합성 ACK 표본과 사용자 체감 피드백은 [최신 입력 지연 기록](2026-10-08-inside-input-latency.md)으로 연결한다. 아래5089 및 이전 APK 기록은 각 당시의 증거다.

## 이전5089 연결과 초기 URL

당시 설치본은5089였다. [연결과 URL 보고서](2026-10-08-inside-browser-url.md)는 Google20초 연결 회귀 및 실제 URL GET·JavaScript ready·정상 CLOSED·소유 정리와 설정132 보존을 구분한다. [입력 지연](2026-10-08-inside-input-latency.md)의 당시 raw 두 표본은 약1초이며 클릭 지연 자체나 FPS 합격이 아니다. 아래 기록은 해당 과거 APK의 증거다.

## 이전 d74 설치본의 Google Chrome 연결 수정

당시 APK는 `d74dd1ecd39e1054766e4ff8ac43384457da1066c39bfd9f002042c0114115f4`다. [설치18](../../build/diagnostics/y900-android-inside-product-update-20261008-18/receipt.json)은 설정 132개와 입력 서비스·역할·마이크 거부·global Shizuku lifetime 보존을 확인했다. Chrome 추가 입력 표면을 일반 WindowId로 검사하던 원인과 정확한 수정 범위는 [입력 표면 진단](2026-10-08-inside-chrome-input-surface.md)에 기록했다.

[Google 기기 시험08](../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-08/receipt.json)은 준비 후 20초 유지·오류 0·실제 GTK 압축/raw frame 27개 수신·source 선택 27개·정상 CLOSED와 소유 자원 정리를 통과했다. 로그인·일반 사이트·물리 입력·장시간 사용·전체 GPU 경로·60/144fps 수락은 별도다. [기존 org Chromium 회귀09](../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-09/receipt.json)도 준비 후 20초·압축 프레임 13개·정상 CLOSED·소유 자원 정리를 통과했다. 아래 d806/ae2/f010의 실패·성공 기록은 각 APK의 역사적 증거다.

## 이전 d806 설치본의 Chrome 재현

당시 설치본은 `d8066741ef26d04b409990970c906e261eecb10a908bed84e26576b8f68b0388`다. [update15](../../build/diagnostics/y900-android-inside-product-update-20261008-15/receipt.json)는 현재 설정 132개와 입력 서비스·역할·마이크 거부를 보존했다. 아래 ae2/f010 기록은 해당 APK의 역사적 증거로 유지한다.

사용자가 연 실패 창의 고정 component는 Google `com.android.chrome/com.google.android.apps.chrome.Main`이었다. 실제 환경의 Loopy PID·세션도 현재값과 일치했다. [브로커 현재 상태](../../build/diagnostics/y900-inside-connection-state-20261008-01/receipt.json)는 RUNNING, 정확한 child PID/birth/generation, Hub admitting을 확인했고 [두 Chrome 앱의 metadata03](../../build/diagnostics/y900-inside-chrome-metadata-20261008-03/receipt.json)에서는 기존 target task가 없었다. 메시지만으로 Shizuku 중단이나 기존 task 충돌로 분류하지 않는다.

[Google 재현01](../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-01/receipt.json)은 OPENED·FOCUS ACK·FRAME_ZLIB 표시까지 성공했지만 이후 ERROR12/HOST_UNAVAILABLE를 받았다. CLOSED 미수신을 cleanup 실패로 해석한 당시 driver의 failed receipt를 보존한다. [별도 소유 자원 정리01](../../build/diagnostics/y900-inside-chrome-own-cleanup-20261008-01/receipt.json)은 검사 process/window/display 부재와 scope 제거를 확인했다. 일반 ERROR 경로는 CLOSED를 보내지 않는다.

[Google 재현02](../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-02/receipt.json)에서도 최초 5개 compressed frame 뒤 ERROR12가 발생했다. 관찰한 각 프레임의 header→release queue flush는 약 27–64ms이고 모두 drain됐으므로, 관찰한 프레임의 5초 반환 지연으로 단정할 수 없다. 새 frame 준비·task/focus/platform 조회 중 정확한 native 실패 지점은 아직 미확정이다. 검사 창과 task/display/process/scope는 정리됐으며 기존 task와 설정을 보존했다.

[동일 경로의 org Chromium 재현03](../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-03/receipt.json)은 PASS다. UID10372의 내부 task255/display67, 2512×1592/density320, OPENED·focus/input 준비·압축 FRAME 13개·동일 Pixbuf의 native draw source 13개를 확인하고 20초 유지했다. 정상 CLOSED ACK와 task/display/input 정리, process/window/scope 제거 및 설정·역할·기존 task 보존을 확인했다. 이 trial은 실제 GTK 소비·그리기 경로의 짧은 기능 시험이며 로그인·실제 마우스/키·전체 물리 GPU 경로·60/144fps 수락이 아니다.

## 이전 ae2 설치 기록

2026-10-08, Y900/TB522FU의 현재 설치 APK는 `ae2c3c281f2d8133ed14260bd26044a4e6c5c8f70d6fc642bbeb30d8a6be40fc`다. [빌드 receipt](../../build/deliverables/LoopyDesktop-2026-10-08-chromium-inside-default-arm64/build-receipt.json)의388,070,645 B ARM64 산출물과 [update14](../../build/diagnostics/y900-android-inside-product-update-20261008-14/receipt.json)가 일치한다. [ae2 공개11](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-11/receipt.json)과 [일반 Omarchy menu·Apps 두 실행 경로](../../build/diagnostics/y900-chromium-normal-routes-20261008-01/receipt.json)가 제한된 실제 내부 기능·소유 자원 정리를 통과했다. f010 시험09는 과거 증거로 유지한다. 물리 입력·실사용 지연·전체 GPU 전달·패널60/144fps 합격은 아직 아니다.

## 업데이트 전 f010의 Linux Chromium 실패

[f010 읽기 전용 확인](../../build/diagnostics/y900-user-chromium-failure-20261008-01/receipt.json)에서 브라우저 창·target task·Chromium 프로세스는 없었다. [f010에서 관찰한 MIME 경로](../../build/diagnostics/y900-user-chromium-failure-20261008-01/route.json)는 HTTP·HTTPS·HTML 모두 `chromium.desktop`이며, 위 Android `org.chromium.chrome` 시험09와 다른 Linux 경로다. 이 부재 관찰만으로 종료 원인을 확정하지는 않는다.

[별도 공개 재현03](../../build/diagnostics/y900-browser-native-public-20261008-03/receipt.json)은 sandbox를 해제하지 않고 `PENDING` → `SUID_SANDBOX` 안내를 확인했다. `passed=true`는 실패 안내·소유 창/프로세스 종료·전용 scope 정리·환경 보존의 합격이다. 1256×796 native 창은 startup 안내 창이며 Linux Chromium 페이지·웹 기능 통과가 아니다. 물리 입력과 presentation 필드도 false다.

[설정 차이](../../build/diagnostics/y900-user-chromium-failure-20261008-01/configuration-drift.json)는 기존119개 설정의 삭제·변경 없이 Chromium BrowserMetrics1개와 Crash Reports2개가 추가된122개다. 내용을 기록하거나 제거하지 않았고 재현03은 shell2개까지 현재124개 해시를 보존했다. 아래 이전 영수증의121개 보존은 당시 기준으로 유지한다.

## ae2 빌드·설치와 현재 연결 상태

[호스트 receipt](../../build/diagnostics/browser-route-final-host-tests-20261008-01/receipt.json)는121 tests·실패0·오류0·skip0이다. ROOT의 실제 ZIP 확인에서 관련 assets5개가 일치했고 native7개는 변경되지 않았다. ae2는 [plain Chromium route](../../android/assets/omarchy-bridge/browser_inside_route.py), 정확한 stock `chromium.desktop`의 빈 [gtk-launch 경로](../../android/assets/omarchy-bridge/browser_desktop_launch.py), View 초기 geometry 대기와 SendGuard를 포함한다. URL·다른 인자·사용자 지정 프로필을 Android 경로로 바꾸거나 Linux 커널 sandbox를 해결한 변경은 아니다. [ROOT driver01](../../build/diagnostics/chromium-normal-routes-root-source-20261008-01/run.py)의 완료된 일반 경로 시험은 아래에 구분한다.

[update14](../../build/diagnostics/y900-android-inside-product-update-20261008-14/receipt.json)는 update-only 설치와 현재124개 해시·입력 서비스·HOME/ASSISTANT/BROWSER 역할·microphone 거부를 보존했다. 업데이트 동안 global Shizuku14779의 lifetime 보존도 확인했다. 설치 성공은 내부 브라우저 기능 합격과 구분한다.

[ae2 공개10](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-10/receipt.json)은 `GRANT=0`, `HELLO=0`, `OPENED=0`, `FRAME=0`이며 첫 Session OPEN을 queue·flush·ACK한 증거도 없다. 준비 단계 timeout으로 기능 시험은 실패했다. 당시 native panel은 `BIND_TIMEOUT`이었고 소유 backend가 없었다. 원래 receipt의 CLOSED0·own-window/own-scope 정리 오류를 보존한다. [별도 retirement01](../../build/diagnostics/y900-android-chromium-public10-retirement-20261008-01/receipt.json)은 소유 PID 부재·scope 제거를 통과했지만 `functional_browser_passed=false`, `canonical_CLOSED_received=false`이며 OPEN 자원을 만든 적이 없는 정리다.

[후속 broker-start01](../../build/diagnostics/y900-chromium-broker-start-20261008-01/receipt.json)은 UserService32375와 소유 shell child32396의 RUNNING을 확인했다. global server는 이후 관찰에서31382로 바뀌었고 교체 원인은 미확인이다. ROOT가 global server를 재시작한 것은 아니다. 이 후속 상태나 다음 공개11의 성공으로 공개10의 원인을 확정하거나 실패를 고쳐 쓰지 않는다.

[SendGuard 소스 receipt](../../build/diagnostics/android-inside-send-guard-source-20261008-01/source-receipt.json)는 packet 시작·flush 전체 검증과 매 write FD/peer/stop 검증을 유지하며 같은 packet 내부 birth 검사를8ms 간격으로 재확인한다.8ms는 사망 감지 보장 시간이 아니다. 아래 f010 시험09 입력 시간·프레임 결과는 변경 전 결과이며 ae2의 속도 개선이나60/144fps 증거로 사용하지 않는다.

## ae2 공개11과 일반 실행 경로의 완료 결과

[공개11](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-11/receipt.json)은 `passed=true`, `cleanup_errors=[]`다. org UID10372의 새 task235/display48과 native GTK 창을 확인했고 처음 보낸 OPEN과 실제 OPENED, 기능 본문·최종 상태 모두2512×1592/density320/epoch1이었다. remote focus·input_enabled가 true인 해당 lease에서 localhost 공개 페이지의 loaded·ready·click·key가 각각1회, 고정 HTTPS fetch가 opaque 성공을 반환했다. WebGL은 ANGLE/Qualcomm Vulkan1.3.284/Adreno830을 반환했고 rAF303회/5016.6ms는 JavaScript callback 표본이다. 전체 ImageReader→GTK/Cairo→Loopy 표시 경로의 GPU·물리 FPS 증거가 아니다.

기능 본문에는 FRAME62개·copy62개·같은 Pixbuf/sequence의 Cairo source 선택62개가 있었다. hook은 `cr.paint()` 전이므로 source-selected만 증명한다. 최종 FRAME64개·CLOSED1개와 task/display/input 정리3개, canonical actor 종료·scope/metadata jar/reverse 제거·HTTP 서버 종료를 확인했다. 소유 public nonce 문서만 release ACK와 `about:blank` location replacement로 해제했으며 일반 URL·탭·사용자 기록을 지운 것이 아니다.124개 해시·기존 task 기준 상태·역할·입력 서비스·APK를 보존했다.

| 합성 진단 명령 | 이전 f010 시험09 | 현재 ae2 시험11 |
| --- | --- | --- |
| NAVIGATE,56 ACK | 63.260초 | 59.341초 |
| PUBLIC_CLICK,2 ACK | 1.311초 | 2.152초 |
| PUBLIC_KEY,2 ACK | 1.490초 | 1.710초 |

같은 observer 계열의 명령 완료 시간을 기록했지만 물리 GTK 이벤트·장치는 거치지 않았다. 이 두 표본으로 명확한 지연 개선을 주장하지 않는다. `physical_input_verified=false`와 `physical_presentation_verified=false`를 유지하며 SendGuard 도입을 입력 성능·60/144fps 합격으로 표현하지 않는다.

[일반 경로01](../../build/diagnostics/y900-chromium-normal-routes-20261008-01/receipt.json)은 기존 Omarchy browser menu wrapper와 Apps의 `loopy-app-launch` → `gtk-launch chromium.desktop`을 실제 호출했다. menu는3.292초/task236/display49, Apps는3.268초/task237/display50에 native GTK 소유 창과 같은 org Chromium의 ChromeTabbedActivity 내부 task를 확인했다. 이 시간은 launch 관찰 완료 시간이며 물리 입력 지연이 아니다. 두 경로 모두 소유 창/task 제거,124개 해시·역할·서비스·APK·기존 task 보존과 원래 source/binary 보존을 확인했다. 이 두 정리 시험을 로그인·일반 사이트의 완료 시험으로 넓히지 않는다.

[일반 사용자 창01](../../build/diagnostics/y900-chromium-user-ready-20261008-01/receipt.json)은 현재 ae2에서 진단 marker·환경·workspace 없이 실제 normal Omarchy browser wrapper를 실행해 통과했다. 3.492초에 native GTK PID19411/stableId402653192와 ChromeTabbedActivity task238/display51의 내부 창을 확인했다. 이번에는 `ordinary_user_window_intentionally_retained=true`로 사용자용 창을 열어두었으며, 앞선 진단의 전체 창 정리와 구분해 metadata jar만 제거하고124개 해시·서비스·역할·APK를 보존했다. 물리 입력·물리 표시·일반 사이트·로그인은 검증하지 않았다.

## 아래 완료된 기능 결과의 APK 범위

다음 설치·회복·공개 기능 시험09는 당시 f010 `f01091c87505d649f12bde4b7d17df56f67f8be47f83dbe1a710a03f30b66f62`에서 기록한 역사적 증거다. 원래 실패·성공 영수증과 당시121개 보존 기준을 그대로 유지한다.

## 설치한 Chromium

[Chromium 공식 snapshot](https://storage.googleapis.com/chromium-browser-snapshots/AndroidDesktop_arm64/1714198/chrome-android-desktop.zip)의 `ChromePublic.apk`만 가져왔다. 저장소 generation `1791444440744037`, revision `b5fbbfa53723e0c3a3401d55f58a796d1baa43b8`, 버전 `157.0.8093.0` / code `809300074`, ARM64다. 전체 zip 및 다른 앱을 설치하지 않았다. [출처·압축 entry 검증](../../build/diagnostics/android-chromium-official-candidate-20261008-01/download-receipt.json).

APK는417,270,392 B, SHA-256 `6f50806d94b85efb0933fccc75f474c90622e5f605d0526266d43ec10e26b905`다. SDK 도구의 APK v2 서명 검증을 통과했으며 인증서 SHA-256은 `32a2fc74d731105859e5a85df16d95f102d85b22099b8064c5d8915c61dad1e0`다. 이는 snapshot의 Chromium 시험용 서명이며 Google Chrome 정식 배포·자동 업데이트 보장은 아니다. [서명 결과](../../build/diagnostics/android-chromium-official-candidate-20261008-01/signature.txt).

[신규 설치](../../build/diagnostics/y900-android-chromium-install-20261008-01/receipt.json)는 직전 package 부재와 설치된 APK의 동일 해시를 확인했다. 새 `org.chromium.chrome` UID10372로 설치했으며 기존 `com.android.chrome` UID10313을 덮어쓰지 않았다. 추가 runtime 권한, 기본 브라우저 변경 및 사용자 프로필 복사는 없었다. 설치만 한 시점과 아래 실제 실행 시험은 별도 영수증이다.

## 실제 내부 실행과 정리

[실행 영수증](../../build/diagnostics/y900-android-chromium-inside-canonical-20261008-01/receipt.json)의 `passed=true`와 `cleanup_errors=[]`를 확인했다.

| 항목 | 실제 결과 |
| --- | --- |
| launcher 검증 | MAIN launcher alias와 실제 ChromeTabbedActivity가 같은 APK/UID10372이고 실제 Lenovo PackageManager의 mode4/document0임을 확인했다. 해당 UID의 기존 task는 없었다. |
| Android 소유 창 | 새 task218/display39의 base/orig는 고정 launcher, real은 같은 APK의 ChromeTabbedActivity였다. 실제 top은 FirstRunActivity였다. |
| Wayland 창 | 원래 Hyprland에서 native GTK PID7047/birth77091902/stableId402653204 창을 확인했다. XWayland 창이 아니다. |
| 실제 화면 전달 | canonical FRAME, display copy, 같은 Pixbuf와 sequence의 Cairo source 선택을 확인했다. paint 완료·GTK commit·패널 표시는 별도 증거가 없다. 본문1개·종료 시 누적2개의 sequence다. |
| 포커스 | 해당 lease의 `remote=true`, `input_enabled=true`다. 실제 키 입력이나 화면 반응 지연의 측정은 아니다. |
| 종료 | canonical CLOSED1개와 task/display/input 정리3개를 확인했다. observer의 실제 `/proc` 부재 뒤 전용 폴더와 SHA가 고정된 metadata jar를 제거했다. |
| 기존 환경 | 기존 Google Chrome task131/display0,121개 설정·shell 파일, HOME·ASSISTANT·BROWSER 역할, 입력 서비스와 f010 APK를 보존했다. 원래 작업공간으로 돌아갔다. 기존 화면 보호기는 해제됐으므로 포커스의 `screensaver_dismissed` 판정을 따로 기록했다. |

observer는 canonical `inside_wire`, `inside_input`, `inside_window`를 그대로 로드했다. 결과·오류를 바꾸지 않는 receive/copy/Cairo 관찰 wrapper만 사용했다. Cairo hook은 `Gdk.cairo_set_source_pixbuf()`가 반환한 뒤 기록하며, canonical `cr.paint()`보다 앞선다. 따라서 이 카운트는 **source-selected** 증거이고 paint 완료·GTK commit·물리 표시 증거가 아니다. 계정·화면 픽셀·탭 제목·URL·사용자 입력을 기록하지 않았다. 물리 presentation과 physical input 필드는false다.

앱 설치 broadcast 뒤 Android catalog에 나타나는 `Chromium · Android`가 이 새 앱의 내부 실행 경로다. 기존 Google Chrome task를 채택하거나 이동하는 정책을 열지 않았다. 단일 내부 창은 닫을 때 소유 task를 제거하며, 프로필은 앱의 별도 저장소에 유지된다.

## 공개 웹 사용 시험의 현재 결과

초기 공개 페이지 시험들은 입력 전에 중단했다. 이후 완료된 시험09의 합격은 아래 별도 결과로 기록한다. [시험01](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-01/receipt.json)은 초기 설정의 공개 버튼을 찾지 못해 입력 전에 중단했고, [시험02](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-02/receipt.json)의 제한된 재관찰도 같은 결과였다. 두 시험 모두 소유 창·task/display·프로세스·임시 파일을 정리했고 기존 Google Chrome task131과121개 설정·역할·입력 서비스·APK를 보존했다.

[진단03](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-03/receipt.json)은 실제 task221/display42와 첫 canonical FRAME/Cairo source 선택을 확인한 뒤8초 대기했다. 접근성 관찰은 소유 task/UID를 전후 재확인했지만 해당 display의 application window0개·node0개를 반환했다. 따라서 **초기 설정 버튼 미발견은 현재 관찰 경로의 한계**이며, spinner가 보였거나 Chromium의 native/account/policy 초기화가 멈췄다는 증거는 아니다. 일반 계정·텍스트·화면 픽셀은 읽지 않았고 입력 명령도0개였다. 공개 페이지·인터넷·입력 반응 시험은 시작하지 못했다.

공식 [Android 16 접근성 구현](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r2/services/accessibility/java/com/android/server/accessibility/AccessibilityManagerService.java)의 `AccessibilityDisplayListener.isValidDisplay()`는 private virtual display의 owner가 SystemUI UID가 아니면 창 추적에서 제외한다. 현재 inside 구현은 shell caller가 private virtual display를 만들며 실제 display의 PRIVATE·TRUSTED·OWN_FOCUS flag를 확인한 뒤 OPENED를 보낸다. 관찰한0개 창은 공식 설계와 일치한다. Lenovo framework가 해당 upstream과 동일한 binary라는 증거는 아니다. `eventTypes=0`만 바꾸는 해결책이나 production PRIVATE 보호 제거를 적용하지 않는다.

진단03도 `canonical_closed_and_reaped=true`, `cleanup_errors=[]`이며 기존 task·설정·서비스·역할·APK 보존을 확인했다. 실제 public-page pass와 사용자 입력·GPU·FPS 결과로 승격하지 않는다. 후속 시험은 새 Chromium의 초기 설정만 기본 display에서 진행한 뒤 같은 내부 창 경로를 확인하는 방향으로 이어졌다. 기존 Google Chrome의 task와 프로필은 대상으로 삼지 않는다.

[기본 display 초기 설정 시험01](../../build/diagnostics/y900-android-chromium-onboard-20261008-01/receipt.json)은 새 task222의 UI를 읽었지만 공개 legal footer에서 `settings-missing`으로 중단했다. 입력·action은0개였다. 소유 task 제거·같은 기존 Loopy task 복귀·Google Chrome task131·121개 설정·역할·서비스·APK 보존과 helper jar 제거를 확인했고 `cleanup_errors=[]`다. 고정 Chromium revision의 [공개 문자열](https://chromium.googlesource.com/chromium/src/+/b5fbbfa53723e0c3a3401d55f58a796d1baa43b8/chrome/browser/ui/android/strings/android_chrome_strings.grd)은 실제 UMA 링크를 `Manage`로 정의한다. `Settings`는 해당 링크의 실제 화면 문구가 아니다. 기기의 legacy `persist.sys.locale=en-US` 속성은 실제 앱 표시 언어를 나타내지 않았다. [관찰03](../../build/diagnostics/y900-android-chromium-onboard-20261008-03/receipt.json)의 실제 공개 footer는 한국어83자였고, 정확한 `관리하기` span79..83을 확인했다. 이 label만 추가한 helper07을 새로 봉인했다. 기존 봉인 helper·production source는 바꾸지 않았다.

## 초기 설정 완료 과정의 추가 결과

[초기 설정04](../../build/diagnostics/y900-android-chromium-onboard-20261008-04/receipt.json)는 실제 `관리하기` span을 선택하고 UMA dialog의 중첩 switch를 false로 바꾼 뒤 다시 관찰해 사용 통계 전송 해제를 확인했다. 실제 로그인 건너뛰기 action도 framework accepted=true였다. 이후 새 task225 안의 `RequestRoleActivity`가 나타나 전체 시험과 정리는 아직 통과하지 못했다. 기본 브라우저 설정을 누르지 않았다.

BACK은 해당 dialog를 닫지 못했다. [회복03](../../build/diagnostics/y900-android-chromium-onboard-recovery-20261008-03/receipt.json)은 소유 task와 공개 제목을 재확인하고, 실제 UI에 보이는 유일한 `android:id/button2`의 `취소`를 사용했다. positive 기본 앱 설정 버튼은 disabled였고 선택하지 않았다. 이후 [별도 target metadata](../../build/diagnostics/android-chromium-role-state-20261008-01/metadata.json)에서 FirstRun이 사라지고 새 task226의 ChromeTabbedActivity를 확인했다. 기본 브라우저 역할은 기존 `com.workspacebrowser`였다.

225→226은 Chromium의 FirstRun 완료 PendingIntent 재실행과 일치한다. 기존 helper는 같은 작업 번호와 Google Chrome task131의 running 목록 보존을 요구해서 이 단계의 정리를 거부했다. 당시 running task 관찰에 Google131이 나타나지 않았으며, 이것만으로 최근 task·프로필·탭 삭제를 증명하지 않았다. 초기 설정04와 회복03 영수증은 실패로 그대로 보존하고, 소유 candidate task226 정리는 아래 별도 회복04로 분리했다.

## 완료된 회복04와 공개 기능 시험04

[회복04](../../build/diagnostics/y900-android-chromium-recovery-20261008-04/receipt.json)는 `passed=true`, `cleanup_errors=[]`다. 기본 display의 소유 task226에서 실제 top `ChromeTabbedActivity`를 확인한 뒤 해당 task만 제거하고 기존 Loopy task213의 포커스·가시성을 확인했다. 초기 설정 helper와 복구 helper jar를 정리했으며121개 설정·shell 파일, 역할·입력 서비스·f010 APK를 보존했다. 사용 통계 전송 해제는 이전에 확인한 결과로 구분했다. 이는 초기 설정 이후 소유 task 정리의 합격이며 웹 사용 합격이 아니다.

회복04 시작 시점에 Google Chrome UID10313의 RunningTasks와 **완전한 RecentTasks 관찰** 모두 빈 목록이었고 task131도 없었다. 회복 전후 이 빈 기준 상태를 보존했다. 따라서 이 회복의 보존 결과는 초기 내부 실행 당시 task131 보존과 구분한다. `google_deleted_inferred=false`이며, 부재의 원인이나 프로필·탭 삭제를 추론하지 않는다.

[공개 기능 시험04](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-04/receipt.json)는 `passed=false`다. 새 lease task227/display43의 `OPENED=1`, `ACK=3` 이후 `FRAME=0`, `received.ERROR=1`이었다. **ERROR1은 수신 횟수이며 broker 오류 코드1을 뜻하지 않는다.** 이 영수증은 payload code를 보존하지 않았다. `remote=false`, `input_enabled=false`, display copy·Cairo source 선택0개, 공개 입력 명령0개와 key/button ACK0개다. 준비 상태 확인에서 실패해 공개 페이지·HTTP 서버·reverse mapping·키보드·마우스 입력 시험을 시작하지 못했다. 초기 FirstRun 화면 전달의 합격을 현재 기능 브라우저의 합격으로 옮기지 않는다.

공개 시험04의 `CLOSED=0`, `closed_cleanup=null`, `cleanup_errors=["own-window-AssertionError","own-scope-AssertionError"]`도 그대로 남긴다. 이 영수증에는 canonical 종료·scope 정리의 합격 증거가 없다. metadata jar 제거, 작업공간 복귀 기준 충족과 설정·서비스·역할·APK 보존은 확인했지만 전체 정리 PASS로 묶지 않는다.

[별도 public04 retirement](../../build/diagnostics/y900-android-chromium-public04-retirement-20261008-01/receipt.json)은 소유 observer PID 부재, 기존 org task 부재와 display43 부재를 확인한 뒤 잔여 scope를 제거했다. 이전 CLOSED를 관찰한 것은 아니며 `prior_functional_receipt_remains_failed=true`다. public04의 기능·canonical 정리 실패 영수증을 이 후속 정리로 고쳐 쓰지 않는다.

[standalone shadow 진단](../../build/diagnostics/y900-android-chromium-own-display-20261008-01/receipt.json)은 별도 shell helper의 WindowSession relay가 RESIZE 단계에서 `diagnostic-relay-unknown`/`platform-illegal-state`로 실패했다. 소유 task/display/focus와 helper 정리는 확인했지만 실제 app의 Provider GRANT relay를 사용하지 않았고, `canonical_failure_attributed=false`다. 이 UNKNOWN을 production canonical 실패 원인으로 옮기지 않는다.

## f010 공개 기능 시험09의 완료 결과

[시험09](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-09/receipt.json)는 `passed=true`, `cleanup_errors=[]`다. 새 org UID10372 task231/display47의 base/orig alias와 real/top ChromeTabbedActivity를 확인했다. native GTK Wayland 창 안에서 `remote=true`, `input_enabled=true`인 lease로 제한된 공개 기능을 확인했다. 실제 사용자 탭·계정·화면 픽셀은 기록하지 않았다.

| 확인 | 완료된 시험09 결과와 범위 |
| --- | --- |
| 공개 페이지 | 전용 localhost fixture의 loaded·ready·click·key가 각각1회였다. 고정 `https://example.com/`의 credentials 없는 fetch가 opaque 응답을 받았다. 이 한 HTTPS 경로의 성공을 모든 DNS·Wi-Fi 메뉴·사이트의 합격으로 넓히지 않는다. |
| 합성 입력 | NAVIGATE는56 ACK/63.260초, PUBLIC_CLICK은2 ACK/1.311초, PUBLIC_KEY는2 ACK/1.490초였다. 클릭과 x 키의 공개 DOM event 증가를 별도로 확인했다. |
| 프레임 전달 | 기능 본문에서 FRAME63개·display copy63개·같은 Pixbuf/sequence의 Cairo source 선택63개를 확인했다. `cr.paint()` 이전 source-selected 관찰이며 paint 완료·패널 FPS가 아니다. |
| WebGL renderer | 공개 WebGL context가 `ANGLE (Qualcomm, Vulkan 1.3.284 (Adreno (TM) 830 (0x44050001)), Qualcomm Technologies Inc. Adreno Vulkan Driver)`를 반환했다. Android Chromium의 해당 WebGL renderer 증거이며 ImageReader→GTK/Cairo→Loopy 최종 표시 전체가 GPU 경로라는 증거는 아니다. |
| rAF 표본 | WebGL clear를 수행하는 공개 requestAnimationFrame callback303회/5008.4ms였다. JavaScript callback 표본이며 물리 패널의60/144fps나 end-to-end 전달 FPS가 아니다. |
| 종료·보존 | 최종 CLOSED1개와 task_removed·display_removed·inputs_released 모두 true였다. canonical observer 종료, scope·metadata jar·reverse 제거와 HTTP 서버 종료를 확인했다.121개 설정·shell 파일, Android 역할·입력 서비스·f010 APK, 기존 task 기준 상태와 작업공간 복귀 기준을 보존했다. Google task131이 돌아왔다는 결과는 아니다. |

입력은 [고정 observer03](../../build/diagnostics/android-chromium-public-input-observer-source-20261008-03/observer.py)이 canonical Session의 InputState에 key/button intent를 직접 만드는 합성 진단 경로다. GTK 물리 이벤트 진입은 거치지 않았다. 위 시간은 명령 파일 게시 뒤 각 명령의 ACK 완료 상태까지 root가 관찰한 총 시간이며, 단일 키·클릭의 실제 사용자 지연이나 페이지 반응 지연이 아니다. `physical_input_verified=false`와 `physical_presentation_verified=false`를 유지한다. NAVIGATE의63.260초는 이 진단 경로에서 실제로 측정한 값이며 빠른 실사용 입력의 합격으로 표현하지 않는다.

[시험08](../../build/diagnostics/y900-android-chromium-public-canonical-20261008-08/receipt.json)의 실패는 공개 fixture가 `location.pathname='/'`에 `'/event'`를 붙여 `//event`를 만든 시험 코드 오류였다. [수정한09 fixture](../../build/diagnostics/android-chromium-public-root-source-20261008-09/public_page.py)는 고정 `/event`를 사용했다. 이08 실패로 기기 DNS 오류를 주장하지 않으며08 receipt도 실패로 보존한다.

## 다음 확인

현재 ae2의 공개 기능·일반 launcher 경로를 확인했으나 물리 키보드·마우스의 GTK 이벤트 전달과 실제 반응 시간, 로그인·일반 사이트 사용, Android Chromium 렌더링부터 Loopy의 최종 물리 표시까지의 GPU·FPS는 별도 검증이 필요하다. 일반 Linux Chromium의 커널 sandbox 제약은 이 Android 앱의 성공으로 해결되지 않는다. [Linux 브라우저 후보의 현재 결과](2026-10-08-linux-browser-candidates-current.md).
