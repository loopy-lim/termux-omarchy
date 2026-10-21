# Y90013 Wayland · 남은 작업 검증

2026-10-06. 기본은 Android 네이티브 Wayland 호스트와 Alpine/Sway이며 Termux/X11 경로로 바꾸지 않았다. 물리 TB522FU는 연결되지 않았다.

## 이번에 구현한 동작

- Android 메뉴와 SSH 창에서 GTK3 Wayland **원격 화면 · RDP/VNC**로 진입한다. Remmina1.4.40과31개 추가 의존성을 기존 고정 index로 검증해 총293개 패키지를 잠갔다. endpoint만0600 파일에 저장하며 비밀번호 저장·클립보드·폴더 공유는 기본으로 끈다. [사용법](remote-desktop.md), [패키지 확장 영수증](../build/diagnostics/remote-desktop-lock/receipt.json).
- Android EGL1.4에서 surfaceless extension이 없는 경우 각 bootstrap/renderer/fence context가 독립1×1 pbuffer를 소유한다. 생성·current·unbind·destroy와 실패 정리를 실행형 C 검사로 확인한다. GLES3.2를 초과하는 데스크톱 GL 버전 요청은 드라이버 호출 전에 거절한다.
- VirGL helper의16KiB LOAD와 RELRO 정렬을 함께 수정·검사한다. Android crash reporter를 유지하고 생성한 vtest server 소스도 build receipt에 기록한다. 이것은 ELF 패키징 증거이며 실제16KiB kernel 실행은 미검증이다.
- 원래 태블릿 기능인 전체 화면/입력 반납, 연결·분리 정책, 숫자 키패드·보조 버튼·터치, 한글 IME, 배율·화면 고정, 공유 문서·SSH는 전체 회귀 검사 대상이다.

## GPU 결과의 경계

[초기 pbuffer 후보](validation/2026-10-06-remaining-virgl-third-vm/receipt.json)는 bootstrap GLES3.1까지 성공했으나 게스트 연결은 실패했다. [Android native crash log](../build/diagnostics/remaining-virgl-third-native-log.txt)는 앱 UID10224의 helper가 GLES4.6 요청을 드라이버에 넘긴 뒤 emulator EGL 오류 출력에서 SIGSEGV를 일으킨 것을 확인한다. PC를 당시 후보의 unstripped helper에 대조해 `loopy_egl_create → virgl_egl_create_context → vrend_renderer_init` 호출을 확인했다. 잘못된 GLES 요청을 거절한 [후속 픽셀 검사](validation/2026-10-06-remaining-virgl-fourth-vm/receipt.json)에서는 **virpipe ready·실제 offscreen pixelVerified=true**가 됐다.

