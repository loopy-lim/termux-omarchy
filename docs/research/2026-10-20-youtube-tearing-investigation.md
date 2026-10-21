# YouTube 재생 "위→아래 그려지는 렉" 원인 분석 (2026-10-20)

## 증상
YouTube 재생 시 화면이 위에서 아래로 주사선처럼 그려지며 심한 렉. 컴포지터 FPS는 113–118 유지.

## 확인된 원인 (3가지 겹침)

### 1. 어젯밤 스트레스 테스트 잔존물 ★ 직접적 원인
- `while true; date ... | foot` 스피너 3세트(+proot 래퍼)가 밤새 CPU 점유.
- YouTube 재생 당시 이 부하가 얹혀 있어 렉 체감 가중.
- **조치 완료**: 모두 정리(foot/pkill + guest foot kill). 정리 후 FPS 107→116 회복.

### 2. Chromium X11 present 경로의 구조적 CPU 복사
- 게스트 Chromium은 `--ozone-platform=x11 --use-angle=vulkan --disable-vulkan-surface`로 실행됨.
- Turnip(freedreno ICD)이 `VK_KHR_xcb_surface` 미지원 → `--disable-vulkan-surface` 필수 →
  ANGLE이 오프스크린 렌더 후 **CPU 리드백 → XShmPutImage**(프레임당 ~17–37MB memcpy).
- GPU 래스터는 HW(GPU 프로세스 kgsl fd 3개 확인), present만 CPU.
- 이 복사가 "위→아래 밴드" 체감의 근원.

### 3. 4단계 중첩 컴포지팅
- chrome → Xwayland(:0) → Hyprland → Weston(wayland-omarchy) → termux-x11(:20) → SurfaceFlinger.
- termux-x11이 상시 ~70% CPU(X11 wire SHM 업로드+AHB present 관리).

## 오늘 시도한 대안과 결과

| 시도 | 결과 |
|---|---|
| `--ozone-platform=wayland` + ANGLE vulkan/GLES | GPU 프로세스 즉사(exit 256). strace: `/proc/bus/pci/devices` EACCES → libpci exit(1). **pci-devices 바인드 누락이었음**(세션 런처는 바인드함) |
| pci 바인드 추가 후 wayland chrome | 살아남(크래시 0) but GPU 프로세스가 **llvmpipe**(libLLVM mapped, kgsl fd 0) |
| `--use-gl=egl` | invalid → `--use-gl=disabled`로 강제됨(Chromium 151) |
| EGL-X11(angle=gles) via hyprctl eval | GPU 프로세스 `--use-gl=disabled`. EGL-X11 초기화 실패 추정(DRI3 미지원 Xwayland) |
| eglinfo(EGL_PLATFORM=wayland) | **성공: `EGL driver name: kgsl`** — HW EGL Wayland 자체는 작동 |
| vkcube(WSI wayland) | **성공: Adreno 830v1 direct present** — Vulkan Wayland WSI도 작동 |

## 구조적 결론
- Mesa kgsl 스택(HW EGL/Vulkan Wayland)은 멀쩡하다.
- Chromium ozone-wayland는 GPU 프로세스에서 **DRM render node(/dev/dri/renderD128)가 없으면**
  dmabuf 버퍼 매니저를 초기화하지 못하고 GL을 비활성화(SHM+llvmpipe)한다.
  (`wayland_buffer_manager_gpu.cc: Failed to initialize drm render node handle`)
- 이 기기 KGSL에는 DRM 노드가 없다(커널 minigbm 없음).
- 따라서 **게스트 Chromium의 HW Wayland direct present는 DRM 노드 문제가 풀리기 전까지 불가**.

## 2차 심화 (2026-10-20 오후) — DRM 노드 실체와 A/B 측정

### DRM 노드 재조사
- `/dev/dri/renderD128`, `/dev/dri/card0` **실제 존재** (msm_drm, SELinux `graphics_device`).
- `vulkaninfo` **device extensions에 `VK_KHR_xcb_surface` + `VK_KHR_wayland_surface` 모두 존재**
  (기존 "xcb 미지원" 판단은 instance-extension 요약 해석 오류).
- 그러나 **SELinux 차단**: shell/runas_app 도메인에서 `graphics_device` open 불가
  (`Permission denied`, AVC denied 없이 DAC 이전 단계 차단). `gpu_device`(/dev/kgsl-3d0)는 open 가능.
