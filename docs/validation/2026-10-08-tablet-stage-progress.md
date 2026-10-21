# Y900 실제 GPU·셸·SSH 후속 검증

2026-10-08, Y900 / TB522FU / Android 16 / 앱 UID 10330. 전체 Omarchy 목표는 진행 중이다. 현재 설치 제품은 입력 캡처·일반 빌드 기본 runtime 수정본 `0589092c…`다. 실제 prod01 업데이트는 PASS이며 새 제품을 유지했다. HOME·설정116개와 zsh/tmux 2개·UID·접근성 및 서비스 상태를 보존했고 마이크 권한 거부를 유지했다. [현재 APK와 설치 기록](../../build/deliverables/LoopyDesktop-2026-10-08-native-input-runtime-arm64/README.md), [prod01 원본](../../build/diagnostics/y900-production-default-capture-update-runs-20261008-01/prod01/receipt.json).

새 기본 runtime `e2a0eba5…`는 실제 NDK27/API28 빌드와 UID2000의 격리 커널 회귀3개를 통과했다. 일반 SDK 빌드는 runtime 후보 인자 없이 기본 경로를 선택했고 기존 네이티브 선택3개를 유지했다. 호스트 기본 경로11개·입력 소유권7개·launcher2개·검토 회귀3개도 통과했다. 새 제품의 input10a 입력 기능은 통과했으나 포커스 복원 실패로 전체 FAIL이다. App UID10330 셸·SSH·클립보드 또는 실제 권한 상실 수락은 아직 물려받지 않는다.

아래 `7c14004c…`·`554fff4b…`·`1148c45e…`와 임시 진단 APK 결과는 각각 당시의 이력이다. 새 제품의 GPU 성능 측정은 없으며 기존 약17fps·숫자 조합 포커스 복원 실패·클립보드 전체 FAIL·Timing11 ON 전체 FAIL을 유지한다. [이전7c 제품 기록](../../build/deliverables/LoopyDesktop-2026-10-08-gtk-icon-data-arm64/README.md).

Android 내부 표시의 shell broker 시험01–06 FAIL은 유지한다. 06은 이미지11개를 얻었으나 공개 중심 색상3개가 원본과 달랐고 고정 palette 일치·프레임 내보내기는0이었다. 후속 **inside07은 소유한 공개 Android 앱의 VD·초기 픽셀·클릭1회·F12 1회·프레임3개 독립 호스트 전체 검사·정리를 PASS**했다. 초기 공개 장면의 profile을 한 번 고정해 후속 픽셀도 같은 범위로 판정했으며 생산 색상 보정이나 원인 확정이 아니다. 일곱 실행 모두 설정118·서비스·역할·현재0589 제품·기본 Loopy 포커스를 보존했다. [inside07 원본](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside07/receipt.json), [단계별 기록과 경계](../research/android-app-inside-wayland-20261008.md).

후속08은 App UID 소스 파일을 shell UID에서 hash 조회해 창 실행 전에 실패했고,09는 `GdkWayland 3` GI namespace 부재로 broker·픽셀 단계 전에 실패했다. 두 실행의 정확한 소유 폴더는 별도 정리 기록으로 제거했다. **inside10은 실제 관리된 GTK Wayland 창 식별과 broker 첫 공개 프레임의 Java·독립 호스트 전체 검사 및307,200바이트 GUI 전송까지 통과**했으나 `live-phase-0` timeout으로 전체 FAIL이다. 이 단계는 paint 대기와 GTK 클릭을 함께 포함하며 당시 GUI 이벤트·stderr가 보존되지 않아 내부 실패 위치·paint ACK 부재를 단정하지 않는다. broker task/display·viewer 창/프로세스/폴더·target 정리와 설정118·서비스·역할·현재 제품·기본 Loopy 포커스 보존은 통과했다.09·10의 원래 포커스 창은 사라져 복원하지 못했다. [inside08 정리](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside08-cleanup/receipt.json), [inside09 정리](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside09-cleanup/receipt.json), [inside10 원본](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside10/receipt.json).

**inside11은 공개 Android task173/display9/UID10341의 첫 프레임을 Java·독립 호스트 전체 검사 후 실제 관리된 GTK Wayland 창(PID6371/birth74572553/stableId402653199)의 draw callback까지 전달했다.** 보존된 이벤트에 `public-frame-painted frame_id=1`이 있고 stderr는0바이트다. 클릭/F12 이벤트·relay 명령은0이며 paint 대기·GTK 클릭을 함께 포함하는 phase0 timeout의 세부 원인은 미기록이다. 물리 presentation·완료된 상호작용·일반 앱 호스팅/성능은 수락하지 않는다. broker task/display·GTK 창/프로세스/폴더·target 정리, 원래 `no_initial_window` 복원 및118·서비스·역할·현재0589·기본 Loopy 포커스 보존은 통과했고 cleanup 오류도 없지만 본문과 전체 receipt는 FAIL이다. [inside11 원본](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside11/receipt.json), [보존 draw 이벤트](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside11/events.jsonl).

## 전체 출력 GPU 비교

