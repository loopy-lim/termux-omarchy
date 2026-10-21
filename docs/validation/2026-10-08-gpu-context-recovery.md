# Y900 GPU 앱, 컨텍스트 전환, 입력 소스 검증

검증 기기는 `Y900` / `TB522FU` / Android 16이며, 이 문서의 초기 조사 APK SHA256은 `22e57dc33b83652bf1c2f8610ab1f9ff12a971957ee71566fdc00077fc7e9c8f`이다. 아래 시험은 이 APK의 실제 앱 UID `10330`과 보존된 Arch 이미지에서 수행했다. 별도 실행 바이너리와 격리 fixture를 설치 APK의 동작으로 확대하지 않는다. 당시 기본 세션은 소프트웨어이고 Android 출력은 Adreno GLES이다. 현재 설치본과 후속 제품 복구 검증은 [1148 후보](../../build/deliverables/LoopyDesktop-2026-10-08-recovery-input-arm64/README.md), 실제 GPU 기본 세션과 표시율은 [92de 후보 이력](../../build/deliverables/LoopyDesktop-2026-10-08-gpu-desktop-arm64/README.md)을 따른다.

## GTK의 GLES 초기화

GTK `1:3.24.52-1` aarch64 패키지 SHA256 `bad14c1e2e4fa9cd662a501d400a3b74858ae5721e28ca42257fdbd7fe632944`와 공식 태그 소스를 대조했다. GLArea는 `use_es`를 적용하기 전에 공용 paint context를 realize한다. 따라서 `GDK_GL=gles`는 Gtk/Gdk 초기화 전에 자식 실행 환경에 있어야 한다. 이전 widget04/05는 이 설정이 없었다.

`build/diagnostics/y900-performance-20261007/gpu-gdk-gles01.json`은 실제 Wayland Gtk.GLArea의 `virgl (Adreno (TM) 830)` 렌더러, 두 번의 정확한 `[51,102,153,255]` GPU readback, Android 표시 영역의 같은 RGB, 오류 0을 기록한다. 14.285초에 222회 draw, 약 15.54 draw/s이며 CPU 데스크톱을 거치는 이 경로는 성능 합격이 아니다.

격리 Hyprland 시험의 초기 두 실패도 보존했다. nested01은 시험 부모 Wayland 주소를 절대 경로로 바꾸지 않아 fallback backend를 사용했고, nested02는 시험 Unix socket 경로가 너무 길었다. nested03은 이 두 문제를 고친 뒤 실제 GPU Hyprland와 GPU 앱의 동시 실행에서 compositor가 `SIGABRT`로 종료됐다. 기존 사용자 세션은 유지됐다.

## 실제 다중 클라이언트 GUI와 남은 오류

동일 `bfbcfa48de583688860d72c599c42668dfc8666e777399e1b2866bc707493d9a` 서버를 새로 시작한 nested05에서는 GPU Hyprland와 GTK 앱이 동시에 실행됐다. GTK가 14.132초에 622회 draw했고, 두 GPU readback 및 compositor screencopy의 공용 fixture RGB가 맞았다. 서버의 `VREND_DEBUG=khr` 설정과 새로운 수명 조건이 포함된 시험이며, 약 44.01 draw/s를 지속 Android 데스크톱 FPS로 해석하지 않는다.

원래 nested05 드라이버는 종료 시 외부 shell까지 서버로 선택해 argv 검증에서 멈췄다. 별도 `finalize-gpu-nested-gles05.py`가 실제 서버 PID와 전체 cmdline을 확인하여 종료했고, `gpu-nested-gles05-acceptance.json`은 종료와 픽셀 검증을 보완한다. 실패 드라이버와 결과를 덮어쓰지 않았다.

기본 info 설정의 fresh 서버와 ARM watchdog을 사용한 recovery06에서는 다음 서버 오류가 기록됐다.

```
vrend_check_no_error: context error reported 1 "Hyprland" Unknown 1286
context 1 failed to dispatch CLEAR: 22
client: VTEST_CLIENT_ERROR_COMMAND_DISPATCH
```

`1286`은 framebuffer 연산 오류이다. caps 조회가 임시 framebuffer를 변경하고, 새 context 생성도 실제 EGL context를 바꾸지만 기존 renderer의 현재-context 추적과 어긋난다. 실제 C 라이브러리와 GLES 회귀에서는 원본의 caps/create/repeat 세 경우 모두 같은 CLEAR 22 / GL 1286을 재현했고, 컨텍스트 경계를 고친 세 경우는 정확한 texture readback을 통과했다. 이 회귀는 ARM VM이며 Adreno 실기기 증거로 확대하지 않는다.

