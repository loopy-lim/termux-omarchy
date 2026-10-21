# Chromium 다중 창·한글 입력과 남은 Omarchy 문제

실제 Lenovo Y900 연결 기기 `Y900`의 native Termux 세션에 Chromium 임시 경로 수정을 영구 적용했다. 일반 실행 두 창은 같은 Chromium 프로세스로 열렸고 프로필 오류 대화상자는 없었다. Linux 내부 한글 조합 시험과 사용자 물리 한/영 전환은 각각 정상 확인됐다. 사용자는 키보드·마우스 끊김이 여전히 비슷하다고 보고했다. 전체 Omarchy 사용 완료나 입력 지연 해결로 판단하지 않는다.

## 적용과 검증

- guest `TMPDIR=/run/user/1000`만 추가했다. `/tmp` Unix socket bind의 EACCES(13), 같은 사용자 프로필의 첫·두 번째 창 성공을 확인한 후 적용했다. SELinux나 길이 제한 중 어느 정책이 거부했는지는 이 시험으로 특정하지 않았다.
- 관리 소스 19개를 검증한 뒤 기존 공개 시험 창 3개만 있는 상태에서 세션을 종료·업데이트했다. 후속 `runtime-update-tmpdir.json`은 기존 `runtime-update.json`을 바꾸지 않고 이전 소스·설치 기록·첫 업데이트 기록을 백업한다. 변경된 runtime 대상은 `omarchy_commands.py` 하나다. [적용 기록](../../build/diagnostics/termux-omarchy-chromium-tmpdir-install-device-20261009-01/receipt.json)
- 새 세션 `3bac299b-7ba4-452f-a48e-372b1e1cdb1b`의 실제 Hyprland 환경에서 TMPDIR을 확인했다. 보호 PRoot 실행 파일·EXITKILL 요청과 Fcitx 프로세스 1개를 확인하고 15초 후에도 ready였다. 1920×1280·배율 1.25·요청 60 Hz를 유지했다. [재시작 기록](../../build/diagnostics/termux-omarchy-chromium-tmpdir-restart-device-20261009-01/receipt.json)
- 임시 환경 override 없이 일반 `chromium --new-window`를 두 번 실행했다. 두 Xwayland 창의 실제 PID는 모두 16887이고 프로필 오류 대화상자는 0개였다. 이는 런처 UI 클릭 자체의 수용 검증은 아니다. [첫 창](../../build/diagnostics/termux-omarchy-chromium-normal-launch-device-20261009-01/receipt.json), [두 번째 창](../../build/diagnostics/termux-omarchy-chromium-normal-launch-device-20261009-02/receipt.json)
- 공개 입력칸에 compositor로 고정 키를 전달한 시험에서 `가나다 abc`와 composition event 3개, 한글·영문 복귀를 확인했다. 물리 키보드를 우회한 시험이다. 이후 사용자는 같은 확인 창에서 물리 한/영 전환과 두 언어 입력이 정상이라고 답했다. [Linux 조합 기록](../../build/diagnostics/termux-omarchy-chromium-normal-ime-device-20261009-01/receipt.json)
- 기존 223개 관련 host 검사는 실패·오류·skip 없이 통과했다. 현재 기기 시험과 별도 근거이며, 모든 프로젝트 검사가 통과했다는 의미는 아니다. [host 기록](../../build/diagnostics/termux-omarchy-chromium-tmpdir-host-20261009-01/test-receipt.json)

브라우저 프로필을 초기화하지 않았고 DPI/배율·사용자 Chromium flags를 변경하지 않았다. 정상 종료하지 않았던 이전 세션의 ‘Restore pages?’ UI는 공개 확인 화면에 남아 있다. 프로필 오류 0개 결과를 모든 브라우저 문제 해결로 확대하지 않는다.

## 포인터와 실제 데스크톱

