# Y900 내부 Notion 최초 실행

현재 설치 APK는 `f01091c87505d649f12bde4b7d17df56f67f8be47f83dbe1a710a03f30b66f62`다.
[보존한 배포물](../../build/deliverables/LoopyDesktop-2026-10-08-single-task-inside-arm64/artifact-identity.json)은 빌드 산출물이며 `device_verified:false`를 유지한다. 실제 기기 결과는 아래 별도 영수증에 묶었다.

Notion처럼 direct launcher의 `singleTask`/document mode0 앱은 기존 UID·package 작업이 어느 디스플레이에도 없을 때 내부 창에서 처음 실행할 수 있게 했다. 기존 작업이 있으면 계속 실행 전에 거부한다. Chrome task131을 이동하거나 삭제하는 변경은 없으며, Chrome의 새 인스턴스 경로는 아직 남아 있다.

## 이번 변경과 검증

| 검증 | 결과와 범위 |
| --- | --- |
| [정책 RED](../../build/diagnostics/android-inside-singletask-policy-20261008-01/red.json), [GREEN](../../build/diagnostics/android-inside-singletask-policy-20261008-01/green.json) | 기존 최초 실행 거부를 먼저 재현하고 423 assertions 통과. mode2/direct/doc0만 추가 허용. alias·다른 document mode·UID/package 작업 충돌·metadata 변경·기존 task 정리 거부 유지. |
| [SDK 빌드](../../build/diagnostics/singletask-sdk-20261008-01/receipt.json) | PASS, 49.4초. 이전 e76 대비 제품 입력 변경은 TargetGuard.java 한 파일뿐. native7개와 browser/inside 자산은 byte 동일. |
| [업데이트](../../build/diagnostics/y900-android-inside-product-update-20261008-13/receipt.json) | Y900/TB522FU에 update-only 설치. 직전 editor 확인, UID10330·119설정+zshrc/tmux2·역할·접근성·마이크 거부 보존. 별도 [종료 영수증](../../build/diagnostics/y900-shizuku-before-single-task-update-20261008-01/receipt.json)은 이전 소유 브로커만 협력 종료했음을 기록. global Shizuku14779 재시작 없음. |
| [공개 mode2 앱](../../build/diagnostics/y900-android-inside-singletask-product-runs-20261008-01/product28/receipt.json) | PASS. 실제 새 task215/display36, native GTK/Cairo draw와 F12, 두 번째 OPEN 실행 전 거부·기존 첫 창 보존, CLOSED·task/display/input 정리, Chrome131·121설정·포커스 보존. 물리 입력·색 정확도·FPS 합격은 아님. |
| [실제 Notion02](../../build/diagnostics/y900-notion-inside-canonical-20261008-02/receipt.json) | PASS. 최신 실제 PM metadata UID10316/mode2/doc0/direct와 기존 Notion task 부재 확인. 실제 Notion task217/display38이 canonical native Wayland 창에 열림. 전달 frame과 실제 Cairo source 호출의 같은 pixbuf/sequence 확인. 자기 창 CLOSE ACK의 task/display/input 정리, 실제 observer 프로세스 부재, Chrome131·121설정·역할·접근성·포커스 보존. |

Notion 내용·픽셀·창 제목·입력·로그인 정보는 관찰 영수증에 기록하지 않았다. Android Notion의 실제 프레임을 내부 GTK 창에 전달하는 경로이며 Linux Notion이나 Linux Chromium 실행 증거가 아니다. Notion 로그인·편집·한국어 입력·클립보드·물리 포인터·장기 사용성과 실제 화면 표시 FPS는 별도로 남아 있다.

## 진단 수정과 남은 제한

첫 공개 [product27](../../build/diagnostics/y900-android-inside-singletask-product-runs-20261008-01/product27/receipt.json)은 direct task의 `orig`가 JSON에서 생략된 경우를 alias처럼 조회한 root 검증 코드 때문에 실패했다. 앱의 draw·키·정리는 확인됐으며, 생략된 optional metadata를 처리한 다음 product28 전체 흐름을 통과했다. 이전 실패 기록은 그대로 보존했다.

첫 [Notion01](../../build/diagnostics/y900-notion-inside-canonical-20261008-01/receipt.json)은 CLOSED 정리 ACK 이후 observer가 `exited` 상태를 쓰고 실제로 종료하기 전 root가 PID 부재를 즉시 요구한 문제로 실패했다. 별도 [정리 확인](../../build/diagnostics/y900-notion-inside-cleanup-recovery-20261008-01/receipt.json)으로 종료·새 task/display 부재·Chrome131 보존·자기 파일 제거를 확인했다. 실제 PID 부재를 기다리는 수정 후 Notion02 전체 검증이 통과했다. 제품 소스를 바꾼 오류 수리는 아니다.

사전 snapshot과 Android start Binder 호출은 원자적이지 않다. 동시 외부 앱 실행까지 경쟁을 없앴다고 주장하지 않는다. 기존 task 재사용 거부와 새 task claim/정리 경계는 유지한다. [AOSP ActivityStarter](https://android.googlesource.com/platform/frameworks/base/+/437c2aab950a/services/core/java/com/android/server/wm/ActivityStarter.java)

일반 Linux Chromium의 sandbox 문제는 이번 변경으로 해결되지 않았다. e76의 제한된 공개 오프라인 GPU 진단은 [이전 브라우저 보고](2026-10-08-inside-browser-startup-current.md)에 따로 보존하며 현재 f010의 60/144fps 합격으로 옮기지 않는다. [내부 Chromium 실행 대안 조사](../research/2026-10-08-chromium-internal-options.md)는 Termux/Bionic·Android Chrome 내부 창·실제 Linux/AVF·원격 경로의 조건을 구분한다.
