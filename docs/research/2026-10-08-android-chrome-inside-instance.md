# Android Chrome 154를 Omarchy 내부 새 창으로 실행할 조건

확인일 2026-10-08. **공식 Chrome 154 소스에는 새 인스턴스 후보 경로가 있지만, 기존 사용자 Chrome task131을 보존하면서 현재 설치본을 내부 VD에 실행할 수 있다는 증거는 아직 없다.** 현재 f010의 기존 task 충돌 거부를 유지한다. 이 조사는 로컬 소스·보존된 공개 메타데이터·공식 HTTPS 소스 읽기만 수행했다. 생산 코드 변경, 테스트, 빌드, ADB, 앱 실행, APK 의미 분석, 사용자 프로필·화면 내용 읽기는 하지 않았다.

## 현재 제품과 기기 증거

| 항목 | 실제 기록과 해석 |
| --- | --- |
| 제품 | [artifact identity](../../build/deliverables/LoopyDesktop-2026-10-08-single-task-inside-arm64/artifact-identity.json)의 APK SHA-256은 `f01091c87505d649f12bde4b7d17df56f67f8be47f83dbe1a710a03f30b66f62`. 이 파일만으로 기기 검증을 주장하지 않는다. |
| 현재 task 보존 | 같은 APK의 [공개 singleTask fixture product28](../../build/diagnostics/y900-android-inside-singletask-product-runs-20261008-01/product28/receipt.json)은 Chrome UID10313의 **task131/display0**과 base/real/orig/top component를 전후 동일하게 기록한다. `preexisting_user_browser_task_unchanged=true`; 이것은 fixture 시험이며 실제 Chrome 내부 실행 합격이 아니다. |
| Chrome launcher | 같은 공개 PM 기록: `com.android.chrome/com.google.android.apps.chrome.Main` → `org.chromium.chrome.browser.ChromeTabbedActivity`, 같은 APK/UID, alias와 실제 activity 모두 mode4/doc0, enabled/exported, permission 없음. mode4는 `singleInstancePerTask`, doc0은 `none`이다. |
| 설치 버전 | [공개 PM 버전 receipt](../../build/diagnostics/android-chrome-version-metadata-20261008-01/receipt.json): `154.0.8037.126`, versionCode `803712604`, minSdk32/targetSdk36. |
| OS 속성 | [공개 SDK receipt](../../build/diagnostics/android-chrome-sdk-properties-20261008-01/receipt.json): sdk `36`, sdk_full `36.0`, sdk_minor 없음. **실제 Java `Build.VERSION.SDK_INT_FULL` 필드 직접 확인은 false**다. 속성 문자열을 그 API 숫자나 비교 결과로 대체하지 않는다. 공개 code path는 base/chrome/ko/on_demand split 존재만 확인했다. |

현재 [TargetGuard](../../android/src/dev/loopy/desktop/AndroidInsideTargetGuard.java) 118–130행은 mode4/doc0·3을 허용하면서 **모든 display의 같은 UID 또는 base/top/real/orig package task가 하나라도 있으면 시작 전에 거부**한다. Chrome131은 이 조건에 해당한다. 146–150행은 PM descriptor와 두 task snapshot을 재확인하고, 153–179행은 START_SUCCESS 뒤 새 own VD의 새 task만 claim/cleanup한다. 이전 task를 이동·종료·cleanup 소유로 취득하는 경로는 없다.

[Display](../../android/src/dev/loopy/desktop/AndroidInsideDisplay.java) 151–158행은 원래 launcher alias에 MAIN/LAUNCHER, NEW_TASK|MULTIPLE_TASK, own launchDisplayId를 사용한다. 현재 Chrome 전용 extra는 없다. [기존 guard 테스트](../../tests/java/AndroidInsideTargetGuardTests.java) 223–267·275행 이후는 새 lease, prior task 거부, 모든 display의 충돌, alias/PM 변경 경계를 다룬다. Chrome의 내부 할당 정책이나 실제 154 실행을 검증하지 않는다.

## 공식 154 소스에서 확인한 경로

