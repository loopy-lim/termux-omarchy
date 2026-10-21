# Wayland와 네이티브 입력 · 방향 정정과 검증

사용자가 원한 것은 Wayland 데스크톱과 네이티브 키보드·마우스 사용 경험이다. Termux 사용 허용을 X11/i3로 바꾸어도 된다는 의미로 해석한 것은 잘못이었다. X11 실험은 중단하고, Android 네이티브 Wayland 호스트에 연결한 Sway를 제품의 기본 경로로 유지한다. 실험 소스·설정 복원·실패 기록은 별도로 보존한다.

## 현재 구현

- 앱의 공개 런처는 Loopy Desktop 하나다. 앱 메뉴와 설정에서 X11 경로를 기본 네이티브 데스크톱으로 권하지 않는다.
- Android 물리 키 이벤트를 focused View/pre-IME 및 선택적 접근성 경로에서 받아 evdev key로 JNI와 Wayland `wl_keyboard`에 전달한다. 단축키와 키 해제는 장치별로 관리하며 한글 조합·Android IME 확정 문자는 inner Sway로 전달한다.
- 상대 마우스 입력은 Android가 전달한 모든 배치 delta를 순서대로 처리하고 화면 경계마다 제한한다. JNI 큐는 연속된 이동만 합치며 키·버튼·스크롤 순서를 유지한다. 캡처와 포커스, 입력 반납은 구분한다.
- 마우스 분리나 캡처 해제는 포인터 상태만 해제한다. 키보드 제거·비활성화는 해당 장치의 키만 해제한다. 다른 장치의 Ctrl/Shift는 유지하며, 실제 포커스·Surface 상실이나 태블릿 전환에서는 전체 입력을 반납한다.
- 숫자 키패드의 숫자·내비게이션·연산·Enter와 NumLock의 Wayland 잠금 상태를 제공한다. 초기 guest NumLock은 꺼짐이며 전달된 NumLock 키로 토글한다. 이미 켜져 있는 외부 키보드의 Android meta/LED 초기 상태를 guest에 자동 동기화하는 기능은 없고 실기기 확인 항목이다.
- Wayland 화면의 Android 합성·출력에는 GLES를 사용하고 실패하면 CPU로 복귀한다. Sway의 기본 합성과 게스트 앱 렌더는 pixman/software GL 경로다. VirGL은 같은 앱 UID의 실제 EGL/GLES 픽셀 검사와 실패 이유에 따라 사용할 후보를 판정한다.

이 구조는 Android 앱이 키보드·마우스의 전역 권한을 모두 얻었다는 뜻이 아니다. OEM 예약 키와 원시 트랙패드 접점은 운영체제·장치의 전달 범위와 사용자 승인에 따른다. [권한과 대체 방법](research/android-authority-alternatives.md)을 참고한다.

## 태블릿 구현과 검증 상태

대상은 **Y900 13 TB522FU · Snapdragon 8 Elite · Android 16 · 3840×2560**이다. 다른 Y900용 Mali/Dimensity 조사와 OEM 설정 쓰기를 적용하지 않는다. [TB522FU의 OS 경로](research/loopy-os-paths.md)는 recovery 소스와 native Linux kernel/DRM/GPU/절전의 확보 조건을 구분한다.

- 전체 화면 터치 메뉴, 좁은 360dp 창의 제어 버튼, 소프트 키보드 표시/숨기기와 창 조작.
- 한글 조합·확정·삭제·Enter의 단일 입력 큐와 Android 입력 정책 총64KiB 상한. 활성 Wayland 입력 필드의 직접 문자열은 요청당 UTF-8 4000B를 문자 경계에서 내부 분할한다. 지원하지 않는 앱의 가상 키보드 대체 경로에만 세션당 새 문자4073종 용량이 적용된다. 오류 전에 전달된 입력은 완전히 롤백하지 않으며 자동 재전송하지 않고 오류를 명시한다.
- 터치 탭·드래그·두 손가락 스크롤/우클릭, 저장되는 100~200% Sway 배율.
- Linux 화면 고정의 시스템 확인, Home/Recents 제한, Ctrl+Alt+Esc/터치 해제. 비치명적 오류는 고정을 풀지 않는다. 전역 단축키·IME 우회까지 명시적 입력 반납을 따르고 Activity 재생성 후에도 유지한다.
- 화면 고정 중 외부 Android 앱·권한·입력기·안내 브라우저 진입은 해제 안내로 돌아온다. Android task를 분리하고 사용자 설정은 자동으로 부여하지 않는다.
- 공유 SAF root ID/Unicode 파일 CRUD, traversal 및 공유 root/parent/child symlink 차단. 같은 UID의 경로 교체에 대한 원자적 보안 경계는 주장하지 않는다. 이전 잘못된 URI는 재선택하며 파일은 보존한다.
- 실제 OpenSSH와 Wayland 연결 UI·최근 주소·host key 확인·timeout/keepalive·실패 메시지 유지. Remmina RDP/VNC 화면 클라이언트를 추가했으며 태블릿 수신 서버는 미구현이다.

