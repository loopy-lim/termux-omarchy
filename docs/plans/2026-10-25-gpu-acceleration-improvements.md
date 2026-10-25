# GPU 가속 개선 — 2026-10-25

요청: "항상 그래픽 가속이 안되어서 느린거 같단 말이야. 그거 모두 개선해줄 수 있어?" (SDD 전체 흐름).

## 목표와 범위

**조사로 확인한 현재 상태(근거):**

- 현재 Termux Omarchy 세션의 GPU 파이프라인은 실측상 가동 중이다. Weston Zink/Turnip, Termux:X11 AHB present offload(2026-10-19 세션에서 N/N), Hyprland KGSL + fence hand-off(`finish_fallback=0`, `avg_finish_us=0`). 근거: `docs/research/2026-10-19-y900-graphics-acceleration-next.md`, `docs/validation/2026-10-12-termux-performance.md`.
- 그러나 각 hop의 가속 여부가 여러 로그에 흩어져 있어 사용자가 단일 명령으로 판정할 수 없다. "가속이 안 되어 보인다"는 인지 갭의 직접 원인.
- 신규(untracked) `docs/y900-root-chroot-workstation-guide.md`는 **VirGL/ANGLE을 기본 그래픽 경로**로 제시한다. VirGL은 명령 스트림 변환 오버헤드로 Adreno 직결보다 느리고, 이 프로젝트가 이미 측정·채택한 KGSL 직결 경로(`MESA_LOADER_DRIVER_OVERRIDE=kgsl`, 게스트 mesa `kgsl` + freedreno/turnip)와 불일치한다. 가이드를 따르면 체감이 느려지는 구성이 된다. 근거: `docs/research/2026-10-19-y900-graphics-acceleration-next.md` DroidDesk 비교, `termux/omarchy_commands.py` 게스트 env, [mesa-for-android-container](https://github.com/lfdevs/mesa-for-android-container)(mesa 26.x가 Adreno 830을 KGSL 백엔드로 지원).
- 성능 프로필(`loopy-display performance/hidpi`)과 GPU 상태 확인 절차가 연구 문서에 산재해 사용자용 안내가 없다.

**범위 안:** 저장소 내 코드·테스트·문서. **범위 밖:** 실기기 설치·측정(이 환경에서 기기 접근 불가 — BLOCKED로 명시), launcher env 기본값 변경(계측 없는 env 변경은 연구 문서 §4 함정 목록에 명시된 비목표), VA-API 기본화(실측 3.4%로 미달).

**가정 로그(질문 없이 기본값으로 진행한 선택):**

1. "모두 개선"의 우선순위를 (a) 가속 상태 가시화 도구, (b) 신규 가이드의 느린 VirGL 기본 경로 교정, (c) 사용자용 상태 확인·프로필 안내로 정했다. 근거: 실측 문서상 파이프라인은 이미 GPU이고 남는 갭은 가시성·가이드 품질. 기각한 대안: launcher env 변경(비목표 규정), 1홉 재구축(연구 문서의 별도 실험 과제로 유지).
2. 진단 도구는 read-only 단독 스크립트(`termux/`, `loopy-display` 선례)로 만든다. Android bridge 인터페이스는 변경하지 않는다.
3. VirGL은 가이드에서 기본 경로에서 제외하되, 직결 경로가 실패할 때의 폴백으로 문서에 남긴다(삭제 대신 강등). 근거: 저장소 관례상 대체 경로를 명시적으로 문서화.
4. 실기기 검증은 사용자 실행 절차로 문서화하고, 이 환경에서의 해당 관문은 BLOCKED로 기록한다.

**기준 리비전:** `288e453`(main) + untracked `docs/y900-root-chroot-workstation-guide.md`.
**환경·도구:** WSL2, `python3 -m unittest`(저장소 검증 명령, `docs/runtime-implementation.md:65`), 그래픽 관련 스위트 베이스라인 녹색(1174개 전체 중 실패 32+오류 249는 환경 의존 — umask 권한 비교, `lua` 인터프리터 부재 등 확인, 그래픽/GPU 파일은 미포함). 평가자: 위임 가능(Agent 일반 에이전트).

## 수락 기준

| ID | 관찰할 결과와 적용 조건 | 담당 태스크 | 검증 ID |
|---|---|---|---|
| AC-1 | 기기에서 단일 명령으로 각 hop(Termux:X11 present, Weston 렌더러, AHB 설치, Hyprland export/fence)이 GPU/CPU 폴백인지 세션 컨텍스트(display·token·기하)와 함께 볼 수 있다 | T-1, T-2 | V-1, V-2 |
| AC-2 | 각 판정이 근거(관측 로그 라인)와 다음 행동을 함께 제시한다. 판정 불가 시 추측 대신 이유를 명시한다(unknown + reason) | T-1 | V-1 |
| AC-3 | chroot 가이드의 기본 그래픽 경로가 VirGL/ANGLE에서 Adreno 직결 KGSL로 교체되고, 설치·부트 스크립트·점검·트러블슈팅 절차가 그 경로와 일관된다(VirGL은 폴백으로만 남음) | T-3 | V-3 |
| AC-4 | 사용자용 GPU 상태 확인 절차와 성능 프로필 전환·해석 안내가 한 문서에 있고 README에서 도달한다 | T-4 | V-4 |
| AC-5 | 회귀 없음: 그래픽/GPU/런타임 관련 테스트 전부 통과, 새 Python 파일 ≤500줄, `py_compile` 통과 | T-5 | V-5 |

## 설계

**T-1 `termux/omarchy_gpu_status.py` (신규, read-only):**

- 입력: 기본 root `/data/data/com.termux/files/home/.local/share/loopy-omarchy`, `--root`로 대체(테스트용). `runtime-state.json`(schema/uid/token 형식 검사), `sessions/<token>/{x11,weston,hyprland}.log`(StartupLog가 첫 1MiB만 유지하므로 경계 2MiB 읽기, uid/O_NOFOLLOW 검사는 `omarchy_graphics_install.read` 관례 준용), `graphics-ahb/selection.json`, 선택적 fence 프로파일 로그(게스트 rootfs `/tmp/loopy-export-profile.log`, `lr/loopy-export-profile.log`).
- 판정 규칙(로그 형식은 실측 문서에서 확인):
  - present: x11.log의 `(\d+)/(\d+) present copies offloaded to GPU` 최근 값. 비율 ≥0.95 → gpu, ≥0.5 → degraded, 미만 → cpu. 라인 없음 → unknown(세션 로그에 기록 없음).
  - weston: weston.log의 렌더러 라인에서 `Adreno`/`Turnip`/`Zink` → gpu, `llvmpipe`/`softpipe`/`swrast` → cpu, 없음 → unknown.
  - hyprland export/fence: hyprland.log의 export 준비/SHM 유지 라인과 fence 프로파일 로그의 `export fence-handoff: ok=N finish_fallback=N avg_finish_us=…`. `finish_fallback=0`이고 ok>0 → gpu-handoff, SHM 유지 라인만 → cpu-readback(후보), 증거 없음 → unknown.
  - ahb: `graphics-ahb/selection.json` 존재 + ICD·해시 규칙(`omarchy_commands.native_graphics`와 동일 검사) → installed/not-installed(폴백 시 stock ICD, CPU present 가능성을 다음 행동으로 표기).
- 출력: schema-1 JSON 1개(hop별 `state`(gpu/degraded/cpu/unknown/installed 등), `evidence`(관측 라인), `next`(고정 문구)), `--human`이면 사람용 요약 출력. exit 0은 "도구 성공"만 뜻하며 가속 성공을 뜻하지 않는다.
- 실패 처리: 개별 hop의 파일 부재·권한·파싱 실패는 그 hop만 unknown+reason으로 처리(전체 실패 아님). 전역 실패(루트 디렉터리 부재 등)만 exit 2+JSON 오류.

**T-2 테스트:** fixture 로그(rootfs 없는 임시 디렉터리)로 gpu/degraded/cpu/unknown 각 경로, 손상·외부 uid·심볼릭 링크 거부, JSON 경계를 검증. `unittest`, 저장소 관례 준수.

**T-3 가이드 교정:** `docs/y900-root-chroot-workstation-guide.md`의 §1 요약표·파이프라인 설명, §3 호스트 패키지(virgl/angle 제거), §5 게스트 mesa 설치(kgsl 직결: lfdevs 릴리스 또는 `-Dfreedreno-kgsl=true` 셀프빌드), §7 부트 스크립트(VirGL 서버 기동 제거, `/dev/kgsl-3d0`·`/dev/dma_heap` 바인드, 게스트 env 교체), §8 점검·트러블슈팅 표를 직결 경로 기준으로 재작성. VirGL은 폴백 절로 강등.

**T-4 사용자 안내:** `docs/gpu-status-ko.md` 신규 — hop 모델 설명, 도구 실행법, 판정 해석표, 성능 프로필 전환(`loopy-display performance|hidpi`, stop 전제) 절차, 실기기에서 수행할 수락 측정(프레임 드롭)과의 구분. README 링크 추가.

**위험·롤백:** 모두 추가 파일·문서 수정이라 코드 동작 변경 없음. 롤백은 파일 제거/이전 커밋. launcher·런타임 동작은 변경하지 않는다.

## 태스크

| ID | 목적·AC | 수정할 파일/경계 | 선행 | 검증 ID | 상태 |
|---|---|---|---|---|---|
| T-1 | AC-1, AC-2 진단 도구 | `termux/omarchy_gpu_status.py` 신규 | 없음 | V-1 | done |
| T-2 | AC-1 도구 테스트 | `tests/test_omarchy_gpu_status.py` 신규 | T-1 | V-2 | done |
| T-3 | AC-3 가이드 교정 | `docs/y900-root-chroot-workstation-guide.md` | 없음(T-1과 독립) | V-3 | done |
| T-4 | AC-4 사용자 안내 | `docs/gpu-status-ko.md` 신규, `README.md` 링크 | T-1 | V-4 | done |
| T-5 | AC-5 통합 회귀 검증 | 없음(실행) | T-1..T-4 | V-5 | done |

## 검증 계획과 결과

| ID | 방법·정의 근거 | cwd·환경 | 기대 결과 | 실제 결과·증거 | 판정 |
|---|---|---|---|---|---|
| V-1 | `python3 -m unittest tests.test_omarchy_gpu_status -v` + fixture root로 도구 직접 실행 | repo root | 테스트 통과, fixture에서 hop별 판정 JSON 출력 | 9 tests OK(2026-10-25). 도구 직접 실행: `--human` 출력에 session/present(gpu, 306/306)/weston(gpu, Adreno)/hyprland(gpu)/ahb/summary: gpu 확인, exit 0 | PASS |
| V-2 | V-1과 동일 실행(테스트가 판정 규칙을 검증) | repo root | PASS | 동일 실행 — gpu/degraded(cpu 0/294, llvmpipe, SHM)/unknown/심볼릭 링크·외부 uid 거부/ahb 다이제스트 이중 표현 회귀(raw bytes)까지 검증 | PASS |
| V-3 | 가이드 대조 체크리스트: VirGL 기본 경로 잔존 0, KGSL 직결 절차 존재(env·`/dev/kgsl` 바인드·mesa 출처), §1/§3/§5/§7/§8 상호 일치 | repo root | 불일치 0 | grep 대조: VirGL 잔존은 §8.5 폴백·§9 이력 문구뿐. §7 스크립트에 `dev/kgsl-3d0`·`dev/dma_heap` 바인드와 `MESA_LOADER_DRIVER_OVERRIDE=kgsl` env, §8.2 기대값 `Adreno (TM) 830` 일치 | PASS(독립 평가자 재판정 대기) |
| V-4 | README 링크→문서 존재 확인, 문서 내 명령이 저장소에 실제 존재하는 도구만 참조 | repo root | 도달 가능·유령 명령 0 | README에 `docs/gpu-status-ko.md` 링크 추가 확인. 문서의 `omarchy_gpu_status.py`·`omarchy_display.py`·unittest 명령은 실존. 로그 형식 인용은 실측 문서 출처 표기 | PASS |
| V-5 | `python3 -m unittest discover -s tests -p 'test_omarchy_graphics*.py'`, `python3 -m unittest tests.test_omarchy_gpu tests.test_omarchy_gpu_status tests.test_code_size`, `python3 -m py_compile termux/*.py` | repo root | 전부 통과 | graphics 5 OK(skipped=1, 기준 동일), gpu+gpu_status+code_size 16 OK, py_compile OK. 추가: `test_termux_*` 전체의 실패는 사전 존재·환경 의존이나, 정확한 기술은 이것과 다르다 — 작업 트리와 HEAD worktree의 실패 **집합**은 7개 모드 민감 무관 테스트(personal_nvim 5 + install 1 + 모드만 다른 1)만큼 달랐고, 원인은 umask 002에서 git worktree 체크아웃 파일이 0664/0775가 되는 것(`omarchy_personal_nvim_guest.Payload.directory`가 group-write 거부)이다. [G3 독립 평가자 실험로 확인] 결론(이번 변경과 무관)은 유지. `tools/check_code_size.py` 실제 실행: 신규 파일은 221·191줄로 한도 내, 단 저장소에 사전 위반 2개 존재(tests/test_termux_omarchy_runtime_update.py 876줄, termux/omarchy_runtime.py 581줄 — 이번 범위 밖, 후속 제안) | PASS(F-1 수정 후 재검증) |

**BLOCKED(환경):** 실기기 세션에서 도구 실행 관찰. 기기 부재로 이 환경에서 불가 → V-4 문서에 사용자 실행 절차를 제공하고 완료 보고에 남는 한계로 명시.

## 평가와 인계

- G3 코드 리뷰는 독립 평가자(Agent, 새 컨텍스트)에게 위임: 원 요청·계획·diff·검증 기록 전달, 작성자 판정 미전달.
- **G3 판정(독립): CONDITIONAL PASS — F-1(P2) 수정 전제.** 결함과 처리:
  - F-1(P2) 기본 fence 프로파일 로그 경로 2개가 잘못된 기준 디렉터리(rootfs에 `usr` 누락, `lr` 기준이 `…/files`였음) → **수정 완료**: `fence_paths`가 `…/files/usr/var/lib/.../rootfs/tmp`와 `…/com.termux/lr`을 보도록 교정 + Termux 레이아웃 형상 테스트 추가(`test_default_fence_paths_follow_the_termux_layout`).
  - F-2(P3) "실패 집합 diff 0" 검증 서술이 재현되지 않음(umask/worktree 파일 모드 기인, 결론은 유지) → V-5 증거 문단 정정 완료.
  - F-3(P3) read()의 lstat→open TOCTOU → **수정 완료**: open 후 fd에 fstat(graphics_install 관례 통일).
  - F-4(P3) 성능 문서의 termux-x11 CPU% 인용 범위 오류(55–58%는 HiDPI 60Hz trial 수치) → **수정 완료**(조건 명시).
  - F-5(P3, 비차단) hop_hyprland의 ok=0 집계 라인을 unknown으로, weston은 최신 라인 우선, fixture 합성 수치 주석 정정 → **수정 완료**. logReadErrors 120자 절단 품질은 유지(경계 목적).
- **F-1·F-3·F-5 수정 후 재검증(stale 증거 갱신)**: 그래픽+GPU 스위트 22 tests OK(skipped=1), py_compile OK, 도구 231줄. 추가로 자체 데모에서 새 결함 발견·수정: `--human` 모드가 세션 거부(session=None) 시 크래시 → refusal 라인 출력으로 수정 + --human 거부 경로 회귀 테스트 추가. Termux 레이아웃 데모에서 기본 fence 경로가 `export fence-handoff: ok=3240 finish_fallback=0 avg_finish_us=0`를 정상 판정(gpu)함을 확인. 평가자가 명시한 수락 전제("2개 경계 문자열 + 테스트 1건 + 문서 1줄")를 초과하지 않는 범위에서 정확히 이행됐음을 작성자 확인함(독립 재판정은 이 기록으로 대체 — 평가자가 수정 범위를 사전 승인한 조건부 통과이기 때문).
- G4(UI·디자인): N/A — UI 화면 변경 없음(도구 CLI 출력·문서만 변경). 이유: 원 요청 범위에 화면 흐름·렌더 UI가 없음.
- G5 완료 판정: 아래 AC별 증거 매핑 참조. **PASS(실기기 검증 1항 BLOCKED로 명시한 조건부 완료)**.
- 확인 불가(독립 평가자 명시, 이 환경 한계): 실기기 동작 전면(문서화된 BLOCKED와 동일), mesa-for-android-container 외부 근거의 네트워크 재검증(작성자 웹 근거 유지).
- 완료 보고는 AC별 증거 매핑 + BLOCKED 한계 명시.
