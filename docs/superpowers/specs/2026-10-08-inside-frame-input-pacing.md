# Android 내부 앱 FRAME과 입력 처리 순서

## 목표와 증거 범위

실제 Android 앱을 같은 Hyprland Wayland 창 안에서 사용하면서, 큰 무손실 FRAME 전송 때문에 현재 lease의 입력 적용이 기다리는 구간을 줄인다. 첫 단계는 **single actor의 소유권을 유지하는 재개 가능한 partial response writer**다. 같은 응답 stream의 ACK 대기는 첫 단계 이후에도 남는다. 전체 목표인 fidelity-preserving native/GPU 전달과 물리 최소60fps·목표144fps는 아래 후속 gate로 보존한다.

이 문서는 SOURCE 설계다. 제품 코드·테스트·봉인 진단·설치 APK를 변경하지 않으며 실행·JDK/JVM·SDK·ADB·빌드·기기 작업은 ROOT만 수행한다. 진행 중인 초기 URL handoff와 Shell 편집을 겹치지 않는다. 구현은 별도 tests-first 승인 이후에 시작한다.

현재 d74의 [Google Chrome 시험08](../../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-08/receipt.json)과 [org Chromium 시험09](../../../build/diagnostics/y900-inside-chrome-canonical-trial-20261008-09/receipt.json)는 각각 준비 후20초 유지, decode/copy/source 선택, ERROR0, CLOSED와 소유 정리를 통과했다. FPS·일반 사이트·물리 입력 지연 수락은 아니다. Google 시험의 raw FRAME27은15,996,416 bytes이며 first_header_ns323686464616416→complete_receive_ns323687309021520, 차이는844.405104ms다. **한 프레임의 관찰값**이고 압축/원시 전송 전체의 분포나 물리 input-to-photon latency를 대신하지 않는다. 이전 실패 영수증은 그대로 유지한다.

## 실제 seam과 선택

조사 시점 소스는 다음과 같다. 이것은 설계 기준 bytes이며 미래 후보의 source closure나 설치본 전체 일치 증거는 아니다.

| 파일 | SHA256 | 현재 계약 |
| --- | --- | --- |
| `android/src/dev/loopy/desktop/AndroidInsideShell.java` | `a903e6e11b5f2bd9835b2074da5b4790258fe025c0d7b4d317f8fe5b8672d5ce` | Connection actor의 read→handle→capture→동기 response |
| `AndroidInsideWire.java` | `efdfe1e9f1fd63604550f51fa65741cbb948524ecd9d9df73765ee16d8218175` | 실제 LIR1 encoder와 whole-packet Writer |
| `AndroidInsideBrokerPolicy.java` | `0b591a7468108dac15ed2576d52050d92a9ccce281082484739a0d8a56a871cd` | command admission/commit, 한 pending frame, exact retirement |
| `AndroidInsideSendGuard.java` | `5bffb44ae2a40335f5e8f257d4c66b070ea5169e475cf49db6a591020a012a97` | 모든 attempt의 cheap 검사, packet start/end full 검사,8ms birth 재검사,3초 packet 예산 |

`Connection.run()`은 `read()`와 `handle()` 뒤 `display.pixels()`와 `AndroidInsideFrameDelivery.offer()`를 호출하고, `writer.response(outgoing)`이 끝나야 다음 client packet을 읽는다. FD는 O_NONBLOCK지만 OutputStream의 내부64KiB write/retry 반복은 전체 packet을 끝내기 전 반환하지 않는다. Wire의 Writer는 length/header/payload/flush를 하나의 동기 호출로 보낸다.

GTK `View.poll()`도 동일 main loop에서 최대128×64KiB 수신, Decoder의 축적·inflate, Session의 owned bytes 복사, GLib.Bytes/Pixbuf를 처리한 뒤 output을 flush한다. Session은 한 command ACK를 받은 뒤 다음 command를 보낸다. 따라서 server 송신과 GTK processing 모두 입력 대기에 기여할 수 있다. 현재 소스 사실만으로 기여율을 확정하지 않는다.