Linux 출력과 실제 Android Surface는 모두 1920×1269, Linux 배율 150%, 관측 패널 주사율 120Hz였다. 소유한 GTK GLES 장면의 Adreno renderer·알려진 두 픽셀·활성 창·포커스·Wayland idle inhibitor·SurfaceFlinger 표시 시각·종료 및 작업공간 복원을 검사했다. 화면 보호기가 장면을 가린 P01 실패는 보존했다. 물리 입력부터 화면 표시까지의 지연 측정은 아니다.

| 실행 | 정확한 APK SHA 앞부분 | 결과 | 표시율 |
| --- | --- | --- | --- |
| [제품 P02](../../build/diagnostics/y900-stage-product-p-20261008-01/loopy-stage-p02-report.json) | `1148c45ed672` | 전체 시험 통과 | 전체 장면 17.51fps, 같은 45초 준비 후 12초 구간 17.57fps |
| [계측 OFF01](../../build/diagnostics/y900-stage-off-run-20261008-01/loopy-stage-off01-report.json) | `5cf2aacf1136` | 전체 시험 통과 | 전체 장면 17.15fps, 같은 12초 구간 17.14fps |
| [계측 ON01](../../build/diagnostics/y900-stage-on-run-20261008-01/loopy-stage-on01-report.json) | `065d5c78ad08` | 실패: Linux 측 1–3단계 기록 누락 | 장면 표시 17.19fps. 공통 6단계 구간은 미확정 |
| [계측 ON03](../../build/diagnostics/y900-stage-on-run-20261008-03/loopy-stage-on03-report.json) | `ccb742d977aa` | 전체 6단계·공통 구간·소유한 창 정리 통과 | 공통 11.913초, 실제 표시 200회, 16.79fps |
| [이전 제품 P03](../../build/diagnostics/y900-runtime-reaping-run-20261008-01/loopy-stage-loopy-stage-runtime-p03-report.json) | `554fff4bf0a6` | 실제 Adreno 픽셀·활성 창·표시 구간·정리·복원 통과 | 전체 장면 17.20fps, 같은 45초 준비 후 12초 구간 17.57fps |

ON01의 Android 측 기존 SHM snapshot은 평균 약 2.406ms, 전체 화면 업로드는 1.545ms, eglSwap은 0.509ms였다. 각 구성요소의 12초 창에서 측정한 값이며 프레임별 합산이나 전체 병목 확정에 사용하지 않는다. 커서와 출력의 두 텍스처 저장 공간을 매 프레임 재할당했으나 계측한 두 호출의 합은 약 0.013ms였다. 이 값만으로 60fps 개선 원인으로 삼지 않는다.

Linux 계측은 컴포지터 stderr에 기록되고 첫 수집기는 Quickshell 전용 로그를 읽었다. ON01 실패를 보존하고, ON03에는 진단 전용 stderr 수집을 추가해 6단계를 모두 수집했다. ON03 각 단계 평균은 GPU readback 6.261ms, 행 변환 2.734ms, 부모 출력 callback 7.167ms, Android SHM snapshot 2.405ms, 텍스처 업로드 1.523ms, eglSwap 0.508ms였다. 부모 callback에는 뒤 세 단계가 포함되므로 여섯 수치를 합산하지 않는다. 실제 표시 간격 중앙값은 58.333ms였다. 현재 계측 범위로는 이 간격을 설명하지 못하며 GTK 전체 paint, 클라이언트 SHM 업로드와 컴포지터의 resolve 이전 구간을 추가 조사한다. 현재 출력 크기의 지속 60fps·144fps, 실제 물리 입력 지연, 장시간 안정성은 미완료다. [stderr 추가 전 비교 원본](../../build/diagnostics/y900-stage-runner-20261008-03/comparison-before-stderr-capture01.json).

후속 전체 프레임·클라이언트 계측 OFF/ON의 실제 ARM 및 SDK 빌드는 완료했다. 첫 세 실행은 장면 시작 전에 검사기 준비 대기에서 중단됐으며 FPS를 얻지 못했다. timing02는 비동기 Activity 시작 직후 PID 조회, timing03은 Activity 준비 이후 Linux 프로세스 0개와 임시 Surface 1920×1119에서 중단됐다. `-W`와 PID 대기는 timing03에서 통과했다. 세 실행 모두 현재 제품 `7c14004c…`로 복원했고 설정·서비스·마이크 차단을 보존했다. 이 실패를 GPU 성능 측정이나 제품의 native ABI 충돌로 해석하지 않는다. 다음 검사기는 Linux 프로세스·입력 상태·1920×1269 전체 화면이 준비된 뒤 원래 시간창으로 진행한다. [timing02 실패·복원](../../build/diagnostics/y900-timing04-cycle-runs-20261008-02/timing02/cycle.json), [timing03 실패·복원](../../build/diagnostics/y900-timing04-cycle-runs-20261008-03/timing03/cycle.json).

