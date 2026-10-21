# 2026-10-09 앱 호환성 현재 상태 · 초안

현재 설치본에서 Linux Foot·Neovim·Nautilus의 제한된 실제 GUI 사용은 통과했다. Google Chrome은 내부 창 시작을 확인했지만 정상 종료에 실패했고, 강제 RAW Chromium 시험도 실패했다. 아직 “대부분의 앱이 잘 동작한다”는 결론은 내릴 수 없다.

기준 APK는 `30ea2114f67bd7a728dd1ad5d5d991fe8b541025803f3966946c9ebc2b80249e`다. [update02](../../build/diagnostics/y900-android-inside-product-update-20261009-02/receipt.json)는 update-only 설치와 설정132개·입력 서비스·역할·마이크 거부·global Shizuku lifetime 보존을 확인했다. 아래 결과는 이 설치본에 한정한다.

| 앱·시험 | 확인한 동작 | 남은 경계 |
| --- | --- | --- |
| [Foot + Zsh02](../../build/diagnostics/y900-linux-daily-apps-20261009-foot-02/receipt.json) · PASS | 실제 native Wayland 창에서 공개 명령 입력, 파일 결과 확인, 종료 코드0, 새 창으로 재실행. 소유 IPC 합성 키136개가 dispatch됐다. | 물리 키보드·마우스, 사용자 Zsh 설정, 실제 표시·GPU·FPS는 미검증. |
| [Neovim01](../../build/diagnostics/y900-linux-daily-apps-20261009-nvim-files-01/receipt.json) · PASS | 실제 Foot/Neovim 창에서 공개 임시 파일 입력·저장, 정상 종료, 재실행한 buffer와 저장 파일 일치. | `--clean`과 격리 프로필 범위이며 사용자 플러그인·전체 설정 합격이 아니다. |
| [Nautilus01](../../build/diagnostics/y900-linux-daily-apps-20261009-nvim-files-01/receipt.json) · PASS | 소유 공개 디렉터리의 실제 native Wayland 창 열기, 정상 종료, 새 창으로 재열기. | 파일 이동·복사·삭제, Android 공유 저장소, 사용자 D-Bus 서비스와의 통합은 미검증. |
| [Google MAIN02](../../build/diagnostics/y900-inside-google-main-device-20261009-02/receipt.json) · FAIL | 기존 Google Chrome 앱의 새 내부 창에서 frame decode/copy·native Cairo source 선택과 입력 준비를 확인해 `startup_passed=true`. | 입력 명령0개, 정상 `CLOSED=0`. 소유 자원 사후 정리 성공을 기능·정상 종료 합격으로 바꾸지 않는다. |
| [Chromium 강제 RAW03](../../build/diagnostics/y900-inside-multiwindow-raw-device-20261009-03/receipt.json) · FAIL | 첫 2512×1592 RAW frame15,996,416 B를 완전히 수신·복사하고 release flush했다. | 첫 창의 후속 sequence2는 완전 수신·복사·release가 미확인이다. 전체 두 창 입력·종료 절차 합격이 아니다. |

Linux 세 앱은 테스트 전용 HOME·프로필·D-Bus 및 공개 임시 파일을 사용했다. 입력은 소유 창을 확인한 합성 compositor IPC이며 실제 물리 입력 경로를 검증하지 않았다. 이들의 native Wayland 창 확인과 Chrome의 Cairo source 선택은 물리 paint 완료·GPU 가속·60/144fps 증거가 아니다.

위 시험들의 소유 자원 정리와 설정132개·서비스·역할·APK 보존은 각 영수증에서 통과했다. 사후 정리의 합격은 Chrome 시험 실패를 취소하지 않는다. 예전 Foot01 실패와 다른 APK의 과거 결과도 그대로 보존한다.

새 burst writer·typed timeout 관련 [GREEN05](../../build/diagnostics/inside-shared-tasks-green-20261009-05/receipt.json)는211 tests 및 기존 Java guard423 assertions를 통과했다. 플랫폼·GTK 경계는 test double이므로 기기 RAW 진행·입력 지연·정상 종료 개선의 증거가 아니다. 다음 후보의 SDK 빌드·설치·기기 결과는 이 문서에 아직 반영하지 않았다.

후보 APK·빌드 receipt: **ROOT가 새 후보 확정 뒤 추가할 자리**. 현재 설치본과 후보를 혼동하지 않는다. 테스트 밖의 사용자 편집기가 실행 중이므로 다음 업데이트 직전에 새 작업 저장 확인이 필요하다.

다음 검증은 새 설치본의 기존 Google Chrome, 기본 압축 경로의 두 창, 강제 RAW 진행·정상 CLOSED, 그리고 Linux 세 앱 재검증이다. 이후 Writer 공개 문서 저장·재열기, Evince 공개 PDF, imv 공개 이미지, mpv 공개 클립을 실제 GUI로 확인해야 앱 호환성 범위를 넓힐 수 있다. 설치 패키지 수나 `--version` 성공으로 이를 대체하지 않는다.

소스 감사에서 아래 경로는 남은 후보로 확인했으며 이번에 수정하거나 실제 실패를 재현하지 않았다.

- [원본 helpers.lua](../../build/omarchy-sources/omarchy/default/hypr/helpers.lua)의 `o.launch()` 및 [원본 메뉴](../../build/omarchy-sources/omarchy/default/omarchy/omarchy-menu.jsonc)의 Share→Receive에는 UWSM 경로가 남는다. [Android 파생 caller 목록](../../android/assets/omarchy-bridge/app-launch-sources.sha256) 밖의 helper·JSON 경로는 별도 호환성 확인이 필요하다.
- [원본 AppLibrary.qml](../../build/omarchy-sources/omarchy/shell/services/AppLibrary.qml)의 일반 시작 표시는 전체 창 수·활성 창 변화 또는15초 만료로 닫힌다. 선택한 앱의 실제 준비·실패 판정으로 볼 수 없다.
- [원본 웹앱 launcher](../../build/omarchy-sources/omarchy/bin/omarchy-launch-webapp)는 `--app=URL`을 Linux 브라우저로 넘긴다. [typed 내부 route](../../android/assets/omarchy-bridge/browser_inside_route.py)는 그 flag를 인정하지 않는다. 일반 단일 URL·Notion Web 내부 route와 다르며 사용자 프로필·private·custom flag를 조용히 제거해서 해결하지 않는다. Linux 브라우저 sandbox의 과거 실패는 [별도 기록](2026-10-08-linux-browser-candidates-current.md)에 남아 있다.

이번 문서는 완료된 ROOT 영수증과 읽기 전용 소스 감사를 정리한 초안이다. 새 코드 실행·테스트·기기 조작이나 기존 봉인 자료 변경은 하지 않았다.
