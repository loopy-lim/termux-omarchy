# Android Chrome 내부 입력 표면 진단 — 2026-10-08

관측된 종료 원인은 포커스 메타데이터의 창 종류 검사였다. 같은 Chrome UID의 추가 입력 표면을 일반 `IWindow` 포커스 증거처럼 검사하면서 `CAPTURE / inside-focus-window-type / sequence=2`로 종료됐다. 아래 수정은 관측된 입력 표면을 포커스 증거에서 제외한다. 입력 대상 UID나 기존 Android 작업 보호 조건을 넓히지 않는다.

수정 APK `d74dd1ecd39e1054766e4ff8ac43384457da1066c39bfd9f002042c0114115f4`의 빌드·서명·update-only 설치를 완료했다. [현재 설치18](../../build/diagnostics/y900-android-inside-product-update-20261008-18/receipt.json)은 설정 132개·입력 서비스·역할·마이크 거부·global Shizuku lifetime 보존을 확인한다. [Google Chrome 기기 시험08](../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-08/receipt.json)은 새 설치본에서 PASS다. 이전 실패와 관측 영수증은 당시 결과 그대로 보존한다.

## 실제 관측

[수동 네이티브 진단02](../../build/diagnostics/y900-inside-chrome-native-diagnostic-20261008-02/receipt.json)는 설치 APK `66d36ce37423e032eed1b59636c2c01540c497bf68a02784efd38a79b72250d0`에서 `CAPTURE`, `inside-focus-window-type`, 요청 순서 `2`를 확인했다. 분리된 검사 순서상 해당 실패까지 토큰 존재·양수 PID·대상 UID 검사는 통과했다. 이 코드만으로 표면의 프로세스 역할을 판별하지는 않는다.

[범위 제한 WindowInfos 관측02](../../build/diagnostics/y900-inside-chrome-window-observation-20261008-02/receipt.json)는 소유 lease `display=71 / task=261`에서 다음 동시 행을 기록했다.

| 메타데이터 | 일반 앱 창 | 추가 입력 표면 |
| --- | --- | --- |
| UID | 10313 | 10313 |
| PID | 5963 | 6132 |
| `layoutParamsType` | 1 | 0 |
| `inputConfig` | 0 | 2048 |
| visible / focusable / input channel | 모두 true | 모두 true |
| window token 존재 | true | true |

같은 표본에서 토큰 중복은 없었고, 실제 VD·SF 크기는 모두 `2512×1592`, 밀도는 `320`이었다. 관측기는 이름·화면·입력·토큰 값·앱 내용 대신 숫자와 불리언만 보존했다. 추가 PID가 Viz인지에 대한 별도 역할 검증은 없다. 관측 receipt의 PASS는 관측 범위·소유권·관측기 종료 확인이며, Chrome 기능 시험이나 canonical `CLOSED` ACK 성공을 뜻하지 않는다(`canonical_closed_ack=false`).

## 공식 플랫폼 경로

