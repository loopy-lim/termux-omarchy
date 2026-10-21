# Hyprland export `glFinish` → `EGL_ANDROID_native_fence_sync` hand-off

목적: PRoot Hyprland(KGSL)가 `eglExportDMABUFImageMESA`로 presentation DMA-BUF를 내보낸 뒤, parent Weston이 샘플하기 전에 치는 `glFinish()`를 **안전하게** 제거하기 위한 계약. 해상도 scale-down은 비목표.

증거 표기: **[계약]** = 스펙·소스·패치가 요구하거나 구현하는 동작. **[실측]** = 이 기기·세션에서 관측한 사실만. 이 조사 에이전트는 기기에 없음 → 새 실측은 공백으로 둔다.

개발 스캐폴드(구현·프로브만, hand-off 아님): [`experiments/hyprland-export-fence/`](../../experiments/hyprland-export-fence/).  
선행 맥락: [Y900 graphics next](2026-10-19-y900-graphics-acceleration-next.md) §7.

---

## 1. 현재 스택과 `glFinish`가 하는 일

```text
PRoot Hyprland (KGSL GLES)
  staging FBO → eglExportDMABUFImageMESA → IBuffer::setPresentationDMABUF
  CGLRenderbuffer::unbind: presentationDMABUFActive → glFinish()  ← 여기
       │
       ▼ wl_surface attach/commit (Aquamarine Wayland client)
native Weston (Zink → Turnip / AHB)
       │
       ▼ Present
Termux:X11
```

**[계약]** Omarchy v0.1.1 Hyprland presentation patch는 export 성공 시 SHM readback을 건너뛰고, KGSL이 implicit DMA-BUF fence를 붙이지 않는다고 명시하며 `glFinish()`로 “parent가 샘플하기 전 GPU 작업 완료”를 강제한다. native-fence hand-off는 “다음 최적화”로만 적혀 있다.

출처: `build/omarchy-v011-source/patches/hyprland/0001-render-carry-proven-Android-KGSL-presentation-path.patch` (`CGLRenderbuffer::unbind` export early-return 주석 + `glFinish()`).

**[계약]** Aquamarine는 presentation DMA-BUF를 `zwp_linux_buffer_params_v1`로 parent에 올리고, commit 직전 `AQ_ANDROID_DMABUF_GLFINISH`일 때만 **별도** `glFinish()`를 친다(HEAP/dmabuf allocator 경로 진단용). presentation override 자체에는 fence FD 필드가 없다.

출처: `build/omarchy-v011-source/patches/aquamarine/0001-wayland-carry-proven-Android-KGSL-buffer-pipeline.patch` (`CWaylandOutput::commit` GLFINISH 주석; `CWaylandBuffer` constructor의 `presentationDMABUF` create_immed).

**[실측·선행 보고]** (이 문서가 재측정하지 않음; next-doc §7 인용)

| 항목 | 보고 값 |
| --- | --- |
| `HYPRLAND_GL_DMABUF_EXPORT=1` | 활성; open FD에 `/dmabuf:` · `anon_inode:sync_file` |
| Termux:X11 AHB Present | N/N GPU @ ~120 FPS (HiDPI) |
| `HYPRLAND_SHM_PROFILE` | export early-return 때문에 hot path 미진입 |

출처: [2026-10-19-y900-graphics-acceleration-next.md](2026-10-19-y900-graphics-acceleration-next.md) §7.  
**공백 [실측]:** export 경로 `glFinish` 평균 µs, probe ok/fail — scaffold만 존재, 후보 바이너리 A/B 전.

---

## 2. Khronos `EGL_ANDROID_native_fence_sync` 계약 **[계약]**

공식 스펙: <https://registry.khronos.org/EGL/extensions/ANDROID/EGL_ANDROID_native_fence_sync.txt> (Version 3, 2012-09-04).  
Android 요약(동일 소유권 규칙): <https://source.android.com/docs/core/graphics/sync>

### 2.1 두 생성 모드

