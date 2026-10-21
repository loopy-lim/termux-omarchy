# 태블릿의 공식 VS Code ARM64 → SSH 개발 서버

2026-10-09 기준 선택은 **Microsoft VS Code 1.141.0 Linux ARM64 공식 압축본**이다. 태블릿에서 편집기 창을 열고 `loopy@100.80.133.120` 개발 서버에 공식 Remote SSH 확장으로 연결한다. Android Tailscale 연결, SSH 인증, GUI 실행 결과는 기기 검증에서 별도로 확인한다.

## 출처와 지원 범위

- Microsoft의 [공식 업데이트 API](https://update.code.visualstudio.com/api/update/linux-arm64/stable/latest)는 `1.141.0`, commit `2a59476c9bfcb90b3ddc372c36762471b7dfad1c`, Linux ARM64 tar.gz와 SHA-256을 제공했다. 고정 응답과 HTTP 메타데이터는 `build/diagnostics/termux-omarchy-vscode-readiness-20261009-01/`에 보존했다.
- 검증한 압축본은 **349,562,023 bytes**, SHA-256 `3b6ea238a2aa9000bab0137c19f06d4e8edcb5587438a3afc9dc9739e793e934`이다. `build/diagnostics/termux-omarchy-vscode-download-20261009-02/receipt.json`이 다운로드 검증 기록이다. 공식 HTTPS 메타데이터와 파일 해시 일치 검증이며, 별도 서명 파일 검증을 했다는 뜻은 아니다.
- [공식 요구 사항](https://code.visualstudio.com/docs/supporting/requirements)은 지원 Linux 배포판과 glibc 2.28 이상을 명시한다. Android/PRoot는 지원 플랫폼 목록에 없다. Linux ARM64 배포물이 있다는 사실과 이 태블릿에서 실행된다는 증거를 구분한다.
- [Portable 문서](https://code.visualstudio.com/docs/setup/portable)에 따라 압축본 옆 `data`가 사용자 데이터와 확장을 보관하며 명령행의 데이터 경로보다 우선한다. 공식 CLI는 `data/tmp`가 있으면 `TMPDIR`도 그 경로로 덮어쓰므로, 새 설치에서는 해당 폴더를 만들지 않고 기존 짧은 bind 경로 `/run/user/1000`을 사용한다. 원본 CLI 위치·SHA·바이트 구간은 `build/diagnostics/termux-omarchy-vscode-installer-host-20261009-02/official-cli-evidence.json`에 보존했다.

## 현재 설치 경계

기준 패키지는 actual 599개이며 `build/diagnostics/termux-omarchy-full-package-metadata-device-20261009-03/installed-inventory.json`의 Q SHA는 `bf595ab948376ab481a53d5a969320a93c20341ad3e0d78560bd766d1928a679`이다. OpenSSH 10.5p1, glibc 2.43, GTK 3, NSS, libsecret, libxkbfile, ALSA가 이미 있다. VS Code/Electron 패키지는 없다. 고정 저장소의 `visual-studio-code-bin 1.140.0-1`과 `lsof` 패키지 후보는 공식 1.141.0 압축본 설치에 사용하지 않는다. 전체 시스템 업그레이드도 하지 않는다. 실제 동적 로딩 및 ARM64 Electron 실행 여부는 기기 검증 범위다.

새 설치기는 아래 경로만 추가한다.

| 항목 | 게스트 경로 |
|---|---|
| 공식 코드·번들 라이브러리 | `/opt/loopy-vscode/1.141.0/` |
| 전용 설정 | `/opt/loopy-vscode/1.141.0/data/user-data/` |
| 설정 파일을 추가할 위치 | `/opt/loopy-vscode/1.141.0/data/user-data/User/settings.json` |
| 전용 확장 | `/opt/loopy-vscode/1.141.0/data/extensions/` |
| 임시 파일 | `/run/user/1000` (기존 짧은 bind 경로, 새로 생성하지 않음) |
| CLI/GUI 실행기 | `/usr/local/bin/loopy-vscode` |
| 앱 메뉴 항목 | `/usr/share/applications/loopy-vscode.desktop` |

설치 기록은 Termux 관리 루트의 `vscode-install.json`이다. 전체 SHA·크기, ARM64 ELF 및 제품 버전, 압축 경로·개수·총 크기를 먼저 검증한다. 소유 UID와 기존 루트/컨테이너/PRoot guard를 확인하고 설치 및 runtime-control 잠금을 획득한 뒤, 새 전용 버전 디렉터리에만 복사한다. 0700/0600으로 정규화하고 원자적으로 게시한다. 알 수 없는 기존 버전, 실행기, 부분 설치, 바뀐 기록은 보존하고 거절한다. 정상 반복 실행은 기록을 포함해 다시 쓰지 않으며, 이미 생성된 전용 설정/확장은 검증 대상 코드와 분리해 보존한다.

현재 실행 중인 Linux 세션은 유지할 수 있다. 최초 설치가 새 전용 경로와 새 실행기만 추가하고 기존 패키지·로드된 라이브러리를 바꾸지 않기 때문이다. 기존 버전 업그레이드/교체와 자동 복구는 이 설치기의 기능이 아니다. 기존 홈 설정, SSH 키, pacman 데이터베이스, 서비스, 배율, 프로필은 수정하지 않는다.

실행기는 공식 `bin/code` CLI를 유지하고 native Wayland 및 현재 Unix Pulse 경로를 사용한다. Android PRoot용 `--no-sandbox`는 [Electron 문서](https://www.electronjs.org/docs/latest/tutorial/sandbox) 기준 Chromium 샌드박스를 끈다. [PRoot의 제약](https://github.com/termux/proot-distro#limitations)은 실제 root/커널 namespace를 제공하지 않으므로 setuid 비트로 이를 해결했다고 주장하지 않는다. 이 실행 모드는 기기 동작 확인 전까지 host 구현 후보이다.

## Remote SSH 후속 검증

[공식 Remote SSH](https://code.visualstudio.com/docs/remote/ssh)는 로컬 OpenSSH 클라이언트와 `ms-vscode-remote.remote-ssh` 확장을 사용하고 서버 쪽에 VS Code Server를 설치한다. 빌드·디버그·프로젝트 실행을 서버로 보내는 구성이다. 기기 담당이 명시적인 전용 SSH config와 portable settings만 추가하고 기존 SSH 키/설정을 보존한다. 이 설치기는 연결하거나 확장을 설치하지 않는다.

[Marketplace 서명 검증](https://code.visualstudio.com/docs/configure/extensions/extension-marketplace)을 유지해 공식 확장을 설치한다. 확장 파일 준비, 실제 CLI 설치, 창 표시, SSH 인증 및 원격 서버 연결 성공은 각각 별도 확인해야 한다. 서버는 [현행 Linux 원격 요구 사항](https://code.visualstudio.com/docs/remote/linux)에 맞는 커널·glibc·libstdc++와 SSH daemon/bash/tar/curl 또는 wget을 갖춰야 한다. 네트워크의 22번 포트 도달만으로 인증과 원격 개발 성공을 뜻하지 않는다.

대안으로 [VSCodium ARM64](https://github.com/VSCodium/vscodium)는 존재하지만 [공식 Remote SSH 호환성이 다르다](https://github.com/VSCodium/vscodium/blob/master/docs/extensions-compatibility.md). [code-server ARM64](https://coder.com/docs/code-server/install)는 브라우저 IDE이며 [Microsoft Remote 확장을 그대로 제공하지 않는다](https://coder.com/docs/code-server/FAQ). 이번 네이티브 공식 VS Code → SSH 흐름에서는 둘 다 설치하지 않는다.