사용자는 포인터가 너무 빨리 움직인다고 명확히 답했다. 기존 Termux:X11 `capturedPointerSpeedFactor=176`을 100으로 낮추고 다른 저장 preference가 모두 같음을 확인했다. Linux 세션은 유지했으며 원래 176으로 복구할 수 있다. 이 값 변경은 지연 개선 증거가 아니다. [속도 적용 기록](../../build/diagnostics/termux-omarchy-pointer-speed-device-20261009-01/receipt.json)

공개 확인 창만 있는 Android Termux:X11 화면 한 장을 확인해 상단 Omarchy bar가 보이지 않는 것을 확인했다. Quickshell 정상 실행 로그에서 빈 `/etc/machine-id`로 D-Bus가 abort하고 Quickshell이 반복 종료되는 원인을 확인했다. UID·rootfs·소스·잠금 파일을 검증하고 빈 파일을 백업한 뒤 처음 한 번만 ID를 생성했다. 기존 0444 mode와 `/var/lib/dbus/machine-id → /etc/machine-id` symlink inode를 유지했고, 공개 기록에는 ID 원문을 남기지 않았다. [machine-ID 적용](../../build/diagnostics/termux-omarchy-machine-id-install-device-20261009-01/receipt.json)

같은 세션에서 정상 shell 실행 후 실제 `omarchy-background`와 `omarchy-bar` layer가 alpha 1로 표시됐고, 원본 Omarchy root menu도 실제 layer와 한 장의 공개 화면으로 확인했다. 이는 각 메뉴 항목의 기능 검증이나 이후 재시작의 자동 복구 증거는 아니다. Qt shell의 UPower·PipeWire·NetworkManager·Bluetooth·portal·polkit 서비스 경고는 남아 있다. proc exe readlink 접근 실패와 hardcoded shellReady=false는 shell 부재 판정 근거로 사용하지 않는다. [shell 실행](../../build/diagnostics/termux-omarchy-shell-launch-after-machine-id-device-20261009-01/receipt.json), [메뉴](../../build/diagnostics/termux-omarchy-shell-menu-device-20261009-01/receipt.json), [공개 메뉴 화면](../../build/diagnostics/termux-omarchy-shell-menu-device-20261009-01/root-menu-public.png)

12.242초 CPU 관찰에서 X11·Weston이 `other-termux`에 포함됐다. 값은 전체 CPU 포화 또는 Chromium 병목을 증명하지 않는다. 물리 입력부터 화면까지의 지연은 아직 측정하지 않았다. [읽기 전용 CPU 관찰](../../build/diagnostics/termux-omarchy-chromium-normal-cpu-readonly-device-20261009-01/receipt.json)

후속 설치 전 확인에서 기존 세션이 이미 `stopped`, `terminationConfirmed=true`였다. supervisor의 `operationEvidence`는 resources capture 중 `FileNotFoundError`였고, 자식 종료·정리 후 stopped 상태가 게시됐다. 설치 시험 01은 ready 전제에서 중단되어 패키지를 쓰지 않았다. 정리 실패나 Chromium 원인으로 단정하지 않는다. 사라지는 임시 파일의 점검 경쟁 조건을 기존 코드에서 재현했다. 같은 root와 부모 디렉터리가 유지된 경우에만 사라진 자식을 건너뛰도록 수정했고, root 소실·경로 교체·소유권 불일치는 계속 거부한다. 관련 host 검사는 47개 통과·Linux 전용 7개 skip·실패와 오류 0개였다. [회귀 검사](../../build/diagnostics/termux-omarchy-inventory-race-host-20261009-02/receipt.json) [중단한 preflight](../../build/diagnostics/termux-omarchy-nvim-tools-install-device-20261009-01/receipt.json)