| `eglCreateSyncKHR(dpy, EGL_SYNC_NATIVE_FENCE_ANDROID, attribs)` | 의미 |
| --- | --- |
| `EGL_SYNC_NATIVE_FENCE_FD_ANDROID` = `EGL_NO_NATIVE_FENCE_FD_ANDROID` (-1) 또는 속성 생략 | **export 모드**: 현재 바인딩된 client API context의 command stream에 fence를 넣고, **다음 Flush** 이후 native fence FD가 sync에 붙는다. condition = `EGL_SYNC_PRIOR_COMMANDS_COMPLETE_KHR`. |
| `EGL_SYNC_NATIVE_FENCE_FD_ANDROID` = 유효한 FD | **import/wrap 모드**: 기존 native fence를 감싼다. EGL이 **FD 소유권을 가져감**; 호출자는 이후 그 FD를 쓰면 안 된다. condition = `EGL_SYNC_NATIVE_FENCE_SIGNALED_ANDROID`. |

필수: 현재 context (`eglGetCurrentContext` ≠ `EGL_NO_CONTEXT`), display 일치, client API가 fence를 넣을 수 있을 것. 그 외 attribute → `EGL_BAD_ATTRIBUTE`.

### 2.2 `eglDupNativeFenceFDANDROID`

- sync의 `EGL_SYNC_NATIVE_FENCE_FD_ANDROID`를 **dup**해 반환한다.
- FD가 아직 `EGL_NO_NATIVE_FENCE_FD_ANDROID`이면 → `EGL_NO_NATIVE_FENCE_FD_ANDROID` + `EGL_BAD_PARAMETER` (flush 전 dup이 여기 해당).
- **Issue #2 소유권:** EGL API로 넘기거나 받아오는 FD는 소유권 이전. **수신자가 close**. 제공자가 계속 쓰려면 먼저 dup.

### 2.3 `eglDestroySyncKHR`

native fence sync이고 내부 FD가 -1이 아니면 **그 내부 FD를 close**.  
따라서 올바른 export 순서: create → (flush) → **dup(호출자용 FD)** → destroy(sync; 내부 FD close) → 호출자가 dup FD를 parent에 넘김.

### 2.4 `glFinish`과의 관계

- `glFinish` = CPU가 prior GL 효과가 실현될 때까지 **블로킹**.
- native fence export = prior 명령 완료 시 신호되는 **sync_file**; CPU는 블로킹하지 않아도 되고, **소비자가 fence를 wait**해야 샘플링이 안전하다.
- fence를 만들고 hand-off 없이 `glFinish`만 제거하면 **stale/corrupt**가 계약상 예상 실패 모드다.

---

## 3. Mesa / freedreno 구현 **[계약]**

로컬 Mesa 트리(연구 복사본): `build/termux-va-research-20261012/mesa-source/` (upstream Mesa와 동일 경로의 1차 소스).

### 3.1 확장 광고

`egl_dri2.c`: `__DRI_FENCE_CAP_NATIVE_FD`가 있을 때만 `disp->Extensions.ANDROID_native_fence_sync = EGL_TRUE`.

```727:729:build/termux-va-research-20261012/mesa-source/src/egl/drivers/dri2/egl_dri2.c
   if (dri_fence_get_caps(dri2_dpy->dri_screen_render_gpu)
      & __DRI_FENCE_CAP_NATIVE_FD)
      disp->Extensions.ANDROID_native_fence_sync = EGL_TRUE;
```

freedreno: `caps->native_fence_fd = fd_device_version(screen->dev) >= FD_VERSION_FENCE_FD`.

```720:720:build/termux-va-research-20261012/mesa-source/src/gallium/drivers/freedreno/freedreno_screen.c
   caps->native_fence_fd = fd_device_version(screen->dev) >= FD_VERSION_FENCE_FD;
```

**공백 [실측]:** Y900 guest KGSL Mesa가 display extension 문자열에 `EGL_ANDROID_native_fence_sync`를 실제로 광고하는지, `FD_VERSION_FENCE_FD`를 만족하는지. (Hyprland는 기동 시 `eglCreateSyncKHR` / `eglDupNativeFenceFDANDROID`를 **무조건 load+RASSERT**하므로, 현 설치가 뜨면 심볼은 존재한다 — 확장이 비어 있어도 stub일 수 있어 probe가 필요.)