이번에는 main 대신 [공식 태그 154.0.8037.126](https://chromium.googlesource.com/chromium/src/+/refs/tags/154.0.8037.126)을 직접 읽었다. 태그 commit은 **`8eaafabb47f12210d524f648b78bce074fa3c83e`**, `chrome/VERSION`은 MAJOR154/MINOR0/BUILD8037/PATCH126이다. 아래 링크는 이 commit에 고정한다. 같은 버전 이름이 설치된 Google APK의 코드·feature 상태가 이 소스와 동일하다는 증명은 아니다.

| 후보와 조건 | 고정 소스에서 확인한 계약 |
| --- | --- |
| mode4와 NEW_TASK\|MULTIPLE_TASK | Android [activity launch mode 문서](https://developer.android.com/guide/topics/manifest/activity-element#lmode)와 [MULTIPLE_TASK 문서](https://developer.android.com/reference/android/content/Intent#FLAG_ACTIVITY_MULTIPLE_TASK)는 새 task 인스턴스 경로를 설명한다. **Android 새 task 생성과 Chrome의 새 browser instance 할당은 별도 단계**다. OEM framework의 현재 실행 결과는 이번 조사에서 확인하지 않았다. |
| 플래그에 의한 자동 prefer-new | [MultiWindowUtils](https://chromium.googlesource.com/chromium/src/+/8eaafabb47f12210d524f648b78bce074fa3c83e/chrome/android/java/src/org/chromium/chrome/browser/multiwindow/MultiWindowUtils.java) 589–603행: SDK_INT≥BAKLAVA에 더해 **SDK_INT_FULL>BAKLAVA**, ACTION_MAIN, 두 task flag를 모두 요구한다. 공개 sdk_full=36.0만으로 이 조건이 true라고 볼 수 없다. false라면 현재 플래그만으로 fresh instance를 요구하지 못한다. |
| 명시적 prefer-new | 같은 소스 518–537행은 내부 새 창에 두 flag와 `EXTRA_PREFER_NEW=true`를 사용한다. 603행은 이 boolean을 safeGetBooleanExtra로 읽고 별도 self-trust 검사를 두지 않는다. [IntentHandler](https://chromium.googlesource.com/chromium/src/+/8eaafabb47f12210d524f648b78bce074fa3c83e/chrome/android/java/src/org/chromium/chrome/browser/IntentHandler.java) 264–268행의 정확한 이름은 **`com.android.chrome.prefer_new`**다. 임의 extra 추측이 아니라 source-backed 후보지만 외부 호출의 안정된 public API 보장은 미확인이다. |
| MAIN과 window ID | [ChromeTabbedActivity](https://chromium.googlesource.com/chromium/src/+/8eaafabb47f12210d524f648b78bce074fa3c83e/chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java) 4215–4237행은 preferNew를 allocator에 전달하고 invalid ID이면 새 activity 시작을 거부한다. 4287–4316행의 외부 VIEW 전달은 기존 activity로 갈 수 있다. 현재 MAIN은 그 VIEW 분기에 해당하지 않는다. 4324–4328행은 window-ID extra를 self-trusted intent에서만 인정한다. 기존 ID·self-trust·caller spoof는 사용하지 않는다. |

## 기존 Chrome 보존을 막는 구체적 조건

[MultiInstanceManagerApi31](https://chromium.googlesource.com/chromium/src/+/8eaafabb47f12210d524f648b78bce074fa3c83e/chrome/android/java/src/org/chromium/chrome/browser/multiwindow/MultiInstanceManagerApi31.java) 367–437행은 **removeInvalidInstanceData → finishExcessRunningActivities → 기존 task mapping → preferNew** 순서다. preferNew는 기존 task mapping보다 뒤에 있으며, 여유와 새 ID가 없으면 invalid를 반환한다. true extra 하나가 모든 상태에서 fresh instance를 보장하지는 않는다.

같은 소스 536–583행은 instance-limit downgrade 처리 전이고 `active instance 수 − max + 1 > 0`이면 LRU 기존 AppTask에 **finishAndRemoveTask()**를 호출한다. 이것은 새 창 실패 후에도 되돌릴 수 있는 작업이 아니다. 따라서 시작 후 task131 존재 확인만으로 보존을 보장할 수 없다. 711행 이후는 내부 persisted state 정리도 시작 전에 수행한다.

MultiWindowUtils 217–233행의 max는 desktop/메모리 분류에 따라 다르고, 1296–1337행의 active instance 수는 **Chrome 내부 persisted ID/task mapping**으로 계산한다. 공개 Android task 목록만으로 그 mapping의 개수·유효성·downgrade 상태를 확정할 수 없다. 이번 조사에서는 그 private store를 읽거나 reset하지 않았다.

안전한 후보의 필요조건은 정확한 설치 코드 계약, 유효한 새 task/instance 할당, 기존 task 종료 분기에 들어가지 않는다는 사전 증거, 같은 UID/package의 동시 시작 제어다. 이 증거가 부족하거나 ID/capacity가 invalid면 실행 전 거부해야 한다. 기존 task 이동, launchTaskId, profile reset, window-ID 추측으로 해결하지 않는다.

## 가장 작은 다음 gate

1. **읽기 전용 API 확인:** 담당 root가 고정 시스템 helper에서 실제 SDK_INT, SDK_INT_FULL, VERSION_CODES_FULL.BAKLAVA 숫자만 수집해 자동 prefer-new 조건을 판정한다. Chrome 시작·프로필 읽기 없이 가능한 최소 추가 관찰이다. sdk_full 문자열은 이미 수집했으므로 반복하지 않는다.
2. **설치 계약과 사전 안전 증거:** 태그 154의 정적 후보는 이번에 확인했다. 남은 것은 설치 Google APK의 해당 동작·feature/runtime 상태와 allocator가 task131을 종료하지 않을 사전 증거다. 공개적으로 제공되는 Chrome capability/contract가 없다면 private store 대신 확정할 근거가 부족한 상태로 남긴다. 단순 task 수를 capacity 증거로 승격하지 않는다.
3. **실행 이전 정책 검증:** 필요한 증거가 확보된 뒤에만 Chrome 전용 고정 boolean 후보를 broker 내부 typed 정책으로 설계한다. 임의 Intent extra를 RPC에 노출하지 않는다. PM/버전 변경, unknown SDK/limit, 기존 mapping, limit 초과, 중복 시작은 사전 거부하고 task131을 claim/cleanup하지 않는 RED 사례부터 root가 검증한다. 현재 guard를 우회한 실제 Chrome trial은 다음 단계가 아니다.

실제 내부 Chrome의 새 task·frame·입력·resize·cleanup 합격은 위 gate 뒤 별도 실행 증거가 필요하다. Android 화면을 Wayland 창에 전달하는 이 경로는 Android Chrome 자체이며, Linux Chromium의 sandbox·GPU·native Wayland 지원을 검증하는 경로는 별도로 남는다.

## 입력 identity

| 입력 | SHA-256 |
| --- | --- |
| PM 버전 receipt | `fcbf7551a268819ac8a7efc4cdc45f9d54970a89e96b33f47a583370844ed9c2` |
| SDK 속성 receipt | `c9e3a13d92be3fd9c811eb38d9d8ef9098876aa0bebef92ecaeecbf0a11675d4` |
| f010 product28 receipt | `c4ae9a7b64884d974c4d1e6841fc0d118f7375b7e67a843f941d2e05a892b9cd` |
| 현재 TargetGuard | `1f655dd724feb742c73dd79b6d9c1db994f4cb966f0df0fcfcdd79ef6307b259` |
| 공식 154 chrome/VERSION | `bed0ce9f31f6e662b44d293a7de7e26d85c687cbb13b1ddcf6c3a112d37abc3d` |
| 공식 154 MultiWindowUtils.java | `7a5a0598a1873cd7a249fea05a8eec5008360e0195a9a3c0b4589d5d8905019d` |
| 공식 154 MultiInstanceManagerApi31.java | `a66fd93a982a1756dfa7ba3e7c29bed7c29f89bc0f63fa467ebd6a95d15e32d3` |
| 공식 154 ChromeTabbedActivity.java | `e35eaa221f03c602488f3809d6f5d6d2219f695cccc2d3a660205ded5773a829` |
| 공식 154 IntentHandler.java | `225dd5c2899ba526ae0d2570cf024c38a293756c8fae1ba188c3948911aea87d` |

공식 소스 hash는 HTTPS Gitiles TEXT 응답을 디코딩한 UTF-8 본문 기준이다. APK 역분석은 하지 않았다. 태그·commit·VERSION·본문을 읽어 확인한 기록이며 기기 실행 receipt가 아니다.