후속 timing04는 준비 대기를 통과했지만 시작 시점의 임시 높이 1119와 수집 시점의 전체 높이 1269를 같은 레이아웃으로 판정해 중단됐다. timing05는 추가 필드 관찰 단계, timing07은 시작 중 여러 `Hyprland` 이름을 즉시 거부하는 단계에서 중단됐다. 세 실행 모두 공개 GPU 장면 시작 전 실패이며 현재 제품 복원은 통과했다. 별도의 현재 제품 관찰에서는 필드가 완전한 성공 결과에도 JDI 알림 한 줄이 붙는 경우를 확인했으나, 당시 timing05가 같은 원인이었다고 확정하지 않는다. timing07 당시 PID·상태·birth 기록이 없어 여러 실제 컴포지터가 동시에 살아 있었다고 단정하지 않는다.

timing09는 설치 전 설정 보존 검사에서 중단됐다. `.config` 파일 수가 113개에서 116개로 늘었으며 추가된 것은 Chromium의 crash metadata·dump·BrowserMetrics 파일 3개였다. 기존 113개 파일의 hash는 모두 그대로였고 삭제·내용 변경은 없었다. 신규 파일의 내용은 읽거나 삭제하지 않았고, 새 검사에서도 116개 설정과 zsh/tmux 2개를 모두 보존 대상으로 삼는다. 이 실행에는 설치·GPU 장면·새 FPS 측정이 없었다. [설치 전 실패](../../build/diagnostics/y900-timing04-cycle-runs-20261008-09/timing09/root-preinstall-failure.json), [hash 기반 추가 파일 대조](../../build/diagnostics/y900-config-inventory-delta-20261008-01/receipt.json).

timing10은 116+2 보존·입력·전체 화면 준비·native origin·두 번의 동일 peer/크기 확인을 통과하고 실제 Adreno 장면을 실행했다. 전체 장면의 실제 SurfaceFlinger 표시 1,399회는 약 17.546fps, 간격 중앙값 58.333ms였다. 다만 GTK가 준비 초기의 1280×846에서 타일 배치 1256×796으로 바뀐 뒤 초기 FBO metadata만 남아 OFF 레이아웃 검사에서 실패했다. 이 크기 변경은 준비 중 발생했고 45–57초 수집 창 안에서는 발생하지 않았다. 전체 receipt는 FAIL이며 ON 계측과 801–815 구간 비교는 실행되지 않았다. 소유한 창·프로세스 정리와 현재 제품·118개 파일·서비스·마이크 차단 복원은 통과했다. [OFF 실패 원본](../../build/diagnostics/y900-frame-run-off04-timing10/loopy-frame-off04-timing10-report.json), [제품 복원](../../build/diagnostics/y900-timing04-cycle-runs-20261008-10/timing10/cycle.json).

timing11은 준비 중 GTK 크기 변경의 최초·최종 metadata와 조회 시간 이력을 보존한 뒤 OFF 검사를 통과했다. OFF 전체 실제 표시는 17.426fps, 공통 측정 창은 17.019fps였다. ON 전체 표시는 17.513fps였지만 **전체 ON receipt는 FAIL**이다. 원시 로그에 801–805와 scheduler 경로 807은 정상 기록됐으며, 필요한 806(commit→같은 surface의 frame callback 전송)만 없었다. 수집기는 SHM buffer attach마다 대기를 시작하지만 같은 surface에 현재 callback이 없으면 전송 계측에 도달하기 전에 반환한다. 실제 해당 surface의 callback 요청 수를 관찰하지 않았으므로 806을 임의로 N/A 또는 성공으로 바꾸지 않는다. [OFF 통과](../../build/diagnostics/y900-frame-run-off04-timing11/loopy-frame-off04-timing11-report.json), [ON 실패 원본](../../build/diagnostics/y900-frame-run-on04-timing11/loopy-frame-on04-timing11-report.json).

실제 ON의 독립적으로 유효한 부분 기록은 GTK paint 전체 평균 54.622ms, 소유한 render 콜백 0.067ms, render 호출 간격 54.785ms였다. 컴포지터 전체 프레임은 9.504ms, resolve 전 구간 0.150ms, 다음 프레임까지의 컴포지터 밖 간격 45.291ms, 클라이언트 SHM 업로드 1.920ms였다. 비용은 테스트 콜백 밖 GTK paint 구간에 집중되지만, 아직 내부 `glReadPixels` 또는 `eglSwapBuffers`에 귀속하지 않는다. 중첩된 평균과 서로 다른 표본 수를 합산해 프레임을 분해하지 않으며, 이전 6단계 성공을 새 ON 전체 성공으로 물려받지 않는다. 최종 실제 FBO는 widget scale 2의 2512×1592였고 출력은 1920×1269·150%를 유지했다. 소유한 장면 회수와 원래 제품·118개 파일·서비스·마이크 차단 복원은 통과했다. [부분 기록 분석과 hash 입력](../../build/diagnostics/y900-timing11-analysis-20261008-01/analysis.json), [전체 실패 및 제품 복원](../../build/diagnostics/y900-timing04-cycle-runs-20261008-11/timing11/cycle.json).

## 실제 SSH와 셸

제품 `1148c45e…`의 실제 `/usr/bin/ssh`는 생산 PRoot/NSS 문맥에서 소유한 일회성 서버에 접속했다. 정상 nonce 응답, 잘못된 서버 키 거부, 서버 종료 후 실패, 같은 키·포트로 재시작 후 재접속을 모두 통과했다. 사용자 키·agent·known_hosts는 사용하지 않았고 서버·forward·전용 HOME을 정리했다. 외부 사용자 서버 인증과 RDP 수락은 별도다. [SSH03 실제 기록](../../build/diagnostics/y900-owned-ssh-20261008-03/run-ssh-production-1148-03/receipt.json).

