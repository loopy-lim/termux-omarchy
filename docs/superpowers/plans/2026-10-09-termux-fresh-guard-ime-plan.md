# Termux 실제 Omarchy 경험과 신규 guard·IME 설치 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 현재 Termux에서 원본 Omarchy의 런처·메뉴·패널·테마·앱이 실제로 연결되는지 먼저 대조하고, 확인한 사용 경험의 누락부터 보완한다. 이미 적용한 private PRoot guard와 Fcitx 입력은 이후 신규 설치에서도 재현한다. 이 계획의 완료를 전체 Omarchy 지원 완료로 표시하지 않는다.

**Architecture:** 고정된 원본 Omarchy와 Android bundle의 차이를 명시적으로 추적한다. 기존 Hyprland·Quickshell·앱 및 사용자 HOME를 유지하고, 필요한 PRoot/Android 어댑터만 정확한 원본 바이트를 확인한 뒤 적용한다. 새 설치는 기존 component installer를 순서대로 호출하며 각각의 identity·lock·backup·journal을 유지한다.

**Tech Stack:** Python 3, 실제 filesystem 기반 unittest, Bash/Lua/QML, Arch Linux ARM ALPM·detached signatures, Termux proot-distro 5.8.x, private PRoot/Weston14, Hyprland, Quickshell, Fcitx5.

**Spec:** [전체 설계](../specs/2026-10-06-omarchy-full-design.md), [원본 lock](../../../third_party/omarchy.lock.json), [현재 전체 패키지 대조](../../research/2026-10-09-omarchy-termux-full-coverage.md). 최신 사용자 지시인 “지금 wm만 wayland이고 나머지는 omarchy가 제대로 안된거 같아서”를 우선한다. 새 설치 포장은 실제 Omarchy 경험의 진단·개선보다 뒤에 둔다.

## Global Constraints

- 원본 패키지 요청 158개, 매뉴얼 51장, shell QML 119개의 기능 요구를 유지한다. 패키지·서비스·하드웨어 접근이 없다고 항목을 완료 또는 범위 밖으로 바꾸지 않는다.
- 기존 Termux 설치·컨테이너·Chromium/Neovim 프로필·HOME·Mac/KeyBridge 설정·Android 데이터는 보존한다. 변경 대상의 정확한 SHA/mode/ownership를 확인하고 private backup을 만든다. 사용자 편집은 덮어쓰지 않는다.
- 이 계획 작성 작업은 저장된 source·manifest·receipt 읽기와 이 문서 작성만 수행했다. ADB, 설치, 앱 시작/종료, 계정·권한 변경은 실행하지 않았다. 향후 기기 작업은 ROOT만 맡는다.
- `shellReady=False`는 현재 `termux/omarchy_runtime.py:249`의 하드코딩이다. shell 실패의 증거로 사용하지 않는다. 실제 Quickshell PID·source 경로·IPC 응답·메뉴 동작을 확인한다.
- source/test/build, package installation, process/IPC, surface, 실제 사용자 동작과 물리 입력을 별도 증거로 기록한다. 패키지 52/158을 사용 경험 완료율로 표현하지 않는다.
- 전역 `proot` 교체, 광범위 패키지 업그레이드, 자동 세션 종료·시작, 전체 HOME 덮어쓰기, 미확인 socket/PID 정리는 하지 않는다. 현재 작업공간은 Git 저장소가 아니므로 Git 초기화·commit·push 단계도 추가하지 않는다.
- 새 Python 모듈은 약 500줄 이하로 유지한다. 설치 파일의 source pin은 최종 소스 바이트에서 재계산하며 과거 artifact/receipt는 수정하지 않는다.

---

## 1. 현재 확인된 사실과 우선순위

### 실제 Omarchy 범위

