# 현재 Termux 설치와 Omarchy 전체 범위 대조

## 최신 실제 설치 599개 기준

2026-10-09 Neovim 지원 도구 7개 설치 후의 [실제 기기 inventory](../../build/diagnostics/termux-omarchy-full-package-metadata-device-20261009-03/installed-inventory.json)와 [기기 조회 영수증](../../build/diagnostics/termux-omarchy-full-package-metadata-device-20261009-03/receipt.json)을 기준으로 다시 계산했다. **원본 158개 요청 중 57개 충족, 101개 미충족**이다. 592개 기준보다 `lazygit`, `lua51`, `luarocks`, `tree-sitter-cli`, `unzip` 5개 요청이 추가 충족됐다. 함께 설치된 `lua-luarocks`, `zip`은 원본 요청 밖의 의존 패키지다. 이전 592개 패키지의 버전·제공·충돌·의존 metadata는 모두 그대로다.

이 결과는 추정 inventory가 아니라 새 실기기 추출본과 정확히 일치한다. 패키지 목록 SHA256은 `bf595ab948376ab481a53d5a969320a93c20341ad3e0d78560bd766d1928a679`, metadata SHA256은 `ec3561c1c89fcaf3c6482f735ae0c186c66e9259c4e37f09c233362e57a1f40f`다. 동일 원본 158개 목록, 동일 고정 DB, 기존 resolver와 원본 libalpm 비교기를 사용했으며, 새 기기 영수증의 version comparison 3개와도 일치했다. 별도 [계산 영수증](../../build/diagnostics/termux-omarchy-coverage-post-nvim-20261009-01/receipt.json), [요청별 충족 근거](../../build/diagnostics/termux-omarchy-coverage-post-nvim-20261009-01/coverage.json), [입력 해시](../../build/diagnostics/termux-omarchy-coverage-post-nvim-20261009-01/source-refs.json), [재현 스크립트](../../build/diagnostics/termux-omarchy-coverage-post-nvim-20261009-01/reproduce.py)를 보존했다.

기존 버전을 유지하는 [최신 추가 전용 transaction](../../build/diagnostics/termux-omarchy-coverage-post-nvim-20261009-01/transaction.json)은 **새 패키지 329개**, 다운로드 **1,244,254,215 bytes**, 설치 크기 **4,908,271,860 bytes**이며, 아래의 GStreamer 3개·GVfs 1개·Nerd Font 충돌 1개는 동일하게 남아 `unresolved`다. 전체 의존성이 해소되거나 archive 서명 검증이 끝난 설치 transaction이 아니다. 592개 기준의 전체 교체 후보도 과거 입력 기준 문서로 보존하며 현재 599개에 그대로 적용하지 않는다.

이번 계산은 ADB·네트워크·패키지 쓰기 없이 수행한 ALPM metadata 대조다. `pacman -T`의 새 실행 결과나 전체 앱·서비스 동작 완료율로 표시하지 않는다. 개인 Neovim 설정과 plugin 적용, 원본 메뉴의 Android 동작 연결은 별도 범위이며 [실행·Android 어댑터 감사](2026-10-09-omarchy-launch-android-adapter-audit.md)에 남은 실행 경로를 기록했다.

## 보존 기록: 한글 입력 설치 직후 592개 기준

아래 본문과 표의 ‘현재’·‘최신’은 당시 592개 inventory를 뜻한다. 영수증과 계산 출력은 수정하지 않았으며, 현재 인계 수치는 위의 599개·57/158을 사용한다.

2026-10-09, 한글 입력 패키지 설치 후 연결된 Y900 `Y900`의 실제 Termux UID 10323에서 PRoot guest UID 1000으로 ALPM metadata를 다시 조회했다. [최신 실기기 영수증](../../build/diagnostics/termux-omarchy-full-package-metadata-device-20261009-02/receipt.json)은 패키지 목록 전후 일치, 같은 Linux 세션과 오디오·Android 설정 서비스 ready를 확인했다. 이 조회와 후속 오프라인 계산은 설정·패키지 변경이나 데스크톱 재시작을 하지 않았다.

