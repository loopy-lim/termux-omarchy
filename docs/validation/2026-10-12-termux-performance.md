# Y900 Omarchy 성능·장시간 안정성 개선 — 2026-10-12

**2026-10-12 최신 검증:** native/guest libxshmfence 공유 ABI를 맞춘 뒤, 4K HiDPI에서 YouTube1080p60 약3분 + Web Code 실제20회 저장 + 미리보기 동시 시험이 **10,965frame/87drop(0.7934%)**로 통과했다. Notion은 로그인된 idle 상태였고 영상 디코딩은 software다. [최신 검증·이전 잘못된 PASS의 정정·남은 패키징 범위](2026-10-12-native-fence-desktop.md)를 우선한다. 아래 기존 guest Chromium/Electron 수치와 당시 미달 판정은 이전 단계의 이력이다. 무지연·무손실 주장은 하지 않는다.

후속 production stop/start와 browser stale-lock 복구·폰트 확인은 최신 검증 문서에 별도 기록했다. [현재 소스·receipt의 scoped manifest](2026-10-12-native-fence-reproducibility.json)는 재현 증거 목록이며 범용 installer 완료를 뜻하지 않는다.

실제 대상은 `Y900` / Lenovo TB522FU / Android 16 / Adreno 830이다. 기존 Arch ARM64·Hyprland·Omarchy와 개인 키보드·tmux·Neovim·VS Code 설정을 유지한다. 이번 작업은 기존 설치본의 업데이트이며 Android 위에서 root/systemd 기능까지 동일하게 제공한다는 주장이 아니다.

## 발견과 변경

1. **Termux:X11 연결 감시 참조 누수.** 10월 11일 native crash의 직접 원인은 JNI global reference 51,200개 한도 초과였다. 50,713개가 `MainActivity$$ExternalSyntheticLambda42`였고 backtrace는 `onReceiveConnection → BinderProxy.linkToDeath`를 가리켰다. 연결 알림마다 새 DeathRecipient를 등록하던 호출을 Activity당 한 개로 제한하고, 연결 교체·Activity 종료 때 해제한다. 이전 연결의 늦은 종료 알림은 새 연결을 끊지 않는다.
2. **종료된 앱의 좀비 누적.** 기존 subreaper는 정상 사용 중 입양한 자식의 종료 상태를 회수하지 않았다. `identity()`가 좀비를 숨기므로 살아 있는 프로세스 수만 보는 검사는 이를 발견하지 못했다. 자신의 직접 자식이면서 종료된 입양 프로세스만 PID별 `waitpid(WNOHANG)`로 회수한다. 등록된 Popen 자식의 종료 코드는 원래 감독자가 읽도록 유지한다.
3. **유튜브 AV1 CPU 비용.** 실제 Chromium의 GPU 합성은 ANGLE/Turnip/Adreno로 활성화되어 있지만 영상 디코딩은 software다. 유튜브에만 AV1/VP9 선택을 막고 H.264를 선택하게 하는 작은 로컬 확장을 추가했다. 기존 Omarchy 확장 목록은 유지한다. H.264는 유튜브에서 보통 최대 1080p이며, 하드웨어 디코딩 구현은 아니다. Notion·다른 사이트의 코덱 동작을 바꾸지 않는다.

Android 프로세스 한도는 기존 4096, Termux 배터리 최적화 예외 및 `RUN_ANY_IN_BACKGROUND=allow`를 확인했다. 더 큰 한도나 무제한 프로세스 설정으로 변경하지 않았다. RAM 약 7.2GiB와 zram 약 5.8GiB의 물리 한계, OEM 정리·메모리 부족 종료는 남는다.

## 재현·실기 결과

