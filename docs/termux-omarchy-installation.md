# Termux의 격리 Omarchy 설치와 재실행

2026-10-09 기준 경로는 기존 Termux의 **새 `loopy-omarchy` 컨테이너 → patched Hyprland/Quickshell → private Weston 14 → Termux:X11**이다. 게스트 앱은 Wayland를 사용하고 Android 화면은 X11 Activity가 표시한다. 별도의 i3 kit나 기존 Loopy Android 내부 앱 세션을 Omarchy로 대체 표시하지 않는다. 기존 Termux HOME, 다른 컨테이너, Loopy 프로필과 설정을 유지한다.

실제 Omarchy 화면·GPU 픽셀·런처 재실행과 짧은 native Surface 관찰은 확인했다. 새 격리 Linux의 DNS/HTTPS, zsh·tmux·ripgrep 실행과 기존 XWayland 경로의 Chromium GPU 합성·공개 페이지 입력도 확인했다. 전용 AAudio 출력, Linux 볼륨·음소거와 Omarchy 오디오 메뉴도 연결했다. 개인 zsh/tmux/KeyBridge 바인딩을 추가하고 실제 tmux Alt 숫자·Foot 글자 크기 조절을 검사했다. Neovim·fd·fzf·Yazi·Waypipe와 개인 셸의 선택 도구를 추가했고 정상 Omarchy 런처에서 편집기/파일 관리자 표시와 공개 파일 저장을 확인했다. 사용자가 Lenovo Security 최초 동의와 자동 시작 허용을 완료한 뒤 키보드 서비스의 실제 연결을 확인했다. 물리 입력은 사용자 확인 대기다. [현재 검증 문서](termux-omarchy-validation.md)에 정확한 범위를 구분했다.

## 설치 후 한 명령어

ROOT가 검토한 런처를 관리 디렉터리에 배포한 뒤 **기본 Termux 셸**에서 실행한다.

```sh
python "$HOME/.local/share/loopy-omarchy/omarchy.py"
```

인수 없이 실행하면 `start`다. 종료·상태 조회는 같은 런처의 고정 동작을 사용한다.

```sh
python "$HOME/.local/share/loopy-omarchy/omarchy.py" stop
python "$HOME/.local/share/loopy-omarchy/omarchy.py" status
python "$HOME/.local/share/loopy-omarchy/omarchy.py" doctor
```

`start`는 고정된 `com.termux.x11/com.termux.x11.MainActivity`를 Termux의 `$PREFIX/bin/am`으로 연 뒤 입력 helper의 `ensure`를 실행한다. 소유한 10개 preset이 맞는지 확인하며, 원래 9개 snapshot이면 원본을 유지하고 accessibility 자동 실행 설정 하나만 추가한다. 사용자 변경은 덮어쓰지 않고 멈춘다. 이 확인이 성공해야 런타임을 시작한다. `stop/status/doctor`는 Activity나 입력 설정을 변경하지 않는다.

Activity 실행 파일은 Termux 소유의 symlink 아닌 일반 실행 파일, 64 KiB 이하, 링크 수 1, group/world 쓰기 비트 없음과 실행 비트를 확인한다. 고정 argv·`shell=False`·7초 제한이며 child 출력은 저장하지 않는다. 임의 Intent data나 명령어를 받지 않는다. `am` 성공이나 IPC `ready`를 물리 입력·전체 앱 기능의 수락으로 표시하지 않는다.

[최초 launcher01](../build/diagnostics/termux-omarchy-launcher-device-20261009-01/receipt.json)의 Activity 오류는 보존했다. [activity01](../build/diagnostics/termux-omarchy-activity-device-20261009-01/receipt.json)에서 `/system/bin/am`의 caller UID 거부와 Termux `am` 0.8.0의 성공을 확인해 경로를 수정했다. 현재 런처 `304996e5…`는 [중복 start/status](../build/diagnostics/termux-omarchy-launcher-device-20261009-03/receipt.json), [정상 stop](../build/diagnostics/termux-omarchy-launcher-device-20261009-04/receipt.json), [새 세션 start/status](../build/diagnostics/termux-omarchy-launcher-device-20261009-05/receipt.json)를 실제 기본 Termux 컨텍스트에서 통과했다. 새 start는 2.706초, status는 0.104초였다.

`stop`은 런타임이 기록한 자기 supervisor에게 정리를 요청한다. subreaper가 실제 자식들을 종료·reap한 뒤 소유한 socket/lock만 정리한다. `cleanup-unconfirmed`, 잃어버린 supervisor, 교체된 inode는 임의 PID kill이나 폴더 삭제로 복구하지 않는다. 기록을 보존하고 원인을 확인한다. 이미 살아 있는 동일 소유 세션의 `start`는 새 세션을 중복 생성하지 않는다.

## 재부팅 복구와 권한 경계

현재 런타임은 kernel boot UUID를 journal에 기록한다. 이전 부팅임이 확인됐을 때만 정확한 root/session/runtime inode·owner marker·기록된 자원을 검증하고 정리한다. 같은 부팅의 supervisor 유실, 교체되거나 미등록인 파일은 거부한다. boot ID가 없는 옛 journal은 이미 정상 종료된 경우만 이관한다. 실제 앱 UID에서 boot ID 읽기와 호스트 15개 복구 회귀는 통과했지만 **태블릿 재부팅 후의 실행 시험은 하지 않았다**. 자동 부팅 실행도 설치하지 않았다.

