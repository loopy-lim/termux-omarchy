# GPU 가속 상태 확인과 성능 프로필 (Y900 · 한국어)

"가속이 안 되어서 느리다"를 판단하려면 먼저 **어느 구간이 GPU이고 어느 구간이 CPU 폴백인지** 알아야 합니다. 이 문서는 현재 Termux Omarchy 세션의 그래픽 파이프라인을 한 명령으로 점검하는 방법과, 체감을 위한 성능 프로필 전환 절차를 정리합니다.

## 파이프라인과 점검 지점

```text
[게스트 앱] → Hyprland(KGSL Mesa) → Weston(Zink/Turnip) → Termux:X11(AHB present) → Android 화면
                 hop: hyprland          hop: weston            hop: present
                                        hop: ahb (AHB 전송 설치 여부)
```

각 hop의 판정 근거는 세션 로그입니다. 도구는 로그를 **읽기만** 하고 런타임을 바꾸지 않습니다.

| hop | 근거(로그) | gpu 기준 | cpu 폴백 근거 |
| --- | --- | --- | --- |
| present | `x11.log`의 `N/M present copies offloaded to GPU` | offload ≥95% (실측 306/306, [연구](research/2026-10-19-y900-graphics-acceleration-next.md)) | 0/294 ([10-12 실측](validation/2026-10-12-termux-performance.md)) |
| weston | `weston.log`의 renderer 라인 | Adreno/Turnip/Zink | llvmpipe·softpipe |
| hyprland | `hyprland.log` export 라인 + fence 프로파일 로그 `export fence-handoff: ok=N finish_fallback=N` | ok>0 이고 fallback=0 | SHM 유지 또는 fallback>0 |
| ahb | `graphics-ahb/selection.json` + 파일 해시 | 설치·해시 일치 | 미설치(스톡 ICD, CPU present 가능) |

## 실행 방법 (Termux)

세션이 ready 상태일 때 Termux에서:

```sh
# 저장소 termux/omarchy_gpu_status.py를 기기의 같은 경로 관례로 복사해 둔 뒤
python3 ~/dev/termux-omarchy/termux/omarchy_gpu_status.py --human
```

`--human`을 빼면 schema-1 JSON 한 덩어리가 출력됩니다. JSON의 `exitIsToolSuccessOnly`가 말하듯 **exit 0은 도구가 정상 실행됐다는 뜻일 뿐, 가속 수락이 아닙니다.**

fence 후보(실험 패치 Hyprland)의 프로파일 로그는 기본 위치(rootfs `/tmp`와 `lr/`)에서 자동으로 찾지만, 다른 위치에 옮겼다면 `--fence-log <경로>`로 직접 지정할 수 있습니다(반복 지정 가능, 최신 집계 라인을 사용).

### 판정 해석

- 각 hop의 `state`: `gpu` · `degraded`(부분 offload, glFinish fallback 등) · `cpu` · `unknown`(증거 부재 — 세션이 stopped이거나 로그 형식을 못 읽음).
- `unknown`은 실패가 아니라 **증거가 없다**는 뜻입니다. 세션을 start한 직후 로그가 쌓이면 다시 실행하세요.
- `ahb: integrity-error`는 해시가 어긋난 것이므로 `graphics-ahb`를 재설치하거나 제거해야 합니다(스톡 ICD로 자동 회귀하며 present가 CPU로 떨어질 수 있음).
- 요약(`summary`)은 present·weston·hyprland 중 가장 나쁜 값입니다.

## 체감 조정: 성능 프로필

GPU 파이프라인이 정상이어도 **4K(3840×2560)·배율 2.5**에서는 픽셀량 자체가 비용입니다. 실측 기준 HiDPI 120Hz에서 `termux-x11` CPU ≈70%(60Hz trial에서 55–58%), performance(1920×1280·배율 1.25·120Hz)에서 ≈42%입니다([연구 §7](research/2026-10-19-y900-graphics-acceleration-next.md)). 이는 해상도 타협이지 "새 GPU 가속"이 아닙니다.

```sh
# 먼저 세션 종료 (실행 중 변경은 거부됩니다)
python3 <런타임 경로>/omarchy_runtime.py stop <request-uuid>
# performance 프로필 적용 후
python3 <경로>/omarchy_display.py performance
# HiDPI 복귀는 hidpi 프로필
```

`omarchy_display.py`는 데스크톱이 **완전히 종료**된 상태(terminationConfirmed)에서만 동작하며, Android 밀도와 Hyprland 배율·Chromium 배율을 한 쌍으로 바꿉니다. 중단 시 `display-before.json` 백업이 남습니다.

## 검증의 구분 (중요)

- 이 도구는 **구간별 GPU/CPU 여부**만 판정합니다. 체감 성능 수락(60/144fps, 프레임 드롭 ≤1%)은 별도 측정입니다: [성능 검증 기록](validation/2026-10-12-termux-performance.md), [스크롤](validation/2026-10-12-scroll-responsiveness.md).
- `GL_RENDERER=Adreno` 문자열 하나로 end-to-end 가속을 주장하면 안 됩니다 — [함정 목록](research/2026-10-19-y900-graphics-acceleration-next.md#4-비목표--함정) 참고.
- 남은 실측 병목(2홉 중첩 합성, 소프트웨어 영상 디코딩, HiDPI 픽셀량)은 도구가 아니라 [연구 문서의 실험 계획](research/2026-10-19-y900-graphics-acceleration-next.md#5-12주-연구-계획과-수락-기준)의 대상입니다.

## 도구 자체의 검증 상태와 한계

- 판정 규칙·보안 경계는 fixture 로그 테스트로 검증됐습니다: `python3 -m unittest tests.test_omarchy_gpu_status`.
- **실기기 세션에서의 실행 관찰은 아직 없습니다.** 기기 로그의 실제 형식이 fixture와 다르면 해당 hop은 `unknown`으로 나오며, 그 경우 실제 로그 라인을 근거로 파서를 갱신해야 합니다(추측 보강 금지).
- chroot/루트 가이드 경로의 그래픽 점검은 별도입니다: [Y900 chroot 워크스테이션 가이드 §8.2](y900-root-chroot-workstation-guide.md).
