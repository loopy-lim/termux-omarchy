# TB522FU의 내부 Linux 브라우저: 다음 실행 경로

확인일 2026-10-08. 목표는 Omarchy 내부의 실제 native Wayland 브라우저와 유지되는 renderer sandbox다. Android 외부 앱 실행, sandbox 해제, OS unlock/flash는 이 목표의 대체 완료 조건이 아니다. 이 문서 작성에서는 다운로드·컴파일·테스트·기기 실행을 하지 않았다.

가장 작은 다음 실행 후보는 **stock Linux Firefox의 기본 sandbox 시험**이다. Chromium을 계속 사용하려면 **검증된 별도 Linux 커널 환경**, 또는 **Android 프로세스 격리를 실제 renderer launcher에 연결하는 포트**가 필요하다. Termux의 Wayland flag만 켜는 재빌드는 보안 문제를 해결하지 않는다. Firefox 후보 역시 아래 소스에 근거한 추론이며 현재 태블릿 합격이 아니다.

## 현재 실제 증거

| 항목 | 관찰과 한계 |
| --- | --- |
| 현재 제품 | APK `e76bd44f8b5458b4c402774791f1cddaf1bf382328d206f74e7f923e5ba88b0e`, 실제 앱 UID 10330. [공개 Chromium 13](../../build/diagnostics/y900-chromium-inside-public-20261008-13/receipt.json)의 기본 arm은 SUID helper fatal로 종료했다. |
| canonical 시작 UI | [공개 native UI](../../build/diagnostics/y900-browser-native-public-20261008-01/receipt.json)는 sandbox 인자 변경 없이 실제 Wayland 시작 창에서 `SUID_SANDBOX` 고정 오류를 보이고 정리됐다. 이 receipt의 `passed=true`는 **오류 UI와 정리**의 합격이다. 브라우저 사용 가능 합격이 아니다. |
| 제한된 출력 진단 | 같은 Chromium 13의 명시적 sandbox 해제 arm은 공개 offline native Wayland 창과 CDP를 확인했다. `gpu_verified=false`, `physical_presentation_verified=false`; 보안·GPU·60 FPS 합격이 아니다. |
| namespace | 별도 disposable 앱의 `unshare(CLONE_NEWUSER)`는 EINVAL 22였다. 더 강한 같은 기기 [이전 커널 설정 증거](../../build/diagnostics/y900-recovery-input-20261008-01/kernel-config1148-01.json)는 `USER_NS`, `PID_NS` 미설정과 `SECCOMP_FILTER=y`를 기록한다. 이전 APK 기록을 현재 브라우저 실행 합격으로 재사용하지 않는다. |
| 현재 AVF | [현재 e76 사전 검사](../../build/diagnostics/y900-browser-platform-capability-20261008-01/receipt.json): AVF feature/APEX/`vm` CLI 존재, shell의 `MANAGE_VIRTUAL_MACHINE`·`USE_CUSTOM_VIRTUAL_MACHINE` 허용. [실제 `vm info`](../../build/diagnostics/y900-browser-platform-capability-20261008-01/vm-capability.json): **protected VM만 지원**, `/dev/kvm` 없음, VFIO 미지원, assignable devices 없음, OS 목록 `microdroid`, log/ramdump/adb debug policy 모두 false. **VM 시작은 하지 않았다.** |

설치 rootfs의 Chromium ELF는 325,782,488 B, SHA-256 `8dee915b6acdd643cdb4198666c29c96e5ffec0ba39bd3338be3d49884eddf13`이다. [rootfs manifest](../../build/deliverables/Omarchy-2026-10-07-arm64-output-orientation-rootfs/manifest.json)에는 Chromium·WebKitGTK와 `qemu-user-static`이 있고 Firefox·`qemu-system`은 없다. 사용자 실행 에뮬레이터는 별도 guest 커널을 제공하지 않는다. 현재 [RuntimeSession](../../android/src/dev/loopy/desktop/RuntimeSession.java)은 실제 kernel UID를 유지한다. PRoot의 가상 root 소유 표시가 SUID 권한을 만들지는 않는다.

## 후보별 필요한 작업

