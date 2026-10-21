# Loopy Desktop 빠른 시작

Android 위에서 실제 Linux 앱인 **Loopy Browser · WebKit·Geany 2.0·Mousepad·Thunar·foot**를 Sway 창으로 사용하도록 구성했습니다. 브라우저는 자체 GTK3 UI와 실제 WebKitGTK 2.48.1 엔진을 사용합니다.

기본 실행 경로는 **Loopy Desktop의 Wayland/Sway 데스크톱**이다. 대상은 Y900 13 **TB522FU**다. [현재 APK와 검증 범위](../build/deliverables/LoopyDesktop-2026-10-07-native-prompt-arm64/README.md)와 [실기기 점검](y900-test-checklist.md)을 확인한다. Android VM의 합성 입력은 물리 USB/Bluetooth 입력과 GPU 성능의 수락을 대신하지 않는다. 이번 작업에서는 실기기를 연결하거나 변경하지 않았다.

현재 APK는 372,636,567바이트(약 355MiB)이며 압축을 푼 Linux 파일과 준비 중 임시 파일을 저장할 공간이 추가로 필요하다. 고정 패키지는 **262개**다. 업데이트할 때 기존 브라우저 프로필·프로젝트·Linux 설정은 보존한다. 이전 APK 이력은 [기존 검증](capability-fallback-validation.md)에 있다.

## Wayland 데스크톱 처음 열기

1. 제공된 APK를 설치하고 **Loopy Desktop**을 엽니다. 업데이트할 때는 기존 앱을 삭제하지 말고 데이터를 보존합니다.
2. 첫 실행은 Linux 파일을 준비하므로 시간이 걸립니다. 이미지 크기와 기기의 저장장치 성능에 따라 소요 시간이 다릅니다.
3. 물리 키보드나 마우스·트랙패드가 처음 감지되면 **실사용 준비 · 권한/진단**이 한 번 열립니다. 이미 연결한 채 처음 실행해도 표시됩니다. 아래 항목을 필요한 만큼 설정하고 **완료**로 닫습니다. 다시 연결하거나 앱을 다시 열어도 반복해서 안내하지 않습니다.
4. Android의 전체 화면 안내가 뜨면 사용자가 직접 확인 버튼을 눌러 닫습니다.
5. Sway 배경·상단 바·앱 메뉴가 나타나면 앱 이름을 검색하고 방향키와 Enter로 엽니다. Escape는 메뉴를 닫습니다.

상단 바에는 작업공간을 표시합니다. 오른쪽 위 상태 표시와 트레이는 제거했습니다.

**Ctrl+Alt+Esc** 또는 Android **뒤로 가기**로 입력 캡처를 풀고 상단 제어 버튼을 엽니다. 비상 단축키는 데스크톱 단축키를 Super나 Alt로 바꿔도 Ctrl+Alt+Esc입니다.
**데스크톱**은 Linux 화면으로 돌아갑니다. 전체 화면 오른쪽 아래 **메뉴**에서도 같은 제어를 열 수 있습니다. **메뉴 → 앱**은 Android 측 빠른 메뉴입니다.
Android 앱을 실행하면 원래 Android 창이 열립니다. Linux 창 안에 Android 앱이 들어가는 구조는 아닙니다.

## 실사용 준비 · 권한/진단

**메뉴 → 설정** → **실사용 준비 · 권한/진단**에서 언제든 다시 엽니다. 설정과 준비 화면은 스크롤할 수 있습니다. 준비 화면을 열면 기존 설정 창은 닫힙니다. **완료**로 닫고 **데스크톱**을 누르면 전체 화면으로 돌아갑니다. 물리 키보드·마우스/트랙패드 개수와 서비스 상태는 연결 변경에 따라 갱신됩니다.

