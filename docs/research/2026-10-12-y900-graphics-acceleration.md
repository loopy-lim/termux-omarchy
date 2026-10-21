# Y900 Omarchy 그래픽 가속 조사 — 2026-10-12

목적: GPU renderer 문자열 또는 하드웨어 decoder 이름을 얻는 데서 끝내지 않고, 영상·브라우저·편집기를 동시에 쓸 때의 frame deadline과 CPU 부하를 개선한다. 소스 조사와 별도 후보를 사용한 기기 실험을 함께 기록한다. 버퍼 처리 비용은 줄였지만 전체 재생 성능은 아직 합격하지 못했다.

## 확인된 경로와 증거 경계

현재 런처 `termux/omarchy_commands.py`는 native Termux:X11 → native Weston X11 backend(GL renderer, Zink/Turnip) → PRoot Hyprland(KGSL) 구성을 만든다. guest에서 `HYPRLAND_ANDROID_DMABUF=1`, `HYPRLAND_GL_DMABUF_EXPORT=1`, `FD_KGSL_ENABLE_DMABUF=1`을 지정한다. 따라서 **현재 Hyprland 출력이 항상 CPU SHM readback이라는 설명은 잘못**이다. 환경변수는 요청 상태이고 실제 buffer import/export 성공을 증명하지 않는다. Weston은 compositor renderer와 출력 backend를 구분하며 X11 backend는 X 서버 안에 중첩되는 방식이다. [Weston 공식 문서](https://wayland.pages.freedesktop.org/weston/toc/running-weston.html)

기존 수치는 `docs/validation/2026-10-12-termux-performance.md`와 `build/diagnostics/termux-omarchy-performance-20261012/va-*.json`의 기록이다. 같은 브라우저·renderer·영상·편집 부하로 교차 반복한 실험이 아니므로 CPU 0.61% 대 VA 2.22–3.53% 손실만으로 원인을 확정하지 않는다. 기존 하드웨어 후보를 기본값으로 승격하지 않은 판단은 유효하다.

## hardware decode가 느렸던 이유를 좁히는 소스 증거

조사한 고정 소스는 termux-va `c7ae229bb01970212eea741d153f6805411f051d`, Mesa bridge `8c095276f525605c67c5212aabd8e42ef588790a`이다.

| 경계 | 소스에서 확인한 작업 | 의미 |
|---|---|---|
| MediaCodec → bridge SHM | `daemon/termux-va.c:1197`의 `send_frame_shm()`은 raw NV12를 memfd slot으로 memcpy | SHM은 IPC payload 복사를 줄이지만 decoder surface 자체의 end-to-end zero-copy는 아님 |
| SHM → VA surface | `tva_bridge.c:1680` 이후 reader direct-copy가 우선; 실패 시 staging malloc+memcpy | direct-copy 성공률과 fallback 빈도가 중요 |
| VA surface 채우기 | `tva_bridge.c:950`의 CPU-copy 기본값 true; KGSL import GPU upload의 consumer 가시성 문제를 명시 | `DMD_VA_CPU_COPY=0`은 성능 설정이 아니라 동기화·화질 검증이 필요한 진단 후보 |
| CPU-write 동기화 | `tva_bridge.c:1169` 이후 DMA-BUF sync로 CPU write를 감쌈; 직접 map 경로의 fd/mmap/munmap 수명 | 매 프레임 mapping 비용과 PRoot syscall 비용이 합쳐질 가능성 |
| GPU upload | `tva_bridge.c:1460`의 texture_subdata와 후속 flush | GPU copy를 골라도 decoder→SHM 복사는 남음 |

[termux-va 고정 소스](https://github.com/lfdevs/termux-va/blob/c7ae229bb01970212eea741d153f6805411f051d/daemon/termux-va.c), [Mesa bridge 고정 소스](https://github.com/lfdevs/mesa-for-android-container/blob/8c095276f525605c67c5212aabd8e42ef588790a/src/gallium/frontends/va/tva_bridge.c)

1920×1080 NV12의 순수 payload는 3,110,400 bytes/frame, 60fps에서 한 번 복사마다 약 186.6 MB/s이다. 실제 메모리 read+write traffic, stride padding, cache flush 비용은 더 크다. 이는 산술 추정이며 Y900 실측 bandwidth가 아니다. CPU memcpy 제거가 반드시 더 빠른 것은 아니다. 비동기 GPU submission과 동기화 지연도 deadline을 소비한다.

## 우선순위 실험

1. **동일 official Chrome GLES/Wayland 세션에서 software decode → VA default → VA GPU upload 교차 비교.** 동일 로컬1080p60 영상, 동일 창 크기, 동일15회 VS Code 저장, 동일 warmup으로 최소 A/B/A 또는 반복3회. 기존 Notion은 읽기 전용 유지. 영상 drop률뿐 아니라30초별 drop, longest freeze, requestVideoFrameCallback의 presentedFrames/mediaTime, 저장→미리보기 반영 p95, 프로세스별 CPU/PSS를 함께 기록한다. decoder 이름 및 플랫폼 decode 여부를 각 trial마다 확인한다. Chromium의 VAAPI 문서도 GPU 상태와 decoder 실제 선택을 구분한다. [Chromium 공식 VAAPI 문서](https://chromium.googlesource.com/chromium/src/+/main/docs/gpu/vaapi.md)
2. **CPU_COPY=0의 정확성 먼저 확인.** 일정한 색 블록·frame 번호를 가진 비DRM fixture에서 대표 프레임의 색·순서·크롭·stride를 비교한다. 재생/seek/resize/loop 종료 후 재시작도 시험한다. decoder 성공이나 canvas 프레임 수만으로 stale GPU surface를 검출할 수 없다. FFmpeg download framemd5는 decoder 출력 검증에는 유용하지만 Chromium→compositor에서의 가시성까지 증명하지 않는다. 화면 캡처는 이 미해결 화질 질문에 필요한 몇 장으로 제한한다.
3. **VA direct-copy mapping 비용 계측 후 재사용 검토.** per-frame 로그 대신 누적 count/ns/bytes를 종료 시 출력: exportFD, mmap, DMA_BUF_SYNC_START/END, memcpy, munmap, staging fallback, producer wait. map cache는 FD 정수로 키를 잡으면 안 된다. pipe_resource의 소유권과 destroy 시점, 해상도 변경, surface pool 교체에 묶어 invalidate해야 한다. 동기화 ioctl은 map을 재사용하더라도 생략하지 않는다. 실제 비용이 작으면 구현하지 않는다.
4. **Chromium Xwayland → native Wayland 비교.** 동일 Chrome/decoder/GL로 표시 backend만 바꾼다. 현재 `XWAYLAND_NO_GLAMOR=1`이 지정되어 있으므로 Xwayland 경계 비용을 분리할 가치가 있다. Wayland 전환이 자동 zero-copy 또는 더 빠름을 의미하지 않으며 입력/IME/clipboard/resize를 함께 검증한다.
5. **실제 compositor 출력 buffer 유형 계측.** Hyprland resolve 호출에서 dmabuf-export 성공/실패, SHM fallback count, readback bytes/time, Weston import 유형, frame callback→present 지연을 집계한다. `build/omarchy-refresh-20261008`의 `LoopyShmReadback.cpp:59`는 glReadPixels 뒤 BGRA swizzle/copy, `Wayland.cpp:1010` 이후는 wl_shm/dmabuf 분기를 보여준다. 그러나 그 오래된 snapshot에서 최신 `HYPRLAND_GL_DMABUF_EXPORT` 구현을 찾지 못했으므로 현재 설치 binary의 소스 일치부터 확인해야 한다. 이 branch가 실행될 때만 그 복사를 현재 병목이라고 부른다.

Weston→Termux:X11도 GL renderer라는 이유만으로 direct scanout이라고 부르면 안 된다. 해당 설치 Mesa WSI와 X11 DRI3/present 경로에서 buffer import·copy·fence를 확인해야 한다. 위 소스 조사만으로 마지막 경계의 복사 횟수는 확정하지 못했다.

## 근본적인 zero-copy 후보와 제약

Android의 `AImageReader_newWithUsage(PRIVATE, GPU_SAMPLED_IMAGE)` → MediaCodec 출력 ANativeWindow → `AImage_getHardwareBuffer()`는 CPU-readable raw NV12를 거치지 않는 후보이다. PRIVATE image는 CPU 접근용이 아니며 AHardwareBuffer를 EGL texture 등 GPU에 전달할 수 있다. acquired image 수와 release fence를 관리하지 않으면 decoder pool이 막힌다. [Android NDK Media API](https://developer.android.com/ndk/reference/group/media)

AHardwareBuffer는 AF_UNIX로 handle 전달이 가능하고 EGL/Vulkan external-memory 경로가 있다. 하지만 Android native handle은 Linux DRM PRIME descriptor와 동일한 계약이 아니다. vendor format/plane stride/offset/modifier, fence 및 buffer lifetime을 소비자에게 정확히 전달해야 한다. glibc guest가 Android bionic API를 그대로 링크할 수 있다고 가정해서도 안 된다. 첫 검증은 native Termux에서 MediaCodec→AHB→native GPU import까지 수행하고, 이후 guest DMA-BUF import를 별도 gate로 둔다. Android API 존재만으로 Y900 KGSL·SELinux·guest driver의 실제 호환성을 증명할 수 없다. [Android AHardwareBuffer API](https://developer.android.com/ndk/reference/group/a-hardware-buffer), [Khronos Android external memory](https://docs.vulkan.org/refpages/latest/refpages/source/VK_ANDROID_external_memory_android_hardware_buffer.html)

PRoot는 ptrace 기반이다. native browser/decoder helper는 이 경계를 피하는 비교군이 될 수 있지만, 모두를 native로 옮겨 Omarchy 앱 통합을 깨뜨리는 것은 목표 달성이 아니다. 먼저 native helper를 현재 compositor와 연결해 syscall/CPU 차이를 확인한다. Android Chrome/YouTube 분할 화면은 기기 decoder·display의 상한을 보는 비교군이지 Omarchy 내부 가속의 완성으로 취급하지 않는다. [Termux PRoot 소스](https://github.com/termux/proot)

## 채택 기준

동일 조건에서 편집·미리보기와1080p60 동시 재생이 개선되고, 대표 pixel/frame 순서 검사·seek/resize·기존 입력/설정 보존이 통과해야 기본값으로 채택한다. 30초 단일 성공이나 renderer 문자열만으로 장시간 안정성을 주장하지 않는다. 우선 조치로 cache sync 제거, SELinux 비활성화, 무제한 프로세스 증가, 임의 GPU debug flags 일괄 적용은 하지 않는다. 새 후보는 현재 프로필·패키지를 보존한 별도 경로에서 실패 시 원복 가능한 상태로 검증한다.

## 추가 조사: native Weston → Termux:X11의 마지막 복사 경계

`Could not get DRI3 device` 경고만으로 CPU WSI를 판정하면 안 된다. 설치된26.0.6에 해당하는 공식 Termux recipe commit `cc8bf9d492d59ca9ede9a77b3801b0928c0ec484`의 `0017-preserve-egl-support-in-zink.patch`는 Termux:X11에서 DRI3 open이 실패해도 Zink+Turnip을 유지하도록 해당 실패분기의 return을 true로 바꾼다. DRM device open과 DRI3 pixmap import는 별도 동작이다. [공식26.0.6 패치](https://github.com/termux/termux-packages/blob/cc8bf9d492d59ca9ede9a77b3801b0928c0ec484/packages/mesa/0017-preserve-egl-support-in-zink.patch)

Mesa26.0.6 `tu_wsi_init()`은 `sw_device=false`이다. `wsi_common_x11.c`에서 MIT-SHM을 요청하는 조건은 `wsi_dev->sw && !WSI_DEBUG_NOSHM`이고, hardware `x11_image_init()`은 DMA-BUF fd를 DRI3 pixmap으로 보낸다. 이는 **unmodified Turnip/Kopper 경로의 소스 계약**이며 현재 세션의 호출 계측은 아니다. 소스 열람은 같은 태그의 mirror로 확인했고 원본 경로를 아래에 남긴다. [Mesa tu_wsi.cc](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-26.0.6/src/freedreno/vulkan/tu_wsi.cc), [Mesa X11 WSI](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-26.0.6/src/vulkan/wsi/wsi_common_x11.c)

그러나 GPU가 그린 DMA-BUF를 X 서버가 받는 것과 Android Surface까지 CPU복사 없이 표시하는 것은 다르다. 공식 Termux:X11 `fa3a8b430e2896a19f44c99a9cb056254615ae06`의 조건은 다음과 같다. 이 upstream native 구현이 설치 APK와 동일한지는 별도 확인이 필요하다.

| 입력/분기 | 코드 동작 | 판단 |
|---|---|---|
| DRI3 modifier LINEAR/INVALID/1274 | `loriePixmapFromFds()` → `LorieBuffer_wrapFileDescriptor()` | CPU-mappable raw fd buffer 생성 |
| DRI3 modifier1255/1256 | AF_UNIX를 통해 AHardwareBuffer handle 수신 | Android EGLImage로 import 가능한 별도 custom 경로 |
| imported raw FD의 Present flip | `loriePresentFlip()`은 기본FALSE; Turnip 문제 주석 | swapchain과 root 크기가 같아도 flip 거부될 수 있음 |
| Present GPU copy | 양쪽 buffer가 AHardwareBuffer여야 함; raw FD는 변환대상이 아님 | rawFD 입력은 CPU present copy로 fallback할 가능성이 구체적으로 존재 |
| 최종 renderer의 FD buffer | `LorieBuffer_bindTexture()`가 glTexSubImage2D 호출 | rawFD가 직접 표시되는 경로에는 texture upload가 남음 |
| 최종 renderer의 AHB buffer | EGL_NATIVE_BUFFER_ANDROID → EGLImage texture | 마지막 texture upload는 피하지만 그전에 CPU Present copy가 있었을 수 있음 |

[Termux:X11 InitOutput.c](https://github.com/termux/termux-x11/blob/fa3a8b430e2896a19f44c99a9cb056254615ae06/lorie/src/main/cpp/lorie/InitOutput.c), [Termux:X11 buffer.c](https://github.com/termux/termux-x11/blob/fa3a8b430e2896a19f44c99a9cb056254615ae06/lorie/src/main/cpp/lorie/buffer.c)

따라서 다음 표적은 Weston의 렌더러 교체보다 **X11에서 받은 pixmap의 실제 유형과 Present copy/flip 횟수**다. native binary의 소스·hash 일치를 먼저 확인하고, 기존 debug 지원이 있다면 최초 import 로그 `DRI3: imported raw fd`/`imported AHardwareBuffer`, 누적 `present copies offloaded to GPU`를 수집한다. 필요하면 rawFD/AHB import count, flip 거부이유, CPU Present copy bytes/time, texture-upload bytes만 추가한다. 프레임마다 로그를 내면 측정 자체가 병목이 된다.

유효한 장기 개선 후보는 Weston의 Turnip swapchain을 Termux:X11 custom AHB import 계약과 연결하거나, raw DMA-BUF를 Android GPU에서 안전하게 import하는 경로를 추가하는 것이다. DRM modifier·stride·fence·resource lifetime를 모두 맞춰야 하므로 `--enable-zero-copy` 한 줄로 해결되지 않는다. `TERMUX_X11_FORCE_FLIP=1`은 rawFD flip의 명시적 문제우회 옵션이며 현재 세션 기본값으로 권장하지 않는다. CPU copy가 실측 병목으로 확인된 뒤 별도후보에서 손상·동기화·resize를 검증할 대상이다.

## 이번 실기기 실험 결과

조사에 이어 위 Mesa bridge를 계측·수정해 같은 Y900 세션에서 시험했다. 기존 기본 드라이버는 유지했다. 아래는 official Chrome 155 GLES/Wayland, 같은 로컬1080p60 H.264 fixture, 동일512×288 CSS 영상 영역, warmup/seek 뒤 약30초의 표본이다. Code와 기존 Notion 창은 열려 있었지만 이 비교에서는 실제 편집 입력을 추가하지 않았다. 순차 단일 표본이므로 장시간 또는 반복 교차 검증 결과는 아니다.

| 실제 decoder / 경로 | 프레임 | 누락 | 비율 |
|---|---:|---:|---:|
| FFmpeg software (`sw3`) | 1,799 | 34 | 1.89% |
| VA 기본 (`hw1`) | 1,808 | 63 | 3.48% |
| VA GPU upload `DMD_VA_CPU_COPY=0` (`gpu1`) | 1,805 | 62 | 3.43% |
| VA 기본 반복 (`sw2`, 파일명 오류) | 1,805 | 58 | 3.21% |
| VA 기본 + 누적 계측 (`profile1`) | 1,809 | 58 | 3.21% |
| VA shared-buffer batch sync (`batch1`) | 1,801 | 62 | 3.44% |

`sw2`는 생성된 실행 인자에서 software 강제 옵션이 누락되어 실제 VA였다. 이름 대신 Media 이벤트의 decoder를 판정 근거로 삼았다. 최초 `sw1`은 창 복구/Code 재시작이 겹쳐1,513프레임과21.2% 누락이었으므로 성능 비교에서 제외한다. 모든 실패·원본 receipt를 보존했다. 측정 코드는 `build/diagnostics/termux-omarchy-performance-20261012/gpu-research-measure.mjs`이다.

### 복사 병목을 계측하고 수정한 결과

`profile1`의 decoder 종료 집계2,570프레임에서 direct-copy 평균6.506ms, DMA-BUF END 동기화 합계 평균5.255ms, memcpy 평균0.301ms였다. KGSL의 contiguous NV12 두 plane은 같은 DMA-BUF인데 기존 구현이 각 plane마다 START/END를 수행한다. 따라서 단순 memcpy보다 **같은 객체의 중복 cache synchronization**을 먼저 줄였다.

[실험 패치](../../experiments/termux-va-batch-sync/README.md)는 같은 device/inode/size 확인, 영역 범위·겹침 검사 후 두 plane을 하나의 START/END 안에서 복사한다. CPU sync 자체를 없애지 않으며 기존 resource 수명과 소비자 완료 계약은 유지한다. EINTR/EAGAIN 재시도, 영구 START/END 실패 시 codec broken 전파를 구현했다. 실패 후 기존 경로로 넘어가 frame을 성공 처리하는 초기 후보의 오류는 설치 전에 수정했다. [Linux DMA-BUF CPU access 규약](https://docs.kernel.org/driver-api/dma-buf.html#cpu-access-to-dma-buffer-objects)

수정본 주 decoder의3,754프레임 집계에서 direct-copy 평균3.769ms, END 평균2.699ms, batch fallback0이었다. 관측된 평균 처리 시간은 약42% 감소했지만 집계는 warmup과 측정 후 재생까지 포함하고 서로 다른 순차 표본이다. 이 수치를 사용자 체감42% 개선으로 해석하면 안 된다. 실제30초 영상 누락률은 개선되지 않았다.

정확성 검사는 실제 패치 함수의 Linux ASan/UBSan harness(동일 객체·padding·retry·영구 실패·별도 객체·겹침·범위·opt-out)를 통과했다. 기기 FFmpeg NV12 framemd5는 software와720/720 동일했고, Chrome에서3초 seek 후 GPU 합성 화면640×360 픽셀도 계측 기본본과 완전히 같았다. 한 시점 화면 비교는 모든 seek/resize/장시간 surface 수명의 검증이 아니다. FFmpeg 검사시간 CPU3.83초/VA4.18초에는 hwdownload와 해시 연산이 포함되므로 재생 성능 수치로 쓰지 않는다.

### 마지막 출력 경계의 실측

실제 foreground Termux:X11 `LorieNative` 로그는 여러5초 구간에서 `0/294 present copies offloaded to GPU`와 같은 값을 기록했다. **해당 Present 복사에 GPU offload가 사용되지 않는다는 것은 실측 사실**이다. 전체 GL 렌더링이 software라는 뜻은 아니다. native Weston은 Zink/Turnip을 로드하고 있다. `gpu-x11-present.log`에 원본을 남겼다.

raw DMA-BUF→CPU Present fallback이라는 소스 설명과 일치하지만, 설치 native binary와 정확히 일치하는 source provenance 및 런타임 import 유형까지 대조하지 않았으므로 특정 분기만을 원인으로 확정하지 않는다. 다음 변경은 이 경계의 `rawFD/AHB import count`, CPU copy bytes/time, flip 거부이유를 계측한 뒤 AHB import 계약을 연결하는 것이다. 수명·release fence·resize 검증 없이 강제 flip을 기본화하지 않는다.

### 보존 및 정리

후보는 기본값으로 승격하지 않았다. 하드웨어 디코딩 연결 성공과 버퍼 처리 단축은 확인했지만, 사용자 요구인 YouTube+Notion+개발의 매끄러운 동시 실행을 달성한 상태는 아니다. 원격 검증은 사용자 요청대로 뒤로 미룬다.

시험 준비 도중 이전 진단 helper가 `hl.dsp.window.close("address:...")`의 문자열 인자를 잘못 사용해 활성 Code 창을 닫았다. 새 helper는 `{window="address:..."}` 형태와 시험 프로필 프로세스 검사를 사용하도록 수정했다. Code의 시험 프로젝트를 다시 열었고 마지막 저장 `Y900 live edit 15`는 보존했다. 개인 문서는 수정하지 않았다. 이 진단 오류를 Android 프로세스 종료 현상으로 세지 않는다. 최종 Code와 로컬 미리보기를 `Local Dev`에 복구했으며 원래 Chromium의 Notion/YouTube 두 창과 데스크톱 세션을 유지했다.