세 후보 중 첫 단계는 partial writer로 한정한다.

1. **Partial writer + 기존 한 stream:** wire bytes와 인증 경로를 유지하며 actor가 bulk 송신 사이 입력을 적용할 수 있다. ACK는 이미 시작한 FRAME 뒤에 대기한다.
2. **별도 인증 control/media 또는 frame FD:** input ACK도 큰 payload와 분리할 수 있지만 새 FD 수명·인증·프로토콜 협상이 필요하다. 첫 단계의 범위가 아니다.
3. **native decode/storage와 GPU buffer import:** Python/Cairo 비용과 대량 pixel 복사를 줄이는 전체 목표다. 실제 guest/parent GPU interop 검증 없이 첫 단계 성공으로 확대하지 않는다.

## 첫 단계 partial writer 계약

### Wire와 writer

기존 OPEN/OPEN_ZLIB, FRAME/FRAME_ZLIB, command/release 바이트와 caps를 그대로 유지한다. 초기 URL 작업에서 승인된 추가 action도 이 scheduling 변경으로 재정의하지 않는다. encoder를 다른 테스트/adapter에 복제하지 않는다.

미래 구현의 작은 interface는 `start(Message)`, `step()`, `pending()`, 완료된 packet identity 조회로 제한한다. 이름은 구현 시 결정하되 아래 동작을 고정한다.

- 실제 `AndroidInsideWire` encoder가 length/header를 생성한다. payload를 다시 전체 복사하지 않고 actor가 독점 소유한 immutable bytes를 packet 완료 또는 connection 종료까지 보관한다.
- prefix/header/payload의 정확한 offset을 유지한다. `step()`은 최대64KiB의 **한 write attempt**를 수행하고 actor로 돌아온다. 마지막 bytes가 성공하면 같은 step에서 full flush guard까지 완료한다. 마지막 write와 flush 사이에 client read를 넣어 실제 정상 client의 즉시 LIA를 premature release로 잘못 거부하지 않는다. EAGAIN/partial write/EINTR가 packet을 재시작하거나 새로운 length를 만들지 않는다.
- 매 실제 attempt마다 기존 `SendGuard.beforeAttempt`를 호출한다. cheap FD/fstat/SO_PEERCRED/stop 검사, full packet 시작·끝 검사와8ms birth 검사, clock rollback·3초 예산·IO failure poisoning은 유지한다. EAGAIN와 여러 actor turn이 예산을 새로 시작하지 않는다.
- packet 마지막 bytes 뒤의 full flush guard가 성공해야 완료다. OS write 성공이나 queued 상태만으로 ACK/FRAME 송신 완료를 표시하지 않는다.
- active packet의 bytes 사이에 다른 ACK/ERROR/CLOSED를 끼우지 않는다. partial 실패 후 새로운 JSON/LIR1 오류를 같은 stream에 이어 붙이지 않는다. poisoned writer는 전체 authenticated FD 종료와 owned cleanup으로 간다.
- legacy 동기 Writer의 기존 사용자 계약을 조용히 바꾸지 않는다. 새 partial adapter와 기존 Writer가 하나의 socket에서 동시에 write하지 못한다. actual encoder 재사용과 기존 round-trip 검사를 함께 유지한다.

### Connection actor

새 thread가 policy/input/display lease를 소유하지 않는다. 기존 actor 한 개가 client packet parsing, `policy.accept`, target/focus 전후 관찰, 실제 targeted injection, commit, capture와 retirement를 계속 순서대로 수행한다.

한 turn은 bounded client read/handle→가능한 control reply 선택→한 write attempt→필요한 poll 순서다. 송신이 막혀도 POLLIN을 같이 기다리며 입력을 읽을 수 있어야 한다. POLLOUT만 기다리는 내부 반복으로 되돌아가지 않는다. packet이 없을 때만 capture/compression을 시작한다. queued control reply가 있으면 새 FRAME보다 먼저 선택한다.