임시 ON01 `065d5c78…`에서는 공개 기본 설정으로 만든 별도 HOME/PTY에서 기본 셸과 full Mac 셸을 각각 첫 시작 1회·재시작 3회 측정했다. 기본 셸 첫 준비는 307ms, 재시작은 179–215ms, 첫 합성 입력 ACK는 0.23–0.41ms였다. Mac 셸은 첫 준비 479ms, 재시작 371–538ms, ACK 8.23–12.05ms였다. 페이지 캐시를 비운 측정이나 실제 사용자 `.zshrc`·물리 키·화면 지연 측정은 아니다. HOME·설정·작업공간·포커스를 보존했다. [8회 실제 기록](../../build/diagnostics/y900-owned-shell-20261008-01/run-shell-public-on01/receipt.json).

Mac 셸 실행마다 종료됐지만 회수되지 않은 자식 2개가 남았다. 새 runtime 후보는 실제 ARM 커널의 UID 2000 시험에서 자식 회수·정상 정리·취소 정리 3개를 통과했다. 아직 제품 APK/App UID 10330에서 적용됐다는 증거는 아니다. [실제 C runtime 시험](../../build/diagnostics/y900-recovery-input-20261008-01/runtime-reaping-candidate01/actual-device-green01.json). 빌드 선택기의 호스트 검증 17개는 통과했고 GPU 계측 후 제품 적용을 진행한다.

후속 제품 `554fff4b…`에 검증한 runtime을 연결해 실제 앱 UID 10330에서 같은 공개 셸 fixture를 반복 실행했다. 8회 모두 통과했고 미회수 자식은 전부 0개였다. 기본 셸 준비는 183–254ms, Mac 셸은 381–490ms였다. 이전 단계의 미적용 상태는 당시 이력이다. [현재 실제 8회 기록](../../build/diagnostics/y900-owned-shell-20261008-01/run-shell-runtime-product01/receipt.json), [두 APK 비교](../../build/diagnostics/y900-runtime-reaping-run-20261008-01/shell-comparison01.json).

같은 새 제품에서도 실제 Linux SSH 정상 응답·잘못된 서버 키 거부·서버 중단 후 실패·재시작 접속 네 단계가 통과했다. 소유한 서버·worker·reverse·전용 HOME을 정리했다. [현재 SSH 기록](../../build/diagnostics/y900-owned-ssh-20261008-03/run-ssh-runtime-product01/receipt.json). 외부 사용자 서버 인증과 RDP 수락은 별도다.

일반 개발 빌드의 기본 runtime 경로를 연결하는 별도 수정안은 아직 적용 전이다. 수정안의 정확한 C 소스와 공개 fixture를 실제 Orb Linux 커널에서 컴파일·실행한 회귀는 통과했다. 부모가 살아 있는 동안 입양한 종료 자식의 PID가 회수됐고, 부모 종료 코드 17과 무관한 sentinel 생존·정상 종료를 확인했다. 기존 Android 후보와 같은 C 소스지만 이 시험을 새 기본 producer의 ARM ELF·APK 검증으로 확대하지 않는다. [실제 Linux 회귀](../../build/diagnostics/y900-runtime-default-linux-20261008-01/receipt.json).

새 GTK 수정 제품 `7c14004c…`에서도 실제 Linux SSH의 정상 응답·서버 키 거부·서버 중단 후 실패·재시작 접속 네 단계가 통과했다. 소유한 서버·worker·reverse·전용 HOME의 정리까지 확인했다. 사용자 서버 키나 외부 인증을 사용한 시험은 아니다. [새 제품 SSH 기록](../../build/diagnostics/y900-owned-ssh-20261008-03/run-ssh-gtk-product01/receipt.json).

## 이전 제품의 앱 실행

이전 제품 `554fff4b…`에서 별도 HOME·D-Bus와 공개 테스트 문서로 Foot 및 Neovim 창의 실행·포커스·1초 생존·종료·전용 파일 정리를 통과했다. 준비 ACK까지의 상한은 Foot 1.565초, Neovim 1.913초이며 검사기의 조회·IPC 시간을 포함한다. Neovim은 `--clean`과 읽기 전용 문서로 검사했으므로 사용자 플러그인·편집·저장 수락은 아니다. [Foot 기록](../../build/diagnostics/y900-owned-app-smoke-20261008-04/run-runtime-six04/foot/receipt.json), [Neovim 기록](../../build/diagnostics/y900-owned-app-smoke-20261008-04/run-runtime-six04/nvim/receipt.json).

같은 실행의 Nautilus 창은 3.119초 상한으로 준비 ACK·포커스·생존을 통과했으나 검사기 정리 단계가 `ValueError`로 실패해 전체 묶음은 실패로 보존했다. 이후 검사한 해당 coordinator와 알려진 자식 22개의 PID는 모두 사라졌고 원래 작업공간·포커스도 복원했다. 미확정 전용 HOME/controller는 보존했다. [실패 원본](../../build/diagnostics/y900-owned-app-smoke-20261008-04/run-runtime-six04/files/receipt.json), [실제 잔여 프로세스 확인](../../build/diagnostics/y900-runtime-reaping-run-20261008-01/appsmoke04-residuals01.json). 이 실패를 Nautilus 시작 실패나 PDF·오피스 통과로 확대하지 않는다.

