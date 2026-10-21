# 내부 Chromium의 HTTP(S) URL 전달

상태: **설계만 작성됨. URL 시작·기존 창 handoff는 아직 구현·실기기 검증되지 않았다.** 사용자 요청의 Omarchy/Android 연결 범위 안에서 진행하며 추가 제품 승인 단계를 만들지 않는다. 생산 소스·테스트·APK·receipt는 이 문서 작업에서 변경하지 않는다.

## 목적과 보존 전제

일반 Chromium 호출의 HTTP(S) 링크 하나를 실제 Android `org.chromium.chrome`의 내부 Wayland 창에서 연다. 해당 브라우저의 현재 세션에 인증된 소유 창이 있으면 **그 창의 기존 연결과 task lease**에 전달한다. 소유 창이 없으면 URL을 최초 시작 Intent에 전달한다. 기존 사용자 창의 프로필·탭을 reset하거나 다른 Android 작업을 채택하지 않는다.

ROOT가 전달한 현재 설치 기준은 ae2와 사용자 task238/display51이다. 이 작업은 그 창을 이동·종료·재시작하거나 기기에서 조회하지 않았다. 현재 ae2의 창에는 새 URL handoff가 없으므로 나중에 작성할 registry에 그 task 번호를 넣어 채택할 수 없다. 구 창이 살아 있는 동안 새 구현의 안전한 결과는 명시적인 unavailable이다. 실행 중인 작업의 정리는 별도 현재 저장 확인/소유권 절차를 따른다.

## 읽은 현재 구현

- `browser_inside_route.component()`는 `/usr/bin/chromium` 단독 또는 Wayland flag 하나만 인정한다. `CHROME_USER_DATA_DIR`/`CHROME_CONFIG_HOME` override와 fresh catalog 부재는 원래 Linux 경로로 남긴다.
- `browser_launch.main()`이 이 선택을 수행한다. Linux 진단에 쓰는 `run(argv)` 자체는 내부 Android 경로로 바꾸지 않는다.
- `browser_desktop_launch.py`는 정확한 두 인자 `gtk-launch chromium.desktop`만 다룬다. 실제 Gio DesktopAppInfo commandline을 GLib로 파싱하고 stock 실행 토큰과 말단 `%u`/`%U` 하나만 인정한다. 현재 URL 추가 인자는 원래 gtk-launch로 전달된다.
- `inside_window.run()`은 매번 임의 application ID/window nonce를 만들고 `Gio.ApplicationFlags.NON_UNIQUE`를 사용한다. 현재 재사용용 public registry/URL listener는 없다.
- 실제 lease는 Python `Session.task`, Java connection별 policy와 `AndroidInsideTargetGuard.Ticket`에 있다. Shell의 `windows` set은 중복 nonce 방지이지 다른 연결의 task를 얻는 API가 아니다. `AndroidInsideAppHub`의 grant/focus maps도 URL registry가 아니다.
- `platform_action.web`는 파일 기반 별도 Android web 요청이며 현재 내부 창 lease와 연결되지 않는다. 이를 내부 URL 전달이나 인증된 재사용으로 설명하지 않는다.

현 소스에서 이미 정해진 번호는 OPEN1, OPEN_ZLIB11, FRAME4, FRAME_ZLIB7이며 VERSION1/HELLO capabilities127을 유지한다. lossless 소스가 존재한다는 사실과 설치된 ae2에서 동작한다는 증거는 구분한다.

## 제안 API와 호환성

새 타입으로만 URL을 확장하고 원래 OPEN/OPEN_ZLIB/FRAME의 바이트를 변경하지 않는다. 아래 12/13은 **이 설계의 예약 후보**, 현재 구현된 action이 아니다.

| 요청 | 후보 wire | 자원 | 추가 데이터 |
| --- | --- | --- | --- |
| OPEN / OPEN_ZLIB | 기존 1 / 11 | task/display=0 | 기존 그대로 |
| OPEN_URL | 새 12 | task/display=0 | compact byte(0/1), URI length(u16)+ASCII bytes |
| NAVIGATE_URL | 새 13 | 기존 양수 task/display | URI length(u16)+ASCII bytes |