| 영역 | 확인한 근거 | 정확한 의미와 다음 작업 |
| --- | --- | --- |
| 현재 상단 바 부재 | `termux-omarchy-shell-audit-readonly-device-20261009-01/desktop-public-fixture.png`에서 세 Chromium fixture 창 위에 Omarchy 바가 보이지 않는다. 같은 receipt는 readOnly=true, 공개 fixture만 촬영했음을 기록한다. | 가장 먼저 실제 Quickshell 기동·bar surface·autostart를 진단한다. 이 receipt의 PASS는 읽기 감사 성공이며 desktop 완성 판정이 아니다. |
| 원본과 설치 소스 차이 | 공식 lock은 `81145eb1fd41532fcae4310b26f860608e2eaf82`; Android bundle의 components.lock은 `158e8cfb3a03f7b390e4213eaf15edcea0dfaa98` | 버전 문자열이나 “Omarchy” 프로세스명만으로 원본 51장/119 QML의 기능을 충족했다고 할 수 없다. 실제 설치 파일을 두 소스와 대조하는 일이 우선이다. |
| 앱·도구 범위 | 최신 실기기 inventory 592개, 요청 충족 52개/미충족 106개. metadata SHA `54d8051ae0bb8918a36674c4168f885edc8f6662609c8475deb6f2fb6d5328a4` | `omarchy-nvim`, `starship`, `lazygit`, `gum`, LibreOffice, Obsidian, OBS, LocalSend, Moonlight 등 기본 경험을 구성하는 항목이 남아 있다. 설치된 Neovim은 `nvim` 요청을 충족하지만 원본 `omarchy-nvim` 설정/동작을 대신 증명하지 않는다. |
| 기본 앱 실행 경로 | 공식 `shell/Services/AppLibrary.qml:85`는 `uwsm-app -- gtk-launch`; `bin/omarchy-launch-terminal`은 `uwsm-app -- xdg-terminal-exec`. Android bundle에는 PRoot용 `uwsm-app`와 AppLibrary·Foot 우회 patch가 이미 있다. | `uwsm` 패키지가 없다는 이유로 메뉴 전체가 깨졌다고 단정하면 안 된다. 실제 설치한 override와 `.desktop` Exec, MIME, D-Bus 활성화, focus 동작을 확인한다. |
| 웹앱 오디오 경로 후보 | Android bundle patch `0002-runtime-carry-proven-Android-PRoot-compatibility-fixes.patch:230`의 `omarchy-launch-webapp`는 PRoot에서 `PULSE_SERVER=tcp:127.0.0.1:4715` 강제. 현재 guest payload 11파일은 일반 browser만 교체하고 webapp은 포함하지 않는다. | 현재 관리 오디오는 `unix:/run/user/1000/pulse/native`이다. 설치한 webapp 바이트가 이 patch와 같다면 일반 Chromium과 웹앱의 오디오 경로가 달라진다. 실제 파일·환경·공개 오디오 재생으로 먼저 입증할 구체적 후보이다. |
| 초기화·서비스 생략 | 같은 patch의 `default/hypr/autostart.lua:526`은 PRoot에서 shell만 시작하고 return. agents refresh, system update timer 등도 PRoot에서 비활성화한다. | 현재의 정상 shell 기동은 first-run provisioning·power profile·automount·agent/update 기능의 정상 동작을 뜻하지 않는다. 생략한 기능마다 실제 대체 구현 또는 OS 경로가 필요하다. 무조건 timer를 다시 켜는 해결은 하지 않는다. |
| Android 패널 범위 | `termux/omarchy_android_client.py:16`의 action은 `ping/wifi/bluetooth/desktop`뿐이다. guest manifest는 Wi-Fi/Bluetooth QML과 오디오 helper를 포함한다. | Wi-Fi/Bluetooth 설정창 연결은 일부 기능의 증거다. 배터리·밝기·마이크·카메라·알림·파일·power/lock의 전체 연결을 증명하지 않는다. |
| 테마·바 | bundle builder는 실제 Omarchy config/applications를 복사하고 Tokyo Night의 current-theme을 생성한다. 공식 shell은 사용자 `shell.json`이 유효하면 defaults 전체를 대체한다. | “테마가 없다”는 결론도 아직 근거가 없다. 현재 shell.json, 활성 plugin registry, current-theme·GTK/Qt/Foot 설정의 실제 바이트와 테마 전환 결과를 대조해야 한다. |

저장된 과거 기기 증거에는 shell ping, Wi-Fi/Bluetooth panel, 일반 Chromium·Foot·Yazi, 오디오, 원격 앱 등 부분 동작이 있다. ROOT가 guard+TMPDIR 적용 후 Chromium 두 창과 실제 한영 입력 성공을 전달했다. 그러나 최신 공개 화면에는 상단 바가 없으므로 과거 shell ping을 현재 shell 동작의 증거로 재사용하지 않는다. 최신 receipt의 `processes: []`는 `/proc/exe` readlink 접근 문제를 포함하므로 프로세스가 없다는 증거가 아니며, `shellStartupMessages: []`도 stdout 전달 여부를 확인하기 전 기동 실패로 단정하지 않는다. 원본 QML이 존재하는 것과 메뉴에서 기능이 실행되는 것도 구분한다.