[기본 GTK proxy 창의 실패](validation/2026-10-06-remaining-virgl-window-vm/receipt.json)는 **Unable to create a GL context**로 Cairo 안내에 내려갔다. [GTK3.24.49의 공식 Wayland GL 구현](https://github.com/GNOME/gtk/blob/3.24.49/gdk/wayland/gdkglcontext-wayland.c)은 공유 context를 기본 OpenGL 프로필로 먼저 만들며 `GDK_GL=gles`로 GLES를 선택할 수 있다. [GLES 프로필 대조](validation/2026-10-06-remaining-virgl-gdk-es-vm/receipt.json)는 실제 **virgl GTK readback RGBA51/102/153/255와 Android Surface `ff336699`**을 확인했다. 실행 PID15768·UID10224이고 shader version을 허위로 올리지 않았다.

검증된 수동 proxy 실행에만 `GDK_GL=gles`를 유지하도록 제품에 반영했다. 기본 Sway/WebKit의 `GDK_GL=disable`은 유지한다. 최종 전체 시험은 시험용 override 없이 실제 제품 wrapper의 VirGL 창 표시를 다시 확인했다. 실패 경로에서는 명시적인 Cairo fallback과 같은 Linux 세션을 요구하며, fallback 통과를 GPU 창 성공으로 표시하지 않는다. VirGL 종료 로그의 Mesa resource 명령 오류도 보존한다. 일반3D·shader/texture/depth·다중 창·연속 frame 성능 수락은 아직 남는다.

VM은 Android16 ARM64, 앱 UID10224, `untrusted_app`, **SwiftShader·4096B kernel page**다. Adreno830 하드웨어·성능·전력·실제16KiB 런타임의 증거가 아니다. 기본 Sway/WebKit 렌더는 CPU/pixman/Cairo이고 Android 화면 합성은 GLES 실패 시 CPU로 복귀한다. VirGL은 선택 검사 경로이며 기본 세션을 가속 세션으로 변경하지 않는다.

## 원격 검증의 경계

[실제 VNC 왕복](validation/2026-10-06-remaining-vnc-second-vm/receipt.json)은 일반 앱 UID의 Remmina가 독립 RFB3.8 loopback counterpart에서 RGB51/102/153을 받고 Android Surface에 `ff336699`로 표시한 결과다. 상대는 A와 Enter의 down/up, 포인터 좌표 및 왼쪽 클릭 down/up을 각각 확인했다. 최종 전체 시험의 동일 케이스에서 최종 APK를 다시 검사했고 통과했다.

counterpart는 인증 없는 시험 전용 local 서버다. 실제 네트워크·서버 비밀번호/키·TLS·RDP 인증·물리 키보드/마우스·하드웨어 디코드는 남아 있다. 태블릿을 원격 서버로 공개하는 기능은 미구현이다.

## 최종 산출물과 검사

최종 APK는 **335,291,732B**이며 SHA-256은 `88303384ee1353f922d2a96f29eeeab916ca65291b0135844122fe89b54c5ba0`다. rootfs SHA는 `e3337346fb59b99228c71572f5e89911bde8492d4b0c35b099e5fcf6bf4cd3fd`다. **호스트504개·네이티브49개·최종 Android VM49/49개, 실패0**을 확인했다. 전체 VM에서는 시험용 GLES override를 사용하지 않고 제품 wrapper의 실제 VirGL GTK readback과 Android Surface 색상 `ff336699`가 통과했다. 실제 VNC 화면·A/Enter·포인터 클릭 왕복도 같은 APK에서 다시 통과했다. VM의 immersive/pin 설정과 소유 SSH fixture의 포트·listener·worker 정리가 완료됐다.

- [전달 APK](../build/deliverables/LoopyDesktop-2026-10-06-y90013-wayland-remote-arm64.apk), [전달 영수증](validation/2026-10-06-remaining-work/delivery.json)
- [전체 VM49 결과](validation/2026-10-06-remaining-final-second-vm/receipt.json), [호스트504 로그](validation/2026-10-06-remaining-work/host-tests-release.txt), [네이티브49 로그](validation/2026-10-06-remaining-work/native-tests.txt)
- [현재 입력·payload 무결성](validation/2026-10-06-remaining-work/integrity-final.json), [독립 package/source/ELF 감사](validation/2026-10-06-remaining-work/independent-final-package.json), [로컬 코드 크기 검사](validation/2026-10-06-remaining-work/code-size-release.txt)

독립 감사는 APK 입력113개, Wayland source28개, runtime3개, PRoot source4개·upstream824개, VirGL 생성파일6개, 고정 패키지293개와 실제 APK native5개·asset7개를 대조했다. 모든 고정 SHA와 파일 크기·ELF LOAD/RELRO 조건이 맞았고 종료 시 같은 파일을 다시 확인했다. 외부 primary source를 보존한 validation 기록은 로컬500줄 모듈 제한에서 제외하지만 제품 코드와 tests의 제한은 유지하며 최대499줄이다. 이전 [APK24](../build/deliverables/LoopyDesktop-2026-10-06-y90013-wayland-arm64.apk)와 영수증은 보존하며 새 APK 결과로 재사용하지 않는다.

호스트 전체 검사 중 macOS가 이미 종료된 zombie만 남은 자식 그룹에 EPERM을 반환한 경우를10번 재현했다. 환경 밖 실행에서도 같은 결과였다. 종료 정리는 leader 종료와 group 소멸을 모두 확인한 경우만 처리하고, live leader/descendant의 권한 실패는 유지한다. [실제 자식·후손·외부 그룹 보존 검사](validation/2026-10-06-remaining-work/exit-group-green.txt), [최종 호스트504개](validation/2026-10-06-remaining-work/host-tests-release.txt). 중단된 Termux 실험의 출력 제한 helper 유지보수이며 Wayland를 X11로 변경하지 않는다.

## 저장 공간과 OS

오래된 Gradle9.4.1 transforms **2,826,264,576B**만 추가 제거했다. [계획](validation/2026-10-06-remaining-work/cache-plan.json), [실제 정리](validation/2026-10-06-remaining-work/cache-cleanup.json). 별도로 작업 소유 VM의 이전 rootfs 캐시 하나를 제거했으며 현재 이미지·기존 전달 APK·Linux 홈·설정·공유 파일을 보존했다. [전후 검증](validation/2026-10-06-remaining-work/owned-vm-cache-cleanup.json). 새 GLES 프로필 이미지의 설치 공간으로 이전 APK24의 작업 VM 캐시 **913,911,808B**를 추가로 정리했다. [실제 정리와 보호 데이터 전후 일치](validation/2026-10-06-remaining-work/owned-vm-cache-cleanup-third.json). 처음 정리는 mode000인 옛 mount placeholder의 `du` 거절로 삭제 전 중단했고 [실패 영수증](validation/2026-10-06-remaining-work/owned-vm-cache-cleanup-second.json)을 보존했다. 후속 정리는 앱 프로세스0·캐시 marker/UID·실제 디렉터리를 확인하고 해당 옛 placeholder만 읽을 수 있게 한 뒤 제거했다. 기존 APK24 파일·현재 캐시·홈·설정·공유 파일의 SHA/manifest는 동일하다. 원래 실패 로그와 사용자 데이터를 삭제하지 않았다.

[TB522FU OS 조사](research/loopy-os-paths.md)는 공개 kernel 및 Qualcomm graphics/display 모듈을 추가로 확인하고 commit/파일 SHA를 고정했다. 보드 DTB/DTBO·일치하는 firmware·패널/입력·충전/절전·복구 경로와 재현 빌드는 아직 확보·검증하지 못했다. Android ROM, native Linux OS 이미지, 부팅·플래시는 완료하지 않았다.

실기기가 연결되면 `./dev/device-check --serial 정확한값 --expect-manufacturer lenovo --expect-model TB522FU`의 읽기 전용 수집부터 시작한다. [Y900 점검표](y900-test-checklist.md)에 USB/BT·OEM 키·NumLock 초기 동기화·펜 pressure/tilt·실제 remote 인증·GPU·절전·열/전력을 남겼다. 펜 전용 입력·Linux 오디오/알림 bridge·임의 Android 예약 키 회수도 미구현/미수락이다.

작업 소유 emulator-5582는 종료했고 ADB에서 serial 부재를 확인했다. AVD 데이터는 보존했다. [종료 영수증](validation/2026-10-06-remaining-work/vm-cleanup.json).