소유량은 active packet1개, pending FRAME1개, 아직 전달 완료되지 않은 command reply1개다. 기존 canonical Session의 one-command pacing을 유지한다. 악성 client가 ACK 전달 전에 다음 command를 보내도 commit이 policy.pending을 비운 것을 무제한 ACK queue 권한으로 해석하지 않는다. adapter는 reply 전달 완료까지 그 command reservation을 유지하고 추가 command를 OPERATION_PENDING으로 거부하며 connection을 fail closed한다. exact old frame release는 그 예약과 별개로 처리할 수 있다. EOF/peer death/backend STOP은 packet 또는 command reservation을 기다리지 않고 owned retirement를 시작한다.

`AndroidInsideInput.apply()`의 immutable lease/display/UID·ordinary WindowId focus 전후 검사,3인자 targetUID injection, held obligation 예약과 성공 이후 state 갱신은 그대로다. physical key UP·repeat·button·scroll 순서를 합치거나 버리지 않는다. frame 우선순위를 낮추는 것을 input authority를 낮추는 근거로 삼지 않는다.

### FRAME 수명·resize·close

capture와 codec 준비 후 **기존 fresh Witness.observe/checkPeer/geometry 검사**를 통과하고 `policy.offerFrame`이 성공해야 packet을 reserve한다. 부분 송신 중 신규 FRAME을 capture/acquire하지 않는다. 현재 `pixels(false)`의 no-acquire 계약도 유지한다.

LIA release는 전체 packet 송신 완료 뒤, exact pending lease/epoch/sequence에 대해서만 유효하다. partial FRAME 도중 미리 보낸 release를 받아 slot을 재사용하면 아직 전송 중인 payload가 바뀔 수 있으므로 거부한다. frame sequence와 payload가 active writer와 같은 snapshot이어야 한다.

첫 단계는 현재 release5초와 send3초 예산을 유지한다. release deadline 시작이 송신 시작 전이라는 사실을 기록하며, 전송과 반환을 분리한 deadline 정책 변경은 별도 증거/회귀/승인 대상으로 남긴다. actor의 input/관찰에 든 시간도 기존 packet 예산을 회피하지 않는다.

RESIZE·FOCUS_OFF·RELEASE_ALL은 정상 순번/authority를 통과하면 같은 actor에서 held input을 실제 retire할 수 있다. active FRAME은 이전 immutable geometry 그대로 끝내고 해당 control ACK는 그 뒤에 보낸다. 이후 FRAME은 새 ACK/epoch와 pending-frame retirement 조건을 모두 만족해야 한다. 기존 GTK pending-resize-frame replay 및 copied ACK 의미를 바꾸지 않는다.

정상 CLOSE는 실제 input/task/display/focus retirement 결과를 유지한다. active FRAME을 같은 예산 안에 끝내고 exact old LIA를 받은 경우에만 CLOSED를 순서대로 전송한다. socket death·stop·poisoning이면 전체 authenticated FD를 shut down/close한 뒤 local stream copy를 abandon할 수 있지만, 이를 성공 CLOSED나 borrowed GPU buffer 반환 증명으로 만들지 않는다. 불확실한 input/task/display/focus 정리는 quarantine에 남으며 observer와 자원 budget을 재사용하지 않는다.

## 첫 단계의 정확한 개선 범위

큰 FRAME이 부분 송신 중일 때 이미 client→server 방향으로 들어온 **현재 lease의 첫 input apply**는 전송 완료보다 먼저 수행할 수 있다. 같은 응답 stream의 ACK는 FRAME 뒤에 남으므로 다음 key·key UP·반복 명령이 canonical ACK pacing을 기다릴 수 있다. 빠른 입력 전체·물리 latency 개선 완료를 주장하지 않는다.

codec 준비와 capture도 actor를 동기적으로 점유한다.25ms codec 예산은 native call hard preemption이 아니다. 반복 task/focus Binder 관찰 및 GTK inflate/copy/draw의 비용도 첫 단계에 남는다. pixel format·색·해상도·alpha·density를 낮춰 성능 합격을 만들지 않는다.