최신 설치 byte 증거는 launch-shell `29862bc5ff49e710a0cc3661ff3f980fbf75c689eb3573f0c629b9a4b44981a3`, shell.qml `7efa623ad2f0c572fec318c1dbac24c9f10203863e6804e032d83065e3bcd6a8`, uwsm-app `d8c8205d9f9be84b2dccec5e58f19e7bfb2f3e25812701bd7ab606549562c037`, webapp `3d4d96eb622789e597760a07b4288db2a7221eaa1635aee1c76a9f3d2c9b0aa5`이다. ROOT의 실제 source 조회는 uwsm direct-exec와 terminal Foot 분기를 확인했다. 이 경로를 다시 구현하기보다 bar 기동과 webapp PULSE 불일치를 우선한다.

주요 근거 파일:

- `docs/research/2026-10-09-omarchy-termux-install-audit.md` 및 `third_party/cache/omarchy-android-c189d33/source/omarchy-android-c189d33bf34a7a50fad3ff46bbd97e5c29b48910/manifest/components.lock`.
- 위 source의 `builder/guest/assemble-release-rootfs.sh`, `runtime/guest/root/usr/local/bin/uwsm-app`, `patches/omarchy-shell/0001-shell-carry-proven-PRoot-launcher-optimizations.patch`, `0002-runtime-carry-proven-Android-PRoot-compatibility-fixes.patch`.
- `build/omarchy-sources/omarchy/default/omarchy/omarchy-menu.jsonc`, `shell/Services/AppLibrary.qml`, `shell/shell.qml`, `config/omarchy/shell.json`, `bin/omarchy-theme-set`.
- `build/diagnostics/termux-omarchy-guest-payload-20261009-01/guest-manifest.json`, `termux/omarchy_android.py`, `docs/termux-omarchy-validation.md`.

## 2. 실제 사용 경험을 먼저 복구하는 실행 순서

### Task 0: 현재 보이지 않는 Omarchy 바의 실제 기동 경로 복구

**Files:** ROOT가 수집 중인 `build/diagnostics/termux-omarchy-shell-audit-readonly-device-20261009-01/`; 현재 설치한 `usr/share/omarchy/bin/omarchy-launch-shell`, `home/omarchy/.config/hypr/hyprland.lua`와 autostart include; 재현한 원인에 해당하는 최소 source/회귀 테스트만 수정한다.

- [ ] ROOT의 현재 Quickshell 진단 결과를 먼저 받는다. 실제 설치 source와 환경·PID/birth·socket/IPC·bar layer surface를 한 세션 token에 묶는다. 제한된 `/proc/exe` 필터의 빈 결과 대신 읽기 가능한 cmdline/identity와 실제 IPC를 함께 사용한다.
- [ ] ROOT가 확인한 사용자 Hyprland preload의 `flock -n ${XDG_RUNTIME_DIR:-/tmp}/omarchy-shell-launch.lock omarchy-launch-shell`와 default autostart의 shell launch가 어떤 순서로 실행되는지 확인한다. lock 경합, child lifetime, stderr/stdout 전달, QML load/plugin failure를 각각 분리한다. lock 파일이 있다는 이유만으로 삭제하지 않는다.
- [ ] 진단 재실행은 ROOT가 소유한 세션 경계 안에서 한 번 수행하고 실제 stderr를 private diagnostic log에 남긴다. 이미 정상인 Chromium·한영 입력·프로필은 유지한다. 중복 shell을 무조건 추가하거나 기존 PID를 이름으로 죽이지 않는다.
- [ ] 원인을 재현하는 RED 테스트를 먼저 작성하고 해당 startup/adapter만 수정한다. shell import/IPC 오류라면 정확한 QML/source patch로, supervisor/lock 문제라면 소유권과 재실행 계약으로 해결한다. 원인이 밝혀지기 전 전체 shell 교체·전체 source upgrade를 하지 않는다.
- [ ] 최종 SHA에서 정상 시작 후 **상단 바 표시 → Apps 메뉴 열기 → 앱 실행 → 메뉴/설정 재열기 → 정상 stop/start 뒤 동일 바 복귀**를 확인한다. 바 표시만으로 119 QML 전체를 통과 처리하지 않는다. 이 Task를 fresh archive 작업보다 먼저 완료한다.