후속 검사기06은 요청 파일을 완전히 쓴 뒤 원자적으로 공개하고, 정확한 pidfd의 종료 확인에 짧은 대기 구간을 둔다. 현재 설치본의 Nautilus는 준비 상한 2.725초로 실행·포커스·생존·정리 전체를 통과했고 입양한 자식 22개를 회수했다. Writer·Calc도 각각 7.788초·6.619초 상한으로 공개 문서를 열고 생존·정리·복원을 통과했다. 검사기 지연을 포함하는 상한이며 편집·저장·실제 표시 픽셀 수락은 아니다. [Nautilus06](../../build/diagnostics/y900-owned-app-smoke-20261008-06/run-runtime-rest06/files/receipt.json), [오피스06](../../build/diagnostics/y900-owned-app-smoke-20261008-06/run-runtime-office06/receipt.json).

Evince는 같은06에서 창 준비 전에 종료 코드 134로 끝났다. stderr의 고정 분류는 GTK 아이콘 assertion과 namespace loader였으며 자식 15개·전용 HOME을 정리했다. PDF 실행은 미완료로 남기고, 다른 앱의 통과와 구분한다. [PDF06 실패](../../build/diagnostics/y900-owned-app-smoke-20261008-06/run-runtime-rest06/pdf/receipt.json).

PDF 원인 대조에서는 설치 제품을 유지하고 실행 환경의 데이터 검색 경로만 바꿨다. 기본 경로는 다시 종료 코드 134로 실패했고, 앱에 이미 포함된 신뢰 아이콘 캐시 경로를 추가한 실행은 준비 상한 2.188초로 창 실행·생존·정리·복원을 통과했다. 자식 16개를 회수했고 미회수 자식은 0개였다. 이 대조를 근거로 `OmarchyDesktopLaunch`의 `XDG_DATA_DIRS` 한 항목에 `/loopy-remote-client/usr/share`를 두 번째로 추가했다. Android 앱 목록이 먼저 유지되며 별도 라이브러리·테마·샌드박스 설정은 추가하지 않았다. 실제 Java 환경 구성 검사 2개와 SDK 빌드는 통과했고 새 APK의 기본 실행은 다음 실제 검증 대상이다. [기본 경로 실패](../../build/diagnostics/y900-evince-icon-diagnostic-20261008-01/run-pdf-icons-original01/pdf/receipt.json), [신뢰 경로 대조 통과](../../build/diagnostics/y900-evince-icon-diagnostic-20261008-01/run-pdf-icons-trusted01/pdf/receipt.json).

새 제품 `7c14004c…`를 실제 업데이트 설치한 뒤 별도 XDG 우회가 없는 기본 PDF arm을 실행했다. 신뢰 아이콘 경로는 생산 환경에서 상속됐고 Evince의 공개 PDF 창이 약 2.108초 준비 상한으로 실행·포커스·생존·종료·파일 정리·작업공간 복원을 모두 통과했다. 이전 대조 실행의 통과를 새 제품에 물려받지 않았다. HOME·115개 설정·UID·접근성 서비스·정책은 보존했다. [새 제품 기본 PDF 실행](../../build/diagnostics/y900-evince-icon-diagnostic-20261008-01/run-gtk-product-original01/receipt.json), [실제 업데이트](../../build/diagnostics/y900-gtk-icon-data-update-20261008-01/gtk-icon-data-update.json).

## 7c 제품의 Android·Wi-Fi·DNS 연결

제품 `7c14004c…`의 실제 Linux 실행 문맥에서 Wi-Fi panel·shell·toggle 진입점 3개, Notion 앱·웹 진입점 2개, DNS·HTTPS 1개를 모두 통과했다. Wi-Fi 진입점은 실제 Android Wi-Fi 설정으로 이동했고 Notion은 실제 앱, 웹 진입점은 Chrome으로 이동했다. 매번 같은 컴포지터 PID·생성 시각·소켓을 유지한 채 원래 Linux 작업공간·포커스·전체 화면·입력 우선권으로 복귀했다. 전용 controller와 coordinator도 정리했다. [현재 제품 6개 실제 기록](../../build/diagnostics/y900-gtk-icon-android-interop-20261008-02/run-android-7c14002/receipt.json).

Linux에서 `example.com` DNS와 인증서를 검증한 HTTPS 응답 200, `www.notion.so` DNS와 인증서를 검증한 HTTPS 응답 403을 확인했다. Notion의 403은 DNS 실패가 아니며 로그인·문서 편집 성공으로 해석하지 않는다. Wi-Fi 전파 켜기·끄기나 재접속, Notion 계정 내용은 이 시험의 대상이 아니다. 첫 검사기의 결과 읽기 문법 오류는 실패 원본으로 보존했고 알려진 전용 파일만 따로 정리했다.