| 항목 | 사용 방법 |
| --- | --- |
| 키보드 입력 우선권 | **입력 우선권 설정**에서 사용자가 **Loopy 입력 우선권** 접근성 서비스를 켭니다. **사용 설정됨 · 서비스 연결 대기**와 **키보드 우선권 연결됨**은 다른 상태입니다. 화면 내용은 읽지 않습니다. 기본 Ctrl+Alt로 먼저 사용하고, 연결 후 설정에서 Super/Command 또는 Alt를 선택합니다. |
| APK 설치 후 접근성 제한 | Android 13 이상에서 사용 설정이 제한되면 **Loopy Desktop 앱 정보**를 열어 메뉴의 **제한된 설정 허용**을 선택한 뒤 다시 시도합니다. |
| 세션 알림 | Android 13 이상에서 **세션 알림 허용**을 눌러 OS 권한 창을 엽니다. 허용하면 알림의 복귀·**Linux 세션 종료** 버튼을 쓸 수 있습니다. 거부 후에는 **알림 설정**에서 변경하며 데스크톱 사용은 계속할 수 있습니다. |
| 백그라운드 세션 · 선택 | 화면을 끈 뒤 작업이 중단되는 경우 **배터리 최적화 설정**에서 Loopy Desktop의 예외 여부를 직접 선택합니다. 예외 설정도 강제 종료·메모리 회수 뒤 미저장 상태를 복원하지는 않습니다. |
| 기본 홈 · 선택 | **기본 홈 선택**에서 Loopy Desktop을 선택하면 Android 홈 버튼으로 돌아올 수 있습니다. API 29 이상에서는 지원되는 Home 역할 선택 창을 열고, 다른 버전이나 기기에서는 홈 설정으로 연결합니다. 원래 홈으로 돌리려면 **기본 홈 변경**에서 기존 Android 홈을 선택합니다. |

준비 화면이 권한이나 기본 홈을 자동으로 변경하지는 않습니다. 제조사 예약 키와 시스템 제스처의 전체 제어는 일반 앱의 공개 API만으로 보장하지 않습니다. 필요한 설정 화면을 열 수 없으면 준비 화면에 안내를 표시하며 Linux 세션을 종료하지 않습니다.

## 터미널 입력 모드

기본 터미널은 빠른 Linux 프롬프트를 사용하는 Zsh입니다. 명령 별칭·fzf·zoxide·기록·tmux 설정을 유지합니다. 현재 Mac과 같은 프롬프트 외형, 자동 제안과 구문 강조를 원하면 **메뉴 → 터미널 입력 모드 → Mac 전체 외형**을 선택하세요. 빠른 모드는 해당 세 가지 화면 기능을 생략해 입력 부담을 줄입니다.

선택은 다음에 여는 터미널부터 적용합니다. 열린 터미널은 계속 사용할 수 있으며, 기존 `.zshrc`와 `.tmux.conf`를 덮어쓰지 않습니다. **빠른 Linux 프롬프트**를 다시 선택하면 가벼운 모드로 돌아갑니다. Mac 전용 실행 파일·SDK 경로는 Linux 도구로 바뀌거나 설치된 경우에만 사용합니다.

**메뉴 → Linux 데스크톱 선택**에서 Sway 또는 Omarchy/Hyprland를 고를 수 있습니다. Omarchy는 [별도 전체 이미지 설치](omarchy-android-installation.md)가 먼저 필요합니다. 준비에 실패하면 현재 데스크톱을 유지합니다. 현재 APK의 새 이미지 GUI 활성화와 Y900 실기기 성능 확인은 진행 중입니다.

## Linux 앱과 키보드

| 기본 단축키 | 동작 |
| --- | --- |
| Ctrl+Alt+Enter | foot 터미널 |
| Ctrl+Alt+Shift+E | Mousepad 그래픽 편집기 |
| Ctrl+Alt+Shift+B | Linux Loopy Browser · WebKit |
| Ctrl+Alt+Shift+C | Geany 코드 편집기 |
| Ctrl+Alt+E | Thunar 파일 관리자 |
| Ctrl+Alt+Space | Linux 앱 검색 메뉴 |
| Ctrl+Alt+Tab | 열린 창 목록 |
| Ctrl+Alt+1…9 | 작업공간 전환 |
| Ctrl+Alt+Shift+1…9 | 현재 창을 다른 작업공간으로 이동 |
| Ctrl+Alt+Shift+Q | 현재 Linux 창 닫기 |
| Ctrl+Alt+Esc | 입력 캡처 해제·Android 제어 메뉴 열기 |

