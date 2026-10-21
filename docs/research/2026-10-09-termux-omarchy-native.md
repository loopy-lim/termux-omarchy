# Termux에서 실제 Omarchy / Hyprland를 실행하는 경로

조사일: 2026-10-09. **소스 조사만 완료**했다. 패키지 다운로드·설치, 코드 실행, 컴파일, ADB, 기기 성능 측정은 하지 않았다. 사용자는 기존 Termux:X11을 출력 호스트로 쓰는 것을 허용했다. 따라서 X11 위에 실제 Hyprland가 Wayland compositor로 동작하는 구조는 후보에 포함한다. i3/Xfce/KDE를 Omarchy 완료로 부르지는 않는다.

현재 가장 짧은 구현 경로는 **BlackFireAlex의 patched Hyprland + Weston + Termux:X11을 별도 PRoot 컨테이너에서 검증하는 것**이다. PRoot 없는 Bionic Hyprland는 별도의 포팅 단계다. 아래의 “가능성”은 원문과 구조에 근거한 추론이며 현재 태블릿의 실행 성공·입력 지연·60/144 FPS 수락을 뜻하지 않는다.

## 1. 세 가지 후보

| 후보 | 실제 구현 / 재사용할 부분 | 현재 요구와의 거리 |
|---|---|---|
| **A. BlackFireAlex Omarchy Android** | `Termux:X11 ← patched Weston ← patched Hyprland/Aquamarine ← Omarchy Shell/앱`. ARM64 Arch userspace는 PRoot 안에서 실행한다. | 실제 Omarchy/Hyprland를 포함하므로 첫 검증 후보. 저자의 Adreno 840 검증을 Adreno 830에 적용할 수는 없다. Chromium은 로컬 XWayland 표시이며 Linux process/GPU sandbox를 끈다. |
| **B. Bionic native Hyprland 포팅** | 공식 Termux Weston/Mesa와 lfdevs의 native KGSL Mesa·Anland compositor adapter를 재사용한다. Hyprland/Aquamarine의 Android allocator/backend를 별도로 이식한다. | PRoot syscall 변환을 없앨 수 있는 구조적 후보. Anland의 지원 표는 KWin/Weston/Mutter이며 Hyprland 지원은 확인하지 못했다. 현재 Omarchy 완성본이 아니다. |
| **C. Adreno 830의 wlroots/Vulkan→SHM 참고 경로** | Azkali의 Galaxy S25/830용 patched Phosh/Fedora PRoot. Vulkan compositor 결과를 SHM/X11로 표시한다. | 830용 driver·buffer 실험 참고용. Phosh를 Omarchy로 대체하지 않는다. 해당 구성의 GTK 앱은 Cairo이며 앱 전체 GPU 가속을 증명하지 않는다. |