최신 Remmina·VirGL 변경과 전달 APK는 [남은 작업의 최종 검증](remaining-work-validation.md)에 별도로 기록한다. 아래 APK24 결과는 이전 후보의 보존된 증거이며 새 APK의 결과로 사용하지 않는다.

## 이전 APK24 수락 기록

이전 APK의 소스로 호스트 **482개**, 네이티브 Wayland **49개**, Android 16 ARM64 VM **47/47개 · 실패0**를 확인했다. VM 앱 UID는 **10224**, SELinux는 `u:r:untrusted_app:s0:c224,c256,c512,c768`이다. VM 준비 설정은 원래 값으로 복원했고, 소유 SSH fixture의 포트 전달·listener·worker도 정리했다.

- [전달 APK](../build/deliverables/LoopyDesktop-2026-10-06-y90013-wayland-arm64.apk) · 327,103,828 bytes · SHA-256 `57173bed54fe3206f0daf2ee1be95fd33b8dc17842cf1071a70f49de859ce77b`
- [전체 VM 결과](validation/2026-10-06-tablet-final-fourth-vm/receipt.json), [전달 영수증](validation/2026-10-06-tablet-host/delivery.json)
- [호스트 로그](validation/2026-10-06-tablet-host/host-tests-thirteenth.txt), [네이티브 로그](validation/2026-10-06-tablet-host/native-tests-second.txt)
- [현재 소스 검토](validation/2026-10-06-tablet-host/review-thirteenth.json), [현재 runtime 검토](validation/2026-10-06-tablet-host/final-runtime-thirteenth-review.json), [현재 APK 독립 감사](validation/2026-10-06-tablet-host/independent-package-twelfth.json), [입력·payload 무결성](validation/2026-10-06-tablet-host/integrity-thirteenth.json)
- [작업 소유 VM 종료](validation/2026-10-06-tablet-host/vm-cleanup.json) · 임시 AVD와 guest 사용자 데이터는 보존했다. 중단된 X11 실험의 제품 종료 성공을 의미하지 않는다.

이 VM은 **SwiftShader·4096-byte kernel page**를 사용한다. Android GLES 합성과 guest software GL의 화면 출력·fallback은 검사했지만, Y900 GPU 가속·성능·16KiB kernel 런타임·native OS 부팅의 성공으로 확대하지 않는다. 게스트의 일반 hardware 3D/DMA-BUF, native TB522FU OS 이미지·부팅·드라이버·절전은 완료되지 않았다. SSH 고정 loopback counterpart는 해당 fixture 사용자에 `none` 인증과 nonce 응답만 제공한다. 실제 원격 서버의 비밀번호/키 인증·네트워크 복구·원격 화면 스트리밍 수락을 대신하지 않는다.

첫 화면 고정 시험은 VM의 Android 화면 고정 설정이 꺼져 있어 확인 요청이 나타나지 않았다. [실패 기록](validation/2026-10-06-tablet-pin-vm/receipt.json)을 보존한다. 제품에는 사용자가 보안 설정에서 켜는 안내를 추가했다. VM runner에서만 원래 설정을 저장→시험용 활성화→복원하며 일반 APK는 설정을 쓰지 않는다.

반복 rootfs 업데이트를 보존한 이전 VM에서 새 APK의 설치 공간이 부족했다. [설치 실패 기록](validation/2026-10-06-tablet-pin-enabled-vm/receipt.json)을 보존하고, 이전 VM 환경을 삭제하지 않은 채 새 임시 VM을 생성했다. 사용자의 캐시 정리 허용에 따라 실행 중인 Gradle이 없음을 확인하고 재생성 가능한 Gradle8.14.3 transforms **3,152,437,248 bytes**만 제거했다. 프로젝트/SDK/runtime/VM 데이터는 보존했다. [캐시 정리 영수증](validation/2026-10-06-tablet-host/cache-cleanup.json). 후속 입력 경로 빌드에 필요한 공간으로 오래된 Gradle9.3.1 transform 항목 **1,500,258,304 bytes**만 추가로 제거해 총 **4,652,695,552 bytes**를 정리했다. [추가 정리 영수증](validation/2026-10-06-tablet-host/cache-cleanup-second.json).




