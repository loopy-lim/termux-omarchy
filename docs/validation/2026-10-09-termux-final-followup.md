# Termux Omarchy 후속 정리

Lenovo Y900 `Y900`, native Termux UID 10323 기준이다. 아래 앞선 앱·CPU 관찰의 Linux 세션 `4537c309-5d5e-4486-9083-624f0dafbfe1`은 종료·복구했다. 자원 수정 후 세션 `0890ca5a-3038-4fa7-8dda-2957c9f02764`에서 부하·앱·네트워크·확대 관찰을 수행했다. 이후 사용자 승인 후 Termux:X11 APK를 네 차례 교체했다. 확대 대응 세션은 `1d907e2d-191b-4635-8343-4294850e2d05`, 스크롤 후 포인터 정지 대응 세션은 `8632feb3-1d8b-4ef8-84b7-1d247f457695`, 입력 상태 재발 방어 세션은 `a57f9028-0c31-4592-a074-0e0dc764eafa`다. GPU 조회 중 마지막 세션이 종료돼 자료를 보존·복구하고 Caps 호환 APK를 설치했다. Caps 호환 APK의 세션은 `044bceeb-c5d3-4f59-97d8-a827143e9e02`였으며, 후속 직접 입력 수정 APK 적용 후 현재 세션은 `2e9eb6a1-c83f-466b-8bb5-f053c6f3fcc2`다. 현재 사용 안내 문서를 최신 진입점으로 삼고 초기 APK·Sway 자료는 이력으로 구분했다.

## 이번 적용과 확인

- 앞선 native PRoot 임시 경로 수정 적용·재시작에서 개인 설정·이전 journal·전역 PRoot 보존, bar·background 자동 시작과 설정 오류 없음을 확인했다.
- 종료 전 정상 런처의 Chromium·VS Code 동시 창 표시. 사용자 Remote-SSH 연결 성공 확인과 해당 별칭의 resolver 성공·exec server 생성 로그 확인. 원격 파일 편집은 별도다.
- 종료 전 Linux 세션의 DNS·인증서 검증 HTTPS 200, Android bridge ping, AAudio 출력 sink 준비. 소리 청취·Wi-Fi 재연결은 별도다.
- native Termux의 새 `loopy-omarchy` 명령 최초 설치에서 상태 ready, 동일 재설치 무변경, 기존 셸 rc와 당시 세션 보존을 확인했다.
- setup08에 현재 승인된 단축키 payload를 포함하고 이전 07 묶음 보존. 해당 시점 archive/catalog/단축키 hash와 packaging 14개, terminal 13개 검사를 재실행했다. setup08은 이후 자원 감시 수정을 포함하지 않으며 새 기기 전체 설치를 뜻하지 않는다.
- [개인 Neovim 설치 02](../../build/diagnostics/termux-omarchy-personal-nvim-install-device-20261009-02/receipt.json): AstroNvim 설정·잠금 plugin 소스 81개 오프라인 설치 `PASS`, 누락 0개, build script 미실행. [시작 검사 04](../../build/diagnostics/termux-omarchy-personal-nvim-guest-start-device-20261009-04/receipt.json)는 Astro·Lazy 활성과 guest exit 0을 확인했지만 같은 세션 종료로 전체 `FAILED`다. 개인 설정의 GUI 수락은 아니다.

## VS Code 동기화 중 종료와 복구

사용자는 VS Code Settings Sync·확장 설치 중 전체 Linux 세션이 종료됐다고 보고했다. [민감한 본문을 기록하지 않은 로그 집계](../../build/diagnostics/termux-omarchy-vscode-sync-crash-log-device-20261009-01/receipt.json)는 `Sync started` 1회, `Installing extension` 123회, `Sync done` 0회를 확인했다. 이 집계만으로 특정 확장이나 Android의 프로세스 제한을 종료 원인으로 확정하지 않는다.

[native 실패 상태](../../build/diagnostics/termux-omarchy-resource-crash-readonly-device-20261009-01/receipt.json)의 직접 종료 경로는 런타임 자원 감시의 `resource-type` / `ResourceFailure`였다. [종류 확인](../../build/diagnostics/termux-omarchy-resource-types-readonly-device-20261009-01/receipt.json)에서 native UID 10323 소유, 깊이 1, 크기 0인 FIFO 4개가 기존 감시기가 허용하지 않는 종류로 확인됐다. 당시 cleanup에는 `descendant-changed`도 기록됐으며 기존 프로세스 도우미의 별도 256개 제한을 4096개로 수정했다. FIFO를 만든 앱의 신원은 이 자료로 확정하지 않는다.

[복구 기록](../../build/diagnostics/termux-omarchy-failed-resource-quarantine-device-20261009-01/receipt.json)은 정확한 inode·소유자·mode로 확인한 FIFO 4개와 미등록 소켓 2개, 총 6개 항목을 별도 quarantine에 보존한 뒤 정상 `stop`을 수행했다. `stopped`, `terminationConfirmed=true`, `ownerGone=true`로 `PASS`다. 상태 파일을 수동 편집하거나 항목을 삭제하지 않았으며 quarantine을 보존한다.

## 프로세스 정책과 자원 수정 적용

[Android 정책 기록](../../build/diagnostics/termux-omarchy-process-policy-device-20261009-01/receipt.json)은 이전 1024에서 설정 조회값과 실제 ActivityManager 적용값 4096까지 확인했다. override 조회만 4096인 단계에서는 실제 적용값이 계속 1024였고, 이후 base 설정 변경 이벤트를 전달한 뒤 `finalEffectiveConstants`가 4096이 됐다. 프로세스 감시는 끄지 않았고 전역 config sync 설정도 바꾸지 않았다. 재부팅 후 유지와 무제한 실행은 검증하지 않았다.

별도 고정 [resources-update01 묶음](../../build/deliverables/LoopyOmarchy-Termux-resources-update-20261009-01.tar.gz)은 FIFO를 열지 않는 metadata 감시·복구 검사, 프로세스 추적 한도 수정, 실패 원인 기록과 대응 터미널 명령 pin을 담는다. SHA-256은 `fbc1f982600e1187d670456a33ff6c75528d97efea0e8d010cefa73d9f6f5cff`다. [호스트 회귀 78개](../../build/diagnostics/termux-omarchy-resources-update-host-20261009-01/receipt.json)는 모두 통과했다. setup08과 terminal-command01 고정 자료는 수정하지 않았다.

[native 업데이트·재시작 기록](../../build/diagnostics/termux-omarchy-resources-update-device-20261009-01/receipt.json)은 확실한 종료 후 runtime·processes·resources 세 파일을 적용하고 다섯 번째 journal을 추가했으며 이전 네 journal·백업·개인 설정·전역 PRoot를 보존했다. 기존 터미널 명령도 원래 바이트를 별도 백업하고 갱신했다. 새 세션의 시작·상태 `ready`와 1920×1280, AAudio·Android bridge 준비를 확인해 `PASS`다. 두 응답의 `shellReady=false`는 현재 런타임 코드의 고정값이며 실제 shell 부재를 나타내지 않는다.

[후속 화면 상태](../../build/diagnostics/termux-omarchy-trackpad-browser-state-device-20261009-01/receipt.json)는 같은 새 세션에서 원본 `omarchy-bar`·`omarchy-background`가 모두 alpha 1로 표시되고, 화면 1920×1280·배율 1.25·설정 오류 없음·기존 VS Code Wayland 창 보존을 확인해 `PASS`다. 설정 변경이나 런타임 재시작 없이 확인했다. 전체 앱, 동기화 완료, 개인 Neovim GUI와 장시간 안정성 수락은 별도다.

[후속 native 부하 검사](../../build/diagnostics/termux-omarchy-process-fifo-load-device-20261009-01/receipt.json)는 같은 새 세션에서 VS Code Wayland 창을 부하 전후에 확인했다. guest UID 1000의 공개 `sleep` 자식 300개를 0.85초에 만들고 FIFO 4개와 함께 8초 유지했다. 관찰 최대 세션 자손은 336개로 종전 256개 한도를 넘었으며 300개 자식 회수·FIFO 4개 제거·같은 세션 `ready`를 확인해 `PASS`다. 실제 Settings Sync 완료, 4096개 실부하, 장시간 soak 또는 물리 지연 수락은 아니다.

[부하 이후 native 상태 검사](../../build/diagnostics/termux-omarchy-vscode-post-load-health-device-20261009-01/receipt.json)는 20.268초·40회 관찰 동안 같은 세션 `ready`와 VS Code Wayland 창을 확인했다. 최신 로그의 고정 marker는 `Sync started` 1회·`Installing extension` 117회이며 `Sync done`은 0회다. 관찰한 로그에서 GPU process 종료·`exit_code=11`·`FATAL`·예기치 않은 extension host 종료 marker는 모두 0회였다. 이후 사용자는 “동기화·설치 중에도 유지됨”이라고 실제 재시험 결과를 확인했다. 진행 중 세션 유지에 대한 사용자 확인이며 동기화·전체 확장 설치 완료를 뜻하지 않는다.

## VS Code 빈 Buffer 쓰기 호환 수정

[실제 Electron 재현](../../build/diagnostics/termux-omarchy-vscode-empty-backing-repro-device-20261009-01/receipt.json)은 guest UID 1000·Electron 43.7.7에서 길이 0인 Buffer·Uint8Array의 쓰기가 `EFAULT: bad address in system call argument, write`로 실패함을 확인했다. 같은 환경의 실제 provider 검사에서 [원본 9사례 중 3개가 EFAULT로 실패](../../build/diagnostics/termux-omarchy-vscode-provider-regression-red-device-20261009-01/receipt.json)했고, [호환 수정 후 9개 모두 통과](../../build/diagnostics/termux-omarchy-vscode-provider-regression-green-device-20261009-01/receipt.json)했다. 쓰기를 mock하지 않았으며 잘못된 descriptor·읽기 전용 descriptor·잘못된 offset의 오류와 양수 길이·position 동작도 검사했다.

[호환 수정 builder](../../termux/vscode_write_compat.py)는 `sharedProcessMain.js` 한 파일에 54바이트 guard만 추가한다. [native 적용 02](../../build/diagnostics/termux-omarchy-vscode-empty-write-apply-device-20261009-02/receipt.json)는 사용자 저장·Code 재시작 승인 후 기존 Code 프로세스 10개를 정상 종료하고 원본을 native 백업 `vscode-empty-write-compat-20261009-01`에 보존한 뒤 적용해 `PASS`다. 새 Code PID 23819의 native Wayland 창을 확인했고 Linux 세션 `1d907e2d-191b-4635-8343-4294850e2d05`와 기존 Chromium PID 17475는 유지됐다. 개인 설정을 직접 편집하거나 Linux를 재시작하지 않았다. source SHA는 원본 `ae097590baddecb463094d667dfc8851b2a3238e20af6527b4c341810b6978c6`에서 `8e3aff92636f07db7951d67bdb58a6e96428f4e69a45f1a6dfd421d32872f446`로 바뀌었다. 기존 고정 설치 산출물은 수정하지 않았다.

이후 최신 Sync Now 재시험에서 사용자는 “동기화는 진행되지만 테마가 아직 안 바뀜”이라고 확인했다. [후속 테마·동기화 읽기 전용 점검](../../build/diagnostics/termux-omarchy-vscode-theme-sync-readonly-device-20261009-01/receipt.json)은 같은 세션의 로그 폴더 `20261009T114350`에서 `Sync started`·`Sync done` 각 4회, `EFAULT` 0회, `SettingsSkipped` 3회를 확인해 진단 `PASS`다. 수정 후 네 번의 동기화 시도에서 해당 쓰기 오류가 관찰되지 않은 개선 증거이며, 모든 동기화 자원이 성공했다는 뜻은 아니다.

