# 태블릿의 독립 웹 앱과 VS Code SSH 개발

실제 Lenovo Y900 `Y900`의 native Termux UID 10323에서 확인한다. 아래 앱·PTY 검사의 최초 세션은 `d7f0f3e5-a80e-436c-b3b6-c5bbf76e6578`이다. 사용자의 작업 저장·재시작 승인 후 임시 경로 수정을 적용했고 현재 세션은 `4537c309-5d5e-4486-9083-624f0dafbfe1`이다. 기존 Chromium 프로필·배율·flags, Omarchy 실행기와 이전 설치 기록을 보존한다.

## Notion·Figma

새 `/usr/local/bin/loopy-launch-webapp`은 기존 PRoot 웹 앱 실행기의 기본 옵션과 Unix Pulse 오디오를 사용한다. 기존 Omarchy 실행기를 덮어쓰지 않는다. 사용자 앱 목록에 Notion·Figma 항목을 추가했다. 두 항목 모두 `gtk-launch`로 실행한 뒤 별도의 새 mapped window를 확인했다. 현재 Chromium 창은 Xwayland를 사용한다. Wayland compositor 위에서 모든 앱이 Wayland native라는 의미는 아니다.

- [설치 기록](../../build/diagnostics/termux-omarchy-webapps-install-device-20261009-01/receipt.json): 새 파일 3개, 기존 실행기와 설치 기록 보존, 세션 재시작 없음.
- [실제 실행 기록](../../build/diagnostics/termux-omarchy-webapps-launch-device-20261009-01/receipt.json): Notion·Figma 각각 새 창, 두 창 모두 실제 Chromium PID 29275. 로그인과 문서 편집은 미검증. 창은 사용을 위해 열어두었다.
- [WebGL 확인](../../build/diagnostics/termux-omarchy-chromium-webgl-device-20261009-01/receipt.json): 공개 loopback 진단 창에서 WebGL 2·WebGL 사용 가능. 실제 renderer는 ANGLE, Qualcomm Vulkan Adreno 830v1, turnip Mesa다. 강제 GPU 옵션이나 프로필 변경 없이 확인했다. 시험 창 닫기·서버 종료·기존 focus 복구·동일 Linux 세션을 확인했다. Figma 문서 편집 성능이나 물리 60/144 FPS 측정은 아니다.