### 3.2 `eglCreateSyncKHR(EGL_SYNC_NATIVE_FENCE_ANDROID)` → flush 내장

```2931:2938:build/termux-va-research-20261012/mesa-source/src/egl/drivers/dri2/egl_dri2.c
   case EGL_SYNC_NATIVE_FENCE_ANDROID:
      dri2_sync->fence = dri_create_fence_fd(
            dri2_ctx->dri_context, dri2_sync->base.SyncFd);
      ...
```

`dri_create_fence_fd`에서 `fd == -1`(export)이면 **이미** `st_context_flush(st, ST_FLUSH_FENCE_FD, ...)`:

```130:136:build/termux-va-research-20261012/mesa-source/src/gallium/frontends/dri/dri_helpers.c
   if (fd == -1) {
      /* exporting driver created fence, flush: */
      st_context_flush(st, ST_FLUSH_FENCE_FD, &fence->pipe_fence, NULL, NULL);
   } else {
      /* importing a foreign fence fd: */
      ctx->create_fence_fd(ctx, &fence->pipe_fence, fd, PIPE_FD_TYPE_NATIVE_SYNC);
   }
```

즉 Mesa 경로에서는 create 시점에 fence-fd flush가 일어난다. 스펙의 “다음 Flush에서 native FD 생성”과 맞물린다.

### 3.3 `eglDupNativeFenceFDANDROID`

```2991:3009:build/termux-va-research-20261012/mesa-source/src/egl/drivers/dri2/egl_dri2.c
   if (sync->SyncFd == EGL_NO_NATIVE_FENCE_FD_ANDROID) {
      /* try to retrieve the actual native fence fd.. if rendering is
       * not flushed this will just return -1, aka NO_NATIVE_FENCE_FD:
       */
      sync->SyncFd = dri_get_fence_fd(
         dri2_dpy->dri_screen_render_gpu, dri2_sync->fence);
   }
   ...
   if (sync->SyncFd == EGL_NO_NATIVE_FENCE_FD_ANDROID) {
      _eglError(EGL_BAD_PARAMETER, "eglDupNativeFenceFDANDROID");
      return EGL_NO_NATIVE_FENCE_FD_ANDROID;
   }
   return os_dupfd_cloexec(sync->SyncFd);
```

flush가 안 됐거나 driver가 FD를 못 내면 dup 실패. 반환 FD는 cloexec dup; 호출자 close.

---

## 4. Hyprland 로컬 패치 — 이미 로드된 API, 쓰이지 않는 export hand-off **[계약]**

### 4.1 로드 / assert

presentation patch는 upstream과 같이:

- `loadGLProc(..., "eglCreateSyncKHR")`
- `loadGLProc(..., "eglDupNativeFenceFDANDROID")`
- `RASSERT` 둘 다

추가로 `eglExportDMABUFImageQueryMESA` / `eglExportDMABUFImageMESA`만 붙인다.

출처: 동일 hyprland presentation patch (`CHyprOpenGLImpl` ctor).

### 4.2 upstream `CEGLSync::create` 패턴 (재사용 후보)

Hyprland main은 release/explicit-sync용으로 이미 다음 순서를 쓴다:

1. `eglCreateSyncKHR(dpy, EGL_SYNC_NATIVE_FENCE_ANDROID, nullptr)`
2. `glFlush()` — 주석: “we need to flush otherwise we might not get a valid fd”
3. `eglDupNativeFenceFDANDROID`
4. 실패 시 `eglDestroySyncKHR` 후 null
5. 성공 시 `CEGLSync`가 sync+FD 소유; destructor가 `eglDestroySyncKHR`

출처: <https://github.com/hyprwm/Hyprland/blob/main/src/render/OpenGL.cpp> (`CEGLSync::create`).

Mesa export create가 이미 `ST_FLUSH_FENCE_FD`를 치므로 2)는 방어적 중복 flush에 가깝다. **export hand-off 구현 시에도 이 순서를 그대로 맞추는 것이 안전**하다.

### 4.3 presentation `unbind` — 지금

```text
if (m_gpuExported && presentationDMABUFActive()) {
    glFinish();   // ← hand-off 전까지 유지
    unbind FBO; return;
}
```

