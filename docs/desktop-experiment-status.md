# 데스크톱 개발 이력과 현재 제품 상태

이 문서는 초기 APK·Sway 경로의 개발 이력이다. 2026-10-09 현재 Y900의 사용 경로는 Termux 기반 Hyprland·Omarchy이며 아래의 미연결·미구현 문구를 현재 기기 상태로 해석하지 않는다.

2026-10-05의 초기 단일 터미널 납품과 첫 Sway 후보는 **과거 검증 단계**다. 사용자가 이후 전체 데스크톱·키보드·트랙패드 구현을 다시 요청했고, 현재 기본 빌드 입력과 앱 화면은 Sway 제품 경로로 바뀌었다. 터미널 전용을 현재 최종 범위로 취급하지 않는다.

## 과거 증거

- [터미널 최종 VM 영수증](validation/2026-10-05-terminal-final/receipt.json): 당시 APK에서 14/14. 이 수치와 SHA는 현재 Sway 제품 APK를 검증하지 않는다.
- [첫 데스크톱 후보](validation/2026-10-05-desktop-first/receipt.json): Sway 1.10.1/wlroots 0.18.2/pixman/foot가 앱 Surface에 표시됐지만 17/20. Super 창 생성·작업공간·런처 3개가 실패했다.
- [OS 입력 진단](validation/2026-10-05-desktop-modifier-diagnosis/receipt.json): 해당 VM에서 Super가 Surface로 전달되지 않았고 Ctrl+Alt는 전달됐다. 이 결과를 Y900 또는 접근성 서비스를 켠 실제 물리 키보드 결과로 확대하지 않는다.

## 현재 소스에 반영한 경로

Sway 바·wmenu 검색 메뉴·타일링 작업공간 1–9가 기본 화면이다. foot 외에 Mousepad, Thunar, nvim, btop, yazi 등 고정 ARM64 패키지를 포함한다. `tools/prepare_desktop.py`가 `build/desktop/rootfs.tar.gz`를 만들고 `dev/build`의 기본 rootfs는 그 파일이다. guest 설정은 `guest/desktop/`에 있다.

`DesktopSessionService`가 Linux/Wayland host를 Activity와 분리해 보유하고, Surface 또는 Activity 재생성에는 기존 세션 화면을 다시 붙인다. 화면을 떠나는 것은 세션 종료와 다르고, **세션 종료**만 Linux 프로세스 정리를 요청한다. `DesktopCommands`의 제한된 action은 UUID별 guest 작업 파일로 전달된다. Android 앱은 검사된 앱 목록에서 원래 Android 창으로 열며, Linux 창은 서비스에 남는다. 내부 Sway selection과 Android ClipboardManager는 `DesktopClipboardBridge` 및 guest `wl-copy`/`wl-paste` worker로 연결한다.

입력에는 장치별 key 해제, 기본 Ctrl+Alt 및 선택 가능한 Meta/Alt, Caps 짧은 탭 한/영·Caps+HJKL, 두벌식 조합, Android IME commit, 마우스/터치패드/터치, 가로·세로 스크롤과 전달된 다중 접점 제스처가 있다. 사용자가 켜는 접근성 서비스는 키 사전 필터를 제공하고 Android 14+에는 mouse/touchpad 모션 소스를 요청한다. 시스템이 원시 접점을 제공하지 않는 기기에 제스처를 만들어내지는 않는다. Deskweft의 키 필터·장치 해제 설계는 참고했지만 해당 코드나 Shizuku OEM 설정 도구를 제품에 복사·내장하지 않았다([조사](research/deskweft-reuse.md)).

## 남은 검증 경계

최종 데스크톱 APK는 [VM 시험](validation/2026-10-05-desktop-delivery-vm/receipt.json) 14/14, 호스트 111개, 네이티브 36개를 통과했다. [검증 기록](desktop-validation.md)에 APK·rootfs·소스 입력과 실행 증거를 연결했다. 납품 파일은 `../build/deliverables/LoopyDesktop-2026-10-05-desktop-arm64.apk`다. 이전 터미널 APK와 구분한다.

Y900 실기기는 아직 연결되지 않아 확인하지 못했다. 실제 Lenovo 키보드/트랙패드 식별, OEM 예약 Meta 처리, raw 멀티터치 수신, 화면 회전·resize, 절전 복귀, CPU 렌더링의 지연·전력은 [실기기 점검](y900-test-checklist.md)에서 확인한다. Android 13 이하에는 접근성 모션 소스 API가 없고 API 34+에서도 원시 접점은 보장되지 않는다. GPU/DMABUF 가속, Omarchy 원본 Arch/Hyprland 배포, 모든 Android 앱을 Wayland 창 안에 넣는 기능은 현재 구현 범위가 아니다.