- `inside_window.run(encoded, initial_url=None)` 및 Session의 선택적 initial URL로 기존 호출을 보존한다. URI와 compact 선택은 한 연결의 최초 시작 요청에서 고정한다. 일반 앱에는 URL action을 허용하지 않고 정확한 `org.chromium.chrome/com.google.android.apps.chrome.Main` alias만 허용한다.
- 새 NAVIGATE_URL은 open action이 아니다. READY→OPENING이나 ticket claim을 호출하지 않고 ACTIVE의 현재 lease에만 적용한다. 화면 압축 선택도 바꾸지 않는다.
- 기존 클라이언트와 구 OPEN packets는 새 broker에서도 같다. 구 broker의 unknown action 거부는 display/task 생성 전 실패로 끝낸다. OPEN 재시도, URL 없는 실행, Android 외부 브라우저 또는 Linux 두 번째 실행으로 우회하지 않는다.
- HELLO127을 전역 255 등으로 바꾸지 않는다. 현재 decoder는 정확히127을 요구한다. 새 URI 지원 확인이 필요하면 별도 버전 negotiation 설계가 필요하며 이 최소 확장의 성공을 capability127만으로 추정하지 않는다.
- 기존 ERROR/ACK/OPENED/CLOSED 형식은 유지한다. NAVIGATE ACK는 Android 전달과 같은 lease/focus의 재확인만 뜻한다. 웹 페이지 로딩 성공을 뜻하지 않는다.

## argv와 URI 계약

공통 순수 parser는 empty call 또는 `/usr/bin/chromium` + 선택적 **단일** `--ozone-platform=wayland` + **단일** HTTP(S) URI만 선택한다. 선택적 Wayland flag는 URL 앞에 둔 정해진 두 형태를 지원한다. 임의 순서 재배열이나 옵션 추론은 하지 않는다.

- custom executable/flags, private/incognito, profile/user-data-dir, 중복 flag, 다중 URL, profile 환경 override는 원래 literal argv를 보존한다. 기존 x11 rejection64도 유지한다. `browser_state.plan()`을 우회하지 않는다.
- Desktop 경로는 정확한 gtk-launch 프로그램+`chromium.desktop`+URL 하나일 때만 추가로 후보가 된다. fresh Gio commandline이 stock base argv와 말단 `%u`/`%U` 정확히 하나를 가진 경우에만 그 필드에 URL 하나를 대입한 것과 동등하게 선택한다. field code 없는/custom/모호한 entry와 다른 인자는 원래 execvp로 남긴다. shell 실행, desktop/MIME/default-browser/config 쓰기는 없다.
- URI는 한 문자열의 **1..2048 ASCII bytes**인 serialized URI다. client와 Java에서 같은 test vectors를 검증한다. `http`/`https` hierarchical URI, 비어 있지 않은 host, 존재하면 port1..65535, 정상 percent triplet을 요구한다. localhost와 정상 IPv4/IPv6 URI도 공개 fixture를 위해 지원한다.
- userinfo, NUL/제어/공백/DEL, 역슬래시, invalid percent encoding, opaque/상대 URI, `intent:`/`file:`/`content:`/`javascript:` 등은 거부한다. Unicode/IDN은 최초 범위에서 변환하지 않고 해당 원래 Linux 경로를 유지한다. 검증을 위해 parse하되 승인된 ASCII 원문을 trim/normalize/unquote/재작성하지 않는다.
- URI는 메모리와 인증된 bounded IPC에만 둔다. registry, config, argv용 새 파일, title, 로그, exception message, receipt에 URI를 저장하지 않는다. 기존 `platform_action.web`의 다른 contract를 그대로 재사용해 내부 action으로 취급하지 않는다.

## 소유 창 handoff: nonce를 유지하는 방식 선택

