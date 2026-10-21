# 태블릿 자체 Android 내부 창 연결 — 2026-10-08

후속 최종 APK e76bd44의 실제 native 재연결/product26/Chromium13/실패 GTK 안내와 남은 범위는 [최신 검증](2026-10-08-inside-browser-startup-current.md)에 기록했다. 아래 a8ee 실패·회복 시험은 이전 설치본의 이력이며 후속 성공으로 덮어쓰지 않는다.

이 문서의 첫 검증 APK는 `a8ee786f165448a90373d8125344cbf90def1a04862c35c53db703d56ad5e6c9`이다. 실제 TB522FU/Y900에서 Shizuku가 Loopy UserService를 시작하고, 그 서비스가 고정 app_process 브로커를 소유한다. ADB는 관찰·설치·공개 입력 시험에 연결돼 있으며 브로커 시작 명령은 실행하지 않았다. 물리 USB 분리·재부팅 자동 시작·모든 Android 앱·60/144fps 수락은 별개다.

## 실제 설치·시작

[고정 APK와 빌드 영수증](../../build/deliverables/LoopyDesktop-2026-10-08-tablet-shizuku-apex-inside-arm64/artifact-identity.json), [update11 PASS](../../build/diagnostics/y900-android-inside-product-update-20261008-11/receipt.json)는 설치 SHA, UID10330, 설정119개와 zsh/tmux2개, 역할·접근성3개·마이크 거부 보존을 확인한다. Shizuku13.6.0/API13.1.5 UserService 경로를 사용한다. 이전 aee1은 실제 접근 허용 뒤 START_REFUSED였고 해당 실패를 보존했다.

실제 readonly APEX JAR들의 UID1000을 UID0 전용 검사에서 거부한 원인을 수정했다. 현재 검사는 bounded canonical boot JAR, UID0/1000, regular, group/other 쓰기 비트 없음, 실제 statvfs ST_RDONLY를 모두 요구한다. [123조건 GREEN](../../build/diagnostics/shizuku-apex-owner-host-20261008-01/green/receipt.json), [그 전 행동 RED](../../build/diagnostics/shizuku-apex-owner-host-20261008-01/red/receipt.json)를 구분한다. 별도 root 실행 Python50개 및 bridge47개가 통과했고 전체 실제 SDK APK 빌드도 성공했다. DEX652개에 Shizuku dependency가 포함되고 hidden framework stub은 없으며 native7개는 이전 설치본과 byte-identical이다.

[실제 native 준비 화면](../../build/diagnostics/y900-shizuku-native-controls-20261008-02/ready-02.json), [프로세스](../../build/diagnostics/y900-shizuku-native-controls-20261008-02/process-ready.json), [controller](../../build/diagnostics/y900-shizuku-native-controls-20261008-02/controller-ready.json)는 app9627→UserService9703→child9743/UID2000/birth76331991/generation763319901971585와 세션e7ed4d7b-49bc-44c0-8dfd-4a56496cd9c8을 묶는다. native dialog의 실제 Shizuku ‘항상 허용’ 선택은 [기록](../../build/diagnostics/y900-shizuku-native-controls-20261008-01/access-granted-action.json)에 남아 있다.

## 실제 앱의 내부 창

[product25 PASS](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product25/receipt.json)는 공개 mode4/alias Android 앱의 actual frame→canonical GTK Wayland→Cairo draw, F12, 소유 UHID 클릭·scroll, GTK960×640/Android1920×1280/density320 resize와 같은 geometry/sequence8의 draw, CLOSED와 task/display/FD/입력·시험 폴더 정리를 확인한다. 관찰 도구4회 모두 exit0이며 FRAME8개/draw6개를 확인했다. 전체71.56초는 시험 작업 시간이고 입력 latency가 아니다. 물리 presentation과 물리 입력 수락은 false다. 공개 tint palette 조건의 PASS이며 정확 원색 수락이 아니다.