## 실제 소스 회귀 harness

다음은 **설계된 테스트 seam**이며 테스트 파일을 작성하거나 실행하지 않았다. 단순 scheduling 모델이나 source 문자열 일치만으로 첫 단계 GREEN을 만들지 않는다.

1. **현재 동기 경로 behavioral RED:** actual Wire Writer와 actual Connection의 `run/read/handle` body를 사용한다. controlled OutputStream/Os adapter가 length/header 뒤 FRAME payload write를 barrier에서 멈춘 상태에서 exact current-lease input packet을 다른 방향으로 공급한다. 입력 apply ledger가 FRAME 마지막 bytes 허용 전에 갱신되는지를 확인한다. 현재 동기 writer는 이를 수행하지 못해야 한다. 실패 assertion 뒤 gate를 풀고 thread/retained cleanup을 반드시 종료한다. compile/API absence는 이 behavioral RED와 분리한다.
2. **partial module의 실제 bytes:** actual Protocol/Policy/Codec/Wire/SendGuard와 미래 PacketWriter를 compile한다. write 결과1byte/short/EAGAIN/EINTR/failed/clock rollback을 scripted adapter로 공급한다. 출력 전체가 기존 Writer의 FRAME4·FRAME7·control packet과 byte-identical하고 actual Reader가 동일 rows로 decode해야 한다. header/body offset·flush identity·poison·원래 deadline이 직접 검증된다.
3. **실제 actor chain GREEN:** 동일 actual Connection body가 packet을 부분 송신하면서 actual policy admission→input apply adapter→fresh commit을 실행해야 한다. FRAME 끝 이전 apply, FRAME 뒤 ACK, 이후 다른 command ACK 순서를 각각 ledger/actual Reader로 확인한다. 입력 operation은 test double이므로 Android injection/SELinux/physical 입력 증거가 아니다.
4. **must-fail 계약:** foreign UID/task/display/epoch/focus·stale sequence·unknown key, early LIA, 두 번째 queued ACK, FD/peer/birth 교체, writer error/deadline, EOF/STOP, close/resize 중 old FRAME/LIA, failed input retirement/failed task removal은 거부·정리 또는 quarantine를 유지해야 한다. 반대로 peer가 마지막 payload bytes를 받은 순간 LIA를 queue한 경우에는 마지막 write→full flush 완료→다음 read 순서로 정상 retirement를 받아야 한다. DOWN 성공 뒤 transport 실패에서도 정확한 UP retirement obligation을 잃지 않아야 한다.
5. **GTK 실제 Session 계약:** ACK-paced 다음 command와 resize FRAME-before-ACK replay가 기존 actual Decoder/Session에서 유지된다. wire FRAME count, owned copy/replay callback, source 선택, draw, presentation은 각각 분리한다. host test의 GTK/OS doubles를 실기기 GUI acceptance로 확대하지 않는다.

actual Shell 전체를 host Android stubs로 compile하거나, 기존 `test_inside_embedded_focus.py`처럼 정확히 한 signature의 실제 method body를 추출할 수 있다. 추출한다면 body를 test에 재작성하지 않고 현재 hash/signature/cardinality를 검증한다. AndroidDisplay·socket·clock·Binder만 doubles로 치환하고 무엇이 doubles인지 receipt에 명시한다. actual constructor/FD admission까지 검증했다고 주장하지 않는다. 모든 compile/test 실행은 ROOT가 수행한다.

기기 수락은 fresh candidate에서 동일 own public page·geometry·session/source pins로 한다. numeric packet begin/end/input read/apply/ACK·frame return을 구분하고, 동일 공개 패턴의 compressed와 raw fallback을 모두 포함한다. user 계정·페이지·키·URL·pixel·live token을 로그에 넣지 않는다. 기존132 설정·서비스·역할·user tasks·exact focus와 owned CLOSED/EOF 정리는 별도로 확인한다. current d74 단일 raw844ms와 비교만으로 물리 지연 개선이나 FPS를 판정하지 않는다.