당시 기본 settings는 115바이트였고 UI 테마 키·local lastSync settings 자료가 없었다. 후속 [고정 오류 이유 확인](../../build/diagnostics/termux-omarchy-vscode-sync-conflict-reason-readonly-device-20261009-01/receipt.json)은 설정 충돌로 세 차례 건너뜀과 충돌 감지 1회를 확인했다. [공식 Accept Remote UI 적용](../../build/diagnostics/termux-omarchy-vscode-sync-conflict-ui-accept-remote-device-20261009-01/receipt.json)은 원래 로컬 백업을 보존하고 클라우드 업로드 없이 원격 개인 설정을 수신했다. settings는 14,890바이트·SHA-256 `7d379a3cefc03c618639f56dd34d969e23273f6d013bfa91714b952f322d5a41`이며 lastSync settings 자료가 생겼다. [후속 읽기 전용 확인](../../build/diagnostics/termux-omarchy-vscode-theme-sync-readonly-device-20261009-02/receipt.json)은 `Xcode Classic (Dark)`·`material-icon-theme`·글자 크기 16·custom title bar 설정과 로컬 설정 갱신 marker를 확인했다. 테마 확장 설치와 실제 화면 적용은 다음과 같이 구분한다.

## VS Code 확장 서명 검증기와 개인 테마

