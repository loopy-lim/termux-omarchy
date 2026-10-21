# 현재 Omarchy 세션의 명시적 오디오 재시도

2026-10-08. 다음 구현을 위한 설계·실행 순서 초안이다. 이 문서 작성에서 제품 소스, 테스트, 빌드, 기기를 실행하거나 변경하지 않았다. 현재 Chromium/Notion 내부 창 작업과 별개이며, 기존 APK의 오디오 결과를 새 구현의 수락으로 사용하지 않는다.

## 목적과 현재 누락

Linux 앱과 Hyprland를 닫지 않고 **Linux 사운드 재개**로 소리 출력만 복구한다. 초기 Android 출력 실패, 출력 worker 종료, PipeWire 종료를 구분하며 한 번의 사용자 요청으로 한 번만 시도한다. 실패해도 원래 데스크톱을 유지하고 읽을 수 있는 상태와 재시도 버튼을 남긴다.

현재 근거:

- [OmarchyDesktopLaunch.java:121–134](../../../android/src/dev/loopy/desktop/OmarchyDesktopLaunch.java)은 AudioTrack 준비를 한 번만 시도하고, 실패하면 Linux 오디오 supervisor까지 생략한다.
- [DesktopAudioPlayer.java:80–82](../../../android/src/dev/loopy/desktop/DesktopAudioPlayer.java)은 살아 있는 출력 worker만 `resume-request`를 읽어 focus를 풀어 준다. 같은 파일의 96–109행에서 실패하면 worker와 AudioTrack이 종료되므로 후속 요청을 읽을 주체가 없다. `start()`는 매번 `mkfifo`를 호출하므로 같은 FIFO에 새 player를 붙일 수도 없다.
- [audio_services.py:119–127](../../../android/assets/omarchy-bridge/audio_services.py)은 Android 출력 또는 소유 서비스 실패 시 children을 종료하지만 다시 시작하지 않는다. `ready`도 실패 시 false로 갱신해야 한다.
- [DesktopAudioControl.java:17](../../../android/src/dev/loopy/desktop/DesktopAudioControl.java)과 [audio_control.py:16](../../../android/assets/omarchy-bridge/audio_control.py)은 현재 token·0700 디렉터리·0600 파일의 요청 채널을 이미 제공한다. 이 채널을 유지한다.

## 선택한 최소 구조

세션 소유 `DesktopAudioSession` 관리자 하나를 추가하고, 기존 `audio_services.py`에 오디오 자식만 다시 시작하는 작은 상태 기계를 넣는다. 전체 데스크톱 재시작은 미저장 작업을 잃으며, player만 재생성하면 초기 누락된 supervisor/PipeWire 실패를 복구하지 못하므로 사용하지 않는다.

| 소유자 | 책임과 경계 |
| --- | --- |
| `OmarchyDesktopLaunch` | 현재 token·audioDirectory로 관리자 하나를 시작/종료한다. 원래 Hyprland 명령을 한 번만 실행한다. AudioTrack 실패만으로 오디오 supervisor를 생략하지 않는다. |
| 새 `DesktopAudioSession` | `resume-request`의 **유일한 소비자**. 현재 세션 확인, 시도 직렬화, native player 수명, 고정 명령/상태 채널, UI 상태를 담당한다. player가 죽어도 관리자는 살아 있다. |
| `DesktopAudioPlayer` | 검증된 기존 FIFO에 붙어 PCM을 재생한다. `alive()`와 메모리상의 명시적 `requestResume()`만 노출한다. 요청 파일을 읽지 않는다. focus 변경은 계속 player worker가 수행한다. |
| `audio_services.py` | 자신이 생성한 PipeWire/WirePlumber/Pulse `Popen`들만 종료·wait·재시작한다. 원래 desktop `Popen`은 재시도 대상이 아니며 종료 코드를 보존한다. |
| `audio_control.py`/작은 GTK 상태 창 | 기존 token-only 요청을 게시하고 현재 고정 상태를 보여 준다. 파일 게시 성공을 복구 성공으로 표시하지 않는다. |

모듈은 각각 500줄 미만으로 유지한다. 관리자의 파일 codec/순수 상태 전이가 커지면 별도 작은 모듈로 분리한다. 새 임의 argv·경로·shell 명령 채널이나 외부 포트를 만들지 않는다.

## 상태와 세 가지 복구

상태는 `STARTING`, `READY`, `FOCUS_BLOCKED`, `OUTPUT_UNAVAILABLE`, `SERVICES_UNAVAILABLE`, `RECOVERING`, `CLOSED`로 제한한다. `READY`는 살아 있는 현재 native player와 현재 세대의 `loopy_android_sink` 준비를 모두 확인한 상태이며, 실제 청취 성공을 의미하지 않는다. UI는 원인별로 “Android 출력 준비 실패”, “Linux 소리 서비스 종료”, “다른 앱이 소리를 사용 중”을 표시한다. 세션 종료 후에는 재시도 버튼을 비활성화한다.