[세 번째 전체47 후보](validation/2026-10-06-tablet-final-third-vm/receipt.json)는47개 모두 통과했지만, [추가 실제 DOM 검사](validation/2026-10-06-tablet-host/ime-semantic-code-observation.json)에서 IME Enter의 `key=Enter`, `code=Escape` 불일치를 확인했다. 가상 키보드의 예약 기호를 순서대로 배정해 Return이 evdev1을 사용한 것이 원인이다. 의미 제어 키는 표준 Linux evdev 위치로 고정하고, 임의 Unicode 기호는 예약 위치와 기존 할당을 피하도록 했다. [실제 Unix wire·SCM_RIGHTS·libxkb 경계 회귀](validation/2026-10-06-tablet-host/ime-semantic-evdev-host/receipt.json)는 전체4073종 문자 용량과 코드 충돌 거절을 확인한다. 최종 브라우저 시험은 기존 Unicode·삭제·Enter 조건에 `KeyboardEvent.code=Enter`를 추가했다. 물리 NativeBridge 키 경로는 별개이며, 미지원 앱의 임의 Unicode 가상 키 기호까지 물리 문자 위치를 보장하지 않는다.

[두 번째 전체47 실행](validation/2026-10-06-tablet-final-second-vm/receipt.json)은46개 통과, 두 번째 화면 고정 승인 확인1개 실패였다. 기존 시험은 알려진 SystemUI 버튼의 터치 주입 성공을 확인했지만 실제 승인 상태는 확인되지 않았다. [Android16 primary와 원래 실패](validation/2026-10-06-tablet-host/system-pin-approval-primary/receipt.json)에 따르면 확인창은300ms 이동 애니메이션을 적용하며 내부 panel은 배경 터치를 흡수한다. 다만 원래 실패에 버튼 좌표 기록이 없으므로 애니메이션을 확정 원인으로 기록하지 않는다. [시험 전용 승인 회귀](validation/2026-10-06-tablet-host/system-pin-approval-host/receipt.json)는 같은 SystemUI 창의 현재 버튼이 visible/enabled/clickable이며 좌표가200ms 이상 안정된 경우에만 물리 터치를 보낸다. 기존12초 안에서 최대3회로 제한하고, 창이 사라지거나 바뀌면 추가 터치를 중단하며 실제 OS PINNED에서만 성공한다. 제품의 시스템 승인은 자동화하지 않는다. 최종 전체 결과는 두 승인 좌표·주입/실제 상태 기록을 각각 보존하고 터치로 고정을 풀고 종료하는 강한 기존 조건을 다시 확인했다.

[원래 전체 호스트12 실행](validation/2026-10-06-tablet-host/host-tests-twelfth.txt)은480개 중 SSH fixture1개가 실패했다. 당시 packet·thread 순서 trace가 없어 다음 controlled 실패와 원인이 같다고 확정하지 않는다. [실제 Paramiko/OpenSSH 대조·primary·RED/GREEN](validation/2026-10-06-tablet-host/ssh-fixture-graceful-host/receipt.json)에서는 exec callback 복귀 전 transport가 닫혀 ACK99를 보내지 못하는 순서를 재현했다. fixture의 소유 receive thread만 남은 deadline 안에서 최대2초 join한 뒤 기존 정리를 실행하도록 고쳤다. 기존 SSH exit0·정확한 nonce·인증·외부 명령 거절·정리 조건은 유지했고, ACK99 실제 전송과 비협조 peer의 제한된 종료를 포함한3개 회귀가 통과했다. 후속 전체 통과의 개수와 로그는 위의 [현재 호스트 결과](validation/2026-10-06-tablet-host/host-tests-thirteenth.txt)로 연결한다. 이는 테스트 counterpart의 수정이며 제품의 원격 인증·외부 네트워크 수락으로 확대하지 않는다.

전체 시험 중 좁은 제어 바의 대기 조건이 메뉴 포커스 상실을 완료로 판단해 시험의 main-thread assertion이 프로세스를 종료했다. UI 예외는 시험 thread로 돌려보고, 메뉴 닫힘·실제 보이는 버튼·포커스를 확인하도록 정정했다. [원래 실패](validation/2026-10-06-tablet-final-vm/receipt.json), [원인 기록](validation/2026-10-06-tablet-host/vm-narrow-ui-diagnosis.json), [개별 재검사](validation/2026-10-06-tablet-touch-wait-vm/receipt.json)를 보존한다.

