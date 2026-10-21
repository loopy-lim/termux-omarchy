# 4K HiDPI 실제 휠 스크롤 검증

이 검증은 파일 저장 반영 시간을 스크롤 반응속도로 취급하지 않는다. Y900(ADB Y900, TB522FU)의 3840×2560, Hyprland scale2.5, native Chromium에서 실제 XTest 휠 버튼 입력을 외부 Termux:X11 → Weston → Hyprland → Xwayland → 앱까지 보냈다. Notion 로그인 상태의 기존 페이지는 읽고 스크롤만 했으며 본문을 수집하거나 편집하지 않았다. Code는 별도 로컬 시험 프로젝트의 5,001줄 fixture를 사용했다. 원격 SSH 검증은 사용자 요청대로 제외했다.

## 측정 경계

[scroll-run.mjs](../../build/diagnostics/termux-omarchy-performance-20261012/scroll-run.mjs)와 [native input](../../build/diagnostics/termux-omarchy-performance-20261012/scroll-native-input-template.py)이 100ms 간격의 휠64회 또는256회(8회 아래/8회 위 반복)를 보낸다. rAF에서 문서 위치 변화를 기록하고, 별도로 Android SurfaceFlinger의 실제 presentation timestamps를 수집한다. 화면 내용·Notion 제목·인증 토큰은 수집하지 않는다.

- wheel arrival는 XTest 제출부터 JS wheel handler까지다. 손가락/USB 장치부터 패널의 빛까지인 input-to-photon 수치가 아니다.
- rAF/위치 변화는 앱의 스크롤 진행을 나타낸다. SurfaceFlinger가 프레임을 표시했다는 것만으로 그 프레임의 스크롤 내용이 새로 바뀌었다고 판단하지 않는다.
- ready-to-present는 Android 출력 경로의 일부 대기시간이며 전체 입력 지연과 합산하지 않는다.
- 최초 입력 손실 또는90ms 이상 지연/모호한 매칭은 matchedWheels 수에 드러낸다. 매칭된 표본의 p95만으로 전체 입력에 대한 보장을 하지 않는다.
- `MEASURED`는 유효한 움직임을 측정했다는 뜻이다. 무지연/무손실 성능 PASS가 아니다.
- 최종 시험은 Hyprland에서 대상 창을 먼저 focus한 뒤 입력 좌표를 다시 구한다. 가로 스크롤 레이아웃에서 Code+YouTube 또는 YouTube+Notion이 보이며, 세 창이 항상 동시에 화면 안에 있는 것은 아니다.
- 영상은 각 receipt의 videoBefore/After에 1920×1080, paused=false, hidden=false가 모두 있어야 동시 재생 시험으로 취급한다. 최종 MAILBOX visible/endurance 시험은 추가로 video element의 실제 물리 좌표와 visibleAreaRatio≥0.95를 앞뒤에서 확인한다. 이전 FIFO 비교에는 이 물리 가시성 조건이 없어 엄격히 동일한 동시 영상 부하의 A/B라고 단정하지 않는다. 초기 `code-scroll120-video.json`의 videoBefore/After=null은 영상 동시 재생 수락에서 제외한다.

## 확인한 원인과 수정

### Code 휠 단위