CLI는 Termux 앱 소유의 private HOME/PREFIX와 Linux 파일 권한으로 실행된다. guest는 `--user omarchy`이며 PRoot의 guest UID나 guest root는 Android root 권한을 제공하지 않는다. Android grant, 접근성 서비스 목록과 실제 연결은 각각 확인해야 한다. Y900에서는 사용자가 Lenovo Security의 Internet/Privacy Policy 동의를 완료하고 **Autostart Manager에서 Termux:X11의 자동 시작을 허용**한 뒤 KeyInterceptor가 연결됐다. 런처가 약관을 대신 수락하지 않는다. 설치된 shared-UID APK는 화면과 입력 서비스의 프로세스가 달라 실제 키 필터가 활성화되지 않는 추가 오류가 있었다. 같은 프로세스로 연결한 수정 후보를 준비했으며 설치·물리 확인 전이다. 서비스 연결만으로 모든 Android 예약 키를 회수했다고 표시하지 않는다. [현재 키보드 상태](termux-omarchy-validation.md#키보드cli-권한의-현재-상태)를 확인한다.

## 원격 연결

현재 기기의 Omarchy 런처에서 **Remote Connections**를 열거나 Linux 터미널에서 `omarchy-remote`를 실행한다. SSH terminal 또는 Wayland app을 선택하고 `user@host`/기존 SSH alias를 입력한다. Wayland 선택에서는 실행 파일 이름 하나를 입력한다. 앱 인수나 별도 SSH 옵션이 필요하면 CLI를 사용한다.

```sh
omarchy-remote ssh user@host
omarchy-remote ssh -p 2222 user@host
omarchy-remote wayland user@host foot
omarchy-remote wayland --no-gpu user@host foot
```

원격 Linux에도 Waypipe와 실행할 Wayland 앱이 필요하다. 원격 로그인 환경의 XDG_RUNTIME_DIR, SSH Unix 소켓 forwarding, Vulkan loader/driver가 있어야 GPU 프로토콜을 사용하는 기본 경로가 준비된다. `--no-gpu`는 원격 GPU 프로토콜을 끄는 명시적 대안이다. 평소 OpenSSH의 host key 확인·암호/키 인증을 사용한다. 메뉴가 인증 키를 자동 복사하거나 서버 권한을 자동 허용하지 않는다.

[현재 source·실기기 원격 검사](termux-omarchy-validation.md#ssh와-원격-wayland-앱)는 임시 Linux 시험 서버의 SSH·원격 앱 표시·공개 입력·저장·정상 종료까지 확인했다. 실사용 서버·RDP·인터넷 성능·물리 키 전달은 별도 남아 있다. 시험용 키와 서버는 제거했고 등록된 메뉴/helper는 유지했다. 이번 guest 배포는 [ready02](../build/diagnostics/termux-omarchy-remote-ready-device-20261009-02/receipt.json)에 원본 helper 백업과 새 SHA를 기록했다. 기존 개인 SSH 파일은 변경하지 않았다.

## 오디오 출력과 메뉴

현재 runtime은 자기 foreground PulseAudio/AAudio 출력과 Unix socket/cookie를 함께 관리한다. Linux 앱은 `unix:/run/user/1000/pulse/native`와 `/run/user/1000/pulse/cookie`로 연결된다. Omarchy QML의 볼륨 도우미는 `/usr/local/bin/omarchy-proot-audio`다. Linux 터미널에서 다음 명령을 사용한다.

```sh
omarchy-proot-audio status
omarchy-proot-audio volume 50
omarchy-proot-audio mute-toggle
```

`status`의 세 숫자는 볼륨 0–100, 음소거 0/1, 출력 사용 가능 0/1이다. 출력이 사라져도 Linux 창을 함께 종료하지 않는다. 오디오 자동 재시작은 아직 없으며 다시 실행할 때는 작업을 저장한 뒤 위 런처의 `stop`과 `start`를 사용한다. 최초 장애 시험의 종료 오류는 자식 exec 도중 명령줄만 바뀌는 경우였다. 현재 source는 소유 관계를 새로 확인한 뒤 종료를 이어가며, 실제 동일 장애→첫 stop→fresh start를 세 번 통과했다. 오디오 시작 직후 빈 cmdline을 잘못 기록하는 오류도 수정했다. `cleanup-unconfirmed`를 성공으로 간주하거나 별도의 임의 PID kill/폴더 삭제로 우회하지 않는다. 물리 마이크와 Android 전체 볼륨 설정은 이 도우미의 대상이 아니다.

## 현재 입력 설정 복원

적용된 Omarchy 입력 preset의 원본은 `omarchy-input.json`에 보존돼 있다. 이를 되돌리는 고정 helper 명령은 다음과 같다.

```sh
python "$HOME/.local/share/loopy-omarchy/omarchy_input.py" restore "$(python -c 'import uuid; print(uuid.uuid4())')"
```

helper가 적용한 값과 현재 값이 같은 알려진 설정만 복원한다. 현재 10개 snapshot과 옛 9개 snapshot 모두 지원하며, 관찰된 사용자 변경과 관련 없는 키는 보존한다. 부분 실패는 snapshot을 유지한다. CLI는 X11 전역 preference 저장소를 사용하고 조회·쓰기는 원자적 CAS가 아니므로 동시에 편집하지 않는다. 권한 grant나 accessibility 서비스 목록 자체를 복원하는 명령은 아니다. [정확한 preset·Escape 동작·검증 범위](termux-omarchy-validation.md#입력-설정과-되돌리기)를 확인한다.

## 개인 Linux 설정

새 Linux 터미널은 zsh를 사용한다. tmux는 Ctrl+A와 Alt+1…0으로 창을 선택하고, Foot는 Alt+- / Alt++로 글자 크기를 바꾼다. 현재 기기에는 Caps+D/F가 보내는 evdev 183/184를 `code:191`/`code:192`로 받아 이전/다음 작업공간으로 연결하는 후속 설정을 별도 적용했다. 이는 아래 고정 설치 묶음에 포함된 변경이 아니며 실제 입력 확인 범위는 현재 사용 안내(키보드와 트랙패드)에 기록한다. 기존 Meta 숫자 작업공간 바인딩은 유지한다. [개인 설정 문서](termux-omarchy-personal-profile.md)에 실제 검증 범위·source include·백업 연결을 정리했다. 위 X11 입력 `restore`는 이 Linux 개인 설정을 복원하지 않는다. 물리 키보드 서비스와 Meta/Alt 배열·clipboard/IME는 아직 전체 수락하지 않았다.

현재 서명된 추가 도구 25개를 설치해 패키지는 585개이며 기존 560개 버전은 유지됐다. 기본 편집기는 nvim이고 eza/bat/fd/fzf/zoxide와 zsh autosuggestions/syntax highlighting이 연결된다. `omarchy-launch-editor <path>`는 정상 새 Foot 창에서 실행되며 `omarchy-launch-or-focus-tui yazi <directory>`도 사용할 수 있다. 기존 TUI 런처의 PRoot 경로는 누락된 `xdg-terminal-exec` 대신 Foot를 직접 실행하도록 [source](../termux/omarchy-launch-tui)를 보완했다. 정확한 서명·버전과 배포 백업은 [검증 문서의 도구 추가](termux-omarchy-validation.md#추가-개발-도구와-정상-omarchy-실행-경로)에 연결했다. Waypipe 설치를 실제 원격 연결 완료로 간주하지 않는다.

## 현재 설치를 재현하는 고정 입력

| 입력 | 값 |
| --- | --- |
| upstream 소스 | BlackFireAlex/omarchy-android `c189d33bf34a7a50fad3ff46bbd97e5c29b48910` |
| bundle | `omarchy-android-aarch64-0.1.1.bundle.tar`, 1,181,941,760 bytes |
| outer SHA256 | `7e9f1cd67533bc0d3988b5cb3831aef52f1527dd90391d9d868ed9345021cdb2` |
| rootfs SHA256 | `dbee00c0cb41f6b213c153ff4dc1c0898ba99dd0543ac13cef1601820366e2c5` |
| package lock SHA256 | `1d2935de23e434f37731052ba868e9833cba541afd517ff4e130c832d397b550` |
| patched X11 backend SHA256 | `8cfb78a4a1a146596228c34f55562c3325c10bc355a5dff5f5765ca77093ea0e` |
| private Weston package | lfdevs/anland-termux `5.13.3`, `weston_14.0.2-3_aarch64.deb` |
| Weston deb SHA256 | `25d1c5ee4013e14097d6e37a3227d6fcef8f43d6d7a2dd0ee130a77e1af31c8a` |
| reviewed private host payload SHA256 | `939ad9f94b1cfe96d4472b3c3bb9323c8ec9191d8c88fa2fca3e2064c273f728` |
| private host manifest SHA256 | `6c07cb0968ef9aef7caaefc311aeaffe119290957eb5bbf11245d860f1155c3d` |
| current native + guest + tools + workflow setup SHA256 | `b59230fa13e16cf230f166432a6ed260483873cbd192f21aa32e5a770a0152a9` |
| guest payload / manifest SHA256 | `49112da74b842970dde875334a1a1fd488c35dbd24a42badfbbb2cf94beb5e4f` / `23f46b7836d26ef0c2088ab172238b7f7c982cfc3d19f912e5325ded76a36547` |
| workflow payload / manifest SHA256 | `f6227b03cc7a24b946b615589bfb1ddf7ddede999da8fe42de4697c6bce0c5cf` / `74f20e68ac2e3a632306c1379f927cabc01ab8a7d46ba71213d1e40c1f863d08` |
| developer tools manifest SHA256 | `bb331b6bd248f2246f6caa6b3ff14b5f9771ebfca8049660c69a243e7383da84` (29 packages + 29 detached signatures) |

[출처·설치 검토](research/2026-10-09-omarchy-termux-install-audit.md)와 [Wayland/GPU 경로 검토](research/2026-10-09-termux-omarchy-native.md)에 원본 링크와 패치 경계를 기록했다. upstream `install/start/stop` 스크립트는 실행하지 않는다. 현재 repository apt Weston은 16이므로 bundle의 ABI 14 backend를 연결하거나 전역 Weston을 downgrade하지 않는다.

## 재현 순서

1. 기존 `com.termux`/`com.termux.x11` 설치와 서명을 유지한다. 기본 Termux UID/SELinux 컨텍스트에서 작업한다. `run-as`는 준비 수단이며 실제 앱 컨텍스트 실행을 대신하는 수락 증거가 아니다. Python, proot-distro **5.8.x**, termux-x11-nightly, xprop, xwininfo, native pulseaudio/pactl와 AAudio sink, D-Bus와 native Mesa/Turnip 의존성을 먼저 확인한다. 실제 고정 버전/ABI와 패키지 추가는 별도 검토 단계다. 현재 추가 의존성 `libc++=30`도 private Weston 로더의 준비 조건이다.
2. outer bundle을 새 소유 staging 경로에 둔다. 현재 staging은 `$HOME/.local/share/loopy-omarchy-install-stage-20261009-01/bundle.tar`다. [installer](../termux/omarchy_install.py)는 outer hash, `SHA256SUMS`, manifest와 package closure를 모두 확인한 뒤 새 컨테이너만 설치한다. host에는 guest rootfs의 절대 symlink를 추출하지 않는다.
3. [native + guest setup 묶음](../build/deliverables/LoopyOmarchy-Termux-native-setup-20261009-05.tar.gz)과 [archive checksum](../build/deliverables/LoopyOmarchy-Termux-native-setup-20261009-05.tar.gz.sha256)을 대조하고 본인 소유 0700 폴더·0600 일반 파일로 준비한다. base installer, native 런처 9개, private Weston14와 guest 오디오/Android 설정, 개인 셸·키 설정·앱/원격 런처 payload와 서명된 개발 도구 29개·manifest·license를 포함한다. 같은 폴더에서 `python ./omarchy_setup.py --bundle <owned bundle.tar>`로 호출한다. 별도 소스·payload 경로는 `--sources`, `--weston-payload`, `--weston-manifest`, `--guest-payload`, `--guest-manifest`, `--workflow-payload`, `--workflow-manifest`, `--tools-dir`로 지정한다. [통합 명령](../termux/omarchy_setup.py)은 모든 입력의 고정 SHA와 경계를 base root 생성 전에 검증한다. 큰 rootfs bundle과 Termux native 패키지는 archive에 포함되지 않는다. Linux 개발 도구 archive와 detached signature는 포함된다.
4. 통합 명령의 [private Weston installer](../termux/omarchy_host_install.py)가 `weston-host/{bin,lib,share}`를 준비한다. 고정 tar의 member·path·type·mode·전체 87개 파일 SHA를 먼저 확인하고 새 private stage에만 쓰며, 전체 inventory와 실제 `weston 14.0.2` 실행을 확인한 뒤 exclusive directory rename으로 게시한다. 기존 동일한 완성본은 파일·디렉터리 inode를 유지하고 재사용한다. 변경 파일·추가 파일·symlink·불완전 journal은 보존하고 거부한다. 신규 host는 현재 세션이 없거나 정상 종료가 확인됐을 때만 준비한다. 별도 `weston-install.json`에 UID/root/host identity·source pins·phase를 기록하고 원래 base journal과 `weston-host.json`은 유지한다. 이전 기기 전용 materializer는 최초 설치의 역사적 증거로 남기며 새 설치에서 호출하지 않는다.
5. [guest 연동 installer](../termux/omarchy_guest_install.py)가 helper 5개, AndroidSettings QML·Network/Bluetooth panel·qmldir, Hyprland와 browser의 PulseAudio 주소 등 총 11개 파일을 준비한다. 모든 대상을 먼저 검사해 정확한 원본 SHA 또는 적용된 SHA만 수락하고 사용자 수정·symlink·누락된 필수 원본은 유지하며 거부한다. 변경은 세션이 없거나 정상 종료가 확인됐을 때만 허용하고 실제 runtime-control.lock을 함께 잠근다. 원본 5개를 private backup에 저장·fsync한 뒤 파일을 게시하며 중간 오류의 backup과 INSTALL_UNKNOWN journal은 보존한다. 이미 일치하는 설치는 source inode를 유지하며 guest-install.json만 최초 등록한다. native 런처 9개의 기존 바이트·inode 보존과 실행 중 누락 파일 추가 거부도 유지한다. 개발 도구 설치는 아래 별도 단계에서 같은 명령으로 처리한다.

   같은 명령의 [workflow installer](../termux/omarchy_workflow_install.py)는 검증한 개인 profile 5개·rc entry 2개·Foot/Hypr/tmux 설정 3개·TUI/focus launcher 3개·remote helper/desktop entry 2개를 함께 준비한다. [workflow manifest](../build/diagnostics/termux-omarchy-workflow-payload-20261009-01/workflow-manifest.json)의 SHA·mode·원본 SHA가 모두 맞을 때만 적용하고 변경 원본 6개를 먼저 백업한다. 사용자 rc/설정이 다른 경우 전체 적용을 거부하며 기존 파일은 유지한다. adapter와 별도 `workflow-install.json`을 쓰며 같은 설치/runtime lock을 사용한다. 현재 설치본의 개인 owner.json과 원래 profile backup은 변경하지 않는다. 새 설치의 소유/백업 기록은 native managed root의 workflow journal에 있으며 기존 personal API의 owner.json을 자동 생성하거나 자동 복원하지 않는다.

Android 설정 연동의 guest `/usr/local/lib/loopy-omarchy/omarchy_android_client.py`, `/usr/local/bin/omarchy-proot-settings`, shell `Ui/AndroidSettings.qml`과 qmldir 등록은 이제 위 guest installer가 함께 준비한다. [UI patch](../termux/omarchy-settings.patch)에는 Network·Bluetooth의 PRoot 분기와 **`Ui/qmldir` type 등록**이 함께 필요하다. 현재 source hash·원본 백업·정확한 설치 경계는 [설정 연동 배포](../build/diagnostics/termux-omarchy-settings-upgrade-device-20261009-01/receipt.json), [등록 보정](../build/diagnostics/termux-omarchy-settings-ui-register-device-20261009-01/receipt.json), [운영 증거 보강](../build/diagnostics/termux-omarchy-settings-operation-evidence-device-20261009-01/receipt.json)에 있다. 수정한 사용자 파일에 이 patch를 자동 강제 적용하지 않는다. [현재 검증 문서](termux-omarchy-validation.md#android-설정-연동의-범위)의 실제 호출 범위·남은 키보드 권한을 먼저 확인한다.

6. [tools installer](../termux/omarchy_tools_install.py)는 고정 [29개 package manifest](../build/diagnostics/termux-omarchy-tools-payload-20261009-01/tools-manifest.json)의 압축본·detached signature를 private guest stage에 준비한다. [guest worker](../termux/omarchy_tools_guest.py)는 기존 trusted keyring의 GPG VALIDSIG·FULLY/ULTIMATE trust와 실제 pacman package metadata를 대조한다. 새 key import나 sync DB refresh는 하지 않으며 별도 options-only config의 Required/TrustedOnly를 사용한다. 이미 같은 버전인 도구는 재설치하지 않고, 버전이 다른 기존 도구는 보존하며 거부한다. 누락된 package만 실제 pacman 설치 계획에 나타나는지 검토한 뒤 기존 모든 package 버전을 유지하며 추가한다. 변경은 정상 종료된 세션에서만 허용하고 같은 install/runtime lock을 사용한다. 시스템 pacman config·core/extra sync DB의 SHA를 전후 대조한다. `tools-install.json` 및 guest transaction 기록의 INSTALL_UNKNOWN은 보존하고 자동 재시도하지 않는다. API 의미는 [pacman](https://man.archlinux.org/man/pacman.8.en)·[keyring](https://man.archlinux.org/man/pacman-key.8.en) 공식 문서에 따른다.

7. 설치 후 `python "$HOME/.local/share/loopy-omarchy/omarchy.py"`로 데스크톱을 실행한다. 런타임은 빈 X display `:20`–`:99`, 자기 UUID 상태와 짧은 `/data/data/com.termux/lr` owner marker를 사용한다. HOME/storage를 guest에 bind하지 않는다. 전용 오디오 출력만 연결하고 마이크·Android 전체 오디오 설정·OS roles·프로세스 정책은 변경하지 않는다. 입력 helper는 앞서 설명한 10개 X11 설정만 관리한다. 알 수 없는 socket이나 세션은 채택하지 않는다.

이 태블릿에는 [runtime 묶음 전달](../build/diagnostics/termux-omarchy-runtime-delivery-device-20261009-01/receipt.json)을 마쳤다. 기본 Termux의 `$HOME/.local/share/loopy-omarchy-native-runtime-20261009-01/`에 archive·checksum·README를 보관하고 실제 앱 UID에서 archive와 9개 내부 SHA를 대조했다. [기존 설치 적용](../build/diagnostics/termux-omarchy-runtime-adopt-device-20261009-01/receipt.json)은 원본 journal을 private 백업하고 같은 소스 SHA만 등록했으며 Linux 재시작이나 소스 재작성은 하지 않았다. 이 전달과 기존 설치 적용은 새 기기의 전체 설치 성공을 뜻하지 않는다.

후속 [native setup 전달·실행](../build/diagnostics/termux-omarchy-native-setup-delivery-device-20261009-01/receipt.json)은 Weston payload를 포함한 archive 18개 파일을 실제 앱 UID에서 대조·준비한 뒤 **압축본에서 나온 통합 명령의 기본 경로**로 현재 설치를 재사용했다. 이 태블릿에서 실행할 명령은 다음과 같다. 모든 기존 source·host 파일과 base/legacy/host journal의 바이트가 유지됐다. 정상 Linux 세션도 유지됐으며 권한 변경·재시작은 하지 않았다.

```sh
python "$HOME/.local/share/loopy-omarchy-native-setup-20261009-01/source/omarchy_setup.py" \
  --bundle "$HOME/.local/share/loopy-omarchy-install-stage-20261009-01/bundle.tar"
```

[실기기 설치 검사](../build/diagnostics/termux-omarchy-host-setup-device-20261009-01/receipt.json)는 앱 UID 38개 검사와 별도 시험 HOME의 실제 Weston 87개 새 설치·version 실행을 통과했다. 이 시험 HOME은 Linux rootfs를 새로 설치하지 않았으며 원래 container identity와 native 의존성을 사용했다. 전체 새 기기의 Omarchy·guest 통합 완료를 뜻하지 않는다.

현재 개발 도구까지 재현할 때는 [고정 archive manifest](../build/diagnostics/termux-omarchy-tools-archives-20261009-02/manifest.json)와 기존 trusted keyring으로 전체 서명을 확인하고, 현재 설치 목록과 비교해 새 패키지만 추가하는 pacman 계획을 먼저 검토한다. 기록된 device runner는 이 태블릿의 정확한 session/목록에 묶인 영수증용 코드이므로 다른 설치에 그대로 실행하지 않는다. 전체 DB refresh나 오래된 데스크톱 패키지 upgrade로 이 추가를 대체하지 않는다. TUI source는 guest `/usr/share/omarchy/bin/omarchy-launch-tui`의 원래 `f53f3f47…` 바이트와 symlink/소유권을 확인·백업한 뒤 repository source `2328d269…`로 교체한 상태다. `/usr/local/bin/omarchy-launch-tui`는 해당 guest 경로의 symlink로 유지한다. [실제 배포](../build/diagnostics/termux-omarchy-tui-upgrade-device-20261009-01/receipt.json)에 원본 백업 위치가 있다.

현재 설치의 후속 수정으로 runtime `e88e8bb7…`/resources `b7df91ac…`와 [generic focus](../termux/omarchy-launch-or-focus) `4c103e1b…`/[TUI focus](../termux/omarchy-launch-or-focus-tui) `f0654a85…`도 적용했다. [배포 영수증](../build/diagnostics/termux-omarchy-yazi-launch-upgrade-device-20261009-01/receipt.json)에 네 원본의 정확한 SHA와 private 백업 위치가 있다. guest symlink는 유지하며 다른 사용자 설정을 덮어쓰지 않았다. 공백·특수 문자 인수를 보존하고 소유 Yazi DDS 서버의 정상 재생성을 인증한다. 이 태블릿의 session/소스에 묶인 device runner를 다른 설치에 그대로 재실행하지 않는다. [실제 8회 재실행·정상 종료/시작 검사](../build/diagnostics/termux-omarchy-yazi-repeat-gui-device-20261009-02/receipt.json)를 확인한다.

## 확인된 범위와 남은 검증

- [실제 설치 영수증](../build/diagnostics/termux-omarchy-install-device-20261009-01/receipt.json): native Termux UID 10323/`untrusted_app_27`에서 새 컨테이너와 관리 backend 설치, exit 0.
- [private Weston14](../build/diagnostics/termux-omarchy-weston-host-20261009-01/receipt.json): 고정 payload 87개 파일 대조 및 `weston 14.0.2` 실행.
- [native GPU](../build/diagnostics/termux-omarchy-native-gpu-20261009-02/receipt.json): Zink/Turnip의 실제 Adreno 830 renderer와 공개 녹색 픽셀 검사 통과.
- [guest GPU](../build/diagnostics/termux-omarchy-guest-gpu-20261009-01/host-receipt.json): 같은 Termux 컨텍스트의 Arch PRoot에서 Freedreno `Adreno (TM) 830v1`과 공개 녹색 픽셀 검사 통과.
- [nested parent](../build/diagnostics/termux-omarchy-native-parent-20261009-04/receipt.json): Weston GL renderer·1920×1280 X output·요청 60 Hz 및 소유 프로세스 정리 검사 통과. 이는 전체 Hyprland/Quickshell의 실제 화면·입력·지속 FPS를 입증하지 않는다.

첫 runtime START01은 정상 guest symlink를 리소스 inventory가 거부해 실패했다. 원본 실패를 보존하며 후속 START02는 1.541초에 준비돼 실제 Quickshell·wallpaper·커서 한 개를 확인했다. IPC는 Hyprland 0.56.1/commit `5c897c03…`, 1920×1280/60 Hz/scale 1.6, config errors 없음을 확인했다. 공개 Foot/PTY 문자열·Escape 합성 수신은 통과했으나 Meta 조합과 마우스는 미수락이다. 현재 boot-aware 소스로 정상 종료 뒤 새 세션 재실행도 통과했다.

소유 Android Surface의 2.1초 관찰에서 126개 presentation buffer/59.524 FPS를 기록했다. Linux의 모든 frame 신선도·입력 지연·장시간 안정성·144 FPS를 측정한 값은 아니다. 물리 입력, 키보드 서비스 실제 연결, 재부팅 시험과 전체 앱·서비스 통합은 남아 있다. bundle의 Linux Chromium wrapper에는 sandbox-off 구성이 있으므로 sandbox가 검증된 브라우저로 표시하지 않는다. installer/runtime 준비는 browser를 실행하지 않았고, 이후 별도 공개 로컬 페이지·새 프로필 검사에서 기존 XWayland/ANGLE Vulkan GPU 합성과 WebGL·합성 입력이 통과했다. 직접 Wayland Chromium 후보의 GPU 합성은 아직 통과하지 않았다. [현재 영수증·제한](termux-omarchy-validation.md)을 기준으로 확인한다.

## 이전 native + guest 묶음

[실기기 guest setup](../build/diagnostics/termux-omarchy-guest-setup-device-20261009-01/receipt.json)은 실제 앱 UID에서 검사 54개와 별도 작은 rootfs fixture의 11개 설치·원본 5개 백업을 통과했다. 현재 rootfs에는 파일을 교체하지 않고 같은 설치를 등록했고 실제 guest UID 1000의 audio status·Android settings ping도 통과했다. 작은 fixture는 새 Linux rootfs 전체를 설치하거나 실행한 시험이 아니다.

[현재 묶음 전달·기본 경로 실행](../build/diagnostics/termux-omarchy-integrated-setup-delivery-device-20261009-02/receipt.json)은 archive 22개 파일을 검증·준비하고 아래 한 명령으로 native+guest setup을 실행했다. 기존 런처·Weston·guest 11개 파일의 바이트·inode, 4개 journal의 바이트, 동일 Linux 세션을 유지했다. 최초 [delivery01](../build/diagnostics/termux-omarchy-integrated-setup-delivery-device-20261009-01/receipt.json)은 검사 스크립트의 옛 파일 개수 18 조건 때문에 압축 해제 전 실패했으며 source 디렉터리 생성이나 설치 실행은 하지 않았다. 이 실패를 보존하고 조건을 수정한 별도 delivery02로 검증했다.

```sh
python "$HOME/.local/share/loopy-omarchy-native-setup-20261009-02/source/omarchy_setup.py" \
  --bundle "$HOME/.local/share/loopy-omarchy-install-stage-20261009-01/bundle.tar"
```

당시 묶음에는 개인 도구/프로필 배포가 포함되지 않았다. 전체 새 기기 설치·물리 입력·키보드 서비스 연결·지속 성능과 144 FPS·모든 앱 로그인 수락은 남아 있다. 설치 명령의 `fullDesktopConfigured=false`는 이 범위를 완료로 표시하지 않는 경계다.


## 이전 개인 설정·앱·원격 런처 통합 묶음

[호스트 검사](../build/diagnostics/termux-omarchy-workflow-setup-green-20261009-01/receipt.json)는 설치기 59개와 원격 helper 15개, 총 74개를 통과했다. [실기기 검사](../build/diagnostics/termux-omarchy-workflow-setup-device-20261009-01/receipt.json)는 실제 앱 UID 10323에서 설치기 59개, 별도 작은 rootfs fixture에 workflow 15개 설치·정확한 원본 6개 백업, 현재 Linux의 Foot 설정·zsh 문법·원격 도움말·런처 문법 실행을 통과했다. fixture는 새 Linux rootfs 전체를 설치하거나 부팅한 시험이 아니다.

[압축본 전달·기본 CLI 실행](../build/diagnostics/termux-omarchy-workflow-setup-delivery-device-20261009-01/receipt.json)은 archive 25개를 검증하고 아래 한 명령을 실행했다. 기존 Weston 87개·native 런처 9개·guest adapter 11개·workflow 15개 파일과 설치 journal 5개 및 동일 세션을 유지했다. 권한 변경이나 Linux 재시작은 없었다.

```sh
python "$HOME/.local/share/loopy-omarchy-native-setup-20261009-03/source/omarchy_setup.py" \
  --bundle "$HOME/.local/share/loopy-omarchy-install-stage-20261009-01/bundle.tar"
```

당시 묶음에는 큰 rootfs bundle과 추가 개발 도구 패키지가 포함되지 않았다. 새 기기 전체 설치, 재부팅·물리 키보드/마우스·지속 성능·앱 로그인 수락은 계속 남아 있다.


## 현재 개발 도구까지 통합한 묶음

최신 배포는 아래 **새 Linux 설치와 원본 권한 수정**의 05 묶음이다. 이 절의 04 검사는 당시 기존 설치 재사용의 역사적 증거다.

[호스트 검사](../build/diagnostics/termux-omarchy-tools-setup-green-20261009-01/receipt.json)는 설치기 74개·원격 helper 15개, 총 89개를 통과했다. [실기기 검사](../build/diagnostics/termux-omarchy-tools-setup-device-20261009-01/receipt.json)는 실제 앱 UID에서 설치기 74개와 기존 guest trusted keyring으로 전체 29개 서명을 확인했다. 기존 도구가 모두 같은 버전이라 package transaction 없이 설치를 등록했고, 다시 실행해 journal 바이트를 유지했다. 현재 package 585개/모든 버전·시스템 pacman config·core/extra sync DB·같은 Linux 세션을 유지했다.

[압축본 전달·기본 CLI 실행](../build/diagnostics/termux-omarchy-tools-setup-delivery-device-20261009-01/receipt.json)은 30,333,574-byte archive의 파일 86개를 검증하고 아래 한 명령을 실제 앱 컨텍스트에서 실행했다. 기존 source/adapter/workflow 파일과 journal 6개·package/DB/config·동일 세션을 유지했다.

```sh
python "$HOME/.local/share/loopy-omarchy-native-setup-20261009-04/source/omarchy_setup.py" \
  --bundle "$HOME/.local/share/loopy-omarchy-install-stage-20261009-01/bundle.tar"
```

이 04 묶음 검사 당시 새 package transaction 경로는 호스트에서 외부 pacman/GPG 경계를 대체한 시험만 수행했다. 이 현재 기기 재사용 검사와 이전 수동 package 추가를 새 installer의 실제 신규 transaction 성공으로 합치지 않는다. 당시 새 기기 전체 설치·신규 transaction·재부팅·물리 키보드/마우스·지속 성능·전체 앱/로그인 수락은 남아 있었다. 최신 신규 transaction 범위는 아래에 따로 기록한다.

## 새 Linux 설치와 원본 권한 수정

[실제 새 container 검사](../build/diagnostics/termux-omarchy-fresh-setup-device-20261009-03/receipt.json)는 별도 빈 HOME/PREFIX에서 실제 PRoot-Distro 5.8을 사용해 고정 bundle을 새로 설치했다. 통합 CLI가 본체·private Weston·guest adapter·tools·workflow 모두 `INSTALLED`로 끝났고 총 설치 시간은 93.358초였다. 기존 556개 package의 버전을 유지하며 신뢰 서명을 확인한 도구 29개만 추가해 585개가 됐다. 시스템 pacman config와 core/extra DB를 유지했다. 기존 데스크톱 token·native journal·개인 설정은 보존했다.

첫 [신규 설치 실패](../build/diagnostics/termux-omarchy-fresh-setup-device-20261009-02/receipt.json)에서는 workflow 원본 mode와 설치 후 mode를 혼동했다. [읽기 감사](../build/diagnostics/termux-omarchy-fresh-workflow-audit-device-20261009-01/receipt.json)에서 원본 SHA는 모두 일치하지만 Foot/Hypr/tmux 원본은 `0644`, TUI launcher 원본은 `0755`임을 확인했다. [workflow source](../termux/omarchy_workflow_install.py)는 이 네 경로의 정확한 원본 mode를 고정했고 [guest installer](../termux/omarchy_guest_install.py)는 알려진 원본 내용·mode를 확인한 뒤 원하는 `0600`·`0700`으로 바꾼다. 다른 mode나 사용자 편집은 보존하며 전체 적용을 거부한다. 원본 6개의 내용·mode는 별도 workflow journal과 백업에 남긴다.

[호스트 92개](../build/diagnostics/termux-omarchy-original-modes-green-20261009-01/receipt.json)와 [실제 앱 UID의 설치기 77개](../build/diagnostics/termux-omarchy-original-modes-device-20261009-01/receipt.json)가 통과했다. 후자의 전체 driver는 `/usr/sbin` 정상 alias를 `/usr/bin` 문자열만으로 검사해 진단 assertion에서 실패했으므로 전체 driver 성공으로 취급하지 않는다. [후속 실제 PTY](../build/diagnostics/termux-omarchy-fresh-pty-device-20261009-01/receipt.json)는 정규화한 경로와 새 zsh·Git 별칭·Neovim/tmux/Waypipe, workflow 15개와 원본 백업을 확인했고 ZLE 경고 없이 통과했다. 물리 키 입력 지연 측정은 아니다.

현재 [05 archive](../build/deliverables/LoopyOmarchy-Termux-native-setup-20261009-05.tar.gz)는 30,334,195 bytes/SHA `b59230fa…`, 86개 파일이다. [실기기 배포](../build/diagnostics/termux-omarchy-original-modes-delivery-device-20261009-01/receipt.json)는 archive 전체 SHA와 86개 내부 파일, 압축본의 기본 CLI 실행·같은 Linux 세션과 파일/journal 보존을 확인했다. 기본 Termux에서 다음 명령을 사용한다.

```sh
python "$HOME/.local/share/loopy-omarchy-native-setup-20261009-05/source/omarchy_setup.py" \
  --bundle "$HOME/.local/share/loopy-omarchy-install-stage-20261009-01/bundle.tar"
```

이 새 container 시험은 기존 Termux Python·PRoot·native 라이브러리를 재사용했다. **native 의존 패키지 bootstrap와 새 container의 그래픽 시작은 검사하지 않았다.** 따라서 `freshContainerComponentsVerified=true`, `actualNewToolsTransactionVerified=true`지만 `fullFreshInstallVerified=false`·`fullDesktopConfigured=false`를 유지한다. 재부팅·물리 입력·OEM 동의·지속 성능/144 FPS·전체 앱/로그인과 OS 수준 서비스 수락은 계속 남아 있다.

[검사용 저장소 정리](../build/diagnostics/termux-omarchy-fresh-cleanup-device-20261009-01/receipt.json)는 이번에 만든 두 container와 복제한 rootfs 압축본만 제거했다. 정확한 root/rootfs inode와 원본 고정 SHA, 활성 세션을 거부하는 PRoot-Distro exclusive lock을 확인했다. 기존 데스크톱·6개 journal은 유지됐고 사용 가능 공간이 11,612,647,424 bytes 늘었다. 시험의 소스/영수증과 작은 component는 보존했으며 현재 native 설치나 다른 프로젝트 캐시는 삭제하지 않았다.
