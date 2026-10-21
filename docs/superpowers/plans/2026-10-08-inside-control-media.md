# Android 내부 창 control/media 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 같은 owned Wayland 창에서 큰 무손실 FRAME이 막혀 있어도 현재 lease의 click/key ACK와 다음 입력이 control FD로 진행되게 한다.

**Architecture:** 별도 v2 endpoint에서 명시적으로 협상한 control/media pair를 기존 Binder grant에 묶는다. 한 Shell actor가 정책·입력·task·focus와 두 partial writer를 독점하며, Python의 bounded media reader/decode worker는 GTK와 Session을 호출하지 않는다. RESIZE ACK와 CLOSED는 기존 FRAME의 완료와 exact LIA를 기다린다.

**Tech Stack:** Android API36 Java, LocalSocket/SCM_RIGHTS, ParcelFileDescriptor, existing Shizuku UID2000 UserService, Python socket/recvmsg/zlib, GTK3/GLib.

**Spec:** [control/media seam](../specs/2026-10-08-inside-control-media-seam.md), [first partial-writer 계약](../specs/2026-10-08-inside-frame-input-pacing.md).

## Global Constraints

- 이 파일은 SOURCE 계획이다. ROOT만 모든 Python/JVM/SDK/빌드/ADB/기기 실행을 수행한다. 아직 제품·테스트를 작성하지 않는다.
- 기존 v1 endpoint, LIG1/LIP1/LIA1/LIR1 bytes, caps127, OPEN/OPEN_ZLIB/OPEN_URL12, 프로필·user config·role·permission·현재 task를 보존한다. 이 작업은 NAVIGATE13을 추가하지 않는다.
- v2 실패 후 v1·외부 Android 앱·다른 browser를 자동 실행하지 않는다. v1은 명시적으로 선택한 별도 시도이며 기존 실행 창을 다른 transport로 전환하지 않는다.
- active control packet1, control reply reservation1, active media packet1, pending frame1을 유지한다. FRAME4/7의 해상도·색·stride·alpha·lossless bytes를 낮추지 않는다.
- 기존 send3초, frame-release5초, **Java actor retire 후 close2초**, Python GRANT/HELLO5초·open15초·command8초·View close5초를 유지한다. seam의 close5초는 GTK 예산이며 actor 예산을 바꾸지 않는다.
- actual Binder UID2000/PID/birth/session/generation, exact FD, PM/TaskLease, ordinary WindowId focus, targeted three-argument injection, before/after checks와 quarantine를 유지한다.
- 두 FD도 CPU pixel 전달이다. GPU/native import, 실제 presentation 최소60fps·목표144fps, 전체 Omarchy 완료를 대신하지 않는다. 모듈마다500줄 미만이다.

## 현재 호출 경로와 수정 경계

| 실제 source seam | 현재 동작 | 이번 변경 |
| --- | --- | --- |
| `AndroidInsideHostController.refresh/bind/invoke/beginStop/retireHub` | Hub 활성화→Shizuku bind→같은 source/build/owner/generation child→clean STOPPED 뒤 Hub 종료 | 기존 상태와 RPC 유지. Hub가 v1/v2 listener를 소유하고 quiesce/retire가 둘 다 포함하는지 회귀로 확인 |
| `AndroidInsideUserService.caller/beforeLaunch/start/Scope.binderDied` | actual app caller UID/PID/birth, installed source/build, owner death, monotonic generation | 제품 수정 대상이 아니다. pair 추가로 새 service/authority를 만들지 않음 |
| `AndroidInsideProvider.call` | 정확한 take/ack/focus/release_focus method·typed extras, actual shell Binder caller | take2/ack2의 별도 exact shape만 추가. focus/release_focus는 기존 grant token 사용 |
| `AndroidInsideAppHub.Hub.accept/sweep/close`, `Pending.check`, `take/ack` | app-UID socket 한 개, pending10초, grant5초, 전체 최대8, Hub original만 ACK에서 close | 새 endpoint와 작은 v2 queue/transfer owner. v1/v2가 같은 grant/focus budget을 공유 |
| `AndroidInsideShell.serve/ExternalProvider.call/Connection.run/handle/retire/stop` | 한 accepted FD dup, 한 actor·partial writer·replySequence·sentFrame | take2/ack2 선택, 두 FD owner, 두 writer scheduler. constructor/FD helpers를 새 모듈로 분리해 Shell을500줄 미만 유지 |
| `inside_wire.connect/socket_identity/check_peer/Decoder/Output/Retirement` | Hub actual kernel peer, single stream·whole frame decode, one copied LIA | 기존 API와 v1 Decoder는 유지. 새 pair bootstrap·role decoder가 shared metadata/command/release codec을 사용 |
| `inside_window.Session.receive/_advance`, `View.start/connected/poll/flush/disconnect/close/destroy` | ACK paced command, current/inflight resize geometry, GTK에서 decode/copy | pair gate, bounded control callback, media worker completion 전달과 양 FD cleanup |
| `OmarchySessionBridge.prepare` | fixed asset 목록과 content-addressed owned publishing | `inside_channels.py`, `inside_media.py`를 실제 asset 목록에 추가 |