| 현재 상태 | 명시적 요청의 처리 |
| --- | --- |
| 출력과 서비스가 살아 있고 focus만 차단됨 | 같은 player worker에 `requestResume()`를 전달한다. PipeWire/AudioTrack을 재시작하지 않는다. Android의 focus 거부는 그대로 `FOCUS_BLOCKED`로 남는다. |
| 초기 AudioTrack 준비 실패 | 검증된 FIFO와 supervisor를 계속 유지한다. 요청 시 native player를 새로 준비하고 성공한 경우에만 Linux 서비스 시작을 지시한다. Hyprland PID·birth·socket은 유지한다. |
| native worker 실패 | 소유 Linux 오디오 자식의 quiesce/reap 확인 → 이전 native worker 종료/join 확인 → 같은 FIFO의 오래된 PCM 폐기 → 새 player 준비 → 새 서비스 시작 순서로 진행한다. 이전 worker가 종료되지 않으면 새 player를 만들지 않는다. |
| PipeWire 계열 자식 실패 | supervisor가 남은 소유 자식을 모두 회수한다. 살아 있는 native player를 유지하고, 명시적 요청에서만 새 서비스 세대를 시작한다. 요청이 허용한 focus 재개는 player worker에 전달한다. |

재시도 중 추가 요청은 합쳐 처리하고 병렬 시도를 만들지 않는다. 실패 뒤 타이머가 자동으로 다음 시도를 시작하지 않는다. 구조가 안전하지 않은 디렉터리/FIFO는 재시도하지 않고 오류로 남긴다. 앱 프로세스 자체의 사망은 현재 Linux 메모리를 보존할 수 없으므로 이 기능의 복구 대상이 아니다.

## 세션·FIFO·요청 계약

1. `DesktopAudioFiles`/관리자 준비 단계에서 FIFO를 **한 번만** 만든다. AudioTrack 초기화와 분리한다. player 재시도는 기존 FIFO에 붙으며 파일을 unlink/교체하지 않는다. 디렉터리는 실제 앱 UID·0700, `session`은 0600·최대65바이트·정확한 `token + newline`, FIFO는 UID·0600·FIFO 형식과 최초 기록한 device/inode를 요구한다. 경로 부모, 열린 descriptor와 읽기 전후 identity를 함께 확인한다.
2. 관리자는 닫힘 여부, launcher가 소유한 token/runtime, 현재 `DesktopSessionService`의 실행 중 token을 재시도 전후 확인한다. 새 세션이나 종료가 확인되면 이전 관리자는 입력·상태 게시를 중단한다. 준비 중인 후보 세션이 현재 세션의 오디오를 교체하지 않는다.
3. 공개 `resume-request`는 기존 token-only·65바이트 한도를 유지한다. 관리자가 원자적으로 소유 요청을 claim하고 nofollow descriptor의 UID/mode/content/inode를 확인한 뒤 그 claim만 삭제한다. 교체 경쟁이나 malformed/symlink 요청은 소비하지 않으며 다른 파일을 삭제하지 않는다. Python supervisor/player/GTK는 이 파일을 소비하지 않는다. 닫힌 runtime 디렉터리를 새 세션에서 재사용하지 않는다.
4. Java→Python은 새 전용 `service-command.json`, Python→Java는 `service-state.json`을 사용한다. schema1, 정확한 현재 session, 양의 증가 generation, 고정 `QUIESCE`/`START` 및 `STOPPED`/`STARTING`/`READY`/`UNAVAILABLE`만 허용한다. 각 파일은 일반 파일·0600·현재 UID·최대512바이트이며 unknown field와 잘못된 type을 거절한다. 원자적으로 게시하고 이전 generation/다른 token의 명령·ACK를 무시한다. generation은 관리자 수명 안에서만 증가하고 정리·새 세션을 넘어 재사용하지 않는다.
5. 관리자가 게시하는 `android-state.json`은 schema1/session/generation/state의 정확한 필드를 가진 0600·현재 UID·최대256바이트 일반 파일로 확장하고 `ready`/`unavailable`/`closed`만 허용한다. supervisor는 `QUIESCE`를 처리한 세대의 모든 소유 children을 실제 wait한 뒤에만 `STOPPED`를 게시한다. native failure 때 관리자에게 이 ACK가 필요하다. `START`는 같은 session/generation의 native ready와 FIFO identity를 확인한 뒤 처리한다. 고정 `pactl get-default-sink` 성공과 정확한 sink 이름을 확인한 뒤에만 `READY`를 게시한다. 기존 `state.json`의 `ready/running/reason`은 이 실제 상태와 일치시킨다.
6. 상태 파일의 유일한 Java 게시자는 관리자다. player의 늦은 callback/finally가 후속 세대의 `ready`를 덮어쓰지 않도록 현재 object/generation을 확인한다. 이전 worker join 후에만 새 player를 시작한다. 준비 상한은 native 2초, 서비스 5초, quiesce/join 3초 이내로 두고 전체 시도는 monotonic10초 상한으로 제한한다. 한도를 넘기면 실패 상태로 남기며 데스크톱을 종료하지 않는다.

