# Android 앱을 Loopy/Wayland 안에 띄우는 경로

2026-10-08 소스·공식 API 조사와 후속 실기기 검증. 현재 제품 `0589092c…`의 Android 앱 연계는 **별도 Android task 실행**이다. 제품의 AndroidApps.launch는 아직 내부 창에 연결하지 않았다. 아래의 별도 진단 경로에서는 root·OS 플래시 없이 TB522FU의 공개 Android 시험 앱을 실제 GTK Wayland 창에 표시하고 제한된 입력 왕복을 검증했다. 초기 소스 조사, 후속 기기 시험과 제품 기능의 수락 범위를 구분한다.


## 현재 확인된 내부 표시 경계

후속 [inside16](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside16/receipt.json)에서 **실제 다른 UID의 공개 Android 시험 앱 → 실제 관리된 GTK Wayland 창 → 클릭/F12 → Android 앱 화면 변경 → Wayland draw ACK → 시험 터미널 포커스 복귀·정리**의 유한 왕복은 전체 통과했다. 시험 Android UI를 Linux에서 다시 그린 모사 화면이 아니다. Android VirtualDisplay의 원래 RGBA 프레임3개를 전달했다. GTK의 클릭 좌표는116,103이며 broker는 그 장면의 동일한 중간 밴드에 **고정 중심 클릭**을 보낸다. 임의 좌표/키 전달이나 물리 입력 지연·presentation·FPS 수락은 아니다.

16은 사용자 셸 설정을 읽지 않는 소유한 foot/sleep120 터미널을 기준으로 포커스 복귀를 검증했다. 터미널은53.5초의 시험 동안 살아 있었고 정확한 PID/birth/stableId로 복귀했다. 소유한 Android task/display/GTK 창·프로세스·파일은 정리했고 설정118·서비스·Assistant/HOME 역할·제품0589·기본 Loopy 포커스는 보존했다. 실제 Notion/Chrome 내부 실행과 현재 AndroidApps.launch 제품 경로 통합은 남아 있다.

[16의 외곽 anchor 검사](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside16-anchor/receipt.json)는 원래 창의 class를 `org.omarchy.screensaver`로 기록했다. 설치된 화면 보호기 스크립트 두 개는 [고정 원본 소스](../../build/diagnostics/y900-screensaver-lifetime-source-20261008-01/source.json)와 [SHA가 일치](../../build/diagnostics/y900-screensaver-lifetime-source-20261008-01/installed-source.json)하며, 원본은 포커스를 잃으면 화면 보호기를 종료한다. 외곽 receipt는 이를 일반 창 소실로 취급한 기존 guard 때문에 **FAIL을 그대로 유지**한다. 내부16의 PASS와 외곽 검사의 FAIL은 별개다. 09/10/13/15에서는 원래 창의 class를 보존하지 않았으므로 이 원인을 소급 적용하지 않는다.

새 [AndroidInsideProtocol.java](../../android/src/dev/loopy/desktop/AndroidInsideProtocol.java)·[AndroidInsideSession.java](../../android/src/dev/loopy/desktop/AndroidInsideSession.java)는 창별 task/generation/geometry/focus/input/payload 수명을 관리하는 순수 호스트 코드다. 루트의 [실제 JDK 컴파일·93개 동작 검증](../../build/diagnostics/android-inside-host-java-20261008-01/receipt.json)은 통과했다. 현재 APK에는 이 경로가 연결되지 않았으며 실제 권한 백엔드·Wayland/Android 어댑터·지속 프레임·resize/reconnect/close·지원 앱 검증은 별도 실제 단계다.

## 현재 연결 지점