[서명 실패 읽기 전용 확인](../../build/diagnostics/termux-omarchy-vscode-extension-signature-readonly-device-20261009-01/receipt.json)은 테마·아이콘 검증기의 `UnknownError`·내부 코드 137을 확인했다. [실제 native A/B](../../build/diagnostics/termux-omarchy-vscode-signature-gc-ab-device-20261009-01/receipt.json)는 공식 ARM64 검증기와 동일한 서명된 Xcode 패키지로 baseline exit 137·GC heap 초기화/CoreCLR 실패·`0x8007000E`를 재현했다. 자식 프로세스에만 `DOTNET_GCHeapHardLimit=0x10000000`을 적용하면 758ms에 exit 0으로 패키지 무결성·서명 신뢰·타임스탬프 검사가 모두 통과했다. native `RLIMIT_AS`는 unlimited였으며 Android 프로세스 수 한도 오류로 분류하지 않는다. 이는 [VS Code 공식 오류 사례](https://github.com/microsoft/vscode/issues/249427) 및 [.NET의 프로세스별 GC 설정](https://learn.microsoft.com/en-us/dotnet/core/runtime-config/garbage-collector#heap-hard-limit)과 일치한다. 정확한 실패 mmap 주소·크기는 측정하지 않았다.

[호환 builder](../../termux/vscode_signature_compat.py)와 [native 적용](../../build/diagnostics/termux-omarchy-vscode-signature-helper-apply-device-20261009-01/receipt.json)은 공식 검증기 SHA-256 `62dbbc4da520c1b2923a862487e68714542f364bd600ea3a3049e9bd3ab59c5d`를 실행 가능한 원본 sibling 백업으로 보존하고, 259바이트 launcher SHA-256 `d55c33c2999b2c752f99d08c263d04f7623a518bf736a974b50907ea068e2cd7`만 원자적으로 적용했다. 검증기 자식에만 GC 설정을 전달하며 전역 환경·VS Code의 서명 정책·공식 JS 모듈·ASAR는 유지한다. PREPARED/APPLIED journal과 디렉터리 fsync를 확인했다. [호스트 실제 공식 모듈 검사](../../build/diagnostics/termux-omarchy-vscode-signature-module-regression-host-20261009-01/receipt.json)는 원본·launcher 양쪽 모두 실제 Microsoft 검증기에서 정상 서명 패키지 성공과 변조된 정상 ZIP의 `PackageIntegrityCheckFailed` 30 거부를 확인했다. 호스트 시험은 고정 guest 실행 경로만 Mac 공식 검증기 경로로 바꿨으며 native A/B와 구분한다.

[정상 Marketplace 설치 04](../../build/diagnostics/termux-omarchy-vscode-personal-theme-install-device-20261009-04/receipt.json)는 Xcode Theme 5.2.0·Material Icon Theme 5.39.0 모두 CLI exit 0·설치 성공 marker와 정확한 manifest/theme contribution을 확인해 `PASS`다. Marketplace 서명 검증은 켜져 있고 개인 settings hash·기본 SSH config는 유지됐다. 별도 [공식 패키지·서명의 Mac 검증](../../build/diagnostics/termux-omarchy-vscode-appearance-signed-host-20261009-01/receipt.json)도 두 확장 모두 통과했다. 설치와 실제 테마 화면 표시·전체 확장 동기화 완료는 별도다.

이후 [실제 native 공식 ASAR 모듈 검사](../../build/diagnostics/termux-omarchy-vscode-signature-module-regression-device-20261009-01/receipt.json)에서도 정상 서명 패키지는 `Success`·내부 코드 0, 변조 패키지는 `PackageIntegrityCheckFailed`·내부 코드 30으로 거부돼 `PASS`다. 실제 검증 함수를 mock하거나 서명 검사를 우회하지 않았으며 자식 전용 GC 설정과 부모 환경 보존을 확인했다. 이 결과는 서명 검증 경로에 대한 수락이며 전체 확장 설치 완료를 뜻하지 않는다.

[최초 테마 pin 확인](../../build/diagnostics/termux-omarchy-vscode-theme-pinning-readonly-device-20261009-01/receipt.json)은 두 테마 모두 실제 설치 registry의 `pinned=true`를 확인했다. 개별 package metadata에 pin 값이 없다는 사실로 pin 해제를 판단하지 않았다. 이후 두 확장 각각의 공식 자동 업데이트 UI에서 pin을 해제했다. [읽기 전용 재확인 03](../../build/diagnostics/termux-omarchy-vscode-theme-pinning-readonly-device-20261009-03/receipt.json)은 두 확장 모두 `registryPinned=false`, 기존 버전·manifest·개인 settings hash 보존을 확인해 `PASS`다. 전역 자동 업데이트 설정은 default로 유지했다.

## 확장 동기화 재점검과 복구

[확장 읽기 전용 감사](../../build/diagnostics/termux-omarchy-vscode-extensions-audit-device-20261009-01/receipt.json)는 로컬 lastSync snapshot 기준 개인 확장 127개 중 당시 설치 14개·누락 113개를 확인했다. 새 클라우드 목록을 직접 가져온 검사는 아니다. 당시 로그 폴더 `20261009T121318`의 동기화 시작·종료 marker는 각 5회였지만, `Extensions: No changes` 4회만으로 누락이 없다고 판단하지 않는다. renderer 로그에는 `EFAULT`가 1회 있었으며 구체적인 작업·발생원은 아직 확인하지 못했다. 앞선 `20261009T114350`의 `EFAULT` 0회와 실제 sharedProcess 빈 쓰기 9사례 통과는 각각 당시 범위의 증거로 유지한다.

처음 감사의 skipped·builtin 빈 배열은 `lastSyncextensions.json` 바깥 필드를 조회한 결과로, 실제 skipped 상태가 없다는 뜻이 아니었다. [올바른 저장 위치 재확인](../../build/diagnostics/termux-omarchy-vscode-extensions-sync-state-device-20261009-02/receipt.json)은 application storage의 `extensions.lastSyncUserData`에서 skipped 115개·builtin 96개를 확인했다. 이전 누락 113개는 모두 skipped 목록에 포함됐다. 기존 감사 영수증을 수정하지 않고 해석을 정정한다.

[확장 복구 01](../../build/diagnostics/termux-omarchy-vscode-extensions-recovery-device-20261009-01/receipt.json)은 EditorConfig·Prettier·ESLint·YAML·Even Better TOML·Error Lens·Pretty TypeScript Errors·Tailwind CSS·rust-analyzer 9개를 설치했다. 다음 OpenAI 확장에서 90초 timeout이 발생해 전체 결과는 `FAILED`·`extension-timeout`이다. 개인 settings 편집·동기화 초기화·클라우드 삭제·Code 재시작은 없었고 Linux·GUI는 유지됐다. 이 실패 기록을 후속 결과로 덮어쓰지 않았다.

[확장 복구 02 최종 기록](../../build/diagnostics/termux-omarchy-vscode-extensions-recovery-device-20261009-02/receipt.json)은 93개 신규 설치·앞서 설치한 9개 재사용으로 복구 대상 108개 중 102개를 확인했다. 최초 설치 14개를 합한 총 설치는 116개다. 실행 결과는 `PASS`지만 `recoveryCompletedWithoutGaps=false`로 6개 누락이 남는다. `amazonwebservices.codewhisperer-for-command-line-companion`·`dzannotti.vscode-babel-coloring`·`github.copilot-nightly`·`ms-vsliveshare.vsliveshare-pack`·`ms-vsonline.vsonline`·`withfig.fig`는 각각 공식 CLI exit 1·`not found`로 설치하지 못했다. 사용자 비활성·ignore 또는 Windows 전용인 별도 5개는 의도적으로 보류했다. 개인 settings SHA-256 `7d379a3cefc03c618639f56dd34d969e23273f6d013bfa91714b952f322d5a41`·기존 비활성 확장 2개·앱과 Linux 세션을 유지했다. 사용자 요청에 따라 설치를 마무리하며 추가 Sync Now·초기화·비활성 확장 재활성화는 요청하지 않았다. 명시적 확장 활성화 명령은 없었지만 GUI 자동 활성화 가능성은 있다.

[복구 후 제한된 native 감사](../../build/diagnostics/termux-omarchy-vscode-extensions-post-recovery-audit-device-20261009-01/receipt.json)는 registry와 등록 확장 116개의 정확한 ID·버전·platform·manifest를 확인해 `PASS`다. GitLens manifest는 1,090,029바이트로 앞선 감사 02의 1 MiB 제한을 넘었으며, 이번에는 파일별 4 MiB·전체 32 MiB 한도에서 총 4,501,184바이트를 읽었다. 사용자 settings·앱·Linux 세션은 유지했다. [호스트 의존성 분석 02](../../build/diagnostics/termux-omarchy-vscode-extension-dependencies-host-20261009-02/receipt.json)에서 추가 설치 가능한 필수 누락은 없다. Java Test가 요구하는 유일한 미설치 필수 확장 `redhat.java`는 기존 사용자 제외를 유지했다. 참조된 내장 확장 5개(`ms-vscode.js-debug`, `vscode.git`, `vscode.github-authentication`, `vscode.docker`, `vscode.yaml`)의 존재는 앞선 native 내장 확장 96개 감사에 근거하며 이번에 다시 훑지 않았다. 선택 pack의 미설치 항목 `serayuzgur.crates`·`ms-vscode.cmake-tools`·`ms-vscode.azure-repos`·`openai.codex-audio`는 개인 snapshot 밖에 있고 `redhat.java`는 사용자 제외라 추가하지 않았다.

현재 GUI 로그에는 33개 설치 확장의 활성화 시도 marker 48회가 있지만 각 기능의 성공을 입증하지 않는다. 선택한 활성화 실패·확장 호스트 종료·서명 오류 marker는 없었고 sharedProcess에도 선택한 오류 marker가 없었다. renderer의 `EFAULT` 1회는 남아 있으며 특정 확장이나 작업으로 연결하지 못했다. 실제 확장 기능·테마 표시·원격 편집은 별도 수락 대상이다. 이번 감사·분석은 추가 동기화·설치·재시작 없이 수행했다.

## 개인 동기화 이후 SSH 별칭

클라우드 개인 settings에는 이전 앱 전용 `remote.SSH.configFile`·로그인 터미널 설정이 없다. [기본 SSH config 복구](../../build/diagnostics/termux-omarchy-vscode-default-ssh-config-apply-device-20261009-01/receipt.json)는 settings와 클라우드를 다시 편집하지 않고 기존 파일이 없을 때만 mode 0600의 기본 config에 관리 별칭 파일 Include를 추가했다. guest `ssh -G`가 `loopy-development`를 `loopy@100.80.133.120`으로 해석하는 것을 확인해 `PASS`다. 개인 키·비밀번호·다른 config 본문을 기록하지 않았으며 연결·인증을 요청하지 않았다. 이후 APK 재시작에서도 config와 개인 settings hash를 보존했다. 실제 Remote-SSH 재연결·원격 편집은 앞선 연결 성공 자료와 구분한다.

## 후속 인터넷 단절·웹 종료 보고

이후 사용자는 인터넷이 완전히 끊기고 웹 창도 닫힌다고 보고했다. [신고 후 native·guest 점검](../../build/diagnostics/termux-omarchy-network-loss-device-20261009-01/receipt.json)은 같은 세션에서 두 실행 환경 모두 example.com·VS Code Marketplace·Code 업데이트·Notion·Figma의 DNS를 해석하고 인증서 검증 HTTPS에 도달했다. Marketplace의 HTTP 404와 Notion·Figma의 301은 연결 도달 응답이며 서비스 기능 완료를 뜻하지 않는다. 점검 중 같은 세션 `ready`를 확인해 `PASS`지만 그 시점에 native·guest 차이가 없었다는 제한된 증거다. 간헐적 인터넷 단절·브라우저 종료의 원인과 해결은 아직 확인하지 않았다.

[후속 파일·로그 점검](../../build/diagnostics/termux-omarchy-browser-network-followup-device-20261009-01/receipt.json)은 실제 guest resolver가 symlink가 아닌 일반 파일이며 nameserver가 `8.8.8.8`·`8.8.4.4`임을 확인했다. `/usr/bin/chromium`은 67,672바이트 ELF 실행 파일로, 실행 스크립트를 읽은 검사가 아니다. 같은 세션의 고정 fatal·GPU 종료·네트워크·메모리·자원 감시 marker 집계는 모두 0회였다. 이 제한된 집계는 모든 종료나 간헐적 단절이 없었다는 증거가 아니다.

[정상 Chromium 재실행](../../build/diagnostics/termux-omarchy-browser-reopen-device-20261009-01/receipt.json)은 같은 세션에서 3.021초에 Xwayland 창을 확인했다. 관찰 구간 끝 19.664초까지 같은 PID 9884·birth 86814646의 Chromium과 기존 VS Code Wayland 창이 함께 유지돼 `PASS`다. 창은 사용자를 위해 열어 두었으며 설정을 바꾸지 않았다. 현재 검사의 실패로 표시하지 않되, 약 20초의 성공을 간헐적 인터넷 단절·웹 종료의 해결로 확대하지 않는다.

## 트랙패드 확대 관찰과 APK 업데이트

사용자는 트랙패드를 움직일 때 화면이 커진다고 보고했다. APK 교체 전 [renderer zoom 관찰 01](../../build/diagnostics/termux-omarchy-live-view-zoom-device-20261009-01/receipt.json)·[02](../../build/diagnostics/termux-omarchy-live-view-zoom-device-20261009-02/receipt.json)와 [03의 관찰 trace](../../build/diagnostics/termux-omarchy-live-view-zoom-device-20261009-03/stdout.jsonl)에서 관찰한 renderer zoom은 모두 100%였다. 03은 helper timeout으로 끝났으며 `PASS`로 표시하지 않는다. [geometry 01](../../build/diagnostics/termux-omarchy-live-view-geometry-device-20261009-01/receipt.json)·[02](../../build/diagnostics/termux-omarchy-live-view-geometry-device-20261009-02/receipt.json)의 관찰값은 입력 source 1920×1280, viewport·측정 화면 3840×2560이었다. APK 교체 전 geometry 02는 180회 표본에서 이 값과 renderer zoom 100%가 일정했으며 Java exit 0으로 끝났고 helper deadline 강제 종료가 없었다. 호스트 관찰 도구의 종료도 범위를 제한한 프로세스 조회로 확인했다. 이 값만으로 사용자 확대 순간과의 시간상 연관이나 원인을 확정하지 않는다.

[guest 확대·modifier 관찰](../../build/diagnostics/termux-omarchy-trackpad-zoom-modifiers-device-20261009-02/receipt.json)은 90회 표본에서 cursor zoom 1, 좌우 Ctrl·Alt·Super가 모두 눌리지 않은 상태와 같은 세션 `ready`를 확인했다. 사용자 보고를 부정하는 자료가 아니며, 실제 확대 사건과 연결한 재현은 아직 확보하지 못했다.

[Termux:X11 후보 준비 기록](../../build/termux-x11-trackpad-zoom-20261009-01/artifact/receipt.json)의 [APK](../../build/termux-x11-trackpad-zoom-20261009-01/artifact/LoopyOmarchy-TermuxX11-trackpad-pinch-candidate-20261009-01.apk)는 SHA-256 `9b1018d3ec114a8174966aa52c66aabc43a7e30439b0d54a29ca83fee054074f`다. 분기 경로 검사 10개와 DEX·payload 보존 검사를 확인했고 기존 키보드 프로세스·한글 키 수정 및 native library를 유지한다. 이 동결 준비 영수증의 `PREPARED_NOT_INSTALLED_CAUSE_UNCONFIRMED`는 준비 당시의 과거 상태이며 원본 자료는 변경하지 않았다.

사용자 저장·재시작 승인 후 APK 업데이트를 진행했다. [첫 정상 종료 요청 01](../../build/diagnostics/termux-omarchy-trackpad-update-stop-device-20261009-01/receipt.json)은 cleanup의 `descendant-changed`로 `FAILED`였고, [같은 세션의 정상 종료 재요청 02](../../build/diagnostics/termux-omarchy-trackpad-update-stop-device-20261009-02/receipt.json)는 `stopped`·`terminationConfirmed=true`·`ownerGone=true`로 `PASS`였다. 실패 기록을 성공으로 덮어쓰지 않았다.

[실제 APK 설치](../../build/diagnostics/termux-omarchy-trackpad-update-apk-device-20261009-01/receipt.json)는 설치된 SHA-256이 위 APK와 일치해 `PASS`다. 앱 제거·데이터 삭제 없이 업데이트했으며 키보드 설정과 화면 배율 preference `displayScale=200`·`scaled`를 유지했다. Linux 런타임 11개 파일·입력 journal·native 명령의 hash와 inode도 종료 전후 모두 동일했다.

[첫 시작 요청 01](../../build/diagnostics/termux-omarchy-trackpad-update-start-device-20261009-01/receipt.json)은 실제 Linux 시작 전에 `launcher-activity-unavailable`로 실패했다. 현재 X11 Activity를 foreground로 연 뒤 정상 native `loopy-omarchy start`를 실행한 [재시도 02](../../build/diagnostics/termux-omarchy-trackpad-update-start-device-20261009-02/receipt.json)는 `PASS`다. 새 세션 `1d907e2d-191b-4635-8343-4294850e2d05`, live X11 1920×1280·Hyprland 배율 1.25·60 Hz, bar·background alpha 1·설정 오류 없음·AAudio·Android bridge 준비를 확인했다. 이 기록은 설치·시작·보존 확인이며 물리 트랙패드 확대의 원인이나 해결을 확정하지 않는다.

[설치 후 앱·배율 관찰](../../build/diagnostics/termux-omarchy-trackpad-post-update-observe-device-20261009-01/receipt.json)은 60.7초 동안 같은 새 세션 `ready`를 확인해 `PASS`다. Chromium PID 17475의 Xwayland 창은 3.468초, VS Code PID 17501의 native Wayland 창은 5.52초에 표시됐으며 두 창 모두 59.686초까지 유지됐다. live X11 1920×1280·Hyprland 배율 1.25·guest cursor zoom 1은 전 표본에서 일정했다. 별도 [설치 후 geometry 관찰](../../build/diagnostics/termux-omarchy-live-view-geometry-post-update-device-20261009-01/receipt.json)은 60회 표본의 geometry·renderer zoom 100%가 고정된 상태로 Java exit 0·`deadlineStop=false`로 끝났다. 일반 키 입력이나 화면 캡처 없이 관찰했으며 관찰 종료 후 forward도 `finally`에서 제거했다. 이 제한된 관찰은 물리 입력 통과나 사용자 증상 해결을 뜻하지 않는다.

이후 사용자는 클릭은 되지만 트랙패드를 움직여도 포인터가 움직이지 않는다고 확인했다. [event7 원시 입력 관찰](../../build/diagnostics/termux-omarchy-trackpad-kernel-motion-device-20261009-01/receipt.json)의 ABS 제스처와 겹치는 [120초 Linux 포인터 관찰](../../build/diagnostics/termux-omarchy-trackpad-motion-device-20261009-01/receipt.json)에서 X root 좌표 1450,563과 Hyprland 좌표 1160,450이 일정했다. 포인터 관찰의 `PASS`는 조회 성공·같은 세션 유지이며 실제 포인터 이동 성공이 아니다.

[입력 handler 상태 관찰](../../build/diagnostics/termux-omarchy-trackpad-state-observe-device-20261009-01/receipt.json)의 실제 상태 표본 10개에서 pointer capture·window/view focus가 활성 상태였고 density 2.5·captured pointer speed 1이었다. 중첩 touchpad handler의 `suppressCursorMovement`·`swipeCompleted`는 true, root handler의 두 값은 false였다. 이 상태 차이를 관찰했지만 포인터 정지의 원인으로 확정하지 않는다.

되돌릴 수 있는 `capture=false` 90초 A/B 시험을 진행했다. [A/B 포인터 관찰 기록](../../build/diagnostics/termux-omarchy-trackpad-capture-ab-device-20261009-01/receipt.json)의 진단 `PASS`는 조회·같은 세션 유지와 원래 preference 복원·다른 preference 무변경을 포함하며 포인터 좌표는 계속 일정했다. 함께 실행한 [A/B 원시 입력 관찰](../../build/diagnostics/termux-omarchy-trackpad-kernel-capture-ab-device-20261009-01/receipt.json)의 event7 counts는 빈 값으로 hardware 제스처가 관찰되지 않았다. 따라서 capture 변경의 동작 효과는 `INCONCLUSIVE`이며 행동 `PASS`로 표시하지 않는다.

`preferencesRestored=true`는 설정값 복원이다. 소스의 preference reload 경로만으로 capture를 다시 요청하지 않으므로 일반 클릭의 `ACTION_UP` 전 실제 Android pointer capture까지 복귀했다고 보장하지 않는다. 이후 사용자는 “움직이다가 두 손가락으로 스크롤 한 번이라도 하면 멈춤”이라고 답했다. 이 답변은 A/B의 원시 입력 기록과 시간상 일치가 확보되지 않아 capture 정책의 효과로 판정하지 않는다.

[스크롤 대응 APK 준비 기록](../../build/termux-x11-trackpad-scroll-20261009-01/artifact/receipt.json)은 실제 production method에서 원본 22사례 중 5개 실패, 수정 후 22개 통과와 실제 DEX 분기 18개·기존 pinch guard 10개 검사를 확인했다. 물리 touchpad가 여러 손가락 스크롤에서 한 손가락 이동으로 돌아올 때 이동 억제를 해제한다. 3→1 전환에서도 기존 swipe 동작을 재실행하지 않고 이동을 재개한다. 기존 클래스 1,662개·키보드 manifest·native 수정과 APK payload 493개 중 492개는 바이트가 같고 `classes.dex`만 바뀌었다. 준비 기록의 `NOT_INSTALLED`는 당시 상태다.

사용자 저장·재시작 승인 후 [실제 APK 설치](../../build/diagnostics/termux-omarchy-trackpad-scroll-install-device-20261009-01/receipt.json)에서 SHA-256 `1dfe7a0392a5af5b87db6639345f3fb09a54127a20804ca29c0ca4b4dfad65b4` 일치를 확인했다. 앱 제거·데이터 삭제 없이 업데이트했으며 [정상 시작 03](../../build/diagnostics/termux-omarchy-trackpad-scroll-start-device-20261009-03/receipt.json)은 새 세션 `8632feb3-1d8b-4ef8-84b7-1d247f457695`의 `ready`, live X11 1920×1280·Hyprland 배율 1.25·60 Hz·원본 bar/background alpha 1·AAudio·Android bridge와 설정 오류 없음을 확인해 `PASS`다. 키보드·화면 preferences와 런타임 파일·개인 settings·EFAULT provider 수정·기본 SSH config hash를 보존했다. 이후 사용자는 “처음부터 이동이 안 됨”이라고 확인해 새 APK의 물리 포인터 이동 수락은 `FAILED`다. Alt+Space/Alt+Tab/Esc·확대 재발의 새 APK 물리 수락도 별도로 남아 있다.

[후속 40초 좌표 관찰](../../build/diagnostics/termux-omarchy-trackpad-synthetic-cursor-device-20261009-01/receipt.json)은 같은 세션의 79회 표본에서 X11·Hyprland 각각 20개 좌표를 확인했고 자체 X11 연결 닫기·helper 회수를 완료했다. 관찰기 자체는 입력을 주입하지 않았지만 같은 구간에 별도 외장 마우스와 합성 MOVE가 겹쳤다. 이후 사용자는 움직인 포인터가 외장 마우스였고 트랙패드는 처음부터 움직이지 않는다고 정정했다. 따라서 이 좌표 변화는 물리 트랙패드 이동 성공이나 입력 출처를 구분하는 자료로 사용할 수 없다.

[metadata 02](../../build/diagnostics/termux-omarchy-trackpad-motion-metadata-device-20261009-02/receipt.json)의 첫 이벤트 후 예외와 [03](../../build/diagnostics/termux-omarchy-trackpad-motion-metadata-device-20261009-03/receipt.json)의 0 hit 종료는 보존한다. 관찰기의 JVM slot·DEX local 불일치를 바로잡은 후 [물리 metadata 05](../../build/diagnostics/termux-omarchy-trackpad-motion-metadata-device-20261009-05/receipt.json)는 Lenovo device 96·source 1048584(`TOUCHPAD`)·tool `FINGER`의 한 손가락 `ACTION_MOVE`, 두 손가락 `POINTER_DOWN`·`MOVE`가 root·nested handler에 도달함을 확인했다. 관찰한 10개 handler 표본의 `suppressBefore`·`swipeCompletedBefore`는 모두 false였다. [트랙패드만의 120초 원시 관찰](../../build/diagnostics/termux-omarchy-trackpad-only-physical-host-20261009-03/kernel-receipt02.json)도 tracking 4·ABS X 993·ABS Y 989·BTN_TOUCH 4와 helper 회수를 확인했다. metadata 05는 Java exit 0·cleanup 완료·강제 deadline 종료 없음이며 event-thread breakpoint로 실행을 잠시 교란한 관찰이다. 이 결과는 hardware 입력과 앱 수신을 입증하지만 Linux 포인터 이동·문제 해결은 입증하지 않는다. slot 수정은 관찰기 수정이며 production 입력 수정이 아니다.

[onScroll 관찰 02](../../build/diagnostics/termux-omarchy-trackpad-scroll-metadata-breakpoint-host-20261009-02/receipt.json)는 nested handler의 device 96 callback 6개에서 X/Y 이동량 모두 0이 아니고 이동 억제가 false지만 `pointerCount=2`임을 확인했다. 사용자는 한 손가락 이동만 수행했다고 답했다. 파일 시각으로 추정한 callback 구간은 [원시 관찰 04](../../build/diagnostics/termux-omarchy-trackpad-only-physical-host-20261009-04/kernel-receipt02.json)의 첫 단일 접촉 구간과 겹친다. Java의 UTC를 직접 기록한 시험은 아니므로 정확한 동시성·지속적인 가상 접촉을 확정하지 않는다. 이후 [120초 좌표 관찰](../../build/diagnostics/termux-omarchy-trackpad-scroll-cursor-device-20261009-01/receipt.json)의 X11·Hyprland 좌표는 각각 1개로 일정했고, 원시 입력의 후속 단일 접촉 이동과 관찰 시간이 겹친다. 관찰기와 자체 연결은 모두 정리했다.

[커널 슬롯 단일 조회](../../build/diagnostics/termux-omarchy-trackpad-kernel-slots-device-20261009-01/before-capture-reset.json)는 정확한 event7 장치의 접촉 슬롯 4개가 모두 비활성임을 확인했다. 앞선 callback과 다른 시각의 조회이므로 이것만으로 Android 내부 상태 불일치를 확정하지 않는다. [입력 캡처 복구 시험](../../build/diagnostics/termux-omarchy-trackpad-capture-reset-device-20261009-01/receipt.json)은 잠금과 세션·앱 생존 확인 아래 `pointerCapture`만 false로 바꿨다가 정확한 원래 설정으로 복구했다. Linux·VS Code·Chromium 재시작과 키·포인터 주입은 없었다. true 설정만으로 즉시 capture를 요청하지 않으므로 사용자의 빈 Linux 화면 터치 후 실제 이동·스크롤 재시험이 필요하며, 복구 작업의 `PASS`는 물리 포인터 해결을 뜻하지 않는다.

복구 후 [접촉 수 120초 조회](../../build/diagnostics/termux-omarchy-trackpad-kernel-slots-device-20261009-01/after-reset-count-poll.json)의 220개 표본은 모두 접촉 0개였다. [이동 metadata 관찰](../../build/diagnostics/termux-omarchy-trackpad-motion-derived-breakpoint-host-20261009-01/receipt.json)에도 입력 hit가 없었고, 관찰 종료 후 사용자는 “이동은 되지만 스크롤 후 멈춤”이라고 답했다. 캡처 재연결의 일시 복구는 확인했지만 스크롤 후 정지는 남아 있다. 이 응답을 앞선 0 hit 구간의 입력 관찰로 소급하지 않는다. 0 hit deadline에서 Java exit 0과 별개로 `cleanupCompleted=false`가 기록된 관찰기 종료 경쟁도 보존한다. [종료 후 상태](../../build/diagnostics/termux-omarchy-trackpad-capture-reset-device-20261009-01/post-observer-health.json)는 남은 ADB forward 없음과 같은 frontend·Code·Chromium·Linux 세션 생존을 확인했으며, target breakpoint 삭제를 별도 검증했다고 주장하지 않는다.

이 종료 경쟁은 [실제 정리 메서드 추출 시험](../../build/diagnostics/termux-omarchy-jdwp-cleanup-host-20261009-01/LegacyCleanupRaceTest.java)에서도 예상 RED(exit 1)로 재현했다. 후속 [공유 정리 coordinator](../../build/diagnostics/termux-omarchy-jdwp-cleanup-host-20261009-01/README.md)는 같은 정리 완료를 최대 1.5초 기다리고, 실패·시간 초과·중단을 비정상 종료로 표시하며 독립 2초 fallback을 둔다. 호스트 11개 시험과 새 관찰기 컴파일이 통과했다. 기기에서의 정리 검증이나 입력 문제 해결과는 구분하며 `cleanupCompleted=false`였던 기존 관찰기는 그대로 재사용하지 않는다.


사용자 스크롤 후 [필드만 읽는 상태 조회](../../build/diagnostics/termux-omarchy-trackpad-after-scroll-state-host-20261009-01/receipt.json)는 Java exit 0·10개 표본·목표 앱 정지 및 메서드 호출 없음으로 완료했다. capture·window/view focus·activity·키 서비스와 속도 배율 1.0은 유지됐지만 nested `SuppressCursorMovement=true`, `SwipeCompleted=true`, GestureDetector `StillDown=true`·이전 UP 없음이 남았다. 실제 APK에서 swipe 완료는 3개 이상 포인터가 임계값을 넘을 때 설정된다. 물리 두 손가락에 이전 접촉이 더해졌다는 가설과 맞지만, 접촉 ID와 전환 이벤트 관찰 전에는 원인으로 확정하지 않는다.



[유효한 접촉 ID의 호스트 재현 04](../../build/diagnostics/termux-omarchy-trackpad-lifecycle-host-20261009-01/attempt04/receipt.json)는 production 입력 라우팅·Swipe/Tap detector·Trackpad strategy를 포함한 6개 그룹·52개 이벤트를 확인했다. 정상 2→1 전환은 이동을 재개했고, 이전 접촉 ID가 남는 입력에서는 같은 억제·swipe 완료·StillDown·이전 UP 없음 상태가 재현됐다. Android GestureDetector·MotionEvent 등은 명시적 stub이며 OEM 입력 변환의 원인 확정이나 해결 검사가 아니다. 잘못된 ID가 있었던 03과 수정한 04의 입력·기록을 모두 보존했다.

[Android 기본 트랙패드 처리 3분 비교](../../build/diagnostics/termux-omarchy-trackpad-uncaptured-ab-device-20261009-01/receipt.json)는 `pointerCapture`만 false로 바꾼 뒤 원래 설정을 정확히 복구했다. [비교 중 필드 조회](../../build/diagnostics/termux-omarchy-trackpad-uncaptured-state-host-20261009-01/receipt.json)는 capture false·키 가로채기/키 서비스 true를 확인했다. [종료 후 조회](../../build/diagnostics/termux-omarchy-trackpad-uncaptured-ab-device-20261009-01/post-health.json)는 같은 frontend·Hyprland·Code·Chromium PID/birth와 남은 ADB forward 없음을 확인했다. 사용자는 “스크롤 뒤 멈추거나 이동하지 않음”을 보고했다. [물리 응답 기록](../../build/diagnostics/termux-omarchy-trackpad-uncaptured-ab-device-20261009-01/physical-report.json)처럼 응답은 자동 복구 후 도착했으며 실제 동작 시각은 미확인이다. 이 비교만으로 기본 경로의 효과를 확정하지 않고, 영구 적용하거나 해결 완료로 표시하지 않았다.



사용자 순서 시험과 겹친 [접촉 경계 관찰 02](../../build/diagnostics/termux-omarchy-trackpad-contact-boundary-breakpoint-host-20261009-02/receipt.json)는 Java exit 0·정리 확인으로 끝났다. 273개 breakpoint hit 중 128개 기록 제한에 도달해 수집한 4.748초이며 전체 물리 순서를 모두 기록했다고 표시하지 않는다. nested에는 억제 상태가 남은 한 접촉 MOVE 9개, 최종 UP, 새 DOWN 후 억제·swipe 상태 해제가 보였다. [동시 커널 조회](../../build/diagnostics/termux-omarchy-trackpad-kernel-slots-device-20261009-02/contact-boundary-count-poll.json)는 548개 표본의 접촉 0·1·2개를 확인했다. Java 시각은 MotionEvent 생성 시각이 아닌 호스트 수신 시각이며, 이벤트별 관찰 중간값 11.87ms·최대 54.41ms로 입력 대기가 생길 수 있어 Java/커널 수 차이를 잔류 접촉의 원인 증거로 사용하지 않는다.

[포인터 이동 조회](../../build/diagnostics/termux-omarchy-trackpad-contact-boundary-cursor-device-20261009-01/receipt.json)는 590개 표본 중 이동 변화 39회, 그중 breakpoint 정리 후 38회를 확인했고 자체 X11 연결 닫기·helper 회수를 마쳤다. 사용자도 이번에는 움직임이 돌아왔다고 보고했다. [관찰 종료 후 상태](../../build/diagnostics/termux-omarchy-trackpad-post-boundary-state-host-20261009-01/receipt.json)는 목표 앱 정지·메서드 호출 없이 capture·focus·키 서비스 true, 억제·swipe·StillDown false·이전 UP 있음으로 완료했다. [해석과 제한](../../build/diagnostics/termux-omarchy-trackpad-contact-boundary-breakpoint-host-20261009-02/analysis.json)처럼 APK나 영구 입력 설정을 바꾸어 해결한 것이 아니며, 이후 [관찰 없이 실제 반복 시험](../../build/diagnostics/termux-omarchy-trackpad-contact-boundary-breakpoint-host-20261009-02/observer-free-physical-report.json)에서 사용자는 “계속 정상 동작함”을 확인했다. 현재 세션의 이동·스크롤 복구 수락이며, 새 APK 설치에 따른 재발 방지나 장시간 안정성 수락은 아니다.


## 입력 상태 재발 방어 후보

[소스 차이](../../build/termux-x11-trackpad-lifecycle-20261009-01/source-review.patch)는 물리 touchpad·FINGER·TrackpadInputStrategy에만 적용한다. 감지기의 `onScroll` 호출이 생략돼도 한 접촉 MOVE에서 이동 억제만 해제하고, 최종 UP/CANCEL은 기존 strategy·감지기·버튼 전달 뒤 억제·swipe·drag 상태를 정리한다. 기존 onScroll·키보드·화면·클릭 구현은 유지한다. 커서 이동을 만들어내는 수정이 아니며 이번 정지의 모든 발생 원인을 확정한 것은 아니다.

[호스트 RED](../../build/diagnostics/termux-omarchy-trackpad-lifecycle-host-20261009-01/attempt05/red01/receipt.json)에서 의도한 네 사례가 실패했고, [최신 GREEN](../../build/diagnostics/termux-omarchy-trackpad-lifecycle-host-20261009-01/attempt06/green02/receipt.json)은 16개 그룹·93개 이벤트로 통과했다. 실제 production strategy를 통한 LEFT hold는 MOVE에서 유지하고 최종 UP에서 정확히 한 번 해제함을 확인했다. Android GestureDetector·MotionEvent·capture 변환은 명시적인 stub이므로 실기기 검증을 대신하지 않는다. 기존 strategy의 CANCEL held-button 해제 동작은 변경하지 않았다.

[서명 APK 검증](../../build/termux-x11-trackpad-lifecycle-20261009-01/artifact/receipt.json)은 새 경로 37개·기존 onScroll 18개·줌 10개가 통과했다. 다른 클래스 1,662개·기존 명령·분기·switch 목적지를 보존하고, [기존 GOTO 진입 RED→GREEN](../../build/termux-x11-trackpad-lifecycle-20261009-01/tests/branch-entry01/receipt.json)으로 guard 우회 방지를 확인했다. payload 493개 중 492개는 동일하며 `classes.dex`만 변경했다. 기존 package·version·signer와 정렬 검사를 통과했다.

[후보 APK](../../build/termux-x11-trackpad-lifecycle-20261009-01/artifact/LoopyOmarchy-TermuxX11-trackpad-lifecycle-candidate-20261009-01.apk)는 14,576,519바이트, SHA-256 `dd801ee0ae7132144b14a8af93f9bed834733cd8ea65fb070f3db75d0924dc24`다. [포장 검토](../../build/termux-x11-trackpad-lifecycle-20261009-01/package-review.json)의 상태는 `HOST_VALIDATED_NOT_INSTALLED_PHYSICAL_FIX_UNCONFIRMED`다. 해당 포장 기록은 설치 전 고정 상태다. 이후 새 저장·재시작 승인 후 [정상 종료](../../build/diagnostics/termux-omarchy-trackpad-lifecycle-stop-device-20261009-01/receipt.json)·[업데이트 설치](../../build/diagnostics/termux-omarchy-trackpad-lifecycle-install-device-20261009-01/receipt.json)를 완료해 설치 APK의 같은 SHA를 확인했다. 앱 제거·데이터 삭제·권한 일괄 부여는 없으며 native UID 10323을 유지했다. 기존 이전 세션의 사용자 수락을 새 APK의 수락으로 옮기지 않는다.

[새 시작 01](../../build/diagnostics/termux-omarchy-trackpad-lifecycle-start-device-20261009-01/receipt.json)은 세션 `a57f9028-0c31-4592-a074-0e0dc764eafa` ready·화면 1920×1280·배율 1.25·60 Hz·bar alpha 1·설정 오류 없음을 확인했지만 3초 시점의 background alpha 0으로 `FAILED`다. [읽기 전용 재확인](../../build/diagnostics/termux-omarchy-trackpad-lifecycle-start-recheck-device-20261009-01/receipt.json)에서는 같은 세션·Quickshell PID의 background/bar alpha 1을 확인해 `PASS`다. 개입 없는 후속 준비 확인이며 특정 애니메이션·이미지 로드가 원인이었다고 확정하지 않는다. 기존 native Activity 시작 오류 102를 우회해 shell 권한으로 Activity를 먼저 표시하고 native Runtime의 정상 start 진입점을 호출했으며 기본 CLI의 자동 Activity 시작이 해결됐다는 주장은 아니다. 런타임 파일·명령·입력 journal·개인 settings·EFAULT provider 수정·기본 SSH config·키보드·화면 preferences는 정상 종료 시의 새 baseline과 일치했다.

[앱 시작 검사](../../build/diagnostics/termux-omarchy-trackpad-lifecycle-apps-start-device-20261009-01/receipt.json)는 Chromium PID 26598(Xwayland)·Code PID 26628(native Wayland) 표시와 20초 관찰 중 같은 세션 유지를 확인했다. [필드만 읽는 상태 조회](../../build/diagnostics/termux-omarchy-trackpad-lifecycle-post-install-state-host-20261009-01/post-health.json)는 10개 표본의 focus·키 서비스 유지·제스처 차단 해제, Java exit 0·남은 ADB forward 0개로 끝났다. 새 세션에서 사용자 터치 전 실제 pointer capture는 false, preference는 true였으므로 preference만으로 실제 capture 활성화를 주장하지 않는다. 관찰 도구를 모두 종료한 뒤 반복 이동·두 손가락 스크롤 후 이동·딸깍 클릭·Alt+Tab 시험을 요청했다. [사용자의 실제 입력 확인](../../build/diagnostics/termux-omarchy-trackpad-lifecycle-install-device-20261009-01/physical-report.json)에서 “이동·스크롤·클릭·Alt+Tab 모두 정상”이라는 응답을 받아 최신 설치 APK의 해당 기능 수락을 완료했다. 별도 마우스 없이 반복 순서를 세 번 수행하도록 요청한 시험이며 계측 기록과 사용자 보고를 구분한다. 장시간·절전·회전·복귀 안정성, 물리 입력 지연·FPS 측정과 확대 재발의 수락으로 확대하지 않는다.

## CPU 관찰

종료 전 세션에서 공개 빈 Chromium 창을 켜 둔 10.059초 동안 프로세스별 CPU 시간을 관찰했다. 시스템 `/proc/stat` 및 일부 task/scheduler 정보는 Android 앱 권한에서 읽지 못하므로 전체 CPU 사용률·runqueue 대기는 UNKNOWN이다. 이 관찰에서는 권한이나 커널 설정을 바꾸지 않았다.

| 프로세스 종류 | CPU 시간 | 한 코어 대비 평균 |
| --- | ---: | ---: |
| native X server | 2610ms | 25.947% |
| native PRoot | 1320ms | 13.123% |
| native Weston | 580ms | 5.766% |
| Hyprland | 560ms | 5.567% |
| Chromium GPU | 10ms | 0.099% |
| Chromium utility | 10ms | 0.099% |
| Chromium main·renderer | 관찰 tick 차이 0 | 관찰 tick 차이 0 |

관찰 도구 자체 CPU는 810ms이며 Xlib 인증 helper 23개의 합산 CPU는 80.335ms다. helper는 모두 닫기·회수됐고 강제 종료는 없었다. 같은 세션·Chrome PID/birth를 유지했다. 관찰 overhead와 제한된 workload가 있으므로 입력 끊김 원인을 특정하거나 실제 클릭 지연·GPU 대기·60/144fps를 입증하는 자료로 쓰지 않는다.

[실제 CPU 관찰](../../build/diagnostics/termux-omarchy-chromium-scheduler-device-20261009-07/receipt.json). 앞선 03~06의 실패는 X socket 경로 가정, 정상 subreaper 입양, Android의 folded cmdline, 읽기 제한에 대한 관찰기 호환성 문제였다. 실패 자료는 보존하며 성공으로 덮어쓰지 않았다.

## 시작 안내·Caps 추가 확인

현재 사용 안내 문서에 시작·복귀·앱 실행·단축키·현재 설치본과 확인 범위를 모았다. 기본 Android Termux 터미널에서 `loopy-omarchy`로 시작한다. [Termux를 앞에 둔 실제 명령 검사](../../build/diagnostics/termux-omarchy-terminal-foreground-start-device-20261009-01/receipt.json)는 exit 0·동일 ready 세션·기존 앱과 설정 보존을 확인했다. 재부팅 후 새 시작을 추가 수락한 기록은 아니다.

[현재 KeyBridge 설정](../../build/diagnostics/termux-omarchy-keybridge-current-device-20261009-01/receipt.json)의 Caps 방향키·F13/F14와 Hyprland binding은 등록돼 있으나, [사용자 실제 시험](../../build/diagnostics/termux-omarchy-caps-check-device-20261009-01/physical-report.json)은 실패다. 확인 창에는 아래·위·오른쪽 각 1회와 예상 밖 32바이트가 도착했고 왼쪽·작업공간 전환은 0회였다. 원시 글자는 저장하지 않았다. 이 결과만으로 입력 중복을 원인으로 확정하지 않는다. 사용자 보고의 L 조합은 Android PIN·지문 잠금 화면을 열었으며 Meta/Alt 중 정확한 modifier는 아직 미확인이다. 확인 창은 정상 종료하고 기존 작업공간·focus를 복원했다.

[설치된 KeyBridge APK의 키 매핑 확인](../../build/diagnostics/termux-omarchy-keybridge-installed-apk-20261009-01/host-keymap-review.json)은 F13/F14 별칭이 Android 키 번호 183/184로 전송됨을 확인했다. 수정 전 X11 native 매핑에서 이 번호의 scanCode 0 입력은 F13/F14가 아니다. 이후 기존 KeyBridge 설정을 보존하는 artifact07 호환 APK를 설치해 조건에 맞는 가상 입력을 Linux evdev 183/184로 전달했다. 이는 키맵의 F13/F14 심볼 일치를 보장하지 않으며 후속 코드 바인딩에서 그 차이를 처리한다. 설치·호스트 검사를 물리 수락과 구분한다.

## VS Code 가속 비교의 확인 한계

[공개 프로필 비교](../../build/diagnostics/termux-omarchy-vscode-gpu-public-trial-device-20261009-01/receipt.json)는 현재 Code를 유지한 채 별도 공개 프로필에서 Wayland와 X11/ANGLE Vulkan을 순서대로 실행했다. 두 상태 명령 모두 exit 0이었지만 GPU 정보가 반환되지 않아 두 경로의 가속 판정은 실패다. 시험 자식을 회수하고 기존 Code PID·설정·창·세션을 보존했다. Chromium의 앞선 GPU 성공을 VS Code에 적용하거나 상태 명령의 exit 0을 가속 성공으로 해석하지 않는다. 실제 FPS와 입력 지연도 이 시험에서 측정하지 않았다.

## 남은 수락 범위

후속 GPU 조회 시험에서는 Linux 전체가 종료됐다. [안전 감사](../../build/diagnostics/termux-omarchy-gpu-trial-unexpected-exit-device-20261009-01/host-candidate-safety-audit.md)는 감시 임시 경로의 시험 프로필 누적과 일반 파일 258개 관측을 확인했다. 실제 운영 함수의 호스트 검사에서 256개는 허용하고 257·258개는 거부한다. Weston·PRoot의 SIGTERM은 남았지만 당시 저장 상태는 ready·오류 근거 없음이었다. 자원 제한으로 전체 retirement가 시작됐다는 경로와 실패 상태 저장의 크기 제한 문제는 코드에 존재하나, 최초 발생 오류를 확정한 기록은 없어 추정으로 남긴다. 두 시험 실행기는 기기 작업 전에 종료되도록 차단했고 가속 개선 성공으로 표시하지 않는다.

사용자의 새 저장·업데이트 승인 이후 [복구 02](../../build/diagnostics/termux-omarchy-gpu-trial-unexpected-exit-device-20261009-01/recovery-receipt02.json)는 죽은 세션의 파일과 상태를 별도 경로에 모두 보존했다. 원래 상태를 정상 종료로 고치거나 파일을 삭제하지 않았다. 남은 정확한 이전 PulseAudio PID만 종료했고, TERM 대기 실패 후 동일 PID/birth/command를 확인해 KILL했다. [Caps APK 설치](../../build/diagnostics/termux-omarchy-keybridge-handoff-install-device-20261009-01/receipt.json)는 `01c788af1397604aa8a9b8d1f215afcff7693eb5296d85740d686b714ac35049`를 데이터 삭제 없이 업데이트했다. 호스트 29사례·실제 helper DEX 연결·기존 클래스 1,663개 decoded-identical과 payload 492개 보존은 통과했지만, 당시 Caps·기존 입력의 새 APK 물리 수락은 대기 중이었다. 이후 방향키·트랙패드·Alt+Tab은 아래 실제 입력 재확인 02에서 수락됐으며 Caps+D/F는 후속 설정 적용 대상으로 남았다. Android 잠금 조합은 바꾸지 않았다.

[새 시작 02](../../build/diagnostics/termux-omarchy-keybridge-handoff-start-device-20261009-02/receipt.json)는 정상 Runtime 진입점에서 세션 `044bceeb-c5d3-4f59-97d8-a827143e9e02` ready·상단 바·배경·개인 설정과 화면/키보드 설정 보존을 확인했다. 시작 01은 출력 receipt의 줄바꿈과 기기 저장 receipt의 해시 차이로 실제 시작 전에 실패했으며, 원본 실패 기록을 보존했다. 새 시작은 그 차이를 기기의 실제 파일 해시로 확인한 뒤 진행했다. 기본 CLI의 백그라운드 Activity 오류 102가 해결됐다고 주장하지 않는다.

[앱 복구 확인](../../build/diagnostics/termux-omarchy-keybridge-handoff-apps-start-device-20261009-01/receipt.json)은 같은 새 세션에서 기존 프로필로 Chromium PID 15803(Xwayland)·Code PID 15828(native Wayland)를 다시 열었다. 두 앱의 창과 PID/birth를 20.984초 유지했고 런타임·개인 설정·입력/화면 preferences를 보존했다. GPU 비교 시험은 실행하지 않았다. 이어 새 Caps 확인 창 두 개를 준비했고, 후속 사용자 확인 02의 방향키·트랙패드·Alt+Tab 수락과 Caps+D/F 실패를 아래에 기록했다.

물리 키보드·마우스의 체감 끊김, 실제 화면 표시 FPS, 장시간 GPU 안정성, 절전·회전·복귀와 모든 Omarchy 앱·메뉴 동작은 별도다. 설치 APK의 최초 트랙패드 시험은 실패했지만 후속 상태 복구 뒤 관찰 없는 반복 이동·스크롤은 정상으로 수락됐다. 이전 입력 상태 재발 방어 APK(`dd801ee…`)에서는 관찰 없는 반복 이동·두 손가락 스크롤 후 이동·물리 클릭·Alt+Tab을 모두 정상으로 사용자 확인했다. 이 수락은 새 Caps 호환 APK의 물리 수락과 구분한다. 앞선 외장 마우스·합성 MOVE가 겹친 좌표 변화를 이 수락의 근거로 사용하지 않는다. 확대 보고의 원인도 미확정이다. 인터넷 단절·웹 종료는 조사 중이며, 자원 감시 수정이나 관찰 진단의 성공으로 해결됐다고 표시하지 않는다. VS Code는 개인 설정 수신·116개 등록/manifest·추가 설치 가능한 필수 누락 없음·테마 pin 해제를 확인했다. 사용자 제외 Java·공식 CLI에서 찾지 못한 6개·의도적 보류 5개는 유지한다. 33개 확장의 활성화 시도와 실제 기능 성공을 구분하며, 원격 편집·테마 표시와 renderer `EFAULT` 1회의 발생원은 별도 확인 대상이다. 추가 동기화 없이 현재 설치 결과를 유지한다. 루트 권한·systemd·직접 장치 제어가 필요한 upstream 기능은 Android 연결 기능 또는 원격 서버 대안이 필요하다. 설치·호스트 검사·짧은 창 표시와 전체 실사용 수락을 구분한다.


## Caps 호환 APK 실제 입력 재확인

[사용자 실제 확인 02](../../build/diagnostics/termux-omarchy-caps-check-device-20261009-02/physical-report.json)은 현재 APK `01c788af…`와 세션 `044bceeb…`에서 Caps+H/J/K/L 방향키, 트랙패드 이동·두 손가락 스크롤 후 이동·딸깍 클릭·Alt+Tab을 정상으로 수락했다. Caps+D/F 작업공간 전환은 실패했다. 확인 창 counts는 왼쪽 7·아래 5·위 4·오른쪽 8·예상 밖 입력 0이며 원시 글자는 기록하지 않았다. [정리 확인](../../build/diagnostics/termux-omarchy-caps-check-device-20261009-02/cleanup-receipt.json)은 두 확인 창의 정상 종료·파일 제거·원래 작업공간과 focus 복구를 확인했다. Caps+Shift 선택·Caps 단독 한/영 탭·Android 잠금 방지·장시간·지연/FPS는 이번 수락 범위에 없다.

## Caps+D/F 키 이름과 설정 적용 확인

[읽기 전용 키맵 조회](../../build/diagnostics/termux-omarchy-caps-df-audit-device-20261009-01/receipt.json)는 기존 Hyprland에 F13/F14 이름 바인딩만 있고, native X11의 키값 191/192는 각각 `0x1008ff81`(XF86Tools)·`0x1008ff45`(XF86Launch5)로 해석됨을 확인했다. F1/F12 대조군은 일치했고 자체 X 연결과 helper는 닫기·회수했다. native keymap 조회를 물리 Android 입력 관찰로 확대하지 않는다. 실제 Lua 프로필의 호스트 재현은 이 심볼에서 각각 바인딩 0개로 실패했으며 `code:191`/`code:192`로 교체한 뒤 네 사례가 통과했다. 이름 바인딩과 코드 바인딩을 함께 남겨 이중 전환하는 경우도 검사한다.

[설정 적용 01](../../build/diagnostics/termux-omarchy-caps-df-update-device-20261009-01/receipt.json)은 정상 개인 프로필 설치 API로 후보를 설치했지만 `reload-not-observed`로 실패했다. Lua 코드 바인딩이 `sMkKeys`에 저장되는 반면 현재 Hyprland JSON 목록은 그 값과 `displayKey`를 출력하지 않아, 확인 도구의 `keycode` 조건으로는 새 바인딩을 식별할 수 없었다. 원래 프로필을 같은 API로 복원·reload했고 기존 세션·앱·설정·focus 보존 검사를 통과했다. 실패를 성공으로 덮지 않았으며 [후속 읽기 전용 조회](../../build/diagnostics/termux-omarchy-caps-df-audit-device-20261009-02/receipt.json)도 원래 바인딩과 같은 세션을 확인했다. 후속 확인은 `displayKey`가 표시되는 일반 텍스트 목록의 해당 두 바인딩만 대조한다.

2026-10-10의 [설정 적용 02](../../build/diagnostics/termux-omarchy-caps-df-update-device-20261009-02/receipt.json)는 `PASS_APPLIED_RELOADED_PHYSICAL_TEST_PENDING`이다. 부모 검토·해시 고정 후 정상 개인 프로필 설치 API로 `bindings.lua`만 변경하고 인증된 Hyprland 연결에서 reload했다. 일반 텍스트 목록의 `code:191`/`code:192` 각각 한 등록, 기존 F13/F14 중복 없음, 설정 오류 없음을 확인했다. 다른 네 프로필 파일·모든 기존 창의 PID/birth·작업공간·focus·런타임·X11 preferences·Code와 Chromium 설정을 보존했다. 런타임과 앱 재시작·입력 주입·원시 입력 수집은 없었다.

[부모 parser 재현](../../build/diagnostics/termux-omarchy-caps-df-update-device-20261009-02/parent-host-parser-replay.json)은 실제 HyprCtl 직렬화 형식에서 14개를 통과했다. 실제 Lua 개인 프로필의 네 경우와 개인 프로필 검사 11개도 통과했다. 고정 setup08 패키징 검사 14개는 해당 압축 파일의 SHA와 이전 프로필을 검사하도록 구분했으며 최신 Caps 코드를 포함한 새 설치 묶음 검증은 아니다. [확인 창 03](../../build/diagnostics/termux-omarchy-caps-check-device-20261009-03/receipt.json)을 서로 다른 두 작업공간에 준비했다. [사용자 재시험 03](../../build/diagnostics/termux-omarchy-caps-check-device-20261009-03/physical-report.json)은 작업공간이 전환되지 않고 창이 바뀌는 것 같다는 보고로 실패다. 사용자는 Alt+방향키 설정도 언급했다. [정리](../../build/diagnostics/termux-omarchy-caps-check-device-20261009-03/cleanup-receipt.json)는 두 확인 프로그램의 deadline 종료·창 소멸·파일 제거·원래 작업공간과 focus 복구를 확인했다. counts 0은 전환 여부의 계측 근거가 아니며 사용자 실패 보고를 그대로 남긴다.

[Android 잠금의 host 검토](../../build/diagnostics/termux-omarchy-android-lock-host-20261010-01/report.md)는 AOSP Meta+L 정책·Lenovo Win+L 자료·공개 접근성 필터 계약을 대조했다. 기존 설치 KeyBridge APK 스냅샷과 두 DEX 해시를 재확인했으나 현재 기기를 다시 조회한 자료는 아니다. 검증된 Lenovo L 비활성화 설정은 찾지 못했다. 물리 Meta/Alt 구분·현재 접근성 콜백 도착과 소비 반환값은 미측정이며 절대 제어 불가나 해결 완료로 판정하지 않는다. 기기·APK·잠금 설정 변경은 없었다.

후속 사용자 응답은 Meta+L로 Android가 잠기며 Meta+Caps+H/J/K/L은 창 포커스 이동, Caps+D/F는 작업공간 전환이 목적임을 명확히 했다. Alt+방향키 작업공간 전환은 요청 범위에서 제외했고 Alt+Caps+H/L의 Home/End, K/J의 문서 처음·끝 이동을 추가 요청했다. 앞선 host 잠금 보고서의 modifier 미확인은 작성 당시의 범위이며, 콜백 도착과 소비 반환값은 여전히 미측정이다.

[실제 compositor API 검사 02](../../build/diagnostics/termux-omarchy-caps-real-dispatch-device-20261010-02/receipt.json)는 같은 설정의 `hl.dsp.focus({workspace="e+1"})`·`e-1`을 직접 실행해 실제 작업공간 ID `1→2→1`을 확인했다. 기존 앱의 PID/birth·창이 속한 작업공간을 보존했고 확인 창 포커스를 복원했다. 이는 Lua 전환 API의 성공이며 등록된 콜백 참조 실행·Android 키 전달·물리 Caps 수락은 아니다. [native X11 합성 입력 검사 03](../../build/diagnostics/termux-omarchy-caps-real-dispatch-device-20261010-03/receipt.json)은 Weston 포커스 소유권을 확인하지 못해 입력 전에 `SKIPPED`했다. 자체 X 연결과 helper를 닫기·회수했고 확인 창의 원래 포커스를 복원했다. 확인 창 04·05는 정리했다.

## Alt+Caps Home/End 이동 설정

[이동 설정 적용 01](../../build/diagnostics/termux-omarchy-navigation-update-device-20261010-01/receipt.json)은 `reload-not-observed`로 실패했고 같은 정상 설치 API로 기존 `a26499…` 프로필을 복원·reload했다. 복구 뒤 기존 앱의 PID/birth·작업공간·focus·보호 설정 보존을 확인했다. 실제 symbolic 키는 Lua parser의 `kb.key=lastKeyArg`에 저장되어 일반 텍스트 목록도 `LEFT`처럼 표시되는데, 확인 도구가 `ALT + LEFT`를 기대했다. modifier는 별도 `modmask=8`이다. 코드 키의 `displayKey` 대체 경로를 symbolic 키에도 적용한 관찰기 오류이며, 실행01과 실패·복구 기록은 보존한다. 프로필 동작을 성공으로 판정하지 않고 관찰기만 수정해 후속 적용한다.

[후속 감사 02](../../build/diagnostics/termux-omarchy-navigation-audit-device-20261010-02/receipt.json) 뒤 [적용 02](../../build/diagnostics/termux-omarchy-navigation-update-device-20261010-02/receipt.json)는 `PASS_APPLIED_RELOADED_PHYSICAL_TEST_PENDING`이다. 개인 binding SHA `1741cc7a…`를 정상 API로 적용하고 reload했으며 Alt+LEFT/RIGHT/UP/DOWN의 네 symbolic 키·modmask 8·고유 설명과 기존 Caps 코드 두 개 보존을 확인했다. 다른 binding·네 프로필 source·열린 앱 PID/birth·작업공간·focus·설정·런타임을 보존했고 앱 재시작은 없었다. 후속 [사용자 실제 확인](../../build/diagnostics/termux-omarchy-navigation-update-device-20261010-02/physical-report.json)에서 VS Code의 Alt+Caps+H/L 줄 처음·끝과 K/J 문서 처음·끝 네 조합 모두 정상으로 수락됐다.

## Caps+D/F의 Android 직접 입력 경로

Android 16 AOSP `InputDispatcher.notifyKey()`는 InputFilter를 호출하지만 `injectInputEvent()`의 키 경로는 정책 처리 뒤 큐에 직접 넣는다. 일반 InputManager 주입은 접근성 필터를 거치지 않는 코드 경로이며 `FLAG_SOFT_KEYBOARD=2` 자체가 원인은 아니다. 이는 upstream 근거로 Lenovo 기기의 실제 전달 성공과 구분한다. [InputDispatcher](https://android.googlesource.com/platform/frameworks/native/+/refs/heads/android16-release/services/inputflinger/dispatcher/InputDispatcher.cpp), [InputManagerService](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android16-release/services/core/java/com/android/server/input/InputManagerService.java).

보존된 실제 MainActivity DEX의 `lambda$onCreate$4`는 LorieView 키 listener에서 `TouchInputHandler.sendKeyEvent()`를 직접 호출한다. `MainActivity.handleKey()`도 이 listener로 위임하지만 현재 artifact07의 호환 helper는 KeyInterceptor 호출에만 연결되어 있어 직접 입력 경로에 없다. 따라서 접근성 stub 호출만 통과한 호스트 29사례는 직접 주입된 F13/F14의 전달을 보장하지 못한다. 공통 listener 앞에서 정확한 가상 183/184만 처리하고 나머지 기존 sender를 한 번 호출하는 수정 방향을 조사한다.

[합성 Android 시험 01](../../build/diagnostics/termux-omarchy-caps-android-pair-device-20261010-01/receipt.json)은 입력 전에 `android-main-activity-not-focused`로 중단했고 주입 0회·확인 창 포커스 복원을 확인했다. Android 16의 `dumpsys window windows` 출력에는 전역 `mCurrentFocus` 필드가 없어 확인 도구가 foreground를 판정하지 못했다. `dumpsys window`를 고정 enum으로 필터링한 후속 읽기에서는 Termux:X11을 확인했다. 이 실패를 입력 전달 시험의 RED로 해석하지 않는다.

[합성 시험 02](../../build/diagnostics/termux-omarchy-caps-android-pair-device-20261010-02/receipt.json)는 Android 184 DOWN/UP은 허용됐지만 완료 marker의 mode 666이 native 안전 읽기 조건에 걸려 관찰 전에 중단했다. `inputInjected=false`는 native marker 검사가 먼저 실패한 상태이며 실제 주입은 host `injections`에 기록되어 있다. 이 결과로 전환 실패를 판정하지 않는다. 후속 marker는 mode 600으로 원자적으로 완성되도록 수정했다.

[합성 시험 03](../../build/diagnostics/termux-omarchy-caps-android-pair-device-20261010-03/receipt.json)은 Android 184 DOWN/UP 허용·UP 확인 뒤 실제 활성 작업공간이 1에 남는 것을 관찰했다. 기대값 2와 달라 `synthetic-184-no-workspace-transition`로 실패했고 183은 보내지 않았다. 확인 창 포커스를 복구했으며 [확인 창 06 정리](../../build/diagnostics/termux-omarchy-caps-check-device-20261010-06/cleanup-receipt.json)에서 자체 창 정상 종료·파일 제거·기존 VS Code focus 복원을 확인했다. 코드 경로 누락과 실제 합성 실패를 확인했지만 아직 수정 APK를 설치하거나 물리 Caps+D/F를 수락한 결과는 아니다.

## 직접 입력 경로 수정 APK 후보

[후보 빌드 확인](../../build/termux-x11-keybridge-direct-input-20261010-01/artifact/receipt.json)은 SHA-256 `64ed17827121d6118bb001ce1bc85ba030d475a5f32f6f57a695d83abaa7fd71`, 14,576,519바이트다. 기존 APK는 직접 Activity listener의 호스트 시험에서 16개 통과·8개 실패였고, 수정 helper는 직접 입력 24개·기존 회귀 29개를 통과했다. 일반 이벤트는 원본 객체로 sender에 한 번 전달하며, 정확한 가상 183/184만 공통 legacy 처리로 연결한다. 두 경로가 같은 paired-UP 상태를 공유하고 공통 listener에서 `activity.handleKey()`를 재호출하지 않는다.

부모가 검토·고정한 소스로 빌드한 실제 DEX는 KeyInterceptor 호출과 MainActivity listener 호출의 두 곳만 같은 길이로 교체했다. 기존 다른 클래스 1,662개는 decoded-identical이며 바뀐 두 클래스도 그 두 호출 외의 코드·register·debug·try 정보를 보존했다. compiled helper 4개가 실제 APK와 일치하며 재귀 경로 없음·실제 API signature/public/static 일치를 확인했다. payload 493개 중 492개·native·manifest는 이전 설치본과 바이트 동일하고 signer·package·version도 같다. 이 빌드 receipt의 상태는 설치 전 호스트 확인으로 고정했으며 실제 기기 적용은 아래 설치 03으로 별도 기록한다.

[설치 절차 호스트 확인](../../build/diagnostics/termux-omarchy-direct-input-update-device-20261010-01/host-preflight.json)은 부모 검토·소스 해시 고정 뒤 새 저장 확인이 없으면 어떠한 subprocess/ADB 호출도 전에 중단함을 확인했다. 정상 CLI stop·종료 확인·`install -r`·같은 UID/marker/KeyBridge 설정 유지·정상 Runtime start·25초 bar/background 확인을 준비했다. 이후 사용자가 현재 작업 저장과 업데이트를 승인했다. [첫 실행의 점검 실패](../../build/diagnostics/termux-omarchy-direct-input-update-device-20261010-01/preflight-failure.json)는 KeyBridge가 non-debuggable 앱이라 private 설정을 `run-as`로 읽지 못해 기기 변경 전에 중단한 기록이다. Linux 종료·설치·재시작은 일어나지 않았다. 비공개 설정 접근을 우회하지 않고 설치된 KeyBridge APK의 공개 identity와 기존 opt-in marker 보존으로 후속 절차의 점검을 한정한다. APK identity는 현재 TOML 설정의 실시간 해시 확인을 대신하지 않으며 설정을 읽거나 편집했다는 주장을 하지 않는다.


[정상 종료 02](../../build/diagnostics/termux-omarchy-direct-input-update-device-20261010-02/stop-receipt.json)는 CLI exit 0이지만 응답이 `failed/cleanup-unconfirmed`여서 실패다. 설치와 새 시작을 실행하지 않았다. 런타임 상태는 `failed/cleanup-operation-failed`, cleanupEvidence는 `terminate/descendant-changed`다. [후속 프로세스 확인](../../build/diagnostics/termux-omarchy-direct-input-update-device-20261010-02/post-stop-process-health.json)은 기존 supervisor PID/birth가 유지되고 X11·오디오는 종료됐으며 Weston·PRoot·Android 연결·Hyprland는 해당 supervisor의 zombie 자식임을 확인했다. 최초 실패한 자식 PID나 변경 필드는 기록되지 않아 PID 재사용 등의 원인을 확정하지 않는다. 원본 구현이 보유한 supervisor의 명시적 정상 종료 재시도 경로를 사용하며 상태를 직접 성공으로 고치거나 광범위한 프로세스 종료를 하지 않는다.


[정상 종료 재시도 03](../../build/diagnostics/termux-omarchy-direct-input-update-device-20261010-03/stop-receipt.json)은 이전 실패 receipt와 보호 설정, 같은 supervisor PID/birth·실패 상태가 일치할 때 기존 CLI stop을 다시 호출했다. `stopped/terminationConfirmed=true`·관리 프로세스 종료·설정 보존을 확인해 PASS다. 수동 signal·상태 편집·실패 기록 덮어쓰기는 없었다. 이 재시도로 종료는 완료됐으나 최초 `descendant-changed`의 정확한 자식과 변경 필드는 여전히 미확정이다.

[설치 03](../../build/diagnostics/termux-omarchy-direct-input-update-device-20261010-03/install-receipt.json)은 후보 `64ed1782…`와 실제 설치 SHA 일치, 업데이트만 수행, 데이터·UID·marker 보존, KeyBridge 설치 APK identity 보존을 확인했다. KeyBridge의 현재 private TOML은 읽거나 편집하지 않았으며 marker는 이전 검토 설정의 정적 적용 기록이다. [정상 시작 03](../../build/diagnostics/termux-omarchy-direct-input-update-device-20261010-03/start-receipt.json)은 새 세션 `2e9eb6a1-c83f-466b-8bb5-f053c6f3fcc2` ready·bar/background 표시·설정 오류 없음·1920×1280·런타임과 개인 설정 및 입력 preferences 보존을 확인했다.


[기존 앱 복구](../../build/diagnostics/termux-omarchy-direct-input-apps-start-device-20261010-01/receipt.json)는 현재 새 세션에서 기존 Chromium 프로필의 Xwayland 창(PID 8724)과 Code native Wayland 창(PID 8758)을 열고 같은 PID/birth·창을 20.048초 유지했다. 프로필 디렉터리 inode, 런타임·개인 파일·입력/화면 preferences를 보존했고 새 공개 프로필·GPU 시험·추가 Sync는 실행하지 않았다.

[수정 후 Android 합성 입력 04](../../build/diagnostics/termux-omarchy-caps-android-pair-device-20261010-04/receipt.json)는 실제 설치 SHA `64ed1782…`와 새 세션·개인 binding·전경·자체 확인 창을 고정했다. 정확한 Android 가상 184·183의 DOWN/UP 허용·UP 확인 후, 실제 활성 작업공간과 자체 창 focus `1→2→1`을 관찰해 `PASS_SYNTHETIC_ANDROID_WORKSPACE_1_2_1`이다. 기존 사용자 창의 PID/birth·작업공간을 유지하고 자체 창 focus를 복구했다. 같은 03 시험의 이전 APK 실패와 구분하며, 합성 입력 성공을 물리 Caps 조합·트랙패드·지연/FPS의 수락으로 확대하지 않는다. 이후 확인 창 A/B에서 물리 Caps+F/D 및 Alt+Tab·스크롤 후 포인터 이동을 사용자에게 요청했다.


[현재 APK 물리 시험 07](../../build/diagnostics/termux-omarchy-caps-check-device-20261010-07/physical-report.json)은 사용자 응답 “Caps+D/F 작업공간 전환만 안 됨”으로 실패다. 같은 선택의 Alt+Tab·트랙패드 이동→스크롤→이동은 정상 수락이지만 물리 클릭을 다시 수락한 것으로 확대하지 않는다. 합성 입력 04의 통과를 실제 Caps 조합 성공으로 승격하지 않는다. [정리 07](../../build/diagnostics/termux-omarchy-caps-check-device-20261010-07/cleanup-receipt.json)은 자체 확인 프로그램의 deadline 종료·파일 제거·원래 작업공간/Code focus 복원을 확인했다.

## 현재 KeyBridge 설정과 물리 Caps 전달 관찰

[저장 설정 UI 읽기](../../build/diagnostics/termux-omarchy-keybridge-current-device-20261010-01/receipt.json)는 현재 설치된 KeyBridge 설정 편집 화면에서 저장된 TOML만 읽고, 필요한 Caps 매핑과 SHA만 남겼다. draft 표시가 없고 설정 SHA `628cc8736c1c09d0be7035f7e4a1aa8247984e3f1911ee9a1fc81d1e9e25ff5c`가 기존 private opt-in marker와 일치했다. Caps+D/F는 F13/F14, H/J/K/L은 방향키, 단독 탭은 language다. 설정 변경·저장·명시적 연결 버튼 사용은 없었고 UI에는 ADB 키 전송 연결됨이 표시됐다. 설정 화면을 여는 행위와 Linux 확인 창의 focus 복구는 있었으므로 완전히 무영향인 관찰로 주장하지 않는다.

[메타데이터 관찰 01](../../build/diagnostics/termux-omarchy-caps-key-metadata-observer-host-20261010-01/receipt.json)은 현재 공유 Termux 프로세스의 PID/birth·UID·설치 APK·전경을 고정하고 두 입력 함수 진입점에서 허용한 Caps/D/F/F13/F14 메타데이터만 읽었다. 물리 Caps는 Android 142/scan58이며 D/F와 함께 접근성 경로에 도착했다. 변환된 F13 10 DOWN/10 UP, F14 3 DOWN/3 UP은 Activity listener에 도착했고 모두 virtual·scan0·flags2·meta0·source257·repeat0·windowFocused=true였다. DOWN/UP 수는 균형이 맞지만 함수 반환값·native 전송 결과·compositor 전환은 이 도구가 기록하지 않았다. 각 이벤트의 디버그 처리 정지는 약 9~63ms이며 입력 지연 측정값으로 사용하지 않는다. 60.016초 뒤 cleanup confirmed·자체 forward 제거를 확인했고 관찰기는 종료됐다.

[확인 창 08의 관찰 중 사용자 응답](../../build/diagnostics/termux-omarchy-caps-check-device-20261010-08/physical-observer-report.json)은 “오 지금 다 잘되는데?? 머야 어케한거야??”다. 이 턴에 APK나 키맵을 바꾸지 않았으며 설정 UI 확인·새 확인 창 focus·디버거의 타이밍 영향 중 어느 것이 복구에 기여했는지는 미확정이다. 앞선 확인 창 07은 정리 시 deadline 종료였지만 사용자 시험 시각과 만료 시각의 선후는 알 수 없어 이전 실패를 만료 탓으로 단정하지 않는다. 관찰 종료 후 같은 A/B 창에서 Caps+D/F를 세 번 왕복하도록 별도 요청했다.

[설치 KeyBridge APK 비교](../../build/diagnostics/termux-omarchy-keybridge-reconnect-host-20261010-01/report.md)는 실제 설치 snapshot SHA `9ec3d986…`의 `SettingsActivity.onResume()`가 기본 `request=false`로 `Bridge.connect()`를 호출하는 경로를 확인했다. Shizuku 설정·ADB binder·권한이 준비되고 `connected=false`·`binding=false`일 때만 새 연결을 시도한다. 설정 화면을 열면 무조건 연결이 초기화된다거나 이번에 재연결이 실제 발생했다는 뜻은 아니다. 화면을 열기 전후의 live connection 전이는 관찰하지 않았다.

[관찰 종료 후 사용자 확인 08](../../build/diagnostics/termux-omarchy-caps-check-device-20261010-08/physical-report.json)은 Caps+F/D로 작업공간을 세 번 왕복하도록 요청한 뒤 받은 **“관찰 없이도 계속 정상”** 응답이다. 현재 APK `64ed1782…`·세션 `2e9eb6a1…`의 물리 Caps+D/F 전환을 수락한다. 왕복 횟수를 기계로 센 결과나 장시간·지연 측정은 아니며 추가 APK/키맵 변경도 없었다. [정리 08](../../build/diagnostics/termux-omarchy-caps-check-device-20261010-08/cleanup-receipt.json)은 자체 확인 창이 deadline으로 종료된 뒤 파일 제거·원래 작업공간·Code focus 복원을 확인했다. 방향키 counts 0은 작업공간 전환 성공/실패의 계측 근거가 아니고 사용자 수락을 대체하지 않는다. 최초 실패와 이후 복구의 원인은 미확정으로 남긴다.

## 현재 Y900의 Meta+L Android 잠금 단축키 차단

사용자가 Meta+L 잠금을 막도록 명시적으로 요청했다. [기기 읽기](../../build/diagnostics/termux-omarchy-android-lock-device-20261010-01/read-only-preflight.json)는 현재 기기가 Lenovo TB522FU·Android 16·사용자 0이며 `keyboard_combo_win_l` system row가 없음을 확인했다. 기존 다른 모델의 성공만으로 이 기기에도 적용된다고 판단하지 않았다.

[실제 펌웨어 snapshot](../../build/diagnostics/termux-omarchy-android-lock-device-20261010-01/firmware-snapshot.json)은 `/system/framework/services.jar`, SHA `d419950e2d77cb1dbfe56fdb053dabe832cc4291a767d850a00272378eb68bcc`·25,540,201 bytes다. [좁은 DEX 메서드 근거](../../build/diagnostics/termux-omarchy-android-lock-firmware-host-20261010-01/provenance.json)에서 `KeyboardSettingsObserver.updateKbComboWinLSwitch()`가 `Settings.System.getIntForUser("keyboard_combo_win_l", 1, USER_CURRENT)`로 읽고 1일 때만 `mKbComboWinLEnable=true`로 설정함을 확인했다. `KeyboardShortcutController.interceptSystemKeysAndShortcutsAfterQueueing()`는 해당 flag가 false이면 잠금용 `KEYCODE_POWER=26` 주입을 건너뛴다. ContentObserver를 통한 설정 갱신 경로도 있다. 이는 현재 펌웨어의 코드 근거이며 실제 콜백 실행이나 물리 키 수락과 구분한다.

[원본 백업](../../build/diagnostics/termux-omarchy-android-lock-device-20261010-01/setting-backup.json)을 먼저 남기고, 같은 serial·build·사용자 0·펌웨어 SHA·ready 세션·UID를 확인한 뒤 system 설정 한 항목만 0으로 바꿨다. [적용 receipt](../../build/diagnostics/termux-omarchy-android-lock-device-20261010-01/apply-receipt.json)는 0 재조회·runtime state 바이트 유지·같은 Termux PID·UID 10323을 확인해 `APPLIED_READBACK_VERIFIED_PHYSICAL_META_L_TEST_PENDING`이다. 앱 재시작·APK 설치·KeyBridge 설정 변경은 없고 Android 사용자 전체에 적용된다. 화면 잠금 보안이나 전원 버튼 잠금을 해제하는 설정이 아니다. 원래 없던 row이므로 원복 시 저장값 1이 아니라 해당 row 삭제가 원본 상태다.

별도의 Android 16 system gesture 처리에서 Meta+L 자체가 소비될 수 있어, 잠금 side effect 차단을 Linux 키 전달 성공으로 확대하지 않는다. Meta+L 뒤 PIN·지문 화면으로 넘어가지 않는지와 Meta+Caps+H/L의 기존 창 이동은 사용자에게 따로 확인을 요청했다. 재부팅 지속성·다른 Lenovo 빌드·다른 사용자·다른 Meta 조합은 이번 확인 범위가 아니다.

[후속 실제 키 확인](../../build/diagnostics/termux-omarchy-android-lock-device-20261010-01/physical-report.json)은 현재 설정 0·같은 APK/세션에서 사용자의 두 응답 **“잠기지 않고 Linux 화면 유지”**, **“창 이동도 정상”**을 기록했다. 물리 Meta+L의 Android 잠금 차단과 Meta+Caps+H/L의 Linux 창 포커스 이동을 각각 수락한다. 일반 Meta+L 자체가 Linux에 도착했다거나 Meta+Caps+J/K 등 다른 조합·재부팅 유지·장시간·지연까지 수락한 것은 아니다. 적용 receipt의 당시 pending 상태는 이 후속 수락 기록으로 보완하며 원본 기록은 덮어쓰지 않았다.
