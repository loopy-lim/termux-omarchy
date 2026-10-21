# Y900 Alt 확대·축소와 화면 복귀 수정

현재 설치 APK는 `1790152c9593ce835b2aaf4adbe18cd8a240a2870a8f1d52a03541f64c79f611`다. [설치20](../../build/diagnostics/y900-android-inside-product-update-20261008-20/receipt.json)은 설정132개·서비스·역할 보존을 통과했다. partial writer의 호스트 증거, 제한된 합성 ACK 표본과 사용자 체감 피드백은 [최신 입력 지연 기록](2026-10-08-inside-input-latency.md)으로 연결한다. 아래 확대·축소와 물리 복귀 기록은 각 당시 APK의 증거이며1790에서 재측정한 결과로 옮기지 않는다.

2026-10-08, 대상 ADB `Y900` / Lenovo `TB522FU`만 확인했다.

## 이전5089 설치 상태

당시 APK는 [초기 URL 수정본](../../build/deliverables/LoopyDesktop-2026-10-08-inside-browser-url-arm64/app.apk) `5089f5dd4868add6dcad8a778eed077588564252ecaae384439a8b1fa5005dc7`였다. [설치19](../../build/diagnostics/y900-android-inside-product-update-20261008-19/receipt.json)은 설정132개·서비스·역할을 보존했다. native7개와 Android 키보드/Surface 핵심 소스는 이전d74와 같다. 초기 URL Python 경로는 변경됐다. 아래 확대·축소 실측은 d806 당시 증거이며 새 APK에서 물리 입력·화면 복귀를 재측정했다고 표시하지 않는다. [Chrome/URL 보고서](2026-10-08-inside-browser-url.md)와 [입력 지연](2026-10-08-inside-input-latency.md)을 구분한다.

## 이전 d806 상태

설치한 APK: [tablet-input-resume-02-arm64/app.apk](../../build/deliverables/LoopyDesktop-2026-10-08-tablet-input-resume-02-arm64/app.apk).
SHA-256: `d8066741ef26d04b409990970c906e261eecb10a908bed84e26576b8f68b0388`.
사용자가 현재 작업 저장과 업데이트를 승인한 뒤 update-only 설치했다. [설치 receipt](../../build/diagnostics/y900-android-inside-product-update-20261008-15/receipt.json)는 설정 132개, KeyBridge·Leftcar 서비스, 앱 역할, 마이크 거부와 global Shizuku lifetime 보존을 확인했다. 초기 후보 `f6239b13…`는 설치하지 않은 역사적 산출물로 남긴다.
사용자가 다시 Alt++ 문제를 보고했을 때 기존 Foot PID 4508은 mapped native Wayland 창으로 살아 있었다.

## 원인과 변경

- 기존 Hyprland 확대 명령의 `plus` keysym은 unshifted keycode 조회에서 실패했다. Foot에는 `Ctrl+equal`, 다른 앱에는 `Ctrl+Shift+equal`을 정확히 선택한 창으로 전달한다.
- Mac 배열의 물리 Alt와 PLUS·키패드 ± 조합도 같은 확대·축소 명령으로 처리한다. 일반 scanless PLUS를 추측해 다른 키로 바꾸지는 않는다.
- 데스크톱 명령 오류가 `openControls()`를 호출하던 경로를 제거했다. 상태 안내와 Toast를 표시하고 fullscreen/input ownership을 유지한다. 실제 표시 장치 오류의 복구 화면은 유지한다.
- 화면 복귀 때 목표 View 크기와 실제 holder 크기를 구분하며, 현재 크기에 맞는 유효 buffer로만 attach한다. 동일한 fit으로 반올림되더라도 입력 좌표를 갱신하고, 중지된 복귀 callback은 폐기한다. 시스템 바 적용 후 insets를 다시 요청한다.
- 이전 lossless frame 전송 수정도 포함한다. 기존 native ELF 7개는 이전 APK와 바이트가 같다.
- 내부 브로커 종료 실패 후 명시적인 종료 재시도에서 STOP을 다시 보내도록 수정했다. 다만 이전 브로커의 clean ACK 실패는 해결됐다고 표시하지 않는다. 설치 전 기존 소유 child/service만 신원 검증 후 종료한 별도 cold recovery를 수행했으며, global Shizuku는 재시작하지 않았다.

## 실행한 검증

- 확대·축소/키보드/명령 오류 UI: RED 30개 중 5 실패 → GREEN 31개 통과. `build/diagnostics/tablet-zoom-green-20261008-01/receipt.json`.
- 실제 Surface/Chrome callback harness: RED 8개 중 6 실패 → geometry와 인접 lifecycle/IME/입력 검사 51개 통과. Android holder·UI queue·JNI 경계는 doubles이며 실물 BufferQueue 검증은 아니다. `build/diagnostics/tablet-geometry-green-20261008-01/receipt.json`.
- 수정된 Python 모듈을 기기의 임시 소유 범위에만 올려 실제 Foot 확대·축소를 확인했다. 터미널 크기가 `170×48 → 187×51 → 170×48`로 바뀌어 원래 글자 크기로 복구됐다. 검사 창과 파일은 제거했고 사용자 터미널은 닫지 않았다. `build/diagnostics/y900-foot-zoom-20261008-02/receipt.json`.
- 브로커 명시적 STOP 재시도: RED 3개 중 1 실패 → GREEN 3개 통과. 실제 controller 메서드와 RPC doubles의 검사이며 실제 clean ACK 증거는 아니다. `build/diagnostics/inside-stop-retry-green-20261008-01/receipt.json`.
- 변경하지 않은 lossless 전송 소스는 기존 128개 통과 receipt 및 freeze hash와 동일하다. 이번 키보드·화면·재시도 검사 85개와 별도 증거다.
- 전체 Android API 36 SDK 빌드 및 APK 서명 검증을 수행하고, build input/source freeze 28개/패키지 Python assets를 대조했다. 정확한 설치 산출물은 위 02 디렉터리의 `packaging-receipt.json`과 `build-receipt.json`에 기록한다.
- 독립 소스 검토에서 material blocker를 발견하지 못했다.
- 설치된 d806 APK에서 소유 Foot 검사 창으로 semantic 축소·확대와 Android 합성 Alt+-/Alt++/Alt+Shift+=를 확인했다. `170×49 → 187×51 → 170×49`로 복구되고 fullscreen/input ownership을 유지했다. [기기 receipt03](../../build/diagnostics/y900-foot-zoom-20261008-03/receipt.json). 사용자는 실제 키도 동작한다고 별도로 확인했다. 합성 키 검사를 물리 키 실측으로 표시하지 않는다.

## 남은 기기 확인

receipt03의 HOME/복귀 3회는 실제 background 진입을 확인하지 않았고 attachment token이 모두 2였다. 따라서 앱을 실제로 벗어난 뒤 하단 잘림이 복구됐다는 증거로 사용할 수 없다. 관찰한 View 3774×2494와 holder/native output 1920×1269 정합성은 해당 순간의 geometry 증거다.

사용자가 명령 동작과 함께 일반 Linux 명령 실패 안내를 보고했다. 현재 세션의 class-only ValueError는 아직 zoom·scale·clipboard 중 원인을 구분하지 못했다. Chrome 내부 연결의 창 종류 검사 실패는 별도 수정 및 Google 기기 시험08에서 확인했다. 앱 복귀 후 실제 하단 잘림, 압축 전송 전체 경로, 입력 지연/물리 FPS와 전체 Omarchy 수락은 미완료다.
