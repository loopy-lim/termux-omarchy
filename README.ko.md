# Termux Omarchy

[English](README.md) · [설치·실행](docs/INSTALL.ko.md) · [배포 준비](docs/DISTRIBUTION.ko.md) · [개발 방식](docs/DEVELOPMENT.ko.md) · [라이선스 목록](legal/README.md)

Android 태블릿에서 Termux, Hyprland와 Omarchy를 사용하는 Wayland 데스크톱 실험입니다. 키보드·트랙패드의 자연스러운 사용, GPU 렌더링, 익숙한 터미널 작업 흐름에 집중합니다.

**현재는 [v0.1.0-alpha.2](https://github.com/loopy-lim/termux-omarchy/releases/tag/v0.1.0-alpha.2) 실험용 바이너리 배포입니다.** 고정된 런타임 자산, 소스에서 빌드한 Termux:X11 APK와 일치하는 companion, 대응 소스 아카이브를 제공합니다. 사용자는 Android NDK가 필요하지 않습니다. 이 후보는 **새 기기 GUI 수락 검증을 통과하지 않았으며** `fullFreshInstallVerified`는 `false`입니다.

설치 대상은 Android 기본 사용자의 네이티브 ARM64 Termux이며, 일치하는 GitHub 서명 계열, Android API 28 이상과 접근 가능한 Adreno KGSL 장치가 필요합니다. 새 데스크톱 설치 경로이며 이전 비공개 설치의 마이그레이션은 지원하지 않습니다. 적용 전에 [설치 안내](docs/INSTALL.ko.md)를 확인하세요.

## 구성

Android의 Termux:X11 안에서 native Weston → Arch Linux ARM PRoot → Hyprland와 Omarchy shell을 실행합니다. Linux 창 관리는 Wayland이며 Chromium은 Xwayland를 사용합니다. Termux:X11은 Android 화면 표시와 입력을 담당합니다.

PRoot는 Android 커널을 공유합니다. 별도 Linux 커널·systemd 부팅·Wi-Fi 장치 직접 제어를 제공하지 않으며, 필요한 기능은 Android 설정이나 원격 서버에 연결합니다.

## 포함한 내용

- 세션 시작·종료·복구, 제한된 자식 프로세스 처리와 설치 검증 코드
- 최신 셸·tmux·Hyprland 작업 흐름 소스
- Termux:X11 키 전달·트랙패드 제스처·입력 수명 주기 수정 소스와 회귀 검사
- 고정된 다운로드·새 설치 도구, 페이로드 목록, 라이선스 고지와 대응 소스 아카이브

개인 설정·SSH 대상·비밀번호·브라우저 데이터·확장 파일·서명키·화면·원본 기기 로그는 제외했습니다. Git에는 소스와 검사를 담습니다. 바이너리는 릴리스 자산과 고정한 업스트림 다운로드로 별도 제공합니다.

## 실험용 설치 자산 다운로드

기존에 신뢰하는 서명 APT 소스가 있는 Android **Termux 앱 기본 셸**에서 시작합니다. 첫 단계는 Git·Python이 없을 때만 설치하며 전체 업그레이드는 하지 않습니다. Termux 홈 안의 새 절대 경로를 사용하세요.

```sh
if ! command -v git >/dev/null; then
  pkg install git
fi
if ! command -v python3 >/dev/null; then
  pkg install python
fi
cd "$HOME"
git clone --branch v0.1.0-alpha.2 --depth 1 https://github.com/loopy-lim/termux-omarchy.git termux-omarchy-alpha2
cd termux-omarchy-alpha2
python3 -B installer/verify.py
python3 -B tools/acquire_distribution.py --plan
export OMARCHY_ASSETS="$HOME/termux-omarchy-v0.1.0-alpha.2-assets"
python3 -B tools/acquire_distribution.py --output "$OMARCHY_ASSETS"
```

고정한 파일 88개를 내려받고 로컬 manifest 2개를 검증해 복사하여 총 90개 파일을 구성합니다. 다운로드는 설치·압축 해제·권한 부여를 하지 않습니다. 기존 출력이나 실패한 부분 출력은 보존하고 재사용을 거부합니다. [설치 단계](docs/INSTALL.ko.md)에 따라 정확한 APK를 Android 동의로 설치하고, 누락된 네이티브 의존성을 준비한 뒤 자산을 명시적으로 적용하세요.

## 설치한 데스크톱 시작

**Android의 Termux 앱 기본 셸**에서 실행합니다.

```sh
loopy-omarchy start
loopy-omarchy status
loopy-omarchy doctor
```

명시적 설치 단계를 마친 뒤 사용할 수 있습니다. 소스 복제나 다운로드만으로 launcher가 설치되지 않으며 설치기는 런타임을 자동으로 시작하지 않습니다.

| 명령 | 용도 |
| --- | --- |
| `loopy-omarchy start` | 시작하거나 실행 중인 세션으로 복귀 |
| `loopy-omarchy status` | 상태 확인 |
| `loopy-omarchy doctor` | 실행 조건 점검 |
| `loopy-omarchy stop` | 작업 저장 후 세션 종료 |

## 키보드

아래는 검토한 프로필의 동작입니다. Caps 조합에는 선택적으로 구성한 KeyBridge 서비스와 입력 전달이 필요합니다. 일반 사용자를 위한 이식 가능한 KeyBridge 설정은 아직 정리되지 않았고 helper는 기본으로 꺼져 있습니다. 기본 설치나 Lua 프로필만으로 Caps 조합이 활성화되지 않습니다.

| 조합 | 동작 |
| --- | --- |
| Alt+Space | Omarchy 메뉴 |
| Alt+Tab / Alt+Shift+Tab | Linux 창 전환 |
| Meta+1…0 / Meta+Shift+1…0 | 작업공간 이동 / 창 보내기 |
| Caps+H/J/K/L | 방향키 |
| Caps+D/F | 이전·다음 기존 작업공간 |
| Meta+Caps+H/J/K/L | 방향에 있는 창으로 포커스 이동 |
| Alt+Caps+H/L | 줄 처음·끝 |
| Alt+Caps+K/J | 문서 처음·끝 |
| Alt+C/V | 앱에 맞게 복사·붙여넣기 전달 |
| Alt+- / Alt++ 또는 Alt+= | Foot 글자 크기 축소·확대 |
| Alt+1…0 | tmux 창 선택 |

Meta+L의 Android 잠금은 OEM 정책에 해당합니다. 시험한 펌웨어에서는 차단을 확인했지만 다른 기기에 자동 적용하지 않습니다. [Android 권한·정책 안내](docs/PERMISSIONS.ko.md)를 참고해 주세요.

## 확인 범위

기존 시험 설치에서 스크롤 후 트랙패드 이동·물리 클릭·Alt+Tab·Caps 작업공간 전환·Home/End·Meta+L 잠금 차단을 사용자가 확인했습니다. 앞선 GPU 검사에서는 Adreno 경로로 픽셀을 렌더링했습니다.

내보낸 전체 APK 소스로 Android ABI 4종의 오프라인 빌드를 통과했고 guard도 오프라인 재빌드에서 바이트가 일치했습니다. 이 결과만으로 릴리스 후보의 Android 설치·입력 전달·GUI 수락을 검증한 것은 아닙니다.

새 기기 의존성 준비·GUI 수락, 개발 중 관찰한 간헐적 네트워크·세션 종료, 장시간·재부팅 동작은 추가 확인이 필요합니다. 관찰된 Chromium 영상 코덱은 소프트웨어였고 VS Code GPU 가속·모든 확장 기능은 미확인입니다. 지속 60/144 FPS와 입력 지연 수치는 측정·수락하지 않았습니다. [검증 기록](docs/VALIDATION.ko.md)에 범위를 구분했습니다.

## 개발 시작

호스트 검사에는 Python 3.12 이상, zsh, JDK 17 이상이 필요합니다.

```sh
python3 -B tools/check_publication.py
```

소스 checkout에서 실행합니다. 호스트 검사는 Android에 설치하거나 설정을 바꾸지 않습니다. [개발 문서](docs/DEVELOPMENT.ko.md)에 구성별 검사, [배포 준비](docs/DISTRIBUTION.ko.md)에 릴리스 입력 재빌드 절차를 정리했습니다.

## 라이선스

프로젝트의 새 연결 코드와 입력 수정은 [GPL-3.0-only](LICENSE)로 제공합니다. 포함한 외부 소스는 원래 라이선스와 저작권 고지를 유지합니다. 자세한 범위는 [NOTICE](NOTICE.md)와 [구성요소 목록](legal/README.md)에 있습니다.

Omarchy·Hyprland·Termux·Lenovo·Chromium·Microsoft의 공식 프로젝트가 아닌 독립적인 실험입니다. 이름은 구성요소 식별에 사용하며 공식 제휴나 보증을 뜻하지 않습니다.
