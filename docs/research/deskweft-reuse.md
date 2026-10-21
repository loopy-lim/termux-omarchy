# Deskweft 재사용 조사 (2026-10-05)

## 확인 범위와 결론

로컬 원본은 `/Users/loopy/dev/ll3/deskweft`에 있다. 이 저장소의 Android 앱은 키보드 리매핑·설정 앱이며, macOS 배경·창 관리 제품에 결합되어 있다. Android 안에서 Linux Wayland/Sway 화면을 실행하거나 Android Surface로 출력하는 구현은 없다. 따라서 Loopy Desktop의 디스플레이·세션·런처 구현을 대체하는 코드는 찾지 못했다. [Deskweft README 9–20행](/Users/loopy/dev/ll3/deskweft/README.md:9), [Android 출처 22–26행](/Users/loopy/dev/ll3/deskweft/android/PROVENANCE.md:22).

## 입력 우선권에서 가져올 수 있는 것

- [RemapService 70–94행](/Users/loopy/dev/ll3/deskweft/android/app/src/main/java/dev/loopy/keybridge/RemapService.kt:70)은 AccessibilityService `onKeyEvent`에서 외부 물리 키보드·SOURCE_KEYBOARD·DOWN/UP만 받아 Rust 리매퍼로 보낸다. [접근성 XML 1–8행](/Users/loopy/dev/ll3/deskweft/android/app/src/main/res/xml/accessibility.xml:1)은 `flagRequestFilterKeyEvents`와 `canRequestFilterKeyEvents`를 둘 다 선언한다. Loopy Desktop도 이 권한 조합을 이미 선언했다. Deskweft는 Meta의 모든 OEM 단축키를 반드시 회수했다는 물리 입력 증거는 제공하지 않는다.
- [ShortcutProbe 3–34행](/Users/loopy/dev/ll3/deskweft/android/app/src/main/java/dev/loopy/keybridge/ShortcutProbe.kt:3)은 사용자가 선택한 한 chord를 접근성 서비스와 앱 단계에서 별도로 관찰하고, 장치 ID·키 코드·기한·down/up을 구분한다. [검증 테스트 15–44행](/Users/loopy/dev/ll3/deskweft/android/app/src/test/java/dev/loopy/keybridge/ShortcutProbeTest.kt:15)은 다른 장치/숫자 이벤트를 합쳐 성공 판정하지 않는다. Loopy Desktop의 실기기 우선권 진단에 이 **증거 분리 방식**을 참고할 수 있다. 주입 이벤트는 물리 Meta 키 회수 증거가 아니다.
- [RemapService 142–157행](/Users/loopy/dev/ll3/deskweft/android/app/src/main/java/dev/loopy/keybridge/RemapService.kt:142)은 입력 장치 제거/변경 시 해당 장치가 소유한 눌린 키를 해제한다. Loopy Desktop에는 `InputPriorityService`의 `InputManager.InputDeviceListener` → `KeyCapturePolicy.clearDevice` / `DesktopSurface.releaseDevice` → `KeyboardRouter.releaseDevice` 경로와 회귀시험을 연결했다. 실제 Y900 장치 분리 시험은 별도다.

## 기기 설정과 세션 경계

- [LenovoShortcutPolicy 5–14행](/Users/loopy/dev/ll3/deskweft/android/app/src/main/java/dev/loopy/keybridge/LenovoShortcutPolicy.kt:5)은 Win+E/I/S/숫자 OEM 설정 키만 허용한다. [LenovoSettingsShell 11–35행](/Users/loopy/dev/ll3/deskweft/android/app/src/main/java/dev/loopy/keybridge/LenovoSettingsShell.kt:11)은 Shizuku/ADB shell 권한으로 `settings system` 값을 읽고 명시적으로 변경·복원한다. 이는 보통 앱 권한의 해결책이 아니며 제조사별·기기별 행위다. Loopy Desktop 기본 작동의 전제 조건으로 이 설정 쓰기를 편입하지 않는 편이 맞다.
- [Bridge 52–90행](/Users/loopy/dev/ll3/deskweft/android/app/src/main/java/dev/loopy/keybridge/Bridge.kt:52)은 연결 세대 번호로 오래된 비동기 결과를 버리고 연결 상실 시 소유한 키 출력만 정리한다. Loopy Desktop은 입력 서비스의 소유 키 up 균형, 데스크톱 세션 UUID별 IPC 무시와 같은 원칙을 이미 적용 중이다. Shizuku Binder 서비스·주입 파이프라인 자체는 Loopy Desktop의 로컬 Linux compositor 입력 경로와 다르다.
- Deskweft Android의 `launch:editor`는 [TomlConfig 62–76행](/Users/loopy/dev/ll3/deskweft/android/core/src/main/kotlin/dev/loopy/keybridge/core/TomlConfig.kt:62)의 Android package intent이며, [RemapService 96–104행](/Users/loopy/dev/ll3/deskweft/android/app/src/main/java/dev/loopy/keybridge/RemapService.kt:96)에서 Android 앱을 시작한다. Linux `.desktop` 파일이나 Sway launcher는 아니다.
- Deskweft Android 앱에는 `onMotionEvent`, `setMotionEventSources`, SOURCE_TOUCHPAD 원시 다중 접점 또는 Linux 데스크톱 터치패드 제스처 처리가 없다. 따라서 Loopy Desktop의 API 34 접근성 모션 소스 경로를 Deskweft 실행 경험으로 검증했다고 볼 수 없다. 확인 위치: [Android 앱 소스](/Users/loopy/dev/ll3/deskweft/android/app/src/main/java/dev/loopy/keybridge/RemapService.kt:23), [접근성 XML](/Users/loopy/dev/ll3/deskweft/android/app/src/main/res/xml/accessibility.xml:1).

## 라이선스·검증 한계

Deskweft 자체 [루트 LICENSE](/Users/loopy/dev/ll3/deskweft/LICENSE:1)는 MIT다. 다만 Android 코드는 [KeyBridge 고정 커밋 출처](/Users/loopy/dev/ll3/deskweft/android/PROVENANCE.md:1)에서 들여왔으며 원본 커밋에는 루트 라이선스 파일이 없다고 출처 문서가 명시한다(28–31행). 이 조사에서는 코드를 복사하지 않고 설계·검증 패턴만 참고했다. Deskweft의 Shizuku, OEM 설정 쓰기, Mac→Android UHID helper는 각각 별도 권한·전송 경로이므로 Loopy Desktop의 일반 Android 공개 SDK 기능으로 설명하면 안 된다. [입력 공유 안내 39–43행](/Users/loopy/dev/ll3/deskweft/docs/INPUT_SHARING.md:39).
