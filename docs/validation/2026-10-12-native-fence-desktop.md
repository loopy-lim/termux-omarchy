# Y900 native browser fence 수정과 4K 동시 작업 검증

후속 최신 검증은 [실제 휠 스크롤 개선 기록](2026-10-12-scroll-responsiveness.md)이다. 아래 저장·미리보기 시험은 이전 단계의 증거이며 스크롤 반응속도 측정이 아니다.

2026-10-12 최종 엄격 시험은 **3840×2560 HiDPI에서 YouTube1080p60 약3분, Web Code 실제 입력·저장20회, 로컬 미리보기 동시 사용**을 통과했다. 영상10,965프레임 중87프레임이 누락되어 **0.7934%**였다. Notion은 로그인된 상태로 열려 있었으며 이 시험에서 문서를 편집하지 않았다. 무손실·무지연이나 무제한 앱 실행을 뜻하지 않는다.

## 채택 근거

| 확인 항목 | 실제 증거 |
| --- | --- |
| 엄격 동시 작업 | [webcode12-youtube-long.json](../../build/diagnostics/termux-omarchy-performance-20261012/webcode12-youtube-long.json): PASS,10,965frame/87drop,360표본·측정구간182.74초 |
| 실제 Code 편집 | 같은 receipt의 editorResult: native XTest 입력을 통한371–390번 변경20/20저장 성공. 미리보기에서도 해당20개 결과 관측 |
| 영상 가시성 | 같은 receipt의360개 video표본 모두hidden=false,1920×1080 재생 |
| 실제 패널 출력 | [webcode11-pixel-gate.json](../../build/diagnostics/termux-omarchy-performance-20261012/webcode11-pixel-gate.json):3840×2560 물리 캡처에서 RGB3/3,각160,000pixel 일치. 이 독립 pixel gate는 아래 webcode11 workload 판정 오류와 구분 |
| 두 ABI fence 호환 | [fence-interop.json](../../build/diagnostics/termux-omarchy-performance-20261012/fence-interop.json): native→guest/guest→native,signal-before-wait/wait-before-signal 각각20회,총80회 PASS |
| 원래 native library의 비호환 | 같은 interop receipt: allocated fence size96,expected4로 exit2. private futex 후보에서는 양방향 성공 |
| 메모리 표본 | [webcode12-memory-watch.jsonl](../../build/diagnostics/termux-omarchy-performance-20261012/webcode12-memory-watch.jsonl):160표본,MemAvailable693,296–1,346,148KiB,SwapFree 최저2,237,816KiB. 시스템 전체 메모리 값이며 단일 앱 사용량이 아니다. 3분 부하 생존 증거이며 장기 누수 부재나 OEM 종료 불가능의 증거는 아님 |

최종 workload receipt의 SHA256은 `4d1f203c7dc754783045b172e054a020a922c6b1aa92180c215d77d2b7553458`이다. 실제 판정은 [엄격 harness](../../build/diagnostics/termux-omarchy-performance-20261012/webcode12-youtube-long.mjs)의 frames>10,000,drop<1%,editor PASS,정확히20개 saved=true 및 preview 메시지 조건을 함께 사용했다. 20회 편집은 기록 자체에서371–390 연속값임도 확인했다. 물리 키 입력부터 패널까지의 지연 시간을 측정한 것은 아니다.

## 실제 해결한 문제

native Termux Chromium은 Android/bionic의 libxshmfence를 사용하고 guest Xwayland는 Linux/glibc 쪽 library를 사용한다. 공식 Termux recipe는 pthread backend를 선택하지만 guest의 futex 공유 구조는4byte word이다. 원래 native library가 만든 공유 구조는96byte로, 동일 API 이름이라도 두 프로그램이 읽고 쓰는 layout이 달랐다. GPU swapchain의3개 image 뒤 Present가 멈췄고 DOM/decoded counters만 진행했다.

