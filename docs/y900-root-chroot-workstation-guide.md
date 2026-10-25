# Lenovo Legion Y900 (13" Gen 4 / 8 Elite) Native Linux Workstation Guide

> **Target Architecture:** Rooted Android (`KernelSU` / `Magisk`) + Native `Chroot` (Arch Linux ARM64) + `Termux:X11` (SurfaceFlinger Direct) + `mesa KGSL/Turnip 직결` (Adreno 830 GPU Acceleration) + `i3wm`/`picom` (Omarchy Style) + `xremap` (macOS Keybindings & CapsLock Layer)

이 문서는 원본 가이드를 검토·보강한 버전입니다. 원문 대비 바뀐 점은 [§9 요약](#9-원문-대비-개선-사항)에 정리했습니다.

---

## 1. 아키텍처 개요: 왜 Root + Chroot인가?

| 구분 | Non-Root (`proot-distro`) | **Root (`Native Chroot` - 본 가이드)** |
| :--- | :--- | :--- |
| **시스템 콜 & 파일 I/O** | `ptrace` 번역 오버헤드로 `node_modules` / 컴파일 시 속도 반토막 | **네이티브 커널 직접 공유 (오버헤드 0%, UFS 4.0 속도 100% 활용)** |
| **키보드 리매핑** | `/dev/uinput` 접근 불가로 `xmodmap` 등 구형 X11 도구에 의존 | **커널 레벨 `uinput` 접근 가능 → `xremap` / `keyd` 완벽 구동** |
| **프로세스 제약** | Android Phantom Process Killer에 수시로 강제 종료됨 | 부팅 스크립트(`service.d`)로 안드로이드 제약 영구 무력화 |
| **그래픽 & 주사율** | 소프트웨어 렌더링 시 끊김 | **Adreno 830 직결 (KGSL mesa/Turnip) + `picom` GLX 백엔드로 144Hz 애니메이션** |

> **그래픽 파이프라인 한 줄 요약:** Chroot 앱의 OpenGL → chroot 안의 KGSL mesa(freedreno GL/turnip Vulkan) → `/dev/kgsl-3d0` → Adreno 830. GPU 변환 브로커(VirGL 서버)가 **없는 직결 경로**이며, X 서버는 Chroot 안에서 따로 띄우는 것이 아니라 **안드로이드 쪽 Termux:X11 하나를 `DISPLAY=:0`으로 공유**합니다.
>
> **왜 VirGL이 아닌가:** VirGL은 게스트의 GL 명령을 스트림으로 변환해 호스트가 다시 그리는 방식이라 명령 변환 오버헤드가 상시 붙고, 데스크톱 합성(picom GLX 백엔드)에서 병목이 됩니다. Adreno 직결 KGSL은 이 프로젝트(Termux Omarchy)의 실측 문서(`docs/research/2026-10-19-y900-graphics-acceleration-next.md`)와 [mesa-for-android-container](https://github.com/lfdevs/mesa-for-android-container)(mesa 26.x 기준 Adreno 810/830/840 공식 지원)가 공통으로 쓰는 표준 경로입니다. VirGL은 §8.5의 폴백으로만 남깁니다.

---

## 2. Android 호스트 사전 작업 (제약 해제 및 필수 앱)

### 2.1 필수 안드로이드 앱 설치
1. **Termux** 및 **Termux:X11** (GitHub Releases 최신 Nightly 권장)
2. 안드로이드 설정 → 앱 → `Termux`, `Termux:X11`, `Tailscale` → 배터리 → **제한 없음(Unrestricted)** 설정
3. (권장) 안드로이드 설정 → 배터리 절전 중에도 Wi-Fi 유지. 개발자 옵션에서 **"절전 모드 시 Wi-Fi 유지"** 관련 항목이 있다면 ON

### 2.2 `Termux:X11` 앱 Preferences 필수 세팅
* **Output:**
  * `Fullscreen`: **ON**
  * `Hide cutout`: **ON**
  * `Display resolution mode`: **`custom`** (3200x2000이 너무 작다면 `1920x1200` 또는 `2240x1400`으로 지정 시 픽셀 매칭과 가독성 최적)
  * `Reseed screen While Soft Keyboard is open`: **OFF**
* **Mouse:**
  * `Touchpad emulation mode`: **`Direct`** (물리 마우스/트랙패드 1:1 반응)
  * `Capture pointer on click`: **ON** (안드로이드 우클릭 '뒤로가기' 방지 및 144Hz 네이티브 커서 활성화)
* **Keyboard:**
  * `Capture external keyboard`: **ON** (`Cmd`, `Alt+Tab`, `CapsLock` 등 모든 키를 안드로이드가 가로채지 못하게 차단)
  * `Show additional keyboard bar`: **OFF**

### 2.3 Root 권한으로 안드로이드 프로세스 킬러 및 네트워크 스로틀링 해제
Termux에서 `su`를 입력해 루트 셸을 열고 아래 명령어를 실행합니다. 재부팅 후에도 유지되도록 Magisk/KernelSU의 `service.d` 스크립트(§7 끝의 템플릿)로 등록하는 것을 권장합니다.

```bash
su -c '
  # 1. Phantom Process Killer 완전 무력화
  #    (A12L 이상. set_sync_disabled_for_tests는 Google 서버의 동기화도 차단)
  /system/bin/device_config set_sync_disabled_for_tests persistent
  /system/bin/device_config put activity_manager max_phantom_processes 2147483647
  settings put global settings_enable_monitor_phantom_procs false

  # 2. Wi-Fi 절전 및 백그라운드 패킷 드랍 방지 (SSH/Mosh 끊김 해결)
  #    (wifi_sleep_policy는 신형 Android에서 무시될 수 있으나 해롭지 않음)
  settings put global wifi_scan_throttle_enabled 0
  settings put global wifi_sleep_policy 2
  cmd wifi set-wifi-saver-enabled false

  # 3. Termux 백그라운드 확정 (배터리 "제한 없음"과 이중 방어)
  am set-standby-bucket com.termux active
  am set-standby-bucket com.termux.x11 active
'
```

> 검증 방법: 재부팅 후 `su -c "device_config get activity_manager/max_phantom_processes"`가 `2147483647`이면 성공. `settings_enable_monitor_phantom_procs`는 `device_config` 동기화로 원복될 수 있으니 service.d 등록이 사실상 필수입니다.

---

## 3. 호스트 Termux 그래픽/오디오 브릿지 구축

루트 환경이라도 화면 출력(`SurfaceFlinger`)과 오디오(`AAudio`)는 안드로이드 호스트의 Termux 데몬을 브릿지로 띄워 공유받는 것이 가장 빠르고 안정적입니다. **GPU 드라이버는 호스트 Termux에 설치하지 않습니다** — Chroot 안의 앱이 자체 KGSL mesa를 통해 `/dev/kgsl-3d0`으로 직접 렌더링하므로 VirGL 서버·ANGLE 브리지가 필요 없습니다.

```bash
# 일반 Termux 세션(Non-root)에서 실행
pkg update && pkg upgrade -y
pkg install x11-repo -y
pkg install termux-x11-nightly pulseaudio wget tar -y
```

> 루트 셸(`su`)이 이미 있으므로 `tsu`는 불필요합니다. Termux 자체 GUI 앱을 쓸 일이 생기면 그때 TUR의 `mesa-kgsl` 계열을 별도로 설치하면 되고, 이 가이드의 Chroot 경로와는 무관합니다.

---

## 4. Arch Linux ARM64 Chroot 구축

`/data/local/arch` 경로에 실제 Arch Linux ARM64 루트 파일시스템을 풀고 구성합니다.

### 4.1 Rootfs 다운로드 및 압축 해제
```bash
su
mkdir -p /data/local/arch
cd /data/local/arch

# Arch Linux ARM64 공식 최신 Rootfs 다운로드 및 압축 해제
wget http://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz
tar -xpf ArchLinuxARM-aarch64-latest.tar.gz --numeric-owner
rm ArchLinuxARM-aarch64-latest.tar.gz
```

### 4.2 Chroot 초기 진입 및 기본 시스템 세팅
```bash
# 필수 커널 파일시스템 마운트
mount -o remount,dev,suid /data
mount --bind /dev /data/local/arch/dev
mount --bind /dev/pts /data/local/arch/dev/pts
mount --bind /proc /data/local/arch/proc
mount --bind /sys /data/local/arch/sys

# Chromium 등이 요구하는 POSIX 공유메모리 (누락 시 브라우저 크래시)
mkdir -p /data/local/arch/dev/shm
mount -t tmpfs -o size=2g,mode=1777 tmpfs /data/local/arch/dev/shm

# Chroot 진입
chroot /data/local/arch /bin/bash

# --- 이하 Chroot (Arch Linux) 내부에서 실행 ---
# 1. DNS 및 안드로이드 네트워크 그룹(aid_inet) 권한 등록
rm -f /etc/resolv.conf
printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\n' > /etc/resolv.conf
groupadd -g 3003 aid_inet
groupadd -g 3004 aid_net_raw
groupadd -g 1077 aid_everybody

# 2. 로캘 생성 (한글 입력기/폰트/앱 다국어의 기반 — 누락하기 쉬운 필수 항목)
sed -i 's/^#en_US\.UTF-8/en_US.UTF-8/; s/^#ko_KR\.UTF-8/ko_KR.UTF-8/' /etc/locale.gen
locale-gen
echo 'LANG=ko_KR.UTF-8' > /etc/locale.conf
echo 'omarchy' > /etc/hostname

# 3. Pacman 키링 초기화 및 전체 업데이트
pacman-key --init
pacman-key --populate archlinuxarm

# Chroot 환경에서는 파일시스템 마운트 체크 시 에러가 날 수 있으므로 pacman.conf에서 CheckSpace 비활성화
sed -i 's/^CheckSpace/#CheckSpace/g' /etc/pacman.conf
pacman -Syu --noconfirm

# 4. 일반 사용자 생성 (예: loopy) 및 sudo/네트워크/입력장치 권한 부여
pacman -S --noconfirm --needed sudo base-devel git vim unzip
useradd -m -G wheel,aid_inet,aid_net_raw,input,video -s /bin/bash loopy
passwd loopy
echo "%wheel ALL=(ALL:ALL) NOPASSWD: ALL" > /etc/sudoers.d/wheel
```

> `input` 그룹은 gid 충돌로 생성에 실패할 수 있습니다(이미 존재하면 무시). 개인 기기라서 `NOPASSWD: ALL`을 쓰지만, 루트화된 안드로이드 자체가 신뢰 경계이므로 Chroot 보안은 안드로이드 보안과 동일선입니다.

---

## 5. Omarchy 데스크톱 환경 & GPU 가속 패키지 설치

Chroot 내부에서 Omarchy 스타일 구성요소(`i3wm`, `picom`, `rofi`, `alacritty`, `polybar`)와 한글 입력기(`fcitx5`), 키매퍼(`xremap`)를 설치합니다.

```bash
# Arch Chroot 내부에서 실행

# 0) GPU 스택: KGSL 직결 mesa (§1 경로). 스톡 Arch mesa는 freedreno-kgsl 백엔드가
#    빌드에 빠져 있어 Adreno 직결이 안 됩니다. 반드시 컨테이너용 mesa로 교체합니다.
#    [mesa-for-android-container](https://github.com/lfdevs/mesa-for-android-container)의
#    Releases에서 Arch ARM64용 GL(freedreno)·Vulkan(turnip) 패키지를 받아
#    릴리스 노트의 파일명 그대로 설치합니다. Mesa 26.x부터 Adreno 830을 지원합니다.
pacman -S --noconfirm --needed mesa-utils libglvnd vulkan-icd-loader
# pacman -U --noconfirm ./<릴리스의 mesa 패키지 파일들>.pkg.tar.zst
pacman -S --noconfirm --needed \
  xorg-xset xorg-xrdb xorg-setxkbmap xorg-xprop xorg-xrandr \
  i3-wm polybar rofi alacritty picom autotiling feh dunst \
  fcitx5-im fcitx5-hangul \
  noto-fonts noto-fonts-cjk noto-fonts-emoji ttf-jetbrains-mono-nerd \
  neovim btop ripgrep fd fzf lazygit nodejs pnpm tmux unzip \
  chromium firefox mosh openssh tailscale xclip xdotool
```

원문 대신 바뀐 점:
* **`mesa` 스톡 패키지 제거, 컨테이너용 KGSL mesa로 교체** — 원문의 `mesa`만으로는 llvmpipe(CPU 소프트웨어 렌더링)로 떨어져 "가속이 안 되는" 느린 환경이 됩니다. 세션 env는 §7의 `MESA_LOADER_DRIVER_OVERRIDE=kgsl`로 잡습니다.
* **`xorg-server`, `xorg-xinit` 제거** — X 서버는 안드로이드의 Termux:X11이 담당합니다. Chroot 안에서 X 서버를 또 설치/실행하면 안 됩니다(`DISPLAY=:0` 클라이언트로만 접속). `xset`/`xrdb` 등 클라이언트 도구만 남깁니다.
* **`fcitx5-im` 그룹**으로 fcitx5·configtool·gtk·qt를 한 번에 설치.
* **`tmux` 추가** — §8의 권장 워크플로우(`mosh … -- tmux a`)에 필요한데 원문에 빠져 있었습니다.
* **`xorg-xrdb`, `unzip` 추가** — DPI 설정(§6.5)과 xremap 압축 해제(아래)에 필요.
* `rustup`은 xremap을 직접 빌드할 때만 필요하므로 목록에서 제외(아래 방법 A 권장).

### `xremap` (X11 버전) 설치
Root 권한이 있으므로 `/dev/input`과 `/dev/uinput`을 직접 제어하는 `xremap`을 사용하면 **앱별 `Cmd` 단축키 분리**와 **`CapsLock` 복합 레이어**를 단일 설정 파일로 끝낼 수 있습니다.

```bash
# 방법 A (권장): 공식 prebuilt 바이너리 — 태블릿에서 cargo 빌드는 10분 이상 걸림
sudo wget -O /tmp/xremap.zip \
  https://github.com/xremap/xremap/releases/latest/download/xremap-x11-linux-aarch64.zip
sudo unzip -o /tmp/xremap.zip -d /tmp/xremap-bin
sudo install -m755 /tmp/xremap-bin/xremap /usr/local/bin/xremap
xremap --version

# 방법 B (대체): 직접 빌드. 에셋 이름이 바뀌었거나 aarch64 빌드가 없을 때
#   pacman -S rustup && rustup default stable
#   cargo install xremap --features x11
#   sudo cp ~/.cargo/bin/xremap /usr/local/bin/
```

> **picom 애니메이션 주의(§6.2 관련):** Arch 스톡 `picom`이 `animations` 옵션을 모르는 빌드라면 picom이 설정 파싱에 실패하며 **아예 실행되지 않습니다.** 부팅 후 `pgrep picom`으로 살아있는지 확인하고, 죽어 있다면 §6.2의 `animations` 블록을 주석 처리(애니메이션만 포기)하거나 애니메이션 엔진이 포함된 빌드(picom ≥ v12 또는 `picom-animations` 계열)로 교체하세요.

---

## 6. 핵심 설정 파일 (macOS 단축키 + CapsLock 레이어 + Hyprland 애니메이션)

이하 모든 설정 파일은 Chroot 내부의 일반 사용자(`loopy`) 홈 디렉터리 기준입니다.

### 6.1 `~/.config/xremap/config.yml` (핵심: 키보드 완벽 제어)
* **물리 키 스왑:** 스페이스바 옆 왼쪽 `Alt`를 맥의 `Super(Cmd)`로, `Win(Super)` 키를 `Alt(Option)`로 맞바꿉니다.
* **`CapsLock` 동작:**
  * **단독 클릭 (`alone`):** 한/영 전환 (`Hangul` 키 발생)
  * **누르고 있기 (`held`) + `H/J/K/L`:** 방향키 (`Left/Down/Up/Right`)
  * **누르고 있기 (`held`) + `D/F`:** 창/워크스페이스 전환용 트리거 (`F13` / `F14`)
* **macOS `Cmd` 단축키 분리:**
  * 브라우저/일반 앱에서는 `Cmd + C/V/X/A/Z/T/W/R/L/F`가 `Ctrl + ...`로 자동 변환됩니다.
  * **터미널(`Alacritty`)에서는** `Cmd + C/V`만 클립보드 복사(`Ctrl+Shift+C/V`)로 변환되고, 실제 `Ctrl + C`는 프로세스 종료(`SIGINT`)로 온전히 보존됩니다.
* xremap은 keymap 매칭에 사용된 수정자(Ctrl_R 등)를 출력에서 제외하므로 `CapsLock+H`는 순수 `Left`로 나갑니다. 단, 물리 오른쪽 `Ctrl + h`도 같은 레이어로 작동합니다(부작용이지만 실용적으로는 장점).

```yaml
# ~/.config/xremap/config.yml
modmap:
  - name: Mac Modifier Swap & Multi-purpose CapsLock
    remap:
      # 1. 스페이스바 왼쪽 Alt를 Cmd(Super_L)로, Win 키를 Alt_L로 스왑 (이미 맥 배열 키보드라면 아래 두 줄 주석 처리)
      Alt_L: Super_L
      Super_L: Alt_L

      # 2. CapsLock: 단독 클릭 시 한/영 전환(Hangul), 누르고 있을 때는 가상 Modifier(Ctrl_R)로 작동
      CapsLock:
        held: Ctrl_R
        alone: Hangul
        alone_timeout_millis: 200

keymap:
  # === A. CapsLock (held: Ctrl_R) 네비게이션 레이어 (전역 작동) ===
  - name: CapsLock Navigation Layer (HJKL & D/F)
    remap:
      # CapsLock + HJKL -> 방향키
      Ctrl_R-h: Left
      Ctrl_R-j: Down
      Ctrl_R-k: Up
      Ctrl_R-l: Right
      # CapsLock + Shift + HJKL -> 텍스트 블록 선택 + 방향키
      Ctrl_R-Shift-h: Shift-Left
      Ctrl_R-Shift-j: Shift-Down
      Ctrl_R-Shift-k: Shift-Up
      Ctrl_R-Shift-l: Shift-Right
      # CapsLock + D / F -> i3wm 창/워크스페이스 전환 트리거 (F13, F14)
      Ctrl_R-d: F13
      Ctrl_R-f: F14
      # CapsLock + U / I -> Home / End
      Ctrl_R-u: Home
      Ctrl_R-i: End
      # CapsLock + Backspace -> Delete
      Ctrl_R-BackSpace: Delete

  # === B. 터미널(Alacritty) 전용 macOS Cmd 단축키 ===
  - name: macOS Shortcuts for Terminal
    application:
      only: [Alacritty, kitty]
    remap:
      Super_L-c: C-Shift-c
      Super_L-v: C-Shift-v
      Super_L-t: C-Shift-t
      Super_L-f: C-Shift-f

  # === C. 일반 GUI 앱 / 브라우저 전용 macOS Cmd 단축키 ===
  - name: macOS Shortcuts for GUI & Browsers
    application:
      not: [Alacritty, kitty]
    remap:
      Super_L-c: C-c
      Super_L-v: C-v
      Super_L-x: C-x
      Super_L-a: C-a
      Super_L-z: C-z
      Super_L-Shift-z: C-Shift-z
      Super_L-s: C-s
      Super_L-f: C-f
      Super_L-t: C-t
      Super_L-w: C-w
      Super_L-r: C-r
      Super_L-l: C-l
      Super_L-n: C-n
      Super_L-Shift-t: C-Shift-t
      # 맥 스타일 브라우저 뒤로/앞으로 가기 (Cmd + [ / ])
      Super_L-LeftBrace: Alt-Left
      Super_L-RightBrace: Alt-Right
```

> **`Cmd + Space`(Rofi)와 입력기 트리거 충돌 방지:** fcitx5 기본 트리거를 그대로 두면 `Super+Space`가 Rofi와 겹칩니다. §6.4의 fcitx5 설정으로 트리거를 `Hangul` 키(CapsLock 탭) 하나로 고정하세요.

### 6.2 `~/.config/picom/picom.conf` (Hyprland 스타일 144Hz 슬라이딩 애니메이션)
Adreno 830 직결(KGSL, §1) 하드웨어 가속 위에서 창이 열리고 분할될 때 쫀득하게 미끄러지는 애니메이션과 둥근 모서리를 담당합니다.

```ini
# ~/.config/picom/picom.conf
backend = "glx";
vsync = true;
glx-no-stencil = true;
glx-no-rebind-pixmap = true;

# 렌더 아티팩트 방지용으로 데미지 트래킹을 끕니다(VirGL 폴백 경로에서 특히 유용).
# 배터리/발열이 걱정되면 true로 되돌리세요(애니메이션은 약간 덜 부드러워짐).
use-damage = false;

# Omarchy / Hyprland 감성 둥근 모서리
detect-rounded-corners = true;
corner-radius = 12;
round-borders = 1;

shadow = true;
shadow-radius = 16;
shadow-opacity = 0.35;
shadow-offset-x = -12;
shadow-offset-y = -12;

# 전체화면 창에 그림자 남는 것 방지
shadow-exclude = [
  "name = 'picom'",
  "_NET_WM_STATE@:32a *= '_NET_WM_STATE_FULLSCREEN'"
];

# picom 애니메이션 엔진 (창 생성/종료/타일링 이동 시 슬라이딩 효과)
# ※ 스톡 picom이 이 옵션을 모르면 실행 자체가 실패합니다 → §5 경고 참고
animations = (
  {
    triggers = ["open", "show"];
    preset = "appear";
    duration = 0.16;
    scale = 0.92;
  },
  {
    triggers = ["close", "hide"];
    preset = "disappear";
    duration = 0.14;
    scale = 0.92;
  },
  {
    triggers = ["geometry"];
    preset = "geometry-change";
    duration = 0.20;
  }
)
```

### 6.3 `~/.config/i3/config` (Omarchy 스타일 타일링 + `CapsLock+D/F` 연결)
창 제목 표시줄을 완전히 없애고 TokyoNight 컬러 테마와 자동 나선형 분할(`autotiling`)을 적용합니다.

```i3config
# ~/.config/i3/config
set $mod Mod4
font pango:JetBrainsMono Nerd Font 11

# 창 타이틀바 제거 및 여백(Gaps) 설정 (gaps는 i3 ≥ 4.22 기본 지원)
default_border pixel 2
default_floating_border pixel 2
gaps inner 8
gaps outer 4

# TokyoNight 컬러 스킴 (Omarchy 기본 테마)
# class                 border  backgr. text    indicator child_border
client.focused          #7aa2f7 #1a1b26 #c0caf5 #7dcfff   #7aa2f7
client.focused_inactive #3b4261 #1a1b26 #565f89 #3b4261   #3b4261
client.unfocused        #24283b #1a1b26 #565f89 #24283b   #3b4261
client.urgent           #f7768e #1a1b26 #f7768e #f7768e   #f7768e

# === CapsLock + D / F (xremap이 보낸 F13 / F14) 창 전환 바인딩 ===
# 1. 같은 워크스페이스 내 이전/다음 창 포커스 순환 (focus next|prev는 i3 ≥ 4.19)
bindsym F13 focus prev
bindsym F14 focus next

# (만약 워크스페이스 자체를 좌우로 넘기고 싶다면 위 두 줄 대신 아래 사용)
# bindsym F13 workspace prev
# bindsym F14 workspace next

# === macOS & Omarchy 핵심 단축키 ===
# Cmd + Space : Rofi 앱 런처 (Spotlight/Raycast 대용)
bindsym $mod+space exec --no-startup-id rofi -show drun

# Cmd + Return : 터미널 실행
bindsym $mod+Return exec alacritty

# Cmd + Tab : 직전 워크스페이스 왕복 (macOS 앱 전환 감성)
bindsym $mod+Tab workspace back_and_forth

# Cmd + Q : 현재 창 닫기 (macOS 스타일)
bindsym $mod+q kill

# Cmd + F : 전체화면 토글
bindsym $mod+f fullscreen toggle

# Cmd + Shift + F : 플로팅 창 전환
bindsym $mod+Shift+f floating toggle

# Cmd + HJKL : 창 포커스 직접 이동
bindsym $mod+h focus left
bindsym $mod+j focus down
bindsym $mod+k focus up
bindsym $mod+l focus right

# Cmd + Shift + HJKL : 창 위치 맞바꾸기
bindsym $mod+Shift+h move left
bindsym $mod+Shift+j move down
bindsym $mod+Shift+k move up
bindsym $mod+Shift+l move right

# Cmd + 1~6 : 워크스페이스 즉시 이동
bindsym $mod+1 workspace number 1
bindsym $mod+2 workspace number 2
bindsym $mod+3 workspace number 3
bindsym $mod+4 workspace number 4
bindsym $mod+5 workspace number 5
bindsym $mod+6 workspace number 6

# Cmd + Shift + 1~6 : 현재 창을 해당 워크스페이스로 보내기
bindsym $mod+Shift+1 move container to workspace number 1
bindsym $mod+Shift+2 move container to workspace number 2
bindsym $mod+Shift+3 move container to workspace number 3
bindsym $mod+Shift+4 move container to workspace number 4
bindsym $mod+Shift+5 move container to workspace number 5
bindsym $mod+Shift+6 move container to workspace number 6

# === 시작 시 자동 실행 데몬 ===
# 1. 화면 DPI (§6.5의 ~/.Xresources — 3K/커스텀 해상도에서 글자 크기의 기준)
exec_always --no-startup-id xrdb -merge ~/.Xresources
# 2. Hyprland 스타일 자동 분할
exec_always --no-startup-id autotiling
# 3. GPU 가속 애니메이션 합성기
exec_always --no-startup-id picom --config ~/.config/picom/picom.conf -b
# 4. 상태바 (원문에는 설치만 있고 실행이 없어 화면에 바가 안 떴음)
exec_always --no-startup-id "killall -q polybar; polybar --reload main"
# 5. (선택) 배경화면 — 파일을 준비한 뒤 주석 해제
# exec --no-startup-id feh --bg-fill ~/Pictures/wallpaper.png
# 6. 한글 입력기
exec --no-startup-id fcitx5 -d
# 7. 키보드 고속 반복률(200ms 딜레이, 40Hz), 마우스 가속·화면 절전(DPMS) 해제
exec_always --no-startup-id xset r rate 200 40
exec_always --no-startup-id xset m 0 0
exec_always --no-startup-id xset s off -dpms
```

### 6.4 fcitx5 트리거 고정 (`~/.config/fcitx5/config`)
CapsLock 단독 클릭이 발생시키는 `Hangul` 키를 한/영 전환 트리거로 등록합니다. GUI(`fcitx5-configtool` → Global Options → Trigger Input Method)로 해도 되지만, 설정 파일로 넣으면 재설치 후에도 유지됩니다.

```ini
# ~/.config/fcitx5/config
[GlobalOptions]
TriggerKeys=Hangul
```

> 기존 기본 트리거(`Ctrl+Space`)도 유지하고 싶으면 `fcitx5-configtool`에서 병행 등록하세요. `Super+Space`는 Rofi에 맡겼으므로 등록하지 않는 것을 권장합니다.

### 6.5 글자 크기와 터미널 폰트
13" 3K 패널(또는 커스텀 해상도)에서 앱 글자가 너무 작아지는 것을 DPI로 잡습니다.

```xdefaults
# ~/.Xresources  — 2240x1400 커스텀 해상도 기준. 작으면 168, 크면 120
Xft.dpi: 144
Xft.antialias: true
Xft.hinting: true
Xft.rgba: rgb
```

```toml
# ~/.config/alacritty/alacritty.toml
[font]
size = 11.0

[font.normal]
family = "JetBrainsMono Nerd Font"

[window]
padding = { x = 6, y = 6 }
opacity = 0.96
```

### 6.6 최소 polybar 설정 (`~/.config/polybar/config.ini`)
§6.3에서 `polybar main`을 실행하므로 설정이 필요합니다. TokyoNight 배색의 미니멀 바입니다.

```ini
# ~/.config/polybar/config.ini
[bar/main]
width = 100%
height = 30
radius = 0
background = #1a1b26
foreground = #c0caf5
padding-left = 1
padding-right = 1
module-margin = 1
font-0 = JetBrainsMono Nerd Font:size=10;2
modules-left = i3
modules-center = xwindow
modules-right = battery date
wm-restack = i3
enable-scroll = false

[module/i3]
type = internal/xworkspaces
label-active = %name%
label-active-foreground = #7aa2f7
label-occupied = %name%
label-occupied-foreground = #565f89
label-urgent = %name%
label-urgent-foreground = #f7768e
label-empty = %name%
label-empty-foreground = #3b4261

[module/xwindow]
type = internal/xwindow
label = %title:0:60:...%

[module/battery]
type = internal/battery
; 실기기에서 ls /sys/class/power_supply 로 이름 확인 후 수정 (예: BTPSY0)
battery = BAT0
adapter = AC
full-at = 98
format-charging = <label-charging>
format-discharging = <label-discharging>
label-charging = ⚡ %percentage%%
label-discharging = %percentage%%

[module/date]
type = internal/date
date = %m-%d %H:%M
label = %date%

[settings]
screenchange-reload = true
```

---

## 7. 원클릭 통합 부팅 스크립트 (`~/boot-omarchy.sh`)

매번 마운트하고 환경변수를 넣을 필요 없이, 안드로이드 Termux에서 `./boot-omarchy.sh` 한 줄만 치면 **X11 + Chroot 마운트(Adreno 직결 포함) + `xremap` + `i3wm`**이 한 번에 켜지는 마스터 스크립트입니다. `./boot-omarchy.sh stop`으로 깔끔하게 내립니다.

원문 대비 바뀐 점: 고정 `sleep` 대신 **X 소켓 대기**, **`/dev/shm`·`/sdcard` 마운트**, **`/dev/kgsl-3d0`·`/dev/dma_heap` GPU 노드 바인드(VirGL 서버 폐지)**, **X 대기 실패 경고**, **stop 서브커맨드**, **로캘·XDG 환경변수**, **xremap 로그 파일**이 추가/교체됐습니다.

일반 Termux 홈 디렉터리(`~`)에 생성합니다.

```bash
cat << 'EOF' > ~/boot-omarchy.sh
#!/data/data/com.termux/files/usr/bin/bash
set -u

CHROOT_DIR="/data/local/arch"
TERMUX_TMP="$PREFIX/tmp"          # X11/Pulse 소켓이 모이는 공용 디렉터리 (Chroot /tmp에 바인드됨)

# ---------- stop 모드 ----------
if [ "${1:-}" = "stop" ]; then
  su -c "
    chroot $CHROOT_DIR /bin/killall -u loopy 2>/dev/null
    sleep 1
    for m in dev/dma_heap dev/kgsl-3d0 dev/shm sdcard tmp dev/pts dev proc sys; do
      mountpoint -q $CHROOT_DIR/\$m && umount $CHROOT_DIR/\$m
    done
  " 2>/dev/null
  killall -9 termux-x11 pulseaudio 2>/dev/null
  echo "Omarchy 세션 종료"
  exit 0
fi

# ---------- 1. 기존 호스트 데몬 초기화 ----------
killall -9 termux-x11 pulseaudio 2>/dev/null

# ---------- 2. PulseAudio 오디오 브릿지 (AAudio → TCP loopback) ----------
pulseaudio --start \
  --load="module-native-protocol-tcp auth-ip-acl=127.0.0.1 auth-anonymous=1" \
  --exit-idle-time=-1

# ---------- 3. GPU 서버는 없습니다 (Adreno 직결) ----------
# KGSL mesa가 chroot 안에서 /dev/kgsl-3d0을 직접 열므로 호스트 GPU 데몬이 필요 없다.

# ---------- 4. Termux:X11 서버 (고정 sleep 대신 X0 소켓 대기) ----------
termux-x11 :0 &
for i in $(seq 1 40); do
  [ -S "$TERMUX_TMP/.X11-unix/X0" ] && break
  sleep 0.25
done
[ -S "$TERMUX_TMP/.X11-unix/X0" ] || echo "[경고] X0 소켓 대기 시간 초과"

# ---------- 5. Termux:X11 앱 화면으로 전환 ----------
am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1

# ---------- 6. Chroot 마운트 + 데스크톱 세션 ----------
su -c "
  mount -o remount,dev,suid /data
  mountpoint -q $CHROOT_DIR/dev      || mount --bind /dev      $CHROOT_DIR/dev
  mountpoint -q $CHROOT_DIR/dev/pts  || mount --bind /dev/pts  $CHROOT_DIR/dev/pts
  mountpoint -q $CHROOT_DIR/proc     || mount --bind /proc     $CHROOT_DIR/proc
  mountpoint -q $CHROOT_DIR/sys      || mount --bind /sys      $CHROOT_DIR/sys
  # Adreno 830 직결: KGSL GPU 노드와 DMA-BUF 힙을 chroot에 노출
  mountpoint -q $CHROOT_DIR/dev/kgsl-3d0 || mount --bind /dev/kgsl-3d0 $CHROOT_DIR/dev/kgsl-3d0
  mountpoint -q $CHROOT_DIR/dev/dma_heap || mount --bind /dev/dma_heap $CHROOT_DIR/dev/dma_heap 2>/dev/null
  # Chromium 등이 요구하는 POSIX 공유메모리
  mountpoint -q $CHROOT_DIR/dev/shm  || mount -t tmpfs -o size=2g,mode=1777 tmpfs $CHROOT_DIR/dev/shm
  # X11/Pulse 소켓 공유: Termux tmp를 Chroot /tmp에 바인드
  mkdir -p $CHROOT_DIR/tmp
  chmod 1777 /data/data/com.termux/files/usr/tmp
  mountpoint -q $CHROOT_DIR/tmp      || mount --bind /data/data/com.termux/files/usr/tmp $CHROOT_DIR/tmp
  # (선택) Android 공유저장소 — ~/sdcard 로 파일 주고받기
  mkdir -p $CHROOT_DIR/sdcard
  mountpoint -q $CHROOT_DIR/sdcard   || mount --bind /sdcard $CHROOT_DIR/sdcard
  # (선택) Chroot 안에서 tailscaled를 직접 띄울 때만 필요 (§8.3 참고)
  # mkdir -p $CHROOT_DIR/dev/net
  # mount --bind /dev/net/tun $CHROOT_DIR/dev/net/tun 2>/dev/null

  # xremap이 /dev/input·uinput을 쓰도록 권한 개방
  chmod 666 /dev/uinput /dev/input/event* 2>/dev/null

  # Chroot 내부의 loopy 유저로 데스크톱 세션 실행
  chroot $CHROOT_DIR /bin/su - loopy -c '
    export DISPLAY=:0
    export XDG_RUNTIME_DIR=/tmp
    export LANG=ko_KR.UTF-8
    export PULSE_SERVER=127.0.0.1
    # Adreno 830 직결(§1): KGSL 백엔드 강제. 이 줄이 빠지면 llvmpipe(CPU)로 떨어진다.
    export MESA_LOADER_DRIVER_OVERRIDE=kgsl
    # 찢어짐(티어링)이 보이면 아래 주석 해제 (§8.4 발열·주사율 팁 참고)
    # export vblank_mode=3 MESA_VK_WSI_PRESENT_MODE=mailbox
    export GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx

    # xremap 백그라운드 실행 (macOS 단축키 & CapsLock 레이어) — 로그는 /tmp/xremap.log
    killall xremap 2>/dev/null
    /usr/local/bin/xremap ~/.config/xremap/config.yml --watch=device >/tmp/xremap.log 2>&1 &

    # i3wm 세션 시작
    dbus-launch --exit-with-session i3
  '
"
EOF

chmod +x ~/boot-omarchy.sh
```

### 7.1 재부팅 후 자동 적용 (Magisk/KernelSU `service.d`)
§2.3의 제약 해제를 재부팅 뒤에도 유지합니다. `/data/adb/service.d/unlock-android.sh`(mode 755)로 저장하세요.

```bash
#!/system/bin/sh
sleep 15
/system/bin/device_config set_sync_disabled_for_tests persistent
/system/bin/device_config put activity_manager max_phantom_processes 2147483647
settings put global settings_enable_monitor_phantom_procs false
settings put global wifi_scan_throttle_enabled 0
cmd wifi set-wifi-saver-enabled false
am set-standby-bucket com.termux active
am set-standby-bucket com.termux.x11 active
```

---

## 8. 외부 서버 연결 최적화 및 트러블슈팅 체크리스트

### 8.1 외부 워크스테이션/홈랩 접속 시 끊김 방지 (`~/.ssh/config`)
Chroot 내부에서 소켓 디렉터리를 먼저 만들고 설정을 넣어 둡니다.

```bash
mkdir -p ~/.ssh/sockets && chmod 700 ~/.ssh/sockets
```

```ssh-config
Host *
    ServerAliveInterval 10
    ServerAliveCountMax 3
    TCPKeepAlive yes
    IPQoS throughput
    ControlMaster auto
    ControlPath ~/.ssh/sockets/%r@%h-%p
    ControlPersist 600
```
* **권장 워크플로우:** 장시간 터미널 작업은 일반 `ssh` 대신 **`mosh user@server -- tmux a`** 조합을 사용하면 태블릿 화면을 덮었다가 몇 시간 뒤에 열어도 0.1초 만에 복구됩니다. (mosh는 UDP 60000–61000 포트가 서버에 열려 있어야 합니다.)

### 8.2 데스크톱 진입 직후 점검 명령어
터미널(`Cmd + Return`)을 열어 순서대로 확인합니다.

1. **GPU 하드웨어 가속 확인:**
   ```bash
   glxinfo -B | grep -E "OpenGL renderer|OpenGL version"
   # "OpenGL renderer string: Adreno (TM) 830" 이면 성공! llvmpipe가 뜨면 CPU 렌더링 중 (§8.3 1번)
   ```
   Vulkan은 `vulkaninfo --summary | grep -A2 GPU0`로 `Adreno (TM) 830`과 turnip 드라이버를 확인합니다.
2. **합성기·키매퍼·입력기 생존 확인:**
   ```bash
   pgrep -a picom; pgrep -a xremap; pgrep -a fcitx5
   pgrep picom || picom --config ~/.config/picom/picom.conf -b   # 애니메이션 미지원 빌드로 죽었을 수 있음 → §5 경고
   tail /tmp/xremap.log 2>/dev/null                              # xremap 에러 확인
   ```
3. **오디오 확인:**
   ```bash
   pactl info | grep -E "Server Name|Default Sink" && speaker-test -t sine -f 440 -l 1 2>/dev/null || paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null || echo "소리 확인은 미디어 파일로"
   ```
4. **Chromium / Firefox 자체 하드웨어 가속 켜기:**
   * Chromium 실행 시 플래그 추가: `chromium --ignore-gpu-blocklist --enable-gpu-rasterization --enable-zero-copy`
   * 시작에 실패하면 §8.3 3번(샌드박스)을 확인하세요.
5. **`CapsLock` 한/영 전환 확인:**
   * 안 되면 `cat /tmp/xremap.log`로 xremap 에러를 먼저 보고, `fcitx5-configtool` → `Global Options` → `Trigger Input Method`에 `Hangul`이 등록돼 있는지 확인합니다(§6.4).
6. **Tailscale:**
   * **Android Tailscale 앱**의 VPN은 UID 기반 라우팅이라 Chroot 프로세스가 그 경로를 못 탈 수 있습니다. Chroot 안에서 `tailscale`을 쓰려면 §7의 `/dev/net/tun` 마운트 주석을 해제한 뒤 `sudo tailscaled` + `sudo tailscale up`으로 Chroot 내부 데몬을 직접 띄우세요(앱과 동시에 같은 기기 중복 사용은 피할 것).

### 8.3 자주 나오는 실패와 처방

| 증상 | 원인 | 처방 |
| :--- | :--- | :--- |
| `glxinfo`가 **llvmpipe** | KGSL 직결 실패 | ① 세션에 `MESA_LOADER_DRIVER_OVERRIDE=kgsl`이 있는지(§7 6번) ② `/dev/kgsl-3d0` 바인드와 권한(§7 6번, `ls -l /dev/kgsl-3d0`은 루트에서 확인) ③ chroot mesa가 컨테이너용 빌드인지(스톡 Arch mesa는 kgsl 백엔드가 없음, §5 0번) 순서로 확인 |
| `mesa: ERROR ... kgsl` / `failed to open /dev/kgsl-3d0` | GPU 노드 미바인드·권한 | §7 6번의 `dev/kgsl-3d0` 바인드 확인. 그래도 실패하면 `su -c 'chmod 666 /dev/kgsl-3d0'`(재부팅 시 원복, service.d 등록 권장) |
| `glxinfo`가 **GLX 에러** | `DISPLAY` 또는 X 소켓 공유 실패 | `[ -S /tmp/.X11-unix/X0 ]` 확인, `DISPLAY=:0` 확인 |
| Chromium/VSCode 등이 **곧바로 죽음** | Android 커널이 user namespace 미지원으로 샌드박스 실패 | 임시로 `--no-sandbox`(보안 약화 주석 필기), 근본 해결은 커널 userns 활성화 여부 확인 |
| picom이 **실행 안 됨** | `animations` 미지원 빌드 | `animations` 블록 주석 처리 또는 애니메이션 지원 빌드로 교체(§5) |
| **한/영 전환 안 됨** | fcitx5 트리거 미등록 또는 xremap 사망 | §6.4 확인 + `tail /tmp/xremap.log` + `/dev/uinput` 권한(§7) 확인 |
| **소리 없음** | Pulse 브릿지 미기동 | 호스트에서 `pgrep pulseaudio`, Chroot에서 `PULSE_SERVER=127.0.0.1 pactl info` |
| **바(polybar)가 안 보임** | 설정 파일 없음 | §6.6 생성 확인, `polybar main` 직접 실행해 에러 메시지 확인 |
| **앱 글자가 너무 작음** | DPI 미적용 | `~/.Xresources`의 `Xft.dpi` 조정(§6.5), `xrdb -merge ~/.Xresources` 후 앱 재시작 |
| 파일 교환이 번거로움 | — | §7의 `/sdcard` 바인드로 Chroot `~/sdcard` ↔ Android 다운로드 폴더 공유 |

### 8.4 성능/발열 팁
* `use-damage = false`(§6.2)는 프레임 전체를 매번 전송하므로 발열이 부담되면 `true`로.
* 144Hz가 불안정하면 Termux:X11 앱과 안드로이드 디스플레이 주사율을 120Hz로 맞추는 쪽이 버팀이가 좋습니다.
* 대용량 컴파일은 `tmux` 세션으로 띄워 두면 화면이 꺼져도 작업이 살아 있습니다.

### 8.5 폴백: VirGL/ANGLE (직결이 불가할 때만)

KGSL 직결이 커널·SELinux 제약으로 불가할 때 쓰는 2차 경로입니다. 게스트 GL 명령을 스트림으로 바꿔 호스트가 다시 그리는 방식이라 **오버헤드가 상시 붙고 직결보다 느립니다.** 직결(§5 0번)이 가능하면 이 절은 건너뜁니다.

1. 호스트 Termux: `pkg install tur-repo -y && pkg install virglrenderer-android angle-android -y`
2. 부팅 스크립트(§7) 3번 자리에 서버 기동 복원:
   ```bash
   export XDG_RUNTIME_DIR="$TERMUX_TMP"; cd "$TERMUX_TMP" || exit 1
   virgl_test_server_android &   # 곧바로 죽으면 구버전 빌드 — 최신 TUR로 재설치
   ```
3. chroot 세션 env(§7 6번)를 `GALLIUM_DRIVER=virpipe`로 교체하고 `MESA_LOADER_DRIVER_OVERRIDE=kgsl` 줄은 주석 처리.
4. 확인: `glxinfo -B`의 renderer가 `virgl (Adreno (TM) 830)` — 괄호 안의 virgl 접두어는 **변환 브리지를 거쳤다는 뜻**이며 직결 경로의 `Adreno (TM) 830`과 다릅니다. llvmpipe가 뜨면 VirGL 서버·소켓부터 확인하세요.

---

## 9. 원문 대비 개선 사항

**치명적 문제 수정**
1. `xorg-server`/`xorg-xinit` 제거 — X 서버는 Termux:X11 하나만 존재해야 함(Chroot는 클라이언트).
2. polybar가 설치만 되고 실행되지 않아 상태바가 아예 안 뜨던 문제 — i3 설정에 실행 추가 + §6.6 최소 설정 제공.
3. `/dev/shm` 미마운트로 Chromium 계열 크래시 가능 — 초기 구성(§4.2)과 부팅 스크립트(§7)에 tmpfs 마운트 추가.
4. 로캘 미설정 — `ko_KR.UTF-8` 생성·적용(§4.2, §7). fcitx5/앱 다국어의 기반.
5. 스톡 picom이 `animations` 옵션을 모르면 **실행 자체가 실패**함 — 경고와 확인 명령·처방 추가(§5, §8.2, §8.3).
6. fcitx5 기본 트리거(`Super+Space` 등)와 Rofi `Cmd+Space` 충돌 소지 — `TriggerKeys=Hangul` 고정(§6.4).
7. `tmux` 미설치 — §8.1 권장 워크플로우에 필요해 패키지 추가.
8. SSH `ControlPath` 디렉터리(`~/.ssh/sockets`) 생성 누락 — 추가(§8.1).
9. Chromium 샌드박스 실패(Android 커널 userns 문제) 처방 추가(§8.3).

**견고성/편의**
10. 부팅 스크립트: 고정 `sleep 1.5` → X0 소켓 폴링, GPU 노드(`/dev/kgsl-3d0`·`/dev/dma_heap`) 바인드, X 대기 실패 경고, `/sdcard`·`/dev/net/tun` 옵션 마운트, `stop` 서브커맨드, xremap 로그 파일. (초안에 있던 VirGL 서버 기동 검사는 §8.5 폴백으로 이동)
11. 재부팅 유지용 `service.d` 스크립트 템플릿 추가(§7.1).
12. DPI(`Xft.dpi`), Alacritty 폰트, `xset s off -dpms`, `$mod+Tab` 워크스페이스 왕복 등 3K 태블릿 실사용 디테일 추가(§6.3, §6.5).
13. xremap을 cargo 빌드 대신 공식 aarch64 prebuilt로 우선 설치(§5).
14. Phantom Killer 해제에 `am set-standby-bucket` 이중 방어와 검증 명령 추가(§2.3).
15. **그래픽 기본 경로를 VirGL/ANGLE에서 Adreno 직결(KGSL mesa/Turnip)로 교체** — 스톡 mesa로는 llvmpipe로 떨어지는 문제와 함께 §1·§3·§5·§7·§8.2·§8.3을 직결 기준으로 재작성하고, VirGL은 §8.5 폴백으로 강등했습니다. 근거: 본 저장소 실측 문서(`docs/research/2026-10-19-y900-graphics-acceleration-next.md`)와 [mesa-for-android-container](https://github.com/lfdevs/mesa-for-android-container).
