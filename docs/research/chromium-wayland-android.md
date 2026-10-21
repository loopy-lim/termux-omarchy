# Y900의 Linux Chromium·Wayland 실행 경계

확인일: 2026-10-08. 대상은 Android 16의 Lenovo Y900 `TB522FU`,
`Y900`와 일반 앱 `dev.loopy.desktop`의 Omarchy 환경이다. 이 조사에서
기기 실행·설치·설정·프로필 변경은 하지 않았다. 아래 실기기 결과는 기존
진단 파일의 결과이며, 이번 소스 변경의 실기기 합격을 뜻하지 않는다.

## 적용한 실행 호환성 수정

원본 `omarchy-launch-browser`는 브라우저 선택, private flag 판별, 기존
브라우저 handoff, 새 창 실행, Hyprland focus를 수행한다. 새 창 실행은
`systemd-run --user` 아래에서 `uwsm-app --`를 호출한다. 기존 Android 변환은
UWSM만 바꿔 systemd 사용자 서비스가 없는 세션에서도 바깥 래퍼를 남겼다.

[OmarchyAppLaunchFiles](../../android/src/dev/loopy/desktop/OmarchyAppLaunchFiles.java)는
기존 SHA-256 manifest의 원본 검사 뒤, 브라우저의 정확한 3행 실행 접두부를
한 번만 찾아 `loopy-app-launch --`로 바꾼다. 원본 파일은 읽기만 한다.
검사 대상 원본 SHA-256은
`2f4a3a94dd10faa964c9337770bdfde4be7dd50912121ca702b673117f465892`이다.
원본 입력은 기존 262144바이트 상한과 일반 파일·실경로 검사에 따르고,
실행 구문이 없거나 여러 개면 실패한다. 브라우저나 샌드박스 인자를 추가하지
않으며, 다른 caller는 기존 UWSM 변환을 그대로 쓴다. 파생 artifact bytes는
기존 bridge directory 버전에 반영되어 이전 bridge 파일을 덮어쓰지 않는다.

[실행 회귀 테스트](../../tests/test_omarchy_app_launch.py)는 실제 Java 파생 코드와
원본 브라우저 스크립트를 실행한다. Chromium·Firefox·Edge의 private 인자,
명령 치환 문자가 포함된 URL의 argv, handoff 성공 때 중복 실행 방지,
원본 focus 처리를 확인한다. systemd가 사용할 수 없는 fixture에서 원본
브라우저 명령이 실행되지 않는 RED를 관찰한 뒤 수정으로 GREEN을 확인했다.
변경된 원본 hash와 없는 실행 구문도 거절한다.

## 샌드박스와 화면 출력은 별도 조건

