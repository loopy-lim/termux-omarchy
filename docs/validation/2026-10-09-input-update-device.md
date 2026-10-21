# Y900 입력 수정 적용과 실기기 확인

사용자의 “지금 실행해주라” 요청에 따라 ADB `Y900`에 준비한 입력 수정본을 적용했다. 물리 한/영 전환과 체감 입력 지연의 최종 사용자 확인은 아직 기다리고 있다. 전체 Omarchy 지원이나 144 FPS 검증 완료를 뜻하지 않는다.

후속 PRoot 보호 경로의 실제 적용·재시작 결과는 [PRoot 보호 검증 문서](2026-10-09-proot-guard-device.md)에 기록했다. 아래 미적용 상태는 이 입력 수정 기록 당시의 결과다.

## 실제 적용한 내용

- 시작 시각·UID·부모·tracer를 대조한 기존 CPU 잔여 프로세스 17637, 17325, 17326만 개별 종료했다. 같은 Linux 세션에서 Termux UID 프로세스의 합산 CPU 사용량은 2초 측정 205%에서 3초 측정 75.66%로 줄었다. 100%는 CPU 한 코어를 뜻한다. 업데이트 후 Chromium 창이 열린 상태의 별도 5초 측정은 68.2%였다. 마지막 측정은 다른 세션·작업 상태이므로 동일 부하의 성능 비교로 해석하지 않는다.
- 한/영 키 전달 수정 Termux:X11 APK를 데이터 보존 업데이트로 설치했다. 설치된 APK를 다시 가져와 SHA-256 `c620ec2b22dbe971561c8391dcc8ab73068588803f1c7794eca8a2d3e2eeb44c`와 14,576,519바이트를 확인했다.
- 신뢰 서명이 검증된 Fcitx·Hangul 패키지 7개와 입력 설정 5개를 설치했다. 기존 autostart 파일은 정확한 원본 해시와 함께 백업했다. 패키지·설정 각각의 설치 기록이 `INSTALLED`이며 pacman 시스템 설정과 동기화 DB는 유지됐다.
- 재시작 중 Quickshell 경로 링크의 정상 재생성을 오류로 판단해 전체 Linux를 종료하던 감시 코드를 수정했다. 변경을 허용하는 범위는 `quickshell/by-path/<32자리 해시>` 링크가 같은 소유자·장치·유형을 유지하고, 문자 그대로 `/run/user/1000/quickshell/by-shell/<같은 해시>`를 가리키며, 대상 디렉터리도 이미 기록된 동일 inode일 때뿐이다. 링크 생성자는 짧게 실행되는 `qs ipc`일 수 있으므로 생성 프로세스의 생존을 링크 수명 조건으로 삼지 않는다. 다른 링크·소켓의 교체 검사는 유지된다.

최종 감시 코드 SHA-256은 `4e2999c012bdf756492d06931f8df50fbf42a8c99a2e0fe382638afc92fc0a57`이다. 기존 소스와 설치 기록을 백업하고 native 설치 기록의 해당 소스 해시도 갱신했다. 실패한 세 번의 임시 runtime 디렉터리는 삭제하지 않고 원래 inode와 함께 격리 보관했다. 검증된 기존 supervisor 소스의 `capture-runtime` 정리 경계는 owned subreaper가 자식을 ECHILD까지 수거한 뒤에만 기록되며, 이를 확인하고 남은 supervisor만 종료했다. 사용자 홈이나 브라우저 프로필은 초기화하지 않았다.

## 현재 태블릿에서 확인한 결과

최종 세션 `cd62fbb0-c017-4917-8d8b-b0d3ea6e1149`는 재시작과 15초 관찰, Chromium 실행 및 후속 CPU 측정 이후에도 `ready`였다. 화면은 1920×1280, compositor 배율 1.25, 요청 refresh 60 Hz로 기존 값을 유지했다. 실제 새 프레임 FPS나 물리 입력 지연을 측정한 결과는 아니다. 설정 오류 응답은 비어 있고 오디오와 Android 설정 연결도 ready다.