[product24 FAIL](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product24/receipt.json)는 draw/F12/클릭 뒤 scroll 직전 JDI 입력 관찰 subprocess가 실패했다. 실제 SCROLL은 전송되지 않았고 resize는 실행하지 않았다. 이 실패를 덮어쓰지 않았으며 CLOSED/시험 자원/121설정과 Chrome task131 보존은 통과했다.

## 종료와 재연결의 발견

[첫 lifecycle FAIL](../../build/diagnostics/y900-shizuku-native-lifecycle-20261008-01/receipt.json)는 native STOP 뒤 controller IDLE/generation0/pid0/pausedtrue, child/UserService 부재, 동일 app9627/Hypr9823/global Shizuku14779를 확인했다. 즉 child clean ACK+reap에 따른 종료는 확인했으나 다시 START할 때 HUB_UNAVAILABLE이었다.

[종료 뒤 own socket](../../build/diagnostics/y900-shizuku-native-lifecycle-20261008-01/socket-after-stop.json) inode43432745가 남아 있었다. [정확 own abstract listener에 payload 없는 연결](../../build/diagnostics/y900-shizuku-native-lifecycle-20261008-01/listener-wake-hypothesis.json) 뒤 기존 inode는 사라지고 native refresh가 inode43794573의 새 Hub를 만들었다. 주소 완전 부재 assertion은 새 Hub 생성 때문에 실패했으므로 그 probe를 무조건 PASS로 기록하지 않는다. [native retry 뒤 실제 child23062 준비](../../build/diagnostics/y900-shizuku-native-lifecycle-20261008-01/after-wake-retry-process.json)를 확인했다. blocked accept를 종료 시 own FD shutdown으로 해제하는 제품 수정과 새 APK 재검증은 진행 중이다. 현재 a8ee의 자가 재시작 완전 수락은 아직 아니다.

## Chromium과 남은 범위

Linux Chromium은 실제 Linux 앱으로 Hyprland 안에 실행하는 경로이고 Android 앱 내부 창과 다르다. 현재a8ee의 [Chromium12](../../build/diagnostics/y900-chromium-inside-public-20261008-12/receipt.json)는 실제 native Wayland1256×796/PID27068/birth76411485, localhost CDP의 ANGLE/Mesa virgl Adreno830 GPU compositing·canvas·raster·WebGL enabled, 공개320×240 canvas301 RAF/5005.4ms(60.135 callbacks/s)을 확인했다. 기본 sandbox는 exit-5/SUID helper FATAL이고 GPU phase는 새 public offline profile에만 --no-sandbox를 사용했다. physical presentation과 일반 gpu_verified 필드는 false다. 관찰 기간·RAF callback을 시작 지연이나 물리 표시 FPS로 승격하지 않는다. 실제 retained Process reap+SID empty 뒤 nofollow bounded Singleton link/socket/profile 정리가 완료돼 probe_complete=true, owned window/leader/scope 부재,121설정·서비스·역할·제품·작업공간/포커스 보존을 확인했다. [helper09 host31개](../../build/diagnostics/chromium-inside-public-source-20261008-09/root-host-verification.json)와 실제 종료를 구분한다. 이전13b 공개 offline 결과는 별도 [보고서](2026-10-08-chrome-mode4-current.md)에 남아 있다. 기본 sandbox 실패와 --no-sandbox 공개 offline 진단을 일상 웹 사용 성공으로 바꾸지 않는다. 34.47초는 창 관찰 기간이며 시작 지연이 아니다. 현재 메뉴는 실행 요청의 ok만 보고 browser abort를 놓쳤다. 원본 Omarchy browser handoff/프로필을 보존하면서 실제 소유 Wayland 창 또는 startup 실패를 표시하는 변경은 진행 중이다.

기존 사용자 Chrome task131은 display0에 그대로 보존한다. Android Chrome은 mode4 alias 메타데이터가 맞지만 기존 task conflict는 거절하며, Notion mode2 task는 아직 내부 창 지원 대상이 아니다. 일반 Chromium sandbox, 재부팅·USB 분리, 완전한 Omarchy/원격 기능, 물리 입력 지연 및60/144fps 검증은 남아 있다.