새 별도 Android 후보 SHA256 `794e985096898cc508933d97375dcfd36667eb19c6fa3a7b84785666ff0d1ffa`를 사용한 `gpu-isolation08-server.json` / `gpu-isolation08.json`은 기본 info 설정에서 실제 GPU Hyprland와 GTK 앱의 생성·그리기·종료 4회가 통과했음을 기록한다. 각 앱은 Adreno virgl 렌더러와 정확한 두 픽셀 readback을 반환했고 compositor는 유지됐다. 서버는 전체 argv와 PID를 확인한 뒤 소유한 프로세스만 종료했다. caps의 stale GL error 1282 로그는 남아 있지만 1286/CLEAR 22/dispatch failure는 발생하지 않았다.

SELinux `ps` 결과에서는 이 별도 서버가 `runas_app`, 실제 ManagedServer가 `untrusted_app`임을 확인했다. UID 10330이 같아도 실행 도메인이 같지는 않다. 따라서 APK에 후보를 포함한 뒤 실제 ManagedServer 경로에서 추가 검증해야 한다. 네 앱의 약 35–41 draw/s는 기존 CPU 세션 안의 nested 시험이며 지속 GPU 데스크톱 FPS가 아니다. GPU 기본 경로는 아직 승격하지 않는다.

## bounded watchdog

별도 실제 ARM `start-hyprland` 후보 SHA256 `39f0a45a6cf881b10e16244cee9e508d80bb9db8a7ce6b19b83f99bcd6adbca4`는 원본 main/Instance/Nix, 실제 고정 Glaze/Hyprutils/툴체인으로 빌드했다. 원본 재빌드와 patched 빌드는 각각 반복 결과가 같고 ARM 프로세스 회귀 8개가 통과했다. 재빌드 baseline은 배포 stock 바이너리와 다르며 이를 영수증에 명시했다.

recovery06은 실제 GPU 실패 뒤 소프트웨어 재시도 로그 1회를 확인했다. 다만 upstream safe mode가 원래 설정과 startup callback을 건너뛰어 정상 GUI 복귀 증거를 얻지 못했다. v4는 소유한 GPU 경로의 첫 소프트웨어 재시도만 같은 설정으로 실행하고, 두 번째 실패는 종료한다. 기존 software/foreign 경로의 upstream safe mode를 유지한다.

실제 ARM v4 후보 `cbbba746c29b30736b04d23501687eadf0e6d36ed4cd9d5c942ad13481b2be7c`를 별도 private 경로에 배치한 recovery07은 GPU 실패 뒤 같은 설정과 startup callback으로 정상 GUI에 복귀했다. `watchdog-gpu-recovery07-host.json`에는 GPU Hyprland PID 10650 → 소프트웨어 PID 10940, 재시도 로그 1회, 실제 GTK의 llvmpipe 렌더러, 오류 0과 정확한 두 GPU API readback, watchdog의 정상 종료가 있다. 사용자의 원래 CPU 세션은 유지됐다. 이 결과는 설치 APK에 v4가 포함됐다는 증거와 구분한다.

`watchdog-recovery07-pixel-acceptance.json`은 공용 fixture의 compositor 출력 RGB `[51,101,152]`를 기록한다. 초기 exact RGB 비교는 실패했으며, 기존 표시 경로의 채널별 ±3 허용 오차로 다시 평가한 결과를 별도로 보존했다. API readback `[51,102,153,255]`는 정확히 일치한다. 약 40.76 draw/s의 짧은 nested 시험은 60 FPS 성능 합격이 아니다.

## 실제 Linux 마이크 소스의 합성 음원 시험

`mic-transport01.json`은 현재 private PipeWire에서 `module-pipe-source`를 실제로 등록하고 `Audio/Source` / S16LE / 48 kHz / mono를 확인했다. 합성 PCM 61,440바이트를 전달했고 실제 `parec` 출력에서 정확한 fixture 패턴 480회가 확인됐다. 반환받은 module ID만 제거하고 source 부재와 기존 `loopy_android_sink` 보존을 확인했다. Android 마이크 권한을 부여하거나 실제 소리를 녹음하지 않았다.

`mic-idle02.json`은 소비자가 없는 SUSPENDED 소스에서 61,440바이트 뒤 FIFO backpressure가 발생함을 확인했다. 따라서 사용자가 먼저 마이크를 켠 뒤 앱을 여는 흐름을 위해서는 대기 상태와 실제 consumer 상태를 연결해야 한다. 권한 허용만으로 녹음하지 않고, 명시적인 현재 세션 활성화와 앱 UI 동의를 요구하는 구현 및 수명 검증을 진행한다.

