# Omarchy/Wayland 원격 화면 · RDP/VNC

**메뉴 → 원격 화면 · RDP/VNC** 또는 SSH 연결 창의 같은 버튼에서 다른 컴퓨터의 데스크톱을 연다. 실제 Omarchy에서는 별도 고정 Arch ARM Remmina 1.4.43 GTK3 클라이언트를 `GDK_BACKEND=wayland`로 실행하며 기존 Hyprland 창·작업공간·키보드·포인터를 사용한다. 기존 Sway/Alpine 경로는 Remmina 1.4.40을 계속 사용한다. 대상 컴퓨터에서 RDP/VNC 서버를 준비하고 태블릿이 주소와 포트에 접근할 수 있어야 한다.

1. RDP 또는 VNC를 선택한다. 호스트는 DNS 이름, IPv4 또는 IPv6이며 URL·shell 명령을 입력하지 않는다.
2. 서버의 실제 포트를 입력한다. 기본은 RDP3389, VNC5900이다. VNC display`:1`은 보통 포트5901에 해당하므로 포트로 입력한다. RDP 사용자는 `DOMAIN\user` 또는 계정 주소도 사용할 수 있다.
3. **원격 화면 연결**을 누르고 Remmina에서 서버 인증서·인증을 확인한다. 창을 열었다는 상태는 원격 연결 완료를 뜻하지 않는다. 연결 오류·재시도·전체 화면·종료는 Remmina에서 처리한다.

Ctrl+Alt+Esc는 원격 창보다 먼저 Android 입력을 반납한다. 세션을 종료하지 않으므로 데스크톱으로 다시 진입해 같은 연결을 사용할 수 있다. 원격의 작업 유지와 재접속은 서버의 세션 정책에 따른다. OEM 예약 키가 원격으로 전달된다는 보장은 실기기 시험에 포함된다.