A의 구조·Chromium XWayland 선택은 [architecture.md](https://github.com/BlackFireAlex/omarchy-android/blob/main/docs/architecture.md), GPU·sandbox 범위는 [README](https://github.com/BlackFireAlex/omarchy-android#readme)에서 확인했다. B의 native/PRoot 지원과 compositor 목록은 [Anland README](https://github.com/lfdevs/anland-termux#readme), 배포 패키지 조합은 [사용자 가이드](https://github.com/lfdevs/anland-termux/blob/main/docs/user-guide.md)에 있다. C의 렌더러 선택은 [Turnip build script](https://github.com/Azkali/phosh-termux-gpu/blob/main/fedora/3-build-turnip.sh)와 [launcher](https://github.com/Azkali/phosh-termux-gpu/blob/main/fedora/launch-gpu.sh)에서 읽었다.

## 2. 실제 nested Hyprland에 필요한 패치

공식 Termux [Weston recipe](https://github.com/termux/termux-packages/blob/master/x11-packages/weston/build.sh)는 `16.0.0`, DRM backend 비활성, GL renderer 활성, 기본 backend `headless`다. 실제 X11 호스트를 쓰려면 X11 backend를 명시해야 한다. recipe에 GL이 있다고 현재 기기의 hardware GPU나 zero copy가 확인되는 것은 아니다.

Aquamarine **v0.15.0**의 [Wayland backend](https://github.com/hyprwm/aquamarine/blob/v0.15.0/src/backend/Wayland.cpp#L91)는 parent Wayland 연결 후 `zwp_linux_dmabuf_v1`을 포함한 protocol을 요구한다. `initDmabuf()`는 feedback의 main device에서 DRM node를 구하고 연다. [Backend.cpp](https://github.com/hyprwm/aquamarine/blob/v0.15.0/src/backend/Backend.cpp#L148)는 DRM FD로 GBM allocator를 만든다. 따라서 “Weston이 실행되고 Turnip Vulkan이 있다”만으로 stock nested Hyprland의 시작 조건을 충족한다고 판단할 수 없다. KGSL만 있는 Android에서는 **no-DRM allocator, SHM/Android buffer 전달, renderer/fence 수명**까지 맞는 패치가 필요하다.

BlackFire의 [실제 host launcher](https://github.com/BlackFireAlex/omarchy-android/blob/main/runtime/host/omarchy-android-start)는 patched Weston X11 module, Zink/Turnip, guest Hyprland, `AQ_NO_KMS_REQUIREMENT`와 Android buffer 관련 옵션을 연결한다. 이는 README에만 있는 계획은 아니다. 다만 이번 웹 도구에서 release tag의 `patches.lock`/패치 본문은 읽지 못했다. **정확한 release의 패치 적용 결과와 binary closure는 설치 전 별도 검증 대상**이다. 환경 변수 이름만으로 upstream allocator gate가 안전하게 제거됐다고 판정하지 않는다.

## 3. KGSL / Turnip / Adreno 830

현재 읽은 공식 Termux [Mesa recipe](https://github.com/termux/termux-packages/blob/master/packages/mesa/build.sh)는 `26.2.4`다. Gallium에 `llvmpipe,softpipe,virgl,zink`, ARM/aarch64 Vulkan에 `freedreno`, KMD에 `msm,kgsl`을 선택한다. [Freedreno subpackage](https://github.com/termux/termux-packages/blob/master/packages/mesa/mesa-vulkan-icd-freedreno.subpackage.sh)는 Turnip ICD와 generic Vulkan loader를 연결한다. **공식 recipe의 직접 Freedreno Gallium과 커뮤니티 KGSL Gallium은 구분**해야 한다.

lfdevs [native Mesa recipe](https://github.com/lfdevs/termux-packages/blob/dev/mesa/freedreno-kgsl/packages/mesa/build.sh)는 `26.3.0`과 Mesa commit `98f3d6229d61452cef80f8563af7c56ae599dc14`를 고정한다. ARM/aarch64에서 Vulkan과 Gallium 양쪽 `freedreno`, KGSL/MSM, EGL/GLX/GBM, X11/Wayland를 빌드한다. 해당 [native PR #25](https://github.com/lfdevs/termux-packages/pull/25)는 Draft다. 공식 Termux에 병합된 동일 기능으로 표시하면 안 된다.

830과 840은 [커뮤니티 device table](https://github.com/lfdevs/mesa-for-android-container/blob/adreno-main/src/freedreno/common/freedreno_devices.py)에서 서로 다른 generation이다. 830은 `a8xx_gen1`, 840은 `a8xx_gen2`다. 공식 패키지의 구형 unofficial 830 patch와 현재 커뮤니티 table도 동일하지 않으므로 **설치한 binary / recipe / device ID를 묶어서 검증**해야 한다. [Mesa 26.0 release notes](https://docs.mesa3d.org/relnotes/26.0.0.html)도 830 placeholder와 840 지원을 구분한다.

KGSL을 여는 데 성공해도 buffer export와 presentation은 다음 gate다. [Turnip loader](https://github.com/lfdevs/mesa-for-android-container/blob/adreno-main/src/freedreno/vulkan/tu_knl.cc)는 KGSL을 read/write로 열며, [KGSL backend](https://github.com/lfdevs/mesa-for-android-container/blob/adreno-main/src/freedreno/vulkan/tu_knl_kgsl.cc)는 DMA heap/ION 실패 시 external-memory-FD 기능이 사라지는 경로를 포함한다. CPU memcpy/SHM fallback과 실제 imported GPU buffer를 구분해야 한다.

Termux:X11 전체를 “software only”로 단정하지 않는다. [공식 PR #1053](https://github.com/termux/termux-x11/pull/1053)은 Present copy/compositing의 GPU offload 변경으로 병합돼 있다. 반면 Phosh 후보 자체는 Vulkan→SHM 경로를 명시한다. 실제 설치 APK/CLI의 commit과 선택한 경로를 별도로 확인해야 한다. 공식 [nightly recipe](https://github.com/termux/termux-packages/blob/master/x11-packages/termux-x11-nightly/build.sh)는 moving nightly와 `SKIP_CHECKSUM`을 사용하므로 nightly라는 이름만으로 artifact를 고정할 수 없다.

## 4. 고정 가능한 입력과 아직 mutable인 입력

| 항목 | 읽은 pin / 범위 |
|---|---|
| BlackFire release | [v0.1.1](https://github.com/BlackFireAlex/omarchy-android/releases/tag/v0.1.1), tag commit `c189d33bf34a7a50fad3ff46bbd97e5c29b48910` |
| release bundle | [main/release.lock](https://github.com/BlackFireAlex/omarchy-android/blob/main/manifest/release.lock): `omarchy-android-aarch64-0.1.1.bundle.tar`, SHA-256 `7e9f1cd67533bc0d3988b5cb3831aef52f1527dd90391d9d868ed9345021cdb2` |
| BlackFire source lock | [main/components.lock](https://github.com/BlackFireAlex/omarchy-android/blob/main/manifest/components.lock): Hyprland `5c9377c15f85c50648f35ca5a213754f95b93ca0`, Aquamarine `a79fb21b2e2a82dd061a6d071802bcf38bd5c383`, Weston `015b3b4d4c05da44a22349ea6e651d1a8f678c59`, Mesa `98f3d6229d61452cef80f8563af7c56ae599dc14` |
| lfdevs native Mesa release | [freedreno-26.3.0-devel-20260824](https://github.com/lfdevs/termux-packages/releases/tag/freedreno-26.3.0-devel-20260824), recipe commit `ccc9cc550efc604188242285f99884183596ebb0` |
| native Mesa artifacts | `mesa_26.3.0_aarch64.deb`: `53ddf6d2636c56e859e82ff3bb881b76779b434ba3776b9d2a6546c57595f8da`; ICD: `0e28474b0023ff16f918624a16e67699f883654f63d817d8a8947a6dfa532cb4` |

위 release/hash는 **출처의 lock/release 값**이며 다운로드 바이트 검증을 수행한 결과가 아니다. BlackFire main은 release 후 추가 commit이 있고, tag manifest를 이번에 열지 못했으므로 main lock과 release bundle의 동일 closure를 추정하지 않는다. 공식 Termux의 현재 HEAD SHA는 웹 도구에서 확보하지 못했다. 공식 recipe·Anland guide·Phosh main은 조사 시점의 mutable source로 남긴다. Anland Weston은 guide가 별도 `freedreno-26.2.0-devel-20260709-weston` 조합을 지정하므로 KWin용 Mesa를 임의로 혼합하지 않는다.

## 5. 설치기 / 시작기를 그대로 실행하기 전 수정할 경계

[BlackFire installer](https://github.com/BlackFireAlex/omarchy-android/blob/main/lib/install.sh)는 새 container/prefix와 bundle checksum을 검사하지만 기존 Termux에 패키지를 설치한다. `tar`의 path 검사만으로 symlink target·nofollow extraction 전체가 검증됐다고 볼 수 없다. [options](https://github.com/BlackFireAlex/omarchy-android/blob/main/lib/options.sh)의 GPU auto 선택은 KGSL read/write 접근을 사용하며 실제 렌더링 검증은 아니다.

host launcher에서는 고정 X11/Wayland socket 삭제, PID/command 기반 stale process 종료, Termux:X11 preference 변경, wake lock, 기본 PulseAudio TCP 및 microphone source가 확인됐다. 현재 사용자 세션을 보존하려면 새 container·nonce runtime·미사용 DISPLAY/socket을 소유하고 PID/UID/birth로 종료를 제한하며, 설정은 compare/restore해야 한다. 첫 공개 GPU/input 실험은 audio·host sharing을 끈다. 이 제한은 installer 재사용 범위를 정하기 위한 실제 source finding이다.

기존 Termux의 배포 서명과 data는 유지한다. [공식 Termux 설치 정책](https://github.com/termux/termux-app#installation) 및 [Termux:X11](https://github.com/termux/termux-x11#readme)의 shared-UID 조건을 먼저 확인한다. F-Droid/GitHub 혼합 plugin을 설치하기 위해 Termux를 삭제하는 경로는 채택하지 않는다. 기존 Loopy의 literal RUN_COMMAND·owned supervisor·compare/restore는 실행기 안전 계약으로 재사용할 수 있지만 이전 i3/software 구현은 Hyprland/GPU 증거가 아니다.

## 6. ROOT가 실행할 최소 다음 gate

1. **실제 Termux production UID/context**에서 버전·서명·package source를 읽고 KGSL/GPU model·DMA heap/ION/DRM node 접근을 확인한다. `run-as`의 추가 group/context 결과는 준비에만 사용한다. `id`, `gpu_model`, device node mode/SELinux label, `dpkg-query`/`apt-cache policy`가 선행 metadata다. device node read/write만으로 SELinux ioctl·Vulkan 성공을 선언하지 않는다.
2. 소유된 새 prefix/container에서 검증한 driver closure로 **최소 Vulkan/EGL render 및 buffer-export/import**를 확인한다. loader enumeration, hardware renderer, 정확한 공개 장면, frame completion/presentation을 나눠 기록한다. 기존 Termux HOME·패키지·X11 preferences에 쓰는 변경은 사전에 목록과 복원 값을 고정한다.
3. 미사용 X11 display와 nonce Wayland socket에서 **Weston → 실제 patched Hyprland → Foot 공개 fixture** 한 개를 실행한다. 실제 Hyprland socket/output, Foot native Wayland, modifier/key repeat/Alt font zoom·mouse motion/click/scroll·resize·focus loss·normal close·재시작을 확인한다. 자기 PID/birth/SID만 종료하고 모든 자식·socket 부재를 확인한다. renderer name, refresh 설정 또는 RAF만으로 낮은 latency/physical FPS를 수락하지 않는다.
4. 이 gate가 통과하면 Omarchy Shell/launcher/settings/audio와 공개 browser를 차례로 붙인다. BlackFire의 Chromium sandbox-off 정책과 XWayland 예외는 별도 명시적 결정이다. 사용자가 X11 호스트를 허용했다는 사실만으로 browser sandbox 정책도 승인됐다고 취급하지 않는다.

기존 [2026-10-06 native Termux 기록](../native-termux-validation.md)은 i3/X11 emulator 실험이며 세 receipt 전체 FAIL을 보존한다. [Termux:GUI/Sway 연구](termux-wayland-gui.md)는 Bionic Wayland allocator/input 참고 자료다. 두 기록 모두 이번 태블릿의 Hyprland·830 GPU·물리 키보드/마우스 수락을 대신하지 않는다. 현재 연구에서 직접 확인하지 못한 release 패치·binary provenance·기기 동작은 계속 UNKNOWN이다.