`mic-status03.json`은 실제 source의 SUSPENDED → consumer가 연결된 RUNNING → muted RUNNING → consumer가 종료된 IDLE 상태를 구분한다. 이 상태를 이용해 명시적으로 켜진 소스가 대기 중일 때 AudioRecord를 만들지 않고, 실제 소비자가 있고 음소거되지 않았을 때만 캡처하도록 연결한다. 이 문서의 실기기 시험은 합성 음원 전송과 상태 관찰이며 실제 마이크 녹음은 아니다.

실제 typed endpoint 소스 `bc6ead8f6cbaf58d0b725c4fe34f7611f5843deeacbbb2ceae16bb5f5fbf0667`를 격리 경로에서 실행한 `mic-typed05.json`은 armed epoch 0 → running 1 → mute/armed → running 2 → consumer 종료/armed → off와 소유한 module 제거를 통과했다. 합성 PCM 61,440바이트를 전송했고 `parec` 출력 158,400바이트에서 정확한 fixture 패턴 480회를 확인했다. 기존 speaker sink는 유지됐다.

앞선 typed04는 같은 상태 전환과 정리를 통과했지만 짧은 기본-latency consumer에서 종료 전 출력이 0바이트여서 PCM 검증에 실패했다. 그 실패를 보존하고, typed05에서는 explicit 10ms consumer latency와 더 긴 합성 전송·대기를 사용했다. Android AudioRecord 경로의 실제 녹음 검증으로 확대하지 않는다.

## 설치 후보 9ea와 실제 ManagedServer

`build/deliverables/LoopyDesktop-2026-10-08-gpu-context-recovery-arm64/app.apk` SHA256 `9ea841f512964474dbe71aa81ed50572fbb43087a2abb4523ecac7f9200a1737`는 고친 VirGL 794e와 watchdog v4를 포함한다. 업데이트 전후 앱 UID 10330, 기존 HOME·115개 설정 파일·프로세스 정책을 대조했고 값이 유지됐다. 첫 설치 driver는 미허용 마이크 권한 행이 dumpsys에서 생략되는 경우를 실패로 잘못 판정했다. 설치 성공 후 그 오류를 보존하고 별도 finalize 기록을 남겼다. 읽기 전용 PackageManager Binder 조회는 RECORD_AUDIO 권한 -1, AppOps는 ignore이며 실제 녹음이나 권한 부여는 수행하지 않았다.

`build/diagnostics/y900-gpu-context-20261008/gpu-managed10-acceptance.json`은 이 APK가 시작한 실제 `untrusted_app` ManagedServer PID 22611에서 GPU Hyprland와 GTK 앱의 생성·그리기·종료 4회를 통과한 결과이다. 각 앱의 Adreno 렌더러와 두 개의 정확한 픽셀 readback, 마지막 compositor 캡처, 정상 종료를 확인했다. 이전 run-as 서버 시험과 구분되는 실제 앱 실행 경로이다. 기존 CPU 데스크톱 안의 nested 시험이므로 전체 GPU 데스크톱 FPS로 해석하지 않는다.

`gpu-qt11.json`은 Qt OpenGL RHI / virgl Adreno / GL 2.1을 확인했지만 픽셀 캡처를 하지 않았다. per-frame 진단 로그를 포함한 짧은 시험의 115 swaps / 4011ms는 성능 합격이 아니다. 이어진 qt12 창 제어 단계 실패도 보존했다. quiet qt13은 실제 소유한 640×400 창을 캡처해 공용 RGB 픽셀 99.375% 일치를 확인했고, 253 swaps / 9033ms 약 28.0회/초를 기록했다. Qt GPU 앱과 CPU 컴포지터가 함께 실행된 경로이며 60fps 목표를 통과하지 못한다.

별도 새 JNI 후보는 실제 두 Wayland 연결 사이에서 오래된 입력이 새 클라이언트에 전달되는 실패를 재현하고 수정했다. 이전 세대 worker의 flock 인계, 새 세대에 저장 배율 적용도 수정했다. 이 소스들은 9ea APK 동결 이후의 변경이며, 별도 다음 설치본과 실기기 복구 검증이 필요하다.

전체 Omarchy 지원, 장시간 60 FPS 이상, 144 FPS, 실제 키 입력부터 화면 표시까지의 지연, Linux Chromium sandbox, 모든 하드웨어·서비스 지원은 이 문서의 통과 범위에 포함되지 않는다.
