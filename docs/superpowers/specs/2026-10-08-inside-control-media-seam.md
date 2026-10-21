# 내부 Android 창의 제어·화면 전송 분리 seam

2026-10-08. **후속 구현을 위한 SOURCE 설계이며 구현·호스트 테스트·APK·기기·물리 입력 지연 수락이 아니다.** ROOT만 실행한다. 이 작업은 이 문서만 작성하고 오디오·브라우저·프로토콜·봉인 결과를 변경하지 않는다.

목표는 [첫 partial-writer 단계](2026-10-08-inside-frame-input-pacing.md) 이후에도 남는 **이미 시작한 FRAME payload 뒤의 click/key ACK 대기**를 제거하는 것이다. 인증된 두 FD, 기존 한 policy actor, 동일 FRAME/LIA codec을 쓰는 작은 다음 단계로 제한한다. lossless fidelity·native/GPU 전달·실제 최소60fps/목표144fps는 별도 전체 목표로 유지한다.

## 확인한 실제 경계

- `AndroidInsideAppHub.take()/ack()`는 현재 client socket을 한 개 dup해 Binder로 shell에 전달한다. GRANT는 Hub가 먼저 쓰며 shell UID/PID/birth/generation은 Binder에서 인증한다. Python의 `SO_PEERCRED` 상대는 **AppHub**이고 shell의 별도 `/proc` birth를 Python이 증명한 것으로 간주하지 않는다.
- `AndroidInsideShell.Connection`에 새 `AndroidInsidePacketWriter`와 `replySequence`/`sentFrame` partial 상태가 작성돼 있다. 이것은 작업 중 소스의 관찰이며 설치·검증 주장이 아니다. 입력을 적용해도 같은 socket의 active FRAME에 ACK를 삽입할 수 없다.
- `inside_wire.Decoder.feed()`는 전체 FRAME을 모은 뒤 inflate한다. `View.poll()`은 GTK에서 최대128×64KiB read, decode, `Session.receive()`, owned copy/Pixbuf, flush를 처리한다. FD만 나눠도 이 main-loop 작업을 그대로 두면 입력 callback 지연은 남는다.
- `Session`은 ACK 이후 다음 command를 보내고 FRAME geometry는 현재 epoch 또는 **inflight RESIZE**만 허용한다. split 뒤 RESIZE ACK가 이전 FRAME보다 먼저 오면 정상 이전 프레임도 `inside-frame-geometry`로 거부된다. `BrokerPolicy.releaseFrame()`은 이미 pending frame의 immutable 이전 geometry를 반환 대상으로 보존한다.

## 최소 선택: 새 v2 pair, resize/close barrier

v1의 endpoint·GRANT·HELLO caps127·OPEN/OPEN_ZLIB/OPEN_URL12·FRAME4/7·LIA1 bytes는 유지한다. 전역 caps에 새 비트를 더해 구 decoder를 깨뜨리지 않는다. 새 `loopy-inside-app-v2-<session>` endpoint와 **명시적인 version2 bootstrap**으로만 두 FD 모드를 선택한다. legacy endpoint와 실행 중인 창을 v2로 전환하거나 다른 task를 채택하지 않는다.

`connect_v2(token, window_nonce)`는 다음 단계가 모두 끝난 뒤 `ChannelPair`를 반환한다.

1. 기존 `LOOPY_ANDROID_PID`와 실제 current-session Hub UID/PID/birth, control FD의 socket type/dev/inode를 검증한다. bounded preface에 version2, 고정 mode `CONTROL_MEDIA`, 현재 window nonce만 전달한다. 임의 경로·URI·전체 환경을 handshake에 넣지 않는다.
2. Hub의 별도 `take2/ack2` 경로가 기존 Binder caller/grant admission을 그대로 적용한다. 승인된 pair 하나에만 media socketpair를 만들고, control의 GRANT2 bootstrap과 함께 **정확히 media client FD 한 개**를 SCM_RIGHTS로 보낸다. bootstrap은 기존 attested session/app/shell identity와 generation, window nonce, 일회 pair nonce, 고정 두 channel 역할을 묶는다.
3. Python은 처음부터 `recvmsg`로 bootstrap을 읽는다. partial data와 ancillary를 함께 유지하고, FD0/2개 이상·예상 밖 ancillary·`MSG_CTRUNC`·중복 FD·동일 control/media inode·비socket·다른 kernel peer를 거부한다. 받은 모든 FD를 실패 경로에서 닫으며 CLOEXEC/non-inheritable과 nonblocking을 설정한다. 일반 `recv()`로 먼저 읽어 ancillary를 유실하지 않는다.
4. shell은 Binder bundle의 정확한 v2 shape, 같은 grant/window/pair nonce와 두 FD identity를 확인하고 두 FD를 dup한 뒤 ACK한다. **socketpair의 kernel peer credentials는 생성한 Hub의 UID/PID다.** FD를 Python에 전달했다고 media peer가 원래 control client PID로 바뀌지 않는다. control은 기존 client UID/PID/birth admission의 authority이고, media는 Binder-attested Hub creator identity·pair nonce·FD identity로 같은 연결에 묶는다. media를 control의 peer 검사 함수에 그대로 넣거나 media peer를 별도 input authority로 쓰지 않는다. Hub는 ACK에서 자기 원본만 닫고 한 actor가 두 dup의 독점 소유자가 된다. 두 FD가 준비되지 않으면 display/task를 만들지 않는다.
5. control `HELLO2`와 media `MEDIA_HELLO2`가 같은 attested pair tuple을 증명해야 Session이 OPEN을 보낸다. 기존 required capabilities127과 compression/OPEN_URL semantics는 유지하고 mode/version 선택을 별도로 검사한다. version 미지원·handshake timeout·한 FD만 성공이면 unavailable이며 v1·외부 Android·다른 브라우저 자동 재실행은 하지 않는다.