### Task 1: 현재 설치와 원본 기능을 대조하는 한 번의 읽기 감사

**Files:** 새 `tools/audit_termux_omarchy_experience.py`, 새 `tests/test_termux_omarchy_experience.py`; 결과는 새 `build/diagnostics/termux-omarchy-experience-audit-20261009-01/` 아래 저장. 원본 source와 현재 rootfs는 수정하지 않는다.

**Interface:** 호스트 비교기는 `--inventory <json> --official-root <path> --bundle-source <path> --output <new-directory>`를 받는다. device inventory 수집은 ROOT의 기존 읽기 전용 실행 경로를 사용하며 ADB 기능을 비교기 안에 넣지 않는다.

- [ ] 먼저 실제 filesystem fixture로 원본 158 요청·51 manual·119 shell QML의 항목이 보고서에서 사라지지 않고, missing/changed/unknown을 PASS로 승격하지 않는 테스트를 작성한다.
- [ ] ROOT가 현재 runtime token/UID/source SHA를 기록한 뒤 `/usr/share/omarchy/{bin,shell,config,default,themes,applications}`, `/usr/local/bin`의 관련 symlink/override, 사용자 `shell.json`, Hypr config include, MIME/default terminal 및 current-theme 링크의 이름·SHA·mode·link target만 수집한다. 브라우저 데이터·history·SSH keys·비밀값은 수집하지 않는다.
- [ ] `.desktop` 파일의 ID/Exec/TryExec/Terminal/DBusActivatable/MimeType를 읽고 실제 `command -v` 결과에 연결한다. ALPM package 부재와 executable 부재를 별도 필드로 기록한다.
- [ ] 원본 menu action/provider → CLI → dependency/service → 실제 설치 파일 → runtime evidence의 연결표를 작성한다. 최소 Apps/Style/Setup/Trigger/Learn/Install/Update/System 전체 root 메뉴를 포함한다. 하드웨어·systemd 경로도 누락시키지 않는다.
- [ ] shell registry·QML error log·IPC 응답과 같은 token의 실제 source 경로를 대조한다. `shellReady` 상태값만 바꾸는 수정은 하지 않는다.
- [ ] 실행: `python3 -m unittest discover -s tests -p 'test_termux_omarchy_experience.py'`. 성공 기준은 전체 요구의 보존과 정확한 분류이며 기능 통과가 아니다.

### Task 2: 공통 앱·desktop·웹앱 실행 계약부터 검증하고 고친다

**Files:** `termux/omarchy-launch-or-focus`, `termux/omarchy-launch-tui`, `termux/omarchy-launch-or-focus-tui`, 관련 `tests/test_omarchy_app_launch.py`/`test_omarchy_tui_launch.py`; Task 1에서 실제 불일치가 확인된 helper만 별도 pinned guest payload로 수정한다.

- [ ] ROOT는 같은 세션에서 메뉴 검색→실행, 원본 단축키→실행, `.desktop`→실행, 다시 실행→focus/새 창이라는 사용자 흐름을 Chromium·Foot·Nautilus·Neovim·Yazi·웹앱으로 각각 확인한다. 성공은 PID뿐 아니라 원하는 창, focus, 인수·파일 경로, 종료 결과까지 기록한다.
- [ ] 우선 webapp의 설치 바이트와 PULSE_SERVER를 대조한다. TCP 강제가 실제 남아 있고 재생 실패를 재현하면, 공개 테스트 오디오와 공백/특수문자 URL 인수를 사용한 RED 테스트 뒤 관리 Unix socket/cookie를 상속하도록 해당 helper만 고친다. 일반 browser의 기존 두 창 성공을 새 webapp 테스트 대신 사용하지 않는다.
- [ ] `.desktop`의 field code·Terminal=true·DBusActivatable와 helper 인수 보존을 검사한다. 이미 동작하는 PRoot용 `uwsm-app`/AppLibrary 우회를 보존한다. 누락 패키지를 채워야 하는 경우 임의 shim으로 설치 완료를 가장하지 않는다.
- [ ] 변경 payload는 알려진 원본 SHA와 mode만 수락하고 guest installer의 backup/journal 패턴을 재사용한다. Chromium profile 삭제·새 default profile 강제·HOME 교체는 하지 않는다.
- [ ] 실행: `python3 -m unittest discover -s tests -p 'test_omarchy_*launch.py'`. 이후 ROOT가 **변경한 실제 파일 SHA**에서 위 사용자 흐름과 정상 stop/start를 한 번 검증한다.

