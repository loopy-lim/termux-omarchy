# 외부 런타임 출처와 라이선스

## 저장소 라이선스 (2026-10-21)

이 저장소의 자작 코드는 루트 [`LICENSE`](../LICENSE)(MIT)를 따른다. 파일·디렉터리
단위의 예외:

- `third_party/pacman-vercmp/` — 수정 없는 Pacman/libalpm 7.1.0 `version.c` 원본과
  GPL-2.0-or-later 전문을 그대로 보존한다(아래 Pacman 절).
- `native/proot-compat/*.patch` — GPL-2.0-or-later인 PRoot에 대한 수정이며,
  이 패치 파일들은 같은 라이선스로 배포된다(아래 PRoot 절).
- `android/assets/omarchy-native/`의 Hyprland·Aquamarine·hyprtoolkit ELF는
  upstream BSD-3-Clause의 빌드 산출물이고, 대응 소스·커밋·라이선스는 아래
  Omarchy 그래픽 후보 절과 `native/omarchy/patches/*.json`에 기록돼 있다.

## 별도 Arch rootfs용 Zstandard 디코더 (2026-10-07)

[Zstandard 1.5.7](https://github.com/facebook/zstd/releases/tag/v1.5.7)의 커밋
`f8745da6ff1ad1e7bab384bd1f9d742439278e99`와 아카이브 SHA-256은
`zstd.lock.json`에 고정한다. 이중 라이선스 중 BSD-3-Clause를 선택하며,
공식 소스의 `LICENSE` 전문은 디코더와 함께 APK의 `ZSTD-LICENSE.txt`에 포함한다.
`tools/build_zstd_android.py`는 NDK 27.1.12297006으로 API28 ARM64 공유 라이브러리를
빌드한다. 앱에 포함한 디코더를 사용하므로 Android 내부 라이브러리에 의존하지 않는다.
압축 창은 최대 128MiB, 해제 스트림은 최대 16GiB로 제한하고, 전체 Arch rootfs에는
별도 PAX 추출기와 설치 경로를 사용한다. 기존 Alpine asset의 제한은 유지한다.
라이브러리·소스·라이선스 영수증이 일치할 때만 빌드에 포함한다.
호스트 JNI 테스트와 ARM64 빌드는 Android 앱 UID 설치 또는 실기기 수락과 구분한다.

## 선택적 Android VirGL bridge (2026-10-06)

VirGL 1.3.0와 libepoxy 1.5.10 소스, Termux Android 패치를
[virgl.lock.json](virgl.lock.json)의 SHA256/커밋으로 고정하고
`tools/build_virgl_android.py`로 Android NDK 27.1.12297006 API28 ARM64 PIE를 빌드한다.
두 upstream의 MIT 라이선스와 Termux 패치 라이선스 원문은 APK의
`VIRGL-LICENSES.txt`에 포함한다. 정적 libepoxy는 Android 시스템 EGL/GLES를 런타임에 연결한다.
ANGLE, Venus, GBM, X11, DRM renderer와 video는 이 빌드에 포함하지 않는다.
실행 파일과 소스 영수증이 일치할 때만 APK에 패키징하며, 서버 실패는 기존 CPU 데스크톱으로 이어진다.
빌드 성공은 앱 UID의 vtest/FD 전달, 게스트 GL 픽셀, 실기기 GPU 가속 합격을 뜻하지 않는다.

확인일: 2026-10-05. 다운로드 대상과 크기·SHA-256은
[runtime.lock.json](runtime.lock.json)에 고정되어 있다. 아래 라이선스는 원 프로젝트의
공개 소스와 Alpine 이미지 내부 패키지 기록에서 확인했다.
다운로드 파일과 설치 스크립트는 호스트에서 실행하지 않는다.

## PRoot와 별도 loader

- 바이너리 제공자: [Local Desktop](https://github.com/localdesktop/localdesktop.github.io/tree/e6a8b580a3376e842cca2e44327a99498d7fb6dc),
  커밋 `e6a8b580a3376e842cca2e44327a99498d7fb6dc`의 `assets/libs/arm64-v8a/`.
- 사용 파일: `libproot.so`와 `libproot_loader.so`. 두 파일 모두 ELF64,
  little-endian, AArch64(`e_machine=183`)로 직접 확인했다.
- 대응 소스: 같은 커밋의
  [PRoot 소스와 Android/APK 패치](https://github.com/localdesktop/localdesktop.github.io/tree/e6a8b580a3376e842cca2e44327a99498d7fb6dc/patches/build-proot-android).
  [빌드 설정](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/patches/build-proot-android/config)은
  Termux PRoot `ab2e3464d04483b98a0614b470f3f8950d5a6468`과 talloc `2.4.3`을 지정한다.
- PRoot 라이선스: `GPL-2.0-or-later`.
  [COPYING](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/patches/build-proot-android/build/proot/COPYING)과
  [loader 소스의 라이선스 선언](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/patches/build-proot-android/build/proot/src/loader/loader.c)을 확인했다.
  PRoot 및 CARE 원 저작권자는 STMicroelectronics이며 loader 소스는
  Copyright (C) 2015 STMicroelectronics를 명시한다.
- PRoot는 talloc을 정적으로 포함한다. upstream
  [설명](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/patches/build-proot-android/README.md)과
  [정적 라이브러리 빌드](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/patches/build-proot-android/make-talloc-static.sh)를 확인했다.
  talloc `2.4.3`은 `LGPL-3.0-or-later`이며,
  [공식 소스 아카이브](https://download.samba.org/pub/talloc/talloc-2.4.3.tar.gz)의
  `talloc.c`와 `talloc.h`가 이 조건을 명시한다. 저작권은 Andrew Tridgell,
  Stefan Metzmacher를 포함한 기여자에게 있다. 확인한 소스 아카이브는 684,092바이트,
  SHA-256 `dc46c40b9f46bb34dd97fe41f548b0e8b247b77a918576733c528e83abd854dd`다.
- 빌드 스크립트의 별도 라이선스는
  [MIT](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/patches/build-proot-android/LICENSE),
  Copyright (c) 2023 green-green-avk다. Local Desktop 자체의
  [최상위 라이선스](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/LICENSE)는
  GPL-3.0이다. 각 구성요소의 선언을 개별 기록한다.

2026-10-06의 Firefox 콘텐츠 샌드박스 호환 실험은 위 고정 소스의
`src/tracee/event.c`에 [작은 패치](../native/proot-compat/0001-forward-tagged-sigsys.patch)를
적용한 Android ARM64 PRoot를 사용한다. `tools/build_proot_compat.py`는 고정 커밋·트리·
원본 파일 해시를 확인하고 NDK 27.1.12297006으로 재빌드한다. 수정 PRoot를 담는 APK에는
loader도 **같은 빌드에서 나온 짝**을 써야 한다. 원래 Local Desktop loader의
`pokedata_workaround` 오프셋은 928바이트, 수정 PRoot가 기대하는 새 loader의 오프셋은
1016바이트라 서로 섞을 수 없다. 새 PRoot의 대응 소스와 talloc 정적 라이브러리·
오브젝트, 빌드 도구·패치·라이선스 전문 및 짝 loader는
`build/deliverables/LoopyDesktop-2026-10-06-proot-source-registers.tar.gz`에 묶는다.
양수 SIGSYS를 전달하기 전에 실제 signal stop의 레지스터를 다시 읽어 ARM64의
syscall stop용 임시 x7 값이 guest 시그널 컨텍스트에 쓰이지 않게 했다.
`proot-source-paired.tar.gz`는 이 추가 수정 전의 별도 진단 자료로 보존한다.
이전 `LoopyDesktop-2026-10-06-proot-source.tar.gz`는 원래 loader를 쓴 별도
`run-as` 진단의 당시 자료로만 보존한다.
번들의 `source/`는 대응 소스 검토용이다. 저장소의
`python3 tools/build_proot_compat.py`는 고정 Local Desktop Git checkout을
`build/proot-compat/localdesktop`에서 확인하거나 공식 원격에서 해당 커밋을 받는다.
소스 번들은 로컬 전달물이며 동일 바이트 재현성과 외부 배포 의무 충족을 보증하지 않는다.

초기 고정 바이너리와 공개 소스의 출처를 보존한 상태이나, 그 원래 바이너리를 같은 소스로
동일 바이트로 재생성하는 빌드 검증은 수행하지 않았다. APK를 외부 배포할 때는 GPL/LGPL 조건에 맞는
라이선스 전문, 전체 대응 소스, 필요한 재링크 자료와 수정 사항을 함께 제공해야 한다.
이 NOTICE만으로 그 배포 의무를 모두 충족했다고 판정하지 않는다.

## Alpine Linux ARM64 minirootfs 3.22.6

- 제공자: [Alpine Linux 공식 aarch64 릴리스 디렉터리](https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/aarch64/).
- 파일: [alpine-minirootfs-3.22.6-aarch64.tar.gz](https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/aarch64/alpine-minirootfs-3.22.6-aarch64.tar.gz).
- SHA-256: `821565fa8f3953eefd12497b166b4b50add2f7c57fb312e75862f5867e06fefe`.
  [공식 SHA-256 파일](https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/aarch64/alpine-minirootfs-3.22.6-aarch64.tar.gz.sha256)과 실제 다운로드를 대조했다.
- 이미지 내부 `etc/alpine-release`는 `3.22.6`이며 `bin/busybox`는 AArch64 ELF다.
- 패키지 소스·빌드 정의: [Alpine aports 3.22-stable](https://gitlab.alpinelinux.org/alpine/aports/-/tree/3.22-stable).
  각 패키지의 정확한 버전·origin·라이선스는 이미지 내부 `lib/apk/db/installed`에 보존된다.

전체 이미지에 단일 라이선스를 적용하지 않는다. 아래는 **고정된 이미지 내부 APK DB**에서
읽은 패키지 라이선스다. 추가 패키지는 이번 이미지에 포함하지 않는다.

| 패키지 | 버전 | SPDX 라이선스 |
| --- | --- | --- |
| alpine-baselayout | 3.7.0-r0 | GPL-2.0-only |
| alpine-baselayout-data | 3.7.0-r0 | GPL-2.0-only |
| alpine-keys | 2.5-r0 | MIT |
| alpine-release | 3.22.6-r0 | MIT |
| apk-tools | 2.14.12-r0 | GPL-2.0-only |
| busybox | 1.37.0-r20 | GPL-2.0-only |
| busybox-binsh | 1.37.0-r20 | GPL-2.0-only |
| ca-certificates-bundle | 20260909-r0 | MPL-2.0 AND MIT |
| libapk2 | 2.14.12-r0 | GPL-2.0-only |
| libcrypto3 | 3.5.8-r0 | Apache-2.0 |
| libssl3 | 3.5.8-r0 | Apache-2.0 |
| musl | 1.2.5-r12 | MIT |
| musl-utils | 1.2.5-r12 | MIT AND BSD-2-Clause AND GPL-2.0-or-later |
| scanelf | 1.3.8-r1 | GPL-2.0-only |
| ssl_client | 1.37.0-r20 | GPL-2.0-only |
| zlib | 1.3.2-r0 | Zlib |

## Linux WebKit 브라우저

데스크톱 이미지는 `desktop.lock.json`에 고정한 Alpine ARM64
`webkit2gtk-4.1` `2.48.1-r1` 패키지의
`/usr/libexec/webkit2gtk-4.1/MiniBrowser`를 포함한다. WebKitGTK와 JavaScriptCore는
`LGPL-2.0-or-later AND BSD-2-Clause`이며, 정확한 패키지 SHA-256과 종속 패키지의
라이선스·출처는 잠금 파일과 이미지의 `usr/share/loopy/DESKTOP-NOTICE.txt`에 기록한다.
[Alpine 빌드 정의](https://gitlab.alpinelinux.org/alpine/aports/-/blob/e9caef1999c50e8a16d8cfaf287b9d83adc59880/community/webkit2gtk-4.1/APKBUILD)는
GTK3 MiniBrowser 빌드를 활성화한다. 대응 upstream 소스는
[WebKitGTK 2.48.1](https://webkitgtk.org/releases/webkitgtk-2.48.1.tar.xz)이다.

브라우저는 Wayland와 CPU 렌더링을 사용한다. GTK3 MiniBrowser의 추가 WebKit
프로세스 샌드박스는 upstream 기본값이 꺼져 있으며, 이 실행 경로도 추가 Linux
namespace 샌드박스를 제공하지 않는다. PRoot는 보안 경계가 아니고, 브라우저의
기본 격리는 실제 Android 앱 UID·SELinux·앱 프로세스 정책에 의존한다.
명시적으로 WebKit 샌드박스를 켠 별도 `run-as` 진단에서는 bubblewrap이
`/proc/sys/kernel/overflowuid` 읽기를 거부당해 브라우저가 시작하지 못했다.
이 진단의 SELinux 도메인·seccomp 상태는 일반 앱 실행의 검증과 구분한다.
기존 Firefox HOME 파일은 패키지 교체 시 삭제하지 않는다.

Python에서 GTK3·WebKit introspection API를 사용하는 바인딩은 Alpine ARM64
`py3-gobject3` `3.52.3-r1`이며 `LGPL-2.1-or-later`다. 패키지 SHA-256과
`python3~3.12` ABI 의존성은 `desktop.lock.json`에 고정한다.
[고정 Alpine 빌드 정의](https://gitlab.alpinelinux.org/alpine/aports/-/blob/9ede4ceeac372a129fcec83a631324338c826fb7/main/py3-gobject3/APKBUILD)의
대응 원본은 [GNOME PyGObject 3.52.3 소스](https://download.gnome.org/sources/pygobject/3.52/pygobject-3.52.3.tar.gz)다.
Python 바인딩을 추가해도 위 Android 격리 경계나 별도 Linux 샌드박스 상태는 바뀌지 않는다.

## 다운로드·검증 사용법

작업 디렉터리와 무관하게 `python3 tools/fetch_runtime.py`는 이 저장소의 `build/runtime/`를
기본 출력으로 사용한다. `--output <디렉터리>`로 출력 위치만 변경할 수 있다.
다운로드 URL이나 잠금 파일을 바꾸는 CLI 옵션은 제공하지 않는다.

크기·SHA-256·ELF 아키텍처와 rootfs 버전을 검증한 캐시는 네트워크 없이 재사용한다.
각 다운로드는 잠긴 파일 크기, 소켓 제한 30초, 전체 제한 180초로 제한하며 리다이렉트를 거부한다.
필요한 모든 파일의 검증이 끝난 뒤에만 임시 파일을 `os.replace`로 개별 교체한다.
무결성 검증 실패 시 기존 파일을 교체하지 않고 임시 디렉터리를 제거한다.
APK 빌드 성공, 앱 UID 실행, VM 및 실제 기기 동작은 별도 검증 단계다.

## 태블릿의 개인 셸 프로필

현재 Mac의 Powerlevel10k 테마, 프롬프트 설정과 Oh My Zsh Git 플러그인·함수를
Linux 셸 프로필로 적용했다. 각 원본의 SHA-256은
`docs/validation/2026-10-06-y900-tablet-fit/mac-shell-source.json`에 기록한다.
Powerlevel10k와 Oh My Zsh의 MIT 라이선스는 rootfs의
`/usr/share/loopy/shell/powerlevel10k/LICENSE`, `/usr/share/loopy/shell/OMZ-LICENSE`에 포함한다.
Mac의 바이너리, 셸 기록, SSH 개인 키와 인증 환경 변수는 포함하지 않는다.

JetBrainsMono Nerd Font Mono Regular는 현재 Mac에 설치된 폰트의 동일 바이트를
사용한다. [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono)의 OFL과
[Nerd Fonts 라이선스](https://github.com/ryanoasis/nerd-fonts/blob/v3.4.0/LICENSE)를
폰트와 함께 `/usr/share/fonts/truetype/`에 포함한다.

## 실제 Omarchy 그래픽 후보의 소스

Omarchy 원본은 MIT 라이선스의 `omacom/omarchy`
`81145eb1fd41532fcae4310b26f860608e2eaf82`다. 실제 그래픽 후보는
BSD-3-Clause의 [Hyprland](https://github.com/hyprwm/Hyprland/tree/efb50993780079460b0cbed1363e2166a2de1d9f)
및 [Aquamarine](https://github.com/hyprwm/aquamarine/tree/f31c47a1b9d300847d8fc3108ad959448103dfc1)
소스를 사용한다. 각 소스 아카이브 SHA-256과 upstream commit은
`omarchy.lock.json`에, 수정 전후 파일 SHA-256은 `native/omarchy/patches/`에 기록한다.
별도 소스 후보마다 원본 `LICENSE`를 보존한다. 이 후보들은 현재 배포 APK에
포함된 완성 Omarchy라는 뜻이 아니다.

Hyprland 빌드 입력은 MIT의 Glaze `b518eec7a22e56ffa238b072c07f47efa7cea97f`
(v7.2.0), BSD-2-Clause의 udis86 `5336633af70f3917760a6d441ff02d93477b0c86`,
BSD-3-Clause의 hyprland-protocols `bd153e76f751f150a09328dbdeb5e4fab9d23622`다.
원본 Git blob와 아카이브 SHA-256을 확인했고, 각각의 `LICENSE`를 소스와 함께
보존한다. udis86와 protocol 입력은 Hyprland의 정확한 submodule pin이며,
Glaze는 해당 Hyprland가 요청하는 v7.2.0이다.


## Separate Omarchy remote clients (2026-10-08)

The fixed Arch ARM extension retains package-provided notices and licenses for Remmina, FreeRDP, LibVNCServer, libappindicator, libcbor, libfido2, SDL3_ttf and VTE. Exact versions, package hashes, license identifiers and official build-system signatures are recorded in `android/assets/omarchy-remote-client.provenance.json`. The complete image and user HOME are preserved. Only the RDP and VNC Remmina plugins enter the runtime plugin bind. Remmina corresponding upstream source: https://gitlab.com/Remmina/Remmina/-/tree/v1.4.43 .

The build-time Arch version comparator uses the unmodified original Pacman/libalpm 7.1.0 `version.c`, under GPL-2.0-or-later. Source and GPL text are retained in `third_party/pacman-vercmp/`; only a minimal build-host header supplies the export macro and standard allocator declarations. The comparison algorithm is unchanged. The library is compiled in a temporary host directory and is not shipped as an Android executable. Original source: https://gitlab.archlinux.org/pacman/pacman/-/blob/v7.1.0/lib/libalpm/version.c .