원본 고정 소스는 `81145eb1fd41532fcae4310b26f860608e2eaf82`이며, 원본 요청 158개를 최신 설치 metadata의 패키지 이름과 `provides`에 대조했다. **52개 요청이 충족되고 106개는 충족되지 않았다.** 현재 총 설치 패키지 수 **592개**는 의존성을 포함한 수다. 52/158은 앱 실행·서비스·물리 입력·사용 경험의 완료율이 아니다. 이번 대조는 새 실기기 inventory를 사용한 오프라인 계산이며, `pacman -T`를 다시 실행한 결과로 표시하지 않는다.

원본 패키지 이름과 설치 패키지 이름이 다른 경우에도 ALPM 제공 항목을 함께 검사했다. 예를 들어 원본 `nvim` 요청은 현재 설치에서 충족된다. 이름만 비교해 Neovim을 미설치로 표시하지 않는다. 반대로 패키지가 설치됐어도 Android 하드웨어 접근이나 systemd 서비스 동작을 수락한 것은 아니다.

이전 원본 전체 transaction 914개는 현재 설치 버전을 기준으로 계산한 추가 전용 transaction이 아니다. 이를 현재 설치에 그대로 합치면 GPU·Hyprland ABI와 라이브러리가 바뀔 수 있다. 현재 설치 완료 증거로 합치지 않으며, 필요한 추가 transaction과 서비스 대체 경로를 별도로 검증해야 한다.

현재 Termux bundle의 Omarchy 고정 소스는 원본 전체 범위의 고정 소스와 다르다. 이 문서는 원본 158개 요청을 현재 설치에 대조한 것이며, 원본 소스·51개 매뉴얼 장·119개 QML까지 모두 적용됐다고 표시하지 않는다. 그 세 범위와 Android/OS 연동 기능은 계속 완료 조건이다.

[최신 계산 영수증](../../build/diagnostics/termux-omarchy-additions-post-ime-20261009-01/receipt.json), [요청별 충족·제공 패키지](../../build/diagnostics/termux-omarchy-additions-post-ime-20261009-01/coverage.json), [입력 파일 경로·해시](../../build/diagnostics/termux-omarchy-additions-post-ime-20261009-01/source-refs.json), [원본 전체 설계](../superpowers/specs/2026-10-06-omarchy-full-design.md).

최신 [inventory](../../build/diagnostics/termux-omarchy-full-package-metadata-device-20261009-02/installed-inventory.json)는 ALPM 592개의 버전·`provides`·`conflicts`·`depends`를 포함한다. 목록 SHA256은 `2d33532c98c71ac342d77f240f9fcdfdcea360a6b86832334c74facf027c8e97`, metadata SHA256은 `54d8051ae0bb8918a36674c4168f885edc8f6662609c8475deb6f2fb6d5328a4`다. 두 해시와 실기기 영수증에 포함된 inventory의 일치를 확인했다. 고정된 원본 libalpm 비교기를 호스트에서 빌드해 실기기 version comparison 3개의 결과와 대조했고, 원본 패키지 목록·고정 DB의 해시도 검증했다.

이 inventory로 기존 설치 버전을 유지하는 [추가 전용 transaction](../../build/diagnostics/termux-omarchy-additions-post-ime-20261009-01/transaction.json)을 다시 계산했다. 원본 요청 158개를 유지하며 **새 패키지 336개**, **다운로드 1,252,296,487 bytes**, **설치 크기 4,941,896,570 bytes**를 식별했다. 기존 이름의 패키지를 업그레이드하거나 교체하지 않는다. 기존 resolver가 받는 네 필드만 계산 입력으로 전달하고 원본 `depends`를 포함한 inventory는 그대로 보존했다. 이 계산은 기존 패키지 교체와 그 역의존성 검증까지 수행하지 않는다.

다음 다섯 제약이 남아 전체 transaction은 `unresolved`, `ready_to_fetch=false`다. 이 계산으로 archive를 다운로드하거나 패키지를 설치하지 않았다. [차단 요인과 설치된 역의존성](../../build/diagnostics/termux-omarchy-additions-post-ime-20261009-01/blockers.json)에 실제 버전과 의존 관계를 보존했다.