긴 한글 IME는 [안정된 가상 키보드 후보](validation/2026-10-06-tablet-ime-persistent-vm/receipt.json)에서 DOM459 codepoint에 머물렀다. 직접 Wayland 문자열 경로를 추가한 [APK19](validation/2026-10-06-tablet-ime-atomic-vm/receipt.json)도 누락된 GTK 입력 모듈 캐시 때문에 개별 키 경로로 실행됐다. [GTK primary·실제 cache 부재·RED/GREEN](validation/2026-10-06-tablet-host/gtk-im-cache-host/receipt.json)에 따라 시작 시 shipped utility로 캐시를 생성하며 사용자 입력 모듈 설정은 바꾸지 않는다. 캐시 수정 후 [APK20](validation/2026-10-06-tablet-ime-cache-vm/receipt.json)은 atomic 문자열을 받았지만 DOM1373에서 멈췄다. [APK21의 bounded trace](validation/2026-10-06-tablet-ime-serial-vm/receipt.json)에서10B/3999B 전송 뒤 fresh done가 이전 주변 문자열을 돌려줘각15초 후 중단됐고, 누락된96B는 전송되지 않았음을 확인했다. WebKit의 비동기 입력 반영 전에 조회한 주변 문자열을 앱 완료 ACK로 비교한 것이 이 후보의 원인이다. 별도로 [queued-state serial 회귀](validation/2026-10-06-tablet-host/ime-serial-input-host/receipt.json)는 유효한 host 결함이며 이 VM 실패의 stale-serial 증거로 확대하지 않는다.

최종 입력은 최신 done·포커스 상태를 읽어 같은 Wayland 연결에서 요청당 UTF-8 4000B를 scalar 경계에 맞춰 전달한다. GTK의 fresh done는 상태 장벽이며 Foot의 주변 문자열 미지원도 앱 완료 ACK로 취급하지 않는다. 삭제·의미 키는 균형 잡힌 가상 키 press/release로 해당 앱에 보내며, 오래된 주변 문자열로 UTF-8 삭제 길이를 추측하거나 이미 전송한 입력을 자동 replay하지 않는다. [비동기 client 모델·입력 순서·진단 실패 격리 회귀](validation/2026-10-06-tablet-host/ime-barrier-input-host/receipt.json), [GTK/WebKit 비동기 입력 primary 근거](validation/2026-10-06-tablet-host/ime-async-primary-host/receipt.json). 실제 완료는 [기존4214B/1404 codepoint의 정확한 브라우저 내용·삭제·Enter 및32미만keydown](validation/2026-10-06-tablet-ime-semantic-vm/receipt.json), [Foot Unicode PTY](validation/2026-10-06-tablet-unicode-semantic-space-vm/receipt.json)와 최종47개로 확인했다. 입력 원문·총량·45초 조건은 유지했다. 같은 실제 브라우저에서 emoji 한 글자를 native Backspace로 지우고 기다림 없이 한글을 확정한 뒤 Enter를 보낸 내용도 정확히 확인했다. 이는 해당 앱과 검사한 입력 순서의 결과이며, 임의 GTK 앱의 모든 문자·제어 키 조합 완료를 보장하는 프로토콜 ACK는 없다. Android 정책 총64KiB와 미지원 앱의 사전 선택된 가상 키보드 경로에만 적용되는4073종 문자 맵 상한을 구분한다. 물리 입력·Y900 처리 속도는 별도 조건이다.

두 손가락 스크롤이 Android에서 전달됐지만 Linux GTK 브라우저에 도달하지 않은 원인은 motion과 axis를 한 Wayland frame에 합친 데 있었다. GTK3의 frame handler가 해당 motion을 먼저 선택해 axis를 남겼다. 스크롤이 있는 입력에서 motion/button frame을 먼저 마감하도록 고쳤으며, [실제 Unix protocol RED/GREEN](validation/2026-10-06-tablet-host/touch-scroll-native/receipt.json)과 [동일 터치 VM 재검사](validation/2026-10-06-tablet-touchscreen-fixed-vm/receipt.json)를 보존한다.

