# Omarchy 내부 Chromium 실행과 태블릿 연결 — 최종 설치 검증

2026-10-08 실제 TB522FU/Y900에 설치한 APK는 `e76bd44f8b5458b4c402774791f1cddaf1bf382328d206f74e7f923e5ba88b0e`다. Chromium 자체를 Ozone Wayland 클라이언트로 실행하는 경로를 사용한다. 일반 샌드박스 웹 사용은 아직 실패한다. Android 앱을 내부 창에 넣는 Shizuku 경로와 Linux Chromium 경로는 별개다.

## 구현과 설치

Android의 브라우저 메뉴는 원본 Omarchy `omarchy-launch-browser`를 호출한다. 원본 기본 브라우저 선택, 기존 브라우저 handoff, private 옵션, literal URL과 포커스 처리를 보존하고, 정확히 고정된 새 실행 구간만 관찰기로 넘긴다. 관찰기는 실제 새 프로세스의 native Wayland 창 또는 실패를 표시한다. 새 실행은 백그라운드로 넘겨 원본 caller의 포커스 처리가 브라우저 종료까지 기다리지 않게 했다.

관찰기는 compositor의 실제 socket peer와 lifetime, 현재 세션의 고정 worker argv·선택된 환경·PID/UID/birth·생존 상태를 검사한다. IPC의 `ok`, exit0, 남은 ready 파일을 새 브라우저 창 준비로 처리하지 않는다. 프로필을 수정·삭제하지 않으며 오류 창을 닫거나 준비 시간이 지나도 브라우저를 종료하지 않는다. 기본 경로가 자동으로 sandbox를 끄거나 Android 앱 전환으로 빠지지는 않는다.

[호스트 GREEN45](../../build/diagnostics/browser-launch-host-green-20261008-03/receipt.json), [최종 source freeze](../../build/diagnostics/browser-launch-source-20261008-03/final03-source/source-freeze.json), [실제 SDK 빌드](../../build/diagnostics/browser-sdk-final-20261008-02/execution-receipt.json), [고정 APK](../../build/deliverables/LoopyDesktop-2026-10-08-browser-startup-inside-arm64/artifact-identity.json), [update12](../../build/diagnostics/y900-android-inside-product-update-20261008-12/receipt.json)를 구분한다. 설정119개와 zsh/tmux2개, UID10330, KeyBridge를 포함한 접근성3개, HOME/ASSISTANT 역할, 마이크 거부를 보존했다. DEX652개에는 Shizuku dependency가 있고 hidden Android stub은 없다. native7개와 canonical inside window/input/wire는 이전 a8ee와 byte-identical이다. APK의 `device_verified:false`는 불변 빌드 영수증의 범위이고 실제 설치·시험은 아래 별도 영수증이다.

독립 검토에서 발견한 포커스 지연, 초기 worker PID 재사용, 종료된 worker 상태의 세 문제는 각각 실제 행동 RED 뒤 수정했다. [RED7/16](../../build/diagnostics/browser-launch-host-red-20261008-02/receipt.json)과 [RED1/2](../../build/diagnostics/browser-launch-host-red-20261008-03/receipt.json)를 보존했다. 최초5bc와 다음c0df SDK 후보는 설치하지 않았다. final03 검토에서 추가 actionable finding은 없었다.

## 현재 APK에서의 실제 시험

| 시험 | 실제 결과와 범위 |
| --- | --- |
| [태블릿 native STOP/START](../../build/diagnostics/y900-shizuku-native-lifecycle-20261008-02/receipt.json) | PASS. 같은 app20544/Hypr20735/Shizuku14779를 유지하고 child20656 종료·reap 후 새 child24785/새 generation으로 재연결. 전역 Shizuku 재시작과 ADB 브로커 시작 명령 없음. |
| [Android 내부 창 product26](../../build/diagnostics/y900-android-inside-product-runs-20261008-01/product26/receipt.json) | PASS. 공개 alias/mode4 앱의 canonical GTK/Cairo draw, F12, 소유 UHID 클릭·스크롤, GTK960×640/Android1920×1280/density320의 같은 geometry/sequence7 draw, CLOSED와 자원 정리. 사용자 Chrome task131/display0 보존. 전체72.10초는 시험 작업 시간이며 입력 지연이 아니다. |
| [실제 Chromium 실패 UI](../../build/diagnostics/y900-browser-native-public-20261008-01/receipt.json) | PASS. 설치한 canonical `browser_launch.run`이 만든 GdkWaylandWindow와 Hyprland native mapped 창을 확인. 실제 child14632 exit-5의 SUID 원인 안내가 표시됐다. 고정 공개 data URL·새 프로필·sandbox 유지. 실제 GTK 안내15.02초 확인 후 자기 창 종료, child wait, 실제 SID 부재, nofollow bounded 정리와 포커스 복귀 확인. 일반 브라우저 실행 성공을 뜻하지 않는다. |
| [Linux Chromium13](../../build/diagnostics/y900-chromium-inside-public-20261008-13/receipt.json) | 정리까지 PASS. 기본 실행은 실제 SUID helper FATAL/exit-5. 공개 오프라인 진단에만 명시적 `--no-sandbox`를 사용해 실제 native Wayland1256×796/PID20655/birth76579080 창 확인. 사용자 프로필과 기본 실행 flags 보존. |
| [별도 app UID user namespace](../../build/diagnostics/y900-chromium-userns-current-20261008-01/receipt.json) | 새 시험 프로세스의 `unshare(CLONE_NEWUSER)`는 -1/EINVAL(22), 생성 실패. 프로세스 종료·reap 확인. 전역 설정 쓰기 없음. 해당 시험 컨텍스트 결과이며 kernel CONFIG 또는 다른 privileged domain의 가능성까지 판정하지 않는다. |