### Task 3: 테마·바·설정·clipboard·notification을 실제 원본 shell에 연결한다

**Files:** Task 1 결과의 QML/config 경로, `termux/omarchy-settings.patch`, `termux/omarchy-proot-settings`, `termux/omarchy_android.py`, `termux/omarchy_android_client.py`. 사용자 `shell.json`·theme 디렉터리 전체를 기본값으로 교체하지 않는다.

- [ ] 현재 유효한 `shell.json`과 공식 default의 bar/plugin 목록을 비교해 사용자 의도·bundle 제한·로딩 오류를 분리한다. 사용자 설정이 defaults 전체를 대체하는 원본 규칙을 유지한다.
- [ ] 기존 테마 이름·배경·GTK3/4·Qt·Foot 상태를 백업한 뒤 ROOT가 원본 Style 메뉴에서 테마 전환→shell/터미널/파일관리자 색상 반영→원래 테마 복귀를 확인한다. source만 비교한 항목을 visual PASS로 표시하지 않는다.
- [ ] 원본 clipboard history/emoji/notification/OSD, Wi-Fi/Bluetooth, monitor/brightness, power/battery 각각에 대해 표시→조작→결과·오류·복귀를 확인한다. Android 연동은 고정 action별 제한된 채널로 확장하고 임의 shell 명령을 받는 API를 만들지 않는다.
- [ ] 실제 기능 경로가 없는 power/lock/suspend·하드웨어 항목은 전체 범위의 미완료로 유지한다. 단순 메뉴 숨김·상수 값·Android 설정창 열기만으로 원본 기능 완료라 하지 않는다.
- [ ] 각 확인된 결함만 실패 fixture/회귀 테스트→최소 patch→최종 source pin→ROOT의 동일 실제 동작 순서로 진행한다. 설치 source 전체 교체는 official/bundle compatibility diff가 검증되기 전 수행하지 않는다.

### Task 4: 원본 앱과 서비스 전체를 채우는 분리된 transaction

**Files:** `third_party/omarchy.lock.json`, `tools/omarchy_packages.py`, `build/diagnostics/termux-omarchy-additions-post-ime-20261009-01/{transaction,blockers,coverage}.json`, 전체 coverage 문서. 다른 담당자가 진행 중인 package resolver 작업과 소유권을 조정한다.

- [ ] 개발 경험은 `omarchy-nvim` 설정, lazygit/Lua/Tree-sitter, starship/mise, docs/man을 묶어서 실제 터미널·편집기 동작 기준으로 처리한다. 설치된 nvim 바이너리 또는 개인 설정 일부로 원본 편집기 요구를 완료 처리하지 않는다.
- [ ] GUI 앱은 각 공식 ARM 공급/소스 빌드/호환 실행 경로와 라이선스·서명·desktop integration·파일 열기·저장·재실행을 검증한다. 모든 106 미충족 요청을 추적하되 공통 실행 경로를 고치기 전에 무작정 일괄 설치하지 않는다.
- [ ] 현재 추가 전용 계산은 336패키지, 다운로드 1,252,296,487 bytes이며 GStreamer exact version 3개·GVfs exact version·Nerd Font 충돌 때문에 `ready_to_fetch=false`이다. 이 미해결 transaction을 그대로 적용하지 않는다. 현재 GPU/Hyprland ABI와 기존 reverse dependency를 보존하는 해결안을 먼저 검증한다.
- [ ] systemd·Docker·스토리지·절전·KMS/DRM/evdev 기능은 PRoot만으로 실제 기능이 성립하는지 분리한다. OS 경로가 필요한 요구는 원본 전체 계획에 유지하며 flash/unlock/wipe 없이 증거와 다음 실행 경로를 정리한다.

## 3. 신규 설치에서 정확히 빠진 guard·IME 통합

실제 entry는 `termux/omarchy_setup.py`이며 `termux/setup.py`는 없다. `termux/generate_setup.py`는 runtime/processes/preferences/install/i3.config 5파일을 embed하는 i3/X11 생성기다. Omarchy archive 생성기로 바꾸거나 재사용하지 않는다.