현재 `7c14004c…`의 Linux `paplay`로 4초 공개 테스트 음원을 재생한 시험도 통과했다. 기본 sink는 Android 연결이었고 재생 중 Android 출력 위치 57,600프레임, 최종 전달 194,560프레임과 정상 idle 복귀를 확인했다. 전용 음원·controller·프로세스를 정리했고 같은 컴포지터·입력 상태를 보존했다. 숫자 출력 메타데이터와 합성 음원만 사용했고 실제 마이크나 사람이 들은 소리를 검사하지 않았다. 종료 뒤 underrun 누계는 2개였으므로 무손실·장시간 오디오나 낮은 지연 수락으로 확대하지 않는다. [현재 소리 출력 기록](../../build/diagnostics/y900-current-speaker-metadata-20261008-03/run-current01/receipt.json), [종료 뒤 idle 확인](../../build/diagnostics/y900-current-speaker-metadata-20261008-03/run-current01/post-idle01.json).

## 현재0589 입력 기능과 전체 실패

input10a는 합성 USB Alt+Tab 양방향과 Lenovo/일반 Esc 각각 누름·뗌1회, 마우스 누름·뗌1회와 움직임1회를 모두 통과했다. 실제 캡처와 Android TYPE_NULL(0)·단일 커서 메타데이터를 확인했고 소유한 장치·창 정리 오류는 없었다. 작업공간은 복원했으나 포커스 복원은 실패해 **전체 receipt는 FAIL**이다. 검사기가 원래 창의 시작 메타데이터를 보존하지 않아 원인을 확정하지 않는다. 새 APK·추출된 runtime `e2a0eba5…`·설정118·서비스의 전후 동일성은 별도 검사로 확인했다. 실제 물리 장치·권한 상실·장시간 재접속의 수락은 아니다. [input10a 원본](../../build/diagnostics/y900-current-input-validation-runs-20261008-input10/input10a/receipt.json), [전후 보호 검사](../../build/diagnostics/y900-current-input-protected-fence-20261008-01/receipt.json).

## 이전 제품의 입력 검사와 미완료 항목

제품 `554fff4b…`의 합성 USB 키보드에서는 Alt+Tab·역방향 전환과 일반/Lenovo 모드 Esc의 Linux press/release를 확인했다. Android View의 실제 `mMousePointerIcon` 값은 `TYPE_NULL(0)`이고 시스템 커서 숨김 상태는 참이었다. 이 값만으로 Linux 커서의 표시 개수나 물리 키보드 수락을 주장하지 않는다. 클릭 검사06은 Linux 커서가 소유한 전체 화면 창 안 `(49,34)`에 있었지만 버튼 이벤트 확인이 실패했다. 후속 검사07은 장식 없는 창의 실제 내용 영역 안에 움직임이 도착한 것을 확인했으나 최종 버튼 press/release는 모두 0개였다. 이동 이벤트는 5개였으므로 버튼 전달 경로를 추가 추적한다. 검사 실패 원본·소유한 장치 및 창 정리·작업공간 복원 기록은 보존했다. [입력06 기록](../../build/diagnostics/y900-current-input-validation-runs-20261008-01/input06/input.json).

제품 `7c14004c…`의 후속 마우스 경로 관찰은 Android ART의 JDI 인자 읽기에서 `INVALID_SLOT(35)`로 중단됐다. 정확한 지점은 `DesktopSurface.onCapturedPointerEvent` 진입 인자이며, 이 관찰 실패를 제품의 클릭 원인으로 해석하지 않는다. 최종 소유한 GTK 창에는 움직임 11개와 버튼 0개가 기록됐고 합성 장치·창 정리·작업공간·포커스 복원은 통과했다. 일반 키·텍스트·클립보드는 수집하지 않았다. [현재 제품 관찰 실패 원본](../../build/diagnostics/y900-mouse-route-observer-runs-20261008-01/mouse-route02/receipt.json).

현재 제품의 합성 `Gdk.Event` 검사에서 이전 수신기 자체의 버튼 분류 오류를 확인했다. 일반 `event`의 `.button`은 `EventButton` 구조체여서 `== 1`이 거짓이지만, 같은 이벤트의 `get_button()`은 유효한 버튼 1을 반환했다. 따라서 기존 버튼 0회 기록은 제품의 클릭 전달 실패 근거로 사용할 수 없다. 원본을 보존하고 접근자로 수정한 새 검사로 다시 확인한다. 이 검사는 실제 사용자 입력을 읽거나 창을 실행하지 않았다. [태블릿의 합성 이벤트 결과](../../build/diagnostics/y900-gdk-event-classification-20261008-01/receipt.json).

접근자를 수정한 input08의 첫 실행은 호스트 Java17과 Java21용 관찰 클래스의 버전 차이로 마우스 생성 전에 중단됐다. Java21로 실행한 다음 검사에서는 포인터 캡처가 꺼진 세션에서 클릭 한 번의 누름·뗌이 각각 2회로 기록됐다. 소유한 장치·창 정리와 작업공간·포커스 복원은 통과했다. 임시 숫자 카운터 설치본의 캡처된 경로에서는 Java 출력과 native 호출 직전 모두 실제 1회씩을 확인했다. 원본 제품으로 복원하며 HOME 설정 파일 113개와 zsh/tmux 2개, UID, 접근성 서비스, 마이크 차단을 보존했다. 이 관찰만으로 캡처 전환이 중복의 원인이라고 확정하지 않는다. [input08b](../../build/diagnostics/y900-current-input-validation-runs-20261008-input08/input08b/input.json), [숫자 경로 관찰](../../build/diagnostics/y900-mouse-shadow-runs-20261008-01/mouse03/mouse-counters.json), [제품 복원](../../build/diagnostics/y900-mouse-shadow-update-runs-20261008-03/mouse03/cycle.json).