| 남은 제약 | 기존 설치와 영향 |
| --- | --- |
| `gst-plugins-bad-libs=1.28.7-2` | 기존 `1.28.6-3`; `sushi → gst-plugin-gtk`에서 요구 |
| `gst-plugins-base-libs=1.28.7-2` | 기존 `1.28.6-3`; Sushi와 `kdenlive → frei0r-plugins → opencv → gst-plugins-base`에서 요구 |
| `gstreamer=1.28.7-2` | 기존 `1.28.6-3`; 같은 GStreamer plugin 경로에서 요구 |
| `gvfs=1.60.3` | 기존 `1.60.2-4`; `gvfs-mtp`, `gvfs-nfs`, `gvfs-smb`에서 요구 |
| `ttf-jetbrains-mono-nerd-basic` 충돌 | 신규 basic `3.5.1-1`과 기존 full `ttf-jetbrains-mono-nerd 3.5.1-2`가 충돌 |

작은 후속 후보로 `lazygit`, `lua51`, `luarocks`, `tree-sitter-cli`의 [참고 transaction](../../build/diagnostics/termux-omarchy-additions-post-ime-20261009-01/nvim-tools-reference.json)도 계산했다. 의존성을 포함한 7개 패키지, 다운로드 8,042,272 bytes·설치 33,624,710 bytes로 해소된다. 이는 설치 계획 참고이며 서명·실제 설치·개인 Neovim plugin/LSP 적용 완료를 뜻하지 않는다.

한글 입력 설치 전의 [실제 `pacman -T` 감사](../../build/diagnostics/termux-omarchy-full-package-audit-device-20261009-01/receipt.json)는 설치 585개, 요청 49개 충족·109개 미충족을 기록했다. 이후 [서명된 Fcitx·Hangul 7개 설치](../../build/diagnostics/termux-omarchy-korean-input-install-device-20261009-02/receipt.json)로 원본 요청 중 `fcitx5`, `fcitx5-gtk`, `fcitx5-qt` 3개가 추가 충족됐다. 과거 [341개 추가 transaction](../../build/diagnostics/termux-omarchy-additions-current-20261009-01/transaction.json)과 [호스트 회귀 30개](../../build/diagnostics/termux-omarchy-additions-green-20261009-01/receipt.json)는 당시 증거로 보존하며 최신 수치와 구분한다.