| 경로 | 공식 소스에서 확인한 조건 | 다음 판단 |
| --- | --- | --- |
| Bionic Chromium + Wayland | [Termux Chromium recipe](https://raw.githubusercontent.com/termux/termux-packages/master/x11-packages/chromium/build.sh)는 `ozone_platform_wayland=false`, X11/headless=true이며 SUID/Android seccomp 제약을 설명한다. [1001 패치](https://raw.githubusercontent.com/termux/termux-packages/master/x11-packages/chromium-host-tools/cr-patches/1001-chromium-disable-sandbox.patch)는 내부에서 no-sandbox를 추가한다. | Bionic/Termux prefix를 Loopy ABI·경로에 맞추고 Wayland dependency/renderer를 빌드해야 한다. 내부 sandbox 해제 패치를 없애는 것에 더해 실제 안전한 child launcher가 필요하다. 현재 커널에서 Linux namespace/SUID를 그대로 요구하는 launcher로는 해결되지 않는다는 소스 기반 판단이다. |
| stock Linux Firefox | [Mozilla SandboxLaunch](https://raw.githubusercontent.com/mozilla-firefox/firefox/main/security/sandbox/linux/launch/SandboxLaunch.cpp) 275–314행은 seccomp·sandbox library/reporter 설정 뒤 user namespace가 없으면 추가 namespace 설정만 건너뛴다. [Sandbox.cpp](https://raw.githubusercontent.com/mozilla-firefox/firefox/main/security/sandbox/linux/Sandbox.cpp)는 content broker와 실제 seccomp filter 설치를 수행한다. | Chromium의 namespace/SUID 시작 계약과 달라 가장 작은 독립 후보다. namespace가 없는 보호는 정상 Linux의 모든 격리와 같다고 주장할 수 없다. 현재 PRoot/SIGSYS 전달과 실제 content filter 동작은 아직 시험하지 않았다. |
| Termux Firefox | [공식 mozconfig](https://raw.githubusercontent.com/termux/termux-packages/master/x11-packages/firefox/mozconfig.cfg)는 X11-only와 `--disable-sandbox`, `--disable-hardening`을 사용한다. | stock Linux Firefox 후보와 다르며 현재 요구의 그대로 사용 가능한 대안이 아니다. |
| AVF protected Linux VM | AVF에는 raw config 경로가 있다. 그러나 허용된 caller, image label, 보호 VM image 검증은 별개다. 현재는 protected-only이며 임의 distro kernel boot가 확인되지 않았다. | 아래 AVB/firmware 조건을 먼저 확인한다. `microdroid` 목록만으로 raw config 불가라고 단정하지도, desktop VM 가능이라고 인정하지도 않는다. |
| QEMU full-system TCG | [QEMU 공식 문서](https://www.qemu.org/docs/master/system/introduction.html)의 TCG는 CPU 에뮬레이션으로 별도 guest 커널을 실행한다. | host namespace 제약을 별도 커널로 분리할 수 있는 후보지만, 현재 패키지가 없고 성능·native Wayland 전달이 미검증이다. 빠른 전체 브라우저 또는 60 FPS를 예상 합격으로 계산하지 않는다. |

Chromium [Linux zygote](https://raw.githubusercontent.com/chromium/chromium/main/content/browser/zygote_host/zygote_host_impl_linux.cc) 94–145행은 사용자 namespace 또는 유효한 SUID helper를 선택하고 둘 다 없으면 중단한다. [Ozone](https://chromium.googlesource.com/chromium/src/+/main/docs/ozone_overview.md)은 화면/입력 backend이므로 이 보안 계약을 대체하지 않는다. Android의 [isolated service](https://developer.android.com/guide/topics/manifest/service-element#isolated)를 renderer에 쓰는 방법은 별도 UID·제한된 IPC/FD broker·lifecycle 포트가 필요하다는 설계 추론이다. manifest 한 줄로 Linux zygote가 전환되지는 않는다.

## protected-only AVF와 custom kernel 경계

고정 upstream [virtmgr commit `5f8e75df64e6f6cb64b7e10930e98784327a20a4`](https://android.googlesource.com/platform/packages/modules/Virtualization/+/5f8e75df64e6f6cb64b7e10930e98784327a20a4/android/virtmgr/src/aidl.rs)의 `create_vm_internal`은 MANAGE 권한, raw/custom의 USE_CUSTOM 권한, protected kernel/initrd와 partition label을 따로 검사한다(437–528, 701–706, 1183–1220행). 앱 private data label은 허용 목록에서 제외된다. `getSupportedOSList()`는 app config 목록이다(958–974행). 같은 snapshot은 protected `networkSupported`를 거절하며 GPU/display 설정도 빌드 기능에 의존한다(583–618행). 이 소스를 Lenovo 설치본과 동일하다고 주장하지 않는다.

[Android 16 pvmfw README](https://android.googlesource.com/platform/packages/modules/Virtualization/+/refs/heads/android16-release/guest/pvmfw/README.md)는 Linux 배포판을 허용 가능한 환경으로 설명하지만 다음 boot 조건을 요구한다: kernel 영역의 appended VBMeta, 필요시 그 VBMeta에 포함된 ramdisk hash descriptor(`initrd_normal`/`initrd_debug`), 유효한 platform DICE handover와 guest identity/instance·rollback 계약. 일반 배포판 kernel/initrd를 raw config에 넣는 것만으로 이 조건을 만족하지 않는다.

[AOSP 보안 문서](https://source.android.com/docs/core/virtualization/security)는 Google/OEM이 신뢰하는 서명과 AVB를 요구한다. [현재 pvmfw main](https://android.googlesource.com/platform/packages/modules/Virtualization/+/refs/heads/main/guest/pvmfw/src/main.rs) 234–241행은 `verify_payload(..., PUBLIC_KEY)`를 호출한다. 같은 소스 87–96행은 일부 Qualcomm QTVM의 검증을 TrustZone에 맡기는 별도 경로를 명시한다. **이 Lenovo의 firmware/verifier·허용 키·guest ABI 경로는 아직 미확인**이다. 자체 키로 footer를 붙였다는 사실은 vendor가 신뢰하는 image임을 입증하지 않는다.

[Microdroid 문서](https://source.android.com/docs/core/virtualization/microdroid)는 bootloader/boot/super/vbmeta 검증과 instance identity 보존을 설명하며, 기본 Microdroid는 Graphics/UI를 제공하지 않는다. 따라서 stock Microdroid boot 성공도 임의 desktop Linux·Chromium·GPU·네트워크·Wayland window 합격으로 확대할 수 없다. DICE는 측정된 guest identity의 증명/secret 파생 계약이며, 그 자체가 모든 OS image의 실행 허가가 아니다.

## 가장 작은 다음 gate

**Firefox:** [Arch Linux ARM의 aarch64 Firefox](https://archlinuxarm.org/packages/aarch64/firefox) 한 버전과 package/source identity를 고정한 독립 overlay로, 현재 exact APK의 production PRoot에서 공개 offline 페이지 한 개를 시험한다. 신선한 private HOME/profile, 기존 Wayland compositor, 기본 sandbox를 유지한다. `MOZ_DISABLE_*_SANDBOX`, 가짜 sandbox capability, sandbox level 감소는 사용하지 않는다. 현재 [tagged SIGSYS PRoot 패치](../../native/proot-compat/0001-forward-tagged-sigsys.patch)는 관련 seam이지만 기존 작은 syscall fixture 합격은 실제 Firefox 합격이 아니다.

판정은 실제 `xwayland=false`와 content process PID/birth, `NoNewPrivs`·추가 seccomp filter/broker 활성 증거, 고정 sandbox 상태 필드 및 소유 process/SID/profile 정리를 분리한다. [Mozilla 진단 필드](https://raw.githubusercontent.com/mozilla-firefox/firefox/main/toolkit/modules/Troubleshoot.sys.mjs) 중 `hasSeccompBPF`, `hasSeccompTSync`, `hasUserNamespaces`, `canSandboxContent`, `effectiveContentSandboxLevel`만 수집한다. 전체 about:support/profile/syscall 인자는 수집하지 않는다. Android에서 상속된 `Seccomp=2`나 preference 값만으로 Firefox filter가 설치됐다고 인정하지 않는다. 첫 시작이 성공하면 고정 공개 content의 실제 정책 거절을 별도로 확인한다. 시작·GPU·실제 표시 FPS는 후속 별도 판정이다.

**AVF:** 현재 e76의 feature/권한 검사와 `vm info`는 완료됐다. 가장 작은 추가 gate는 **설치된 signed guest config/image와 실제 firmware verifier의 identity·AVB 키/ABI 확인**이다. 먼저 고정 `/apex/com.android.virt/etc/microdroid.json`의 공개 시스템 설정을 읽고 그 설정이 참조하는 정확한 image의 SELinux label·digest·AVB metadata를 확인한다. 파일 미존재/읽기 거절은 그대로 미확인이다. installed firmware/key 계약을 확인할 수 없다면 arbitrary custom kernel은 미확인으로 유지한다. 그 뒤 명시적으로 소유된 최소 stock protected guest의 boot/stop/reap 시험이 service 실행 경계를 가르는 첫 실행 gate다. 이는 아직 수행되지 않았으며 distro build보다 앞선다. 이미 확인한 항목을 green 숫자를 위해 반복하지 않는다.

root 담당자의 읽기 전용 재확인 명령은 아래로 제한할 수 있다. 현재 동일 항목 반복은 필요하지 않다. 권한은 앱 manifest 선언이 아니라 실제 caller UID/PID로 `Context.checkPermission`/permission service를 확인해야 한다. CLI `run --help`는 VM 생성이 아니다.

```sh
id -u
pm list features | grep -Fx 'feature:android.software.virtualization_framework'
getprop ro.boot.hypervisor.vm.supported
getprop ro.boot.hypervisor.protected_vm.supported
dumpsys package com.android.shell | grep -E 'android\.permission\.(MANAGE_VIRTUAL_MACHINE|USE_CUSTOM_VIRTUAL_MACHINE): granted='
/apex/com.android.virt/bin/vm info
/apex/com.android.virt/bin/vm run --help
ls -lZ /apex/com.android.virt/etc/microdroid.json
head -c 65537 /apex/com.android.virt/etc/microdroid.json
```

[서비스 구조](https://source.android.com/docs/core/virtualization/virtualization-service)는 `virtmgr` child/RPC와 VM handle lifetime을 사용한다. 단일 `service check` 결과가 not-found여도 AVF 부재 결론은 성립하지 않는다. 새 backend도 VM handle·실제 child·정리 ownership을 유지해야 한다. `vm info`의 빈 assignable devices는 direct GPU assignment 증거가 없다는 뜻이며 모든 paravirtual GPU 부재의 증거는 아니다. kernel boot 가능성, sandbox 보호, 네트워크와 native Wayland 연결, 빠른 실제 표시를 각각 입증해야 한다.

## 입력 identity와 조사 한계

현재 e76 AVF receipt SHA-256은 `2e4ea4a7a5068858372451e1d8cf718cfb6252663197a218a47db9008fc128f2`, vm capability는 `c18952a907fa0d701aa6c2c11ff5e5d29bbad0c57dc2e7bb21c46b56427c35f6`이다. 현재 native 오류 UI receipt는 `a6f161fb200f33bd307db504a5035379c2424b596f2f0e4d77ab953582d925ff`, 공개 Chromium 13은 `4c1e3b1e0f387f4dc72bc3a792f6ce36ed6fd65ed38aa5fcf9d2a5e7b86032ce`이다.

기존 [primary source snapshot](../../build/diagnostics/chromium-wayland-20261008/primary-sources.json)은 Termux recipe `f9454f0bf5a951f1f34ded84cd1e3e27e0972e67b1705e9c2ac30452b4b6e678`, 내부 no-sandbox patch `c06537a43c1c6370ebc7d9780caf9301f6f870273bcbc973cfdca4a500ad21ab`를 고정한다. 이번 링크의 Chromium/Mozilla main·Termux master·AOSP release branch는 움직일 수 있다. 실제 port/시험 전에는 선택 버전의 정확한 commit/package와 모든 patch closure를 새로 고정해야 한다. upstream AVF commit과 현재 OEM 구현의 일치는 확인되지 않았다. 현재 확인된 경계는 stock Chromium 시작 실패, 제한된 offline 출력, AVF의 protected-only 사전 조건이며, 안전하고 빠른 전체 Linux 브라우저 완료는 아직 남아 있다.
