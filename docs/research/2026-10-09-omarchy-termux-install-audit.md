# Termux Omarchy 배포·설치 감사

2026-10-09. 고정 소스와 ROOT가 보존한 번들의 텍스트 metadata를 읽은 결과다. 이 작성자는 설치기·시작기·PRoot·GPU·기기 명령을 실행하지 않았다. 기존 Termux:X11을 출력 호스트로 쓰며 실제 patched Hyprland/Omarchy를 별도 컨테이너에서 검증한다.

## 고정한 입력

소스는 [v0.1.1 tag commit c189d33](https://github.com/BlackFireAlex/omarchy-android/tree/c189d33bf34a7a50fad3ff46bbd97e5c29b48910)이다. 보존된 source tar SHA-256은 `30a8b077d295c60be6b2d39da0d5271271f7916919ed4d261927217c37324831`이다. 태그의 [release.lock](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/manifest/release.lock)은 아직 **0.1.0 / c1af9f…**를 가리킨다. 그 installer의 기본 download 결과를 v0.1.1로 간주하면 안 된다.

ROOT가 선택·다운로드 바이트를 확인한 별도 [v0.1.1 bundle](https://github.com/BlackFireAlex/omarchy-android/releases/download/v0.1.1/omarchy-android-aarch64-0.1.1.bundle.tar)의 SHA-256은 `7e9f1cd67533bc0d3988b5cb3831aef52f1527dd90391d9d868ed9345021cdb2`이다. 로컬 `third_party/cache/omarchy-android-c189d33/bundle/BUNDLE-MANIFEST`는 format=1, version=0.1.1, architecture=aarch64를 선언한다. 보존된 SHA256SUMS의 핵심 값:

| 파일 | SHA-256 |
|---|---|
| rootfs.tar.xz | `dbee00c0cb41f6b213c153ff4dc1c0898ba99dd0543ac13cef1601820366e2c5` |
| patched Weston x11-backend.so | `8cfb78a4a1a146596228c34f55562c3325c10bc355a5dff5f5765ca77093ea0e` |
| BUNDLE-MANIFEST | `1eebd172b5b43657f819910bdafc905daf02df8a35dff5b40dac08000ee49c72` |
| packages-aarch64-0.1.1.lock | `1d2935de23e434f37731052ba868e9833cba541afd517ff4e130c832d397b550` |

manifest의 components/patches/artifacts lock hash는 각각 `4630710656d83b51c8fd6c80024f3c1977dc7c90f7ebf879baedb814c82abb77`, `cc4394dbc47a43b5da7fb27e7084d9f2e8688c7138e6f9def493059dbde066ee`, `eb1ffb44e115c5fac3ca3810ffef9143bcaaf7f764223c2dd5d34e3822b61159`이다. host artifact는 0.1.0의 `9dfabd5bb8bfcae7705aa90d5bad28414a12bf9e9b39337101f3ed92d4037fe4`, 그 source bundle은 `c1af9f82ab5c616f5fa7031f44b3ed17b1b07013169c9e19825b8131c057c1a1`로 선언된다. 버전 문자열만으로 host/guest source closure를 추정하지 않는다.

[components.lock](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/manifest/components.lock)의 정확한 revision:

| 구성 | revision |
|---|---|
| Omarchy | `158e8cfb3a03f7b390e4213eaf15edcea0dfaa98` |
| Hyprland | `5c9377c15f85c50648f35ca5a213754f95b93ca0` |
| Aquamarine | `a79fb21b2e2a82dd061a6d071802bcf38bd5c383` |
| Weston | `015b3b4d4c05da44a22349ea6e651d1a8f678c59` |
| Termux:X11 | `6d3c6883265b4ec8092673e6d2d61ef86cab5405` |
| Mesa fork | `98f3d6229d61452cef80f8563af7c56ae599dc14` |

## 원본 설치기를 그대로 실행하지 않는 이유

[lib/install.sh](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/lib/install.sh#L37)은 공용 Termux prefix에 패키지를 설치한다. `--bundle` checksum은 옆 sidecar에서 읽으므로 선택한 release의 독립 SHA pin을 먼저 대조해야 한다. tar member의 절대경로·`../` 검사는 있으나 링크 대상·중복 member·special file·누적 크기를 포괄하지 않는다. 새 staging은 regular files만 허용하고 이름·개수·전체 크기·각 SHA를 확인해야 한다.

원본은 bundle의 backend/native helper를 쓰지만 host scripts는 **PROJECT_SOURCE에서 복사**한다. [assemble-bundle.sh](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/builder/ci/assemble-bundle.sh#L150)의 lock digests와 installer source pin을 각각 보존한다. 원본 smoke는 실제 guest 프로그램을 실행하므로 정적 설치 완료와 GUI/GPU 수락을 분리한다.

[host start](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/runtime/host/omarchy-android-start#L346)는 이전 시작기/종료기 호출, 고정 X1·Wayland socket 삭제, command-name 기반 stale 프로세스 종료, 전역 X11 preferences/wake lock 변경을 포함한다. PulseAudio 기본 sink/source·TCP·microphone source도 설정한다. 새 관리 실행기에 가져오지 않는다. [options.sh](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/lib/options.sh)의 audio 기본값은 true이고 GPU auto는 KGSL 접근 검사이지 renderer 증거가 아니다.

## 최소 설치·실행 경로

1. 고정 새 container `loopy-omarchy`와 관리 root `$HOME/.local/share/loopy-omarchy`를 사용한다. 기존 container/legacy rootfs가 모두 없는지 확인한다. user HOME·storage를 guest에 bind하지 않는다. journal은 새 root의 UID/inode/token을 기록하고 불확실한 기존 경로를 채택·삭제하지 않는다.
2. 독립 outer SHA와 내부 manifest/checksum을 확인한 bundle만 관리 root `bundle/`에 준비한다. proot-distro 5.8은 `$PREFIX/var/lib/proot-distro/containers/loopy-omarchy/rootfs`를 쓴다. literal `proot-distro install --name loopy-omarchy --architecture aarch64 <owned rootfs.tar.xz>`로 새 rootfs를 설치한다. 기존 user profile을 건드리지 않는다.
3. patched backend는 `weston/x11-backend.so`, 관련 license는 `licenses/`에 둔다. 모듈은 **libweston-14**용이다. 현재 Termux Weston 16에 연결하지 않는다. ROOT가 별도 검증한 Weston14 binary/lib/data를 `weston-host/{bin,lib,share}`에 private extraction하여 ABI/load를 확인한다. 실패하면 명시적 실패로 멈춘다.
4. 기존 [OwnedProcesses/subreaper](../../termux/processes.py)를 재사용한다. X display20–99 중 socket·lock·실제 서버가 없는 번호를 골라 새 termux-x11을 소유한다. 기존 socket을 unlink하지 않는다. 짧은 runtime `/data/data/com.termux/lr`는 새 UID/inode/token 소유 증명으로만 생성하며 live Hypr signature socket의 AF_UNIX 길이를 확인한다.
5. own X11이 준비된 뒤 `xwininfo`의 실제 root width/height를 읽어 Weston과 guest output에 동일하게 전달한다. 고정 2560×1706을 기존 1920×1280 surface에 맞지 않게 쓰지 않는다. literal native Weston은 `--renderer=gl --shell=kiosk --socket=wayland-omarchy --scale=1`을 사용한다. semicolon-separated module map은 소유 patched x11 backend, private14 GL renderer/kiosk shell만 가리킨다. 초기 요청 refresh는 검증된60Hz, UI scale1.5이며 physical FPS 증거는 아니다. host Zink/Turnip과 guest KGSL Mesa 환경은 pinned launcher와 맞추되 실제 renderer는 별도 확인한다.
6. [guest launch](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/runtime/host/omarchy-android-start#L585)의 실제 executable/config를 사용한다. `proot-distro login --isolated --user omarchy`에 own runtime·own empty PCI stub만 bind한다. `dbus-run-session --config-file=/home/omarchy/.config/omarchy/proot-session-bus.conf -- /opt/omarchy-android/hyprland/bin/Hyprland --config /home/omarchy/.config/hypr/hyprland.lua`를 shell 없이 호출한다. UI scale1.5로 시작한다. upstream start/stop/guard/audio helper는 호출하지 않는다.
7. X 연결·Weston socket peer·자기 Hypr IPC version 응답·same-UID/birth/lineage를 나누어 확인한다. 종료는 소유 supervisor에게만 요청하고 모든 자식 reap을 증명한다. 시작 뒤 소유 증명한 정확한 socket/lock inode만 종료 후 재대조해 제거한다. replacement/unknown socket은 실패 상태와 journal로 남긴다. 정상 종료한 static short dir의 owner marker는 보존하여 새 UUID 세션에서만 재사용한다. Hypr IPC readiness는 Quickshell window·실제 output geometry·물리 입력 수락과 구분한다.

## 현재 증거와 남은 gate

ROOT는 실제 Termux production UID10323/context와 Adreno830v2 KGSL read/write를 확인했다고 전달했다. 이것은 ioctl·zero copy·표시 FPS 수락이 아니다. ROOT가 추가로 검증한 native Zink/Turnip 공개 readback 결과는 실제 nested Weston/Hyprland 전체 경로와 구분한다. 새 runtime의 Weston14 ABI·Hyprland 기동·Omarchy shell·native input·공개 GPU 장면·normal close/restart는 이 문서 작성 시 **PENDING**이다. 60/144 physical FPS와 물리 입력 지연은 별도 계측한다.

패키지의 Linux Chromium sandbox-off profile은 설치 doctor에서 표시하고 자동 browser 실행은 하지 않는다. 기본 audio/mic·host sharing도 실행하지 않는다. 기존 [native Termux VM 기록](../native-termux-validation.md)의 i3/X11 software 실험을 이 기기의 Hyprland/GPU 수락으로 재사용하지 않는다.