현재 `AndroidInsideChannels`/`inside_channels` 모듈은 없다. 이름이 비슷한 기존 service를 Channel 구현으로 간주하지 않는다. `AndroidInsideHostRpc`와 `AndroidInsideSupervisor`의 READY/STOPPED 형식도 유지한다.

## 고정 v2 wire와 API 계약

새 endpoint는 `\0loopy-inside-app-v2-<session>`이다. endpoint별 v2 listener가 exact client preface를 먼저 읽고 queue에 넣는다. control과 media는 AF_UNIX/SOCK_STREAM이며, reliable socketpair의 추가 communication FD를 만들지 않는다.

| 순서 | 고정 bytes / 소유자 |
| --- | --- |
| client preface | `i32be(40) + u32be(0x4c494232 LIB2) + u8(2) + u8(mode=1) + u16be(32) + window ASCII32`; 정확히44byte. 임의 URI·path·환경 없음 |
| rights marker | Hub가 control에 `0x32` 한 byte와 **media client FD 한 개**를 SCM_RIGHTS로 한 번 전달 |
| GRANT2 | `i32be(body_len) + u32be(0x4c494732 LIG2) + u8(2) + u8(mode=1) + text(session<=64) + text(window32) + text(pair32) + i32(app_uid,app_pid,shell_uid=2000,shell_pid) + i64(shell_birth,generation,hub_birth,media_client_dev,media_client_ino,media_server_dev,media_server_ino)`; text는 기존 u16be length+ASCII, 전체<=512byte |
| control herald | `i32be(body_len) + u32be(0x4c494332 LIC2) + u8(2) + u8(mode=1) + u8(role=1) + GRANT2의 session부터 끝까지 동일 fields`,<=512byte. 그 뒤 실제 기존 LIR1 HELLO가 오는 것을 logical HELLO2로 처리 |
| media herald | `i32be(body_len) + u32be(0x4c494d32 LIM2) + u8(2) + u8(mode=1) + u8(role=2) + GRANT2의 session부터 끝까지 동일 fields`,<=512byte. 그 뒤 FRAME4/7만 허용 |
| 이후 | control에는 LIP1 command/LIA1 release 입력과 LIR1 OPENED/ACK/ERROR/CLOSED 응답. media에는 정확한 기존 LIR1 FRAME4/7. 한 channel에 다른 role의 packet이 오면 pair 실패 |

GRANT2는 server endpoint가 증명한 kernel app UID/PID에 묶는다. UID/PID/birth/generation/inode는 양수, dev는0이상이며 exact i32/i64 범위를 검증한다. Python은 shell birth를 독립 `/proc` proof라고 부르지 않으며 app-denied shell `/proc`를 읽지 않는다. Shell은 control의 실제 client UID/PID/birth를 유지하고 media의 SO_PEERCRED를 **Hub creator UID/PID/birth**와 검증한다. media peer가 FD 수신 Python PID로 변한다고 가정하지 않는다. FD dev/ino는 receiver-local control identity와 grant에 포함한 socketpair 양쪽 identity를 구분한다.

Python `inside_channels.connect(token, window, mode='v2') -> ChannelPair`는 GRANT2까지만 완료한다. `ChannelPair`는 `control`, `media`, `identity`, `binding`, `check()`, `close()`를 제공하며 `close()`는 두 FD를 idempotent shutdown/close한다. binding은 immutable session/window/pair/app/shell/generation/media identities다. `check()`는 control Hub peer와 두 fstat/socket identity를 검사한다. media 자체로 input authority를 생성하지 않는다.