## Focus·마이크·정리

- 요청이 없는 상태에서 지속 PCM이나 새 서비스가 Android focus를 다시 빼앗지 않는다. 영구 focus loss의 `PlaybackFocus` 차단을 유지한다. 사용자 요청 때만 `userResume()`를 적용하고, 실제 focus grant는 새 audible PCM에서 기존 방식대로 요청한다.
- 관리자는 Activity 대신 기존 started desktop Service/launcher 수명을 따른다. Activity pause, 다른 Android 앱으로 이동, ADB 분리만으로 종료하거나 재생성하지 않는다.
- 오디오 재시도는 `RECORD_AUDIO` 요청·grant·`AudioRecord` 생성·`microphone.authorize()`를 호출하지 않는다. 현재 마이크 거부/꺼짐은 유지한다. 기존 microphone binding을 출력 재시도마다 새로 만들지 않는다.
- 재시도로 PipeWire를 내려야 할 때 이미 활성화된 microphone은 현재 token에 한해 중지하고 종료를 확인한다. 자동으로 다시 녹음하지 않으며 별도 기존 consent UI로 다시 켠다. stop 요청의 activation을 보존해 새 `Endpoint`가 이전 start 요청을 자동 재생하지 못하게 한다. 초기 출력 실패 뒤 최초 binding이 필요하면 `off`인 객체만 준비하며 권한/녹음은 시작하지 않는다.
- 종료는 관리자를 먼저 닫아 새 요청을 차단하고, 마이크 중지·소유 오디오 자식 wait·native worker join/focus abandon/AudioTrack release를 마친다. 닫힘 중 늦은 ACK는 무시한다. 관리자가 생성한 임시/claim 파일만 identity를 확인해 정리한다. runtime 전체 삭제, 다른 세션의 FIFO·요청·프로필, 사용자 HOME·zsh/tmux/키보드 설정을 건드리지 않는다. 재시도에서 `session.close()`/Hyprland terminate를 호출하지 않는다.

## 테스트부터 진행할 구현 순서

1. 순수 관리자 전이와 가짜 player/service transport로 RED를 만든다. 초기 출력 실패, native worker 종료, PipeWire 실패, 살아 있는 focus-only 재개를 각각 분리한다. 원래 desktop 실행 횟수1, 같은 token/Hypr identity, 단일 request 소비·동시 요청 합치기, 요청 없는 자동 재시도0을 확인한다.
2. `DesktopAudioControl`의 claim/고정 codec과 기존 FIFO attach seam을 구현한다. stale token/generation, symlink·부모 교체·FIFO inode 변경·UID/mode 오류, 읽는 중 request 교체, 종료 직전 요청/늦은 callback/ACK를 거절하는 실제 파일 행동 검사를 붙인다. 이전 claim/외부 파일 보존도 검사한다.
3. `audio_services`를 작은 retry 상태 기계로 바꾼다. 실제 시험용 자식 3개와 계속 살아 있는 desktop fixture로 failure→quiesce/reap→explicit start→sink ready를 확인한다. desktop PID/exit code 보존, 자식 종료 실패 때 새 자식0, 초기 native unavailable 동안 desktop 생존을 확인한다.
4. Java 관리자를 launcher에 연결하고 player에서 request 파일 소비를 제거한다. fake native factory의 첫 생성 실패/worker 실패/join 실패를 재현한다. 최대 한 native worker, FIFO inode 유지, microphone factory/권한 호출0(거부 상태), 같은 playback focus 정책을 확인한다.
5. 기존 Linux 사운드 항목에 고정 상태 GTK 창과 재시도 버튼을 연결한다. 게시/ACK/실제 ready를 구별하고 stale/closed에서는 버튼을 막는다. 실제 source freeze → 관련 기존 회귀 → SDK APK 입력 검증을 진행한다.
6. root가 현재 APK·일반 앱 UID에서 전용 공개 PCM으로 각 실패/재시도를 시험한다. 같은 Hypr PID/birth/socket·사용자 설정/권한(특히 microphone denial)·입력 상태를 전후 확인하고 Android 출력 위치/전달 프레임 및 소유 프로세스 정리를 기록한다. 실제 청취·Bluetooth route·장시간 underrun·낮은 지연은 별도 수락이며 숫자 메타데이터 통과로 확대하지 않는다.

이 작업의 완료 조건은 세 실패 경로가 같은 데스크톱에서 명시적으로 복구되거나 정확한 현재 실패 상태를 남기고, focus·마이크 동의·소유 자원·사용자 데이터 경계를 유지하는 것이다. 본 초안은 그 구현이나 기기 수락을 완료했다고 주장하지 않는다.