복원한 **당시 `7c14004c…` 제품**의 input09a는 합성 USB 입력으로 Alt+Tab 양방향, Lenovo 방식과 일반 Esc의 각각 누름·뗌 1회, 마우스 클릭의 누름·뗌 각각 1회와 움직임 1회를 모두 통과했다. 실제 포인터 캡처와 Android `TYPE_NULL`을 확인했고, 소유한 장치·창을 제거한 뒤 작업공간·포커스와 검사 소스를 복원했다. 소유한 공개 테스트 창만 표시한 상태에서 커서 주변 192×192 영역 한 장을 저장해 **그 영역에 커서 한 개가 보임**을 확인했다. 전체 스크린샷은 메모리에서만 사용했고 저장하지 않았다. 이는 실제 연결된 키보드·트랙패드의 모든 상황이나 장시간 재접속 수락을 대신하지 않는다. [현재 입력 통과](../../build/diagnostics/y900-current-input-validation-runs-20261008-input09/input09a/receipt.json), [작은 커서 영역](../../build/diagnostics/y900-cursor-roi-runs-20261008-02/input09a/cursor.png), [영역 소유권·실측 크기](../../build/diagnostics/y900-cursor-roi-runs-20261008-02/input09a/receipt.json).

같은 APK의 숫자 조합 검사에서는 Meta+1…0 작업공간 전환 10개, Meta+Shift+1…0 창 보내기 10개와 현재 작업공간 유지, Alt+1…0 tmux 전환 10개가 모두 의도한 결과를 보였다. 소유한 HID 장치·자식·tmux 서버 및 소켓 정리, 설정과 서비스·프로세스 정책 보존, 작업공간 복원도 통과했다. 다만 정리 시 원래 포커스 창이 없어 **전체 검사 receipt는 FAIL**이다. 기능 30개 성공을 포커스 복원 성공이나 전체 입력 수락으로 합치지 않는다. [현재 30개 결과 및 복원 실패](../../build/diagnostics/y900-current-numeric-runs-20261008-01/numeric7c01/numeric-numeric7c01.json), [보호된 상태 보존](../../build/diagnostics/y900-current-numeric-runs-20261008-01/numeric7c01/protected-state.json).

## Chromium과 다음 작업

당시 `7c14004c…`의 clip02a는 Android/Linux 양쪽이 빈 초기 클립보드일 때만 공개 nonce를 사용했다. 양방향 전달, 소유한 provider/controller의 커널 회수, 회수 이후 원래 빈 Android 상태 복원과 네 번의 후속 heartbeat 확인은 통과했다. 그러나 복원 후 guard에서 원인 문자열이 보존되지 않은 `ValueError`가 발생해 **전체 receipt는 FAIL**이다. 마지막 guard의 116+2 파일·입력7·같은 peer·소스 보존은 통과했으며 정리 오류는 없었다. 방향별 기능 성공을 전체 수락으로 승격하지 않고, 오류 원인을 stderr 알림이나 제품의 복사 오류로 추정하지 않는다. 개인 클립보드 내용은 읽거나 내보내지 않았고 nonempty/rich 초기 상태의 자동 시험은 허용하지 않았다. [실제 결과](../../build/diagnostics/y900-current-clipboard-validation-runs-20261008-02/clip02a/receipt.json).

현재 커널 config에서 USER_NS/PID_NS는 비활성 상태다. 정적 Android namespace probe는 세 실행 경로 모두 main 이전에 기록을 내지 못했고 PRoot는 signal 11을 보고했다. 이 fixture 실패를 namespace syscall 성공/실패로 해석하지 않는다. 소유한 프로세스와 파일은 정리했다. [정적 실패 원본](../../build/diagnostics/y900-namespace-app-20261008-01/receipt.json), [실제 문맥과 정리](../../build/diagnostics/y900-namespace-app-20261008-01/cleanup01.json).

새 동적 probe의 두 번째 실행은 앱 UID 10330에서 `/linkerconfig` 디렉터리 접근을 검사하다 첫 arm 이전에 종료됐다. syscall control은 실행되지 않았다. 원본 기록을 저장하고 소유한 wrapper가 커널에서 회수된 것을 확인한 뒤 전용 파일만 정리했다. 이 접근 제한을 명시적으로 처리하는 새 wrapper를 준비하며 Chromium 샌드박스를 전역으로 끄지 않는다. [동적 실행 실패](../../build/diagnostics/y900-namespace-app-20261008-02/receipt.json), [원본 보존과 정리](../../build/diagnostics/y900-namespace-app-20261008-02/cleanup01.json).