browser에만 private futex libxshmfence를 적용하자 물리 RGB 갱신과 Present 진행이 회복됐다. native Weston↔Termux:X11의 기존 library는 교체하지 않았다. private library SHA256은 `ffd9e69982a4937fe6ce3c23379fb6fd3980660c2b63cfee2b57cc2d34f4e87c`이며 [재현 빌드](../../experiments/xshmfence-futex/README.md)에서 같은 결과를 얻었다. [Termux 공식 recipe](https://github.com/termux/termux-packages/blob/master/packages/libxshmfence/build.sh), [X.Org 원본1.3.3](https://www.x.org/releases/individual/lib/libxshmfence-1.3.3.tar.xz).

실행 경로는 native Chromium155.0.8059.39 → KGSL용 private Xwayland/DRI3 → guest Hyprland → native Weston/AHB → Termux:X11이다. Code UI는 같은 native browser를 사용하고 guest의 공식 VS Code1.141.0 `serve-web` backend를 사용해 별도 Electron UI 비용을 줄였다. 기존 Electron과 설정은 보존한다. native package 버전은 [공식 패키지 단독 upgrade receipt](../../build/diagnostics/termux-omarchy-performance-20261012/native-chromium-upgrade2.json), bridge 배포는 [설치 receipt](../../build/diagnostics/termux-omarchy-performance-20261012/native-browser-install.json)에 남겼다.

영상은 **FFmpegVideoDecoder, kIsPlatformVideoDecoder=false**, 즉 software decoding이다. H.264 선택 hook은AV1/VP9=false,H264=true로 확인했다. GPU 합성과 출력의 개선을 하드웨어 영상 디코딩 구현으로 표현하지 않는다.

## 폐기하거나 제한해야 하는 이전 결과

- **futex 수정 전 zero-drop**: 실제 패널 출력이 정지한 채 counters만 진행했으므로 성능 수락에서 제외한다. GPU renderer 문자열·DOM·video counters만으로 물리 Present를 보장하지 않는다.
- **webcode11의 broad PASS**: [이전 harness](../../build/diagnostics/termux-omarchy-performance-20261012/webcode11-youtube-long.mjs)는 messages>=3만으로 PASS를 허용하고 실제 editor의 성공/20회 저장을 검사하지 않았다. [receipt](../../build/diagnostics/termux-omarchy-performance-20261012/webcode11-youtube-long.json)는 editor341 saved=false인데도 PASS였다. 이는20회 편집 수락으로 사용하지 않는다. webcode12가 이를 대체한다.
- **disable-vulkan-surface 후보**: 물리 출력은 갱신했지만 약59.6%drop으로 기각했다. CPU readback 출력은 최종 성능 경로가 아니다.
- **25초 로컬1518frame/8drop(0.527%)**: 유효한 짧은 보조 표본이며 최종3분 YouTube 결과와 분리한다.

## 성능 시험 이후의 재시작·사용자 설정 확인

[production-lifecycle-install.json](../../build/diagnostics/termux-omarchy-performance-20261012/production-lifecycle-install.json)은 정상 stop의 `terminationConfirmed=true`, 이어진 start의 `status=ready`, `xReady=true`, `hyprlandReady=true`,3840×2560을 기록한다. stop의 `runtimeGone=false`와 start의 `shellReady=false`도 그대로 남아 있으므로 runtime 디렉터리 소멸이나 전체 shell 수락을 이 receipt로 주장하지 않는다. Present 진단 토글은 production 실행에서 제거했다는 통합 보고이며, 최종 실행 환경·로드된 library의 추가 확인은 별도 범위다.

Chromium 정상 종료 후 남은 SingletonLock은 수동 삭제하지 않는다. 현재 [bridge](../../termux/omarchy_android.py)의 `browser_profile_available`은 같은 host의 lock owner PID가 없고 동일 profile을 사용하는 살아 있는 프로세스도 없음을 확인한 경우에만 Chromium 자체 복구를 허용한다. [경계 테스트](../../tests/test_omarchy_native_browser.py)는 stale lock 보존과 live owner 거부를 포함한다. [재실행 receipt](../../build/diagnostics/termux-omarchy-performance-20261012/production-browser-restart-open.json)에는 dispatch3회 성공, 같은 production PID29196의 Code·미리보기 창2개가 기록됐다. 이 결과는 stale-lock 재실행 경계의 확인이며 아직 진행 중인 모든 lifecycle 검증의 완료를 뜻하지 않는다.

[폰트 확인](../../build/diagnostics/termux-omarchy-performance-20261012/native-custom-inspect.json)에서 `fc-match`는 `JetBrainsMonoNerdFont-Regular.ttf`, `JetBrainsMono Nerd Font / Regular`를 선택했다. 전체 테마·확장·키바인딩 보존은 이 font match만으로 확정하지 않는다.

후속 [첫 재시작 편집](../../build/diagnostics/termux-omarchy-performance-20261012/production-editor-restart.json)은401–403번 실제 입력·저장3/3을 통과했다. [두 번째 lifecycle](../../build/diagnostics/termux-omarchy-performance-20261012/production-lifecycle-second.json)도 정상 stop의 terminationConfirmed와3840×2560 ready를 기록했다. 그러나 [첫 Code 실행](../../build/diagnostics/termux-omarchy-performance-20261012/production-final-open.json)은 `Local web editor unavailable`을 반환했다. backend 준비 확인 후 [명시적 재실행](../../build/diagnostics/termux-omarchy-performance-20261012/production-code-final-retry.json)으로 창이 열렸으며, [411–413번 저장](../../build/diagnostics/termux-omarchy-performance-20261012/production-editor-final-retry.json)3/3이 성공했다. 이는 아래 TIME_WAIT 수정 이전의 실패 이력이며 수정 후 재시험과 구분한다.

시작 실패의 후속 원인은 port probe가 Node 서버와 달리 `SO_REUSEADDR`를 설정하지 않아 TIME_WAIT를 사용 중인 listener로 오인한 것이다. helper에 같은 옵션을 적용했다. [native socket 회귀 증거](../../build/diagnostics/termux-omarchy-performance-20261012/code-port-reuse-regression.json)는 일반 bind의 errno98, reuse bind 성공, 실제 live listener 거부를 함께 통과한다. 수정 후 [첫 stop/start](../../build/diagnostics/termux-omarchy-performance-20261012/production-reuse-cycle.json)와 [첫 실행](../../build/diagnostics/termux-omarchy-performance-20261012/production-code-reuse-open.json)이 성공했고, Code가 열린 상태에서 즉시 [다음 stop/start·첫 실행](../../build/diagnostics/termux-omarchy-performance-20261012/production-warm-restart.json)도 성공했다. **수정 후2회 재시작 표본**에서 재시도 없이 열렸다는 증거이며 모든 cold-start 상황의 안정성을 보장하지 않는다. [시험 fixture 복구](../../build/diagnostics/termux-omarchy-performance-20261012/production-fixture-restored.json)는421번 실제 입력·저장을 확인한다.

두 번째 lifecycle receipt는 기존 `mateocerquetella.xcode-12-theme@5.2.0`(17개 파일)과 `pkief.material-icon-theme@5.39.0`(1,277개 파일)의 복사·manifest hash를 기록한다. Marketplace의 `SignatureVerificationInternal / UnknownError` 때문에 검증 기능을 끄지 않고 이미 설치된 원본 디렉터리를 복사한 결과다. 이 증거는 파일 보존이며 Web Code UI에서 테마·아이콘이 활성화됐다는 수락은 아니다. [desktop integration receipt](../../build/diagnostics/termux-omarchy-performance-20261012/production-desktop-integration.json)는 Notion·YouTube·기본 HTTP 경로의 native browser 연결과 같은 PID29196 창을 기록한다.

[최종 live health](../../build/diagnostics/termux-omarchy-performance-20261012/production-final-health-verified.json)는3840×2560, native browser primary1개·창3개, Code profile 활성 표시, preview HTTP200, 빈 launch log를 확인한다. debug port와 Present diagnostic은 모두 꺼져 있고 GPU process maps에 private futex와 Freedreno library가 로드됐다. 마지막 메모리 스냅샷은 MemAvailable852,180KiB/SwapFree2,006,664KiB이며 앞의3분 표본과 별개다. 현재 bridge와 Code helper hash는 기기 측 hash와 일치했다.

최종 기기의 Xwayland SHA256은 `87f549719ab28d39b4ba432513064881dd2b25815f01610de03b4fc381efac6f`로, 로컬 experimental binary의 `261a6c20b7efe7d3411a9d843fa6cbb5253893135e13d75d0a208e1aff3e16fe`와 다르다. manifest에서 두 artifact를 구분한다. 원본 `production-final-health.json` traceback은 수집 script가 socket path 변수를 hash loop에서 덮어쓴 오류였다. 성공 증거는 수정된 `production-final-health-verified.json`만 사용한다. 최종 통합 보고의 targeted host tests는24개(bridge15/browser3/Code6) 통과이며 live health와 다른 검증 수준이다.

[범위가 제한된 재현 manifest](2026-10-12-native-fence-reproducibility.json)는 현재 소스20개, 로컬 graphics artifact, 원본 검증 receipt의 SHA256과 빌드 revision을 기록한다. bridge와 terminal의 현재 source hash는 위 production 배포 receipt와 각각 일치한다. local artifact hash와 실제 기기에 로드된 library의 동일성은 구분하며, 사용자 인증 데이터는 포함하지 않는다. 이 manifest는 범용 installer 또는 clean install 수락이 아니다.

## 남은 범위와 패키징

최종 수치는 해당 기기의 해당3분 workload에 대한 결과이다. Notion 실제 문서 편집, 사용자 요청으로 미룬 원격 코드 연결, 수시간 발열·메모리 압박, 정상 stop/start 이후 모든 설정·로그인·확장 유지 및 실제 손 입력 지연은 별도 확인 범위다. 위 후속 폰트·재실행 증거는 성능 receipt와 별도로 기록했다.

이 문서 작성 시점의 최소 재현 패키징 공백은 다음과 같다.

1. Runtime hash 목록에는 bridge 변경이 들어갔지만, 새 guest web helper/profile exporter/desktop entry와 private futex payload를 설치하는 고정 installer 항목은 아직 확인되지 않았다. 기기 진단 설치와 새 설치의 재현성은 다르다. payload 대상·mode·hash·기존 사용자 파일 충돌 처리·rollback을 한 설치 경로에 넣어야 한다.
2. private Xwayland, guest KGSL/GBM compatibility library, native AHB Mesa, private native futex의 **최종 채택 조합**을 source revision/build command/output hash와 함께 묶어야 한다. 위 scoped manifest가 현재 파일과 receipt를 고정하지만 전체 배포 조합의 clean install은 아직 확인하지 않는다. no-direct-flip 진단 토글을 최종 기본값에 실수로 남기지 않도록 최종 env도 기록해야 한다.
3. native Chromium155의 실제 package/dependency 버전·package hash와 pinned VS Code web server component의 cache/다운로드 무결성을 보존해야 한다. Chromium151은 기존 guest package이므로 native155 pin의 대체물이 아니다. 이번처럼 오래된 apt candidate152 URL은 사라질 수 있다.
4. 사용자 profile migration은 설정·키바인딩·스니펫·확장·Notion 인증의 보존 증거와 분리된 journal이 필요하다. 로그인 데이터 자체를 공유 artifact나 installer에 넣지 않는다.

위 공백은 이번 live 성능 결과를 무효화하지 않지만, clean install 완료나 일반 배포 재현성을 주장할 근거로 삼을 수는 없다.
