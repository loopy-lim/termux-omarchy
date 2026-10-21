# Loopy OS 경로와 태블릿 사용 기준

2026-10-06. 사용자는 앱에 한정하지 않고 OS 개발도 허용했다. 제품 목표는 **Wayland + 네이티브 키보드/마우스 + GPU + 사용자가 해제할 때까지 Linux 중심으로 사용**이다. 대상은 사용자가 지정한 **Lenovo Legion Y900 13 (TB522FU)** 이다. Android/데이터 유지 요구는 아직 지정되지 않아 현재 설치 경로는 데이터를 유지한다. 이 문서는 조사와 실행 경계이며, 태블릿용 OS 이미지가 완성되거나 부팅되었다는 결과가 아니다.

## 판단

완전한 입력 소유가 필수이면 Linux가 부팅되는 OS가 최종 목표에 가장 맞는다. 직접 evdev/libinput을 읽는 compositor가 키보드·마우스·터치·접속/분리를 처리하고 DRM/KMS 화면을 소유한다. Android 앱의 접근성 권한이나 전체 화면만으로 이 구조를 얻을 수 없다. libinput은 Wayland compositor가 입력 장치를 처리하는 라이브러리다. [libinput 공식 설명](https://wayland.freedesktop.org/libinput/doc/latest/what-is-libinput.html).

현재 실행 가능한 호스트 개선은 Android의 화면 고정/허용된 관리 기기의 Lock task와 독립적인 입력 반납이다. Home·최근 앱의 우발적인 전환을 줄일 수 있지만 시스템의 고정 해제 동작과 전원/OEM 예약 기능은 남는다. 일반 앱에 Home와 Recent Apps key가 전달되지 않는 계약이 있으므로 임의 권한을 모두 요청하는 방식으로 해결하지 않는다. [Home/Recent Apps](https://developer.android.com/reference/android/view/KeyEvent), [화면 고정과 관리 잠금](https://developer.android.com/work/dpc/dedicated-devices/lock-task-mode).

## 선택지

| 경로 | 사용자 경험과 성능 | 필요한 실제 준비 | 현재 상태 |
| --- | --- | --- | --- |
| Android Wayland 호스트 + Linux 전용 화면 고정 | 기존 Android·데이터 유지, USB/Bluetooth 입력은 Android가 전달하는 경로, GLES 화면 출력 | 앱 설치; 화면 고정은 사용자가 시스템 확인; 필요 시 접근성 | 이번 구현·VM 검증 경로. 게스트 소프트웨어 렌더링 및 시스템 예약 키의 경계 유지 |
| 기존 DPC가 허용한 관리 기기의 Lock task | Home/최근 앱/알림 등 관리 정책으로 제한, 지정 해제 경로 | 전용 기기 관리와 allowlist; 사용 중인 개인 기기에 임의 Device Owner 등록하지 않음 | 앱의 start/stop Lock task 경로를 사용할 수 있음. DPC 배포·등록 및 관리 기기 실험은 별도 |
| 기기 커스텀 Android ROM + 시스템 Wayland/입력 bridge | vendor GPU/화면 드라이버를 유지하면서 시스템 입력 정책 조정 가능 | 해당 모델의 kernel/device/vendor tree, 빌드 가능한 ROM, AVB/부팅/복구 경로와 기기 | 후보 설계. 시스템 통합 backend는 미구현 |
| 기기 네이티브 Linux/postmarketOS 포트 | DRM/KMS + Mesa + libinput의 직접 데스크톱 경로; Linux가 기본 OS | 해당 보드의 커널·DTB·패널·터치·GPU·USB·Bluetooth/Wi-Fi·충전·절전 지원 | 모델별로 결정해야 함. 지원 기기 명단/기능표 확인부터 시작 |
| vendor Android 드라이버를 재사용하는 Halium 계열 포트 | Android vendor 의존성을 이용하는 Linux 배포판 포트 후보 | 해당 Android 기반·kernel/device/vendor source와 배포판 요구가 맞아야 함 | 공식 porting 문서가 요구하는 조건을 모델에 대조해야 함. 기존 문서의 오래된 Android 버전 조건을 신형 기기에 적용하지 않음 |
| 원격 Linux Wayland 워크스테이션 + 태블릿 클라이언트 | 렌더링·컴퓨팅은 호스트 GPU, 태블릿은 입력·디코드; 네트워크 지연에 영향 | SSH 또는 원격 화면 서버/클라이언트, 인증·주소·재접속 | SSH와 Remmina RDP/VNC 클라이언트 구현. 태블릿 수신 서버·WebRTC·하드웨어 디코드는 미구현 |

[postmarketOS 기기별 배포·기능 확인](https://postmarketos.org/download/), [Ubuntu Touch 공식 기기 목록](https://devices.ubuntu-touch.io/), [Halium 포팅 첫 단계](https://docs.halium.org/en/latest/porting/first-steps.html).

## TB522FU에 맞춘 소스 판단

Lenovo 공식 제품 사양은 **TB522FU, Snapdragon 8 Elite, Android 16, 13인치 3840×2560**이다. 이 저장소의 이전 TB570FU/Dimensity/Mali 조사와 Lenovo OEM 설정 변경 도구를 이 모델의 근거로 사용하지 않는다. 물리 장치는 연결되어 있지 않으며 Android build/보드/부트로더 상태는 아직 실물에서 읽지 않았다. [Lenovo 공식 제품 사양](https://item.lenovo.com.cn/product/1054307.html).

TB522FU용 TWRP maintainer 저장소는 platform `sun`, Virtual A/B, 전용 recovery partition과 화면·터치 경로를 설명한다. `BoardConfig.mk`는 **`BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true`**를 지정한다. 이 recovery device tree만으로 Linux 커널이나 DRM/KMS·Mesa·절전 지원을 얻을 수 없다. 일부 firmware에서 bootloader fastboot가 제한된다는 설명도 maintainer 관찰이며 현재 태블릿에 확인된 상태는 아니다. 읽은 네 파일을 revision **`2ed9572c0869180d2b48b0b765970233fb8cd481`**에 고정하고 URL/해시를 [소스 조사 영수증](tb522fu-source-audit.json)에 기록했다. 제품에 이 소스를 복사하거나 recovery 이미지를 빌드·플래시하지 않았다. [TB522FU recovery maintainer 소스](https://github.com/lanweikayu/android_device_lenovo_TB522FU).

Lenovo GPL 저장소의 공개 요청은 계속 열려 있으나, 추가 조사에서 공개 커널과 Qualcomm 모듈 소스를 확인했다. [커널 저장소](https://github.com/lenovo-basements/android_kernel_lenovo_sm8750)는 revision `210981a0ad749c30080b853d31bc009d9db0592d`, [모듈 저장소](https://github.com/lenovo-basements/android_kernel_lenovo_sm8750-modules)는 `e1f324632d70b2427751820cd48eefc45baab0ce`에 고정했다. 커널의 Makefile·GKI 구성과 모듈의 display/graphics Makefile을 실제로 읽고 [새 조사 영수증](tb522fu-kernel-followup.json)에 URL과 SHA를 기록했다. 이는 커널 전체를 확보하지 못했다는 이전 설명을 보완한다.

[요청자의 마지막 보고](https://github.com/lenovo/gplcc/issues/16#issuecomment-5714103205)는 `dhall_och1909`와 보드 DT overlay를 남은 항목으로 설명한다. 해당 firmware·kernel·4KiB 설정은 다른 소유자의 기기 보고이며 사용자 태블릿의 실측이 아니다. API의 커널 recursive tree는75,908항목에서 **truncated=true**이고 모듈 API는 rate limit이므로, 이 응답에서 검색되지 않은 파일을 전체 저장소에 없다고 단정하지 않는다. 동일 TB522FU의 DTB/DTBO·모듈 빌드·패널·입력·절전을 재현하거나 native Linux DRM 부팅을 확인하지 못했으며 커널/ROM/OS 이미지는 만들거나 플래시하지 않았다.

GPU 조사는 Qualcomm Adreno/Freedreno 경로로 진행해야 한다. Mesa 공식 문서는 정확한 chip 지원 여부를 `freedreno_devices.py`로 확인하도록 안내한다. Snapdragon 브랜드명이나 인접 GPU의 지원만으로 해당 Android KGSL driver, buffer import, 태블릿 panel DRM 출력 또는 Vulkan 지원을 보장하지 않는다. 이번 APK의 Linux 앱은 검증된 llvmpipe/software 경로를 사용하며 Y900 13의 GPU 성능은 아직 실측하지 않았다. [Mesa Freedreno 공식 문서](https://docs.mesa3d.org/drivers/freedreno.html).

현재 선택은 **Android를 유지하는 Wayland 호스트를 사용 가능한 상태로 완성하고, 동일 TB522FU의 kernel/display/input 소스가 확보되면 native Linux OS 포트를 별도 backend로 진행**하는 것이다. 네이티브 OS 포트의 착수 조건은 다음과 같다.

- 동일 SKU·firmware의 kernel source, defconfig, DTB/DTBO 및 필요한 vendor modules를 확보하고 재현 빌드한다.
- USB/BT 입력, 패널/터치, GPU와 display controller, 저장장치, 충전·절전 복귀를 동일 보드에서 각각 검증한다.
- Android 보존 여부와 원복 가능한 recovery/부팅 경로를 정하고, 해시가 고정된 검토 가능한 이미지를 만든 뒤 실기기 설치를 승인받는다.

## 기기를 연결했을 때 읽기 전용 점검

```sh
./dev/device-check --serial <정확한-ADB-serial> --expect-manufacturer lenovo --expect-model TB522FU
```

다른 Y900 모델이면 전체 수집 전에 중단한다. bootloader/verified boot 속성, 화면 크기, 입력 장치와 `/dev/kgsl-3d0`·DRM 노드의 shell 관찰을 수집한다. 이 값은 일반 앱의 접근 권한이나 unlock 가능성을 증명하지 않는다. `lenovo-input`의 설정 쓰기는 TB522FU에 허용하지 않는다.

## 모델 확인 후 실행 순서

1. 정확한 모델/board/SoC/Android build/kernel/bootloader 상태와 Android·데이터 유지 조건을 기록한다. 읽기 전용 장치 점검을 먼저 한다.
2. 지원 배포판의 동일 모델 기능표 및 vendor kernel/device tree/license를 고정한다. 비슷한 SoC나 다른 지역 SKU의 이미지를 사용하지 않는다.
3. DRM/KMS 패널 또는 vendor display 경로, 실제 evdev 접점, USB/Bluetooth hotplug, Mesa/EGL renderer를 검증한다. 화면 없는 부팅이나 llvmpipe 부팅을 네이티브 GPU 실사용 수락으로 표시하지 않는다.
4. 커널/DTB/initramfs/rootfs/부팅 이미지의 해시, recovery/원복 경로, 사용자 데이터 보존 범위를 갖춘다. 부트로더 변경·초기화·플래시는 실제 기기와 구체적인 승인 후 실행한다. Android의 정식 부트로더 해제는 데이터 초기화를 수반하는 계약이다. [AOSP 부트로더 잠금/해제](https://source.android.com/docs/core/architecture/bootloader/locking_unlocking).
5. 기본 화면·입력이 작동한 뒤 충전/잔량·Wi-Fi·오디오·펜·회전/분할·절전 복귀·장시간 열/전력을 확인한다. 실패하는 항목과 대체 동작을 제품 UI 및 기기 수락표에 기록한다.

현재 Mac에는 qemu-system-aarch64/limactl 실행 파일이 확인되지 않았다. Android VM은 APK 호스트 검증용이며 native Linux OS 부팅 증거가 아니다. TB522FU용 커널·보드 드라이버가 검증되지 않은 상태에서 범용 이미지를 기기용 OS 완료로 표시하지 않는다.