종료가 확인된 동일 root에 별도 Neovim 도구 7개를 실제 설치했다. 기존 trusted keyring으로 서명 7개를 확인했고, 592개 기존 패키지 버전·pacman 설정·sync DB를 보존했다. 설치 후 목록 SHA는 `bf595ab948376ab481a53d5a969320a93c20341ad3e0d78560bd766d1928a679`다. lazygit·LuaRocks·Lua 5.1·tree-sitter-cli·zip·unzip 도구이며 개인 Neovim 설정 29개·plugin 81개의 설치 완료를 뜻하지 않는다. machine-ID·dbus symlink와 전역 Termux PRoot도 유지했다. 이 단계에서는 세션을 재시작하지 않았다. [실제 설치](../../build/diagnostics/termux-omarchy-nvim-tools-install-device-20261009-02/receipt.json)

이후 `omarchy_resources.py` 하나만 실제 업데이트하고 `d7f0f3e5-a80e-436c-b3b6-c5bbf76e6578`로 재시작했다. 원본 소스와 기존 두 업데이트 기록을 별도 백업하고, 이전 기록·machine-ID·전역 PRoot·개인 설정을 보존했다. bar와 background 자동 시작, 메뉴 열기·닫기 24회 중 표시 관찰 12회, 같은 세션 ready를 확인했다. 1920×1280·Hyprland 배율 1.25·요청 60 Hz를 유지했다. 실제 layer 검증이 있으므로 응답의 고정 `shellReady=false`만으로 shell 부재를 판정하지 않는다. 이 검사는 모든 사용 패턴의 장기 안정성을 보증하지 않는다. 이후 사용자가 Alt+Space 메뉴 열기·닫기와 마우스 이동 후 “종료되지 않고 포인터 속도도 적당함”이라고 확인했다. 물리 입력 끊김 개선 확인과는 구분한다. [적용·재시작·메뉴 반복 검사](../../build/diagnostics/termux-omarchy-inventory-race-install-device-20261009-01/receipt.json)

## 입력 경로와 Android 연결의 확인 범위

추가 패키지를 설치하지 않고 native Bionic X11 공개 시험 창에서 키·클릭·이동 도착과 XSync 처리를 기록했다. window PID·nonce·peer UID·process birth·현재 세션·foreground를 검증하고, 시험 후 자식 회수·시험 창 소실·이전 X focus 복구·동일 Linux 세션을 확인했다. 시험 02는 키만 도착하고 버튼 이벤트 0개여서 실패로 남겼다. 일반 ADB mouse tap은 실제 mouse button-state 변화를 만들지 않아, 시험 03에서는 고정 상대 이동·균형 있는 버튼 press/release만 주입했다. [실패한 시험 02](../../build/diagnostics/termux-omarchy-input-latency-device-20261009-02/receipt.json), [시험 03](../../build/diagnostics/termux-omarchy-input-latency-device-20261009-03/receipt.json)

시험 03에서 key down/up 각각 28개·button down/up 각각 18개·motion 158개, 처리 콜백 250개·미처리 이벤트 0개를 확인했다. 주입 요청은 키 24쌍·클릭 12쌍·작은 상대 이동 24개였으므로 전체 관찰을 고정 주입만의 표본으로 해석하지 않는다. 창 중앙으로 포인터를 옮기는 검사 자체도 motion을 하나 만들 수 있다. 문자·키 코드·포인터 좌표는 기록하지 않았다. XSync 완료는 X 서버의 요청 처리이며 디스플레이 표시 완료가 아니다. 물리 입력 지연, guest PRoot 비용, 전체 Wayland 경로, 60/144 FPS 달성을 증명하지 않는다. [고정 주입 기록](../../build/diagnostics/termux-omarchy-input-latency-device-20261009-03/adb-input-receipt.json)

Native Wayland 비교 시험은 소유권 확인 단계에서 중단됐다. Weston의 X11 창에 `_NET_WM_PID`가 없어, 창과 프로세스의 연결을 안전하게 확인할 수 없었다. 입력을 주입하지 않았으며 시험 자식 회수·창 소실·이전 focus 복구·동일 세션 유지를 확인했다. 이를 Wayland 지연 측정 결과로 사용하지 않는다. 후속 소스 03은 실행하지 않았다. [중단한 Wayland 시험](../../build/diagnostics/termux-omarchy-input-latency-wayland-device-20261009-02/receipt.json), [읽기 전용 소유권 경계 확인](../../build/diagnostics/termux-omarchy-native-x-focus-boundary-device-20261009-01/receipt.json)