| 코드 근거 | 현재 동작·다음 연결 지점 |
| --- | --- |
| [AndroidAppCatalog.java:16](../../android/src/dev/loopy/desktop/AndroidAppCatalog.java#L16), [27](../../android/src/dev/loopy/desktop/AndroidAppCatalog.java#L27) | Linux `.desktop` 항목이 `platform_action.py launch`를 호출한다. |
| [platform_action.py:19](../../android/assets/omarchy-bridge/platform_action.py#L19), [46](../../android/assets/omarchy-bridge/platform_action.py#L46) | 현재 session token·catalog에 포함된 component만 허용하고 요청을 원자적으로 게시한다. 화면·task를 호스팅하는 프로토콜은 없다. |
| [AndroidApps.java:81](../../android/src/dev/loopy/desktop/AndroidApps.java#L81), [139](../../android/src/dev/loopy/desktop/AndroidApps.java#L139) | `MAIN/LAUNCHER` + `NEW_TASK`로 `Activity.startActivity()`를 호출한다. display ID·TaskFragment·VirtualDisplay를 지정하지 않는다. 화면 고정 중에는 외부 실행을 거부한다. |
| [MainActivity.java:351](../../android/src/dev/loopy/desktop/MainActivity.java#L351), [392](../../android/src/dev/loopy/desktop/MainActivity.java#L392) | 현재 입력 소유권은 Linux Surface의 foreground/focus에 묶이며, `onStop`에서 display/input을 분리한다. 내부 Android pane을 넣으려면 입력·포커스·Surface 수명도 연결해야 한다. |
| [AndroidManifest.xml:2](../../android/AndroidManifest.xml#L2), [25](../../android/AndroidManifest.xml#L25) | target SDK는 36이다. HOME 등록은 있으나 Assistant component나 아래 task/embedding 권한은 없다. HOME 역할만으로 Recents 권한을 얻지는 않는다. |

범위가 정해지면 현재 catalog/token 검증을 유지한 `AndroidApps.launch()` 뒤에 별도 host 모듈을 연결할 수 있다. **Android host 안의 pane**과 **Hyprland가 이동·크기·AltTab을 관리하는 창**은 서로 다른 결과물이므로 먼저 원하는 범위를 확정해야 한다.

## 권한 경로 두 가지

**Assistant 역할을 사용자가 선택하는 경로.** Android 16 AOSP의 Assistant 역할은 사용자별 exclusive 역할이며 `requestable=false`다. 기본 Assistant 교체를 사용자가 명시적으로 선택해야 하고, 역할 자격과 OEM UI를 확인해야 한다. 이 역할에는 `EMBED_ANY_APP_IN_UNTRUSTED_MODE` 권한이 포함된다. 일반 runtime permission dialog로 얻는 권한이 아니다. [Android 16 roles.xml:104–157](https://android.googlesource.com/platform/packages/modules/Permission/+/refs/heads/android16-release/PermissionController/res/xml/roles.xml#104), [권한 정의:4334–4344](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/core/res/AndroidManifest.xml#4334).

해당 권한과 `untrustedEmbeddingAnyAppPermission` flag가 실제로 적용되면 TaskFragment의 untrusted embedding 검사에서 대상 앱 opt-in을 대체할 수 있다. 그래도 host task 안의 bounds 등 제약은 남으며, 권한이 곧 임의 VirtualDisplay 실행·입력 주입 권한이 되는 것은 아니다. 현재 앱의 역할 자격·OEM flag·Window SDK 지원은 미검증이다. [TaskFragment.java:810–821,893–896](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/services/core/java/com/android/server/wm/TaskFragment.java#810).

**사용자가 승인한 ADB shell broker 경로.** AOSP Shell은 `INTERNAL_SYSTEM_WINDOW`, `INJECT_EVENTS`, `MANAGE_ACTIVITY_TASKS`, `ACTIVITY_EMBEDDING` 등을 선언한다. display 실행 검사도 shell이 가질 수 있는 `INTERNAL_SYSTEM_WINDOW` 권한을 별도로 허용한다. 따라서 승인된 shell UID 2000 프로세스가 제한된 대상 task/display/input을 소유하고 Loopy와 연결하는 경로를 검증할 수 있다. 이는 소스에 근거한 가능성 판단이며, Lenovo의 실제 grant·SELinux·API 접근과 재연결 수명은 아직 증명하지 않았다. [Shell manifest:175–176,272–276,974–975](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/packages/Shell/AndroidManifest.xml#175), [ActivityTaskSupervisor.java:1242–1316](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/services/core/java/com/android/server/wm/ActivityTaskSupervisor.java#1242).

broker는 사용자의 디버깅 승인과 살아 있는 shell 연결이 필요하다. `run-as dev.loopy.desktop`은 앱 UID로 바뀌므로 shell 권한을 유지하는 방법이 아니다. `MANAGE_ACTIVITY_TASKS`는 `signature|recents`, `ACTIVITY_EMBEDDING`은 `signature|privileged`이므로 현재 앱에 선언하거나 일반 `pm grant`를 호출하는 것으로 해결되지 않는다. [Android 16 권한 정의:4326–4332](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/core/res/AndroidManifest.xml#4326).

## 일반 SDK와 Wayland 창의 경계

일반 cross-app Activity embedding은 대상이 host 인증서를 `knownActivityEmbeddingCerts`로 신뢰하거나 `allowUntrustedActivityEmbedding=true`로 opt-in해야 한다. 기본값은 false다. 따라서 현재 설치된 Notion/Chrome 등 임의 앱이 협력한다고 가정할 수 없다. [공식 Activity embedding 문서](https://developer.android.com/develop/ui/views/layout/activity-embedding#cross-app-embedding).

`DisplayManager.createVirtualDisplay()`는 제공한 Surface에 Android display 출력을 연결하는 API다. 다른 UID 앱을 그 display에 실행할 권한과 입력을 전달할 권한은 별도 검사 대상이다. VirtualDisplay의 픽셀이 보인다는 사실만으로 Hyprland의 native window가 되지는 않는다. 진짜 Wayland 창에는 픽셀 전달 외에 `xdg_toplevel` 수명, resize, focus, 좌표 변환, 키·버튼 전달, 닫기와 Android task 종료를 묶는 adapter가 필요하다. [DisplayManager API](https://developer.android.com/reference/android/hardware/display/DisplayManager#createVirtualDisplay(java.lang.String,int,int,int,android.view.Surface,int)), [ActivityOptions.setLaunchDisplayId](https://developer.android.com/reference/android/app/ActivityOptions#setLaunchDisplayId(int)), [AOSP display 실행 검사](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/services/core/java/com/android/server/wm/ActivityTaskSupervisor.java#1276).

## 향후 root 담당자의 읽기 전용 조회

아래 `root`는 기기 작업 담당자를 뜻하며 `su` 실행을 뜻하지 않는다. 명시적 serial을 확인한 뒤 담당자만 실행한다. 조회가 실패하면 지원 여부는 미확인으로 남긴다. 역할 추가·권한 grant·display/task 생성 명령은 포함하지 않았다.

```sh
SERIAL='<확인한 기기 serial>'
adb -s "$SERIAL" shell id -u
adb -s "$SERIAL" shell getprop ro.build.version.sdk
LOOPY_USER_ID="$(adb -s "$SERIAL" shell am get-current-user | tr -d '\r')"
case "$LOOPY_USER_ID" in ''|*[!0-9]*) exit 1 ;; esac
adb -s "$SERIAL" shell cmd role get-role-holders --user "$LOOPY_USER_ID" android.app.role.ASSISTANT
adb -s "$SERIAL" shell cmd role get-role-holders --user "$LOOPY_USER_ID" android.app.role.HOME
adb -s "$SERIAL" shell pm has-feature android.software.activities_on_secondary_displays
adb -s "$SERIAL" shell pm list libraries | rg '^library:androidx\.window\.(extensions|sidecar)$'
adb -s "$SERIAL" shell dumpsys package com.android.shell |
  rg '^[[:space:]]*(userId=|android\.permission\.(INTERNAL_SYSTEM_WINDOW|INJECT_EVENTS|MANAGE_ACTIVITY_TASKS|ACTIVITY_EMBEDDING|CREATE_VIRTUAL_DEVICE|ADD_TRUSTED_DISPLAY): granted=)'
adb -s "$SERIAL" shell dumpsys package dev.loopy.desktop |
  rg '^[[:space:]]*(userId=|android\.permission\.(EMBED_ANY_APP_IN_UNTRUSTED_MODE|MANAGE_ACTIVITY_TASKS|ACTIVITY_EMBEDDING): granted=)'
```

명령 문법은 [RoleShellCommand.java:120,197](https://android.googlesource.com/platform/packages/modules/Permission/+/refs/heads/android16-release/service/java/com/android/role/RoleShellCommand.java#120), [PackageManagerShellCommand.java:3724,4679](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/services/core/java/com/android/server/pm/PackageManagerShellCommand.java#3724), [ActivityManagerShellCommand.java:2563](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/services/core/java/com/android/server/am/ActivityManagerShellCommand.java#2563)와 대조했다. `has-feature`의 false/exit 1은 정상적인 미지원 결과다. permission 출력 없음·library 목록 없음은 실제 grant/지원의 확정적인 부정 증거로 쓰지 않는다.

API 36과 secondary-display feature는 사전 조건 일부일 뿐이다. 정확한 Window SDK 지원은 향후 소유한 최소 demo에서 `WindowSdkExtensions.getInstance().getExtensionVersion()`과 `SplitController.getInstance(context).getSplitSupportStatus()`를 읽어 고정 숫자·지원 enum만 기록해야 한다. 해당 demo/조회 CLI는 아직 만들지 않았다. [WindowSdkExtensions](https://developer.android.com/reference/androidx/window/WindowSdkExtensions), [SplitController](https://developer.android.com/reference/androidx/window/embedding/SplitController).

## 최소 실제 검증의 합격 경계

기기 담당자의 실제 읽기 전용 조회에서 API 36·shell UID 2000·secondary-display feature `true`·Window extensions/sidecar 라이브러리를 확인했다. `com.android.shell` package dump에는 `INTERNAL_SYSTEM_WINDOW`, `INJECT_EVENTS`, `MANAGE_ACTIVITY_TASKS`, `ACTIVITY_EMBEDDING`, `CREATE_VIRTUAL_DEVICE`, `ADD_TRUSTED_DISPLAY`, `EMBED_ANY_APP_IN_UNTRUSTED_MODE`의 `granted=true`가 표시됐다. 현재 Assistant는 Lenovo assistant, HOME은 ZUI launcher였다. 이 역할을 바꾸지 않았고 display/task를 만들지 않았다. Loopy permission 행 부재는 확정적인 거부로 해석하지 않는다. 이는 ADB broker 후보의 사전 조건 일부이며 실제 cross-UID Binder 호출·창·입력·GPU 전달의 성공은 아니다. [실기기 조회 기록](../../build/diagnostics/y900-android-window-capabilities-20261008-01/receipt.json).

범위와 권한 경로를 선택한 뒤, 서로 다른 UID의 **소유한 host A + 공개 synthetic target B**로 검증한다. B는 계정·사용자 파일 없이 색상/nonce/버튼 카운터만 표시하며, 임의 앱 embedding을 주장하려면 B의 embedding opt-in 없이 검사한다. 협력 앱 경로는 opt-in arm으로 따로 기록한다.

- 정확한 APK/UID/task/display/host identity와 실제 frame·버튼·키 전달을 확인한다. 단순 외부 task 실행은 내부 표시 성공으로 기록하지 않는다.
- focus 전환, resize/회전, close, broker 끊김/재연결을 검증하고 역할·task·workspace·입력 상태를 복원한다.
- Hyprland 창을 목표로 삼으면 실제 compositor window identity, 이동·크기·z-order·AltTab과 Android task 수명을 함께 확인한다. Android pane/VirtualDisplay 성공을 그 증거로 승격하지 않는다.
- Notion 사용자 데이터·로그인·마이크·카메라·clipboard·일반 입력 관찰은 사용하지 않는다. 권한 거절 또는 OEM 미지원은 별도 결과로 남긴다.

초기 조사의 완료 범위는 소스/API와 연결 지점 확인이었다. 이후의 제한된 실제 VD 시험은 아래에 분리하며 native Hyprland 창 통합은 다음 단계다.

## 후속 실제 shell broker·Wayland 시험01–16

초기 조사 이후 기기 담당자가 UID2000 broker와 계정·사용자 데이터가 없는 공개 synthetic target을 실제 실행했다. 읽기 전용 context 대조에서 최초 `com.android.shell`/UID2000 context의 op-package가 `android`인 불일치를 확인했고, `ContextImpl.createAppContext`의 shell package/op-package/UID2000 일치는 통과했다. Loopy 앱 권한이나 Assistant/HOME 역할을 바꾼 결과가 아니다.

| 실제 실행 | 확인된 경계·전체 결과 |
| --- | --- |
| [inside01](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside01/receipt.json) | shell context package 식별 불일치에서 FAIL. |
| [inside02](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside02/receipt.json) | 소유한320×240 VD(display2) 생성 후 `Context.startActivity` 권한 거절로 FAIL. |
| [inside03](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside03/receipt.json) | 표준 IATM shell null-caller 실행 결과0. task 식별 검사에서 FAIL이며 당시 startup metadata가 없다. |
| [inside04](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside04/receipt.json) | 제한된 준비 대기 후 task168/display4/target UID10334의 component·UID·running·visible 식별 통과. 첫 공개 픽셀 패턴 대기에서 FAIL. |
| [inside05](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside05/receipt.json) | task169/display5 식별과 display state2, ImageReader 프레임12개 획득. 마지막 분류의 알려진 palette 수는 모두0이고76,800픽셀은 다른 opaque 값이었다. 검증된 픽셀·프레임 파일 내보내기는0이며 첫 공개 패턴 대기에서 FAIL. |
| [inside06](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside06/receipt.json) | task170/display6/target UID10336 식별 모두 통과, display state2와 이미지11개. 공개 중심 RGB 표본은 `C97C7A/E01E28/203BBC`이며 원본 `C98591/E02030/2040E0`과 달랐다. 고정 palette 일치0·프레임 내보내기0이며 첫 공개 패턴 대기에서 FAIL. |
| [inside07](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside07/receipt.json) | 소유한 공개 Android 앱의 task171/display7/UID10337 식별, 초기 픽셀·클릭1회·F12 1회, 프레임3개의 독립 호스트 전체 픽셀 검사 및 정리 모두 PASS. 초기 장면에서 한 번 고정한 profile로 후속 장면을 검사했다. Wayland/Loopy 내부 창 시험은 아니다. |
| [inside08](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside08/receipt.json) | App UID로 만든 공개 소스 파일의 SHA를 shell UID에서 읽어 창 실행 전 FAIL. target은 제거했고 설정118·서비스·역할·제품·기본 Loopy 포커스는 보존했다. 후속 검사는 App UID에서 정확한 SHA를 확인하고 소유한 파일2개의 전용 폴더만 정리했다. |
| [inside09](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside09/receipt.json) | Gtk/Gdk/GdkPixbuf는 사용 가능했으나 `GdkWayland 3` GI namespace 부재가 소유한 stderr에 기록됐다. broker·픽셀 단계에 도달하지 못했고 원래 포커스 창이 사라져 전체 FAIL. 설정118·서비스·역할·제품·기본 Loopy 포커스는 보존했다. |
| [inside10](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside10/receipt.json) | runtime GType·prgname과 class/PID/birth/UID·XWayland=false로 실제 관리된 GTK Wayland 창을 확인했다(PID26795, birth74554179, stableId402653198). broker task172/display8/UID10340의 첫 공개 프레임은 Java·독립 호스트 전체 검사를 통과했고307,200바이트를 GUI에 보냈다. `live-phase-0` timeout으로 FAIL. 당시 GUI 이벤트 로그가 없어 paint 대기·GTK 클릭 중 정확한 실패 위치는 미기록이며 클릭/F12·presentation도 미검증이다. |
| [inside11](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside11/receipt.json) | 실제 관리된 Wayland viewer PID6371/birth74572553/stableId402653199와 공개 Android task173/display9/UID10341을 확인했다. 첫 프레임의 Java·독립 호스트 전체 픽셀 검사 후 GUI 전송, 보존 이벤트의 `public-frame-painted frame_id=1`로 GTK draw callback을 확인했다. 하지만 클릭/F12 이벤트·broker relay 명령은0이고 `live-phase-0` timeout으로 전체 FAIL. 물리 presentation·상호작용 완료는 미검증이다. |


| 후속 실제 실행 | 확인된 경계·전체 결과 |
| --- | --- |
| [inside12](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside12/preflight-failure.json) | 최초 입력 상태 검사에서 AssertionError. 당시 JDI 출력은 보존되지 않았으며 target/VD/GTK 생성 전 중단했다. 후속 읽기 전용 상태는 정상이나 최초 원인은 미확정이다. |
| [inside13](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside13/receipt.json) | 실제 DrawingArea1280×846·content1128×846/x76와 최종 이동18의 cursor488,366을 확인했다. GTK 클릭 수신 대기 FAIL. 후속 보존 이벤트는 relay-output 종료이며 예외 위치는 미기록이다. 원래 포커스 창도 사라졌다. 소유 잔여 파일4개는 정확한 SHA/PID 부재 확인 뒤 별도 정리했다. |
| [inside14](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside14/receipt.json) | 좌표 pair 지원 viewer07을 사용했으나 클릭 송신 전 JDI stderr의 `Ignoring cmd 4/199/1 from the VM` 때문에 검사 중단/전체 FAIL. returncode0·완전한 정상 입력 상태가 함께 보존됐다. 창/프로세스/파일·task/display 정리, no_initial_window 복원·보존 검사는 통과했다. 클릭 수정의 실제 수락은 아니다. |
| [inside15](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside15/receipt.json) | 정확한 무시 메시지만 허용하고 완전한 상태 검사와 다른 stderr 거부를 유지했다. 실제 GTK press/release·F12, broker 명령2개, Android 화면 변경·프레임3개의 전체 픽셀 검사와 draw ACK는 본문 PASS. 원래 포커스 PID15666/birth74719119가 사라져 전체 FAIL을 유지했다. 소유 정리·118설정/서비스/역할/0589/기본 Loopy 포커스 보존은 통과했다. |
| [inside16](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside16/receipt.json) | 동일한 공개 Android 앱·실제 Wayland 표시·고정 클릭/F12·3프레임 검사와 정리에 더해 소유한 시험 터미널 PID31248/birth74777010/stableId402653210으로 복귀해 전체 PASS. 바깥 anchor 검사는 원래 화면 보호기 소실 때문에 기존 FAIL을 유지하며 제품 Notion/Chrome·임의 입력·성능 수락으로 확대하지 않는다. |

일곱 실행 모두 소유한 target/task와 생성한 display를 정리했고 설정118·서비스·역할·현재0589 제품·기본 Loopy 포커스를 보존했다. 01–06의 FAIL은 유지한다. 당시의 task/visible metadata·이미지 획득과 06 색상 표본을 공개 콘텐츠 검증 성공이나 최종 원인으로 승격하지 않는다.

기기 담당자의 읽기 전용 색상 조회는 NightDisplay activated=false·ColorMode300·global saturation=false·reduce bright=false였다. 설정은 바꾸지 않았고 이 관측으로 NightDisplay 원인을 추정하지 않는다. 07은 초기 공개 장면의 세 표본으로 제한된 채널별 gain을 한 번 고정하고, 모든 opaque RGBA 픽셀과 후속 green/yellow 장면을 같은 gain·1단위 residual 한계로 검사했다. Java의 전체 검사 후 원래 표시 바이트를 내보냈고 호스트는 initial부터 독립적으로 다시 검사했다. 이는 고정 공개 시험 장면의 수락이며 색상 처리 원인의 확정·생산 색상 보정·임의 앱 콘텐츠 허용이 아니다.

[inside08 정리](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside08-cleanup/receipt.json)는 실행 전 생성된 정확한 소스·FIFO 2개만 제거했다. [inside09 정리](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside09-cleanup/receipt.json)는 정확한 소유 inode를 연 App UID 프로세스가 없음을 확인한 뒤 소스·FIFO·로그 4개를 제거했다. 실패 receipt는 바꾸지 않았다.

10은 broker stdin EOF 뒤 task/display를 정리했고 viewer 창·프로세스·전용 폴더·target도 제거했다. 설정118·서비스·역할·제품·기본 Loopy 포커스는 보존했지만 원래 포커스 PID25936은 사라져 전체 FAIL을 유지한다. `live-phase-0`는 paint ACK 대기와 `gtk_click()`을 함께 포함한다. 당시 GUI 이벤트·stderr가 보존되지 않아 내부 실패 위치나 paint ACK 부재를 단정하지 않는다. 후속 읽기 전용 조회의 Cairo import·`gi.require_foreign` 사용 가능 결과도 10의 원인 증거가 아니다.

11의 [보존 이벤트](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside11/events.jsonl)는 소유 프로세스·ready·첫 프레임 draw ACK·owned-stop만 기록하며 [stderr](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside11/stderr.txt)는0바이트다. receipt에 묶인 두 hash를 대조했다. 세부 단계·포인터 위치 표본이 없어 phase0 timeout의 정확한 내부 원인은 귀속하지 않는다. broker EOF 이후 task/display·GTK 창/프로세스/폴더·target 제거, 원래 `no_initial_window` 작업공간/포커스 복원, 설정118·서비스·역할·제품0589·기본 Loopy 포커스 보존은 모두 통과했고 cleanup 오류는 없었다. 본문 완료와 전체 receipt는 FAIL로 남긴다.

[원본 GTK Wayland consumer](../../build/diagnostics/y900-android-wayland-view-20261008-01/README.md)는 공개320×240 RGBA를 stdin으로 받는 소스 준비물이다. 별도 후속11은 실제 Android 공개 앱의 첫 프레임을 실제 관리된 GTK Wayland 창의 draw callback까지 전달했다. 유한한 첫 프레임 prototype이며 클릭/F12 relay·전체 수명 연결의 수락에는 도달하지 못했다. 사용자 Notion/Chrome의 내부 실행, 로그인 콘텐츠, 실제 브라우저 호스팅이나 생산 성능 결과는 아직 없다.


[13의 base-event 조회](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside13-gdk-event-shapes/receipt.json)에서 get_coords는 bool+x+y triple이었다. [설치된 member-event 조회](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside13-gdk-member-shapes/receipt.json)는 EventButton.get_coords의 x+y pair, get_button/keyval의 bool+값 tuple을 확인했다. 설치된 Gdk.py SHA는48621ec6…다. 원본06 callback에 pair를 제공한 host RED와 viewer07의 pair/triple 경계·callback9개 및 실제15의 통과로 좌표 처리 결함 수정은 검증했다. 13에는 실제 callback 예외 종류/스택이 없어 그 실행의 정확한 예외 위치는 단정하지 않는다.

[13 후속 정리](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside13-cleanup/receipt.json)는 죽은 정확한 viewer PID와 class 부재, 원래 source/log SHA와 전용 폴더 파일4개를 확인했다. 실패 receipt를 다시 PASS로 바꾸지 않았다. 14의 [JDI 관찰](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside14/input-state-observations.jsonl)은 정상 상태/무시 메시지를 함께 기록하며, [OpenJDK source](../../build/diagnostics/y900-jdi-ddm-authority-20261008-01/source.json)의 unknown VM command 처리와 대조했다. 해당 exact message만 허용한 새 driver08은 returncode0·7개 고정 bool·input foreground/focus 조건을 그대로 요구한다.

향후 진단용 [focus02](../../build/diagnostics/future-focus-recovery-20261008-02/README.md)는 정확히 기록한 화면 보호기의 정상 종료와 일반 창 소실을 구분한다. 루트의 호스트9+14개 검사와 소스 봉인 대조는 통과했다. 실제16-anchor receipt를 다시 PASS로 바꾸거나 현재 제품의 창 처리 기능을 수정한 결과는 아니다. 현재0589의 별도 [그래픽 read01](../../build/diagnostics/y900-gdk-readpixels-runner-20261008-02/run-on-read01/receipt.json)은 출력 schema 사전 검사에서 실패해 측정 장면을 만들지 않았으며, 내부 창16의 통과를 성능 수락으로 확대하지 않는다.