고정 상태에서 터치로 종료할 때 자연 종료된 세션 token이 남아 종료 확인이 실패하는 문제를 수정했다. 성공적으로 정리한 세션만 token을 비우고, 정리 실패 시 재시도할 소유 정보는 유지한다. [호스트 lifecycle 회귀](validation/2026-10-06-tablet-host/terminal-token-cleanup-host/receipt.json), [한 번의 터치로 고정 해제 후 종료](validation/2026-10-06-tablet-touch-stop-fixed-vm/receipt.json).

권한 설정과 IME 선택 안내의 오류가 긴 스크롤 맨 아래에 있어 보이지 않는 문제는 오류 문구를 스크롤 밖에 두어 해결했다. APK17의 개별 검사에서 문구 표시와 같은 PINNED 세션 유지는 확인했지만, 기존 helper가 stock AlertDialog 버튼의 ScrollView를 선택했으므로 ‘본문 상하단 모두 확인’ 증거는 유효하지 않다. helper를 오류 문구와 같은 custom layout의 실제 본문 ScrollView로 수정하고, 0 및 양수 최대 scrollY에서 같은 오류 문구가 완전히 보이는지를 최종 전체 검사로 다시 요구한다. 175% 배율 시험은 실제 terminal app_id인 `loopy-terminal`로 수정했으며, [개별 배율·IME 재검사](validation/2026-10-06-tablet-scale-ime-fixed-vm/receipt.json)에서 같은 Linux 세션과 terminal PID 유지, 실제 화면 키보드 표시·숨김을 확인했다.

저장 공간 정리는 사용자 허용에 따라 오래된 호스트 Gradle 캐시 7,016,714,240 bytes를 제거했다. [마지막 추가 정리](validation/2026-10-06-tablet-host/cache-cleanup-fourth.json). 세 번째 정리는 프로세스 검사 오류로 일부 제거 후 중단된 기록을 그대로 보존했다. 별도로 작업 소유 disposable VM의 이전 rootfs 이미지 7,306,838,016 bytes만 제거했으며, 현재 rootfs와 linux-home·설정·공유 파일의 전후 일치를 확인했다. [VM 정리 첫 기록](validation/2026-10-06-tablet-host/owned-vm-rootfs-cleanup.json), [두 번째 기록](validation/2026-10-06-tablet-host/owned-vm-rootfs-cleanup-second.json), [세 번째 기록](validation/2026-10-06-tablet-host/owned-vm-rootfs-cleanup-third.json), [네 번째 기록](validation/2026-10-06-tablet-host/owned-vm-rootfs-cleanup-fourth.json), [다섯 번째 기록](validation/2026-10-06-tablet-host/owned-vm-rootfs-cleanup-fifth.json), [여섯 번째 기록](validation/2026-10-06-tablet-host/owned-vm-rootfs-cleanup-sixth.json), [일곱 번째 기록](validation/2026-10-06-tablet-host/owned-vm-rootfs-cleanup-seventh.json). 마지막 정리는 새 APK의 실제 IME 검사가 통과한 뒤 [Foot 재설치의 저장 공간 부족](validation/2026-10-06-tablet-unicode-semantic-vm/receipt.json)을 보존하고, 현재 이미지와 이전47개 통과 이미지의 데이터를 남긴 채 더 오래된 테스트 이미지 하나만 제거했다.

실제 guest worker가 거절한 작업의 type-only 오류를 Android에 표시한다. 고정된 상태에서 실제 ValueError를 생성하고 안내·보이는 제어 바·동일 token·원래 Sway PID와 시작 시각이 유지되며 명시적으로 복귀하는 것을 최종 전체 검사에 포함했다. 새 observer의 [호스트 회귀 기록](validation/2026-10-06-tablet-host/guest-command-errors-host/receipt-frozen.json)은 실제 Android syscall 및 PINNED VM 검사와 구분한다. 비동기 앱 시작의 성공을 보장하는 기능은 아니다.

후속 전체 시험에서 원격 메뉴의 CLI allowlist 누락과 resize 시험의 이전 LayoutParams 캐스팅을 발견했다. 원격 진입은 제품에서 수정하고, resize 시험은 실제 FrameLayout 구조와 기존 크기를 보존하도록 정정했다. [첫 전체 실패](validation/2026-10-06-tablet-first-full-vm/receipt.json), [원인 기록](validation/2026-10-06-tablet-host/vm-layout-cascade-diagnosis.json)을 보존하며 최종 전체 결과로 대체한다. 이전 시험 실패를 제품 성공으로 바꾸어 기록하지 않는다.