`AndroidInsideChannels.Admitted`는 `controlSocket/controlFd`, `mediaSocket/mediaFd`, `binding`, `checkTransport()`, `checkFull()`, `stop()`를 소유한다. Shell의 Bundle은 정확히 `{control_fd, media_fd, grant_token, session, window, pair, app_uid, app_pid, hub_birth, shell_pid, shell_birth, generation, media_client_dev, media_client_ino, media_server_dev, media_server_ino}`로 한다. `take2` extras는 기존 take와 같고, `ack2`는 기존 ack extras에 typed `window`, `pair`만 더한다. granted pair의 shell·window·nonce·FD tuple이 모두 일치해야 ACK한다.

양 endpoint의 herald를 actor의 bounded bootstrap sender로 먼저 flush한 다음 control의 기존 LIR1 HELLO를 보낸다. display/task가 생기기 전이고 한 packet<=512byte이다. 정상 Session은 양 herald와 HELLO가 같은 tuple임을 확인하기 전 OPEN을 보내지 않는다. Shell도 이 준비 전 command를 admit하지 않는다. 기존 PacketWriter의 Message encoder를 arbitrary bootstrap encoder로 바꾸지 않는다.

### 실제 ancillary 송수신에서 놓치면 안 되는 점

현재 `AndroidInsideAppHub.write()`는 `Os.write`를 호출하므로 LocalSocket의 outbound ancillary queue를 소비하지 않는다. 새 sender는 별도 v2 accepted socket에 다음 좁은 코드를 사용하고, 성공/실패 모두 queue를 비운다.

```java
socket.setFileDescriptorsForSend(new FileDescriptor[]{mediaClient.getFileDescriptor()});
try { socket.getOutputStream().write(new byte[]{0x32}); }
finally { socket.setFileDescriptorsForSend(new FileDescriptor[0]); }
// 성공한 경우에만 기존 bounded Os.write loop로 GRANT2 metadata 전송.
```

accepted FD를 O_NONBLOCK로 두고 rights marker를 재시도하지 않는다. 1byte 성공은 전체 marker 성공이며, EAGAIN/예외/unknown 결과는 해당 pair를 retire한다. sender는 global Hub LOCK 밖에서 Pending와 Hub/session을 전후 확인하고, deadline 안의 단일 per-admission worker가 소유한다. peer를 기다리는 bounded poll은 metadata writer에서만 사용한다. v1/v2 waiting 수+`grants.pending()`+focus 수의 합계8을 넘지 않는다. PREPARING/PREPARED/ISSUED는 같은 grant를 한 번만 세고 각각 더해 중복 계산하지 않는다.

[Android16 AOSP LocalSocketImpl](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-16.0.0_r1/core/java/android/net/LocalSocketImpl.java)의 OutputStream과 [native sender](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-16.0.0_r1/core/jni/android_net_LocalSocketImpl.cpp)는 ancillary send 뒤 remainder를 plain send로 처리한다. 전체 metadata를 그 write 하나에 붙이면 partial failure 시 완료 offset이 Java에 돌아오지 않는다. 그래서 marker 한 byte와 metadata를 나누고 실패를 replay하지 않는다. [AOSP PFD socketpair](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-16.0.0_r1/core/java/android/os/ParcelFileDescriptor.java)는 public `createSocketPair()`의 AF_UNIX stream+CLOEXEC 경로를 확인하는 출처다. 이 소스는 태블릿의 vendor 구현/SELinux 성공 증명이 아니다.

Python은 처음 marker부터 `recvmsg(1, CMSG_SPACE(8*int_size), MSG_CMSG_CLOEXEC if available)`를 사용한다. 정확한 `0x32`, SCM_RIGHTS 한 cmsg·int FD 한 개, `MSG_CTRUNC/MSG_TRUNC` 없음이 필요하다. 먼저 SCM_RIGHTS 모든 완전 int를 collect하고, unknown/duplicate/misaligned ancillary·0/2개 이상·EOF·duplicate inode를 거부하기 전에 받은 FD를 모두 닫는다. wrapping은 `socket.socket(fileno=fd)` ownership 이전 한 번뿐이며 CLOEXEC/non-inheritable와 O_NONBLOCK를 명시한다. 이후 control bootstrap도 recvmsg로 ancillary 없음과 총<=512byte를 확인해 late rights를 유실하지 않는다. 준비 전체5초를 넘기지 않고 cancellation은 확보한 두 FD를 닫는다.