fence create/dup/attach **없음**. proc만 로드된 상태.

---

## 5. Aquamarine presentation 경로 — 누가 fence를 wait해야 하는가 **[계약]**

### 5.1 오늘

1. Hyprland가 `setPresentationDMABUF(attrs)`로 plane FD만 저장(dup).
2. Aquamarine `CWaylandBuffer`가 `zwp_linux_dmabuf` `create_immed`로 parent `wl_buffer` 생성.
3. `CWaylandOutput::commit`: `sendAttach` → damage → `sendCommit` (+ flush).
4. **acquire fence 요청 없음.** parent는 linux-dmabuf 페이로드만 받음.

따라서 **오늘 “누가 wait하나?” = Hyprland의 `glFinish()`뿐.** Aquamarine/Weston은 presentation export fence를 모른다.

`AQ_ANDROID_DMABUF_GLFINISH`는 `BUFFER_TYPE_DMABUF` allocator 버퍼용 진단이며, 런처가 `'0'`으로 두는 계약과 맞물린다. presentation export의 `glFinish`를 대체하지 않는다.

### 5.2 hand-off 시 올바른 waiter

소비자는 **native Weston**이다. Weston GL renderer는 acquire fence가 있으면:

1. `dup(acquire_fence_fd)`
2. `eglCreateSyncKHR(..., EGL_SYNC_NATIVE_FENCE_ANDROID, { EGL_SYNC_NATIVE_FENCE_FD_ANDROID, dupFd, EGL_NONE })` — wrap; EGL이 FD 소유
3. `eglWaitSync` (GPU-side wait)
4. `eglDestroySyncKHR`