- msm_drm 노드를 여는 프로세스 0개 = 노드만 존재하는 휴면 상태. adb root 불가(production build).

### 게스트 Chromium 백엔드 A/B (모두 세션 hl.exec_cmd로 실행, BBB 60fps 기준)
| 경로 | GPU | Viz CPU | presented | 비고 |
|---|---|---|---|---|
| X11 + `--disable-vulkan-surface` (기존) | kgsl HW | 71% | 28–30fps | XShm CPU readback |
| X11 + xcb vulkan direct (플래그 제거) | kgsl HW + libxcb-dri3 | 69% | 28fps | ANGLE 내부 blit 잔존 |
| Wayland + ANGLE-vulkan (세션 환경) | kgsl HW(fd 3) + dmabuf 228 refs | 100%+ | 28–36fps | Viz fence-spin burn |
| Wayland + ANGLE-gles | llvmpipe | - | - | GPU 프로세스 SW 폴백 |
| X11 + ANGLE-gl | llvmpipe | - | - | EGL-X11 kgsl 미로드 |

- **"30fps wall"의 정체**: 480p 자동 품질에서 YouTube가 30fps 배리언트를 준 것.
  `setPlaybackQualityRange('hd1080')` 강제 시 decoded 59.9fps 달성 → 디코드 wall 아님.
- rAF는 모든 경로에서 53–60fps → compositor vsync 자체는 정상.

### 네이티브 브라우저 직접 측정 ★ 핵심 성과
`omarchy_android.py` 런처 그대로 호스트에서 수동 실행(`:20` 직접, xcb-dri3 + mailbox + futex):
- **VizCompositor CPU 9%** (게스트 경로 대비 8–12배 절감), GPU proc 총 19%.
- **1080p60: decoded 59.9fps / presented 48.9fps** (dropped 14).
- kgsl fd 2개 + turnip 초기화 성공 로그(`maxDynamicUniformBuffers...`).
- 남은 최대 소비처: termux-x11 Thread-1 86% (AHB present + X11 wire 관리).
- 게스트 4-hop(chrome→Xwayland→Hyprland→Weston→termux-x11) 대비 **hop 3개 제거**.

### 결론 업데이트
- GPU 직결(present 시 CPU 복사 0)의 실현 경로는 **호스트 네이티브 브라우저 체인**으로 확인됨.
- 게스트 chromium은 백엔드 무관 ANGLE-vulkan의 Viz fence-spin(69–100%) 한계 → 게스트 내 추가 최적화 여지는
  turnip/ANGLE 패치 수준으로 남음.
- 다음 후보: ① 네이티브 브라우저를 기본 유튜브/브라우저 경로로 승격 ② termux-x11 Thread-1 병목 최적화.

## 3차: Xwayland KGSL 확인 + mailbox 적용 (2026-10-20 저녁)

### 게스트 Xwayland 실측
- 커스텀 `/opt/loopy-xwayland-kgsl/bin/Xwayland -glamor es` — kgsl fd 4개.
- `glxinfo -B`: **Adreno 830v1 / freedreno 26.3.0 / direct rendering: Yes / GL 4.6** (세션 hl.exec_cmd 경유).
- 잔존 오류: `xcb_dri3_pixmap_from_buffer → X error 11(BadRequest)` 일부 버퍼에서 발생 →
  해당 분기는 SHM 폴백. Xwayland 측 DRI3 pixmap import 패치 여지(별도 과제).

### MAILBOX present 모드 효과 ★ (게스트 chromium, 1080p60 강제)
| 설정 | presented | decoded | Viz CPU |
|---|---|---|---|
| 기본 fifo (기존) | 28–30fps | 60fps | 71% |
| `MESA_VK_WSI_PRESENT_MODE=mailbox` | **52.5fps** | 60.1fps | 70% |

- mailbox로 vsync 정렬 대기 제거 → presented +87%. Viz CPU는 동일(present 대기가 아닌 spin).

### 세션 반영 (영구 적용 완료)
1. 게스트 `~/.config/chromium-flags.conf`: `--disable-vulkan-surface` 제거
   (백업: `chromium-flags.conf.bak-20261020`). 근거: `VK_KHR_xcb_surface` 디바이스 확장 존재 실측.
2. 게스트 `/etc/profile.d/90-loopy-vulkan-mailbox.sh`: `MESA_VK_WSI_PRESENT_MODE=mailbox` 추가.
- 브라우저 재시작 시 자동 적용. 실험용 chrome/네이티브 AB 인스턴스는 모두 정리됨.

