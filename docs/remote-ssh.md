# Omarchy/Wayland 데스크톱에서 원격 SSH 연결

Loopy의 원격 연결은 다른 Linux·macOS 서버에 접속하는 **SSH 클라이언트**입니다. Linux 메뉴의 `원격 연결`에서 호스트, SSH 사용자, 포트를 입력하면 Wayland `foot` 터미널을 엽니다. 상대 서버에 SSH 서비스가 실행되어 있어야 하며, 태블릿에서 그 서버의 주소와 포트에 접근할 수 있어야 합니다.

처음 연결할 때는 터미널의 서버 지문을 확인하고 인증합니다. 비밀번호·개인 키 내용은 연결 화면이나 최근 연결 파일에 저장하지 않습니다. 이미 사용자가 관리하는 `~/.ssh/config`, 키, `known_hosts`는 OpenSSH의 일반 동작을 따릅니다. 최근 연결에는 호스트·사용자·포트만 최대 16개 저장하며, 다시 선택해 터미널을 열 수 있습니다. 자동으로 인증하거나 연결 성공을 선언하지 않습니다.

실제 Omarchy의 `원격 연결` 작업은 기존 Hyprland IPC를 통해 `/usr/share/loopy/omarchy-bridge/remote_bridge.py ssh`를 실행합니다. Omarchy 이미지에 이미 있는 Arch ARM `openssh` 10.5p1-1과 `foot`을 사용합니다. 연결 화면의 RDP/VNC 버튼도 같은 버전의 도구를 실행합니다. Python/GTK 도구는 기존 Omarchy HOME에서 endpoint 파일을 읽고, SSH 자식에만 Wayland 환경을 지정합니다.