후속 wrapper03은 `/apex` 디렉터리 열거 권한까지 요구해 첫 arm 이전에 실패했다. 열거 권한과 알려진 경로의 접근 권한을 구분한 wrapper04는 실제 12개 대조 실행을 모두 통과했다. 직접 앱 실행·기본 PRoot·가속을 끈 PRoot에서 일반 clone은 성공하고 unshare(0)는 0이었으며, CLONE_NEWUSER와 unshare(CLONE_NEWUSER)는 모두 실제 `EINVAL(22)`이었다. 모든 소유한 자식을 회수하고 앱 생존·원본 로그·파일 정리를 확인했다. 이는 현재 커널의 USER_NS 비활성과 일치하며 일반 프로세스 생성 실패로 확대하지 않는다. [실제 대조 기록](../../build/diagnostics/y900-namespace-app-20261008-04/receipt.json). 샌드박스를 끄지 않은 Linux Chromium과 전체 OS 기능 지원은 여전히 미완료다.

이전 `554fff4b…` 제품 P03을 따로 실행해 runtime 수정 후에도 1920×1269 / 150%의 실제 표시 간격 중앙값 58.333ms와 12초 구간 17.57fps를 확인했다. 당시 제품의 성능 결과를 이전 APK에서 물려받지 않았다. 현재 `0589092c…`의 측정은 아니며 이 장면에서 최소 60fps는 달성하지 못했다.

다음은 GPU의 미계측 구간 조사, 새 기본 runtime의 App UID 실행 검증, 원본 일상 앱 실행·편집·저장, 서비스 및 하드웨어 연결이다. 원본 158개 패키지·51개 장·119개 QML의 전체 완료를 주장하지 않는다. 임시 진단 설치본 `ccb742d977aa…`를 실제 검사 뒤 제품 `554fff4b…`로 교체한 것은 당시 이력이다.


## 2026-10-08 내부 Android 창 후속15

[실제 inside15](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside15/receipt.json)에서 공개 Android 앱의 원래 프레임을 관리된 GTK Wayland 창에 표시하고 고정 클릭/F12를 왕복한 본문은 통과했다. 전체는 원래 포커스 창 소실로 FAIL이다. Notion/Chrome 제품 지원·임의 입력·물리 presentation·성능 수락은 아니다. 설정118/서비스/역할/제품0589 보존과 소유 task/display/GTK/파일 정리는 통과했다.

호스트 session/protocol의 [실제 Java93개 검증](../../build/diagnostics/android-inside-host-java-20261008-01/receipt.json)은 통과했지만 현재 APK의 AndroidApps.launch에는 아직 연결하지 않았다. resize/focus/close/reconnect·지원 앱·권한 backend/adapter와 원래 창 소실 원인 확인이 남아 있다. 상세 기록은 [내부 표시 조사](../research/android-app-inside-wayland-20261008.md)에 있다.

## 2026-10-08 내부 Android 창 후속16

[inside16 전체 검증](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside16/receipt.json)은 공개 Android 앱의 원래 프레임3개를 관리된 GTK Wayland 창에 표시하고 고정 클릭/F12를 왕복한 뒤 소유한 시험 터미널로 포커스를 복원해 PASS였다. 시험 터미널은53.5초 동안 생존했다. 설정118·서비스·역할·제품0589 보존과 소유 자원 정리도 통과했다. 제품의 Notion/Chrome 내부 실행·임의 입력·지속 프레임·60/144fps 수락은 남아 있다.

[외곽 anchor 기록](../../build/diagnostics/y900-android-inside-runs-20261008-01/inside16-anchor/receipt.json)은 원래 창을 `org.omarchy.screensaver`로 식별했다. 설치 스크립트와 고정 원본 SHA가 일치하며 원본은 포커스 상실 시 종료된다. 기존 guard가 일반 창처럼 복원을 요구한 외곽 FAIL은 수정하지 않았다. 이전 class 미기록 실행의 실패 원인도 소급 확정하지 않는다.

## 현재0589의 GDK 경계 측정 시도

[read01](../../build/diagnostics/y900-gdk-readpixels-runner-20261008-02/run-on-read01/receipt.json)은 `special workspace metadata missing`으로 **사전 조건에서 FAIL**이었다. 장면을 만들거나 계측 구간에 진입하지 않았고 새 FPS·ReadPixels 결과는 없다. 설정118·서비스·역할·마이크 거부·앱 세대·봉인 소스는 보존됐으며 설치·재시작은 없었다. 호스트14개 통과와 실제 측정 성공을 구분한다.

[정확한 출력 schema 후속 조회](../../build/diagnostics/root-phase-verification-20261008-02/current-monitor-schema.json)는 `specialWorkspace`가 존재하고 id가-98이며 `activeSpecialWorkspace`는 없음을 기록했다. 앞선 `.get()` 기반 [제한된 projection](../../build/diagnostics/root-phase-verification-20261008-02/current-public-window.json)의 null은 실제 null 필드 존재를 증명하지 않았다. 원본에 맞춘 schema 처리와 알려진 화면 보호기의 수명 전환을 분리한 향후 검사가 필요하다. 이 실패를 GPU 기능 실패로 해석하거나 receipt를 변경하지 않는다.
