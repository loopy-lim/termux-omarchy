# 브라우저·코드·터치패드 확장

사용자가 기존 배포를 기준으로 나머지 기능, 특히 브라우저·코드 편집기·터치패드를 계속 구현하라고 승인했다. Y900 연결은 추후이며 이번에는 소유한 ARM64 Android VM에서 검증한다.

- Linux GUI 브라우저는 공식 Alpine ARM64 Firefox ESR, 코드 편집기는 GTK/Wayland Geany를 추가한다. Neovim과 Mousepad도 유지한다. 패키지 존재만으로 실행 합격을 선언하지 않는다.
- `.desktop` 앱 검색을 추가하되 제한된 파일 크기·경로·실행 파일과 argv를 사용한다. 문자열을 셸에서 평가하지 않는다.
- 영속 HOME 업데이트 시 이전 기본 Sway 설정과 정확히 일치할 때만 갱신한다. 사용자 변경과 프로젝트 파일은 덮어쓰지 않는다.
- 터치패드 POSITION 접점은 touch/generic/captured 모든 실제 진입 경로에서 처리한다. Android가 분류한 두 손가락 스크롤을 원시 접점과 중복 처리하지 않는다. 포인터 캡처의 SOURCE_MOUSE_RELATIVE/AXIS_X/Y를 처리하고 캡처 경로의 관성도 이어간다.
- 브라우저는 실제 Linux HTTP 서버의 페이지와 JavaScript, 키보드 입력·폼 제출, 창 PID·Surface 변화로 검증한다. 코드 편집기는 공유 파일을 GUI에서 수정·저장하고 Python으로 실행한다.
- 원시 터치패드의 Android generic 전달은 프레임워크 주입·GTK 폴더 이동으로 검증한다. 캡처 콜백의 두 손가락 스크롤은 Linux 브라우저의 실제 scroll 이벤트와 픽셀 변화로 검증한다. VM의 합성 입력과 실제 Y900 입력은 별도 증거다.
- 전체 회귀검사와 500행 제한을 확인하고, 기존 배포 APK를 보존한 새 이름의 APK·해시·한국어 안내를 납품한다.

GPU 가속, Linux 오디오·알림 브리지, Omarchy 원본 Arch/Hyprland와의 동등성은 이 확장의 완료 주장에 포함하지 않는다. PRoot에서 Firefox 보안 격리나 실행이 막히면 실제 오류를 먼저 기록하고, 검증 없이 sandbox를 해제하지 않는다.

## 2026-10-06 브라우저 선택 변경

Firefox 후보의 일반 앱 전체 검사는 16/19이며 브라우저 세 검사는 정상 창 시작 단계에서 실패했다. 이를 보존하고 공식 Alpine WebKitGTK 2.48.1-r1에 포함된 GTK3 MiniBrowser로 실행 경로를 변경한다. 별도 `run-as` 진단에서 실제 HTML·JavaScript·키보드 입력·페이지 스크롤이 동작했다. 이 진단은 Seccomp 0·`runas_app`이므로 일반 앱 수락을 대신하지 않는다.

MiniBrowser는 기본 Linux 프로세스 sandbox를 켜지 않으며, 켜는 비교는 bubblewrap 접근 제한으로 실패했다. 제품은 표준 Android 앱 UID·SELinux·상속 seccomp 범위에서 실행한다. 추가 Linux 브라우저 sandbox를 제공한다고 주장하지 않는다. 전역 정책이나 Firefox sandbox를 바꾸지 않고 브라우저의 CPU Wayland 설정만 별도 실행 스크립트에 둔다. 새 APK에서 HTML·JavaScript·폼·HTTPS·합성 캡처 스크롤, 실제 worker UID·Android 정책을 다시 확인한다. 사용자 HOME와 Firefox의 기존 프로필도 삭제하지 않는다.

## 2026-10-06 최종 GTK 브라우저와 DNS 수정

MiniBrowser의 일반 앱 폼 시험에서 첫 글자 keydown이 DOM에 도달하지 않는 문제를 기록했다. Android 라우터 출력·DOM 포커스·down/up 추적을 대조했고 GTK3 WebKit의 비동기 fallback을 가능한 원인으로 좁혔다. GTK 창에서 주소창·탭 단축키를 기본 WebView 처리 전에 처리하는 Loopy Browser로 변경했다. Notebook 탭 변경 뒤 주소·제목 갱신도 연결했다. HTTP·JS·완전한 첫 글자 입력·탭 복귀·Geany 저장/실행·합성 터치패드 탭/스크롤은 d318 APK의 18/19 전체 시험에서 통과했다.

남은 HTTPS 실패는 PRoot의 빈 mode-000 파일을 사용자 resolver로 오인한 문제였다. 해당 파일 바인드 표식만 자동 DNS 대상으로 구분한다. 기존 DNS 내용·symlink·읽을 수 있는 빈 파일은 보존하고 파일을 삭제하거나 수정하지 않는다. 공개 DNS나 TLS 검증 해제를 추가하지 않는다. 호스트 회귀 RED→GREEN, 새 9605 APK의 일반 앱 HTTPS 1/1을 확인했고 같은 APK 전체19도 모두 통과했다. 실제 전달 APK는 `build/deliverables/LoopyDesktop-2026-10-06-apps-arm64.apk`이며 입력·포함 파일·서명·원본과 byte/hash 동일성을 대조했다. 이전 Firefox/MiniBrowser 실패·18/19와 최종 결과는 각각 별도 폴더로 보존한다.

실제 화면 점검에서 탭 제목이 `…`로만 잘리는 현상을 확인해 최소 14글자 폭을 설정했다. 이 최종 UI 빌드 `81d5e4d50e870c825a581c08c3e34df8b8a6ccde542f2c4af954c2b94488bccd`도 일반 앱 전체19·호스트140을 모두 통과했다. 최종 전달 파일은 `build/deliverables/LoopyDesktop-2026-10-06-desktop-apps-arm64.apk`다. 앞선 9605 빌드와19/19도 보존하며 최종 화면과 별도로 구분한다. 화면용 Geany는 `--no-session`으로 시험에서 삭제한 파일을 복원하는 경고를 피하고, 사용자 HOME·프로필은 지우지 않는다.