연결 파일은 Linux 홈의 `~/.local/share/loopy/remote-desktop`에 endpoint별로 저장한다. 전용 디렉터리는0700, 새 파일은0600이며 주소·프로토콜·사용자·포트만 받는다. 비밀번호·token·개인 키 필드는 거절한다. `disablepasswordstoring=1`을 적용하며 `cert_ignore=0`으로 RDP 인증서를 무시하지 않는다. 클립보드와 폴더 공유, SSH 터널은 기본으로 끈다. 기존 파일이 생성한 endpoint 설정과 같으면 바이트·inode·수정 시각을 보존해 다시 연다. 사용자가 수정한 기존 파일은 덮어쓰지 않고 오류를 표시한다. Remmina에서 사용자가 직접 설정한 별도 연결은 Remmina의 설정을 따른다. [고정 Omarchy Remmina의 파일 저장 구현](https://gitlab.com/Remmina/Remmina/-/blob/v1.4.43/src/remmina_file.c), [RDP 인증서 처리](https://gitlab.com/Remmina/Remmina/-/blob/v1.4.43/plugins/rdp/rdp_plugin.c).

패키지는 기존 공식 APKINDEX의 SHA와 크기를 대조하고 APK Q1·identity·datahash를 검증해 고정했다. Remmina와31개 추가 의존성은 [desktop lock](../third_party/desktop.lock.json)에 기록한다. 설치 스크립트를 실행하지 않으며 APK RSA 서명 검사는 별도로 수행하지 않는다.

## 실제 Omarchy 클라이언트

Omarchy는 Alpine 패키지를 실행하지 않는다. 기존 고정 Arch ARM 저장소의 `remmina` 1:1.4.43-3, `freerdp` 2:3.32.1-1, `libvncserver` 0.9.15-1과 추가 의존성 6개를 별도 자산에 담았다. 전체 원격 의존성 297개 중 288개는 설치된 이미지의 동일한 패키지를 재사용한다. 기존 921개 패키지와 전체 이미지 SHA256 `7dcc1b53…`를 유지한다. 추가 패키지 9개는 공식 빌드 시스템 서명 `68B3537F39A313B3E574D06777193F152BDBE6A6`과 각 저장소의 고정 SHA256·크기를 검증했다. [공식 ARM 서명 정책](https://archlinuxarm.org/about/package-signing), [자산 출처와 고정 패키지](../android/assets/omarchy-remote-client.provenance.json).

추가 자산은 7,701,324바이트이며 추출된 2,469항목·28,446,633바이트를 앱 전용의 별도 버전에 보관한다. `RemoteClientRuntime`은 기반 이미지의 설치 표식과 자산 SHA256, 모든 일반 파일의 해시 및 링크를 확인한다. 기존 버전이 손상됐거나 수정되면 그대로 보존하고 시작을 멈춘다. 원본 이미지·사용자 HOME·Mac/KeyBridge 프로필을 변경하지 않는다.

기존 Hyprland 세션에 `/loopy-remote-client`, 선택한 RDP/VNC 플러그인의 `/usr/lib/remmina`, Remmina 자료의 `/usr/share/remmina`만 bind한다. 자식 Remmina에만 추가 라이브러리·자료 검색 경로를 넘긴다. 전역 `LD_LIBRARY_PATH`를 변경하지 않는다. Remmina가 실제로 읽는 고정 플러그인 경로에는 RDP와 VNC만 넣으며 비밀번호 저장·원격 명령·추가 credential 플러그인을 넣지 않는다. 플러그인 경로는 [고정 원본의 초기화 구현](https://gitlab.com/Remmina/Remmina/-/blob/v1.4.43/src/remmina_plugin_manager.c)에 따른다.

Android에서 glycin의 SVG·PNG 파일 로더는 사용할 수 없는 namespace를 요청한다. 원격 자산에는 서명된 기존 Adwaita와 Remmina 아이콘 826개 원본 항목에서 생성한 Adwaita 720개·Remmina 43개 아이콘의 원시 픽셀 캐시를 추가했다. GTK 3.24.52의 [캐시 읽기 경로](https://github.com/GNOME/gtk/blob/3.24.52/gtk/gtkiconcache.c)는 이 픽셀로 pixbuf를 직접 만들며 파일 디코더를 호출하지 않는다. 심볼 아이콘은 [같은 버전의 색상 마스크 생성 방식](https://github.com/GNOME/gtk/blob/3.24.52/gtk/encodesymbolic.c)을 따르므로 GTK의 밝은 테마·어두운 테마 색상을 사용한다. 기존 자식 전용 자료 검색 경로에만 적용하며 glycin이나 다른 이미지 디코더의 sandbox 정책은 바꾸지 않는다.

자산 provenance의 `trusted_icons`에는 각 원본·래스터·원시 픽셀·캐시 해시, 생성 코드 해시, rsvg-convert 2.63.2와 사용 라이브러리 버전, 마스크 CSS와 GTK 원본 해시를 기록한다. 빌드 검사는 전체 원본 목록과 캐시 픽셀을 대조한다. Java 추출기는 모든 파일을 검증한 뒤 두 전용 캐시의 시간 정보만 보정하며, 정상 캐시를 다시 준비할 때에는 시간도 유지한다.

```sh
python3 -m unittest tests.test_remote_connections tests.test_remote_desktop \
  tests.test_omarchy_remote tests.test_omarchy_remote_packages \
  tests.test_omarchy_remote_runtime tests.test_omarchy_remote_inputs \
  tests.test_omarchy_remote_icons -v
```

최초 자산 생성은 `python3 tools/prepare_omarchy_remote.py`로 수행한다. 이미 있는 bundle은 보존하므로 다시 생성할 때는 새로운 `--output` 경로를 지정한다. 준비 과정은 임시 GnuPG 키링에서 공식 ARM 서명을 확인하며 사용자 키링에 쓰지 않는다. 원본 libalpm 7.1.0의 버전 비교 코드를 호스트 임시 라이브러리로 컴파일해 SONAME·epoch·pkgrel 비교를 처리한다. 패키지 설치 스크립트와 ARM 실행 파일을 macOS에서 실행하지 않는다.

캐시를 포함한 후보는 `tools.omarchy_remote_icons.generate(root, 새_아이콘_후보_폴더)`로 만든 뒤 `python3 tools/prepare_omarchy_remote.py --icons 새_아이콘_후보_폴더 --output 새_원격_후보_폴더 --no-publish`로 준비한다. 새 후보를 만들 때 이전 생성 래스터를 원본으로 재사용하지 않는다. `--no-publish`는 canonical APK 자산을 보존하고 후보에 provenance와 inventory를 기록한다.

## 확인한 동작과 남은 수락

호스트 검사는 잘못된 주소·port·비밀 필드·symlink 거절, INI와 argv 처리, 실제 파일 모드와 Wayland 환경, 실행 실패 정리를 확인한다. VM의 `remoteVncDisplaysPixelsAndReturnsNativeInput`은 일반 앱 UID에서 실제 Remmina 창을 열고 독립 RFB3.8 loopback 상대의 RGB`51,102,153`을 Android Surface에서 확인한다. A·Enter의 press/release와 포인터 왼쪽 클릭도 상대가 받는지 확인한다.

이 counterpart는 시험 전용이며 인증 없는 local 연결을 사용한다. 실제 네트워크·비밀번호/키·TLS·RDP 서버·물리 USB/Bluetooth 입력·하드웨어 영상 디코드는 이 결과로 수락하지 않는다. 최신 APK와 검증 영수증은 [최종 작업 검증](remaining-work-validation.md)에 있다. 태블릿을 외부에서 제어하는 수신 서버는 제공하지 않는다.

위의 기존 VM Remmina 화면 증거는 Sway/Alpine 경로다. 2026-10-08 Omarchy 호스트 검증은 실제 Hyprland IPC 요청, SSH/RDP/VNC 자식 명령과 환경, 기존 연결 파일 보존, 서명·의존성·자산 추출을 확인했다. 새 클라이언트 ELF 22개의 `DT_NEEDED` 190개가 고정 기반 이미지 또는 추가 자산에 존재함을 확인했다. 라이브러리 존재는 실제 로딩·TLS 인증·원격 화면 표시를 증명하지 않는다. 새 Omarchy APK의 일반 앱 UID 실행, Y900 화면·물리 입력, 사용자 승인 외부 endpoint의 실제 SSH/인증서·RDP/VNC 연결은 추가 수락이 필요하다.