기존2.5배 HiDPI에서는 한 칸이 wheelDeltaY80으로 들어왔다. [VS Code StandardWheelEvent](https://github.com/microsoft/vscode/blob/main/src/vs/base/browser/mouseEvent.ts)는 Chrome123이후 wheelDeltaY/120을 사용하고, [MouseWheelClassifier](https://github.com/microsoft/vscode/blob/main/src/vs/base/browser/ui/scrollbar/scrollableElement.ts)는 분수·비정수 배수 입력을 터치패드 쪽으로 분류한다. 실제로 smoothScrolling=true만으로는64입력당62–64개 위치 변화에 그쳤다. Hyprland input.scroll_factor=1.5로 정규화하면 wheelDeltaY120이 되어 같은64입력에서684개 중간 위치 변화가 기록됐다(`code-scroll120-factor-video.json`). 이는 스크롤 애니메이션의 개선이며 전체 입력 지연0ms 증거가 아니다. Notion의 한 칸 이동 거리도1.5배가 되므로 이전 factor1.0의 거리와 동일 부하라고 비교하지 않는다.

Code의 `editor.smoothScrolling`과 `workbench.list.smoothScrolling`을 실제 설정 UI에서 활성화했다. `editor.inertialScroll` 후보는 긴 관성 이동을 만들어 false로 원복하고 페이지 재로딩 후 확인했다. 설정 토글만 확인한 결과와 재생성된 편집기의 실제 동작을 구분했다.

### 출력 cadence

기존 [commands](../../termux/omarchy_commands.py)는 Weston·Omarchy·Aquamarine 모두60000mHz였다. 현재는 owned `display-refresh.json`의 검증된 cadence를 세 경로에 동일하게 전달한다. 파일 없는 기존 설치는60Hz를 유지한다. 120Hz 시험에서 Android active mode1, Termux XRandR119.96Hz, Hyprland120Hz, 실제 Android 표시 간격8.33ms를 각각 확인했다. 표시 모드 이름만으로120fps라고 판단하지 않았다. [primary source 조사](../research/2026-10-12-y900-refresh-queue-latency.md).

Weston repaint-window7→4ms는 실제 표시 간격의 tail을 악화시키고 ready-to-present도 약22ms로 유지돼 기각했다.7ms로 원복했다.90Hz도 같은4K/scale에서 별도로 비교했다.

### 전체 세션 종료

Code reload 시 정상 extension host가 동일한 `vscode-git-*.sock` 이름으로 IPC socket을 재생성하면 기존 resource ledger가 `resource-replaced`로 전체 데스크톱을 종료했다. 이 경우는 Android OOM/phantom kill이 아니었다. [resources](../../termux/omarchy_resources.py)는 정확한 이름·socket종류·동일UID/dev/mode·변경inode·SO_PEERCRED·owned process의 엄격한 PID identity·재확인이 모두 맞을 때만 이를 허용한다. 임의 runtime replacement를 허용하지 않는다. [Linux 실 socket7개 테스트](../../tests/test_omarchy_vscode_rebind.py)가 통과했고 수정 이후 reload 및 여러 정상 stop/start가 지속됐다. 실패 당시 runtime은 삭제하지 않고 recovery archive로 보존했다.

## 검증 파일

전체 raw 측정은 `build/diagnostics/termux-omarchy-performance-20261012/*scroll*.json`에 있다. 유효한 대표 baseline은 `code-scroll-baseline2.json`, `notion-scroll-video-baseline.json`이다. `notion-scroll-baseline{,2}`는 X window 탐색 실패, `code-scroll-baseline.json`은 Monaco scrollTop 대신 transform을 측정해야 했던 수집 오류로 성능 수락에서 제외했다.

새 cadence 전달 경계 테스트2개와 Linux IPC replacement 테스트7개가 통과했다. 이 결과는 범용 installer/전체 제품 테스트 통과 또는 원격 SSH 실사용 수락을 의미하지 않는다.

## FIFO 출력 대기 추가 진단

4KiB가 아닌4MiB ring의 `cc,viz,benchmark,input` metadata-only trace를 수집했다. 최초 넓은 category trace는100MiB 상한을 넘어 폐기했고, URL·본문·임의 문자열 args·screenshot은 보존하지 않았다. 성공 파일은 `notion-scroll-frame-trace-summary.json`이다. Notion PID7945는 CDP ProcessTime65.34와 SystemInfo의 유일한 renderer CPU time65.34 일치로 연결했다. trace 자체의 부하가 있으므로 그때의 FPS는 개선 수락으로 사용하지 않는다.

- 실제 BeginFrame interval8336µs로, browser 직전 Xwayland RandR도119.96Hz였다. 마지막 browser 경로만60Hz라는 가설은 맞지 않았다.
- pending swap ACK span261개는 median4.10ms, p9513.59ms,max19.39ms였다. 다른 창의 swap도 포함하므로 Notion 전용 수치로 쓰지 않는다. Chromium의 FIFO/pending1 기본 동작으로도 throttle이 생길 수 있으며 Xwayland 결함을 확정한 것은 아니다.
- Notion의 BeginMainFrame은22.68ms까지 걸렸다. Longtask50ms 문턱 아래에서도120Hz frame budget8.33ms를 넘는다.
- FrameSequenceTracker에서 Notion expected98/dropped_v4 30, expected99/dropped_v4 35 표본이 관측됐다. tracker 종류·기간이 겹칠 수 있어 합산 손실률로 표현하지 않는다.
- native Vulkan query에서 MAILBOX가 지원되고 설치 libvulkan_freedreno에 `MESA_VK_WSI_PRESENT_MODE` override가 존재함을 확인했다(`scroll-mailbox-support.json`). browser에만 MAILBOX를 주는 비교를 수행한 뒤 해당 설정을 선택했다. Weston 환경·image count·fence 해제 규칙은 바꾸지 않는다. 실제 내부 present mode는 Vulkan 표준 query로 역조회할 수 없으므로 지원/환경/동작 결과와 driver source를 구분한다.


## 선택한 설정과 실제 스크롤 결과

`MESA_VK_WSI_PRESENT_MODE=mailbox`를 native Chromium 실행 환경에만 적용했다. 설치 드라이버의 지원과 GPU process 환경, 실제 동작 변화가 근거다. Vulkan 표준 API로 내부 선택된 mode를 역조회했다는 주장은 하지 않는다. 같은 id로 연결한 swap ACK span은 FIFO p95 13.59ms에서 MAILBOX 6.18ms로 줄었다. 서로 다른 trace의 단순 이벤트 개수는 비교하지 않았다. `--disable-renderer-backgrounding`은 뚜렷한 이득이 없어 채택하지 않았고, GPU raster 경로에서 사용되지 않는 `--enable-zero-copy`도 추가하지 않았다.

| 실제256회 휠 시험 | 앱 rAF 간격 p95 | 33.5ms 초과 간격 | YouTube 손실 |
| --- | ---: | ---: | ---: |
| FIFO Notion (`notion-scroll-final-long`) |25.1ms|19|50/1,643|
| MAILBOX Notion (`notion-scroll-mailbox-visible-long`) |16.8ms|6|15/1,658|
| FIFO Code (`code-scroll-final-long`) |16.6ms|12|52/1,646|
| MAILBOX Code (`code-scroll-mailbox-visible-long`) |8.4ms|4|13/1,673|

모두4K/120Hz/scale2.5/factor1.5다. FIFO의 영상 물리 가시성 기록 한계는 위와 같다. MAILBOX Code의 입력256개 중252개만 시간 매칭되어, wheel arrival p95 19.59ms는 매칭 표본에 한정한다. Notion은256개 모두 매칭되며 p95 28.27ms였다. 이는 input-to-photon 지연이 아니다. Android ready-to-present p95는 여전히 약22ms로, 출력 대기 전체를 없앤 것은 아니다.

### 연속 시험

`scroll-endurance-1`부터 `-6`까지 총1,536회 휠 입력을 보냈다. 약180초 메모리 관측 동안 MemAvailable 최저624,992KiB, SwapFree 최저2,023,952KiB였다. 앞의5개 구간(1,280회 입력, 순수 입력128초)은 영상1080p60의 재생·물리 가시성 조건을 모두 만족했다. 합계8,298프레임 중105프레임 손실(1.27%)이었고 Notion rAF p95는16.7ms, Code는8.4ms였다.

마지막6번째 구간은 영상이634.601초에서 paused=true로 끝나고 가시 영역도44%로 바뀌어 `INVALID_VIDEO_VISIBILITY`로 제외했다. 이 구간을 포함해 “3분간 유효한 동시 영상 시험 통과”라고 주장하지 않는다. 유효 구간에서도 최대 rAF 간격41.7–83.4ms가 있었으므로 끊김0·무손실·완전 무지연 수락은 아니다. 실제 휠 수와 매칭 수는 각 receipt에 별도로 남겼다.

초기 MAILBOX Notion warmup/long 두 파일은 창 focus로 스크롤 레이아웃이 움직인 뒤 오래된 좌표에 입력하여 wheel 이벤트0개였으므로 제외했다. focus를 좌표 측정 앞으로 옮긴 뒤 위 visible/endurance 결과를 수집했다.

### 일반 실행 반영

브라우저 전용 MAILBOX,4K120Hz,2.5배 HiDPI,휠 factor1.5,Code smoothScrolling,정상 Git IPC 재생성 허용을 유지한다. 기존 설정 백업을 보존하며 정상 stop/start로 배포했다. 디버깅용 브라우저 종료와 production 창 복원 결과는 `scroll-production-install.json`, `scroll-production-health.json`에 기록한다.

이번 변경과 관련된 Android bridge15개, native browser3개, cadence2개, Linux socket7개 테스트가 통과했다(총27개). 범용 installer 완성·기기 재부팅 지속성·장시간 발열·모든 앱의 동시 사용·원격 SSH 검증은 이 결과에 포함하지 않는다.

최종 production health는 PASS였다. 설치 runtime 5개 SHA가 현재 소스와 일치하고 3840×2560/120Hz/scale2.5, 브라우저1개·창3개, Code 개인 profile, private futex library와 MAILBOX 환경, 미리보기 HTTP200을 확인했다. 디버깅 옵션은 없고 ADB19226 forward도 제거했다. [이번 변경의 소스·기기 receipt manifest](2026-10-12-scroll-reproducibility.json).

커밋 직전 설치 재확인에서도 같은 세션이 ready이고 주요 runtime 소스5개 해시가 일치했다. [최종 설치 상태](2026-10-12-installed-scroll-health.json). 이 작업 폴더의 최초 Git 기록에는 소스·설정·요약 문서를 포함하며, build 산출물·다운로드 cache·과거 raw device 기록·별도 public 배포 저장소는 포함하지 않는다.


## 2026-10-13 연결 전 후속 수정 — 아직 기기 미적용

사용자의 추가 요구는 휠뿐 아니라 자연스러운 터치패드 스크롤, 앱 전환·복귀, 배터리를 함께 개선하는 것이다. ADB 연결 기기0개를 확인했다. 아래 로컬 수정은10월12일의 설치 검증과 구분하며, 현재 태블릿에 적용됐거나 배터리가 절감됐다는 뜻이 아니다.

- 주사율을 시작할 때 세션에 저장한다. 기존에는 출력 단계별 명령을 만들 때마다 설정 파일을 다시 읽어, 도중 변경 시 Weston/Hyprland/Aquamarine 주사율이 달라질 수 있었다. status도 다음 시작 설정이 아닌 세션의 요청 값을 보여준다. 과거 세션에 필드가 없으면 null이며 실제 패널Hz로 추측하지 않는다.
- `MESA_VK_WSI_PRESENT_MODE`와 `vblank_mode`를 공통 실행 환경에서 제거한다. 브라우저는 필요한 MAILBOX를 자체 환경에 지정한다. 앞선 쉘의 테스트 옵션이 컴포지터로 전파되지 않는다.
- PulseAudio는 `-n`으로 기본 설정을 읽지 않으므로 `module-suspend-on-idle timeout=30`을 명시적으로 추가했다. 미사용 출력만 쉬게 하며 supervisor가 소유한 서비스는 종료하지 않는다. [PulseAudio 모듈 문서](https://wiki.freedesktop.org/www/Software/PulseAudio/Documentation/User/Modules/)와 [Termux AAudio 구현](https://github.com/termux/termux-packages/blob/master/packages/pulseaudio/module-aaudio-sink.c)의 suspend/reopen 경로를 확인했다. 기기에서 모듈 가용성, 무음30초 후SUSPENDED, 재생 시RUNNING 복귀, 첫 음성 누락·재생 오류 여부를 확인해야 한다. 이는 아직 절전량 실측이 아니다.
- [최소 주사율 복원 도구](../../tools/android_refresh_policy.py)는 이전 시험의 min=120/peak=120일 때만 min 강제를 해제한다. peak·Linux 주사율·해상도는 바꾸지 않는다. 쓰기 전 mode0600 복구 receipt를 저장하고 사용자·기기 해시를 묶는다. 수동 변경이 발견되면 덮어쓰지 않으며, 불확실한 ADB 응답 후에도 receipt로 복구할 수 있다. [Android 주사율 정책](https://source.android.com/docs/core/graphics/multiple-refresh-rate)에 근거한 후보이고 OEM의 실제 idle 주사율·절전 이득은 미검증이다.
- [배터리 수집 도구](../../tools/measure_android_battery.py)는 배터리 상태를 읽기만 한다. 충전 중·전원 정보 누락·배터리 시뮬레이션·카운터 미지원/상승·10분 미만 측정은 유효 방전 수치로 인정하지 않는다. 단일 실행은 절감 입증으로 표시하지 않는다. 이 도구는 소비전류 추정이며 시간당Wh나 남은 배터리 시간을 추정하지 않는다.

호스트 검증: cadence/environment4개, runtime7개, audio14개, terminal installer16개, battery4개, refresh policy4개로 총49개 통과. 두 cadence/environment 회귀는 수정 전 실패를 확인했다. terminal installer의 오래된 SOURCE_SHA도 갱신했으며 runtime11개 SHA가 소스와 일치했다. `git diff --check` 통과. 오디오 테스트는 실행 설정·소유권 경계이며 AAudio 실기 재생 시험을 대신하지 않는다.

재연결 시 한 번에 여러 정책을 섞지 않고 다음 순서로 검증한다.

1. 기존 상태의 휠/터치패드 짧은·긴 스크롤, 반대 방향 전환, 두 손가락 가로 이동, 포인터 캡처 해제·복귀를 측정한다. 현재 글로벌factor1.5는 휠 검증값이므로 터치패드에도 좋다고 가정하지 않는다.
2. 같은4K/2.5배/밝기/앱 구성에서 최소120 고정만 해제해 유휴·읽기·스크롤을 비교한다. 표시FPS와 콘텐츠 갱신을 구분한다.
3. 오디오 절전 변경은 별도로 시험하고 영상 일시정지→30초 유휴→재생을 반복한다. 영상·오디오 복귀가 나빠지면 해당 변경을 원복한다.
4. 화면 꺼짐·앱 전환·복귀 및 앱 여러 개 사용 중 세션 생존과 입력 복구를 확인한다. 기존250ms 소유권 감시를 측정 없이 느슨하게 만들거나 앱들을 강제 종료하지 않는다.
5. 실제 전원을 분리한 무선ADB 등에서 밝기/온도/영상코덱을 맞추고15분 이상의 baseline/candidate 방전량을 비교한다. USB 연결 상태를 `dumpsys battery unplug`으로 흉내 낸 결과는 사용하지 않는다. 가열 순서 편향을 피하도록 조건을 되돌린 반복도 수행한다.

도구 실행 형태(사용자에게 수동 작업을 요구하는 단계가 아니라 다음 연결 때 사용할 명령):

```sh
python3 tools/android_refresh_policy.py release-minimum --serial DEVICE --receipt /private/tmp/y900-refresh-backup.json
python3 tools/android_refresh_policy.py restore --serial DEVICE --receipt /private/tmp/y900-refresh-backup.json
python3 tools/measure_android_battery.py --serial DEVICE --seconds 900 --output /private/tmp/y900-battery-run.json
python3 tools/measure_termux_reentry.py --runs 10 --output /private/tmp/y900-reentry.json  # Termux 셸에서 기기 직접 실행
```

전체 사용성·배터리·자연스러운 물리 스크롤 개선의 최종 수락은 연결 후에 남아 있다. 이번 로컬 변경을 기존 설치 완료 기록에 합치지 않는다.
