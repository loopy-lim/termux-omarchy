# 설치와 다음 실행

[English](INSTALL.md) · [한국어 README](../README.ko.md)

## 실험용 설치 범위

[v0.1.0-alpha.2](https://github.com/loopy-lim/termux-omarchy/releases/tag/v0.1.0-alpha.2)는 고정된 바이너리 배포 경로를 제공합니다. **이 후보는 새 기기 GUI 수락 검증을 통과하지 않았으며 `fullFreshInstallVerified`는 `false`입니다.** 배포 자산을 받아 적용하는 사용자에게는 NDK나 Android SDK가 필요하지 않습니다.

필요한 조건은 다음과 같습니다.

- Android 기본 사용자의 ARM64 환경, API 28 이상과 Termux가 접근할 수 있는 Adreno `/dev/kgsl-3d0` 장치
- 기존에 신뢰하는 서명 Termux APT 소스를 사용하는 **GitHub 서명 계열**의 네이티브 Termux. 첫 단계에서 Git·네이티브 Python 3가 없으면 준비합니다.
- 이전 관리 런타임·PRoot 컨테이너·launcher·불일치하는 Termux:X11 companion이 없는 새 데스크톱 상태
- Android 설치 동의와 수락 검증용 물리 키보드·트랙패드

다운로드와 게스트 압축 해제를 위해 여유 공간 8 GiB 이상을 계획하세요. 측정한 최대 사용량이 아닌 준비용 여유분입니다.

F-Droid·Google Play·GitHub 서명 계열은 서로 교환할 수 없습니다. 서명 충돌은 중단 조건이며 호환성을 강제로 맞추려고 앱을 삭제하거나 데이터를 지우면 안 됩니다. 기존 비공개 데스크톱 상태와 예상하지 못한 companion 버전·파일은 보존하고 거부합니다. 이번 릴리스는 마이그레이션을 지원하지 않습니다. [공식 Termux 설치 안내](https://github.com/termux/termux-app#installation)와 [Termux:X11 안내](https://github.com/termux/termux-x11)를 참고하세요.

## 1. 정확한 릴리스 입력 받기

Linux나 PRoot 내부가 아닌 **Android Termux 앱의 네이티브 셸**에서 실행합니다. 첫 패키지 명령은 Git·Python이 없을 때만 실행하며 전체 패키지 업그레이드를 요청하지 않습니다.

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

출력은 소유한 디렉터리 아래의 새 절대 경로여야 하며 Termux 홈이 적합합니다. 고정한 파일 88개를 내려받고 로컬 manifest 2개를 검증해 복사하여 정확한 90개 파일 트리를 만듭니다. 압축 해제나 설치는 하지 않습니다. 기존·부분 출력은 삭제 없이 거부하므로 실패한 시도는 보존하고 새 경로를 선택하세요. 소유자·권한 검사가 유효하도록 전체 자산 트리는 네이티브 Termux 저장소에 유지합니다.

해시는 검토한 바이트의 식별자이며 신뢰된 서명자를 증명하지 않습니다. 네이티브 APT는 기존 신뢰 키를 사용하고 게스트 패키지는 기존 신뢰 키링으로 분리 서명을 검증해야 합니다. 도구는 서명 검사를 끄거나 임의의 키를 가져오지 않습니다.

## 2. Android 동의로 정확한 APK 설치

Termux:X11을 바꾸기 전에 작업을 저장하세요. Termux와 UID를 공유하는 앱의 설치는 관련 프로세스를 중단할 수 있습니다. 이전 데스크톱이나 불일치하는 companion이 있으면 변경 전에 중단하고 검토하세요.

정확히 받은 APK에 대해 Android 설치 화면을 요청합니다.

```sh
termux-open --view --content-type application/vnd.android.package-archive "$OMARCHY_ASSETS/input/termux-x11.apk"
```

이 명령은 Android 동의 화면을 열며 설치를 자동 승인하지 않습니다. 안내를 검토하고 요청받았으며 설치하려는 경우에만 이 출처의 앱 설치를 허용하세요. Termux 홈 공개나 공유 저장소 접근 권한은 필요하지 않습니다. 앱 데이터를 보존하고 패키지·인증서 충돌이 있으면 중단합니다. 설치기는 설치된 base APK의 정확한 해시를 이 릴리스와 비교하므로 다른 nightly APK로 대체할 수 없습니다.

공개된 업스트림 개발 서명 식별자는 독점적인 배포자 신원이 아닙니다. 일치하는 인증서는 shared UID 호환성을 제공하지만 이 포크를 공식 Termux 릴리스로 인증하지는 않습니다. APK와 소스에서 빌드한 companion은 한 쌍으로 유지해야 합니다. [서명 안내](../input/full_build/SIGNING.md)를 참고하세요.

## 3. 누락된 네이티브 의존성 준비

네이티브 Termux 셸로 돌아옵니다. Android가 셸을 다시 시작했다면 소스 디렉터리와 자산 경로를 복원하세요.

```sh
cd "$HOME/termux-omarchy-alpha2"
export OMARCHY_ASSETS="$HOME/termux-omarchy-v0.1.0-alpha.2-assets"
python3 -B installer/native.py --check
# 보고된 누락 네이티브 의존성을 설치할 때만 실행:
python3 -B installer/native.py --apply
python3 -B installer/native.py --check
```

명시적 apply는 서명된 APT 메타데이터를 갱신하고 공식 X11 저장소 패키지가 없으면 추가한 뒤 누락된 의존성을 설치합니다. 기존 패키지는 현재 버전에 고정하고 업그레이드·제거를 거부합니다. PRoot-Distro 5.8과 검토한 5.9.0을 지원합니다. 전체 업그레이드·전역 PIP 설치·APK 설치·서비스 자동 시작은 하지 않습니다. 의존성 충돌은 검토해야 하며 검사를 우회하면 안 됩니다. 정확한 릴리스 companion은 일반 저장소 nightly가 아닌 자산 설치기가 처리합니다.

## 4. 새 데스크톱 자산 적용

```sh
python3 -B installer/install.py --check --assets "$OMARCHY_ASSETS"
python3 -B installer/install.py --apply --assets "$OMARCHY_ASSETS"
```

check는 소스와 전체 로컬 자산 트리를 검증합니다. apply는 추가로 네이티브 실행 환경, API·KGSL 접근, 필수 패키지, 정확히 설치된 APK와 새 설치 상태를 검사합니다. 검토한 로컬 companion이 없으면 설치하고 정확한 검토 버전·파일이면 허용합니다. 다른 companion은 보존하고 거부합니다. 그 뒤 데스크톱 구성요소와 launcher를 설치합니다. 예상하지 못한 해시·소유자·symlink·기존 데스크톱 상태는 중단 조건입니다.

`installed-components`는 구성요소 설치가 끝났다는 뜻이며 화면 표시나 물리 수락 검증 성공을 뜻하지 않습니다. 설치기는 데스크톱 시작·Android 권한 부여·접근성 활성화·OEM 정책 변경·개인 프로필 가져오기를 하지 않습니다. 거부를 우회하기 위해 파일을 직접 덮어쓰거나 기존 상태를 지우지 마세요.

## 5. 데스크톱 시작과 확인

```sh
loopy-omarchy start
loopy-omarchy status
loopy-omarchy doctor
```

사용하려는 Android 키보드·입력기·접근성 동의는 Android 설정에서 명시적으로 완료합니다. 일반 사용자용 KeyBridge/Caps 설정은 미해결된 선택 기능이며 helper는 기본으로 꺼져 있습니다. 기본 설치는 해당 매핑을 켜거나 개인 opt-in marker를 복사하지 않습니다.

대상 기기에서 GPU의 실제 화면 출력, 들리는 오디오, 키 누름·해제와 한글 입력, 물리 클릭, 이동→두 손가락 스크롤→손 떼기→다시 이동, 앱 복귀, 정상 종료·시작을 확인하세요. OEM 단축키와 백그라운드 프로세스 정책은 원래 값과 복구 방법을 보존하는 별도 선택입니다. [권한 안내](PERMISSIONS.ko.md)를 참고하세요. 새 후보의 GUI 수락, 지속 60/144 FPS, 지연 측정과 재부팅 동작은 미검증입니다.

## 다음 실행

Android의 **Termux 앱 기본 셸**에서 `loopy-omarchy`를 실행하세요. Linux 안의 Foot 터미널이나 별도 PRoot 셸에서 실행하는 명령이 아닙니다. 실행 중이면 기존 세션으로 돌아가고, 멈춰 있으면 시작합니다.

`loopy-omarchy status`는 상태, `loopy-omarchy doctor`는 실행 조건을 확인합니다. 완전히 종료하려면 작업을 저장한 뒤 `loopy-omarchy stop`을 사용하세요. Android의 다른 앱에서 돌아올 때는 Termux:X11을 다시 열거나, 앞에 띄운 Termux에서 같은 시작 명령을 실행합니다. 재부팅 뒤 자동 시작은 미검증입니다.

복귀 후 포인터가 잡히지 않으면 Linux 화면의 빈 곳을 손가락으로 한 번 터치해 보세요. Caps 조합만 실패하면 설정한 KeyBridge 입력 연결을 확인하세요. 다른 기기의 private opt-in marker를 그대로 복사하거나 임의의 접근성 서비스를 켜지 마세요.

## Linux 안에서 앱 실행

해당 연동 구성이 이미 설치된 환경의 **Linux 터미널**에서 사용합니다.

| 용도 | 명령 |
| --- | --- |
| Chromium | `gtk-launch chromium` |
| 별도로 설치한 VS Code | `loopy-vscode` |
| Notion 독립 웹 창 | `loopy-launch-webapp https://www.notion.so` |
| Figma 독립 웹 창 | `loopy-launch-webapp https://www.figma.com` |
| 원격 연결 메뉴 | `omarchy-remote` |
| Android Wi-Fi 설정 | `omarchy-proot-settings wifi` |

Notion·Figma는 주소창을 숨긴 Chromium 웹 창입니다. Android 앱을 내부에 넣는 구조가 아닙니다. 로그인은 기기에서 직접 하며 실제 문서·디자인 편집까지 수락된 상태는 아닙니다.

SSH는 본인의 별칭·서버 키 확인·인증을 설정하세요. Tailscale이 필요한 서버라면 Android에서 먼저 연결되어 있어야 합니다. 개인 서버 주소·비밀번호·SSH 키는 포함하지 않습니다. VS Code와 확장은 허용된 원본에서 해당 이용 조건에 맞게 설치합니다.

시험한 PRoot 브라우저·편집기 경로에는 `--no-sandbox` 같은 호환성 절충이 필요했습니다. PRoot를 강한 격리 환경으로 취급하지 마세요. 런처 소스를 검토하고 완전한 Linux 보안 환경이 필요한 작업은 원격 서버에서 진행하세요.

## GPU와 크기

native Weston의 Zink/Turnip과 guest Mesa/Freedreno KGSL은 서로 다른 환경입니다. 하나의 전역 환경변수로 둘을 일괄 변경하지 않습니다. 실제 SoC·커널 인터페이스·드라이버·앱 백엔드에 따라 가속 가능 여부가 달라집니다.

renderer 이름뿐 아니라 실제 픽셀·앱 GPU 상태를 확인해야 합니다. 시험 기기에서는 native·guest Adreno 픽셀과 Chromium ANGLE/Vulkan을 확인했습니다. VS Code GPU는 미확인, 영상 코덱은 소프트웨어였습니다. 60 Hz 요청은 지속 60 FPS의 증거가 아니며 144 FPS도 미검증입니다.

화면 픽셀 크기·데스크톱 배율·브라우저 및 터미널 확대는 각각 조정해야 합니다. 검토한 프로필의 배율 1.5는 시작점이며 모든 태블릿에 맞는 값은 아닙니다. 크기 변경 뒤에는 창 복구·스크롤·가장자리·Android 앱 복귀를 함께 확인해야 합니다.