## Task 1: 현재 ACK HOL의 행동 RED를 먼저 봉인

**Files:** Create `tests/test_inside_control_media.py`, `tests/java/AndroidInsideControlMediaTests.java`; actual read-only inputs은 `tests/test_inside_frame_pacing.py`, `AndroidInsideFramePacingTests.java`, production `Connection`/Wire/Policy/Input/PacketWriter/SendGuard다.

**Interfaces:** 기존 fixture `Trial.partial/finished/close`, `Env.enqueue/permit/index`, 실제 nonblocking EAGAIN gate를 사용한다. 새 Class/API가 없어도 현재 source가 compile되어야 한다. OS/display/focus/injection은 doubles이고 실제 actor body는 signature/cardinality 검증 후 추출한다.

- [ ] 아래 새 검사를 기존 actual actor fixture에 추가한다. 첫 FRAME은 받아 exact LIA하고, 두 번째 raw FRAME payload32byte에서 gate를 닫는다. current focus ACK2 뒤 sequence3 KEY DOWN을 보낸다.

```java
static void awaitDecodedAck(Env env, long sequence, long millis) throws Exception {
    long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(millis);
    synchronized (env) {
        while (env.index(Type.ACK, sequence) < 0 && System.nanoTime() < deadline)
            env.wait(Math.max(1, Math.min(10, TimeUnit.NANOSECONDS.toMillis(deadline-System.nanoTime()))));
        check(env.index(Type.ACK, sequence) >= 0, "control ACK missing while media gate closed");
    }
}
try (Trial t = new Trial("key")) {
    t.partial(); t.env.enqueue(command(3, Action.KEY, true, 30, G));
    check(t.env.applied.await(500, TimeUnit.MILLISECONDS), "key apply missing");
    awaitDecodedAck(t.env, 3, 500); // test helper: Env messages의 실제 Reader ACK3를 bounded 대기
    check(t.env.frames == 1 && !t.env.gate, "ACK waited for FRAME completion");
} // finally는 gate 해제→exact actor stop/join→owned FD absence까지 확인
```

- [ ] ROOT: `python3 -B -m unittest tests.test_inside_control_media.ControlMediaTests.test_key_ack_completes_while_frame_gate_closed -v`. Expected RED는 actual apply 성공 이후 **ACK3 없음**이다. compile 실패·missing module·skip은 RED가 아니다. KEY UP/click DOWN/UP도 ACK completion으로 다음 packet을 enqueue하여 FRAME gate를 열기 전 actual balanced injection을 확인한다.
- [ ] current sources/hash, compile0/test1, assertion·finally cleanup을 불변 receipt로 봉인한 뒤에만 Task2 생산 구현을 승인한다. 기존 첫 단계의 `ACK 뒤 FRAME` assertion을 지워 GREEN을 만들지 않는다. v1 fixture는 계속 그 기존 순서를 검증한다.

## Task 2: v2 codec/FD owner와 실제 Hub admission

**Files:** Create `AndroidInsideChannelCodec.java`, `AndroidInsideChannels.java`, `AndroidInsidePairTransfer.java`, `android/assets/omarchy-bridge/inside_channels.py`; Modify `AndroidInsideAppHub.java`, `AndroidInsideProvider.java`; Test `tests/test_inside_channels.py`, `tests/java/AndroidInsideChannelsTests.java`, `tests/fixtures/inside_channels.json`.

**Interfaces:** codec가 preface/grant/herald의 위 exact byte schema를 encode/decode한다. PairTransfer는 Hub의 Pending/check/grants/focus를 소비하는 `prepare/admit/ack/expire/close` owner이며 display/task/input을 알지 못한다. `AndroidInsideChannels.Admitted`와 Python `ChannelPair`는 앞의 계약을 반환한다.