## 후속 전체 목표

**Control/media 분리:** 기존 Binder 실제 UID2000/PID/birth/session/generation/accepted-grant authority 아래 연결된 추가 FD만 허용한다. arbitrary endpoint·TCP·default display fallback은 없다. FD pair를 같은 lease와 owner에 묶고 control actor만 input/task/focus/policy를 소유한다. media worker는 immutable accepted frame만 운반하며 operation ordering과 CLOSE/EOF에 양쪽 FD를 정확히 정리한다. 기존 v1/caps를 몰래 재해석하지 않고 explicit negotiation/fail-closed legacy 계약을 정의한 뒤 구현한다.

**Native decode/storage:** strict metadata와 bounded inflate를 actual native module에서 수행하고 owned latest frame1개만 GTK main loop에 전달한다. Session authority/geometry와 InputState·GTK ingress는 유지한다. shared-memory/FD라면 producer 재사용이 consumer storage/GPU upload 완료보다 앞서지 못한다. ACK는 복사 또는 실제 buffer 반환이며 presentation 증거가 아니다. Pixbuf/Cairo를 제거해도 Android CPU readback·socket·guest swap·parent SHM은 남는다고 보고한다.

**GPU buffer 전달:** ImageReader→AHardwareBuffer→실제 Linux EGL/DMA-BUF import→같은 Hyprland wl_surface→parent GPU composition까지 전체 연쇄가 필요하다. [AHB의 zero-copy 공유와 Android EGL import](https://developer.android.com/ndk/reference/group/a-hardware-buffer)는 공식 지원되지만 opaque gralloc handle을 Linux plane descriptor로 추측하지 않는다. [Linux EGL import](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_image_dma_buf_import.txt)는 실제 FD/fourcc/offset/pitch와 지원된 modifier/sync 계약이 필요하다. guest UID에서 exact vendor/driver/import/Wayland path가 동작하는지는 미검증이다.

[Image.getHardwareBuffer](https://developer.android.com/reference/android/media/Image#getHardwareBuffer())의 Image.close 이후 사용 금지, acquire/release fence와 GPU 사용 완료, resize epoch, bounded retained images/FD, close/death/unsupported cleanup을 설계한다. [ImageReader usage 조합](https://developer.android.com/reference/android/media/ImageReader#newInstance(int,%20int,%20int,%20int,%20long))은 PRIVATE+GPU_SAMPLED_IMAGE를 별도로 다루므로 현재 RGBA CPU reader에 GPU usage를 단순 OR하지 않는다. 실제 format/dataspace/alpha/stride/known public pixels를 검증하고 no-import 상태를 GPU 성공으로 표시하지 않는다. 검은/DRM 보호 화면·권한 차단을 우회하지 않는다.

현재 parent는 `native/wayland-host/src/server.rs`에서 wl_shm만 advertise하고, Hyprland SHM output은 `LoopyShmReadback.cpp`의 glReadPixels와 RGBA/BGRA 변환을 사용한다. 단순 Gtk.GLArea 교체는 이 끝단을 없애지 않는다. [timing11 GTK 분석](../../../build/diagnostics/y900-timing11-analysis-20261008-01/gtk-paint-paths.md)의 전체 receipt806 FAIL과 paint54.622ms 부분 관찰도 그대로 유지하며, GDK readback/EGL swap의 미확정 기여를 새로운 개선의 원인으로 단정하지 않는다.

최종 수락은 lossless known-pixel fidelity·정확한 input/task/window ownership·source-bound draw·actual presentation·연속 최소60fps/목표144fps·부하/전력/장시간·resize/focus/death 복구를 각각 증명한다. rAF·FRAME 수·Cairo callback·20초 생존을 physical presentation으로 대체하지 않는다. Linux 창 밖 Android overlay 또는 외부 앱 전환은 이 목표의 대안 수락이 아니다.