화면 고정 확인은 실제 SystemUI의 비포커스 창에 나타난다. 시험은 해당 창의 알려진 resource ID를 찾아 사용자가 누르는 것과 같은 터치를 보내며, 제품은 시스템 확인을 자동 승인하지 않는다. 실제 `PINNED` 상태에서 Home/Recents 제한·외부 설정 차단·Ctrl+Alt+Esc 입력 반납·같은 guest 유지·터치 종료 후 비동기 고정 해제를 모두 확인했다. [개별 고정 통과](validation/2026-10-06-tablet-pin-clean-vm/receipt.json)를 보존하며, 최종47개 결과에서 같은 검증을 다시 실행했다.

전체 화면 메뉴의 아래 36px가 Android 필수 제스처 영역과 겹치는 것을 실제 좌표로 발견했다. 기존 root padding에 적용된 여백을 제외하고 제스처·컷아웃 여백을 추가했으며, 버튼 전체가 안전 영역 안에 있음을 실제 터치 시험에서 확인했다. [측정 RED](validation/2026-10-06-tablet-host/menu-gesture-overlap-red.json), [같은 조건 GREEN](validation/2026-10-06-tablet-host/menu-gesture-safe-green.json). 실기기의 회전·컷아웃·키보드 분리 및 입력 지연은 별도 점검 조건이다.


[장치 분리 RED](validation/2026-10-06-wayland-input-host/input-detach-red.txt)와 [GREEN](validation/2026-10-06-wayland-input-host/input-detach-green.txt)은 마우스 분리·키보드 한 대 제거·캡처 전환·descriptor 변경·같은 ID 비활성화 다섯 조건을 실제 Java 입력 adapter 출력으로 검사했다. [기존 입력 소유권 검사](validation/2026-10-06-wayland-input-host/input-ownership.txt)도 실행했다. 이는 호스트 정책 검증이며 물리 장치 연결 성공이나 실제 입력 지연 측정이 아니다.

[키패드·5버튼 Wayland 검사](validation/2026-10-06-wayland-input-host/keypad-protocol.txt)는 실제 `wl_keyboard` keymap FD를 libxkbcommon 1.8.1로 파싱하고 NumLock/Shift 조합, 잠금 modifier 전달·키 반복·해제·재바인딩과 버튼 press/release를 확인한다. 호스트 Rust 검사에는 libxkbcommon 공유 라이브러리가 필요하며 `LOOPY_TEST_XKBCOMMON`으로 절대 경로를 지정할 수 있다. 이 호스트 검사 라이브러리는 Android 제품 의존성이 아니다.

최종 Android VM 검사는 실제 Sway 창·native Wayland terminal·키 입력으로만 작성한 파일의 정확한 내용·마우스/트랙패드 조작·화면 출력·입력 반납·세션 복구를 같은 APK에서 확인한다. VM의 가상 키보드/합성 접점과 SwiftShader 결과를 물리 GPU 성능이나 Y900 실사용 수락으로 표시하지 않는다.

## Termux와 GPU 대안

Termux는 실행 기반의 선택이다. Termux:X11/i3는 Wayland 요구를 충족하는 완료물이 아니다. 공식 Termux Sway/wlroots의 Termux:GUI backend는 별도 Wayland 후보이며, 실제 지원 조건과 미검증 범위는 [Termux Wayland 조사](research/termux-wayland-gui.md)에 기록한다. 현재 Loopy의 backend로 연결하거나 VM에서 수락한 기능으로 표시하지 않는다.

[GPU 대안 목록](research/guest-gpu-alternatives.md)은 VirGL·Vulkan/Venus·ANGLE/Zink·지원 Adreno KGSL·Mali DRM·OEM bridge·root·원격 렌더 조건을 구분한다. `WAYLAND_DISPLAY`나 renderer 환경변수만 바꾸어 GPU 가속 또는 프로토콜 호환을 성립시켰다고 주장하지 않는다.

## 실기기 수락

[Y900 점검표](y900-test-checklist.md)에 따라 USB/Bluetooth 키보드·마우스의 연결/분리, 키 반복·숫자 키패드·보조 버튼, Alt/Meta/OEM 예약 키, 한글 입력, 상대 포인터와 드래그·휠·절전 복귀를 확인해야 한다. 실제 GPU renderer·화면 전달·프레임 지연·발열·전력도 해당 기기에서 측정해야 한다. 이번 작업은 실기기를 연결하거나 변경하지 않았다.