- [ ] valid shared bytes와 wrong version/role/window/pair/gen/app/shell/media-inode, missing/extra Bundle keys, actual wrong Binder UID/PID, expired ACK, peer birth change를 먼저 검사한다. 새 모듈 초기 API stub 준비가 필요하면 컴파일 준비를 별도로 기록하고 permissive decode/ownership baseline의 행동 refusal 실패를 ROOT가 확인한다.
- [ ] Python 실제 `socket.socketpair`/sendmsg/recvmsg로 fragmented preface/marker/grant,0/2 FD·truncated control·unexpected cmsg·same inode·regularfile·timeout/EOF/late ancillary를 전달한다. 실패 후 **시험이 소유한 exact fd numbers만** EBADF인지 확인한다. 프로세스 전체 fd inventory를 저장하지 않는다.
- [ ] Hub sender의 actual method body와 typed Provider dispatch를 host stubs로 compile한다. OutputStream writes에만 rights가 붙고 Os.write에는 붙지 않는 stub로 위 one-marker/finally-clear 계약을 검사한다. 실제 JNI/SELinux 증거는 Task6에서 따로 확보한다.
- [ ] v1 `take/ack` 및 packet bytes를 그대로 두고 v2 준비를 shared budget에 reserve한다. LOCK 안에서 reserve/check, LOCK 밖에서 bounded IO, 다시 LOCK에서 active/session/admitting/deadline/peer를 재검사한다. 실패·quiesce·ACK expiry는 모든 Hub-owned PFD/LocalSocket을 close하고 preparing count를 되돌린다.
- [ ] PairTransfer 상태는 WAITING→PREPARING→PREPARED→ISSUED→ACKED 또는 RETIRED로 고정한다. 첫 take2는 동일 authenticated Request/token으로 grant를 한 번 reserve하고 IO worker를 시작한 뒤 null을 반환한다. 후속 take2는 같은 shell PID/birth/generation의 PREPARED만 Bundle로 넘긴다. Request 교체·중복 poll이 새 grant/worker를 만들지 못한다. grant5초는 issue부터 유지하며 IO 완료/Bundle retrieval에서 재시작하지 않는다.
- [ ] 성공한 `ack2`도 **Hub original/parcel만 close**한다. 중복 FD endpoint에 shutdown을 호출하면 receiver dup도 끊기므로 ACK 경로에서 shutdown하지 않는다. 불확실한 IPC 결과를 ACK 성공으로 만들지 않는다.
- [ ] ROOT: `python3 -B -m unittest tests.test_inside_channels tests.test_inside_wire tests.test_android_inside_controller tests.test_android_inside_stop_retry -v`; actual Java tests는 harness가 compile/run한다. v1 positive/negative 결과가 함께 GREEN이어야 다음 단계로 간다.

## Task 3: 한 actor의 두 writer와 RESIZE/CLOSE barrier

**Files:** Modify `AndroidInsideShell.java`; Create `AndroidInsideConnection.java`(기존 Connection body를 ownership 단위로 이동), `AndroidInsidePairIO.java`, `AndroidInsideFocusProvider.java`; reuse unchanged `AndroidInsideWire.responseHead`, `AndroidInsidePacketWriter`, `AndroidInsideSendGuard`, `AndroidInsideBrokerPolicy`, `AndroidInsideFrameDelivery`; extend Task1 tests.

**Interfaces:** `PairIO`는 admitted pair와 두 writer, `readControl()`, `writeControlStep()`, `writeMediaStep()`, `poll()`, `stop()`만 소유한다. `Connection`만 policy/input/display/focus를 호출한다. pure scheduling copy를 테스트용으로 재작성하지 않는다.

새 top-level `AndroidInsideConnection(Context,String session,int appUid,BackendIdentity,AndroidInsideFocus,AndroidInsideChannels.Admitted,Host)`는 원래 actor를 이동한 것이다. `Host`는 `stopping()`, `claimWindow(String)`, `releaseWindow(String)`, `quarantine(AndroidInsideConnection)` 네 메서드만 제공해 Shell의 기존 set/stop owner를 유지한다. focus provider는 기존 exact authority/call body를 작은 `AndroidInsideFocusProvider.java`로 옮기며 새 caller 권한을 만들지 않는다. 이동 뒤 harness는 이 실제 source를 compile하고 test용 actor 모델을 만들지 않는다.

