# 남은 Wayland 실사용 작업

사용자 승인: 기존 Wayland·GPU·입력·원격·Y90013 OS 작업을 계속 마무리한다. 기존 데이터와 전달된 APK는 보존한다. 이 변경은 부트로더 변경, 초기화, 플래시, Device Owner 등록을 실행하지 않는다.

## 원격 화면

Alpine의 고정 Remmina 1.4.40 RDP/VNC 플러그인을 GTK3 Wayland로 실행한다. SSH 화면에서 원격 화면 연결을 열 수 있다. Loopy가 만드는 연결 파일에는 주소·사용자·프로토콜만 기록하고 `disablepasswordstoring=1`, `ignore-tls-errors=0`을 적용한다. 인증과 서버 인증서는 네이티브 클라이언트에서 사용자가 확인한다. 파일과 클립보드 공유는 기본으로 끈다. 연결 종료·재시도는 같은 Linux 데스크톱에서 가능하다.

입력은 기존 Wayland 키보드·포인터 경로를 사용한다. Ctrl+Alt+Esc는 Android에서 먼저 처리하는 반납 단축키다. Remmina 창을 열었다는 사실과 원격 화면·키·포인터가 실제 왕복했다는 증거를 구분한다.

## VirGL EGL

Surfaceless current가 불가능한 EGL에서 context마다 독립적인 1×1 pbuffer를 사용한다. bootstrap, renderer, threaded-fence context의 생성·binding·unbind·destroy·초기화 실패를 동일한 소유권으로 처리한다. 외부 display는 재초기화하거나 terminate하지 않는다. EGL core1.5 또는 정확한 KHR create-context 토큰을 요구한다. GLES 경로에서3.2보다 높은 데스크톱 GL 버전 요청은 드라이버 호출 전에 거절하며 실제 GL/GLES3 이상 검사와 guest 픽셀 검사를 유지한다. 서버 준비만으로 가속을 선언하지 않는다.

## OS·장치 조건

대상은 TB522FU이다. 현재 연결된 물리 기기는 없다. 동일 모델의 kernel/DTB/DTBO/display/input 소스와 복구 경로가 확보되지 않으면 부팅 가능한 OS로 표시하지 않는다. 기존 읽기 전용 device-check를 사용한다. VM 결과를 물리 GPU·USB·Bluetooth·배터리·절전 증거로 확대하지 않는다.

## 제한

코드 모듈은 500줄 이내를 유지한다. 기존 APK24와 검증 영수증을 덮어쓰지 않는다. 패키지는 기존 고정 APKINDEX에서 Q1/datahash를 검증하고 전체 의존성 잠금을 유지한다. 신규 APK와 VM 결과는 별도 이름과 해시로 전달한다.