접속 시도는 10초와 한 번의 시도로 제한합니다. 연결된 세션에는 30초 간격의 SSH keepalive와 세 번의 응답 제한을 사용합니다. 접속 실패나 종료 뒤에도 `foot --hold`로 터미널을 남겨 이유를 읽을 수 있습니다. 새 연결은 연결 화면에서 다시 엽니다. 이 옵션들의 의미는 [공식 OpenSSH 설정 설명](https://man.openbsd.org/ssh_config.5)과 [고정 Foot 1.22.3의 옵션 구현](https://codeberg.org/dnkl/foot/src/tag/1.22.3/main.c)에 따릅니다.

터미널에서 직접 사용할 수도 있습니다.

```sh
ssh -t -o StrictHostKeyChecking=ask -o ConnectTimeout=10 -o ConnectionAttempts=1 \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -p 22 -l 사용자 -- 서버주소
scp ./파일 사용자@서버주소:~/
sftp 사용자@서버주소
```

기존 Sway/Alpine 경로의 고정 클라이언트는 `openssh-client-default`, `openssh-client-common`, `openssh-keygen` 10.0_p1-r10과 `libedit` 20250104.3.1-r1입니다. 기존 고정 APKINDEX의 SHA/크기, APK Q1 control checksum, `.PKGINFO` identity/datahash로 패키지를 확인하며 설치 스크립트는 실행하지 않습니다. APK RSA 서명은 별도로 검증하지 않습니다. [OpenSSH 패키지의 고정 공식 recipe](https://gitlab.alpinelinux.org/alpine/aports/-/blob/bef528746a2df2eb398583b712bd749bd9c977d4/main/openssh/APKBUILD)와 [desktop.lock.json](../third_party/desktop.lock.json)에 버전과 출처가 기록되어 있습니다.

## 클라이언트와 서버의 범위

현재 Loopy는 접속용 SSH 터미널과 [Remmina RDP/VNC 화면 클라이언트](remote-desktop.md)를 제공합니다. 다른 컴퓨터에서 Loopy로 들어오는 SSH/RDP/VNC 서버는 포함하지 않습니다. 원격 셸이나 화면이 필요하면 접속 대상에서 해당 서비스를 준비해야 합니다. 무루트 앱 UID의 이 구현을 태블릿의 실제 Linux 부팅이나 OS 전환으로 취급하지 않습니다.

## 호스트 및 일반 APK 검증

호스트 회귀는 주소·사용자·포트 검증, shell 없는 argv, detached terminal streams, 비밀 없는 최근 연결, 잘못된 파일 보존, 실패한 terminal spawn, keepalive/timeout/실패 화면 보존을 검사합니다.

```sh
python3 -m unittest tests.test_remote_connections tests.test_ssh_package_closure -v
```

일반 APK 계측은 두 검사를 분리합니다.

- `remoteMenuOpensNativeWaylandConnectionWindow`: 실제 Linux 연결 창·일반 Android 앱 UID·Surface 및 실제 guest SSH argv.
- `sshClientExchangesAuthenticatedLoopbackWitness`: 일반 앱 UID의 고정 guest OpenSSH가 별도 loopback SSH2 상대와 인증하고 정확한 nonce 응답을 받음. 상대 서버는 고정 fixture 사용자에만 `none` 인증을 허용하며, 비밀번호·개인 키 인증의 실사용 수락을 대신하지 않습니다.

이 테스트 상대는 APK·guest 이미지에 넣지 않습니다. Python 테스트 라이브러리는 workspace의 `build/ssh-fixture/venv`에만 준비합니다. 현재 lock의 native wheels는 macOS universal2이며, 다른 호스트에서는 호환 wheel을 별도로 고정해야 합니다. 기본 준비기는 구성된 Codex Python 3.12 런타임의 기존 `cryptography`·`cffi`를 읽습니다. 다른 Python을 선택한다면 그 런타임에 해당 라이브러리가 있어야 합니다. global pip 설치는 하지 않습니다.

```sh
python3 tools/prepare_ssh_fixture.py
python3 -m unittest tests.test_ssh_fixture -v
build/ssh-fixture/venv/bin/python tools/ssh_test_server.py \
  --output build/ssh-fixture/수정하지않은새실행명 --lifetime 1800
```

기본 `dev/app-test --serial emulator-5582 --suite desktop --output 새경로`는 준비된 workspace counterpart를 자동 시작하고, 해당 VM의 정확한 reverse 한 개만 생성·검증·정리한다. `tools/vm_ssh_fixture.py`의 cleanup receipt에 listener 종료·worker 0·reverse 제거를 기록한다. 다른 reverse는 변경하지 않는다. 다음은 외부 endpoint를 직접 전달하는 고급 절차다.

출력 `endpoint.json`의 `port`, `public_key`, `nonce`를 사용합니다. 서버는 `127.0.0.1`에만 bind하며 임의 명령이나 호스트 셸을 실행하지 않습니다. host key private bytes는 메모리에만 있습니다. owned VM에서만 같은 port의 `adb reverse`를 만들고 계측에 다음 문자열 인수를 전달합니다.

```text
ssh_fixture_port  = endpoint.port
ssh_fixture_key   = endpoint.public_key
ssh_fixture_nonce = endpoint.nonce
```

검사가 끝나면 만든 reverse 한 개만 제거하고, 생성한 정확한 server process만 종료합니다. SIGTERM은 정상 정리로 처리하고 `receipt.json`에 listener 종료·worker 상태·실제 교환을 남깁니다. 앱은 UUID별 임시 `known_hosts` 파일에 공개 키만 적고 `finally`에서 삭제합니다. 사용자 SSH 파일은 수정하지 않습니다.

테스트 counterpart의 dependency pin은 [ssh-fixture.lock.json](../third_party/ssh-fixture.lock.json), 준비기는 [prepare_ssh_fixture.py](../tools/prepare_ssh_fixture.py)에 있습니다. 최종 일반 APK와 VM 수락은 [Wayland 검증 문서](wayland-native-validation.md)의 정확한 APK·receipt에 따릅니다. 호스트 검사나 컴파일만으로 실제 태블릿의 연결, 네트워크, 키보드·마우스 수락을 선언하지 않습니다.