- [ ] `serve`의 현재 permit8·take/ack·ACK-before-thread 흐름에 take2/ack2를 별도 branch로 추가한다. v1/v2 waiting은 번갈아 검사하여 한 branch starvation을 막는다. response exact shape/두 dup/두 herald/ACK가 완성되기 전 task를 만들지 않는다. constructor/ACK/thread-start failure finally는 둘 다 닫는다.
- [ ] writer별 SendGuard와 byte offsets/poison을 유지한다. 매 media attempt의 fast/full check는 control의 actual client authority와 media Hub-creator identity·FD tuple을 함께 검사한다. kernel UID/PID·fstat는 매 attempt, full birth는 packet start/end·8ms를 유지한다. POLLERR/POLLNVAL/Os.poll exception은 두 writer를 poison하여 새 ERROR를 이어 쓰지 않는다.
- [ ] actor 순서는 bounded control read/handle→가능한 control reply start/step→media 한64KiB step→두 FD POLLIN/POLLOUT poll이다. 정상 media에서는 server가 client data를 기대하지 않으므로 incoming data·EOF는 pair 실패다. control 출력·예약이 있으면 capture/codec를 시작하지 않는다. normal input ACK 후 다음 command는 실제 reply flush 완료 뒤만 admit한다.
- [ ] `replySequence`는 queued/active control ACK 전체에 걸쳐 유지한다. `sentFrame`은 media의 마지막 write+full flush 뒤만 설정한다. LIA는 control에서 받되 exact pending frame==sentFrame이 필요하다. malicious early/duplicate/stale release는 pair를 retire한다.
- [ ] RESIZE commit 뒤 ACK를 `reply`에 보관하고 **policy.pendingFrame()!=null이면 보내지 않는다**. actor가 새 epoch를 capture하지 않으며 client는 inflight RESIZE로 old frame을 받아 discard/LIA한다. full media 완료·exact LIA 뒤 ACK를 보내고 reply reservation을 해제한다. generic input/FOCUS/RELEASE_ALL ACK에는 이 barrier를 적용하지 않는다.
- [ ] CLOSE는 기존 actual retire를 즉시 수행하되 media 완료와 LIA가 남으면 CLOSED를 보류한다. frame·send·close deadline을 turn마다 검사하며 EAGAIN/command/capture로 재시작하지 않는다. either FD death/STOP/poison은 active packet이나 ACK를 기다리지 않고 stop한다. **양 FD shutdown/close 뒤** local stream copy를 abandon한다. held input/task/display/focus 불확실은 기존 quarantine에 남는다.
- [ ] Task1 fixture를 descriptor별 separate byte ledger/Reader·EAGAIN gate로 확장해 v2 ACK3/UP4가 media FRAME2 완료 전 decode되는 GREEN을 확인한다. actual resize ACK는 LIA 전 없음/후 있음, CLOSED는 release 전 없음/후 clean, FD swap/Hub birth change·idle/partial poll failure·EOF·backend stop·input-UP 실패 quarantine를 검사한다.
- [ ] ROOT: `python3 -B -m unittest tests.test_inside_control_media tests.test_inside_frame_pacing tests.test_inside_send_guard tests.test_inside_open_url tests.test_inside_embedded_focus -v`. v1 golden bytes·one-stream ordering과 v2 latency assertion은 다른 test case다.

## Task 4: role decoder와 GTK 밖 bounded media worker

**Files:** Create `android/assets/omarchy-bridge/inside_media.py`; Modify `inside_channels.py`, `inside_window.py`; retain `inside_wire.py` v1 Decoder API; Create `tests/test_inside_media.py`, `tests/test_inside_pair_view.py`; extend `tests/test_inside_window.py`.

**Interfaces:** `ControlDecoder(binding).feed(data)->rows`는 control herald+LIR1 HELLO/OPENED/ACK/CLOSED/ERROR만, `MediaDecoder(binding).feed(data)->FRAME rows`는 media herald+FRAME4/7만 허용한다. shared `wire.metadata`, strict inflate helper, body layout을 재사용한다. legacy `Decoder.granted`를 임의로 true로 덮어 우회하지 않는다.

