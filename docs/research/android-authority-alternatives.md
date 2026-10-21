# Android 입력·권한 대체 경로

2026-10-06 조사. Android 공식 SDK 문서, Android 16 AOSP 소스, Shizuku의 공식 안내·API 저장소를 현재 Loopy Desktop 소스와 대조했다. 물리 Android 기기는 연결하지 않았으며 ADB 설정 쓰기, 권한 부여, root 실행, Device Owner 등록, 초기화는 수행하지 않았다. APK별 실행 증거는 [입력·권한·GPU 검증](../daily-use-gpu-validation.md)에 있다. 아래 고급 입력 backend는 별도 구현·기기 검증이 필요한 제안이며, 공개 설정과 대체 경로 안내는 `대체 방법` 패널에 구현했다.

실사용의 우선 경로는 **기존 Activity 입력 → 필요할 때 사용자 접근성 → 입력기·OEM 설정의 선택적 조정 → 별도 승인한 ADB/Shizuku → 전용 관리 기기 또는 root/OS 통합**이다. 이것은 모든 기능이 단계마다 자동으로 확장되는 순서가 아니다. 입력 관찰, 입력 소비, Android 다른 앱으로 주입, 홈 복귀, 알림, 절전 예외는 서로 다른 능력이다. Android는 runtime·signature·special 권한을 구분하며, signature 권한은 일반 사용자 승인으로 얻지 못한다. [Android 권한 종류](https://developer.android.com/guide/topics/permissions/overview#permission-types).

## 경로별 능력과 조건

| 경로 | 얻을 수 있는 능력 | 필요한 조건·수명 | 여전히 남는 경계 |
| --- | --- | --- | --- |
| 일반 Activity/View | 앱에 전달된 키·터치·generic motion을 Linux로 전달 | 데스크톱 View의 포커스·입력 연결. 현재 기본 경로 | 다른 앱의 입력을 전역으로 소유하지 않는다. Home 같은 프레임워크 전용 키는 일반 앱에 전달되지 않는다. [키 입력](https://developer.android.com/develop/ui/views/touch-and-input/keyboard-input/commands), [Home 키](https://developer.android.com/reference/android/view/KeyEvent.html#KEYCODE_HOME) |
| pointer capture | Android가 전달하는 마우스 상대 이동·버튼을 포커스 View에 집중 | API 26+, 포커스 있는 View 계층, 실제 capture callback 확인 | 알림·다른 앱·설정 창 등 포커스 상실 때 OS가 회수할 수 있다. 키보드·모든 터치 소스의 전역 캡처 권한이 아니다. [공식 pointer capture](https://developer.android.com/develop/ui/views/touch-and-input/gestures/movement#pointer-capture) |
| 사용자 Accessibility 키 필터 | 서비스에 도착한 물리 키를 앱보다 앞에서 소비하거나 통과시킴 | 사용자가 서비스를 켜고 시스템이 연결. `canRequestFilterKeyEvents`와 요청 flag 필요 | 이벤트 복사본 수정은 원본을 바꾸지 않는다. 일반적인 전역 key 재주입 API가 아니다. [서비스 수명·onKeyEvent](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#onKeyEvent(android.view.KeyEvent)), [필터 capability](https://developer.android.com/reference/android/accessibilityservice/AccessibilityServiceInfo#FLAG_REQUEST_FILTER_KEY_EVENTS) |
| Accessibility 모션 소유 | 선택한 mouse/touchpad source의 generic motion을 서비스로 전달 | API 34+, 연결된 서비스, `setMotionEventSources` 적용 | 선택 source는 나머지 시스템에 전달되지 않는다. source 지정만으로 장치가 보내지 않는 raw 접점을 만들 수 없다. [모션 callback](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#onMotionEvent(android.view.MotionEvent)), [source 지정](https://developer.android.com/reference/android/accessibilityservice/AccessibilityServiceInfo#setMotionEventSources(int)) |
| 사용자가 선택한 IME | 현재 입력 대상의 문자 조합·확정, 전달된 하드웨어 키 처리 | 별도 `InputMethodService` 구현·사용자 활성화/선택, 현재 InputConnection | 임의 다른 앱·보안 화면·OEM 예약 키 전체를 소유하는 경로가 아니다. 입력 대상이 없으면 연결도 없을 수 있다. [IME 작성](https://developer.android.com/develop/ui/views/touch-and-input/creating-input-method), [현재 입력 연결](https://developer.android.com/reference/android/inputmethodservice/InputMethodService#getCurrentInputConnection()) |
| ADB 또는 Shizuku shell | shell이 가진 권한으로 허용된 Binder 호출·설정·입력 주입 | 사용자가 디버깅을 승인하고, Shizuku는 앱별 승인과 살아 있는 Binder 필요. UID 2000 | 일반 앱에 shell 권한이 일괄 복사되는 것이 아니다. 다른 앱 데이터·전역 모션 관찰·OEM 정책은 별도 제한. [Shizuku API](https://github.com/RikkaApps/Shizuku-API#differents-of-the-privilege-betweent-adb-and-root), [AOSP Shell 권한](https://android.googlesource.com/platform/frameworks/base/+/android16-release/packages/Shell/AndroidManifest.xml) |
| Device Owner/DPC | 전용 기기의 lock task, 허용 앱·홈·runtime 권한 관리 | 관리용 DPC와 fully managed 등록. 일반 홈 역할과 별개 | `setPermissionGrantState`는 runtime 권한 관리이며 전역 입력 signature 권한 부여가 아니다. [DPC 권한 API](https://developer.android.com/reference/android/app/admin/DevicePolicyManager#setPermissionGrantState(android.content.ComponentName,java.lang.String,java.lang.String,int)), [lock task](https://developer.android.com/work/dpc/dedicated-devices/lock-task-mode) |
| root helper | 접근이 허용된 evdev 관찰, 지원되는 uinput 가상 장치 등의 별도 backend 후보 | 이미 확보한 root, 장치 노드·SELinux·커널 지원·명시적 운영 선택 | root도 SELinux 정책의 대상이다. 프레임워크/OEM 동작을 모두 없애거나 보안 화면 통제를 보장하지 않는다. [Android SELinux](https://source.android.com/docs/security/features/selinux), [getevent](https://source.android.com/docs/core/interaction/input/getevent), [Linux uinput](https://docs.kernel.org/input/uinput.html) |
| 플랫폼 서명·privileged/OEM 통합 | OS가 허용한 입력 필터·관찰·주입 또는 제조사별 단축키 정책 변경 | OEM/커스텀 OS 빌드, 해당 서명·allowlist·정책 또는 실제 OEM 설정 지원 | APK를 단순히 시스템 경로에 두는 것과 플랫폼 서명은 다르다. `INJECT_EVENTS`는 Android 16에서 signature, `MONITOR_INPUT`은 signature/recents다. [AOSP 권한 정의](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/core/res/AndroidManifest.xml#5565), [privileged allowlist](https://source.android.com/docs/core/permissions/perms-allowlist) |

## API 수명에 맞춘 운영

1. **마우스:** 요청과 획득을 분리한다. `requestPointerCapture()` 뒤 `onPointerCaptureChange(true)`/`hasPointerCapture()`가 실제 상태다. 포커스·전체 화면을 떠나면 반납하고 늦게 도착한 획득도 다시 해제한다. 비상 반납 뒤 장치 descriptor 갱신만으로 다시 캡처하지 않는다. 앞부분은 [공식 capture 수명](https://developer.android.com/develop/ui/views/touch-and-input/gestures/movement#pointer-capture), 뒷부분은 [현재 소유권 정책](../../android/src/dev/loopy/desktop/InputOwnershipPolicy.java)·[AUTO 정책](../../android/src/dev/loopy/desktop/AutoDockPolicy.java)의 제품 선택이다.
2. **접근성:** 설정의 활성화와 실제 서비스 연결을 구분한다. 사용자 비활성화·시스템 연결 상실 뒤 이전 객체를 유효한 권한으로 취급하지 않는다. 현재 서비스의 down/up 균형과 장치별 해제도 유지한다. [접근성 수명](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#ServiceLifecycle), [현재 서비스](../../android/src/dev/loopy/desktop/InputPriorityService.java).
3. **모션:** 화면을 소유할 때만 source를 설정하고 반납할 때 0으로 되돌린다. 캡처가 mouse를 View에 전달하면 접근성의 mouse 경로를 함께 사용하지 않는다. source mask는 공통 class bit 때문에 단순 비트 제거 대신 필요한 source를 다시 OR해서 만든다. touchscreen 소유나 touch exploration까지 확대하지 않는다. [source mask 규칙](https://developer.android.com/reference/android/accessibilityservice/AccessibilityServiceInfo#setMotionEventSources(int)), [touch exploration 예외](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#onMotionEvent(android.view.MotionEvent)).
4. **IME:** 사용자 선택과 현재 입력 대상에 종속된다. 현재 연결이 없거나 바뀌면 이전 대상에 문자를 보내지 않는다. 기존 IME로 전환하는 버튼과 문자 확정 경로를 우선 유지한다. [InputMethodService 연결](https://developer.android.com/reference/android/inputmethodservice/InputMethodService#getCurrentInputConnection()), [입력기 선택 API](https://developer.android.com/reference/android/view/inputmethod/InputMethodManager#showInputMethodPicker()).
5. **Shizuku:** 설치됨·서버 살아 있음·앱 승인됨·UID·작업별 성공을 각각 확인한다. Binder received/dead listener를 사용하며 죽은 Binder 호출은 피한다. ADB 시작은 재부팅 후 다시 시작해야 한다. Android 11+는 무선 디버깅, Android 10 이하 비root 경로는 PC 연결 안내가 기본이다. [Binder·승인 API](https://github.com/RikkaApps/Shizuku-API#acquire-the-binder), [공식 시작 안내](https://shizuku.rikka.app/guide/setup/).
6. **홈·알림·배터리:** 설정 화면을 열었다는 사실을 성공으로 기록하지 않는다. Activity 복귀 때 실제 role held·notification permission/app/channel·배터리 예외 상태를 다시 읽는다. 현재 패널이 이미 이 재확인을 수행한다. [홈 role API](https://developer.android.com/reference/android/app/role/RoleManager#createRequestRoleIntent(java.lang.String)), [현재 준비 패널](../../android/src/dev/loopy/desktop/DesktopPermissions.java).

## 실패 증상별로 계속 사용할 경로

아래 순서는 권고다. 각 단계에서 충분한 입력이 되면 더 높은 권한 경로를 요구하지 않는다.

| 막힌 기능·증상 | 먼저 사용할 대안 | 조건이 맞을 때의 추가 경로 | 실패 뒤에도 남길 기능 |
| --- | --- | --- | --- |
| Meta/Win chord가 Android/OEM 동작으로 빠짐 | 기본 Ctrl+Alt, 다른 modifier 설정, 앱 메뉴·작업공간 버튼. 선택한 chord의 Activity/접근성 도착 여부를 따로 측정 | 사용자 접근성 → 제조사 키보드 UI → 실제 지원 모델의 OEM 설정 → 별도 root/OS 입력 backend | 예약 키를 계속 재시도하기보다 전달되는 chord를 유지. Home은 홈 역할로 복귀시키는 대안이 있다. [키 입력](https://developer.android.com/develop/ui/views/touch-and-input/keyboard-input/commands), [Home 역할](https://developer.android.com/reference/android/app/role/RoleManager#ROLE_HOME), [현재 modifier](../../android/src/dev/loopy/desktop/InputSettings.java) |
| 일부 물리 키·한/영이 IME에 잡힘 | 현재 `onKeyPreIme` 경로와 Unicode commit을 확인. 사용자에게 물리 키보드 언어 설정·기존 입력기 선택을 제공 | Loopy 전용 IME 또는 API 33+ 접근성 InputMethod를 별도 구현 | soft IME는 KeyEvent를 항상 보내지 않으므로 문자 확정 경로를 제거하지 않음. [IME 하드웨어 키](https://developer.android.com/develop/ui/views/touch-and-input/creating-input-method#intercept_hardware_key_events), [soft 키 이벤트 한계](https://developer.android.com/reference/android/view/KeyEvent.html), [접근성 InputMethod](https://developer.android.com/reference/android/accessibilityservice/InputMethod) |
| 마우스 capture 요청 뒤 획득 안 됨 | 연결 장치·현재 source·View/창 포커스·Surface 상태 확인. 클릭해서 데스크톱 포커스를 복구하고 실제 callback을 확인 | fullscreen에서 명시적 재시도. API 34+ 접근성 mouse 전달은 별도 source 경로 | 일반 절대 hover/click/scroll과 직접 터치 사용. 요청 true로 성공을 가장하지 않음. [capture 조건](https://developer.android.com/develop/ui/views/touch-and-input/gestures/movement#pointer-capture), [현재 Surface](../../android/src/dev/loopy/desktop/DesktopSurface.java) |
| raw touchpad 접점/여러 손가락 제스처 없음 | generic scroll·클릭·포인터 이동을 사용하고 source/axis/pointer count를 선택적 진단 | API 34+ 접근성 TOUCHPAD → 장치가 지원하면 captured touchpad → 전용 USB HID 또는 허용된 root evdev | 제조사 드라이버가 이미 cursor/scroll로 해석한 정보를 raw 접점으로 복원할 수 있다고 주장하지 않음. [장치 분류](https://source.android.com/docs/core/interaction/input/touch-devices), [source 요청의 no-op](https://developer.android.com/reference/android/accessibilityservice/AccessibilityServiceInfo#setMotionEventSources(int)) |
| 접근성 거부·연결 대기·제한된 설정 | 일반 Activity 입력으로 계속 사용. 사용자가 준비 패널을 다시 열면 설정/앱 정보 안내 | Android 13+에서 사용자가 신뢰 여부를 판단한 뒤 ‘제한된 설정 허용’, 이후 접근성 활성화 | 재진입마다 자동 승인 창·반복 요구 없음. connected 확인 전 전역 단축키 준비 완료로 표시하지 않음. [제한된 설정](https://support.google.com/android/answer/12623953?hl=en), [거부 후 기능 축소](https://developer.android.com/training/permissions/requesting#handle-denial) |
| 세션 알림 없음 | 앱 내 데스크톱/종료 버튼·최근 앱으로 복귀. Linux 사용 유지 | API 33+ 최초 사용자 요청 → 사용자가 다시 선택하면 앱 알림 설정 → 차단된 `desktop_session` 채널 설정 | `POST_NOTIFICATIONS` 거부만으로 FGS 시작을 막지 않음. FGS notice는 Task Manager에 남지만 drawer action은 없을 수 있음. [알림 권한](https://developer.android.com/develop/ui/compose/notifications/notification-permission), [채널 설정](https://developer.android.com/reference/android/provider/Settings#ACTION_CHANNEL_NOTIFICATION_SETTINGS) |
| 다른 앱·화면 꺼짐 뒤 작업 중단 | 서비스 생존과 process exit reason을 확인, 작업 저장. 사용자가 선택할 때 절전 예외/OEM 배터리 화면 안내 | 필요한 동안의 사용자 인지 가능한 FGS·선택적 배터리 예외. 계속 살아 있어야 하는 작업은 별도 서버 세션도 후보 | 예외가 메모리 회수·사용자 Stop·force-stop 뒤 Linux RAM을 복원하지 않음. WorkManager를 실행 중 데스크톱의 RAM 대체물로 취급하지 않음. [Doze 예외 범위](https://developer.android.com/training/monitoring-device-state/doze-standby#support_for_other_use_cases), [사용자 Stop](https://developer.android.com/develop/background-work/services/fgs/handle-user-stopping) |
| Home을 눌러 기존 launcher로 이동 | 준비 화면의 선택적 기본 홈. 거부하면 최근 앱·앱 아이콘·허용된 세션 알림으로 돌아옴 | API 29+ available/unheld이면 role 요청, API 28/unsupported이면 Home settings. 전용 관리 기기에는 DPC persistent Home/lock task 후보 | HOME 후보 등록과 실제 role held를 분리. 홈 역할로 모든 시스템 키를 가로챈다고 주장하지 않음. [RoleManager](https://developer.android.com/reference/android/app/role/RoleManager), [Home settings](https://developer.android.com/reference/android/provider/Settings#ACTION_HOME_SETTINGS), [전용 기기 홈](https://developer.android.com/work/dpc/dedicated-devices/cookbook#custom-launcher) |

## 고급 경로를 선택할 때의 실제 범위

### ADB/Shizuku는 주입과 관찰을 나눠 검사한다

Android 16의 shell은 `INJECT_EVENTS`를 선언한다. InputManagerService의 주입 API는 이 권한을 확인하지만, 전역 pointer monitor는 별도의 `MONITOR_INPUT`을 요구한다. 조사한 Shell manifest에는 후자가 없다. 따라서 **shell 주입 성공은 물리 키 interception·raw 접점 관찰 성공의 증거가 아니다**. OEM의 추가 제한도 실제 호출 결과로 확인해야 한다. [Shell manifest](https://android.googlesource.com/platform/frameworks/base/+/android16-release/packages/Shell/AndroidManifest.xml), [주입·monitor 권한 검사](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/services/core/java/com/android/server/input/InputManagerService.java#992).

선택적 Shizuku backend를 추가한다면 사용자 승인 후 UserService에서 제한된 작업만 제공하고, UID 2000/0·Binder 생존·Android 버전·작업별 결과를 표시한다. 연결 상실 시 큐를 멈추고 해당 backend가 소유한 입력을 정리하는 설계가 필요하다. 비SDK API를 사용하는 UserService는 정상 Android 앱 process가 아니므로 일반 Context API도 그대로 기대하면 안 된다. **현재 Loopy Desktop에는 Shizuku 통합이 없다.** [Shizuku UserService 설명](https://github.com/RikkaApps/Shizuku-API#userservice), [현재 manifest](../../android/AndroidManifest.xml).

ADB의 `install -g`도 실제 Android 16 shell 구현에서 runtime permission 부여 옵션이다. manifest의 모든 이름을 signature·접근성 사용자 선택·홈 역할·배터리 예외로 변환하는 ‘grant all’ 기능이 아니다. 지금 필요한 알림은 사용자 요청으로 해결하고, 입력 주입 때문에 일반 APK에 `INJECT_EVENTS`를 추가해 `pm grant`로 얻을 수 있다고 안내하지 않는다. [PackageManager shell 도움말](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android16-release/services/core/java/com/android/server/pm/PackageManagerShellCommand.java#4776), [signature 권한 규칙](https://developer.android.com/guide/topics/permissions/overview#signature_permissions).

### IME와 접근성의 문자 API는 선택적 편집 경로다

현재 앱은 IME를 **제공**하지 않고 기존 Android IME의 [DesktopInputConnection](../../android/src/dev/loopy/desktop/DesktopInputConnection.java) 입력을 **받는다**. 전용 IME는 한/영 조합과 특정 editor의 물리 키 처리 대안이지만 사용자의 기존 입력기를 교체하는 선택이 필요하다. API 33+ Accessibility InputMethod도 문자 편집 대안이며 현재 서비스에 요청 flag가 없다. 둘 다 우선 해결해야 할 구체적인 문자 문제 없이 기본 의존성으로 추가할 이유는 적다. [IME 서비스 선언](https://developer.android.com/develop/ui/views/touch-and-input/creating-input-method#declare_ime_components_in_the_manifest), [Accessibility InputMethod](https://developer.android.com/reference/android/accessibilityservice/InputMethod), [현재 접근성 XML](../../android/res/xml/input_priority.xml).

### OEM 설정·하드웨어 변경은 기기별 경로다

물리 키보드 설정 UI는 API 24+ `ACTION_HARD_KEYBOARD_SETTINGS`로 열 수 있지만 화면 존재와 remap 항목은 기기별이다. 설정에서 언어/레이아웃을 바꾸는 것과 예약 chord 정책을 끄는 것은 구분한다. 사용자 키보드가 firmware/Fn remap을 제공한다면 OS에 들어오는 chord 자체를 바꾸는 것도 후보지만, 해당 하드웨어의 지원 확인이 필요하다. 후자의 효과는 Android의 키 매핑 위치에 근거한 설계 추론이다. [설정 intent](https://developer.android.com/reference/android/provider/Settings#ACTION_HARD_KEYBOARD_SETTINGS), [AOSP key layout](https://source.android.com/docs/core/interaction/input/key-layout-files).

현재 [lenovo_input.py](../../tools/lenovo_input.py)는 명시적 serial의 **non-VM Lenovo TB570 계열, user 0**만 쓰기를 허용하고 `keyboard_combo_win_e`, `keyboard_combo_win_i`, `keyboard_combo_win_s`, `keyboard_combo_win_number` 네 항목만 다룬다. `inspect`는 읽기 전용이다. `disable`은 원본 snapshot을 먼저 별도 파일에 보존하고 0 쓰기를 검증하며, `restore`는 다른 기기·사용자·후속 변경 충돌을 거부한다. 이것은 소스의 현재 동작이다. 키가 없는 기기에 0을 쓰는 것이 실제 OEM 기능을 끈다는 물리 증거는 없고, TB710·Win+L·다른 제조사 지원도 현재 계약에 없다.

물리 기기 연결 뒤 먼저 사용자 키보드 UI와 아래 읽기 전용 진단 결과를 검토한다. 설정 쓰기는 실제 OEM 효과와 원복 가능성을 확인한 다음 별도로 승인된 작업으로 수행한다. 이번 조사에서는 실행하지 않았다.

```sh
./dev/lenovo-input inspect --serial <PHYSICAL_ADB_SERIAL>
./dev/device-check --serial <PHYSICAL_ADB_SERIAL> --expect-manufacturer lenovo
```

### 전용 USB HID·root·OS 통합은 별도 제품 선택이다

USB host API는 사용자가 지정 USB 장치 접근을 허용하면 endpoint 통신을 할 수 있다. HID 보고서를 앱이 직접 해석하는 backend는 후보지만 일반 Android input stream과 다르다. `claimInterface(force=true)`는 기존 kernel driver를 분리할 수 있어 기존 키보드/포인터 동작과 복귀 검증이 필요하다. Bluetooth·내장 입력 기기로 자동 확대되는 경로도 아니다. **현재 USB HID 직접 reader는 미구현이다.** [USB 사용자 승인](https://developer.android.com/develop/connectivity/usb/host#obtaining-permission), [interface claim](https://developer.android.com/reference/android/hardware/usb/UsbDeviceConnection#claimInterface(android.hardware.usb.UsbInterface,boolean)).

root helper는 허용된 `/dev/input/event*`를 읽거나 지원되는 `/dev/uinput`에 출력하는 별도 설계가 가능하다. 장치 grab·반복·down/up·disconnect·helper death·SELinux를 모두 다뤄야 한다. 독점 grab 뒤 helper가 죽어도 Android 조작을 복구할 수 있는 수단을 먼저 설계한다. 커널에 없는 다중 접점이나 GPU 드라이버를 권한만으로 만들지는 못한다. [getevent의 커널 이벤트](https://source.android.com/docs/core/interaction/input/getevent), [uinput 요구 경로](https://docs.kernel.org/input/uinput.html), [root에도 적용되는 SELinux](https://source.android.com/docs/security/features/selinux).

Device Owner는 전용 관리 기기에 적합하다. 정식 fully managed 등록은 새 기기/초기화 후 setup에서 이루어진다. 공식 개발용 예외는 계정 없는 기기에 별도 DPC를 설치한 뒤 ADB로 등록하는 경로다. 현재 APK는 DPC가 아니며 사용 중 개인 태블릿을 자동으로 초기화하거나 관리 등록하지 않는다. 플랫폼 서명·privileged 통합은 별도 OS 배포 계약이고, 일반 설치 APK의 runtime 권한 확장이 아니다. [관리 등록 조건](https://source.android.com/docs/devices/admin), [개발용 DPC 예외](https://developer.android.com/work/dpc/dedicated-devices/cookbook#development-setup), [privileged allowlist](https://source.android.com/docs/core/permissions/perms-allowlist).

이미 root가 없는 기기를 새로 root/커스텀 OS로 바꾸는 일은 이번 범위에 포함하지 않는다. Android의 bootloader unlock 절차는 사용자 데이터 삭제를 수반한다. 이 경로를 ‘입력 권한 설정’ 버튼으로 숨기거나 자동 실행하지 않는다. [공식 unlock 데이터 경계](https://source.android.com/docs/security/features/verifiedboot/boot-flow#unlock_confirmation).

## 현재 구현과 다음 진단·안내

권한 준비의 `대체 방법`은 실제 접근성 설정/연결 상태를 구분하고, 물리 키보드 설정·기존 입력기 선택·권한 준비 복귀와 고급 경로의 조건을 제공한다. 설정 화면 부재는 일반 Android 설정으로 한 번 대체하며, 두 경로가 실패해도 Linux 세션을 종료하지 않는다. Shizuku/root/DPC/USB HID는 안내이며 연결됨으로 표시하지 않는다. 소스 구현과 APK·물리 수락은 구분하고, 패키지별 결과는 위 검증 문서에서 확인한다.

| 현재 지점 | 현재 동작 | 다음으로 추가할 작은 사용자 경로 |
| --- | --- | --- |
| [DesktopPermissions](../../android/src/dev/loopy/desktop/DesktopPermissions.java)·[DesktopAlternatives](../../android/src/dev/loopy/desktop/DesktopAlternatives.java) | 첫 물리 입력 연결에 1회 안내, 수동 재열기, 설정 복귀/live 상태, `대체 방법`의 [hardware settings](https://developer.android.com/reference/android/provider/Settings#ACTION_HARD_KEYBOARD_SETTINGS)·[IME picker](https://developer.android.com/reference/android/view/inputmethod/InputMethodManager#showInputMethodPicker()), 설정 실패 fallback | 별도 `입력 진단`에서 현재 source·획득 상태·선택한 chord의 도착 단계만 표시 |
| [Linux GL 상태](../../android/src/dev/loopy/desktop/GuestGraphicsStatus.java) | 준비/대체 패널은 현재 세션의 픽셀 검사 스냅샷만 읽고 Android 화면 렌더러와 구분. 게스트 메뉴의 `GPU alternatives / check`는 CPU GL 창 전달 검사 경로 | CPU 픽셀 검사·실제 GUI 전달·하드웨어 GPU 가속을 서로 다른 증거로 기록. Android GLES 성공을 게스트 GPU 수락으로 확대하지 않음 |
| [DesktopSurface](../../android/src/dev/loopy/desktop/DesktopSurface.java) | 실제 capture 상태·포커스·마우스 능력에 따라 요청/반납, pre-IME와 문자 입력 분리 | `요청 중/획득/반납/포커스 없음/마우스 없음`과 선택한 장치 source 표시. 획득 실패 때 클릭·터치 대안을 먼저 제공. [capture callback 계약](https://developer.android.com/develop/ui/views/touch-and-input/gestures/movement#pointer-capture) |
| [InputPriorityService](../../android/src/dev/loopy/desktop/InputPriorityService.java) | 키 필터 연결 확인, API 34+ 전체 화면 source 요청, mouse 중복 방지, 장치별 해제 | 사용자가 선택한 chord만 짧게 검사해 `접근성 도착/앱 도착/Linux 처리`를 구분. 선택하지 않은 입력 내용은 기록하지 않는 진단 설계. 전달 안 된 물리 chord를 synthetic 주입으로 합격시키지 않음. [필터 복사본 계약](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#onKeyEvent(android.view.KeyEvent)) |
| [DesktopPermissions 알림](../../android/src/dev/loopy/desktop/DesktopPermissions.java) | runtime 권한·앱 알림·채널 importance를 확인하지만 표시 문구·버튼은 합쳐짐 | `권한 거부/앱 알림 차단/세션 채널 차단`을 구분하고 마지막 경우 `desktop_session`의 채널 설정으로 연결. [채널 설정 extras](https://developer.android.com/reference/android/provider/Settings#ACTION_CHANNEL_NOTIFICATION_SETTINGS) |
| [DesktopPermissions 접근성](../../android/src/dev/loopy/desktop/DesktopPermissions.java) | 꺼짐/설정됨·연결 대기/연결됨 구분, 제한된 설정 앱 정보 안내 | 한 번 거부한 뒤 자동 재요구 없이 `현재 앱에서 사용 가능`, 사용자가 누른 재설정, 연결 상태 재확인을 제공. [거부 존중](https://developer.android.com/training/permissions/requesting#handle-denial), [제한된 설정](https://support.google.com/android/answer/12623953?hl=en) |
| [DesktopSessionService](../../android/src/dev/loopy/desktop/DesktopSessionService.java) | `specialUse` FGS, 사용자 종료, `START_NOT_STICKY`, RAM 복구를 가장하지 않음 | 예기치 않은 종료 뒤 API 30+ ApplicationExitInfo 원인과 저장된 작업 복귀 안내. 배터리 예외와 OEM 절전 안내는 선택. `specialUse`를 Play 심사 승인·불사 서비스로 표현하지 않음. [specialUse 조건](https://developer.android.com/develop/background-work/services/fgs/service-types#special-use), [사용자 Stop 진단](https://developer.android.com/develop/background-work/services/fgs/handle-user-stopping) |
| [Home 설정](../../android/src/dev/loopy/desktop/DesktopPermissions.java) | ROLE_HOME 요청, 지원 안 됨/기존 held에서 Home settings fallback, 복귀 후 실제 상태 | `후보 등록/사용자가 선택함/다른 홈`을 구분해 선택 실패도 정상 사용 상태로 유지. [role availability·consent](https://developer.android.com/reference/android/app/role/RoleManager) |
| [lenovo_input](../../tools/lenovo_input.py) | 기기 판별·명시적 serial·snapshot·충돌 검사·읽기 전용 inspect | UI에는 현재 지원 조건·읽기 전용 검사 명령과 원복 필요를 안내. 설정 키 또는 모델 확대는 새 소스 근거와 물리 before/after 검증 후 별도 변경 |

추천 실행 순서는 위 표의 **기존 패널 진단·설정 CTA → 실제 기기에서 전달 단계 확인 → 해당 증상에 필요한 선택 backend**다. Shizuku/IME/root를 동시에 새 기본 경로로 만드는 일은 피한다. 런타임 호출 실패나 설정 화면 부재는 Linux 세션을 끝내지 않고 해당 항목을 사용할 수 없다는 상태와 남은 입력 경로를 보여준다. 거부 후 안내는 사용자가 그 기능을 다시 선택할 때 제공하며 반복 승인 요구로 바꾸지 않는다. [Android의 기능 축소·거부 처리](https://developer.android.com/training/permissions/requesting#handle-denial).

## 경로별 합격 증거

- **일반 입력/capture:** 물리 장치 ID·source와 실제 Android callback, capture 획득/반납, Linux 동일 앱의 동작을 함께 기록한다. 요청 성공·주입 입력만으로 물리 수락을 대신하지 않는다. 비상 `Ctrl+Alt+Esc`, 설정 열기, 앱 전환, source-only 갱신, 분리·재연결에서도 held 입력 균형을 확인한다. [현재 물리 점검표](../y900-test-checklist.md).
- **접근성/IME/홈/알림:** 사용자가 실제 승인하거나 거부한 결과, 현재 연결/선택 상태, 준비 패널로 돌아온 결과를 각각 기록한다. 첫 안내 취소, 영구 거부, 채널 차단, OEM 설정 화면 부재, 서비스 끊김을 별도 조건으로 시험한다. [현재 권한 증거의 한계](../daily-use-gpu-validation.md).
- **Shizuku:** 서버 시작 방식·UID·앱 승인·Binder death·재부팅 후 복귀·주입/관찰 작업별 결과를 분리한다. 실패하면 기존 Activity 입력이 계속 가능해야 한다. [공식 API 수명](https://github.com/RikkaApps/Shizuku-API#acquire-the-binder).
- **OEM/root/DPC/OS 통합:** 별도 기기·OS 버전·전후 설정·복원 receipt·실제 물리 입력을 요구한다. 일반 Android VM 결과를 이 경로의 수락으로 확대하지 않는다. 신규 root, 사용자 데이터 초기화, Device Owner 등록은 자동 시험의 일부로 실행하지 않는다.

권한 확대가 입력 전달이나 세션 생존을 자동으로 증명하지 않는다. 사용할 수 있는 기본 경로를 유지하면서, 실패한 능력 하나에 맞는 대안을 선택하고 그 조건에서 실제 결과를 남기는 것이 이 문서의 실행 기준이다.