현재 `omarchy_setup.py`의 prevalidation과 install stage는 base/host/guest/tools/workflow뿐이다. guard·IME import/argument/prevalidation/install/result가 모두 없다. 최신 source의 runtime pin은 11파일이지만 배포한 `LoopyOmarchy-Termux-native-setup-20261009-05`는 옛 9파일이며 guard installer·native3·IME7/config5가 빠졌다. `LoopyOmarchy-Runtime-guard-update-20261009-02.tar.gz`는 기존 설치를 위한 제한된 migration kit이며 fresh installer가 아니다.

### 재사용할 pin과 component 경계

| 구성 | 현재 authoritative source / pin | 생성할 journal |
| --- | --- | --- |
| Base/rootfs | `termux/omarchy_install.py`; outer `7e9f1cd67533bc0d3988b5cb3831aef52f1527dd90391d9d868ed9345021cdb2`; rootfs `dbee00c0cb41f6b213c153ff4dc1c0898ba99dd0543ac13cef1601820366e2c5` | `install.json` |
| Runtime11 | `base.RuntimeSources`와 `base.RUNTIME_SHA` 전체. 현재 commands `637e6cff516edb34af2f81133fc99d000d5f55b25a9b4595f1e792ba061c495e`, runtime `9505572efb220dc4c24d7e77a49c54cdb49b1abcccb88abcb95625653ca3f855` | base의 `runtime_files` 11개 |
| Private PRoot | `omarchy_proot_install.source_files/install`; `omarchy_proot.FILES/MODES` | `proot-guard.json` |
| PRoot 실행 파일 | proot `bdb15a8388038e2d1211ab6dd4d35fdf0bf3d9550cd03b24031eb4ba1de8c5c2`; loader `95a47c09e5401637ce034304362bd179682fba470a9dab78d8be0a56d1f0745c`; shmem `84475798e07c8174dbbfaec70a827fdb02f19ffa69a589380c13e7507fd0e731` | private dir 0700, proot/loader 0700, shmem 0600; 16 KiB ELF/RUNPATH receipt 유지 |
| Fcitx 패키지7 | `omarchy_tools_guest.IME_MANIFEST_SHA` = `9a8c73ec14e3a8f0da611555d9d8a873a58fa02eeaf47ec262f22541493e1e1e`; `tools.install(korean_input=True)` | `korean-input-install.json` |
| 입력 config5 | `omarchy_input_install.COMPONENT`: payload `9f26836651238aa8cebae609c9b9b8774b367ad07b817ebbd054466b5db35e92`; manifest `319dcdfb751420c69a0b55fca7d1dbb94d4c1e71b078957f6ab56d62f1b54fea` | `input-config-install.json`와 원본 autostart backup |

IME 패키지는 fcitx5 `5.1.23-1`, fcitx5-gtk `5.1.7-1`, fcitx5-hangul `5.1.11-1`, fcitx5-qt `5.1.16-1`, libhangul `0.2.0-1`, xcb-imdkit `1.0.9-1`, yoga `3.2.1-1`이다. archive와 detached signature는 `build/deliverables/Omarchy-Hangul-input-packages-20261009-01/`에 있다. config는 `Omarchy-Hangul-input-config-20261009-01/`의 profile·GTK3/4·autostart.lua·ime.lua이다. autostart는 기존 SHA `a3320bdbe91bdd2335a27f25d0cfd0c2b2af1fa525ee7e9dbafb1f11d81188c5`, mode 0644만 교체하며 나머지 신규 대상은 absent 또는 정확한 완성본이어야 한다.

PRoot provenance는 `build/diagnostics/termux-omarchy-proot-guard-update-kit-20261009-02/provenance.json`을 재사용한다. source commit `7266fb3e8516535682f5a9c8f3a7e70f6506eddb`, archive SHA `428c7f9dbb3178bf58956dfbb28449582193f45d2a2bec48851731fe56b525bf`, exitkill patch SHA `8d6466de0f1fd51206cb35b453d2abb676289ae503424c83360bd959b1df8a87`, declaration patch SHA `7508ab6e850dc1c1e687421085e69a24e770b4caabd050cf52da667b95c73178` 및 PRoot COPYING을 함께 전달한다. build receipt SHA는 `58055543e598f988f1adaffb849fdece612134d34ff582e47c2e227375352490`이다.

### Task 5: setup에 기존 guard·input installer만 연결

**Files:** 수정 `termux/omarchy_setup.py`, `tests/test_termux_omarchy_setup.py`. component installer의 검증을 복제하거나 느슨하게 만들지 않는다.