- [ ] 먼저 current actual GTK `View.poll` fixture에서 media raw payload gate가 닫힌 동안 ACK 수신→Session.inflight 해제→다음 command output flush가 진행되는 assertion을 만든다. baseline v1 actual Decoder는 incomplete FRAME 뒤 ACK를 내지 못해 행동 RED여야 한다. callback API absence는 따로 기록한다.
- [ ] `MediaReader(pair, view_generation, deliver, fail)`는 media FD/decoder만 읽는 단일 daemon worker다. `deliver(view_generation,binding,frame)`와 `fail(view_generation,binding,fixed_reason)`은 GTK idle를 한 번 enqueue하는 adapter다. read chunk<=65536, encoded body<=MAX_FRAME+4104, strict stride/format/zlib eof/tail을 유지한다. ready frame1과 decoder in-progress buffer1을 넘지 않고 ready frame을 GTK가 consume하기 전 다음 frame read/decode를 중지한다. input·Session·GLib.Bytes·Pixbuf·Gtk 호출은 worker 금지다.
- [ ] worker가 tuple-matching media herald를 확인하면 startup event를 전달한다. View는 control herald/HELLO와 media ready가 모두 일치할 때만 기존 Session에 normalized GRANT→HELLO를 한 번 전달한다. actual wire HELLO를 검증하지 않고 fabricated keys/caps로 OPEN하지 않는다. pre-open control message1개만 보관하며 다른 row/timeout은 fail closed한다.
- [ ] `View.poll_control`은 한 callback 최대16 packets/64KiB와 monotonic2ms soft budget으로 control만 decode하고 row마다 actual `Session.receive`→output flush한다. 함수 안 media inflate를 넣지 않는다. budget은 hard preemption/물리 지연 보장이 아니며 poll/input callback의 existing guards를 유지한다.
- [ ] media completion은 pair identity+View.generation을 캡처한 idle callback 한 개다. GTK만 `Session.receive(FRAME,copy_frame)`/owned copy/Pixbuf/LIA를 처리한다. frame 전달 전 control ready row를 우선 처리하고, generation·pair changed/dead callback은 폐기한다. 기존 current/inflight RESIZE geometry와 retirement state를 넓히지 않는다.
- [ ] normal closing 중 worker를 먼저 멈추지 않는다. current FRAME은 끝까지 받아 display=False로 copy/retire하고 control로 LIA를 보낸다. CLOSED는 worker가 보유한 ready frame·in-progress decoder buffer 없음과 exact Session cleanup을 모두 요구한다. fatal disconnect는 stop event→양 FD shutdown/close→worker exit 확인의 bounded asynchronous reaper로 처리한다. GTK에서 무한 join하지 않으며 reaper가 끝나기 전 같은 View retry를 열지 않는다.
- [ ] 실제 module + controlled worker/GLib adapter에서 fragmented raw/zlib·fidelity·cross-role packets·late callback·double delivery/return·copy exception·close during decode·partial EOF·timeout·reaper timeout을 검사한다. actual Session unchanged v1 resize replay/close/ACK tests를 유지한다.
- [ ] ROOT: `python3 -B -m unittest tests.test_inside_media tests.test_inside_pair_view tests.test_inside_window tests.test_inside_initial_geometry tests.test_inside_url_start tests.test_inside_frame_codec -v`. worker throughput/test time을 physical presentation으로 부르지 않는다.

## Task 5: 명시 transport 선택과 실제 배포 연결

**Files:** Modify `inside_window.py`, `OmarchySessionBridge.java`; tests `test_inside_launcher.py`, `test_inside_initial_geometry.py`, `test_android_build.py`; existing browser/catalog call sites는 signature compatibility만 확인한다.

**Interfaces:** `run(encoded, initial_url=None, transport='v1')`와 CLI `--transport {v1,v2}`를 제공한다. 초기 구현 default는 v1이고 ROOT의 v2 SDK/기기 gate 후에만 별도 default promotion으로 v2를 선택한다. browser `run(encoded)`/`run(encoded,initial_url=...)`를 바꾸지 않으며 explicit v1 retry는 기존 실패 owner의 retirement가 확인된 뒤 새 owned window 시도로만 가능하다.