Fcitx 프로세스가 한 개 자동 실행되며 XMODIFIERS·Qt·SDL 입력 환경을 상속한다. 기존 세션에서 Chromium 실행 전에 호출한 guest `fcitx5-remote`가 정상 종료하고, 당시 입력기 상태 `keyboard-us`를 반환했다. 이 조회는 Chromium의 포커스된 입력 문맥을 확인한 결과가 아니다. 물리 한/영 전환과 Hangul 플러그인의 실제 조합·확정 입력은 사용자 확인이 남아 있다.

기존 Chromium 실행 경로로 공개 입력 시험 페이지 두 창을 열었고, 실제 Xwayland 창 두 개를 확인했다. 초기 시험기의 제목 비교가 Chromium의 창 제목 접미사를 고려하지 않아 두 번 실패했다. 추가 실행 없이 같은 창들을 공개 제목 부분으로 대조해 확인했다. 개인 URL이나 창 제목은 기록하지 않았다. Chromium 설정과 강제 배율 옵션은 변경하지 않았다. 사용자가 보고한 글자·툴바가 두 배로 보이는 원인은 아직 확정하지 않았다.

## 검사 범위와 재발 방지 후보

최종 변경과 관련된 파일 시스템 검사 5개, runtime 검사 7개, Termux Omarchy 설치·설정 검사 103개가 통과했다. 별도로 넓힌 기존 Omarchy 검사 305개 중 한 개는 기존 ARM refresh 빌드 기록과 현재 `tools/prepare_omarchy.py`의 해시가 달라 실패했고 7개는 skip됐다. 이 실패를 통과로 처리하거나 과거 빌드 기록을 새 소스에 맞춰 고치지 않았다.

PRoot tracer가 갑자기 종료될 때 Linux 자식도 종료하도록 하는 opt-in `PTRACE_O_EXITKILL` 패치도 준비했다. 실제 태블릿의 독립적인 자체 만료 시험에서 원래 옵션은 자식이 남고, 보호 옵션은 자식이 자동 종료되는 것을 확인했다. 전체 PRoot 실행 파일도 고정된 upstream 소스로 컴파일하여 같은 실기기 시험을 통과했다. 시험은 자기 자식만 종료하고 기존 사용자 세션을 유지했다. 이 입력 수정 기록 **당시에는 데스크톱에 아직 적용하지 않았다**. 당시 설치된 PRoot를 보호 패치 적용판이라고 표시하면 안 된다. 이후 실제 적용과 재시작 확인은 위 후속 문서에 구분했다.

이 기록 당시 남은 확인은 평소 물리 한/영 키·Ctrl+Space 조합 입력, 키보드와 마우스의 체감 끊김, Alt+Tab·Alt+Space·Esc·Caps+H/J/K/L 회귀, 사용자가 실행한 Chromium 배율 원인, PRoot 보호 후보의 실제 Omarchy 통합과 지속 동작이다.

## 근거 파일

- `build/diagnostics/termux-omarchy-input-orphan-cleanup-device-20261009-01/receipt.json`
- `build/diagnostics/termux-omarchy-korean-input-install-device-20261009-02/receipt.json`
- `build/diagnostics/termux-omarchy-language-apk-install-device-20261009-01/installed-verification.json`
- `build/diagnostics/termux-omarchy-quickshell-rebind-recovery-device-20261009-03/receipt.json`
- `build/diagnostics/termux-omarchy-input-restart-device-20261009-04/receipt.json`
- `build/diagnostics/termux-omarchy-hangul-browser-visible-readonly-device-20261009-01/receipt.json`
- `build/diagnostics/termux-omarchy-input-after-update-cpu-device-20261009-01/receipt.json`
- `build/diagnostics/termux-omarchy-quickshell-index-final-host-20261009-01/test-receipt.json`
- `build/diagnostics/termux-omarchy-proot-full-lifetime-probe-device-20261009-03/receipt.json`
- `build/diagnostics/termux-omarchy-proot-exitkill-build-20261009-01/build-receipt.json`

기존 한글 입력 준비 bundle에는 이번 Quickshell 수정이나 PRoot 후보가 포함되지 않는다. 고정된 이전 bundle의 검증 결과를 현재 전체 설치판의 검증으로 확대하지 않는다.