**새 CLI 기본값:** `--proot-dir <source>/proot-guard`, `--input-dir <source>/korean-input`, `--input-payload <source>/input-config-payload.tar`, `--input-manifest <source>/input-config-manifest.json`.

- [ ] 기존 실제 filesystem fixture에 native3와 IME archive/signature/config를 복사한다. 입력의 SHA, detached signature bytes, native extra member, config manifest 중 하나씩 훼손하면 base root를 만들기 전에 각 `proot-validation`/`input-validation` stage에서 거절하는 RED 테스트를 추가한다. subprocess CLI를 사용하며 main/installer를 mock하지 않는다.
- [ ] 현재 5종 validation 뒤에 `proot.source_files(args.proot_dir)`와 `input.validate(args.input_dir, args.input_payload, args.input_manifest)`를 추가한다. 모든 source pin 검증을 base.install 앞에서 완료한다.
- [ ] 기존 관리 root가 있으면 `base.walk`와 component의 identity 검사를 거쳐 input `preflight_targets`를 먼저 수행한다. 사용자 GTK/profile/autostart 수정은 다른 component의 신규 mutation에 앞서 거절한다. 각 실제 install에서도 기존 recheck를 유지한다.
- [ ] install 순서를 **base → private guard → Weston → guest → tools → workflow → input(packages → config)**로 한다. fresh root에는 runtime-state가 없는 것이 정상이며 guard가 desktop 첫 실행 전에 게시되어야 한다.
- [ ] 결과에 `prootGuard`와 `input` component 결과를 추가한다. `fullDesktopConfigured: false`, input의 `physicalKoreanInputVerified: false`를 유지한다. 실패 시 기존 sanitized reason와 stage를 출력하고 이후 component는 실행하지 않는다.
- [ ] `python3 -m unittest discover -s tests -p 'test_termux_omarchy_setup.py'`로 RED→GREEN을 확인한다. 이어 `test_termux_omarchy_proot_install.py`, `test_termux_omarchy_korean_input.py`, `test_termux_omarchy_korean_packages.py`만 회귀 실행한다.

예상되는 핵심 호출은 다음과 같다. 기존 component에 있는 검증·lock·backup·journal을 제거하지 않는다.

```python
proot.source_files(args.proot_dir)
input.validate(args.input_dir, args.input_payload, args.input_manifest)
# Existing input preflight, then all component installs in the order above.
guarded = proot.install(args.proot_dir, home, prefix)
ime = input.install(args.input_dir, args.input_payload, args.input_manifest, home, prefix)
```

기존 설치 보존 조건:

- 최신 11파일의 정상 설치만 그대로 재사용한다. 옛 runtime9 또는 TMPDIR 이전 commands는 fresh setup에서 자동 migration하지 않는다. 이미 검증한 별도 updater의 정확한 허용 predecessor와 journal chain을 사용한다.
- guard installer는 이미 설치된 guard도 현재 구현상 stopped 상태를 요구한다. 새 setup은 실행 중인 기존 세션을 자동으로 정지하지 않고 해당 stage에서 거절한다. 이전 setup05의 “live rerun 성공” 증거를 새 setup에 재사용하지 않는다.
- guard 디렉터리만 있거나 journal만 있거나 `.proot-guard-stage-*`, `INSTALL_UNKNOWN`/`UPDATE_UNKNOWN` 등이 있으면 보존하고 거절한다. 자동 adoption·삭제·재시도 복구를 추가하지 않는다.
- 정상 반복 실행에서 파일·directory inode, 원본 backup, 기존 component journal을 유지한다. fresh root에서만 새 UID/rootfs inode에 묶인 journal을 생성한다. 기기의 runtime-update journal을 archive에 넣지 않는다.
- `omarchy_tools_install.guest_job`은 현재 PREFIX의 `proot-distro`를 호출하며 desktop의 private guard selection을 주입하지 않는다. 이 계획은 desktop runtime guard 재현을 뜻한다. package worker까지 동일 보호를 확장하려면 별도의 argv/environment 계약과 테스트를 작성하고, 모든 PRoot 실행이 보호됐다고 먼저 주장하지 않는다.

### Task 6: 재현 가능한 새 fresh archive 생성

**Files:** 새 `tools/package_termux_omarchy_setup.py`, 새 `tests/test_package_termux_omarchy_setup.py`; 새 출력 `build/deliverables/LoopyOmarchy-Termux-native-setup-20261009-06/`와 `.tar.gz`, `.sha256`; 설치 문서의 새 버전 안내. 기존 setup01–05와 guard kit01/02는 불변이다.

