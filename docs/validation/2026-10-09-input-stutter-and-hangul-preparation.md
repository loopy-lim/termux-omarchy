# Y900 입력 끊김·한/영 입력 진단과 수정 준비

대상은 ADB `Y900`의 기존 Termux Omarchy 세션이다. 이 기록은 **적용 전 준비 시점**의 사전 검증을 설명한다. 이후 사용자의 실행 요청으로 APK·입력기 설치와 잔여 프로세스 정리를 수행했다. 현재 적용 결과와 남은 물리 입력 확인은 [실기기 적용 기록](2026-10-09-input-update-device.md)에 기록한다.

## 입력 끊김

12.255초 측정에서 Foot 17637은 CPU 한 코어의 99.63%, Chromium zygote 17325와 17326은 각각 99.14%, 98.90%를 사용했다. 같은 세션에서 다시 2초간 측정해도 각각 100%, 100%, 99%였다. 이 수치는 장치 전체 CPU 사용률이 아니라 한 코어를 기준으로 한다.

세 프로세스의 실제 UID는 10323이고, 부모 PID는 1, TracerPid는 0이다. 시작 시각을 함께 대조해 PID 재사용으로 다른 프로세스를 잘못 식별하지 않았다. 현재 사용자 Chromium은 별도 프로세스이며 기존 PRoot tracer에 연결되어 있다. 이 세 잔여 프로세스는 CPU 경합의 강한 원인 후보다. 물리 키보드·마우스 지연과의 인과관계는 종료 전후 비교를 해야 확인할 수 있다.

현재 세션을 유지한 상태에서 해당 세 프로세스만 종료하고 다시 측정하는 동의를 요청했다. 종료를 승인받으면 UID, PID 시작 시각, 부모·tracer와 현재 Linux 창 연결 여부를 직전에 재확인한다. 다른 프로세스나 프로세스 그룹 전체를 종료하지 않는다.

측정 근거:

- `build/diagnostics/termux-omarchy-input-stutter-cpu-readonly-device-20261009-01/receipt.json`
- `build/diagnostics/termux-omarchy-input-readonly-device-20261009-03/receipt.json`

## 한/영 입력 수정 준비

현재 설치 APK의 Android `LANGUAGE_SWITCH` 키 코드 204는 native 키 테이블에서 0으로 처리된다. scanCode=0인 KeyBridge 전환 이벤트는 Linux의 Hangeul 키로 전달되지 않는다. 수정 APK는 기존 native 테이블 한 바이트를 Linux 키 코드 122로 변경한다. 대응하는 upstream 소스 패치도 함께 제공한다. 기존 scanCode 우선 경로, Alt+Tab/Alt+Space 처리와 다른 492개 APK payload는 동일하다. native 라이브러리 전체 재빌드는 수행하지 않았다.

기존 Linux에는 Fcitx 한글 입력기가 없다. 고정된 패키지 7개를 추가하고, 영어·한글 입력 프로필, GTK X11/Qt 연결 및 Hyprland 시작 시 Fcitx foreground 실행을 준비했다. GTK Wayland 앱의 기본 text-input 경로를 유지하는 설정은 [Fcitx 공식 안내](https://fcitx-im.org/wiki/Using_Fcitx_5_on_Wayland/en)를 따랐다. 실제 Chromium과 터미널에서의 조합 입력은 설치 후 확인해야 한다.

추가 대상:

- fcitx5 5.1.23-1, fcitx5-hangul 5.1.11-1
- fcitx5-gtk 5.1.7-1, fcitx5-qt 5.1.16-1
- libhangul 0.2.0-1, xcb-imdkit 1.0.9-1, yoga 3.2.1-1

설치기는 기존 패키지 버전을 교체하지 않으며, 기존 입력기나 GTK 개인 설정이 변경되어 있으면 적용을 거부한다. `autostart.lua`는 실제 원본 SHA를 확인한 뒤 정확히 백업한다. 패키지·설정 설치 기록을 별도로 유지한다. 실행 중인 Linux는 변경 전에 거부한다.

## 검증 및 배포 후보

관련 검사 62개가 통과했다. 실제 태블릿에서 새 패키지 worker로 7개 서명을 기존 신뢰 키에 대해 검증했고, 기존 585개 패키지 목록을 읽었다. 별도 pacman 사전 검사에서 추가 계획이 정확히 7개인 것도 확인했다. 준비 bundle의 31개 파일을 태블릿에서 다시 해시 검증하고, 실제 설치 경계가 현재 실행 중인 세션을 거부하는지 확인했다. 이 과정에서 사용자 설정이나 패키지를 설치하지 않았다.

준비 bundle:

- `build/deliverables/LoopyOmarchy-Korean-input-update-20261009-01.tar.gz`
- SHA-256 `46b45b23e6a8984412dea4937eb3f3dd3975e6b377f80e77c6a5d9382f0159e0`
- 18,442,018바이트, 31개 파일

APK:

- `build/deliverables/LoopyOmarchy-TermuxX11-language-key-fix-20261009-01.apk`
- SHA-256 `c620ec2b22dbe971561c8391dcc8ab73068588803f1c7794eca8a2d3e2eeb44c`
- 기존 설치 APK와 같은 서명 인증서, 16 KiB zip alignment 확인

검증 근거:

- `build/diagnostics/termux-omarchy-korean-input-implementation-20261009-01/affected-green.txt`
- `build/diagnostics/termux-omarchy-ime-worker-readonly-device-20261009-01/receipt.json`
- `build/diagnostics/termux-omarchy-ime-signatures-readonly-device-20261009-01/receipt.json`
- `build/diagnostics/termux-omarchy-input-target-preflight-readonly-device-20261009-02/receipt.json`
- `build/diagnostics/termux-omarchy-language-apk-verification-20261009-01/source-and-package-receipt.json`

## 남은 확인

사용자 작업을 저장하고 업데이트를 승인받은 뒤, 정확한 잔여 프로세스 종료 전후 CPU·입력 반응 비교, APK 업데이트 및 입력기 설치, 물리 한/영 키와 Caps 탭, Chromium·터미널의 한글 조합 입력을 확인해야 한다. 기존 Alt+Tab/Alt+Space·Esc·Caps+H/J/K/L과 마우스 동작도 함께 확인한다.

배율 설정은 변경하지 않았다. 사용자 Chromium과 시험 창의 외곽 크기는 다르지만, 이것만으로 글자·툴바가 두 배로 보이는 이유를 확정할 수 없다. 사용자가 실행한 창의 실제 배율 문제는 여전히 확인 중이다. 이번 준비를 전체 Omarchy 지원, 입력 지연 해결 또는 144 Hz 검증 완료로 취급하지 않는다.