Chromium13의 localhost CDP는 `ANGLE (Mesa, virgl (Adreno (TM) 830), OpenGL ES 3.2 Mesa 26.2.4-arch1.1)`와 GPU compositing·canvas·raster·WebGL enabled를 보고했다. 320×240 공개 canvas의301 RAF/5004.8ms는 약60.142 callbacks/s다. 물리 화면 표시 FPS·입력 지연·60/144fps 수락은 아니다. video decode/encode는 software, Vulkan은 off이며 WebGPU enabled는 기능 시험이 아니다. 모든 공개 창·프로필·TMP·시험 scope를 정리하고121설정·역할·접근성·제품·작업공간/포커스를 보존했다. `gpu_verified`와 `physical_presentation_verified`는 false를 유지한다.

## 실행 가능한 방향과 남은 선택

일반 실행 진입점은 Omarchy 터미널의 `omarchy-launch-browser`와 앱 메뉴의 브라우저다. 현재 환경에서는 샌드박스 실패 안내까지 동작한다. Chromium의 [공식 Linux sandbox 설명](https://chromium.googlesource.com/chromium/src/+/main/sandbox/linux/README.md)은 namespace/SUID/seccomp 경로를 설명한다. 단순 메뉴·DNS 수정으로 현재 SUID 실패를 해결했다고 보지 않는다.

Termux의 [현재 공식 Chromium 빌드 소스](https://github.com/termux/termux-packages/blob/master/x11-packages/chromium/build.sh)는 X11을 활성화하고 Wayland를 비활성화한다. 같은 소스의 sandbox 설명도 Android에서 setuid 사용과 seccomp 적용의 제약을 명시한다. 따라서 기존 Termux 패키지를 복사하는 것만으로 Wayland와 일반 Chromium sandbox가 해결되지는 않는다. 아래는 구현·실기기 수락이 필요한 경로이며 완료된 기능 목록이 아니다.

| 방향 | 현재 근거와 다음 조건 |
| --- | --- |
| 현재 Linux Chromium + Wayland/GPU | 공개 오프라인 진단은 검증됨. 일반 웹에는 실제 sandbox 경로 해결 필요. sandbox 해제를 기본값으로 저장하지 않음. |
| Termux/Bionic 기반 Wayland Chromium | 별도 Wayland 빌드·라이브러리 경계·sandbox·입력 검증 필요. 현재 공식 X11 패키지는 그대로 대체하지 않음. |
| Android Chrome 내부 창 | 현재 Chrome의 alias/mode4 메타데이터는 확인됨. 기존 사용자 task131을 보존해 충돌 이동/삭제를 거부하고 있음. 실제 Chrome 내부 창 수락은 아직 아님. Notion mode2 역시 현재 내부 창 대상이 아님. |
| 로컬 실제 Linux/VM 또는 root/chroot | sandbox에 필요한 실제 권한과 kernel 기능, Y900 부팅·GPU·입력·오디오 지원을 먼저 검증해야 함. OS flash/unlock/wipe는 수행하지 않음. |
| 원격 Linux Chromium을 내부 창으로 연결 | 원격 호스트와 전송·인증·입력/clipboard·지연 검증 필요. 현재 로컬 Wayland/GPU 시험을 원격 기능 수락으로 바꾸지 않음. |

물리 USB 분리·재부팅 자동 연결, 물리 키보드/트랙패드의 장기 사용과 입력 지연,60/144fps, 모든 Omarchy 앱과 Notion 로그인·일반 Chromium 웹 사용은 남아 있다. 이전a8ee/13b/e6 결과는 [이전 연결 검증](2026-10-08-tablet-inside-shizuku.md)과 기존 보고서에 별도로 보존한다.
