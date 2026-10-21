# Linux GUI 브라우저·코드 편집기 선택 (2026-10-06)

현재 기본 Linux 브라우저는 자체 GTK3/PyGObject UI인 **Loopy Browser · WebKit**, 엔진은 **WebKitGTK 2.48.1-r1**이다. 원본 GTK3 MiniBrowser는 패키지에 포함돼 있지만 기본 실행 UI로 사용하지 않는다. 코드 편집기는 **Geany 2.0-r0**다. 기존 HOME의 Firefox·MiniBrowser 프로필과 사용자 설정·프로젝트는 삭제하지 않는다. 최종 UI는 탭 제목이 세 글자 폭으로 잘리는 화면 관찰을 반영해 `title.set_width_chars(14)`를 추가했다. 최종 APK의 [일반 Android 앱 전체 VM 영수증](../validation/2026-10-06-desktop-apps-ui-delivery-vm/receipt.json)은 **19/19 통과·실패 0개**다. 수락 범위와 동일 APK 식별자는 [앱 확장 검증 기록](../desktop-app-extension-validation.md)에 정리한다.

초기 Firefox·Geany 조사에서 2026-10-05에 Alpine v3.22 aarch64의 [community APKINDEX](https://dl-cdn.alpinelinux.org/alpine/v3.22/community/aarch64/APKINDEX.tar.gz)를 직접 조회했다. 그 조회의 SHA-256은 `58e2b190e6889394b8e35600cabb70e36aa85e42e3b17817961ac72a989770d1`이다. 잠금에 사용한 community 인덱스 SHA-256은 `3b346008f823ec6613f6e7e6b4866458fa8ee6e99c7ddfc287598750c03e49c8`이며, 두 목록 사이에서 버전이 바뀐 항목은 Linux 커널 관련 패키지 12개뿐이었다. 현재 준비는 이동하는 인덱스 대신 main/community 인덱스 식별자를 보존한 [고정 잠금](../../third_party/desktop.lock.json)을 사용한다.

| 앱 | 고정 버전 | 선택 이유 |
| --- | --- | --- |
| [WebKitGTK](https://pkgs.alpinelinux.org/package/v3.22/community/aarch64/webkit2gtk-4.1) | `2.48.1-r1` | 실제 Linux HTML·JavaScript·네트워크 엔진이다. [고정 APKBUILD](https://gitlab.alpinelinux.org/alpine/aports/-/blob/e9caef1999c50e8a16d8cfaf287b9d83adc59880/community/webkit2gtk-4.1/APKBUILD)의 GTK3 선택과 [공식 파일 목록](https://pkgs.alpinelinux.org/contents?arch=aarch64&branch=v3.22&name=webkit2gtk-4.1&repo=community)을 확인했다. 원본 MiniBrowser도 포함하지만 제품 UI는 별도 구현이다. |
| [PyGObject](https://pkgs.alpinelinux.org/package/v3.22/main/aarch64/py3-gobject3) | `3.52.3-r1` | Python에서 GTK3·WebKit2-4.1 API를 사용한다. [고정 APKBUILD](https://gitlab.alpinelinux.org/alpine/aports/-/blob/9ede4ceeac372a129fcec83a631324338c826fb7/main/py3-gobject3/APKBUILD). 추가 APK는 194,473바이트이며 기존 Python `3.12.15-r0`가 `python3~3.12` ABI 조건을 만족한다. |
| [Geany 고정 APK](https://dl-cdn.alpinelinux.org/alpine/v3.22/community/aarch64/geany-2.0-r0.apk) | `2.0-r0` | GTK 기반 실제 그래픽 코드 편집기다. [고정 APKBUILD](https://gitlab.alpinelinux.org/alpine/aports/-/blob/417cde601ef4273a846369134dafbd1d9670186c/community/geany/APKBUILD). |

제품 런처 [loopy-browser](../../guest/desktop/usr/local/bin/loopy-browser)는 `/usr/bin/python3 /usr/local/lib/loopy/browser.py`를 argv 그대로 실행한다. [브라우저 UI](../../guest/desktop/usr/local/lib/loopy/browser.py)는 주소창·탭·뒤로/앞으로·새로고침을 제공하며 HTML·JavaScript·네트워크 처리는 실제 WebKit 엔진이 맡는다. Ctrl+L/T/W/R, Ctrl+Tab·Ctrl+Shift+Tab, Alt+Left/Right와 F5를 처리한다. [주소·저장 경로 정책](../../guest/desktop/usr/local/lib/loopy/browser_policy.py)은 HTTP/HTTPS 주소를 열고 일반 검색어를 DuckDuckGo HTTPS 검색에 전달한다.

래퍼는 `GDK_BACKEND=wayland`, `WEBKIT_DISABLE_COMPOSITING_MODE=1`, `WEBKIT_DISABLE_DMABUF_RENDERER=1`을 설정한다. `GDK_BACKEND`는 데스크톱에도 이미 존재하는 [GTK3 Wayland 선택](https://docs.gtk.org/gtk3/running.html)이며, 두 `WEBKIT_*` 변수만 브라우저 실행 경로에 한정한다. 두 값은 고정 2.48.1의 [가속 compositing 선택](https://github.com/WebKit/WebKit/blob/webkitgtk-2.48.1/Source/WebKit/UIProcess/gtk/HardwareAccelerationManager.cpp)과 [DMA-buf renderer 선택](https://github.com/WebKit/WebKit/blob/webkitgtk-2.48.1/Source/WebKit/UIProcess/gtk/AcceleratedBackingStoreDMABuf.cpp)에 대응한다. 각 WebView도 hardware acceleration 정책을 `NEVER`로 설정한다. Sway의 pixman·CPU shared-memory 출력과 Xwayland 비활성 구성을 유지한다. 패키지의 X11·GPU 라이브러리 존재는 실제 사용 증거가 아니다.

브라우저 데이터는 `$XDG_DATA_HOME/loopy-browser`, 캐시는 `$XDG_CACHE_HOME/loopy-browser`를 쓴다. 해당 XDG 값이 없거나 상대 경로이면 HOME 아래 `.local/share/loopy-browser`와 `.cache/loopy-browser`로 돌아간다. 쿠키는 데이터 디렉터리의 `cookies.sqlite`에 저장한다. Firefox·원본 MiniBrowser 프로필은 그대로 두며 새 UI로 자동 가져오거나 탭을 세션 종료 뒤 복원한다고 주장하지 않는다.

현재 추가 payload 잠금은 **257개 패키지**다. MiniBrowser 후보의 256개 기록은 그대로 유지하고 PyGObject 한 패키지만 추가했다. [준비 영수증](../../build/desktop/receipt.json)의 rootfs는 압축 **324,279,867바이트**, 일반 파일 payload **823,159,749바이트**, **11,207엔트리**다. rootfs SHA-256은 `541b34426b87c526f9b4795bc7aec6f7450844bb78951fb58f3f615d6ce9e552`, 잠금 SHA-256은 `117051db9368ccf02a7eb2a24084813bfa033da3dd3f9adce9481ae877f0b5fb`다. 각 APK는 고정 URL·크기·SHA-256·APKINDEX Q1·APK datahash를 검증했고 RSA 서명을 독립 검증하거나 패키지 설치 스크립트를 실행하지 않았다.

최종 [전달 APK](../../build/deliverables/LoopyDesktop-2026-10-06-desktop-apps-arm64.apk)는 **325,051,509바이트**, SHA-256 `81d5e4d50e870c825a581c08c3e34df8b8a6ccde542f2c4af954c2b94488bccd`다. 전체 VM 시험에 사용한 `build/loopy-desktop-debug.apk`와 바이트·해시가 같다. 테스트 APK는 **57,747바이트**, SHA-256 `eebd89d0a8e78f828f9b3eb389ef7ef0fe54e1d4126ab8e03fe0fa4fb3135006`이다. 호스트 시험 **140/140·32.437초**, 변경 없는 Wayland host native 시험 **36/36**, 코드 파일 **195개·최대 499행**은 빌드·호스트 검증의 범위이며 실제 VM **19/19** 결과와 구분한다. rootfs나 native SHA를 APK SHA로 대신 쓰지 않는다.

최종 VM은 일반 Android 앱 UID **10224**·`untrusted_app`에서 HTTP·JavaScript·첫 글자를 포함한 폼 입력·탭 단축키·외부 HTTPS, Geany 저장·Python 실행, raw/generic 터치패드의 Thunar 이동과 captured 브라우저 스크롤을 확인했다. VM 설정 복구는 `restored=true`다. 입력 이벤트는 합성이며 실제 물리 장치나 포인터 캡처 허용의 수락이 아니다. Y900 실기기·GPU·장시간 성능은 이 결과에 포함하지 않는다.

동일 APK의 [최종 VM 화면](../validation/2026-10-06-desktop-apps-ui-delivery-vm/desktop-apps-screen.png)과 [GUI 영수증](../validation/2026-10-06-desktop-apps-ui-delivery-vm/gui-receipt.json)은 Loopy Browser·Geany·Thunar의 실제 창과 UID 네 값 10224·`untrusted_app`을 기록한다. 이 별도 화면 준비의 IPC 요청 시작은 `run-as`였고 GUI 자식은 일반 앱의 Sway가 실행했다. 영수증의 화면 검토는 오른쪽 위 상태·트레이 제거와 읽을 수 있는 Example Domain 탭 제목을 확인했다. 일반 앱 19개 시험과 화면 준비의 시작 컨텍스트를 혼동하지 않는다.

탭 폭 수정 전 [전달본](../../build/deliverables/LoopyDesktop-2026-10-06-apps-arm64.apk) `9605a26a0672aa39c07278414e8dadac0875ed9f0d14bd9ea1b45cab71ddfea5`와 테스트 APK `89255ccaeb860cf249525729d8dcd1beb76ba0b4e1cc90e0b1fcbc066edd2630`의 [전체 VM 영수증](../validation/2026-10-06-desktop-apps-delivery-vm/receipt.json)은 **19/19 통과·실패 0개**였다. 일반 Android 앱 UID **10224**·`untrusted_app`에서 HTTP·JavaScript·첫 글자를 포함한 폼 입력·탭 단축키·외부 HTTPS, Geany 저장·Python 실행, raw/generic 터치패드의 Thunar 이동과 captured 브라우저 스크롤을 확인했다. 입력 이벤트는 합성이며 실제 물리 장치나 포인터 캡처 허용의 수락이 아니다. VM 설정 복구도 `restored=true`로 기록했다. 새 APK·Y900 실기기·GPU·장시간 성능의 수락으로 재사용하지 않는다.

직전 자체 UI 후보 `d3185d0408eb4a3761d7333b6e196c4954db9bbb53b8aa25e126bc53f2b80956`와 테스트 APK `e38b82adb337611c364290e78a3058cefa0a701bc0676fed0b928d108bfbe676`의 [전체 VM 영수증](../validation/2026-10-06-webkit-desktop-final-vm/receipt.json)은 **18/19**였다. HTTP·JavaScript·첫 글자를 포함한 폼 입력·탭 단축키, Geany 저장·Python 실행, raw/generic 터치패드와 captured 스크롤은 통과했고 외부 HTTPS만 실패했다. 이 결과는 DNS placeholder 수정 전 후보의 기록이며 새 APK의 전체 합격으로 재사용하지 않는다.

## WebKit 프로세스 샌드박스와 진단 경계

현재 자체 UI는 WebContext를 만든 직후, WebView나 worker를 만들기 전에 **`context.set_sandbox_enabled(False)`를 명시한다**. 별도 `WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS` 환경변수는 제품에 설정하지 않는다. 고정 [WebKit 2.48.1 API 구현](https://github.com/WebKit/WebKit/blob/webkitgtk-2.48.1/Source/WebKit/UIProcess/API/glib/WebKitWebContext.cpp#L1398-L1421)은 subprocess 샌드박스를 worker 생성 전에 선택하도록 한다. 현재 경로는 추가 Linux WebKit 프로세스 샌드박스 OFF이며 브라우저 실행을 namespace 격리 제공으로 표현하지 않는다.

PRoot는 보안 경계가 아니다. 기본 격리는 실제 Android 앱 UID·SELinux와 앱 프로세스에 상속된 정책에 의존한다. 최종 `81d5e4d5…` 일반 앱 VM에서 브라우저 UID 네 값은 10224였고 관찰한 WebKit worker의 SELinux는 `untrusted_app`, `Seccomp=2`·필터 1개로 parent와 같았다. 추가 Linux 필터는 없었다. 다른 기기에서 peer의 `attr/current`가 거부되면 미수집으로 남기며 도메인을 추정해 성공 처리하지 않는다.

[격리된 MiniBrowser 진단](../../build/diagnostics/webkit-minibrowser-bt9d3wad/trial-summary.json)은 `run-as` UID 10224·`runas_app`에서 로컬 HTTP의 DOM/JavaScript 응답, 키보드 폼 입력·활성화, PageDown 스크롤을 확인했다. 이 진단은 `WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1`을 명시했고, 관찰한 parent/browser의 `Seccomp=0`, `Seccomp_filters=0`이었다. worker의 정책은 그 진단에서 수집하지 않았다. 이는 일반 앱 도메인·상속 필터·물리/합성 마우스와 터치패드 경로의 합격이 아니다.

원본 MiniBrowser의 [2.48.1 소스](https://github.com/WebKit/WebKit/blob/webkitgtk-2.48.1/Tools/MiniBrowser/gtk/main.c#L82-L84)는 기본 sandbox flag가 false이고 `--enable-sandbox`에서만 켜진다. 비교 진단은 bypass 환경변수를 제거하고 그 옵션을 지정했다. bubblewrap이 `/proc/sys/kernel/overflowuid` 읽기를 거부당한 뒤 dbus-proxy 시작에 실패했으며 HTTP/JavaScript 응답은 없었다. 이 실패를 모든 기기의 namespace 지원 여부로 확대하지 않는다. 외부 HTTPS·미디어·DRM·Linux 오디오·알림 및 Y900 실기기 수락은 별도 대상이다.

## MiniBrowser 입력 관찰과 자체 UI 선택

원본 MiniBrowser는 일반 Android 앱 UID에서 실제 HTTP·JavaScript GUI를 열었다. 그러나 [포커스 확인 시험](../validation/2026-10-06-webkit-browser-focus-vm/receipt.json)은 DOM 포커스가 true여도 입력·제출 값이 `loopy-browser-input` 대신 `oopy-browser-input`으로 남아 실패했다. [native 키 전달 진단](../validation/2026-10-06-webkit-browser-key-delivery-vm/receipt.json)에서는 첫 L의 down/up이 Linux 입력 경로에 전달됐지만 DOM에는 keyup만 관찰됐다. GUI 시작 성공을 폼 입력 수락으로 계산하지 않는다.

WebKit 2.48.1 GTK3의 `shouldForwardNextKeyEvent`가 주소창 accelerator·포커스 전환 이후 남는다는 설명은 **가설이며 원인으로 확정하지 않았다**. 자체 Window는 GTK 기본 처리와 WebKit의 비동기 fallback 전에 브라우저 단축키를 처리한다. GtkNotebook의 탭 전환 콜백도 `connect_after`로 연결해 기본 전환 뒤 새 current page를 읽는다. 폼 입력·탭 전환·스크롤은 탭 폭을 보완한 최종 APK의 전체 VM 19/19 영수증에서 확인했다. 이는 원본 MiniBrowser 실패 원인을 확정하는 증거가 아니다.

`code-server`와 `code-oss`는 조회한 저장소 인덱스에 없어 포함하지 않았다. Geany는 `Projects/hello.py`를 여는 GUI 코드 편집기로 연결했고 Neovim은 별도 터미널 항목으로 남겼다. Geany 선택은 VS Code 제품이나 VS Code 확장 생태계 제공을 뜻하지 않는다. **Other Linux apps**는 설치된 `.desktop` 항목 중 안전하게 argv로 해석할 수 있는 항목을 검색·실행한다.

## 이전 Firefox 후보와 PRoot 수정

이전 [Firefox ESR 140.11.0-r0](https://pkgs.alpinelinux.org/package/v3.22/community/aarch64/firefox-esr) 후보의 [전체 VM 영수증](../validation/2026-10-06-desktop-apps-current-vm/receipt.json)은 **16/19**였다. 데스크톱 기본 14개, Geany 저장·Python 실행, raw 터치패드의 Thunar 이동은 통과했고 Firefox GUI 입력·외부 HTTPS·브라우저 스크롤 세 검사는 실패했다. 그 APK는 `apps-preview-arm64.apk`로 별도 보존하며 현재 Loopy Browser 후보의 결과로 재사용하지 않는다. 당시 payload는 204개 패키지, rootfs `404c3e7f6a0830019ce682321acdb959b54b7343b656190b5c661bfa72e5c228`, 잠금 `c934b4b038de0156295e25a6ac566d03a9a09a0d5d6c57423206822478562c2d`였다.

첫 일반 앱 VM 후보에서 Firefox 창이 생성되지 않았다. 별도 진단은 `Running Firefox as root in a regular user's session is not supported`와 `/run/loopy`의 소유 UID 10224를 출력했다. 이 진단 자체는 `run-as` 컨텍스트이며 일반 앱 수락 시험으로 계산하지 않는다. [첫 후보 영수증](../validation/2026-10-05-desktop-app-extension-first/receipt.json).

[PRoot 매뉴얼](https://github.com/proot-me/proot/blob/master/doc/proot/manual.rst)의 `--root-id`는 실제 권한 상승 없이 UID/GID를 0으로 표시한다. [Mozilla bug 1323302](https://bugzilla.mozilla.org/show_bug.cgi?id=1323302)는 root가 일반 사용자 세션의 실행 디렉터리로 시작되는 경우를 거부하는 근거다. `RuntimeSession`에서 가상 root 옵션을 제거하고 실제 Android UID를 그대로 유지했다. [Sway 1.10.1의 UID 검사](https://raw.githubusercontent.com/swaywm/sway/1.10.1/sway/main.c)는 real/effective UID가 같은 비root 실행과 호환된다. 디렉터리 소유권이나 Firefox sandbox를 임의로 바꾸지 않는다. 최종 `81d5e4d5…` VM 영수증의 guest UID와 Android 앱 UID는 10224로 일치한다.

현재 전달본의 native 조합은 [빌드 영수증](../../build/proot-compat/build-receipt.json)의 파생 PRoot와 같은 빌드의 loader다. ARM64 syscall stop의 임시 x7 값을 실제 시그널 컨텍스트로 취급하지 않도록 수정했다. [격리된 레지스터 진단](../validation/2026-10-06-proot-register-return-o2fhz9b8/receipt.json)은 수정 전 3/4에서 수정 후 4/4였다. 이는 `run-as`의 시그널·레지스터 진단이며 Firefox GUI 수락과 구분한다.

| 전달본 native 파일 | SHA-256 |
| --- | --- |
| `build/proot-compat/arm64-v8a/libproot.so` | `e026656c33fe7fb3734fa2a9bac8a34f5acba7528328374a8c3e216df60a5077` |
| `build/proot-compat/arm64-v8a/libproot_loader.so` | `0738d73bc8e3c0b22f9b59a019a29087195453dcb0b73ced979b00fafe1caefe` |

## 공유 메모리와 Wayland 진단의 범위

실제 Firefox APK에는 `.post-upgrade`의 과거 profile migration 안내만 있으며 실행에 필요한 별도 post-install 초기화가 없다. 패키지 `application.ini`의 Mozilla SourceStamp는 `2e36c464a92f1942683abbed6ceb442308db5eb0`이다.

그 [정확한 ESR140 공유 메모리 소스](https://hg.mozilla.org/releases/mozilla-esr140/file/2e36c464a92f1942683abbed6ceb442308db5eb0/ipc/glue/SharedMemoryPlatform_posix.cpp)의 `HaveMemfd()`는 Android SELinux의 `/proc/self/fd` 읽기 전용 재열기 거부를 예상한다. parent에서 실패하면 named `shm_open` 생성·읽기 전용 재열기·unlink 경로로 자동 전환한다. 현재 `/tmp`를 `/dev/shm`에 bind하는 구성은 그 대체 경로를 제공한다. `MOZ_SHM_NO_SEALS`는 sealing만 생략하므로 memfd 선택을 끄는 설정이 아니다. 이 ESR140의 `IsSafeToMap()`는 항상 true이며 더 최신 Firefox의 seal 필수 조건을 그대로 적용할 수 없다.

x7 수정 전 [proxy-off 진단 로그](../../build/firefox-proxy-off.log)에서는 고유 normal profile, sandbox 유지, `MOZ_DISABLE_WAYLAND_PROXY=1`, 로컬 HTML 파일을 사용했다. parent가 읽기 전용 dup 거부 후 named SHM을 선택한 경고는 있었지만 SHM 생성·재열기·크기 설정 실패는 없었다. 브라우저 `Show`와 xdg 창 생성은 0회였으며 [프로세스 정리 기록](../../build/firefox-proxy-off-cleanup.json)을 남겼다. proxy를 끄는 변경은 제품 해결책으로 채택하지 않았다. 이 한 후보의 결과로 Wayland proxy 전반이나 수정 후 GUI의 성공·실패를 결론 내리지 않는다.

## Android DNS 전달

[RuntimeDns](../../android/src/dev/loopy/desktop/RuntimeDns.java)는 Android의 활성 네트워크 [LinkProperties DNS 목록](https://developer.android.com/reference/android/net/LinkProperties#getDnsServers())을 앱 소유의 regular resolver 파일에 원자적으로 쓰고 guest에 bind한다. default-network callback의 LinkProperties 변경을 반영한다. 기존 guest `/etc/resolv.conf`는 사용자 설정으로 취급하되, **일반 파일·0바이트·권한 0000**을 모두 만족하는 PRoot bind placeholder만 자동 DNS bind를 허용한다. placeholder 자체를 삭제하거나 수정하지 않는다. symlink·읽을 수 있는 빈 파일·내용 있는 권한 제한 파일과 메타데이터를 확인할 수 없는 기존 경로는 보존한다. 숫자 IP만 기록하고 임의 공개 DNS fallback을 추가하지 않는다. 네트워크·DNS가 없거나 파일 갱신이 실패해도 offline 데스크톱과 로컬 fixture 시작을 막지 않는다. 이 구분은 호스트 회귀 시험에서 수정 전 실패·수정 후 통과를 확인했다.

외부 `https://example.com`은 로컬 HTTP·JavaScript와 별도 확인 항목이다. 최종 `81d5e4d5…` 전체 VM 영수증은 실제 `Example Domain · Loopy Browser` 창과 브라우저 UID 네 값 10224를 확인했다. DNS 수정 직후 `9605a26a…`의 [HTTPS 단독 영수증](../validation/2026-10-06-dns-placeholder-https-vm/receipt.json) 1/1과 이전 UI 전체 VM 영수증 19/19도 보존한다. 이는 `run-as` 진단과 구분한다. Private DNS·VPN의 실제 정책과 경로, 네트워크 전환·복구는 Android가 DNS 주소를 제공한다는 사실만으로 보장하지 않으며 [Y900 점검표](../y900-test-checklist.md)에 남긴다. GPU·Omarchy 원본 Arch/Hyprland의 모든 기능·VS Code 확장 생태계·Linux 오디오 지원을 제공 완료로 표현하지 않는다.