FD 전달의 공식 seam은 [`ParcelFileDescriptor.createSocketPair()`](https://developer.android.com/reference/android/os/ParcelFileDescriptor#createSocketPair())와 [`LocalSocket.setFileDescriptorsForSend()`](https://developer.android.com/reference/android/net/LocalSocket#setFileDescriptorsForSend(java.io.FileDescriptor[]))이다. 후자는 다음 data write에 ancillary를 붙이므로 bootstrap writer를 한 번만 소유해야 한다. Python은 [`recvmsg()`/ancillary 계약](https://docs.python.org/3/library/socket.html#socket.socket.recvmsg)을 따른다. 이 API의 존재는 Android SELinux/PRoot에서 해당 pair가 동작했다는 증거가 아니며 ROOT의 실제 앱 UID→Binder shell 시험이 필요하다.

`SO_PEERCRED`의 socketpair 생성 시점 identity 계약은 [Linux UNIX socket 공식 매뉴얼](https://man7.org/linux/man-pages/man7/unix.7.html)에 따른다. 같은 UID라는 사실만으로 두 FD의 pair binding이나 client birth 검사를 생략하지 않는다.

## 하나의 actor와 두 writer

| 소유자 | 최소 계약 |
| --- | --- |
| shell Connection actor | 기존 admission, PM/TaskLease, before/after target UID·ordinary WindowId focus, actual injection, commit, capture, release/cleanup을 계속 독점한다. media worker가 이를 호출하지 않는다. |
| control partial writer | HELLO2·OPENED·ACK·ERROR·CLOSED만 보낸다. 하나의 active small packet과 하나의 command reply reservation만 가진다. FRAME payload를 허용하지 않는다. |
| media partial writer | MEDIA_HELLO2 뒤 FRAME4/7만 보낸다. active packet1/pending immutable frame1, 최대64KiB 한 attempt 후 actor에 반환한다. command/ACK를 허용하지 않는다. |
| actor scheduler | bounded control read/handle→control write→media 한 attempt→두 FD poll 순서다. media EAGAIN에도 control POLLIN/POLLOUT를 기다린다. control reply가 있으면 capture/codec보다 우선한다. |

각 writer는 같은 `AndroidInsideWire.responseHead()` encoder와 첫 단계 SendGuard를 재사용하되 **별도의 FD/offset/poison/deadline**을 가진다. 전체 연결 검사에는 두 FD와 하나의 grant/window/session/generation을 함께 검사한다. actor만 writer를 step하며 추가 Java 송신 thread를 만들지 않는다. 마지막 bytes와 full flush guard를 같은 step에서 완료한 뒤에만 `sentFrame`/reply 완료로 표시한다. partial failure 때 해당 stream에 ERROR를 이어 쓰지 않고 pair 전체를 retire한다.

`replySequence`는 actual control reply의 완료까지 유지한다. policy commit이 pending command를 비웠다고 다음 command/무제한 ACK queue를 허용하지 않는다. 기존 LIA는 이 reservation과 별개로 처리한다. key UP/repeat/button/scroll은 버리거나 합치지 않으며 기존 허용된 pointer-motion 합치기만 유지한다.

## geometry·frame·정리: 최소 barrier가 필요한 이유

일반 input/FOCUS/RELEASE_ALL의 ACK는 pending media FRAME과 관계없이 control로 보낸다. frame의 task/window/geometry는 이 작업으로 바뀌지 않으며 그 immutable snapshot만 정상 LIA의 반환 대상이다.

**RESIZE ACK와 CLOSED만 이전 pending FRAME의 완료·exact LIA retirement 뒤로 보류한다.** RESIZE의 actual input release/resize/commit은 한 actor에서 실행해도 control reply reservation을 유지하고 새 FRAME capture를 막는다. client는 여전히 inflight RESIZE 상태이므로 이전 geometry의 FRAME을 검증·복사·discard/LIA할 수 있다. actor는 해당 LIA 뒤 RESIZE ACK를 쓰고, 완료 뒤에만 새 epoch를 capture한다. 이 barrier를 없애려면 별도 FRAME_OFFER/permit protocol과 늦은 이전 epoch 수락 모델이 추가로 필요하므로 이 최소 단계에는 넣지 않는다.

normal close는 입력 quiesce→RELEASE_ALL/FOCUS_OFF ACK→CLOSE→현재 media packet 끝/반환→owned task/display/input cleanup 증명→CLOSED 순서다. GTK 창이 closing이어도 현재 frame을 끝까지 받아 **표시하지 않고** 반환한다. CLOSED는 두 decoder/worker의 pending frame이 없고 정리가 증명된 뒤에만 수락한다. 기존 send3초/release5초/close5초 예산을 이 분리에서 새로 시작하거나 늘리지 않는다.

media EOF·control EOF·peer/death·backend generation 변경·fd 교체·poison은 모두 pair 전체 실패다. 두 FD가 실제 shutdown/close되고 worker가 멈춘 뒤에만 `abandonFramesAfterDisconnect`를 허용한다. media만 닫혔거나 단순 SHUT_WR는 반환 증명이 아니다. 정상 CLOSED 없이 GTK가 종료된 경로를 cleanup PASS로 승격하지 않는다. pair 불확실 시 새 lease·task·FD를 자동 생성하지 않는다.

## Python/GTK seam

- 새 `inside_channels.py`는 `ChannelPair` bootstrap/두 FD identity/close만 담당한다. control decoder는4096byte bounded metadata만, media decoder는 HELLO2+정확한 FRAME4/7만 허용한다. 기존 v1 `Decoder`의 fallback 해석을 늘리지 않는다.
- 새 `inside_media.py`의 **단일 bounded reader/decode worker**가 media FD만 읽고 byte budget/stride/format/zlib 종료를 검증한다. Session/policy/input/GDK/Pixbuf를 만지지 않는다. ready immutable frame1과 진행 중 buffer1만 유지하며 pending frame이 GTK에 수락·반환되기 전 다음 frame을 읽거나 decode하지 않는다.
- `View`는 bounded control IO callback으로 ACK를 먼저 처리하고 즉시 `Session.output`을 control FD로 flush한다. callback마다 packet/monotonic 예산을 제한해 control spam이 GDK input을 굶기지 않게 한다. 기존128×64KiB media read/inflate를 이 callback에 넣지 않는다.
- media 완료는 connection generation+pair nonce를 고정한 idle callback 한 개로 GTK actor에 전달한다. actor만 기존 `Session.receive(FRAME)`·owned copy·Pixbuf·LIA를 수행한다. disconnect 뒤 callback은 폐기하고 새 세션에 재사용하지 않는다. normal close의 current frame은 drain/retire하며 fatal disconnect의 worker join/FD close는 bounded하고 GTK를 장시간 block하지 않는다.

`Session`의 one-command pacing, target/lease/epoch/focus/retirement 검사는 유지한다. control ACK와 media FRAME 처리 순서만 분리한다. GTK paint/copy, Java capture/compression, GIL/CPU 부하와 panel presentation은 이 seam만으로 사라지지 않으며 클릭/타이핑 전체 개선 또는60/144fps를 보장하지 않는다.

## 실행 가능한 다음 순서와 필수 RED

1. 기존 partial writer가 ROOT 검증을 마친 뒤, `AndroidInsideChannels`/`inside_channels`의 v2 bootstrap·FD ownership부터 독립 RED를 만든다. missing/extra/truncated ancillary, swap/duplicate/mismatched peer/window/session/birth/generation, ACK 전 죽음, FD leak, v1 golden compatibility를 확인한다.
2. actual two-writer scheduler에 막힌 큰 lossless FRAME fixture를 주고 KEY DOWN/UP·click의 actual apply와 **control ACK decode가 FRAME 완료 전에** 일어남을 확인한다. 같은 lease/focus/geometry guard와 command reservation을 유지하고 media와 ACK bytes가 섞이지 않아야 한다.
3. RESIZE ACK·CLOSED barrier, premature/stale LIA, pending-media EOF, poison, budget 만료, peer/owner death, held release 실패와 두 FD 정리를 검사한다. 새 GTK callback/worker의 late generation, frame bound·fidelity·중복 반환·timeout/close를 실제 원본 Session과 연결한다.
4. source freeze/호스트 GREEN/SDK 이후 ROOT가 current 앱 UID의 공개 fixture에서 input ingress→actual Android inject→control ACK→decode/copy/draw 지점을 metadata로 측정한다. 개선과 물리 input-to-photon·실제 presentation은 구분한다. 기존 Chrome/Notion task·사용자 config/역할/마이크 거부를 보존하고 normal CLOSED 및 pair cleanup을 확인한다.

모듈은 각각500줄 미만으로 분리한다. AppHub는 v2 wrapper, Shell은 actor 호출만 남기고 FD/bootstrap/transport를 작은 새 모듈로 옮긴다. 첫 partial-writer 또는 이 문서의 성공을 오디오 재시도·전체 Omarchy 지원 완료로 대체하지 않는다.