GTK unique application + HANDLES_COMMAND_LINE은 Linux session bus를 통해 기존 primary에 인자를 전달할 수 있다. 그러나 현재 ID는 임의 nonce이고 NON_UNIQUE다. 고정 ID로 바꾸는 것만으로 broker 세션·PID birth·task/display·focus를 증명하지 못하며 generic 앱 창 모델과 경합 동작도 바뀐다. `SEND_ENVIRONMENT`로 전체 환경을 전달하는 방식은 쓰지 않는다. [GApplication 공식 계약](https://docs.gtk.org/gio/class.Application.html), [command-line](https://docs.gtk.org/gio/signal.Application.command-line.html)

추천은 기존 NON_UNIQUE/native View와 nonce를 유지하고, fixed browser 전용 **새 owned local handoff 모듈**을 추가하는 것이다. 이 registry는 아직 없다. registry는 발견용이며 task 소유권이나 실행 허가의 근거가 아니다.

1. 현재 `/run/loopy` 아래 검증된 owned0700 하위 디렉터리에 session hash+fixed component로 범위를 정한 reservation과 socket을 만든다. atomic exclusive admission으로 동시 두 호출이 두 브라우저를 시작하지 못하게 한다. 작은 descriptor에는 owner UID/PID/birth, session hash, window nonce, backend generation, target component/UID, 양수 task/display, geometry epoch, socket identity와 state만 둔다. URI·전체 환경·raw authority token은 두지 않는다.
2. descriptor는 O_NOFOLLOW/regular0600/한 링크/size bound/parent dev-inode와 읽기 전후 metadata로 확인한다. Unix endpoint의 실제 SO_PEERCRED UID/PID와 `/proc` birth를 양쪽에서 확인한다. 같은 UID라도 session/nonce/generation/target가 다르면 거부한다. client의 task 번호를 신뢰해 선택하거나 `/proc`의 일반 commandline·탭·title을 수집하지 않는다.
3. 소유 View가 current catalog+GRANT/HELLO+OPENED를 거친 뒤에만 READY를 게시한다. URI 수신은 current LOOPY_SESSION과 exact registry stamp/lease를 socket 안에서 상호 확인한 뒤 허용한다. 구 broker 연결을 다른 sender에게 넘기지 않고 기존 Session actor가 요청을 직렬화한다.
4. 최초 URL은 STARTING owner에 immutable startup argument로 주고 OPEN_URL을 사용한다. 후속 URL은 READY owner에 bounded 한 요청씩 보낸다. 다수 요청의 순서를 보장하되 queue bound/deadline 초과는 BUSY로 반환한다. STARTING/closing/resize/unconfirmed cleanup에 새 task를 시작하지 않는다.
5. registry absent이고 atomic reservation을 얻은 경우만 새 시작을 시도한다. stale/unreachable/unknown owner는 absent와 다르다. PID가 죽었다는 사실만으로 socket/lease/Android 자원 정리를 완료했다고 승인하지 않는다. 소유 자원의 cleanup 증명 없이 descriptor를 삭제하고 재시작하지 않는다.

URL 없는 stock 호출도 인증된 READY owner가 있으면 정확한 창의 present/focus만 요청한다. URL이나 새 task를 만들지 않는다. 없다면 현재의 plain start를 유지하며 STARTING/UNKNOWN 상태를 새 시작으로 우회하지 않는다.

`Gtk.Window.present()`는 정확한 소유 View에만 요청하며 compositor가 허용한 local focus를 실제 확인한다. 제목을 찾아 선택하거나 Android 전역 앱/작업 전환을 호출하지 않는다. future unique-GApplication 방식은 위 authentication/lease 보증을 똑같이 갖춘 뒤에만 별도 대안으로 평가한다.

## 초기 Intent와 현재 lease 재사용

최초 OPEN_URL은 기존 launcher PM admission(유일한 MAIN/LAUNCHER alias, exported/enabled/permission, 같은 package/UID/APK source/alias chain), 두 번의 all-display snapshot, immutable descriptor/prior IDs를 유지한다. 실제 Intent만 explicit ACTION_VIEW+validated data+fixed alias로 만들며 기존 NEW_TASK|MULTIPLE_TASK와 own VD를 사용한다. URI가 임의 Android component/extra/handler를 선택하지 않는다. [Android ACTION_VIEW/data와 explicit component 계약](https://developer.android.com/reference/android/content/Intent#ACTION_VIEW)

NAVIGATE_URL은 **이미 이 connection이 취득한 동일 Ticket/TaskLease**에만 허용한다. `TargetGuard.admit/prior()`의 일반 기존-task 거부를 느슨하게 하지 않는다. 다른 connection, 같은 UID의 다른 task, 기존 사용자/Google Chrome task, 새 display0 task를 채택·이동·종료할 수 없다.

1. Owner actor는 입력을 잠시 quiesce하고 queued 입력을 비운다. held key/button, focus-off 및 borrowed-frame retirement를 기존 exact lease ACK 순서로 완료한다. resize/deadline/stale generation/cleanup pending이면 전달하지 않는다.
2. 정확한 소유 GTK 창을 present하고 local focus를 확인한 뒤 기존 FOCUS(true) 명령과 실제 focus ACK를 기다린다. 이 단계의 URI는 아직 Android에 전달하지 않는다.
3. Shell은 동일 FD/peer UID/PID/birth, stamp/generation, sequence, geometry, 현재 양수 task/display와 ticket의 mayRemove/identity를 다시 확인한다. descriptor/UID/source/alias 변경은 거부한다. 실제 top은 이 fixed browser의 ChromeTabbedActivity여야 하며 FirstRun/외부 top에는 전달하지 않는다. full task snapshot에서는 같은 UID/package의 유일한 row가 바로 이 lease인 것만 허용한다.
4. Android 전달 후보는 explicit ACTION_VIEW/data/fixed alias에 **현재 lease taskId와 displayId를 명시한 ActivityOptions**다. initial NEW_TASK|MULTIPLE_TASK, CLEAR_TOP/CLEAR_TASK, task 이동, guessed Chrome extras, 기본 handler resolution은 재사용 단계에 넣지 않는다. AOSP16의 hidden `setLaunchTaskId`는 존재하지만 START_TASKS_FROM_RECENTS permission과 실제 shell 호출/ActivityStarter/Chromium157의 결과는 아직 확인하지 않았다. 함수 존재만으로 안전한 재사용을 구현했다고 간주하지 않는다. [AOSP16 ActivityOptions](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/android/app/ActivityOptions.java#1935)
5. 재사용은 새 Ticket.started/claim을 호출하지 않는다. 정확한 Android 반환 코드 allowlist는 해당 AOSP 경로와 공개 시험 후 고정한다. 전달 후 동일 UID/task/display/base/original/real/top, PM descriptor와 focus를 재조회하고, 새 같은-package/UID task나 외부 작업 변화가 있으면 ACK하지 않는다. 실패하면 같은 소유 lease의 입력을 quiesce하고 UNKNOWN/UNAVAILABLE로 표시한다. 새로 발견한 task를 임의로 지우거나 자동 재시도하지 않는다.
6. 새 링크는 기존 탭을 덮어쓰지 않는 일반 browser new-tab 동작을 요구한다. Chromium157 ACTION_VIEW가 이를 제공하는지는 미확인이다. 임의 private/profile/tab-id extras로 보정하지 않으며, 공개 fixture의 두 URL로 이 계약을 먼저 검증한다. 소유 lease가 남아 있는 동안 route failure를 Linux/외부 Android 이중 실행으로 우회하지 않는다.

OPENED/FRAME/focus/URL delivery ACK/page load/CLOSED는 각각 다른 증거다. window 종료는 현재 CLOSE→owned task/display/input cleanup→frame retirement를 그대로 따른다. registry는 closing/unavailable를 먼저 게시하고 정확한 자기 descriptor/socket만 정리한다. handoff caller의 timeout은 브라우저를 kill/close하거나 사용자 프로필을 삭제할 권한이 아니다.

## 변경 영역과 의미 있는 테스트

미래 모듈은 각각500줄 이하로 유지하고 현재 `inside_window.py`에 registry/URI/parser 코드를 모두 넣지 않는다.

| 영역 | 필요한 변경 |
| --- | --- |
| browser_inside_route / browser_launch | typed empty-or-one-URI 선택; 현재 `run(argv)` 유지; 선택 후 실패는 propagate |
| browser_desktop_launch / loopy-app-launch | 정확한 stock entry+단일 URL 경로만 공통 parser에 연결 |
| 새 inside_browser_handoff 모듈 | atomic reservation, authenticated owned socket, bounded actor queue, stale/cleanup 경계 |
| inside_window / inside_wire | optional initial URI, owner handoff serialization, 새 action tail codec, 기존 retirement/focus 유지 |
| Protocol / BrokerPolicy / Shell / 새 URI adapter | double URI validation, fixed target, OPEN_URL admission, current-lease NAVIGATE admission/commit |
| AndroidInsideDisplay | 최초 ACTION_VIEW 구성과 gated exact-task reuse adapter; TargetGuard 기존 신규-task 거부는 유지 |
| AppHub / platform_action | 기존 grant/focus/web semantics 유지; reuse의 새 전역 Binder RPC나 외부 web fallback을 추가하지 않음 |

ROOT가 먼저 behavioral RED를 확인한다. 실행은 ROOT만 담당한다.

- literal legacy command/response golden bytes와 HELLO127; OPEN11/FRAME7 유지; 새 action을 구 decoder에 넣었을 때 allocation 없는 fail-closed, 자동 retry 없음.
- empty/one-URL direct+desktop 실제 entry/parser; profile/private/custom/다중 URL/모호한 percent/x11/환경 override의 원래 결과 보존; canonical diagnostics `run(argv)` 불변.
- Python/Java 공통 URI vectors: query/fragment/escaped path/IPv6/localhost/port 경계, credentials/control/backslash/bad percent/Unicode/다중 URI rejection; URI 로그·descriptor 출력 없음.
- concurrent startup, current session만 재사용, registry symlink/hardlink/stale PID/birth/FD/UID/generation/descriptor 교체, STARTING/BUSY/closing, owner death/partial packet/ambiguous delivery: 기존 lease를 채택하거나 이중 실행하지 않음.
- held input release, focus ack, pending resize/borrowed frame, stale geometry/sequence, changed PM metadata, foreign top, 다른 같은UID task, caller/owner/broker death 및 cleanup ACK 전 registry 재시작 거부.
- 공개 nonce fixture: typed initial URI가 **주소창 합성 타이핑 없이** 로딩됨; 두 번째 URI가 같은 Gtk PID/window nonce/backend generation/task/display에 전달되고 첫 공개 탭을 보존함; 나머지 task/service/role/config/profile 경계 유지와 CLOSED 증명. URI 전달 ACK만으로 page load를 통과시키지 않음.

## 남은 사실 확인과 다음 순서

1. exact Chromium157/b5fbbfa의 ACTION_VIEW alias cold-start 및 ChromeTabbedActivity onNewIntent/new-tab 동작, task options와 함께 전달될 때의 dispatch를 primary source로 좁힌다. 현재 확인한 HEAD IntentHandler의 getDataString 경로는 설치157 증거가 아니다. [공식 HEAD IntentHandler](https://chromium.googlesource.com/chromium/src/+/HEAD/chrome/android/java/src/org/chromium/chrome/browser/IntentHandler.java)
2. AOSP16 ActivityStarter exact-task 경로와 실제 shell START_TASKS_FROM_RECENTS/VD 제약 및 성공 결과를 확인한다. 확인 전에는 초기 URI start까지만 구현 가능한 별도 단계이며 기존-task 재사용은 unavailable로 둔다.
3. URI/parser/wire/registry/lease policy에 독립 fixture로 RED→구현→GREEN 및 source review를 수행한다. 설치/현재 user task와 분리한다.
4. 작업 저장/controlled device 조건이 충족된 뒤 fresh APK+fresh own public fixture로 초기 URL과 같은lease reuse를 검증한다. 현재 user task238/display51로 실험하거나 설정/프로필을 reset하지 않는다. 로그인·Notion/private tabs·physical input latency/GPU/60·144fps는 이 fixture의 합격에서 추론하지 않는다.

## 읽기 전용 소스 snapshot

아래는 이 설계 작성 시의 working source SHA256이며 설치 APK/기기 합격을 뜻하지 않는다. 이후 변경은 다시 고정해야 한다.

| 소스 | SHA256 |
| --- | --- |
| browser_inside_route.py | cd6fb6c510047289e8a173712f14f91cf43a4d964c2716f2b1cfcdbf140f178d |
| browser_desktop_launch.py | b3d18f58e567ba3b4f8c5d5cec2e2f13fa520db418d874d2f8396de88e8b438a |
| browser_launch.py | 90f78d78437817787ba60fc83a8deb0ddba2d29a38d2f8443f8ab7241f91ead2 |
| platform_action.py | 1037cd577b45376b9cc94226ad633ad3097d6140504eedccfbdd5cfe81001205 |
| inside_window.py | 09f756a728481829d9d27600973054caaab3c2d2f0bfd1e512346b27630b1426 |
| inside_wire.py | bd541ee594bf62ea3c1ed48a15d5e96a8269a4aff4dc3aee270ec655ef4630eb |
| AndroidInsideAppHub.java | c6574dd11637b60733e958ee0da90f9f3bba92291df83074598a950868304601 |
| AndroidInsideShell.java | a903e6e11b5f2bd9835b2074da5b4790258fe025c0d7b4d317f8fe5b8672d5ce |
| AndroidInsideProtocol.java | dede634550c469db39cf306265f19338c1fca3ce8ebf6c9ab0efb1f1be84c871 |
| AndroidInsideWire.java | efdfe1e9f1fd63604550f51fa65741cbb948524ecd9d9df73765ee16d8218175 |
| AndroidInsideBrokerPolicy.java | 0b591a7468108dac15ed2576d52050d92a9ccce281082484739a0d8a56a871cd |
| AndroidInsideTargetGuard.java | 1f655dd724feb742c73dd79b6d9c1db994f4cb966f0df0fcfcdd79ef6307b259 |
