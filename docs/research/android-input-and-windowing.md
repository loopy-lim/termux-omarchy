# Android 입력·권한·창 관리 선례

조사일: 2026-10-05. 아래는 공식 문서와 소스 조사 결과다.
외부 앱을 설치하거나 Loopy Desktop 입력 코드를 구현한 결과가 아니다.
참조 버전은 [upstream-snapshot.json](upstream-snapshot.json)에 기록했다.

## Key Mapper: 키 정책과 시스템 제어 분리

[Key Mapper](https://github.com/keymapperorg/KeyMapper)는 키보드·마우스 버튼의 매핑,
길게 누르기·연속 누르기·조건부 실행을 제공한다.
우리의 Caps tap/hold 정책을 검토할 선례지만 트랙패드 전체 처리나 Wayland 서버는 아니다.
근거: [고정 버전 README](https://github.com/keymapperorg/KeyMapper/blob/dc70a64bdb17769d7a2632c381596d77dfb2d919/README.md).

현재 소스는 `sysbridge`와 Rust `evdev`를 분리한다.
`ISystemBridge.aidl`에는 장치 조회, grab 대상, evdev 쓰기, Android 입력 주입이 각각 있다.
`SystemBridge.kt`는 root 또는 shell UID를 확인하고 Binder 연결 종료 시 evdev 처리를 중단한다.
이는 **의미 입력 정책과 권한 있는 입력 어댑터를 나누는 근거**다.
근거: [AIDL](https://github.com/keymapperorg/KeyMapper/blob/dc70a64bdb17769d7a2632c381596d77dfb2d919/sysbridge/src/main/aidl/io/github/sds100/keymapper/sysbridge/ISystemBridge.aidl),
[SystemBridge](https://github.com/keymapperorg/KeyMapper/blob/dc70a64bdb17769d7a2632c381596d77dfb2d919/sysbridge/src/main/java/io/github/sds100/keymapper/sysbridge/service/SystemBridge.kt).

공식 [구조 설명](https://keymapper.app/contributing/codebase/)에는 이전 `priv` 모듈 설명도 남아 있다.
현재 구현 위치를 정할 때는 위 고정 소스를 기준으로 삼는다.
라이선스는 [GPL-3.0](https://github.com/keymapperorg/KeyMapper/blob/dc70a64bdb17769d7a2632c381596d77dfb2d919/LICENSE.md)이다.
이번에는 코드 대신 정책/어댑터 분리와 연결 종료 처리 방식을 참고한다.

## Shizuku: 선택 가능한 최소 권한 어댑터

[Shizuku](https://github.com/RikkaApps/Shizuku)는 ADB 또는 root로 시작한 프로세스의 Android API를 Binder로 연결한다.
[API의 UserService](https://github.com/RikkaApps/Shizuku-API/blob/a27f6e4151ba7b39965ca47edb2bf0aeed7102e5/README.md)는
Java/JNI를 별도 프로세스에서 실행할 수 있으나 일반 앱 Context와 같지 않으며 명시적 종료가 필요하다.
따라서 장치 조회·허용된 입력 주입처럼 필요한 작업만 인터페이스에 노출한다.

ADB 방식의 shell UID는 root가 아니다. API 문서도 UID 0/2000과 ADB 권한의 차이를 구분한다.
이번 VM의 shell `unshare/chroot` 거부가 Shizuku 설치만으로 해결될 것이라고 판단할 근거는 없다.
이는 [현재 VM 관찰](../device-capabilities.md)과 [Shizuku 권한 설명](https://github.com/RikkaApps/Shizuku/blob/b844bc491f1790c72328e1a8e5b2349f8978f0ea/README.md)을 연결한 판단이다.

Key Mapper는 Shizuku를 통해 기존 IME를 유지한 키 입력 등 추가 기능을 제공한다.
하지만 Y900의 evdev 접근·grab·원래 이벤트 억제·OEM 예약 단축키는 기능별 확인이 필요하다.
근거: [Key Mapper Shizuku 안내](https://keymapper.app/user-guide/shizuku/).
Shizuku 앱은 [Apache-2.0](https://github.com/RikkaApps/Shizuku/blob/b844bc491f1790c72328e1a8e5b2349f8978f0ea/LICENSE),
API 라이브러리는 [MIT](https://github.com/RikkaApps/Shizuku-API/blob/a27f6e4151ba7b39965ca47edb2bf0aeed7102e5/LICENSE)로 구분한다.

## libinput: 원시 트랙패드가 확인된 뒤의 후보

[libinput](https://wayland.freedesktop.org/libinput/doc/latest/what-is-libinput.html)은
입력 장치 해석과 quirks를 제공하지만 Wayland의 필수 의존성은 아니다.
원시 MT와 장치 FD 접근이 확인된 경우 트랙패드 어댑터 후보로 둔다.
Android 빌드나 Y900 지원은 아직 확인하지 않았다.

[제스처 문서](https://wayland.freedesktop.org/libinput/doc/latest/gestures.html)는
swipe/hold 이벤트를 제공하고 동작 해석을 호출자에 맡긴다.
관성 스크롤까지 모두 처리하는 완제품으로 간주하지 않는다.
일반 Android 앱의 스크롤 이벤트부터 사용하고 raw MT가 없는 장치에서는 없는 제스처를 제공한다고 표시하지 않는다.

## Taskbar: 나중 단계의 Android 데스크톱 셸 참고

[Taskbar](https://github.com/farmerbb/Taskbar/blob/e2a00b9a3f3adda069059abb9aebcb8b4e18954f/README.md)는
런처·최근 앱과 조건부 freeform/외부 화면 데스크톱 모드를 제공한다.
`libtaskbar`도 공개하지만 지원 여부와 설정은 Android 버전·제조사에 달려 있다.
Linux 창 브리지의 대체재가 아니며 MVP 0.3의 셸 참고 대상으로 둔다.
라이선스는 [Apache-2.0](https://github.com/farmerbb/Taskbar/blob/e2a00b9a3f3adda069059abb9aebcb8b4e18954f/LICENSE).

## Loopy Desktop에 반영할 판단

1. MVP 0.1은 포커스된 Linux Activity의 공개 Android 입력 경로부터 검증한다.
2. 키 상태 정책은 플랫폼과 분리한다. 장치 분리·포커스 상실·서비스 종료에서 눌린 키를 해제하고 중복 주입을 막는다.
3. 전역 키 제어는 접근성/IME와 선택적 Shizuku 어댑터를 기능별로 확인한 뒤 추가한다.
4. raw MT·권한이 확인된 경우에만 libinput 통합을 검토한다. Taskbar 기능은 초기 범위에 넣지 않는다.

구체적인 적용 순서는 [해결안](../solution-proposal.md), 실기기 기준은 [Y900 점검](../y900-test-checklist.md)에 있다.
