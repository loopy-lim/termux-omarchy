# Y900 현재 출력 경로의 90/120Hz와 queue latency 조사

현재 경로에서 가장 좁은 시험 지점은 Weston 재빌드가 아니라 **owned Weston 환경의 `WESTON_X11_REFRESH_MHZ`**다. 저장소는 이를60000으로 강제하고, 이미 배포 계열의 Weston patch는30000–240000 override와 parent XRandR timing 탐지를 구현한다. Android 패널·Termux:X11·Weston·Hyprland를 모두 확인해야 하며 advertised120Hz만으로 물리120fps나 입력 지연 개선을 주장하면 안 된다. 이 조사는 기기나 runtime을 변경하지 않았다.

## 소스로 확정된 경계

- [현재 commands](../../termux/omarchy_commands.py)의 `commands()`는 native Weston 환경에 `WESTON_X11_REFRESH_MHZ='60000'`을 넣는다. 따라서 단순히 Android display mode만 올려도 Linux 쪽60Hz 제한은 남는다.
- 고정 v0.1.1의 [Weston X11 patch](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/patches/weston/0001-backend-x11-carry-proven-Android-nested-fixes.patch)의 `x11_compositor_get_refresh_mhz()`가 env를 우선하고, 없으면 active CRTC의 dot_clock/(htotal×vtotal)을 읽는다. `x11_output_set_size()`에서 선택하고 로그에 `x11 output refresh selected`를 남긴다. 실행 중 parent refresh 변경을 계속 추적하는 코드는 이 patch에 없다. mode 변경 후 owned Weston 재시작을 포함해야 한다.
- [Weston14.0.2 upstream x11.c](https://gitlab.freedesktop.org/wayland/weston/-/blob/14.0.2/libweston/backend-x11/x11.c)는 `output->mode.refresh=60000`을 고정한다. GL repaint 후 `weston_output_arm_frame_timer()`를 호출하고 timer로 finish한다. X Present의 실제 표시 완료 시각을 Weston repaint clock으로 직접 받는 경로가 아니다.
- [동일 버전 frontend](https://gitlab.freedesktop.org/wayland/weston/-/blob/14.0.2/frontend/main.c)의 windowed output mode parser는 `%dx%d`만 읽는다. X11 backend에 DRM식 `mode=3840x2560@120`을 넣어도 refresh 설정 경로가 되지 않는다.
- [compositor14.0.2](https://gitlab.freedesktop.org/wayland/weston/-/blob/14.0.2/libweston/compositor.c)의 frame timer는 `frame_time+period`까지의 시간을1ms 정밀도로 올림하고,1.5ms 이상 늦으면 현재 시각으로 finish한다. 따라서 nested timer와 Android VSYNC 사이의 phase mismatch가 남을 수 있다. 현재27ms ready-to-present p95를 이 사실만으로 전부 설명할 수는 없다.

로컬 patch는 `build/omarchy-v011-source/patches/weston/0001-backend-x11-carry-proven-Android-nested-fixes.patch`에 있고, [빌드 script](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/builder/host/build-weston.sh)는 Android용 X11 backend 모듈만 빌드·별도 prefix 설치할 수 있다. 현재 source/ABI와 모듈을 확인한 뒤 사용해야 하며 glibc Orb 빌드를 bionic 모듈로 혼동하면 안 된다. 먼저 설치된 `x11-backend.so`의 두 문자열과 Weston 로그로 기능 존재를 확인하면 불필요한 빌드를 피할 수 있다. 이 조사에서 Orb VM 상태를 확인하거나 빌드를 실행하지 않았다.

## Termux:X11에서 실제 cadence가 결정되는 곳

다음은 공식 Termux:X11 commit `fa3a8b430e2896a19f44c99a9cb056254615ae06` 소스 조사이다. 설치 APK의 native library가 이 revision과 동일하다는 증거는 별도로 필요하다.

1. [LorieView.java](https://github.com/termux/termux-x11/blob/fa3a8b430e2896a19f44c99a9cb056254615ae06/lorie/src/main/java/com/termux/x11/LorieView.java)의 `sendWindowChange()`는 `Display.getRefreshRate()`를 정수로 바꾸어 서버에 보낸다. supported modes 목록이 아니라 현재 Display refresh이다.
2. [InitOutput.c](https://github.com/termux/termux-x11/blob/fa3a8b430e2896a19f44c99a9cb056254615ae06/lorie/src/main/cpp/lorie/InitOutput.c)의 `lorieConfigureNotify()`는 CVT mode와 vblank interval을 갱신한다. `lorieChoreographerFrameCallback()`은 Android Choreographer마다 `lorieRedraw`를 X server work queue에 넣는다. redraw에서 MSC가 증가하고 Present vblank를 수행하며 renderer의 `waitForNextFrame`을 푼다.
3. [renderer.cpp](https://github.com/termux/termux-x11/blob/fa3a8b430e2896a19f44c99a9cb056254615ae06/lorie/src/main/cpp/lorie/renderer.cpp)는 EGL swap interval0을 이미 사용하지만 `waitForNextFrame`으로 다음 Choreographer까지 redraw를 제한한다. root GPU copy 완료 fence를 기다리고 다시 wait flag를 설정한 뒤 Android EGL swap한다. `vblank_mode=0` 같은 이름만 바꾸어 이 cadence가 제거되는 구조가 아니다.

AHB는 buffer transport를 바꾼다. panel refresh를 요청하거나 Weston frame timer를 자동 상향하는 기능은 아니다. Android가120Hz라도 앱별 정책/Choreographer가60Hz이면 최종 경로는 여전히60Hz일 수 있다. 따라서 Android active mode, Termux XRandR mode, Hyprland WAYLAND-1 mode, 실제 SurfaceFlinger presentation 간격을 각각 읽어야 한다.

## 가장 작은 순서의 시험

| 단계 | 한 번에 바꿀 것 | 수락/기각 근거 |
| --- | --- | --- |
| 0 | 변경 전 설치 모듈 문자열, native env, XRandR mode, Android active mode 확인 | 실제 override 지원과60Hz 강제 위치 확인 |
| 1 |3840×2560/scale2.5 유지, Android120Hz와 Weston override120000을 일치 | nested mode120 + 실제 physical presentation 약8.33ms 간격 + 화면 갱신 gate. 처음부터 queue 관련 값을 함께 바꾸지 않음 |
| 2 | 동일 scroll 및 YouTube1080p60+Code 부하를 짧게 재실행 | ready-to-present p50/p95, physical present p95/max, 실제 wheel 반영, video drops, CPU/memory. 물리 cadence가60이면 advertised120 후보를 기각 |
| 3 |120Hz가 처리량/발열/메모리 때문에 나쁘면90Hz 같은 조건 |90Hz는16.67ms 영상과11.11ms 화면 주기가 정수배가 아니므로60fps 영상 pacing도 별도 비교. 부하 여유만으로90을 선호하지 않음 |
| 4 | 채택 refresh 고정 후 Weston repaint-window7→4ms 단일 A/B | ready-to-present 감소와 missed frame 증가를 함께 확인. 필요할 때만4→2ms. baseline보다 p95/max 또는 video drops가 나빠지면 복귀 |

부모가 측정한 현재 기준은 Notion rAF p95≈16.8ms,max50ms(YouTube 병행83.4ms), Android present p95≈16.67ms,max33ms(병행50ms), ready-to-present p95≈27ms다. 이번 조사에서 다시 측정한 값은 아니며 원래 receipt가 최종 근거다. rAF는 실제 panel 표시나 input-to-photon 측정이 아니다.

## repaint-window와 피해야 할 queue 조작

[Weston14.0.2 설정 설명](https://gitlab.freedesktop.org/wayland/weston/-/blob/14.0.2/man/weston.ini.man)은 `[core] repaint-window` 기본7ms를 명시한다. repaint deadline은 다음 frame 시각에서 이 값을 뺀 시간이다. 작은 값은 더 늦게 최신 상태를 그릴 여지를 주지만 너무 작으면 deadline을 놓쳐 한 frame 더 늦어진다.120Hz 주기는8.33ms라7ms는 이른 제출이 될 수 있다. 그러나 X11 backend는 synthetic timer이므로 phase 정렬과 실제 latency 감소는 측정해야 한다. repaint-window를0이나 음수로 바로 낮추는 것은 추천하지 않는다.

현재 [native Mesa X11 WSI 소스](../../build/x11-copy-20261012/mesa-source/src/vulkan/wsi/wsi_common_x11.c)는 `vk_x11_override_min_image_count`, `vk_x11_strict_image_count`를 읽지만 주석에서 image count가 단순 성능 tuning 도구가 아니며2개 강제가 MAILBOX/IMMEDIATE 진행 특성을 훼손할 수 있음을 설명한다. Chrome과 Weston 양쪽에 전역 적용하거나 fence/idle를 조기 해제하지 않는다. 이미 해결한 cross-ABI fence 경계를 다시 훼손할 이유가 없다.

이 단계에서 권고하는 변경은 **refresh env/cadence gate → repaint-window 단독 A/B** 두 가지다. Android BufferQueue 수, Termux renderer fence, swapchain image 수 변경은 trace가 특정 queue 대기를 가리킨 이후의 별도 실험이다.

## 추가 조사: 4K120 Notion scroll의 다음 한 가지 판별 실험

현재 부모 측정은 native Chromium155.0.8059.39, GPU raster/compositing/Vulkan 활성,4K120/scale2.5, software H.264이다. Notion 실제 wheel256회/25.6초에서 rAF p95≈25ms/max83ms,33ms 초과19회,50ms 초과 longtask0회였으며 물리 present p95≈16.67ms/max41.67ms,ready-to-present p95≈22ms다. repaint7→4, renderer backgrounding 해제,90Hz는 채택할 개선을 입증하지 못했다. 아래는 아직 실행하지 않은 source 기반 제안이다.

**다음 실험은 새 성능 flag가 아니라, 동일 visible Notion에서8–10초 실제 wheel 구간의 Chromium trace 한 번이다.** 이를 통해 browser에 frame이 늦게 도착하는지, Viz가 swap 완료를 기다리는지 먼저 구분한다. 현재 증거만으로 GPU queue를 원인으로 확정할 수 없다.120Hz 예산은8.33ms라8–49ms CPU 작업도 frame을 놓칠 수 있으며, longtask0은 main thread 무혐의 증거가 아니다. [Long Tasks 규격의50ms 문턱](https://www.w3.org/TR/longtasks-1/#sec-terminology).

### zero-copy flag를 다음 실험에서 제외하는 정확한 이유

[Chromium155 LayerTreeHostImpl::CreateRasterBufferProvider](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.39/cc/trees/layer_tree_host_impl.cc)는 `use_gpu_rasterization`이면 `GpuRasterBufferProvider`를 먼저 반환한다. 그 뒤에 `settings_.use_zero_copy`를 검사한다. 따라서 현재 실제 GPU raster 경로에 `--enable-zero-copy`를 추가해도 이 tile provider는 바뀌지 않는다. GPU raster가 일부 content에서 떨어진 경우라면 예외이므로 trace에서 실제 provider를 확인한다.

[ZeroCopyRasterBufferImpl::Playback](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.39/cc/raster/zero_copy_raster_buffer_provider.cc)는 SharedImage를 CPU에 `Map()`한 뒤 `PlaybackToMemory()`를 호출한다. 이 flag를 GPU raster의 복사 제거 기능이나 Weston AHB zero-copy와 같은 기능으로 해석하지 않는다. [GPU provider](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.39/cc/raster/gpu_raster_buffer_provider.cc)의 `GpuRasterBuffer::Playback` trace는 worker 쪽 command 처리/제출 시간이지 GPU 실행 완료 시간 전체가 아니다.

### 단일 trace의 수집과 판정

기존 test용 CDP 접속 범위에서 browser `Tracing.start`의 categories를 `cc,viz,gpu,input,input.scrolling,benchmark,toplevel,devtools.timeline`로 제한한다. 8–10초 동안 기존과 같은 wheel 간격·같은 문서 위치·같은 동시 영상 상태를 유지하고 종료한다. screenshot/heap dump/전체 debug category는 추가하지 않는다. 기존 rAF 및 physical present 기록과 같은 구간 표시를 넣는다. trace와 외부 로그의 clock origin을 정렬하기 전에는 절대 timestamp를 직접 빼지 않는다. [공식 Tracing API](https://chromedevtools.github.io/devtools-protocol/tot/Tracing/). 이 측정은 overhead가 있으므로 trace 자체의 FPS를 최종 개선 수치로 쓰지 않는다.

[155 DisplayScheduler](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.39/components/viz/service/display/display_scheduler.cc)에는 다음 이벤트와 명확한 조건이 있다.

- `Swap throttled`: `pending_swaps >= MaxPendingSwaps()`이면 deadline을 late로 한다. pending-swaps span은 `DidSwapBuffers()`에서 시작하고 `DidReceiveSwapBuffersAck()`에서 끝난다. 이는 swap ACK 대기이며 Android panel presentation 완료를 직접 뜻하지 않는다.
- `DisplayScheduler:pending_swaps`: 동시에 열린 span 수,각 ACK 대기 시간과 긴 frame의 겹침을 확인한다. refresh별 max pending 값도 runtime event에서 읽으며120Hz라고 고정값을 추정하지 않는다.
- `Root frame missing`, `More damage expected soon`: surface/frame 준비 지연과 swap throttle을 구분한다.
- `DisplayScheduler::BeginFrame`, `DrawAndSwap`, `OnBeginFrameDeadline`: supplied interval이 실제8.33ms인지, frame 제출과 draw가 어디서16/25/33ms로 벌어지는지 확인한다.

[155 cc Scheduler](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.39/cc/scheduler/scheduler.cc)의 `Scheduler::BeginFrame`, `BeginImplFrame`, `BeginFrameDropped`, `NotifyBeginMainFrameStarted`, `NotifyReadyToCommit`와 실제 page PID의 main-thread task/layout/paint 구간을 함께 읽는다. 다른 탭의 event를 Notion 원인으로 합치지 않는다.

| 같은 긴 frame 구간에서 관측 | 다음 판단 |
| --- | --- |
| BeginFrame은8.33ms인데 Notion main task/layout 또는 commit이8.33ms 이상,root frame missing/submit 공백 동반 | main/render-tree 준비 쪽 증거. longtask0이어도 가능. zero-copy/queue flag보다 document paint/scroll 경로 검토 |
| main/commit은 제때이며 swap-throttled 반복,pending-swap ACK 대기가 지연과 겹침 | Viz/output backpressure 가설 강화. 다음 조사 범위를 Vulkan swap ACK→Xwayland Present로 한정; 곧바로 fence 해제나 image count 축소는 하지 않음 |
| Viz DrawAndSwap은8.33ms 주기로 진행하지만 물리 present만16/25ms로 벌어짐 | browser 외부 Xwayland→Hypr→Weston→Termux 단계 또는 Android queue 쪽으로 범위 축소 |
| trace BeginFrame interval부터16.67ms | browser가120Hz cadence를 받고 있지 않음. zero-copy보다 display/vsync 정보 전달 검증 우선 |
| trace span이 없거나 기록이 손실됨 | 가설 반증이 아니라 관측 실패. 성능 개선으로 판정하지 않음 |

이 한 번의 trace는 원인을 분리하기 위한 실험이다. 지금 단계에서 zero-copy, Vulkan scheduler feature, buffer 수를 함께 바꾸는 조합은 제안하지 않는다.

## bounded trace 수집 후: FIFO acquire backpressure 후보

[metadata-only trace](../../build/diagnostics/termux-omarchy-performance-20261012/notion-scroll-trace-bounded-summary.json)를 읽었다. `Swap throttled`310회는 모두 GPU process에서 관측됐고, 보존된 args는 `pending_swaps=1,max_pending_swaps=1`을 보여준다. `DelayBasedBeginFrameSource::OnTimerTick`의 interval8336μs도 있어 browser timer가120Hz 정보를 못 받는다는 단순 가설은 이 표본과 맞지 않는다. GPU `SwapBuffers` 최대6.737ms, 실제 `GpuRasterBuffer::Playback` 최대0.357ms이다. 후자는 GPU 완료 시간이 아니므로 GPU가 항상 빠르다고 결론내리지는 않는다.

Notion PID7945는 부모가 CDP ProcessTime과 SystemInfo renderer CPU의 유일한65.34초 일치로 식별했다. Notion BeginMainFrame 최대22.684ms는120Hz의8.33ms 예산을 넘는다. 따라서 main-thread 기여가 없다는 가설도 기각해야 한다. YT PID8354의33.481ms를 Notion 값으로 합치지 않는다. 여러 window scheduler가 같은 GPU thread에 섞이고 async id가 제거됐으므로 현재 pending span671개의 순서만으로 ACK p95를 계산하거나310/641을 frame-loss 비율로 취급할 수 없다.

공식155 소스를 더 좁혀보면:

- [SkiaOutputDeviceVulkan::Initialize](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.39/components/viz/service/display_embedder/skia_output_device_vulkan.cc)는 `max_pending_swaps=1`을 고정한다. 따라서1/1 throttle은 queue 보호 동작이며 그 자체가 오류는 아니다.
- [VulkanSwapChain::InitializeSwapChain](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.39/gpu/vulkan/vulkan_swap_chain.cc)는 `VK_PRESENT_MODE_FIFO_KHR`을 요청한다. `PostSubBufferAsync()`는 `PresentBuffer()` 후 worker에서 `AcquireNextImage()`를 실행하고, 다음 image를 얻은 뒤에만 SWAP_ACK callback을 보낸다. 즉 Viz ACK 대기는 Vulkan image 재획득과 연결된다. Xwayland가 release를 늦추면 영향을 줄 수 있지만 이번 trace는 그 원인을 직접 측정하지 않았다.

이제 가능한 **최소 correction 후보는 native browser 환경 한 곳의 `MESA_VK_WSI_PRESENT_MODE=mailbox` 단일 A/B**이다. 채택된 교정이 아니라 가설 시험이다. [Mesa 공식 env 문서](https://docs.mesa3d.org/envvars.html#envvar-MESA_VK_WSI_PRESENT_MODE)와 [Mesa WSI 구현](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-26.0.6/src/vulkan/wsi/wsi_common.c)은 지원 여부를 검사하고 application의 present mode를 override한다. 지원되지 않으면 원래 mode로 fallback한다. [Vulkan present mode 규격](https://docs.vulkan.org/refpages/latest/refpages/source/VkPresentModeKHR.html)에서 MAILBOX는 표시 대기 중 image를 최신 제출로 대체할 수 있어 FIFO backlog와 다르며, IMMEDIATE처럼 tearing을 요구하는 mode는 아니다.

시험 gate와 범위:

1. 실제 로드된 native Freedreno library의 override 지원과 해당 Xwayland surface의 MAILBOX 지원을 먼저 확인한다. env가 들어갔다는 사실만으로 mode가 적용됐다고 수락하지 않는다. unsupported fallback이면 FIFO 대조군과 같은 것이므로 유효한 A/B가 아니다.
2. browser만 정상 재실행하여 해당 env 하나를 추가한다. private futex,4K120,scale2.5,ANGLE/Vulkan,media 경로,Weston 설정은 그대로 둔다. compositor 전체에 env를 전파하지 않는다. image count를 강제 변경하거나 fence를 조기 signal하지 않는다. MAILBOX 전환에 따른 구현의 추가 buffer/memory 가능성은 측정한다.
3. 동일 visible Notion wheel25.6초와 YouTube1080p60에서 물리 ready-to-present/present p95·max,Notion rAF,영상 drops,메모리를 비교한다. rAF만 좋아지고 실제 표시·영상이 나빠지면 기각한다. 이득이 없으면 FIFO로 복귀한다. GPU 가속·물리 갱신·정상 stop은 동일하게 확인한다.

이 후보는 FIFO/acquire wait라는 실제 source 경로를 겨냥한다. Notion의22.684ms main work까지 해결할 것으로 기대하지 않는다. MAILBOX가 효과 없거나 적용 여부를 확인하지 못하면, 다음 자료는 다른 flag가 아니라 현재4MiB ring에서 `id/id2/scope`, scheduler 식별자와 BeginFrame interval·pending/max numeric args만 더 보존한 짧은 trace다. 서로 다른 창의 ACK를 잘못 pairing하지 않는 것이 먼저다.