Chromium Linux의 [zygote 초기화 소스](https://raw.githubusercontent.com/chromium/chromium/main/content/browser/zygote_host/zygote_host_impl_linux.cc)는
새 사용자 네임스페이스를 만들 수 있으면 namespace sandbox를 선택하고,
그렇지 않으면 유효한 SUID helper를 선택한다. 두 경로를 모두 사용할 수 없으면
시작을 중단한다. `--disable-setuid-sandbox`는 다른 보안 경계를 제공하는
인자가 아니다. [Linux sandbox 문서](https://chromium.googlesource.com/chromium/src/+/main/sandbox/linux/README.md)는
권한을 가진 helper가 PID·network namespace와 chroot를 설정하고 권한을
내린다고 설명한다. [SUID 설치 문서](https://chromium.googlesource.com/chromium/src/+/main/docs/linux/suid_sandbox_development.md)는
실제 root 소유와 4755 mode를 요구한다. PRoot의 가상 소유권은 그 권한을
주지 않으며, guest의 root 표시를 바꿔도 이 문제는 해결되지 않는다.

[Ozone 문서](https://chromium.googlesource.com/chromium/src/+/main/docs/ozone_overview.md)에서
Wayland는 입력과 화면 출력 플랫폼이다. `--ozone-platform=wayland`는 컴파일된
backend를 선택한다. 따라서 Wayland 선택이 namespace/SUID 조건을 해결하지
않는다는 결론은 두 공식 소스 경로를 함께 읽은 해석이다.

## 현재 진단 증거

Omarchy rootfs archive SHA-256은
`7dcc1b5382007da2ef2a52d503ee646bdf863f00b45ad65098f8435d9689fd86`이고,
Omarchy commit은 `81145eb1fd41532fcae4310b26f860608e2eaf82`이다.
기존 Arch 진단은 APK
`5ab2934c9775f50ba8602bc426db2e86304de6740e9e2f1e1d9cf21e7919c41b`
아래에서 실행됐다. 이 APK hash를 이번 수정 후보와 혼동해서는 안 된다.

| 경로 | 관찰 | 입증 범위 |
| --- | --- | --- |
| Arch Linux ARM Chromium 153.0.8010.36, 기본 sandbox | [기존 DNS/browser 진단](../../build/diagnostics/y900-performance-20261007/browser-dns.json)에 SUID helper root 소유·4755 조건 오류 | 현재 설치 경로의 기본 sandbox 시작 실패 |
| 같은 Chromium, SUID만 비활성 | [기존 sandbox 진단](../../build/diagnostics/y900-performance-20261007/chromium-sandbox.json)에 `No usable sandbox`, 약 1.05초 후 중단 | 사용자 namespace 대안도 usable하지 않음 |
| 같은 Chromium, sandbox 비활성 진단 | 같은 파일에서 독립된 빈 profile과 data URL의 DOM 출력, 약 9.25초 | CPU 렌더링 가능성만 입증. 제품용 보안·창·입력·네트워크 합격이 아님 |
| 설치된 Termux Chromium 149, Wayland 지정 | [기존 Termux 진단](../../build/diagnostics/y900-performance-20261007/termux-chromium.json)에 `Invalid ozone platform: wayland`, 약 0.08초 후 중단 | 이 binary에 사용할 Wayland backend가 없음 |
| 같은 Termux Chromium, headless | 같은 파일에서 12초 제한 시간 초과, DOM 없음 | usable browser 실행을 입증하지 못함 |

새로 확인한 [Termux 공식 recipe](https://raw.githubusercontent.com/termux/termux-packages/master/x11-packages/chromium/build.sh)는
X11과 headless를 켜고 Wayland를 끈다. 더 중요한 조건은 recipe가 적용하는
[1001 패치](https://raw.githubusercontent.com/termux/termux-packages/master/x11-packages/chromium-host-tools/cr-patches/1001-chromium-disable-sandbox.patch)다.
이는 Termux ChromeMainDelegate에서 no-sandbox switch를 자동으로 추가하며,
해당 보안 인자의 경고 목록도 바꾼다. [1004 패치](https://raw.githubusercontent.com/termux/termux-packages/master/x11-packages/chromium-host-tools/cr-patches/1004-chromium-headless-disable-sandbox-by-default.patch)도
headless에 no-sandbox를 자동 적용한다. 따라서 launcher argv에 그 인자가
없다는 사실만으로 Termux renderer sandbox가 켜졌다고 판단할 수 없다.
Wayland buildflag만 켜는 재빌드도 이 조건을 해결하지 않는다.
이번에 읽은 upstream branch는 움직일 수 있으므로 원문 6개와 SHA-256을
[primary-sources.json](../../build/diagnostics/chromium-wayland-20261008/primary-sources.json)에 보존했다.

## 다음 경로의 조건

현재 일반 Android 앱·PRoot 환경에서 stock Arch Chromium을 안전하게 시작할
launch flag 조합은 확인하지 못했다. 시작을 막는 검사를 제거하거나
`--no-sandbox`를 기본값으로 넣는 변경은 적용하지 않았다.

| 후보 경로 | 먼저 충족해야 할 조건 | 현재 상태 |
| --- | --- | --- |
| sandbox를 지원하는 실제 Linux 실행 환경 | 실제 non-root browser UID, 커널이 허용하는 namespace 또는 실제 권한을 가진 helper, seccomp 동작, Wayland 연결을 각각 확인 | root/container/kernel 권한 조건이 필요한 별도 환경. 이 기기에서 검증하지 않음 |
| 완전한 Linux VM 안에서 Chromium·Wayland 실행 | guest 커널 sandbox, 화면·입력·클립보드 전달, 가속 가능 여부와 시작 시간 측정 | 설계 후보. Y900의 사용 가능한 VM 권한·가속 및 성능 미검증 |
| Android isolated service 기반 Chromium 포트 | Linux zygote launcher를 renderer별 Android service와 제한된 IPC/broker로 연결하고 보안 경계를 검증 | 대규모 별도 포트. 단순 manifest 변경이나 Wayland flag 변경으로 완료되지 않음 |

마지막 후보에 대한 근거는 Android의 [isolatedProcess service 계약](https://developer.android.com/guide/topics/manifest/service-element#isolated)과
현재 Chromium Linux zygote launcher 구조의 차이다. isolated service는 자체
권한 없이 service API로 통신한다. 이를 Linux renderer launcher 대신 쓰려면
rootfs·library·FD·IPC 제공 경로와 lifecycle을 별도로 구현해야 한다는 판단은
소스에 근거한 설계 추론이며 실행 증거가 아니다.

Android 브라우저 Intent 연동은 사용할 수 있는 별도 플랫폼 통합 경로다.
그 연동 성공은 Omarchy 내부 Linux Chromium·Wayland 사용성 완료로 계산하지
않는다. 이번 변경은 원본 launch transport의 확인된 결함을 고친 범위이고,
안전한 Linux Chromium의 실기기 실행은 아직 남아 있다.