현재 세션에서 인증된 Android 연결 서비스의 Wi-Fi 요청이 accepted였고 실제 Android Wi-Fi 패널 foreground를 확인했다. 설정값은 바꾸지 않았다. 반면 desktop 복귀 요청은 unavailable이었고 native TermuxAm 직접 실행도 exit 1·error 102였다. ADB로 Termux:X11을 foreground로 복구했다. 서비스 ping·요청 accepted와 실제 화면 전환 성공을 구별한다. 이후 설정값·서비스 소스를 바꾸지 않고 같은 서비스 요청으로 3회 반복했을 때는 Wi-Fi·복귀 요청이 모두 accepted였고, foreground 관찰에서 두 화면과 최종 Linux 복귀를 확인했다. 첫 실패 원인은 아직 확정하지 못했으므로 영구 수정 완료로 판정하지 않는다. [후속 3회 요청](../../build/diagnostics/termux-omarchy-android-settings-repeat-device-20261009-01/receipt.json), [화면 전환 관찰](../../build/diagnostics/termux-omarchy-android-settings-repeat-device-20261009-01/foreground.json) [Wi-Fi와 복귀 요청](../../build/diagnostics/termux-omarchy-android-settings-current-device-20261009-01/receipt.json), [Wi-Fi 화면 확인](../../build/diagnostics/termux-omarchy-android-settings-current-device-20261009-01/wifi-foreground.json), [복귀 오류](../../build/diagnostics/termux-omarchy-android-desktop-return-probe-device-20261009-01/receipt.json)

## 전달물과 남은 범위

[최신 runtime 업데이트 키트](../../build/deliverables/LoopyOmarchy-Runtime-guard-update-20261009-02.tar.gz)는 178,307바이트, SHA-256 `3771fe35b031f13b3bc23abfc0c692bc1597e79ee9afb650822d30018584ffcd`다. 기존 guard 설치에 TMPDIR을 이어 적용하거나 정확히 일치하는 legacy 소스에서 guard를 설치하는 경로를 제공한다. 전체 Omarchy 신규 설치 묶음이 아니다. [전달 기록](../../build/diagnostics/termux-omarchy-proot-guard-update-kit-20261009-02/delivery-receipt.json)

원본 158개 요청은 실제 599개 설치 목록 기준 57개 충족·101개 미충족이다. Neovim 도구 설치 전 592개 기준 52개 충족 기록과 구분한다. 추가 전용 후보 329개에는 기존 네 패키지 버전·한 폰트 충돌이 남는다. [현재 목록 대조](../../build/diagnostics/termux-omarchy-coverage-post-nvim-20261009-01/receipt.json) 기존 네 패키지 업데이트·한 폰트 교체를 포함하면 158개 요청의 의존성이 해소되는 metadata 후보도 확보했지만, vendor 서명·실제 transaction·ABI·메뉴 기능 검증이 남아 설치 준비 완료로 보지 않는다. manual 51개와 shell QML 119개 기능 연결 확인도 남아 있다. [전체 후보](../research/2026-10-09-omarchy-full-transaction-options.md), [남은 작업 계획](../superpowers/plans/2026-10-09-termux-fresh-guard-ime-plan.md)


신규 설치 묶음 06은 runtime 파일 점검 수정과 machine-ID 초기화 경로를 포함해 host에서 재패키징했다. 41,988,377바이트·SHA-256 `704b2d29b21b5472486cebbc266c764d2ae474838b7a9c153563472442bf7773`다. 이 묶음 자체의 신규 기기 설치와 전체 Omarchy 기능 검증은 수행하지 않았으며, 별도 설치한 Neovim 도구 7개도 포함하지 않는다. [신규 설치 묶음](../../build/deliverables/LoopyOmarchy-Termux-native-setup-20261009-06.tar.gz)