- 콜백 60,000회 등록: 기존 방식 60,000개 누적 → 수정본 최대 1개. 연결 교체·죽은 Binder·늦은 콜백·Activity 10,000회 생성/종료 검사 통과.
- 실제 APK DEX: MainActivity의 두 연결 지점만 변경. 나머지 기존 클래스와 네이티브 라이브러리·manifest 보존, payload 493개 중 492개 동일. 기존 KeyBridge·트랙패드 수정을 유지한다.
- 실제 Termux 앱 권한의 입양 자식 검사: 이전 프로세스 모듈에서 좀비 잔존으로 실패, 후보에서 회수 성공. 등록된 자식의 exit 42를 두 경우 모두 보존했다. 초기 검사에서 `identity()`만 확인한 부정확한 PASS는 `reap2-old.json` 실패 재현으로 대체했다.
- 호스트 `test_termux_*.py` 396개 통과. 별도 updater 4개 및 유튜브 MIME 정책 검사 통과.
- 기존 프로필로 Chromium·VS Code·Notion 실제 창을 열었다. Notion은 로그인 페이지가 아니고 editable 요소가 있는 상태까지 확인했다. 문서 내용·계정·인증정보는 기록하지 않았고 문서 수정은 하지 않았다.
- 제어된 H.264 1080p60 영상+VS Code: 601프레임 중 누락 0. Android SurfaceFlinger 30초 평균 59.60FPS, 최대 간격 50ms. 이는 실제 surface present 시각이며 물리 키 입력부터 화면까지의 지연 측정은 아니다.
- 실제 YouTube 1080p60+Notion+VS Code, AV1 안정 구간: 30초 1,802프레임 중 82개 누락(4.55%). H.264 시험: 1,801개 중 10개(0.56%). 서로 다른 재생 구간이므로 엄밀한 동일 장면 A/B 수치는 아니다.
- 업데이트 후 새 세션에서도 확장 적용·FFmpegVideoDecoder 선택 확인. 앱 초기화와 자식 프로세스 부하가 겹친 첫 20초는 1,201개 중 49개 누락으로 실패했다. 안정화 후 30초는 1,800개 중 2개(0.11%)였고 Notion rAF p95 16.8ms, 최대 33.3ms였다. 앱 시작 중까지 무조건 무지연이라고 주장하지 않는다.

- 설치본의 실제 YouTube 1080p60·Notion·VS Code **180초 연속 확인**: 10,805프레임 중 37개 누락(0.34%). 30초 구간 6개 모두 누락률 1% 미만, 영상 재생·Notion 문서 화면 유지. 같은 설치본의 별도 SurfaceFlinger 30초 측정은 평균 59.80FPS, p95 16.67ms, 최대 66.67ms였다.
- 설치 후 개인 profile의 zshrc·tmux.conf·bindings.lua·Git 설정 5개 원본 해시와 개인 binding `1741cc7a…` 보존을 재검증했다. 현재 native UID 10323과 설치 APK 해시를 확인했다.

## 적용된 자료

- APK: `build/deliverables/LoopyOmarchy-performance-20261012/LoopyOmarchy-TermuxX11-connection-lifetime.apk`
- APK SHA-256: `37f6474db094c5875ba4ca4db44a8a890f91c829e2b3ad1c0dc8fee71029c525`
- 새 세션: `733ac973-fc50-43cc-91dd-375079b070bf`, 1920×1280, 배율 1.25, 요청 60Hz.
- 업데이트: `termux/omarchy_performance_update.py`. 정확한 이전 해시와 정상 종료 상태를 요구하며 원본 실행 파일·설정·설치 기록을 보존한다. 중단된 transaction은 백업을 남기고 자동 덮어쓰기를 거부한다.
- 태블릿 백업: `~/.local/share/loopy-omarchy/performance-predecessor-20261012`.
- 크래시 뒤 남은 이전 세션은 삭제하거나 정상 종료로 위장하지 않고 `recovery-d120adc4-55fc-41dd-8b91-caab53da9838`에 보존했다.
- 전체 실행 근거: `build/diagnostics/termux-omarchy-performance-20261012/`.

## 남은 수락 조건

개발 서버 `loopy-development`의 TCP/22는 도달하지만 BatchMode SSH는 인증 실패다. 기존 호스트 키 검증을 유지했다. Mac에서도 태블릿에 이미 저장된 host key를 별도 known_hosts로 재사용해 StrictHostKeyChecking을 유지한 읽기 전용 접속을 시도했지만 같은 인증 실패였다. 인증정보나 서버 authorized_keys를 변경하지 않았다. 사용자 로그인 후 실제 원격 파일 편집·저장·미리보기와 영상 동시 재생을 확인해야 한다. 실제 물리 키보드/트랙패드 체감, Notion 문서 입력·저장, 장시간 절전/복귀도 별도다.

