# 설치와 다음 실행

[English](INSTALL.md) · [한국어 README](../README.ko.md)

## 이번 공개 범위

이번 소스 알파는 코드 검토·회귀 검사·후속 개발용입니다. **새 태블릿에 곧바로 설치하는 완성 배포판은 아닙니다.** 이전 설치 묶음에는 최신 입력 변경이 없고, 일부 바이너리 입력 생성도 이 저장소만으로 재현되지 않습니다. 이전 묶음을 최신 완성본으로 사용하지 마세요.

설치 코드는 해시·소유자·경로·기존 상태를 검사합니다. 입력 파일이 없으면 해당 준비 작업을 마쳐야 하며, 검사를 끄고 진행하지 않습니다. 실행 중인 설치에 파일을 직접 덮어쓰면 런타임 소유 정보·해시와 달라질 수 있습니다.

## 새 설치에 필요한 조건

- ARM64 Android와 서로 호환되는 Termux·Termux:X11
- 고정한 목록에 맞는 native Python·PRoot-Distro·그래픽·오디오 구성요소
- 해시가 맞는 upstream Omarchy Android 묶음과 검증한 native·guest 입력
- shared UID를 쓸 경우 서로 맞는 APK 서명
- 물리 키보드·트랙패드 시험과 선택 입력 서비스의 Android 최초 동의

시험 설치는 GitHub Termux 서명 계열을 사용했습니다. F-Droid·Google Play·GitHub APK를 섞으면 shared UID·업데이트 서명이 맞지 않을 수 있습니다. 출처 변경을 고려한다면 먼저 기존 Termux 데이터를 백업하고 [공식 Termux 설치 안내](https://github.com/termux/termux-app#installation)와 [Termux:X11 안내](https://github.com/termux/termux-x11)를 확인하세요.

정확한 소스 고정과 남은 빌드 입력은 manifest 및 [입력 소스 문서](../input/README.md)에 있습니다. APK와 전체 rootfs는 이번 배포에 포함하지 않았습니다. [개발 문서](DEVELOPMENT.ko.md)에 완성 배포 전 단계를 정리했습니다.

## 기존 설치에서 여는 방법

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