- [ ] builder는 명시한 source/payload 경로와 **존재하지 않는 output**만 받고 기존 출력은 덮어쓰지 않는 실제 filesystem 테스트부터 작성한다. 이름만 유지한 다른 bytes·symlink·hardlink·extra member를 거절한다.
- [ ] 현재 setup/installers와 RuntimeSources11, Weston·guest·workflow payload, tools29, native3, IME7의 archive+signature, 입력 config5를 포함한다. `proot-guard/`에는 strict validator가 허용하는 3파일만 두고 license/provenance는 상위 metadata 경로에 둔다. `korean-input/`은 developer tools와 분리한다.
- [ ] `RuntimeSources`/host·guest·workflow·tools validators/proot.source_files/input.validate로 **포장할 바로 그 bytes**를 검증한 후 deterministic tar/gzip을 생성한다. 두 번의 새로운 출력 경로 생성 결과가 같아야 한다.
- [ ] file manifest, SHA256SUMS, archive SHA, source commits/patches/빌드 receipt hash, 각 component 크기·개수, license 위치를 생성한다. package archive 내부 라이선스·metadata를 보존하고 trusted keyring의 실제 signature 검증을 생략하지 않는다.
- [ ] README는 별도 rootfs 1,181,941,760-byte bundle과 Termux native prerequisite가 포함되지 않는다는 사실, fresh CLI, stopped existing rerun, 실패 journal 보존, 전체 Omarchy 미완료 범위를 설명한다. 최신 실제 11파일을 구판 “9개 런처”로 쓰지 않는다.
- [ ] `python3 -m unittest discover -s tests -p 'test_package_termux_omarchy_setup.py'`와 압축 해제한 새 archive에서 실제 setup CLI의 invalid-input/no-write 검사를 실행한다. 압축/검증만으로 설치 성공이나 입력 수락을 주장하지 않는다.

## 4. ROOT의 기기 검증과 완료 판단

- [ ] 실제 사용 경험 Task 1–4의 각 변경은 같은 앱 UID, 정확한 설치 SHA, 같은 token에서 사용자 흐름을 검증한다. 로그/IPC/파일 증거를 우선하며 시각 판단이 필요한 최소 순간만 확인한다. 이미 통과한 물리 한영 입력을 새 결함 근거 없이 반복시키지 않는다.
- [ ] fresh archive는 기존 사용자 HOME/PREFIX와 분리된 임시 fixture에서 설치한다. 이전 20261009-03 fresh receipt는 base/host/guest/tools/workflow까지만 증명하므로 guard/IME 신규 단계를 대신하지 않는다.
- [ ] fresh 결과의 base runtime_files11, guard selection/native3, 서명된 IME7, input config5, 각 journal의 UID/rootfs identity를 확인한다. 두 번째 실행의 bytes/inode/journal/backup 보존, 변경한 사용자 config 거절, partial guard 거절을 각각 확인한다.
- [ ] archive에서 실제 첫 실행이 guard를 선택하고 TMPDIR=/run/user/1000을 사용하며 Quickshell/menu/일반 앱/웹앱/IME가 동작하는지 확인한다. 기존 실제 사용자 프로필의 불변성도 검증한다. 시작과 물리 입력 수락은 별도 단계로 기록한다.
- [ ] 원본 158/51/119, 네이티브 입력 성능, GPU, 원격/Android/OS 경로의 미구현·미측정 항목을 유지한다. “fresh guard·IME 재현 완료”와 “전체 Omarchy 완료”는 서로 다른 판정이다.

## 계획 자체의 검토

이 문서는 전체 원본 범위를 유지하고 실제 사용 경험을 fresh 포장보다 앞에 두었다. 설치된 package와 기능 통과, 원본 source와 bundle patch, 저장된 실기기 receipt와 새 검증을 분리했다. 공통 런처에 이미 있는 PRoot 우회를 확인해 패키지 부재만으로 잘못 고치는 일을 피했고, webapp 오디오·생략된 초기화/서비스·제한된 Android action이라는 구체적 다음 조사 대상을 명시했다. 새 설치 변경은 기존 installer 호출과 별도 재현 builder로 제한하며 현재 사용자 설치의 migration/자동 복구 범위를 확장하지 않는다.