| 원본 요청 | 당시 592개 기준 ALPM 요청 충족 |
| --- | --- |
| `aether` | 미충족 |
| `alsa-utils` | 충족 |
| `asdcontrol` | 미충족 |
| `avahi` | 충족 |
| `base-devel` | 미충족 |
| `bash-completion` | 충족 |
| `bat` | 충족 |
| `bluez` | 미충족 |
| `bluez-tools` | 미충족 |
| `bluez-utils` | 미충족 |
| `bolt` | 미충족 |
| `brightnessctl` | 미충족 |
| `btop` | 충족 |
| `chromium` | 충족 |
| `clang` | 미충족 |
| `cliamp` | 미충족 |
| `cups` | 미충족 |
| `cups-filters` | 미충족 |
| `cups-pk-helper` | 미충족 |
| `ddcutil` | 미충족 |
| `docker` | 미충족 |
| `docker-buildx` | 미충족 |
| `docker-compose` | 미충족 |
| `dosfstools` | 미충족 |
| `dotnet-runtime` | 미충족 |
| `dua-cli` | 미충족 |
| `evince` | 충족 |
| `exfatprogs` | 미충족 |
| `expac` | 미충족 |
| `eza` | 충족 |
| `fakeroot` | 미충족 |
| `fastfetch` | 충족 |
| `fcitx5` | 충족 |
| `fcitx5-gtk` | 충족 |
| `fcitx5-qt` | 충족 |
| `fd` | 충족 |
| `ffmpeg` | 충족 |
| `ffmpegthumbnailer` | 충족 |
| `fontconfig` | 충족 |
| `foot` | 충족 |
| `fzf` | 충족 |
| `git` | 충족 |
| `gnome-keyring` | 미충족 |
| `gnome-themes-extra` | 미충족 |
| `grim` | 충족 |
| `gpu-screen-recorder` | 미충족 |
| `gum` | 미충족 |
| `gvfs-mtp` | 미충족 |
| `gvfs-nfs` | 미충족 |
| `gvfs-smb` | 미충족 |
| `herdr` | 미충족 |
| `hype` | 미충족 |
| `hyprland` | 충족 |
| `hyprland-guiutils` | 충족 |
| `hyprland-preview-share-picker` | 미충족 |
| `hyprpicker` | 미충족 |
| `hyprsunset` | 미충족 |
| `imagemagick` | 충족 |
| `imv` | 충족 |
| `inetutils` | 미충족 |
| `inotify-tools` | 미충족 |
| `inxi` | 미충족 |
| `networkmanager` | 미충족 |
| `jq` | 충족 |
| `kdenlive` | 미충족 |
| `kernel-modules-hook` | 미충족 |
| `lazygit` | 미충족 |
| `less` | 충족 |
| `libsecret` | 충족 |
| `libvips` | 충족 |
| `libyaml` | 미충족 |
| `libreoffice-fresh` | 미충족 |
| `llvm` | 미충족 |
| `localsend` | 미충족 |
| `lua51` | 미충족 |
| `luarocks` | 미충족 |
| `man-db` | 미충족 |
| `mariadb-libs` | 미충족 |
| `mise-bin` | 미충족 |
| `monologue` | 미충족 |
| `moonlight-qt` | 미충족 |
| `mpv` | 충족 |
| `mpv-mpris` | 미충족 |
| `nautilus` | 충족 |
| `nautilus-python` | 미충족 |
| `gnome-disk-utility` | 미충족 |
| `noto-fonts` | 충족 |
| `noto-fonts-cjk` | 충족 |
| `noto-fonts-emoji` | 충족 |
| `nss-mdns` | 미충족 |
| `nvim` | 충족 |
| `obs-studio` | 미충족 |
| `obsidian` | 미충족 |
| `omacalc` | 미충족 |
| `omacut` | 미충족 |
| `omawrite` | 미충족 |
| `omarchy-nvim` | 미충족 |
| `omasnap` | 미충족 |
| `owe` | 미충족 |
| `owe-lockfeed` | 미충족 |
| `pacman-contrib` | 미충족 |
| `pamixer` | 충족 |
| `pinta` | 미충족 |
| `plocate` | 미충족 |
| `plymouth` | 미충족 |
| `postgresql-libs` | 미충족 |
| `power-profiles-daemon` | 미충족 |
| `python-gobject` | 미충족 |
| `python-poetry-core` | 미충족 |
| `qt6-base` | 충족 |
| `qt6-declarative` | 충족 |
| `qt6-multimedia` | 충족 |
| `qt6-svg` | 충족 |
| `qt6-wayland` | 충족 |
| `ttfx` | 미충족 |
| `qemu-user-static-binfmt` | 미충족 |
| `qrencode` | 미충족 |
| `qt6-imageformats` | 충족 |
| `quickshell` | 충족 |
| `ripgrep` | 충족 |
| `ruby` | 미충족 |
| `sddm` | 미충족 |
| `slurp` | 충족 |
| `socat` | 충족 |
| `starship` | 미충족 |
| `sushi` | 미충족 |
| `system-config-printer` | 미충족 |
| `tesseract` | 미충족 |
| `tesseract-data-eng` | 미충족 |
| `tldr` | 미충족 |
| `tree-sitter-cli` | 미충족 |
| `tmux` | 충족 |
| `tobi-try` | 미충족 |
| `ttf-ia-writer` | 미충족 |
| `ttf-jetbrains-mono-nerd-basic` | 미충족 |
| `tzupdate` | 미충족 |
| `udiskie` | 미충족 |
| `ufw` | 미충족 |
| `ufw-docker` | 미충족 |
| `unzip` | 미충족 |
| `usage` | 미충족 |
| `uwsm` | 미충족 |
| `vi` | 미충족 |
| `whois` | 미충족 |
| `wireless-regdb` | 미충족 |
| `wireplumber` | 충족 |
| `wl-clipboard` | 충족 |
| `wtype` | 충족 |
| `woff2-font-awesome` | 충족 |
| `xdg-desktop-portal-gtk` | 충족 |
| `xdg-desktop-portal-hyprland` | 미충족 |
| `xdg-terminal-exec` | 미충족 |
| `xournalpp` | 미충족 |
| `yaru-icon-theme` | 미충족 |
| `yay` | 미충족 |
| `yt-dlp` | 미충족 |
| `zbar` | 미충족 |
| `zoxide` | 충족 |