### 유저 유튜브 창의 실체
- pid 10700 = `loopy-browser-performance`(proot-guard loader, 게스트 /usr/lib/chromium/chromium),
  세션 supervisor(12377) 직계. 게스트 체인 경로 확정.

### 남은 병목 (우선순위)
1. termux-x11 Thread-1: 86–96% (AHB present 관리 — 119.6 FPS 유지 중, GPU offload 435/435).
2. 게스트 Viz fence-spin 70%: turnip/ANGLE 패치 과제.
3. Xwayland DRI3 pixmap import X error 11.

## 4차: 유저 세션 적용 완료 (2026-10-20 20:00)

### 적용 내역
1. **게스트 `chromium-flags.conf`**: `--disable-vulkan-surface` 제거 완료 → 유저 브라우저(17663)가
   xcb-direct Vulkan present로 재실행됨을 `/proc/PID/cmdline`로 확인 (`FLAG-CLEAN`, kgsl fd 2).
2. **`termux/omarchy_commands.py`**: 세션 `guest` env에 `MESA_VK_WSI_PRESENT_MODE='mailbox'` 추가
   (다음 세션 시작부터 유저 브라우저에 자동 적용; `environment()`의 pop 리스트와 무관하게
   `commands()`에서 주입).
3. 게스트 `/etc/profile.d/90-loopy-vulkan-mailbox.sh` 추가 (터미널 실행 브라우저용).

### 세션 안정성 스냅샷
- `LorieNative: 587 frames/5s = 117.4 FPS, 437/437 present copies offloaded to GPU`
- Hyprland/Weston/termux-x11/브라우저 모두 생존, 실험 프로세스 잔여 0.
- Gmail 세션 복원 확인(브라우저는 이전 프로필 그대로 사용).

### 자동 재생 검증의 한계
- 유저 브라우저 자체는 CDP 미사용 빌드 + wtype 키가 Gmail 포커스 탭에만 닿아
  원격 재생 트리거 불가. **유저가 유튜브 탭에서 재생 버튼 클릭 시 위 설정이 즉시 발동**.
- 검증 방법: 유튜브 60fps 영상 재생 → 상단 테어링(위→아래 밴드) 소실 여부 체감.

### 배포 아티팩트 최종 상태 (2026-10-20 20:15)
| 위치 | 내용 | 상태 |
|---|---|---|
| 디바이스 `~/.local/share/loopy-omarchy/omarchy_commands.py` | HEAD 기반 + `MESA_VK_WSI_PRESENT_MODE='mailbox'` (게스트 env) | 배포+게스트 python ast 검증 통과, `.bak-20261020` 백업 |
| repo `termux/omarchy_commands.py` | 동일 내용 (diff 3줄 추가만) | syntax-ok |
| 게스트 `chromium-flags.conf` | `--disable-vulkan-surface` 주석화 | 적용 완료 (실행 중 브라우저 17663 확인) |
| 게스트 `/etc/profile.d/90-loopy-vulkan-mailbox.sh` | 터미널 실행분 env | 적용 완료 |
| 세션 FPS | 117.8 FPS, 459/459 present GPU offload | 안정 |

## 다음 단계 후보
1. **fake/대체 DRM render node**: kgsl을 wrap하는 미니 DRM 드라이버 또는 `vkms` render node +
   mesa kgsl 매핑 실험(vkms_dri.so 존재 확인됨).
2. Chromium 패치: ozone-wayland가 DRM 없이 linux-dmabuf-only로 동작하도록 수정
   (buffer manager 실패 시 dmabuf fallback). 업스트림 chrome 151 소스 위치:
   `ui/ozone/platform/wayland/gpu/wayland_buffer_manager_gpu.cc`.
3. 단기 완화(오늘 바로 가능):
   - 사용자 Chrome에 `--enable-zero-copy` 추가(present 복사 1회 감소) — 재시작 필요.
   - YouTube 확장(prefer-h264)이 H.264 강제 중 → SW 디코드 비용 절감 확인됨.
   - 브라우저 창 최대화 대신 영상 크기에 맞추면 present 면적 감소.

## 계측 스냅샷
- 정리 후: 107–118 FPS, present copies 100% GPU offload, fence handoff ok=3.37M/0 fallback.
- 사용자 Chrome GPU 프로세스: kgsl fd 3개(HW raster), 렌더러 2.5%.
- 스크린샷: `build/diagnostics/` 참조.