Caps를 짧게 탭하면 한/영을 전환합니다. Caps를 누른 채 H/J/K/L을 누르면 방향키가 됩니다.
Caps를 길게 누르기만 하면 언어가 바뀌지 않습니다. 화면 키보드는 **메뉴 → 키보드 표시 / 숨기기**에서 엽니다.
전체 창 관리 키는 [키보드 안내](../guest/desktop/root/Keyboard.md)를 참고하세요.
앱 메뉴의 **Other Linux apps**에서는 설치된 Linux 앱의 `.desktop` 항목을 검색합니다. 안전하게 실행 명령을 해석할 수 있는 항목만 표시하므로 모든 설치 앱이 나타나는 것은 아닙니다.
**Linux browser · Loopy Browser**와 **Code IDE · Geany**는 앱 메뉴의 고정 항목에서도 선택합니다. Loopy Browser의 페이지 엔진은 WebKit입니다. Geany는 실제 GUI 코드 편집기이지만 VS Code와 동일한 제품이나 확장 기능을 제공하지는 않습니다.

## 브라우저와 네트워크

**Loopy Browser · WebKit**는 자체 Linux GTK3 주소창·탭 UI를 사용합니다. 원본 MiniBrowser가 기본으로 열리는 구성은 아닙니다. 앱 메뉴의 Android 브라우저는 별도로 원래 Android 창을 엽니다.

| 브라우저 키 | 동작 |
| --- | --- |
| Ctrl+L | 주소 또는 검색어 입력 |
| Ctrl+T / Ctrl+W | 새 탭 / 현재 탭 닫기 |
| Ctrl+Tab / Ctrl+Shift+Tab | 다음 / 이전 탭 |
| Alt+Left / Alt+Right | 뒤로 / 앞으로 |
| Ctrl+R / F5 | 새로고침 |