출처: Weston `ensure_surface_buffer_is_ready` (mirror 예: <https://github.com/microsoft/weston-mirror/blob/f227edd6/libweston/renderer-gl/gl-renderer.c> 해당 함수; `EGL_SYNC_NATIVE_FENCE_*` + `wait_sync`).

그 FD는 Wayland **`zwp_linux_surface_synchronization_v1.set_acquire_fence(fd)`** 로 들어온다 (double-buffered; 다음 `wl_surface.commit`에 적용).  
프로토콜: <https://wayland.app/protocols/linux-explicit-synchronization-unstable-v1>

Weston 15.0.1은 이 프로토콜을 **지원**(표기 v2). `wp_linux_drm_syncobj_v1`은 Weston에서 미지원(x) — sync_file + explicit-sync v1이 이 스택의 현실적 경로.

### 5.3 따라서 Aquamarine의 역할

Aquamarine은 Wayland **client**(Hyprland→Weston). hand-off 설계:

| 단계 | 주체 | 동작 |
| --- | --- | --- |
| A | Hyprland `unbind` | export 렌더 후 `CEGLSync::create`와 동일하게 create→flush→dup; **`glFinish` 생략은 FD를 parent 경로에 넘긴 뒤에만** |
| B | Aquamarine | per-frame(또는 per-commit) presentation fence FD를 받아, parent가 `zwp_linux_explicit_synchronization_v1`을 advertise하면 `set_acquire_fence` 후 attach/commit |
| C | Weston | `ensure_surface_buffer_is_ready`가 GPU wait |
| D | Aquamarine | FD 소유권을 protocol로 넘기면 close하지 않음(프로토콜/서버가 수신); 실패 시 스스로 close + Hyprland는 `glFinish` fallback |

**Aquamarine이 commit 전에 `sync_wait(fd)`만 하고 fence를 parent에 안 넘기면**, guest CPU가 여전히 fence 신호까지 블로킹한다 → `glFinish`와 유사한 CPU 대기로, 파이프라인 overlap 이득이 거의 없다. **올바른 성능 hand-off는 Weston GPU wait**다.

**공백 [실측]:** 설치 native Weston이 `zwp_linux_explicit_synchronization_v1` global을 advertise하는지; Aquamarine Wayland backend가 그걸 bind하는지(현재 패치에는 없음).

---

## 6. Probe-only vs hand-off 설계

### 6.1 Probe-only (지금 scaffold) **[계약]**

위치: [`experiments/hyprland-export-fence/`](../../experiments/hyprland-export-fence/)

| Env | 효과 |
| --- | --- |
| `HYPRLAND_GL_EXPORT_PROFILE` | export 경로 `glFinish` 평균 µs (120프레임) |
| `HYPRLAND_GL_NATIVE_FENCE_PROBE` | create+dup 시도, ok/fail 카운트, **FD close**, **`glFinish` 유지** |

`apply.py`는 presentation patch의 export early-return만 계측한다. launcher 기본 env를 바꾸지 않는다. README acceptance: AHB Present 유지, stale 없음, probe crash 없음.

주의 (설계 메모): probe는 `glFlush`를 create와 dup 사이에 넣지 않는다. Mesa create가 `ST_FLUSH_FENCE_FD`를 치므로 대개 동작해야 하나, **upstream `CEGLSync::create`와 맞추려면 probe에도 `glFlush`를 넣는 편이 낫다** (실패율 해석이 Hyprland 본선과 동일해짐).

### 6.2 Hand-off 설계 (이 문서만; 구현 금지)

안전한 제거 조건(모두 만족):

1. create→flush→dup 성공 (`fd >= 0`, `!= EGL_NO_NATIVE_FENCE_FD_ANDROID`).
2. Aquamarine가 그 FD를 **같은 commit cycle**의 attach 버퍼에 대해 `set_acquire_fence`로 Weston에 전달 (또는 동등한 syncobj — 이 스택에선 비현실).
3. Weston이 fence를 import·wait (위 §5.2).
4. 실패 시 **반드시** 기존 `glFinish()`로 퇴각 (부분 성공 금지).
5. 수명: sync destroy는 dup 이후; Wayland로 넘긴 FD는 이중 close 금지; commit 실패 시 FD leak/early-close 방지.

**하지 말 것:** DMA-BUF plane FD만 넘기고 fence는 버리는 것; parent wait 없이 `glFinish` 삭제; `DMA_BUF_IOCTL_SYNC`로 GPU fence를 대체하는 것(CPU cache sync일 뿐; 기존 next-doc/native-browser 조사와 동일).

---

## 7. 실패 모드 (stale / corrupt / 기타)

| 실패 | 증상 | 원인(계약) |
| --- | --- | --- |
| Finish 제거 + acquire 미전달 | stale/tear/corrupt | parent가 미완료 GPU write를 샘플 |
| dup 실패 후 Finish 생략 | 동일 | Mesa “not flushed → -1” |
| wrap 시 FD를 호출자가 또 close | BAD_PARAMETER / 잘못된 wait | Issue #2 소유권 위반 |
| sync destroy 전 dup 없이 destroy | FD 소실 | destroy가 내부 FD close |
| 잘못된 FD를 `set_acquire_fence` | `INVALID_FENCE` | Weston `linux_sync_file_is_valid` |
| 같은 commit에 fence 두 번 | `DUPLICATE_FENCE` | 프로토콜 |
| Aquamarine만 `sync_wait`하고 Finish 제거 | 동작은 맞을 수 있으나 CPU 대기 잔존 | 성능 hand-off 실패(정합성≠이득) |
| 관측된 `sync_file` FD를 export hand-off로 오인 | 잘못된 완료 판정 | guest explicit-sync/release 등 **다른** 경로일 수 있음 **[실측 공백: /proc FD → 코드 경로 매핑]** |

---

## 8. Parent가 FD로 해야 할 일 (체크리스트) **[계약]**

Weston(실제 sampler) 기준:

1. Client(Aquamarine)로부터 `set_acquire_fence`로 sync_file FD 수신 → 서버가 소유.
2. 해당 `wl_surface.commit`의 dmabuf에만 적용.
3. GL 샘플 전: dup → `eglCreateSyncKHR(EGL_SYNC_NATIVE_FENCE_ANDROID, FD)` → `eglWaitSync` → `eglDestroySyncKHR`.
4. 프로토콜 미광고/미지원이면 client는 hand-off를 포기하고 producer `glFinish` 유지.

Aquamarine(중개) 기준:

1. Hyprland에서 fence FD + presentation dmabuf를 **한 프레임**에 묶음.
2. Registry에 explicit-sync global이 있으면 surface에 `get_synchronization` → commit 전 `set_acquire_fence`.
3. 없으면 FD를 close하고 Hyprland에 실패를 알려 Finish fallback (또는 Aquamarine이 Finish를 치지 말고 Hyprland가 Finish 유지).

linux-dmabuf ** alone**은 fence를 운반하지 않는다.

---

## 9. Probe vs hand-off — 한 줄 구분

| | Probe | Hand-off |
| --- | --- | --- |
| 목표 | `glFinish` 비용·create/dup 성공률 측정 | CPU `glFinish` 제거 + parent GPU wait |
| `glFinish` | **유지** | 성공 hand-off 시에만 생략 |
| FD | close (넘기지 않음) | Aquamarine → Weston `set_acquire_fence` |
| 코드 위치 | `experiments/hyprland-export-fence/` | hyprland unbind + aquamarine commit + Weston은 stock 기대 |
| launcher env | 변경 금지 | 후보 바이너리·trial env만 |

---

## 10. 순위가 매겨진 다음 코딩 스텝

1. **`experiments/hyprland-export-fence` 후보 빌드·배포** — presentation patch 위에 `apply.py`; `/opt/.../hyprland-export-fence` 후보만; launcher 기본 env 불변.
2. **HiDPI trial:** `HYPRLAND_GL_EXPORT_PROFILE=1` → `export glFinish: avg … us`가 load에서 나오는지. AHB Present N/N 유지 확인.
3. **같은 trial:** `HYPRLAND_GL_NATIVE_FENCE_PROBE=1` → ok/fail. fail이면 `eglGetError`/extension 문자열을 로그에 보강(scaffold 소패치). 가능하면 probe에 upstream과 같은 `glFlush` 삽입.
4. **PROFILE이 병목을 증명할 때만** hand-off 설계 착수: (a) Hyprland presentation attrs에 fence FD 슬롯, (b) Aquamarine `set_acquire_fence` if global exists, (c) 실패 시 `glFinish` fallback.
5. **Weston capability 실측:** nested 세션에서 `zwp_linux_explicit_synchronization_v1` advertise 여부. 없으면 GPU-wait hand-off 불가 → Finish 유지 또는 정책 재검토(Aquamarine CPU `sync_wait`는 ROI 낮음으로 기록만).
6. **A/B gate:** Finish-on vs hand-off — scroll/corrupt/stale, Present GPU offload, drop. 통과 전 production binary·env 고정 금지.
7. **비목표 유지:** resolution scale-down을 GPU 가속으로 포장하지 않음; `AQ_ANDROID_DMABUF_HEAP/VULKAN` 동시 변경 금지; Termux:X11 AHB ICD 건드리지 않음.

---

## 11. 출처 인덱스

| 주장 | 출처 |
| --- | --- |
| EGL native fence 의미·소유권·dup | <https://registry.khronos.org/EGL/extensions/ANDROID/EGL_ANDROID_native_fence_sync.txt> |
| Android sync / DupNativeFence 요약 | <https://source.android.com/docs/core/graphics/sync> |
| Mesa create/dup/flush | `build/termux-va-research-20261012/mesa-source/src/egl/drivers/dri2/egl_dri2.c`, `.../gallium/frontends/dri/dri_helpers.c` |
| freedreno `native_fence_fd` cap | `.../freedreno/freedreno_screen.c:720` |
| Hyprland export `glFinish` | `build/omarchy-v011-source/patches/hyprland/0001-render-carry-proven-Android-KGSL-presentation-path.patch` |
| Aquamarine presentation + GLFINISH | `build/omarchy-v011-source/patches/aquamarine/0001-wayland-carry-proven-Android-KGSL-buffer-pipeline.patch` |
| Hyprland `CEGLSync::create` | <https://github.com/hyprwm/Hyprland/blob/main/src/render/OpenGL.cpp> |
| Weston acquire wait | weston `gl-renderer.c` `ensure_surface_buffer_is_ready` |
| Wayland acquire fence | <https://wayland.app/protocols/linux-explicit-synchronization-unstable-v1> |
| Probe scaffold | `experiments/hyprland-export-fence/` |
| Live 기준점(재측정 아님) | `docs/research/2026-10-19-y900-graphics-acceleration-next.md` §7 |