`2048`은 `DISABLE_USER_ACTIVITY = 1 << 11`이다. 입력 표면의 사용자 활동 갱신을 끄는 설정이며, 포커스·소유권 권한을 부여하는 플래그가 아니다. [AOSP InputConfig](https://android.googlesource.com/platform/frameworks/native/+/refs/heads/main/libs/input/android/os/InputConfig.aidl)

Android 16 `WindowManagerGlobal.createInputChannel`의 `grantInputChannel` 인자는 `inputFeatures=TYPE_APPLICATION(2)`, `type=0` 위치에 들어간다. `Session`의 실제 인자 순서와 `InputConfigAdapter`의 feature 변환을 함께 읽으면 이 factory에서 `type=0/config=2048` 조합이 만들어지는 경로가 설명된다. 이는 관측 조합과 일치하는 공식 소스 경로이며, 설치된 OEM 프레임워크의 바이트 동일성 검증은 아니다. [WindowManagerGlobal:894–904](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r2/core/java/android/view/WindowManagerGlobal.java), [Session:914–929](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r2/services/core/java/com/android/server/wm/Session.java), [InputConfigAdapter:48–54](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r2/services/core/java/com/android/server/wm/InputConfigAdapter.java)

네이티브 `AInputReceiver`가 같은 factory를 사용한다. Chromium의 고정 소스 `b5fbbfa53723e0c3a3401d55f58a796d1baa43b8`에서도 InputOnViz 경로가 자식 SurfaceControl과 브라우저 host transfer token으로 batched/unbatched 수신기를 만든다. 이 경로는 추가 입력 표면의 가능성을 뒷받침하지만, 관측된 PID 역할을 확정하지 않는다. [AOSP native receiver:154–184](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r2/native/android/surface_control_input_receiver.cpp), [JNI factory bridge:39–65](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r2/core/jni/android_view_WindowManagerGlobal.cpp), [Chromium input_manager:923–935](https://chromium.googlesource.com/chromium/src/+/b5fbbfa53723e0c3a3401d55f58a796d1baa43b8/components/viz/service/input/input_manager.cc)

WindowInfos의 JNI 변환은 `layoutParamsType`을 명시적으로 복사하므로 Java 필드 누락으로 0이 됐다는 설명은 공식 구현과 맞지 않는다. [InputWindowHandle JNI:223–246](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r2/core/jni/android_hardware_input_InputWindowHandle.cpp)

WMS의 `getWindowId`는 `mWindowMap`에 있는 일반 WindowState를 조회한다. embedded 입력 채널은 별도 `EmbeddedWindowController`에 등록된다. 따라서 추가 입력 표면을 일반 `IWindowId` 질의 대상으로 승인하는 방식은 피한다. [WMS getWindowId:2316–2319 및 grantInputChannel:9318–9330](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r2/services/core/java/com/android/server/wm/WindowManagerService.java)

## 수정 범위

[AndroidInsideFocus](../../android/src/dev/loopy/desktop/AndroidInsideFocus.java)는 API의 `DISABLE_USER_ACTIVITY` 값이 정확히 2048인지 확인한다. 소유 VD의 visible/focusable 입력 행마다 대상 UID, 비어 있지 않은 토큰, 양수 PID, 전체 활성 행 최대 64개, 토큰 유일성을 먼저 검사한다. 이후 **`type=0`이고 전체 `inputConfig` 값이 정확히 2048인 행만** 일반 창 포커스 증거 목록에서 제외한다.

일반 앱 창은 기존 capability 범위의 `WindowSession → IWindowId.isFocused` 질의를 그대로 통과해야 한다. 추가 입력 표면만 있거나 일반 창이 unfocused이면 false다. 다른 UID, null token, PID 0, 예상 밖 type/config, 토큰 중복은 계속 거부한다. 입력 주입의 대상 UID, 작업·VD 소유권, 포커스 전후 메타데이터 재확인, 기존 작업 정리 금지 조건은 변경하지 않았다.

## 회귀 시험과 증거 경계

[RED receipt](../../build/diagnostics/inside-embedded-focus-red-20261008-01/receipt.json)와 `test.log`는 실제 Focus listener의 `record → focused → decide` 경로를 플랫폼 test double로 실행했다. 7개 시험 중 5개가 기존 `inside-focus-window-type` 거부와 기대 동작 차이로 실패했고, 컴파일은 성공했다. [GREEN receipt](../../build/diagnostics/inside-embedded-focus-green-20261008-01/receipt.json)는 수정 소스에서 관련 30개 호스트 시험 성공을 기록한다.

시험은 일반 창+관측된 추가 표면의 일반 창 단독 질의, 추가 표면 단독·unfocused 거부, 다른 UID·잘못된 PID/토큰·type/config 거부, 중복·65개 활성 행 거부, 기존 필터·팝업 포커스, 질의 중 다른 UID로 바뀌는 메타데이터를 검증한다. 실제 SF/Binder·물리 키보드·마우스 동작은 이 호스트 시험의 증거 범위에 포함되지 않는다.

| 소스 핀 | SHA-256 |
| --- | --- |
| `AndroidInsideFocus.java` | `18efd73c32d47c5e122823ad1b19df5330878dbcad27dca186ae12f2005dd007` |
| `tests/test_inside_embedded_focus.py` | `c05e241f463e940a45426f70690f800965f2ea6aa366f39292ecb2ced0fa173f` |
| `tests/java/AndroidInsideEmbeddedFocusTests.java` | `bbc2e55ee129c152d4658abdc9989c594c115f8e2eec4ff96725ac5b16336827` |

앞선 [update15](../../build/diagnostics/y900-android-inside-product-update-20261008-15/receipt.json)는 당시 d806 APK 업데이트에서 설정 132개와 서비스·역할 보존을 확인했다. 이 역사적 보존 증거를 새 수정 APK의 보존 재검증으로 확대하지 않는다. 새 설치18과 Google 기기 시험08은 위에 별도 기록했다. 물리 입력·로그인·일반 사이트·장시간 사용·60/144fps 수락은 미완료다.

## 수정본 Google Chrome 기기 시험08

UID10313/version154.0.8037.126의 정확한 Main alias와 ChromeTabbedActivity를 새 소유 task263/display72 안에 열었다. 실제 설치된 GTK Session/Decoder/View 경로에서 OPENED와 포커스 ACK, `remote=true/input_enabled=true`, 2512×1592/density320을 확인하고 준비 완료 뒤 20초 동안 오류 없이 유지했다. FRAME 27개·디코드 27개·표시 복사 27개·같은 Pixbuf의 native Cairo source 선택 27개를 관찰했다. 압축 프레임과 raw fallback을 모두 수신했다. source 선택은 paint 이전 관측이므로 물리 패널 표시·FPS 증거로 확대하지 않는다.

정상 CLOSED ACK 1개와 task_removed/display_removed/inputs_released를 받았고, 검사 프로세스·GTK 창·VD·task·scope·metadata jar는 제거했다. 기존 작업·설정 132개·입력 서비스·역할·설치 APK를 보존했으며 cleanup_errors는 빈 목록이다. 물리 키보드/마우스 검사는 하지 않았고, 사용자 Google 프로필·탭 내용·화면 픽셀은 기록하지 않았다.

## 기존 Chromium 경로 회귀 시험09

[org Chromium 시험09](../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-09/receipt.json)도 같은 d74 설치본에서 PASS다. UID10372/version157.0.8093.0, task264/display73의 2512×1592/density320 창은 준비 후 20초 유지·ERROR 0·압축 FRAME 13개 디코드/복사/source 선택·정상 CLOSED와 소유 자원 정리를 통과했다. 기존 task·설정·서비스·역할·APK는 보존했다. 이 시험도 물리 입력·paint 완료·FPS·장시간 사용의 증거로 확대하지 않는다.