HTTP·HTTPS 주소를 열며 일반 검색어는 DuckDuckGo HTTPS 검색으로 연결합니다. 주소창에서 Escape를 누르면 페이지로 포커스가 돌아갑니다. 마지막 탭을 닫으면 브라우저 창도 닫힙니다.
쿠키·웹 데이터는 HOME/XDG 아래 별도 `loopy-browser` 디렉터리를 사용합니다. 기본 데이터 경로는 `/root/.local/share/loopy-browser`, 캐시는 `/root/.cache/loopy-browser`이며 쿠키 파일은 `cookies.sqlite`입니다. 기존 Firefox·MiniBrowser 프로필이나 프로젝트는 지우거나 자동 가져오지 않습니다.
브라우저의 Linux 렌더링은 Wayland와 CPU를 사용합니다. [정확한 설정과 공식 근거](research/linux-browser-code-editor.md)를 참고하세요. Android 화면 출력의 GLES 경로는 아래 **화면 출력과 GPU**와 구분합니다.
이 UI는 추가 Linux WebKit 프로세스 샌드박스를 명시적으로 끕니다. 별도 bypass 환경변수는 설정하지 않으며 추가 namespace 격리를 제공하지 않습니다. 기본 격리는 Android 앱 UID·SELinux·상속된 앱 정책에 의존하고 PRoot 자체는 보안 경계가 아닙니다.
외부 HTTPS 확인 주소는 `https://example.com`입니다. 현재 APK의 확인 범위는 [현재 검증 기록](wayland-native-validation.md)을 참고하세요. 검색·다른 사이트·Private DNS·VPN은 각각 별도로 확인합니다. 이전 MiniBrowser 입력 실패와 worker 정책 관찰은 [구성 기록](research/linux-browser-code-editor.md#minibrowser-입력-관찰과-자체-ui-선택)에 보존하며, 이전 APK나 별도 `run-as` 결과를 현재 일반 앱의 성공으로 대신 쓰지 않습니다.

Loopy는 활성 Android 네트워크가 알려 준 DNS 주소를 Linux에 자동으로 전달하고, 네트워크 정보가 바뀌면 갱신합니다. 공개 DNS 서버를 임의로 추가하지 않습니다.
사용자 Linux 환경의 기존 `/etc/resolv.conf`는 보존합니다. 다만 PRoot가 남긴 **권한 0000·0바이트 일반 파일**은 설정 없는 bind placeholder로 구분해 자동 DNS를 연결하며, 그 파일을 삭제하거나 수정하지 않습니다. symlink, 읽을 수 있는 빈 파일, 내용 있는 권한 제한 파일과 정보를 확인할 수 없는 기존 경로는 사용자 설정으로 보존합니다.
네트워크나 DNS가 없어도 데스크톱·편집기·로컬 파일 작업은 사용할 수 있으며, 외부 주소의 이름 조회는 실패할 수 있습니다.
Android의 **Private DNS·VPN** 설정에 따른 연결과 이름 조회는 Y900에서 별도로 확인해야 합니다. Android가 제공한 DNS 주소를 받는 것만으로 해당 기기의 Private DNS·VPN 동작까지 검증한 것은 아닙니다.

## 입력 우선권과 태블릿 전환

키보드 입력 우선권은 **메뉴 → 설정** → **실사용 준비 · 권한/진단**에서 연결 상태를 확인합니다. 접근성 서비스는 데스크톱에 포커스가 있을 때 전달된 키를 정책에 따라 처리하고, 다른 Android 앱에서는 지원되는 데스크톱 복귀 단축키만 처리합니다. 모든 OEM 예약 단축키를 회수한다고 보장하지 않습니다.

트랙패드·마우스로 이동, 클릭·드래그, 스크롤을 사용하고 **설정**에서 속도와 자연 스크롤을 조절합니다.
자연 스크롤 방향은 Loopy의 Android 입력 설정에서 한 번 적용합니다. Linux Sway 쪽 자연 스크롤은 꺼 두어 방향을 다시 뒤집지 않습니다.
다중 접점 제스처는 Android가 실제 접점을 전달할 때만 동작합니다.
Android 13 이하에는 접근성 모션 소스 API가 없으며, Android 14 이상에서도 raw 접점 수신은 기기마다 다릅니다.
Android가 만든 마우스 이벤트, raw 트랙패드 접점, 포인터 캡처의 상대 이동은 서로 다른 입력 경로입니다. 전체 화면의 물리 마우스에서는 상대 이동 캡처를 요청하며, raw 트랙패드를 마우스로 취급해 캡처하지 않습니다. 캡처된 마우스는 Linux 포인터로 조작합니다. 네 가장자리·모서리 클릭과 드래그, 실제 캡처 허용 여부는 Y900에서 별도로 확인해야 합니다.

**메뉴 → Android로 돌아가기**를 선택하면 Linux 화면과 입력 소유권을 반납하고 Android로 돌아갑니다.
설정의 **자동** 모드는 물리 키보드 또는 포인터가 있는 상태와 없는 상태 사이에서 전환합니다. 장치 정보 갱신이나 마우스 캡처에 따른 입력 source 변경은 Ctrl+Alt+Esc로 반납한 상태를 다시 덮어쓰지 않습니다. 모든 키보드·포인터를 분리한 뒤 하나를 다시 연결하면 새 연결로 데스크톱에 진입합니다.
마우스 분리·캡처 해제에서는 포인터만 반납하고 다른 키보드의 Ctrl/Shift는 유지합니다. 키보드를 분리하면 해당 장치의 키만 해제하며, 실제 포커스 상실·화면 해제·태블릿 전환에서는 전체 입력을 반납합니다. Linux 세션은 유지하므로 다시 들어오면 기존 창을 사용합니다.
마우스의 뒤로·앞으로 버튼과 숫자 키패드도 전달합니다. guest NumLock은 처음에 꺼져 있으며 NumLock 키로 토글합니다. 외부 키보드의 Android meta/LED 초기 상태와 자동으로 맞추는 기능은 아직 없습니다.
Linux 프로세스를 끝내려면 **세션 종료**를 누릅니다. Android 강제 종료나 메모리 회수 뒤의 미저장 상태 복원은 지원하지 않습니다.

## 터치·배율·Linux 전용 사용

전체 화면의 오른쪽 아래 **메뉴**는 키보드·마우스 없이도 열 수 있다. 한 손가락 탭은 클릭, 끌기는 드래그, 두 손가락 끌기는 스크롤, 두 손가락 탭은 우클릭이다. 터치 스크롤은 손가락을 따라가며 마우스 자연 스크롤 설정과 별도로 처리한다. **메뉴 → 창 조작**에서 창 목록·작업공간·포커스·크기·전체 화면을 조절한다.

**메뉴 → 설정 → 화면 배율**은 100/125/150/175/200% 중 선택하고 저장한다. Y900 13의 고해상도 화면은 150~175%부터 실제 글자·포인터 위치를 확인한다. 배율이나 화면 키보드 표시로 창 크기가 바뀌어도 같은 Linux 세션을 유지한다. Android IME의 한글 조합·확정·삭제·Enter는 순서대로 전달하며, 총 **64KiB**는 Android 입력 정책의 크기 상한이다. 활성 Wayland 입력 필드에는 확정 문자열을 직접 전달하고, UTF-8 4,000바이트를 넘는 요청은 문자 경계를 지켜 내부 분할한다. Wayland 문자열 입력을 지원하지 않는 앱의 가상 키보드 대체 경로에는 세션 동안 서로 다른 문자 기호를 **최대 4,073개** 추가할 수 있다. 이 용량 초과나 잘못된 Unicode를 포함한 작업은 삭제·문자 전송 전에 거절한다. 일부 입력이 적용된 오류는 자동 재전송하지 않으므로 현재 창을 확인한다. GTK 앱에서 기본 입력 모듈을 바꾸면 가상 키보드 대체 경로를 사용할 수 있다. 다른 Linux IME가 입력을 점유하면 오류 안내를 확인하고 점유를 해제해야 한다. 실제 전달 성공·속도·Unicode 범위는 사용하는 앱과 기기에서 별도로 확인한다. 물리 키 이벤트와 클립보드 전달은 별도 경로다.

**메뉴 → Linux 전용 · 화면 고정**에서 Android 화면 고정이 꺼져 있으면 **Android 화면 고정 설정**으로 먼저 켠다. 앱이 설정을 자동 변경하지 않는다. **시작**을 누르면 Android 확인 화면을 연다. 허용하면 Home·최근 앱의 우발적 전환을 제한한다. **Ctrl+Alt+Esc** 또는 **메뉴 → Android로 돌아가기**로 해제한다. 입력 장치가 끊겨도 터치 메뉴를 유지한다. 사용자가 Android 자체 고정 해제 동작으로 나간 뒤 자동으로 다시 고정하지 않는다. 허용된 관리 기기에서는 Lock task를 사용할 수 있지만 이 앱이 개인 기기를 임의로 Device Owner로 등록하지 않는다. Android의 시스템 해제·전원·OEM 예약 키까지 완전히 차단하는 OS 기능은 아니다.

## 원격 Linux 연결 · SSH

**메뉴 → 원격 연결 · SSH** 또는 Linux 앱 메뉴의 **Remote connections · SSH**에서 주소·사용자·포트를 입력한다. foot 터미널의 실제 OpenSSH 클라이언트가 연결한다. 처음 보는 서버의 호스트 키는 터미널에서 fingerprint를 확인하고 승인한다. 바뀐 키를 자동으로 무시하지 않는다. 비밀번호는 터미널에서 입력하며 연결 화면의 최근 항목에는 주소·사용자·포트만 저장한다. 키와 known_hosts는 Linux 홈의 일반 OpenSSH 경로를 사용한다.

연결이 끊기면 터미널의 오류를 확인하고 최근 주소로 다시 연결한다. keepalive로 끊긴 연결을 감지하지만 원격 프로그램의 메모리를 자동 복구하지 않는다. 원격의 작업을 유지하려면 해당 서버의 tmux 등 세션을 사용한다. `ssh`·`scp`·`sftp`·`ssh-keygen`이 포함된다. SSH는 접속용 클라이언트다. **메뉴 → 원격 화면 · RDP/VNC** 또는 SSH 창의 같은 버튼에서 다른 컴퓨터의 화면에 접속할 수 있다. RDP는 기본3389, VNC는 기본5900이며 서버가 실제로 사용하는 포트를 입력한다. VNC의 `:1` display 번호 대신5901처럼 포트를 사용한다. 사용자·인증·서버 인증서는 Remmina 창에서 확인한다. 원격 창 안의 입력도 기존 Wayland 경로를 사용하고 Ctrl+Alt+Esc는 Android 입력 반납에 예약된다. [원격 화면 사용법](remote-desktop.md). 태블릿으로 들어오는 서버는 포함하지 않는다.

## 화면 출력과 GPU

**실사용 준비 · 권한/진단**의 **화면 렌더러**에서 현재 Android 출력 경로를 확인합니다. **OpenGL ES**는 GLES 출력 경로와 GL 제공자·렌더러 이름을 표시합니다. 출력 초기화가 실패하면 **CPU**로 표시하고, 화면이 분리된 동안에는 화면 연결 대기로 표시합니다.

이 GLES 경로는 Linux가 만든 화면을 Android Surface에 표시하는 데 사용합니다. 새 세션에서 Mesa 픽셀 검사를 실행하고 **llvmpipe → softpipe → Cairo**를 선택합니다. Sway·WebKit의 기본 출력은 pixman/Cairo입니다. 데스크톱 메뉴 **GPU alternatives / check**에서 CPU OpenGL 창과 조건부 VirGL 창을 검사할 수 있습니다. OpenGL 창 초기화 실패는 Cairo 안내 창으로 내려가며 현재 세션은 유지됩니다.

터미널의 `loopy-gl <프로그램> [인수]`는 해당 세션에서 확인된 CPU GL을 적용합니다. `loopy-gl --virgl <프로그램> [인수]`는 실제 VirGL 픽셀 검사와 살아 있는 소켓이 있어야 시작하며, 현재 한 앱씩 사용하는 선택 검사 경로입니다. GTK Wayland proxy 창에는 GLES 프로필을 선택하며, 기본 데스크톱·브라우저를 일괄 VirGL로 바꾸지 않습니다. 최신 VM에서는 proxy readback과 실제 창의 Android Surface 표시를 검사합니다. VirGL 실패·직접 드라이버 부재는 기본 CPU 데스크톱을 막지 않습니다. 재검사는 현재 앱을 재시작하지 않으며 기본 경로는 다음 세션 시작에서 결정됩니다.

**실사용 준비 · 권한/진단 → 대체 방법**에서 물리 키보드 설정·현재 입력기 선택·접근성 설정을 열 수 있습니다. Meta/Win 예약 키가 막히면 기본 Ctrl+Alt 또는 화면 버튼을 사용하고, 원시 접점이 없는 트랙패드는 일반 이동·클릭·스크롤로 계속 사용합니다. ADB·Shizuku·root·관리 기기는 각각 별도 조건과 backend가 필요한 경로로 안내합니다.

고급 안내의 **실험적 X11 · Termux**는 별도 Termux:X11 화면과 i3를 사용했던 중단된 후보이며 **Wayland 세션 아님**을 명시합니다. 일반 메뉴·설정·홈의 별도 실행 항목에서 제외했고, 기본 데스크톱을 쓰기 위해 설치하거나 실행할 필요가 없습니다. [실험 기록](native-termux-validation.md)은 소스와 실패·부분 검증의 이력으로 보존합니다.

별도의 **Termux native Wayland** 후보는 공식 [Sway 패키지](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/sway/build.sh)와 [wlroots Termux:GUI backend](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/wlroots/0003-impl-termux-gui-backend.patch)를 사용합니다. 소스의 실행 backend는 `WLR_BACKENDS=tgui`, 출력 수는 `WLR_TGUI_OUTPUTS=1`이며 Termux:X11/i3와 다른 경로입니다. 현재 Loopy에는 미통합입니다. 호환되는 Termux:GUI 플러그인·서명, 실제 Wayland 클라이언트 화면과 키보드·마우스, GPU import와 기기 지원을 각각 검증해야 하며 환경변수 설정만으로 가속이나 실사용 성공을 인정하지 않습니다.

VM의 GLES·llvmpipe 성공은 실제 GPU 사용이나 성능을 증명하지 않습니다. [대체 경로와 검증](capability-fallback-validation.md), [GPU 방법 전체](research/guest-gpu-alternatives.md), [입력·권한 방법 전체](research/android-authority-alternatives.md), [Y900 점검표](y900-test-checklist.md)에서 실제 지원 조건과 미검증 범위를 구분합니다.

## 복사와 공유 파일

Mousepad 등 GUI 앱에서는 Ctrl+C/Ctrl+V, foot에서는 Ctrl+Shift+C/Ctrl+Shift+V를 사용합니다.
Android와 Linux 사이에는 한글·이모지를 포함한 64KiB 이하 텍스트 클립보드를 연결합니다.
비우기도 전달하며 URI·이미지 클립보드는 지원 범위가 아닙니다. Android 클립보드는 앱 창에 포커스가 있을 때 접근합니다.

Thunar에서 `/mnt/shared`를 엽니다. Android에서는 **메뉴 → 앱** → **공유 파일 · Android**를 선택하고 문서 선택기의 **Loopy 공유 파일**을 사용합니다.
두 경로는 같은 파일을 보여 줍니다. Android 문서 앱이 없으면 공유 파일 선택 화면을 열 수 없습니다.
코드는 `/root/Projects`에 저장하면 됩니다. 앱 메뉴의 **Code IDE · Geany**는 예제 `hello.py`를 열며, 수정한 코드는 이 폴더에 저장할 수 있습니다.
Android와 주고받거나 다른 Android 앱에서 문서 제공자로 열 파일은 `/mnt/shared`에 저장하세요. Geany에서 해당 경로를 열고 저장하면 Android의 **Loopy 공유 파일**에서도 같은 파일을 볼 수 있습니다.

## Y900 13 (TB522FU)과 OS 경로

대상은 Lenovo 공식 사양의 **TB522FU · Snapdragon 8 Elite · Android 16 · 3840×2560**이다. 실제 연결 시 `dev/device-check --serial SERIAL --expect-manufacturer lenovo --expect-model TB522FU`로 모델을 먼저 확인한다. 이전 TB570 계열 OEM 설정 변경 도구를 이 모델에 적용하지 않는다. 예약 키는 기본 Ctrl+Alt, 선택적 입력 우선권, Linux 화면 고정부터 사용한다.

직접 evdev/libinput·DRM/KMS를 소유하는 native Linux OS를 최종 후보로 두되 동일 보드의 kernel/DTB/display/GPU/power 드라이버와 복구 경로가 필요하다. 현재 공개 recovery tree는 커널을 포함하는 OS 포트가 아니다. [모델별 OS 경로와 확보 조건](research/loopy-os-paths.md)에 조사 결과를 기록했다.

현재 Linux 환경은 Alpine/Sway입니다. Omarchy 원본 Arch/Hyprland의 모든 기능·Linux 앱 3D/GPU 가속·Linux 오디오와 알림 브리지를 제공하지 않으며, 기기별 지연·전력·OEM 입력 성능은 실기기에서 확인해야 합니다.
