# Firefox 콘텐츠 샌드박스와 PRoot SIGSYS 경계

확인일: 2026-10-06. 이 문서는 Android 일반 앱 UID에서 Linux Firefox ESR을
실행할 때 발견한 한 경계와 **별도 `run-as` 진단** 결과를 기록한다.
브라우저의 최종 앱 사용성이나 샌드박스 전체 보안성을 입증하지 않는다.

## 원인과 수정 범위

Firefox 콘텐츠 프로세스는 자체 seccomp 필터의 `SECCOMP_RET_TRAP`에 양수
태그를 넣고 SIGSYS 핸들러에서 호출을 판별한다. [Mozilla의 trap 구현](https://searchfox.org/mozilla-esr140/source/security/sandbox/chromium/sandbox/linux/seccomp-bpf/trap.cc)에서
태그는 1부터 할당한다. 고정된 [Termux PRoot `event.c`](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/patches/build-proot-android/build/proot/src/tracee/event.c)는
모든 seccomp SIGSYS를 자체 에뮬레이션으로 넘겼고, 낯선 `openat` 트랩은
guest 핸들러 없이 `ENOSYS`로 끝났다. 별도 원본 PRoot 프로브에서 이를 재현했다.

[수정 패치](../../native/proot-compat/0001-forward-tagged-sigsys.patch)는
태그 0인 Android 기본 필터의 기존 PRoot 에뮬레이션을 유지한다. 양수 태그는
저장한 원래 syscall 번호가 `siginfo.si_syscall`과 같고 PRoot 내부 호출 체인이
없을 때만 guest SIGSYS로 전달한다. ARM64에서는 결과 레지스터와 첫 인자
레지스터가 모두 `x0`이므로 원래 인자 1~6과 스택 포인터를 직접 복원한다.
레지스터 쓰기에 실패하거나 원래 호출을 확인할 수 없으면 종료해 잘못 번역된
호출 인자가 핸들러에 들어가지 않게 한다. 이미 syscall exit stop이 보고되어
`tracee->status == 0`이어도 저장된 원래 호출은 유효할 수 있으므로 그 상태만으로
거절하지 않는다. 핸들러가 없으면 원래 SIGSYS 기본 처분을 따른다.

`PROOT_NO_SECCOMP=1`은 PRoot 자신의 seccomp 가속 경로를 쓰지 않도록 하는
현재 런타임 설정이며 Firefox가 설치하는 필터를 끄지 않는다. 진단에서는
`PROOT_ASSUME_NEW_SECCOMP=1`도 유지했다. Firefox 샌드박스를 전역으로 끄는
환경변수는 이 패치나 제품 설정에 추가하지 않았다.

## 실측과 한계

[검증 자료](../validation/2026-10-06-proot-tagged-sigsys/receipt.json)는
원본과 수정본을 동일한 Android emulator-5580의 앱 UID `run-as` 경로에서
비교한다. `openat`의 guest 경로와 ARM64 첫 인자가 SIGSYS 핸들러에 보이는지,
핸들러가 없을 때 SIGSYS로 종료하는지, 태그 0 `statx`가 기존 PRoot 처리로
성공하는지 확인했다. 원본은 앞의 두 항목 실패·마지막 성공, 수정본은 세 항목
모두 성공했다. 이 테스트는 실제 Firefox 프로세스가 아니며 일반 앱 시작
경로에서 장시간 브라우징·페이지 렌더링·격리성을 확인하지 않는다.

수정 바이너리는 [고정 소스](https://github.com/localdesktop/localdesktop.github.io/tree/e6a8b580a3376e842cca2e44327a99498d7fb6dc/patches/build-proot-android)와
NDK 27.1.12297006으로 빌드했다. 위 `run-as` A/B 당시에는 Local Desktop의
원래 `libproot_loader.so`를 사용했고 세 항목이 통과했다. 그 진단은
`PTRACE_POKEDATA` 우회 경로를 강제하지 않았다. 이후 바이너리 감사에서 원래
loader의 `pokedata_workaround`는 시작점 +928바이트, 새 PRoot 빌드 영수증에
기록된 짝 loader의 같은 코드는 +1016바이트로 확인됐다. PRoot의
[`mem_prepare_after_execve`](https://github.com/localdesktop/localdesktop.github.io/blob/e6a8b580a3376e842cca2e44327a99498d7fb6dc/patches/build-proot-android/build/proot/src/tracee/mem.c)는
시작점에 빌드 시 계산한 오프셋을 더하므로 이 두 loader를 혼합하면 우회 코드
주소가 틀린다. 최종 APK에는 같은 빌드의 loader와 PRoot를 함께 넣어야 한다.

초기 진단 번들 `build/deliverables/LoopyDesktop-2026-10-06-proot-source.tar.gz`는
당시 원래 loader 사용 기록으로 보존한다. 짝 loader를 명시한 대응 소스·패치·
정적 talloc 재링크 재료는 별도
`build/deliverables/LoopyDesktop-2026-10-06-proot-source-paired.tar.gz`에 담았다.
원래 바이너리와 새 바이너리 어느 쪽도 동일 바이트 재현 빌드라고 주장하지 않는다.

## ARM64 레지스터 복원 추가 수정

[추가 A/B 영수증](../validation/2026-10-06-proot-register-return-o2fhz9b8/receipt.json)은
짝 loader를 사용한 최초 수정본에도 남아 있던 별도 결함을 재현했다. ARM64의
ptrace syscall stop은 `x7`에 임시 값을 표시한다. 최초 패치는 이전 syscall
stop의 캐시를 SIGSYS 정지점에서 전체 레지스터로 다시 써, 핸들러와 복귀 뒤의
`x7`이 원래 sentinel 대신 `1`이 됐다. `x6`와 `x19`는 그대로였다.
[Linux v6.1의 ARM64 ptrace 구현](https://github.com/torvalds/linux/blob/v6.1/arch/arm64/kernel/ptrace.c)은
이 임시 상태를 syscall stop 뒤에 되돌린다.

수정은 SIGSYS 정지점에서 `fetch_regs`로 실제 CURRENT를 다시 읽은 다음 원래
guest 인자와 SP만 복원한다. 같은 프로브에서 기존 세 항목과 `x6/x7/x19`
핸들러·복귀 sentinel 검사까지 **4/4** 통과했다. 이는 실제로 잘못된 레지스터
복원 경로가 수정된 증거다. Firefox 일반 창과 웹페이지의 최종 합격은 별도다.

현재 대응 소스는
`build/deliverables/LoopyDesktop-2026-10-06-proot-source-registers.tar.gz`다.
이전 두 번들은 그 당시 실패·수정 상태를 남긴 자료이며 현재 패치와 동일하지 않다.