Notion과 Figma는 주소창 없는 Chromium 앱 창으로 실행되며 기존 브라우저 프로필을 사용한다. 앱 자체 로그인은 사용자가 직접 진행한다. 공식 안내는 [Notion의 Linux 웹 사용](https://www.notion.com/help/notion-for-desktop), [Figma 브라우저 요구 조건](https://help.figma.com/hc/en-us/articles/360039827194-What-are-the-system-requirements-for-Figma), [Linux 로컬 글꼴 지원 제한](https://help.figma.com/hc/en-us/articles/360039956994-Missing-font-alert-in-Figma-Design)을 참고한다.

## SSH 접속 대상

사용자가 지정한 SSH 대상은 `loopy@100.80.133.120`이다. 새 전용 설정 `/home/omarchy/.ssh/loopy-development.conf`에 `loopy-development` 별칭을 등록했다. 기존 `~/.ssh/config`와 known_hosts를 보존했으며 Mac의 개인 키를 복사하지 않았다.

[실제 접속 확인](../../build/diagnostics/termux-omarchy-ssh-target-install-device-20261009-01/receipt.json)에서 서버는 publickey·password·keyboard-interactive 인증을 제공했다. 네트워크 timeout이나 host key 변경 없이 인증 단계까지 도달했으며, 로그인을 완료한 것은 아니다. 비밀번호는 VS Code의 태블릿 로그인 화면에 직접 입력해야 한다.

## VS Code

공식 Microsoft ARM64 1.141.0 파일을 다운로드하고 제공 SHA-256과 전체 349,562,023바이트를 검증했다. [다운로드 기록](../../build/diagnostics/termux-omarchy-vscode-download-20261009-02/receipt.json)

공식 Marketplace의 Remote-SSH 0.128.0, SSH Configuration 0.87.0, Remote Explorer 0.5.0 VSIX를 제공 SHA와 대조한 뒤 전용 portable 경로에 설치했다. 실제 CLI 버전·commit·ARM64와 설치된 확장 세 버전을 확인했다. 기존 Linux 패키지와 다른 편집기 프로필은 변경하지 않았다. [공식 확장 검증](../../build/diagnostics/termux-omarchy-vscode-remote-ssh-marketplace-20261009-01/README.md), [실제 VS Code 설치](../../build/diagnostics/termux-omarchy-vscode-install-device-20261009-01/receipt.json), [CLI·확장 설치](../../build/diagnostics/termux-omarchy-vscode-extensions-install-device-20261009-01/receipt.json)

실제 Hyprland 실행 경로에서 첫 원격 창은 2.464초에 표시됐고 Wayland native였지만 이후 PID가 사라졌다. Remote-SSH 활성화와 로그인 창은 확인하지 못했다. 공개 로컬 workspace를 사용하는 별도 실행은 2.635초부터 19.992초까지 Wayland 창을 관찰했다. 이 시험의 최초 기록은 창 제목 조건 때문에 정리 단계에서 FAILED였으며, 후속 기록에서 공개 nonce를 포함한 launcher 조상·PID/birth·window stable ID를 확인한 뒤 해당 시험 창만 닫고 exit 0·프로세스 소실·기존 Linux 세션 유지를 확인했다. [첫 원격 창](../../build/diagnostics/termux-omarchy-vscode-gui-remote-device-20261009-01/receipt.json), [로컬 창 관찰](../../build/diagnostics/termux-omarchy-vscode-hyprland-gui-device-20261009-01/receipt.json), [시험 창 정리와 오류](../../build/diagnostics/termux-omarchy-vscode-hyprland-gui-cleanup-device-20261009-02/receipt.json)

후속 stdout에는 GPU 자식의 exit 11·재시작과 DRM 장치 접근 거부가 남았다. 전체 VS Code 프로세스 종료와 동일한 현상으로 단정하지 않는다. 기본 세션에 없는 system D-Bus·udev 경고도 있었으며, 현재 증거만으로 원격 창 종료 원인을 확정하지 않는다. native PRoot를 직접 실행한 별도 시험은 내부 Hyprland 대신 outer Weston display를 사용해 비교 조건이 달랐으므로 내부 GUI 안정성 증거로 쓰지 않는다.

VS Code는 설치·CLI·확장 목록과 짧은 로컬 Wayland 창 표시까지 확인한 상태다. 실제 서버 인증·Remote-SSH 활성화·원격 파일 편집·장시간 GPU 안정성은 남아 있다. 전체 Omarchy, 개인 Neovim 설정, 입력 끊김 문제의 완료를 이 기록으로 주장하지 않는다.

### 임시 경로 수정 뒤의 재검사

현재 세션에서 정상 `gtk-launch chromium`과 `loopy-vscode --folder-uri vscode-remote://ssh-remote+loopy-development/home/loopy`를 실제 Hyprland에서 실행했다. Chromium은 3.593초, VS Code는 5.627초에 mapped window로 관찰됐고 35초 관찰 마지막에도 두 창과 동일 Linux 세션이 유지됐다. Chromium은 Xwayland, VS Code는 Wayland native다. [동시 실행](../../build/diagnostics/termux-omarchy-final-app-launch-device-20261009-01/receipt.json)

후속 검사에서 Remote-SSH resolver와 askpass가 실행되고 password 종류의 인증 요청까지 도달했다. 로그 원문·비밀번호·창 제목은 기록하지 않았다. 사용자는 처음 로그인을 나중에 진행한다고 답했지만 이후 실제 연결됐다고 확인했다. 새 로그에는 해당 별칭의 resolved 기록과 exec server 생성·cache 기록이 각각 1회 있다. 연결 재시도 중 resolver error 1회도 있어 이를 숨기지 않는다. 최신 고정 오류 분류에는 GPU exit 11·FATAL·extension host 비정상 종료·glue/f2fs·메모리 할당 실패가 없다. 원격 연결 성립은 사용자 확인과 로그를 함께 근거로 하며, 원격 파일 편집·장시간 안정성은 별도다. [인증 단계](../../build/diagnostics/termux-omarchy-final-code-health-device-20261009-02/receipt.json), [사용자 연결 확인 후 검사](../../build/diagnostics/termux-omarchy-final-code-health-device-20261009-03/receipt.json)

## 터미널의 현재 개인 설정

[현재 구성 읽기](../../build/diagnostics/termux-omarchy-terminal-convenience-readonly-device-20261009-01/receipt.json)는 native Termux의 기존 `.zshrc`와 격리 Linux의 개인 rc 진입점을 구분한다. Linux에는 zsh·tmux·Neovim·Git·SSH·fzf·fd·bat·eza·zoxide·Yazi·Foot·Wayland clipboard 도구가 있다. Linux profile 5개와 rc 연결을 확인했으며, 현재 bindings SHA는 `1a8af509d9f543fba57dbf3cfa81aabfdf7c3397eb23fa96f98744cd86f66bb3`다. 기본 Termux의 command 검사는 `$PREFIX/bin` 범위이며 전체 사용자 PATH나 기존 Termux Desktop 편의 기능 전부를 증명하지 않는다.

[새 실제 PTY 검사](../../build/diagnostics/termux-omarchy-terminal-profile-pty-device-20261009-02/receipt.json)에서 zsh 3회 시작은 0.148–0.152초였다. Git alias, `EDITOR=nvim`, fzf widget, zoxide, autosuggestions, syntax highlighting, Alt+Shift+C 폴더 검색 binding이 활성화됐다. 별도 소유 tmux 시험 서버에서 Ctrl+A·secondary prefix 없음·escape-time 0과 Alt+1…9/0 전체 창 선택을 확인하고 시험 서버만 종료했다. 실제 물리 키보드·화면 표시 지연이나 개인 Neovim 81개 플러그인 적용 증거는 아니다. 최초 PTY 시험은 FAILED로 보존하며 후속 PASS로 덮어쓰지 않는다.

## PRoot 임시 경로 수정과 적용 상태

설치된 proot-distro는 부모 환경을 재구성한다. `PROOT_TMP_DIR`를 부모에만 지정한 실제 CLI 비교는 glue 오류 11개·f2fs probe 경고 1개가 남았고, login 인자의 `-e PROOT_TMP_DIR=<native prefix/tmp>`로 전달한 비교는 stderr가 비었다. 게스트 `TMPDIR=/run/user/1000`은 유지한다. [부모 환경만 지정](../../build/diagnostics/termux-omarchy-proot-native-temp-compare-device-20261009-01/receipt.json), [명시적 전달](../../build/diagnostics/termux-omarchy-proot-native-temp-compare-device-20261009-02/receipt.json)

호스트 수정은 관련 48개 검사를 통과했다. 첫 실제 적용 작업은 보존 snapshot 경로 계산에서 실패하여 stop·source 교체 이전에 종료됐다. 두 번째 작업은 종료 도중 자식 프로세스가 바뀌어 `cleanup-unconfirmed`로 멈췄고 소스는 교체하지 않았다. 살아 있는 동일 세션 supervisor와 종료된 자식을 확인한 후, 세 번째 작업이 정상 종료 증거를 확보하고 `omarchy_commands.py` 하나를 교체했다. 원본과 설치 기록을 백업했으며 기존 세 업데이트 기록, 개인 rc·단축키·VS Code 설정, 전역 PRoot를 보존했다. 실패 기록을 PASS로 덮어쓰지 않았다. [첫 실패](../../build/diagnostics/termux-omarchy-proot-temp-runtime-install-device-20261009-01/receipt.json), [종료 재시도 전 확인](../../build/diagnostics/termux-omarchy-stop-cleanup-readonly-device-20261009-01/receipt.json), [실제 적용·재시작 PASS](../../build/diagnostics/termux-omarchy-proot-temp-runtime-install-device-20261009-03/receipt.json)

새 세션의 실제 native PRoot 환경에서 `PROOT_TMP_DIR=<native prefix/tmp>`와 `PROOT_EXITKILL=1`, 게스트의 `TMPDIR=/run/user/1000`을 확인했다. 후속 IPC 검사에서 원본 Omarchy bar·background가 자동 시작되고, 설정 오류 없이 1920×1280·배율 1.25·compositor 보고 60 Hz를 유지했다. 응답의 `shellReady=false`는 현재 코드의 고정값이며 실제 layer 부재를 뜻하지 않는다. 물리 입력 지연·표시 FPS, VS Code GPU 자식 오류 해결과 원격 인증 완료를 이 검사로 주장하지 않는다. [새 세션 화면 구성 확인](../../build/diagnostics/termux-omarchy-final-desktop-device-20261009-03/receipt.json)
