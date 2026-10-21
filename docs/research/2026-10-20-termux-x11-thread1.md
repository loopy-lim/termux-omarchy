# termux-x11 Thread-1 병목 — 최적화 착수 결정 (2026-10-20)

목적: 남은 최대 CPU 소비처인 Termux:X11 `Thread-1`(LorieNative present 경로)에 대해, 다음 1건의 실험을 **수락/기각 기준과 함께** 확정한다. 이 문서는 착수 결정이지 최적화 완료가 아니다.

증거 표기: **[계약]** = 소스·스펙이 요구하거나 구현하는 동작. **[실측]** = 이 기기·세션에서 관측된 사실. 재인용은 출처를 밝힌다.

선행: [YouTube tearing 조사](2026-10-20-youtube-tearing-investigation.md) §3(남은 병목), [Y900 graphics next](2026-10-19-y900-graphics-acceleration-next.md) §1–3, [AHB WSI 실험](../../experiments/termux-x11-ahb-wsi/README.md).

## 1. 현재 관측 (재인용)

| 관측 | 값 | 출처 |
| --- | --- | --- |
| termux-x11 Thread-1 CPU | **86–96%** (AHB present 관리, 119.6 FPS, present GPU offload 435/435) | [tearing 조사](2026-10-20-youtube-tearing-investigation.md) §3 [실측] |
| native 브라우저 경로에서도 동일 | "남은 최대 소비처: termux-x11 Thread-1 86%" | 동일 문서 §2 [실측] |
| AHB present 자체 | GPU offload N/N — **Present copy는 이미 GPU** | 동일 문서 · [next 문서](2026-10-19-y900-graphics-acceleration-next.md) §7 [실측] |
| termux-x11 kernel CPU | 높은 kernel 비중이 AHB GPU present와 공존(fence/binder/스케줄) | [next 문서](2026-10-19-y900-graphics-acceleration-next.md) §1 [실측 해석] |

**핵심 판정:** Thread-1 비용은 GPU present copy 자체가 아니라, present **관리**(AHB allocation/acquire/release, fence 대기, 버퍼 수명)와 **X11 wire SHM 업로드**의 합으로 추정된다. 둘의 비율은 아직 분해되지 않았다 — **[실측 공백]**.

## 2. 후보 평가

### A. Termux:X11 자체 빌드에 경량 계측 삽입 — **채택 (다음 실험)**

| 항목 | 내용 |
| --- | --- |
| 가설 | Thread-1 비용의 지배 항이 측정 가능한 3개 항(present copy 관리 / wire SHM 업로드 / fence 대기) 중 하나로 분해되면, 최적화 대상이 확정된다 |
| 근거 | 레포가 Termux:X11을 자체 패치·빌드·기기 배포한 선례가 있음 [계약/선례] `experiments/termux-x11-ahb-wsi/` |
| 방법 | 자체 AHB WSI 빌드에 5초 창 카운터 삽입: (1) AHB acquire/release 횟수·소요 µs, (2) X11 wire 업로드 bytes·µs, (3) fence/sync wait µs — LorieNative 로그 또는 파일 싱크로 출력 |
| 위험 | 계측 I/O가 측정 왜곡 (파일 싱크는 세션 종료 후 덤프로 완화); 빌드 드리프트 |
| 반증 | 3항 합이 Thread-1 CPU의 절반에도 못 미치면 분해 프레임 자체를 재검토 |

### B. DRM render node 대체(vkms wrap) — **보류**

게스트 Chromium ozone-wayland의 DRM 노드 요구를 우회하는 커널/드라이버 수준 실험. 이번 네이티브 브라우저 기본화로 브라우저가 게스트 4홉을 떠나므로, 이 후보의 수혜 범위가 게스트 앱으로 축소된다. 비용 대비 우선순위 하락 — 재평가 트리거: 네이티브 브라우저 전환 후에도 게스트 Wayland 앱 수요가 남을 때.

### C. Chromium ozone-wayland dmabuf-only 폴백 패치 — **보류**

`wayland_buffer_manager_gpu.cc`의 DRM 노드 실패 시 linux-dmabuf 폴백. upstream Chromium 빌드 인프라가 레포에 없고, 수혜 역시 게스트 브라우저 한정 — B와 같은 축소 논리.

### D. Xwayland DRI3 pixmap import X error 11 — **병행 가능하나 후순위**

커스텀 `/opt/loopy-xwayland-kgsl`의 일부 버퍼 SHM 폴백 수정. 게스트 경로 한정 + 오류 재현 조건이 아직 좁혀지지 않음 [실측 공백: 어떤 버퍼 크기/포맷에서 BadRequest가 나오는가].

## 3. 결정과 다음 실험 (수락/기각)

**결정: A(Termux:X11 계측 착수)를 다음 실험으로.** 이유: (1) 네이티브 브라우저 기본화 후에도 모든 경로의 공통 최대 소비처, (2) 자체 빌드·배포 선례로 실현 가능성이 확실, (3) B/C/D는 모두 이번 전환으로 수혜가 축소.

실험 스캐폴드: `experiments/termux-x11-thread1-profile/` (신규; AHB WSI 빌드 체인 재사용).

수락: 5초 창 카운터가 idle/scroll/video 3 조건에서 Thread-1 CPU%를 3항으로 분해하고, 지배 항이 ≥50%로 식별될 것.
기각: 3항 합 < Thread-1 CPU의 50% → 분해 프레임 폐기, 대안(Perfetto/system-wide trace) 재검토.
롤백: 계측 빌드 제거 후 stock Termux:X11 APK 복귀 (APK 비파괴 교체 관례 준수).

## 4. 실측 공백 (2026-10-21 1차 충원)

- **[실측]** Thread-1 = 10초 창 6.41초 CPU, **user 0.04 / sys 6.37 (99.4% 커널)** — 세션 idle 기준, receipt `build/diagnostics/gpu-defaults-deploy-20261020/13-thread1-sample.json`. 지배 항은 커널 경로(AHB dma-buf ioctl/fence/binder)로 특정됨 → §3 실험 A의 카운터 설계는 커널 호출별 소요 분해로 조준을 좁힌다.
- **[실측]** 재진입 벽시계 0.40–0.49초(5회), phases 귀속: 활동 시작 265ms / ensure 136ms — ensure 최적화는 게이트 미충족으로 기각. receipt `12-reentry.json`.
- **[실측 공백]** video/scroll 부하 under Thread-1 CPU%와 3항 분해(AHB present 관리 vs wire 업로드 vs fence 대기) — 부하 재현 후 동일 샘플링으로 보강.
- **[실측 공백]** 네이티브 브라우저 기본화 이후 Thread-1 CPU% 재측정 (mimeapps 전환은 적용됐으나 브라우저 클릭 경유 사용은 사용자 확인 대기).
