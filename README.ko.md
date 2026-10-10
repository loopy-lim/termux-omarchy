# Termux Omarchy

[English](README.md) · [설치·실행](docs/INSTALL.ko.md) · [개발 방식](docs/DEVELOPMENT.ko.md) · [라이선스 목록](legal/README.md)

Android 태블릿에서 Termux, Hyprland와 Omarchy를 사용하는 Wayland 데스크톱 실험입니다. 키보드·트랙패드의 자연스러운 사용, GPU 렌더링, 익숙한 터미널 작업 흐름에 집중합니다.

**현재는 소스만 제공하는 개발용 알파입니다.** Lenovo Y900 한 대에서 개발한 런타임·입력 수정·설정을 정리했습니다. 새 태블릿용 완성 설치기와 수정 APK 다운로드는 아직 제공하지 않습니다. 설치 코드를 사용하기 전에 [설치 범위](docs/INSTALL.ko.md)를 확인해 주세요.

## 구성

Android의 Termux:X11 안에서 native Weston → Arch Linux ARM PRoot → Hyprland와 Omarchy shell을 실행합니다. Linux 창 관리는 Wayland이며 Chromium은 Xwayland를 사용합니다. Termux:X11은 Android 화면 표시와 입력을 담당합니다.

PRoot는 Android 커널을 공유합니다. 별도 Linux 커널·systemd 부팅·Wi-Fi 장치 직접 제어를 제공하지 않으며, 필요한 기능은 Android 설정이나 원격 서버에 연결합니다.

## 포함한 내용

- 세션 시작·종료·복구, 제한된 자식 프로세스 처리와 설치 검증 코드
- 최신 셸·tmux·Hyprland 작업 흐름 소스
- Termux:X11 키 전달·트랙패드 제스처·입력 수명 주기 수정 소스와 회귀 검사
- 소스·설치 입력 목록, 라이선스 고지, 재현 가능한 배포를 위한 개발 절차

개인 설정·SSH 대상·비밀번호·브라우저 데이터·확장 파일·서명키·화면·원본 기기 로그는 제외했습니다. APK·rootfs·외부 패키지 바이너리도 이 저장소에서 배포하지 않습니다.

## 기존 설치에서 다시 열기

**Android의 Termux 앱 기본 셸**에서 실행합니다.

```sh
loopy-omarchy
```

별도로 설치가 끝난 환경의 명령입니다. 이 저장소를 복제하는 것만으로 명령이 설치되지는 않습니다.

| 명령 | 용도 |
| --- | --- |
| `loopy-omarchy start` | 시작하거나 실행 중인 세션으로 복귀 |
| `loopy-omarchy status` | 상태 확인 |
| `loopy-omarchy doctor` | 실행 조건 점검 |
| `loopy-omarchy stop` | 작업 저장 후 세션 종료 |

## 키보드

아래는 검토한 프로필의 동작입니다. Caps 조합에는 호환되는 KeyBridge 설정·서비스와 별도의 입력 전달 수정도 필요합니다.

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

Meta+L의 Android 잠금은 OEM 정책에 해당합니다. 시험한 펌웨어에서는 차단을 확인했지만 다른 기기에 자동 적용하지 않습니다. [Android 권한·정책 안내](docs/PERMISSIONS.md)를 참고해 주세요.

## 확인 범위

기존 시험 설치에서 스크롤 후 트랙패드 이동·물리 클릭·Alt+Tab·Caps 작업공간 전환·Home/End·Meta+L 잠금 차단을 사용자가 확인했습니다. 앞선 GPU 검사에서는 Adreno 경로로 픽셀을 렌더링했습니다.

새 기기 설치·모든 앱·지속 60/144 FPS·입력 지연 수치까지 검증한 결과는 아닙니다. 새 설치 준비와 수정 APK 빌드 입력에 남은 작업이 있으며, 간헐적 네트워크·세션 종료와 장시간·재부팅 동작도 추가 확인이 필요합니다. 관찰된 Chromium 영상 코덱은 소프트웨어였고 VS Code GPU 가속·모든 확장 기능은 미확인입니다. [검증 기록](docs/VALIDATION.md)에 범위를 구분했습니다.

## 개발 시작

호스트 검사에는 Python 3.12 이상, zsh, JDK 17 이상이 필요합니다.

```sh
git clone https://github.com/loopy-lim/termux-omarchy.git
cd termux-omarchy
python3 tools/check_publication.py
```

호스트 검사는 Android에 설치하거나 설정을 바꾸지 않습니다. [개발 문서](docs/DEVELOPMENT.ko.md)에 구성별 검사와 배포 전 조건을 정리했습니다.

## 라이선스

프로젝트의 새 연결 코드와 입력 수정은 [GPL-3.0-only](LICENSE)로 제공합니다. 포함한 외부 소스는 원래 라이선스와 저작권 고지를 유지합니다. 자세한 범위는 [NOTICE](NOTICE.md)와 [구성요소 목록](legal/README.md)에 있습니다.

Omarchy·Hyprland·Termux·Lenovo·Chromium·Microsoft의 공식 프로젝트가 아닌 독립적인 실험입니다. 이름은 구성요소 식별에 사용하며 공식 제휴나 보증을 뜻하지 않습니다.