영상 하드웨어 가속 대안으로 [Termux:VA](https://github.com/lfdevs/termux-va)와 별도 Mesa VA bridge를 조사했다. 조사한 daemon commit은 `c7ae229bb01970212eea741d153f6805411f051d`, Mesa bridge branch head는 `8c095276f525605c67c5212aabd8e42ef588790a`다. 현재 동작 중인 Mesa는 교체하지 않았다. 아래 독립 native 시험까지 진행했으며 Chromium 적용과는 구분한다.


## 추가: Android 하드웨어 디코더 독립 시험

Termux 앱의 실제 UID 10323 / `untrusted_app_27`에서 위 고정 daemon 소스를 NDK 27.1.12297006으로 빌드해 시험했다. 선택된 MediaCodec component를 로그에 남기는 관측 코드만 추가했다. 1920×1080 60FPS 12초 H.264 시험 영상의 720프레임을 `c2.qti.avc.decoder`가 모두 처리했다. Inline 방식 4.94초, 공유 메모리 방식 3.42초다. 이는 출력 프레임을 수신한 디코딩 처리량이며 브라우저 재생 FPS·전력 절감·정상 색상 검증은 아니다.

실험 daemon은 자체 Popen 소유로만 종료했고 exit 0을 확인했다. 상시 서비스·자동 시작·기존 GPU 설정을 변경하지 않았다. 근거는 `build/diagnostics/termux-omarchy-performance-20261012/va-native-probe.json`, 빌드 입력은 `build/termux-va-research-20261012/native-build.json`이다. Mesa bridge는 전용 ARM VM의 별도 경로에서 후보 빌드를 진행하며 기존 시스템 라이브러리를 대체하지 않는다.


### VA-API 연결과 브라우저 빌드 제약

별도 Mesa 후보를 전용 ARM VM에서 빌드하고 태블릿 `/opt/loopy-va-candidate`에만 추출했다. 기존 `/opt/omarchy-android/mesa`와 시스템 라이브러리는 유지한다. 실제 PRoot FFmpeg 시험에서 720프레임을 Qualcomm 하드웨어 디코더로 디코딩했으며, NV12 `framemd5` 720개가 software 결과와 순서까지 모두 일치했다. 전체 실행 시간은 CPU 3.77초, VA-API 4.20초였다. GPU→CPU 다운로드와 해시 계산이 포함된 정확성 검사이므로 이 수치를 영상 재생 성능 개선으로 해석하지 않는다. `va-guest-probe.json`에 근거를 기록했다.

현재 Chromium 151의 별도 프로필 시험은 GPU 항목의 `video_decode=enabled` 표시에도 실제 `FFmpegVideoDecoder`와 빈 지원 코덱 목록이었다. [Arch ARM 공식 빌드 설정](https://github.com/archlinuxarm/PKGBUILDs/blob/master/extra/chromium/PKGBUILD)은 VA-API를 끄고 V4L2를 사용한다. 설치 ELF에서도 `vaInitialize`·`VaapiWrapper`·`VaapiIgnoreDriverChecks` 문자열이 없었다. 플래그 표시만으로 하드웨어 디코딩 성공을 판단하지 않는다. 이 초기 브라우저 시험은 자동 종료되는 예전 fixture와 측정 시간이 겹쳤으므로 누락률 성능 비교에는 사용하지 않는다.

Google 공식 ARM64 Chrome 패키지를 저장소 메타데이터의 크기·SHA-256과 대조해 별도 `/opt/loopy-chrome-va-candidate`에 추출했다. 패키지 설치 스크립트·기본 브라우저 변경·프로필 이전은 실행하지 않았다. 시험용 사용자 데이터만 사용한다. 정확한 버전과 해시는 `build/termux-va-research-20261012/chrome-package.json`에 기록한다.


### 실제 Chrome 하드웨어 재생: 기본 적용 보류

Chrome 155.0.8059.39 후보에서 실제 `VaapiVideoDecoder`, `kIsPlatformVideoDecoder=true`, daemon의 `c2.qti.avc.decoder`를 모두 확인했다. 긴 rootfs 경로에 만든 소켓은 PRoot 내부에서 ENOENT였고, 기존 짧은 런타임 경로 아래의 별도 소켓으로 연결을 해결했다. 기존 앱·사용자 프로필은 그대로 열린 상태였다.

| 동일 1080p60 시험 영상, 약 30초 | 프레임 | 누락 | 비율 |
|---|---:|---:|---:|
| 공식 Chrome 후보, 연결 실패 후 CPU fallback | 1,799 | 11 | 0.61% |
| 실제 VA-API 기본 후보 | 1,800 | 40 | 2.22% |
| 세 곳의 프레임별 로그를 debug opt-in으로 제한 | 1,811 | 64 | 3.53% |
| 위 후보 + MediaCodec operating-rate 120 / priority 0 | 1,812 | 37 | 2.04% |

각 조건은 한 번씩의 순차 실행이며 열 상태·시점 차이를 통제한 반복 A/B가 아니다. 어느 hardware 조건도 누락률 1% 미만의 기존 시험 기준을 만족하지 않았으므로 기본값으로 승격하지 않았다. 로그 제한 후보의 1초 구간 측정에서도 누락이 첫 시작에만 몰리지 않았다. `requestVideoFrameCallback` 180회에서 processingDuration 중앙값 56.45ms / p95 115.9ms였으나 이는 Chromium의 디코딩 파이프라인 계측이며 입력 지연이나 MediaCodec 단독 시간은 아니다. 이 값만으로 병목의 원인을 단정하지 않는다. 별도 SurfaceFlinger 측정은 58.21FPS, p95 간격 16.67ms, 최대 50ms였다.

해당 시점의 Android thermal status는 0이었다. 이 한 번의 상태 읽기는 장시간 발열·스로틀링 부재의 증거가 아니다. 하드웨어 디코딩을 쓸 수 있다는 구현 증거와, 사용자가 요청한 매끄러운 동시 작업을 충족한다는 수락 증거를 구분한다.

기본 설치본은 앞서 검증한 H.264 선택 확장과 안정성 수정본을 유지한다. 가속 후보는 자동 시작·기본 브라우저·기존 Chromium 설정에 등록하지 않았다. 후보 브라우저와 daemon 6개는 모두 정상 종료(exit 0)했고 ADB 시험용 포트 전달도 해제했다. 최종 창은 원래 Code PID 17985와 Chromium PID 21356의 두 창뿐이며 같은 데스크톱 세션이 ready다. 개인 프로필 원본 5개와 binding 해시 보존도 재확인했다. 후보 파일과 실패/성공 receipt는 재현을 위해 보존한다. `va-final-cleanup.json`, `verify-after-va.json`이 최종 실제 정리·설정 보존 상태를 기록한다.


## 이전 목표 게이트 — 원격 인증 미확인

후속 현재 상태 확인(`post-trials-idle.json`)에서 같은 세션·원래 Code와 Chromium 창·실제 Quickshell PID 17428을 확인했다. Termux UID의 좀비 프로세스는 0개, 프로세스는 56개였다. RSS 합산 약 1.36GiB는 공유 페이지 중복이 있어 실제 물리 메모리 사용량/PSS와 같지 않다. 이 점검은 여러 시험 브라우저 종료 후 누적 상태 확인이며 장시간 영상/편집 수락 검사를 대신하지 않는다.

`remote-final-gate.json`에서 현재 개발 서버로 연결된 SSH 프로세스는 없고, 기존 호스트 키 검증을 유지한 접속은 exit 255 / 사용자 인증 실패였다. 호스트 키 오류는 아니며 원격 서버 설정이나 인증정보를 변경하지 않았다. 세 차례 목표 턴에 걸쳐 같은 인증 조건이 남았다.

이 시점에는 원격 인증이 미확인이었다. 이후 사용자가 직접 조작할 수 없으므로 태블릿 안의 로컬 프로젝트로 편집·저장·미리보기 검사를 진행하도록 명시적으로 요청했다. 아래 로컬 검사를 먼저 진행하며, 원격 인증을 로컬 검사 통과로 대신 판정하지 않는다. Notion 실제 문서 입력, 물리 입력과 절전/복귀도 별도 검증 범위다. 앞서 앱 초기화가 겹친 구간의 끊김 실패도 열린 항목으로 유지한다. 코드·드라이버 연결 성공이나 짧은 영상 재생 수치만으로 이 조건들을 통과 처리하지 않는다.


## 사용자 요청에 따른 로컬 개발 검증

원격 로그인을 요구하지 않고 Y900의 실제 Arch ARM64 컨테이너 안에 공식 Bun 1.4.3을 설치했다. [공식 설치 문서](https://bun.sh/docs/installation)와 [공식 릴리스](https://github.com/oven-sh/bun/releases/tag/bun-v1.4.3)의 Linux ARM64 바이너리를 사용했다. 다운로드 ZIP SHA-256은 `efa9813da5ed72423bf847f916e8d2c47c0d776add972354026a75e10da9aa21`이며 GitHub 릴리스 asset digest와 일치한다. 설치 경로는 `~/.local/bin/bun`, 실제 실행 버전은 `local-setup.json`에 기록했다. 기존 셸 설정을 덮어쓰지 않았다.

프로젝트는 태블릿 `~/Projects/tablet-dev-lab`, 재현 소스는 [examples/tablet-dev-lab](../../examples/tablet-dev-lab/README.md)이다. Bun HTTP 서버, TypeScript 변환, 파일 감시와 WebSocket 변경 알림, 브라우저 저장소를 사용하는 작업 메모, 로컬 1080p60 시험 영상으로 구성했다. 별도 npm 패키지는 없다. 서버는 `127.0.0.1:4173`에만 바인딩했다. 처음 compositor에서 시작할 때 Bun이 기존 GUI PATH에 없어서 실패했으며 절대 실행 경로로 수정한 뒤 실제 HTTP/브라우저 실행을 확인했다.

첫 Wayland `wtype` 검사는 수정·저장에 실패했다. 이어진 XTest 검사에서도 앱 내부의 파일 탐색기 포커스로 인해 잘못된 편집이 발생했다. 모두 새 시험 파일 안의 실패이며 개인 문서는 수정하지 않았다. 네이티브 X11의 Weston 창을 확인하고 Hyprland의 Code 창과 Code 본문(`Ctrl+1`) 포커스를 명시한 뒤, `Ctrl+A` → 실제 문자열 키 입력 → `Ctrl+S` 경로로 5회 저장을 성공했다. 파일을 밖에서 덮어쓴 뒤 편집기 성공으로 세지 않았다. 실패 receipt도 보존한다.

| 검사 | 실제 결과 |
|---|---|
| VS Code 실제 편집·저장 | 5/5 성공, 저장 내용 일치 |
| 저장한 TypeScript → 브라우저 문구 | 5개 변경 모두 관측 |
| 로컬 1080p60 + 편집 + 기존 Notion 창, 약 90초 | 5,435프레임 중 7개 누락, 0.129% |
| 저장 키 시작 → 브라우저 DOM 첫 관측 | 254–609ms (500ms 폴링 상한 포함) |
| 메모 추가·새로고침 후 유지·완료 | 모두 성공, 시험 메모 제거 |
| 동시 작업 중 프로세스 검사 12초 | 76개 프로세스, 좀비 0개, 같은 데스크톱 세션 |

수치는 `local-editor-x11c.json`, `local-soak-x11.json`, `local-edit-latency.json`, `local-ui-test.json`, `local-development-processes.json`에 있다. 저장 반영 시간은 합성 키 시작부터 DOM 관측까지이며 물리 키보드 입력부터 화면 표시까지의 지연이 아니다. Notion은 기존 로그인 문서를 열린 상태로 유지한 조건이며 기존 문서 내용은 변경하지 않았다. 실제 Notion 입력·원격 네트워크·장시간 발열의 수락으로 확장하지 않는다.


### 실제 YouTube와 로컬 개발 동시 실행

새 브라우저 창이 열린 뒤 Code CLI 호출만으로는 포커스가 돌아오지 않는 경우가 있었다. 첫 YouTube 시험은 영상 누락률 0.932%였으나 편집 0회여서 전체 실패로 남겼다. 이후 compositor에서 Code 창을 명시적으로 포커스하고 본문에 입력했다.

실제 YouTube 1080p60 + VS Code 저장 5회 + 로컬 미리보기 + 기존 Notion 창 조건에서 약 61초간 3,650프레임 중 49개가 누락됐다(1.342%). 저장 5회와 5개 문구 반영은 모두 성공했지만 영상 누락률 1% 미만 기준에는 실패했다. `local-editor-youtube2.json`과 `local-youtube-soak2.json`이 근거다. 이전 로컬 영상 통과 결과로 이 실패를 가리지 않는다. 시험용 별도 Chromium 프로필을 사용했으므로 기존 로그인 브라우저도 함께 실행된 조건이다.


720p60에서도 실제 해상도 1280×720을 확인하고 같은 편집 5회를 실행했다. 3,642프레임 중 51개 누락(1.400%)으로 개선되지 않았다. `local-editor-youtube720.json`, `local-youtube720-soak.json`에 기록했다. 단일 순차 비교이므로 두 해상도의 일반적 성능 차이를 확정하지 않는다. 기본 YouTube 화질 제한을 추가하지 않았다. 이번 실제 Code 저장은 총 15/15회, 브라우저 문구 반영도 15/15회다. 개발 기능 검증과 YouTube 영상 수락은 별개다.

최종 상태는 `Local Dev` 작업공간에 Code와 로컬 미리보기를 나란히 열어 두었다. 기존 Notion·YouTube 브라우저 두 창은 원래 작업공간 1에 보존했다. 시험용 브라우저를 정상 종료한 뒤 디버깅 포트 없이 다시 열었고, ADB 19223 포트 전달도 해제했다. `local-final-state.json`에서 Bun 1.4.3 서버의 응답, 프로젝트 페이지, 저장된 15번째 편집, 닫힌 9223 디버깅 포트를 확인했다. 개발 서버는 사용을 이어갈 수 있도록 실행 중이다. 원격 인증을 요구하지 않고 수행한 로컬 개발 확인은 끝났지만, YouTube 동시 편집의 영상 누락과 기존 장시간/실제 Notion 입력 검증은 여전히 남아 있다.

## 후속 그래픽 가속 병목 조사

[그래픽 조사 및 실기기 결과](../research/2026-10-12-y900-graphics-acceleration.md)에 동일 Chrome 비교, VA copy 구간 계측, shared NV12 DMA-BUF 동기화 패치, 정확성 검사와 실패 결과를 기록했다. `experiments/termux-va-batch-sync`에 고정 소스용 패치·해시·실제 함수 ASan/UBSan harness를 보존했다. 패치 적용 dry-run과 ARM64 빌드가 통과했다.

기존2,570프레임 집계에서 VA direct copy6.506ms/frame 중 END sync5.255ms였다. 같은 allocation의 두 plane을 한 START/END로 처리하는 후보는 주 decoder3,754프레임 집계에서3.769ms/frame, END2.699ms를 기록했다. CPU memcpy 단독 비용은 원본0.301ms/frame이었다. 단일 순차 집계의 관측값이며 전체 체감 개선율은 아니다. 실제30초 재생은1,801프레임 중62누락(3.44%)으로 실패하여 후보를 기본 적용하지 않았다.

후보의 FFmpeg decoded NV12는 CPU720/720프레임과 일치했다. 대표3초 seek의 Chrome 합성 화면640×360도 기본 계측본과 픽셀이 동일했다. Linux sanitizer harness는 padding, 동일/별도 객체, 범위·겹침, ioctl retry, START/END 영구 실패와 opt-out을 통과했다. macOS에서 같은 sanitizer 실행 파일이 응답하지 않아 해당 테스트 프로세스만 종료했고 Linux VM 결과를 검사 근거로 사용했다. 실제 GPU fence와 장시간 resize/seek 수명은 이 단위검사로 판정하지 않는다.

`LorieNative` 실제 로그에서 Present copy의 GPU offload는0회였다. native GL renderer 자체는 Zink/Turnip이며, 이 두 사실을 혼동하지 않는다. 마지막 출력 copy 경계가 다음 드라이버 계측 대상이다.

최종 `gpu-final-open.json`, `gpu-final-state.json`은 같은 데스크톱 token, 원래 Chromium 두 창, 다시 연 Code 및 Local Dev 미리보기, Bun1.4.3 응답, 마지막 저장15번 보존을 확인한다. 진단 close 인자 오류로 Code가 한 번 닫힌 사실과 수정은 연구 문서에 기록했다. 계측·batch daemon은 exit0,9224 debug 포트는 닫혔고 ADB19224 전달을 제거했다. 전용 빌드 VM도 정지했다. 원격 인증은 사용자 요청대로 나중에 검증한다.

## Native AHardwareBuffer GPU 출력 적용

14:22 이후 native Weston 전용 Turnip WSI를 실제 설치했다. `graphics-ahb/selection.json`의 SHA256 검사를 통과한 private ICD만 Weston에 주입하며, guest Hyprland/브라우저의 기존 드라이버와 개인 설정을 전역 교체하지 않는다. 현재 driver SHA256은 `7f05d872e36f32fc130477fb2d6c01da88715dd97b22155bbbca4945092c14d1`이다.

- AHB modifier1255 transport, 실제 linear stride 확인, DMA-BUF memory-type 교집합, Vulkan fence/Present lifetime을 구현했다.
- 640×480/1919×800/1920×1280 동적 색상·프레임 번호 검사가 모두 일치했다.
- 실제 Omarchy의 Termux:X11 로그가 `297/297`, `300/300 present copies offloaded to GPU`를 보고했다. 출력의 CPU copy 경계를 제거한 증거이며, 영상 디코딩까지 하드웨어화됐다는 의미는 아니다.
- Weston은 Zink/Adreno830, DMA-BUF modifiers, explicit sync 지원으로 실행된다.

### 새 경로의 동시 사용 결과

| 조건 | 실제 결과 |
| --- | --- |
| YouTube1080p60 + 이미 열린 Code 편집15회 + local Bun preview + Notion 열린 상태, 약183초 | 11,012frame / 76drop = **0.690%**, Code 저장15/15·DOM 반영15/15 |
| 로컬1080p60 + Code 편집5회 + preview + Notion 열린 상태, 약90초 | 5,438frame / 11drop = **0.202%**, 저장5/5·DOM 반영5/5 |
| 동시 실행 프로세스 표본 | 73개, 좀비0개, 같은 세션 유지; Hyprland IPC p95 **3.38ms** |
| Code 저장키→브라우저 DOM 관측 | 15표본 p50 **272.5ms**, p95 **652.8ms**; DOM 샘플 간격500ms 포함 |

증거: `ahb-steady-youtube.json`, `ahb-editor-steady.json`, `ahb-local-soak.json`, `ahb-editor-local.json`, `ahb-development-processes.json`, `ahb-edit-latency.json`, `ahb-present-gpu.log`.

첫60초 YouTube 시험은 Code 파일 열기 CLI를 동시에 재실행해서 시작2–5초에 손실이 집중됐고1.81%였다. 이를 삭제하거나0.69%로 대체하지 않았다. 183초 시험은 이미 열린 편집기에서 계속 편집하는 조건이다. 따라서 앱 cold-start 무지연, 물리 입력→화면 지연, 장시간 발열, 실제 Notion 문서 편집, 원격 네트워크 성능까지 수락하지 않는다. Notion은 실제 창의 존재를 확인하고 열린 상태로 유지했으며 개인 문서는 수정하지 않았다. 프레임 손실0%라고 주장하지 않는다.

VAAPI hardware decode trial은3.54%라 기본값으로 채택하지 않았다. PRoot 고성능 코어 고정도1.94%로 개선되지 않아 원래0–7 affinity로 복원했다. Chromium native Wayland 실험은 로컬 단기 표본을 통과했으나 실제 YouTube+편집에서24.90%로 악화되어 기본 XWayland 구성을 유지했다. GPU 합성이 software로 떨어진 별도0.66% 표본 역시 채택하지 않았다.

시작 시 잠깐 비어 있는 `/proc/PID/cmdline`을 기록하던 경쟁을 수정했고, 종료 시 snapshot 이후 exec/adoption된 자식은 현재 부모 신원을 다시 확인하도록 보완했다. 부모 소유권을 확인할 수 없는 변경된 PID는 계속 거부한다. 관련 host 검사122개가 통과했다. 종료 직후 X11 peer가 사라지는 전환은 같은 소유권 검사로 최대 3회 자동 재검사하며, 계속 모호하면 소유 anchor를 보존한다. 실제 앱을 연 상태에서 정상 종료·재시작한 `ahb-lifecycle3.json`은 PASS이며 커스텀 설정 10개 해시가 모두 유지됐다. 앞선 lifecycle/lifecycle2 실패 기록도 남겼다.