- [ ] 선택한 transport가 한 endpoint만 connect하고 v2 refusal/timeout 뒤 connect_v1 호출0·external app 호출0인지 actual View.start/connected callback으로 검사한다. initial allocation/debounce/generation cancellation의 기존 tests를 양 mode에 적용한다.
- [ ] v2 listener 준비 실패는 그 endpoint만 unavailable로 두며 이미 준비된 v1 listener를 닫거나 Controller의 backend RUNNING을 v2 지원 증거로 바꾸지 않는다. 이 경우 take2는 null로 새 admission 없음을 응답하여 v1 실행 중인 child를 HOST_UNAVAILABLE 예외로 종료시키지 않는다. v2에서 OPEN을 한 번도 보내지 않은 초기 실패는 양 FD/worker 종료 뒤 명시 v1 새 시도가 가능하다. OPEN 송신 후의 uncertain failure는 기존 task cleanup 증거 없이 새 연결을 자동/수동으로 admit하지 않으며 native backend의 clean STOPPED→새 generation을 거친 explicit retry로 둔다.
- [ ] new Python assets를 `OmarchySessionBridge.prepare`의 실제 fixed list에 추가하여 owned content-addressed publisher에 포함한다. packaged assets/source/build receipt에 새 files가 실제 들어가는지 ROOT real SDK fixture로 검사한다. source 문자열·test import만으로 installed module admission을 주장하지 않는다.
- [ ] HostController/UserService/Provider의 stale session, owner death, permission revoke, build-version rotation, RPC stop retry, quiesce→child drained/cleanup→Hub close를 양 listener/pair로 확인한다. 새 권한·Shizuku request·외부 activity 자동전환을 추가하지 않는다.
- [ ] ROOT focused host GREEN→independent ownership/privacy review→source freeze→real SDK build→artifact exact bytes/hash closure 순서로 진행한다. 이전 receipt는 고치지 않는다. 이 계획은 commit/push를 요청하지 않는다.

## Task 6: ROOT 실기기 비교와 default promotion gate

**Files:** 새 immutable diagnostics source/receipts와 `docs/validation/2026-10-08-inside-control-media-current.md`만 ROOT가 추가한다. 기존 봉인 baseline/실패/preservation 영수증은 유지한다.

- [ ] update-only APK 설치 전 current source/build·config·services/role·task/focus를 다시 fence한다. 현재 Chrome/Notion owned smoke를 재사용하되 private 계정/URL/pixel/key를 로그에 저장하지 않는다. 사용자가 확인한 inside 경험을 전체 native/GPU 수락으로 확대하지 않는다.
- [ ] 먼저 실제 앱 UID Hub의 v2 rights marker→Python recvmsg→Binder take2→UID2000 두 dup→ack2→양 herald/HELLO→normal OPEN→CLOSED/양 FD cleanup을 공개 fixture로 증명한다. one-FD 실패·ACK 전 cancellation·app/service death는 display/task 미생성 또는 owned retirement를 확인한다. JNI/SELinux 실패면 v2 unavailable이며 권한 우회/자동 fallback하지 않는다.
- [ ] 같은 geometry·공개 lossless fixture로 v1/v2 raw와 compressed를 각각 비교한다. media payload gate 또는 자연 backpressure 동안 numeric input ingress/apply/control ACK decode/next input, frame begin/end/LIA/copy/draw를 분리해 측정한다. first ACK가 media 완료 전 왔다는 자료와 실제 다음 DOWN/UP balance가 필요하다.
- [ ] current resize old-FRAME/LIA/ACK barrier와 normal close, focus loss, EOF/STOP, reconnect/detach를 검증한다. config·서비스·역할·기존 user tasks 보존, cleanup와 current-focus return이 불확실하면 시험 전체 PASS를 내지 않는다.
- [ ] v2 연결·기능·preservation/cleanup을 통과한 exact candidate에서만 새 기본값 promotion을 별도 tests-first 변경으로 진행한다. 실패 후 v1 사용은 명시적 선택으로 남긴다. ACK HOL 제거는 이 gate의 합격 항목이며 GTK copy/GIL·capture/codec·physical input-to-photon·GPU/panel60/144fps는 남은 항목으로 계속 기록한다.

## 계획 자체 검토 결과

현재 exact methods/FD owner를 기준으로 negotiation→Hub/Provider→same actor→Python/GTK→packaging→실기기 순서를 닫았다. Task1은 새 API 없이 현재 실제 ACK HOL을 행동 RED로 증명한다. role/ancillary의 새 API stub은 준비 실패와 행동 RED를 구분한다. RESIZE와 CLOSE는 full old FRAME/LIA barrier이고 v1 bytes·OPEN_URL·service generation·권한/기존 설정을 재정의하지 않는다. 별도 GPU 계획과 오디오 retry RED는 이 작업으로 완료되지 않는다.
