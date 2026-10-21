# Native Termux runtime: implementation and alternatives

Checked 2026-10-06 against official Termux, Termux:X11 and Android sources. The approved implementation uses native Termux i3 applications, the public RUN_COMMAND bridge and a separate Termux:X11 Activity. It avoids PRoot in this runtime. Host helper tests and companion provenance checks are complete; the exact final Loopy APK's RUN_COMMAND, visible native GUI, input and cleanup acceptance belong to the upcoming disposable-VM receipt. No physical-device performance or hardware-GPU acceptance is claimed here.

## Selected runtime

Termux packages target Android Bionic and a fixed Termux prefix. They cannot simply be moved into Loopy's app-private root as ordinary Linux binaries: package name, primary Android user and prefix are part of the build assumptions. Existing Alpine musl packages remain a different ABI/runtime. Native i3 removes the PRoot translation layer from this path; lower latency on a particular tablet is an inference to measure, not a benchmark result. [Official execution environment](https://github.com/termux/termux-packages/wiki/Termux-execution-environment), [package management](https://github.com/termux/termux-packages/wiki/Package-Management).

The default kit installs `x11-repo`, `python`, `termux-x11-nightly`, `i3`, `xfce4-terminal`, `mousepad`, `pcmanfm`, `dmenu`, `dbus`, `xorg-xdpyinfo` and `xorg-xprop`. Its small bar and native X11 applications require no additional compositor. Official recipes provide i3 and Openbox; `xfce` is an optional full desktop metapackage, rather than the default dependency set. Recipe snapshots describe available packages, while actual installed versions remain rolling and are reported by the helper. [i3 recipe](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/i3/build.sh), [Openbox recipe](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/openbox/build.sh), [XFCE metapackage](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/xfce4/build.sh).

The terminal default is the native GTK3/VTE `xfce4-terminal`, not Termux's virtual `xterm` package/provider. Startup and Ctrl+Alt+Enter use `--disable-server` so each new terminal belongs to this session instead of opening through an existing terminal's D-Bus instance. This adds one terminal application, not a full XFCE session, and provides a practical Unicode path; rendering/input still require acceptance. Fontconfig searches Android `/system/fonts` plus `$PREFIX/share/fonts`. Verify `fc-match ':lang=ko'` and actual Hangul glyphs before adding fonts; the inspected official package tree does not provide a guessed `fonts-noto-cjk` package. [Terminal recipe](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/xfce4-terminal/build.sh), [Xfce Unicode support](https://docs.xfce.org/apps/terminal/start), [new-process option](https://docs.xfce.org/apps/xfce4-terminal/command-line), [fontconfig recipe](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/fontconfig/build.sh).

The owned VM's read-only Termux font probe returned `Noto Sans CJK KR`/`Regular` from `NotoSansCJK-Regular.ttc`, exit 0. Its [diagnostic record](../validation/2026-10-06-native-termux-loopy-Xdiag-655b3829/stdout.txt) is explicitly a run-as preparation context, not the public command callback or visible VTE glyph/IME acceptance. No extra CJK package was added.

The [VM package preparation receipt](../validation/2026-10-06-native-termux-xfce-setup-Atkn7Q/receipt.json) records 249 installed packages, including xfce4-terminal `1.2.0`, VTE `2:0.84.1`, GTK3 `3.24.52`, i3 `4.25.1-1` and Termux:X11 native package `1.03.01-6`. Its managed source/installed/manifest hashes matched that preparation's helper snapshot; later compatibility fixes require a fresh upgrade and receipt. This is preparation via run-as; public RUN_COMMAND and visible/input acceptance remain separately recorded by the final APK test.

The implementation is [termux/runtime.py](../../termux/runtime.py), its [private i3 configuration](../../termux/i3.config), and the [self-contained installer](../../android/assets/loopy-termux-setup.sh). Installation preserves the user's existing Termux property file and i3 profile, writes managed helpers only into `~/.local/share/loopy-native`, records their hashes and refuses to overwrite edited helpers. It grants no permission, changes no global system setting and needs no root. [Kit instructions](../../termux/README.md).

## Companion identity and launcher

| Item | Selected pin / behavior |
| --- | --- |
| Termux APK | v0.118.3 GitHub ARM64 artifact; source `5b657c6adf4304e5198951ce815fe0205dcac29c` |
| X11 APK | Standard universal debug nightly from 2026-10-05; source `e85aa491a99ee78e3569dba477e12ca4d79148e4` |
| APK packages | `com.termux`, `com.termux.x11` |
| Public X11 Activity | `com.termux.x11/com.termux.x11.MainActivity` |
| Owned window tag | `loopy-native`; Intent data is this tag |
| Native display | First verified unclaimed display in `:20`–`:99` |
| Native companion package | `termux-x11-nightly` from official X11 repository |
| Provenance | Pinned sizes/SHA-256 plus apksigner-verified certificate in [lock](../../third_party/termux.lock.json) and generated receipt |

Termux:X11 requires both its APK and native companion package. Current upstream supports a tagged display in a separate Android window, and bringing the same tag forward reuses that window. The package's loader and APK must remain compatible; a successfully installed pair still needs actual X client and visible-pixel checks. The rolling `nightly` download URL is not a stable pin by itself, so fetch rejects changed bytes rather than silently updating the lock. [Official README at selected source](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/README.md), [native loader package recipe](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/termux-x11-nightly/build.sh).

The standard APK preserves compatibility with the user's existing Termux source. Upstream also provides a shared-UID variant, which requires the GitHub-signed Termux app and is intended to keep foreground CPU classification across Termux and X11. It is an explicit alternative for a compatible existing install, not a default migration or proven tablet performance improvement. Do not replace a differently signed Termux installation or erase its data to obtain it. [Upstream shared-UID explanation](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/README.md#avoiding-slowdowns).

The official GitHub artifacts use a published debug signing key. APK certificate identity alone is therefore insufficient to establish origin; the kit also pins upstream URL, size and SHA-256. Preserve source references and component notices for redistribution. [Termux signing warning](https://github.com/termux/termux-app#github), [local notices](../../termux/NOTICE.md).

## Public command/result contract

Loopy sends an explicit Intent to `com.termux.app.RunCommandService`, action `com.termux.RUN_COMMAND`. The user must grant `com.termux.permission.RUN_COMMAND` to Loopy and explicitly set `allow-external-apps=true` in Termux properties. For this background command, storage and overlay permission are unnecessary. API 30+ package visibility and foreground user initiation also need handling. [Official RUN_COMMAND instructions](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent).

The only executable is `/data/data/com.termux/files/usr/bin/python3`. Its arguments are the fixed owned helper path, one enumerated action and one canonical UUID. No arbitrary shell script or command token travels through this runtime control interface. Start/stop/doctor use real Termux UID processes; installation and ADB preparation are separate from that acceptance.

The callback is a private, explicit, one-shot PendingIntent with a unique request identity. Termux's `result` bundle carries command exit code and internal `err`; `err=-1` means no internal error, which is separate from `exitCode=0`. The pinned publisher always writes `err`, and writes stdout/stderr original lengths as Strings. Loopy rejects truncated/excessive output and stale nonce/action/UID/schema rather than interpreting an exit code as session readiness. [Pinned result publisher](https://github.com/termux/termux-app/blob/5b657c6adf4304e5198951ce815fe0205dcac29c/termux-shared/src/main/java/com/termux/shared/shell/ResultSender.java), [constants](https://github.com/termux/termux-app/blob/5b657c6adf4304e5198951ce815fe0205dcac29c/termux-shared/src/main/java/com/termux/shared/termux/TermuxConstants.java).

| Public action | Successful status | Evidence / meaning |
| --- | --- | --- |
| `start` | `ready` | Real bounded X root property query + valid WM property; three owned live supervisor/X11/WM identities; `xReady`, `wmReady` |
| `doctor` | `ready` or `stopped` | Same readiness gates; bounded native package versions, i3 window count, active window ID/PID and workspace |
| `stop` | `stopped` | Identity-verified supervisor confirms termination/reaping of all owned descendants; no broad name-based kill |
| `input` | `applied` | Explicit bounded preference snapshot/apply/readback |
| `restore` | `restored` | Restore only still-owned values, preserving later user edits |

Each helper reply contains schema `1`, action, request, status, actual UID and display; failures use `failed` plus bounded reason. One JSON object is limited to 16 KiB. The daemon's standard streams are detached so startup result delivery can complete while the desktop continues. State validates supervisor command, UID, PGID, PID/start time and current process identity before requesting cleanup. The supervisor enables Linux subreaper ownership before spawning children, verifies parent lineage/current identities and reaps detached descendants before acknowledging completion. Unknown identity or incomplete cleanup retains its live anchor/marker for explicit retry. Merely finding an X socket or live supervisor cannot report ready. [Linux subreaper semantics](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html).

Some Android kernels omit `/proc/PID/task/TID/children`. These optional discovery files may be absent or denied; the helper then uses verified direct child PIDs and same-UID PPID lineage, while known PID identity checks remain strict. Cleanup succeeds only when no tracked descendants remain **and** `waitpid(-1, WNOHANG | __WALL)` reports `ECHILD`. The supervisor fixes `SIGCHLD` to its default disposition before spawning; a zero wait result means a child is still alive, including one whose identity cannot be read, and cannot authorize a success or an unverified signal. Linux `__WALL` also includes clone children with a different exit signal. This adapts to the platform without treating an empty process scan as termination proof. [Kernel wait semantics](https://man7.org/linux/man-pages/man2/waitpid.2.html).

If the supervisor disappears before confirming cleanup, `doctor` reports failure and a later `start` preserves the unconfirmed owner marker. Only a recorded, confirmed stopped session can be replaced by a new start. This avoids silently abandoning descendants after an externally killed supervisor; recovery requires establishing cleanup rather than overwriting its evidence.

Readiness uses one short `xprop` query of `_NET_SUPPORTING_WM_CHECK`: a successful X response establishes transport, and a nonzero WM window establishes WM readiness alongside the owned process checks. The earlier verbose xdpyinfo enumeration exceeded its output limit on the VM's many visuals and incorrectly classified an actual X connection as failed; bounded regression tests now exercise that counterexample. xdpyinfo remains an installed diagnostic tool, not a required verbose readiness response.

The `doctor` window count excludes i3 dock/bar nodes. Its `activeTerminalShellReady` field is a bounded default-terminal diagnostic: verify the active window PID's UID, find a direct child with the exact native `bash -l` command and nonzero controlling TTY, then recheck child/parent identities and parentage. The scan is limited to one second/4096 entries and uses readable process metadata instead of ptrace-gated cross-process fd links. Missing or uncertain evidence remains false. A mapped terminal can precede its shell; this diagnostic adds no custom-profile startup requirement or environment change, and actual typed-command/IME acceptance remains a separate test.

Closing X11's Activity or sending `ACTION_STOP` closes that window, while upstream's server command continues. Owned process termination is therefore a separate helper operation. [Official lifecycle commands](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/README.md#force-stopping-x-server-running-in-termux-background-not-an-activity), [X11 app lifecycle source](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/lorie/src/main/java/com/termux/x11/LorieApp.java).

## Surface embedding choices

| Route | Feasibility and conditions | Decision |
| --- | --- | --- |
| Public external X11 Activity + RUN_COMMAND | Existing official APIs; focused X11 input; separate Activity | Implemented native backend design |
| Embed existing APK's View directly | LorieView depends on JNI, app lifecycle/input/preferences; no stable exported remote View contract | No supported drop-in embedding claim |
| Own GPL-compatible X11/Lorie fork in Loopy | Build JNI/Xorg/submodules and integrate Surface, input, IME, lifecycle, notices/source | Feasible larger separate project |
| Cooperating SurfacePackage producer | Both apps implement stable IPC; Android SurfaceControlViewHost requires API 30+ | Possible fork protocol, excludes API 28/29 baseline |

The upstream Binder interface exposes an X connection/log output/fatal-error path, not a public SurfacePackage producer. The package loader's support for other apps concerns command-side loading, not a portable Loopy view embedding interface. [LorieView](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/lorie/src/main/java/com/termux/x11/LorieView.java), [Binder interface](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/lorie/src/main/aidl/com/termux/x11/ICmdEntryInterface.aidl), [Android SurfaceControlViewHost](https://developer.android.com/reference/android/view/SurfaceControlViewHost).

## Physical input and explicit preferences

X11's focused Activity handles keys, pointer capture and IME. Loopy must release its built-in capture and suppress global accessibility keyboard ownership during native handoff. Captured pointer input gives relative movement; it does not grant control of Android system-reserved keys. Actual keyboard layout, trackpad scrolling, buttons, capture release and reconnect require physical acceptance. [TouchInputHandler](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/lorie/src/main/java/com/termux/x11/input/TouchInputHandler.java), [key interceptor](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/lorie/src/main/java/com/termux/x11/utils/KeyInterceptor.java).

The opt-in preset owns seven Boolean keys. Accessibility remains a separate user choice. It changes neither touch mode nor global Android settings, and upstream's plain Escape release remains available. [Preference definitions](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/lorie/src/main/res/xml/preferences.xml), [preference CLI](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/lorie/src/main/java/com/termux/x11/LoriePreferences.java).

| Preference | Applied value |
| --- | --- |
| `fullscreen` | `true` |
| `pointerCapture` | `true` |
| `pauseKeyInterceptingWithEsc` | `true` |
| `hardwareKbdScancodesWorkaround` | `false` |
| `preferScancodes` | `false` |
| `showAdditionalKbd` | `false` |
| `showIMEWhileExternalConnected` | `false` |

With the hardware workaround disabled, the pinned X11 view forwards hardware events to its own handler during PreIME, before Android's IME. Software composition and `commitText` keep their existing text path. Upstream's Delete/Ctrl/Shift compatibility path still schedules a 50 ms release fallback and cancels it when normal key-up dispatch arrives. This profile does not patch those upstream timing rules. [Pinned key and IME routing](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/lorie/src/main/java/com/termux/x11/LorieView.java#L541-L580).

With `preferScancodes=false`, printable unmodified key events use Unicode text; Ctrl/Alt/Meta shortcuts still use available raw scancodes, with the upstream AltGr text exception. Shifted printable characters follow the text path. The upstream workaround is intended for OEM scancode issues and explicitly warns about multiple layouts, so the profile is a practical default to validate, rather than acceptance of every hardware/layout combination. [Text versus scancode dispatch](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/lorie/src/main/java/com/termux/x11/input/InputEventSender.java#L244-L267), [upstream preference descriptions](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/lorie/src/main/res/values/strings.xml#L84-L87).

A manual disposable-VM diagnosis changed only the hardware workaround on the same APK and recovered exact long ASCII and Unicode input. That identifies the event-route problem; it does not establish the packaged seven-key preset's public CLI callback/readback or selected UI profile. Fresh final-APK RUN_COMMAND apply, visible terminal input and explicit restore remain the separate acceptance step. Physical OEM keyboards, IMEs and multiple layouts remain unverified here.

The CLI requires a running X11 Activity and lacks a tag selector. Calls have short time/output limits, snapshot only owned keys, verify readback and restore only values whose observed current value still matches the recorded preset. Unowned values and later user edits are preserved; older six-key snapshots never gain ownership of the seventh key. A failed partial apply retains its snapshot for explicit restore. CLI reads and writes are separate requests, so the comparison cannot atomically protect against a simultaneous external settings edit. Avoid changing preferences during apply/restore, and avoid concurrent other X11 windows. Per-window preferences are refused for manual setup rather than silently affecting another window. A preparation screen with no running listener must report failure instead of hanging.

## GPU and fallback

Termux:X11's Android renderer uses GLES and can import its shared buffers; that accelerates presentation, not every native GLX/EGL application. i3/xfce4-terminal/editor/files can run with software client rendering. The native profile sets `LIBGL_ALWAYS_SOFTWARE=true`, but renderer names, rendered pixels and displayed pixels must still be measured separately. Native packages remove musl/Bionic bridging for native Mesa alternatives, while driver/device access restrictions remain. [X11 renderer source](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/lorie/src/main/cpp/lorie/renderer.cpp), [official native Mesa recipe](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/mesa/build.sh), [full GPU alternatives](guest-gpu-alternatives.md).

| Condition | Next route and proof |
| --- | --- |
| Native setup/permission/companion absent | Complete explicit setup or keep the built-in Alpine/Sway runtime; never claim native ready |
| Black frame while real X/WM clients respond | Diagnose visible pixels; upstream `-legacy-drawing` is an optional owned-server retry flag |
| Red/blue channels swapped | Verify known color readback; upstream `-force-bgra` is an optional owned-server retry flag |
| Standard APK CPU throttling is measured | Consider compatible shared-UID variant explicitly; preserve the existing Termux source/data |
| Native client needs 3D | Probe software first; evaluate native VirGL/Zink/Vulkan/device drivers using actual renderer/pixels and ownership |
| OS kills native child processes | Expose failure/recovery; minimize process count; user-controlled OEM power exemptions if measured |

The two drawing flags are researched alternatives, not automatic toggles implemented in the current fixed-action helper. Official Termux warns about Android 12+ phantom processes and excess CPU killing. The kit does not disable those protections globally, root the device or promise daemon persistence. [Upstream display workarounds](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/README.md#running-graphical-applications), [Termux Android warning](https://github.com/termux/termux-app#installation).

### Optional native VirGL diagnostic path

This is a researched, explicitly selected diagnostic route; it is not installed or enabled by the current native helper. The official package snapshot includes `virglrenderer-android` 1.3.0 revision 1, which builds virglrenderer/libepoxy with the NDK and depends on `angle-android`. `mesa-demos` is in `x11-packages`, version 9.0.0 revision 7, and provides native GL test programs plus `eglinfo-system`, a wrapper that uses Android's system EGL library. Native Mesa includes the virgl client, and its Termux patches align the default vtest socket with `$PREFIX/tmp/.virgl_test` and address a glxinfo/virglrenderer-android front-buffer issue. These recipe versions are not a pin of packages later fetched by apt. [Android server recipe](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/virglrenderer-android/build.sh), [Mesa demos recipe](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/x11-packages/mesa-demos/build.sh), [Mesa socket patch](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/mesa/0005-virgl-socket-path.patch), [Mesa front-buffer patch](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/mesa/0009-disable-resource_create_front-for-vtest.patch).

The executable is `virgl_test_server_android`, not Loopy's embedded Android server. Its patched CLI **removes** `--use-gles` and `--use-egl-surfaceless` and always selects EGL/GLES surfaceless. With no ANGLE flag, libepoxy loads system `libEGL.so`/`libGLESv2.so`. `--angle-gl`, `--angle-vulkan` and `--angle-null` select installed ANGLE library directories; only one is permitted. The last flag means a Vulkan null-display configuration, not proof of a software or hardware renderer. Native EGL/surfaceless context initialization, GL capabilities and actual rendering must all work. A working GLES 2 presentation Surface does not prove that the VirGL renderer's GLES 3+ path is available. [CLI/socket patch](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/virglrenderer-android/0007-Ensure-EGL-GLES-ANGLE-help-and-socket-path.patch.beforehostbuild), [epoxy library selection](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/virglrenderer-android/0003-use-angle.patch.beforehostbuild), [ANGLE build configuration](https://github.com/termux/termux-packages/blob/7945fdb5a62d773e98cae56f2e43438d859f9009/packages/angle-android/args.gn.in).

An opt-in manual check in **native Termux**, after the owned X11 display is verified:

```sh
pkg install -y mesa mesa-demos virglrenderer-android
dpkg-query -W mesa mesa-demos virglrenderer-android angle-android
eglinfo-system
```

In one Termux terminal, run the server in the foreground on a new private diagnostic socket. Refuse an existing socket, and keep this terminal/process under explicit ownership:

```sh
test ! -e "$HOME/.local/share/loopy-native/gpu-probe.sock" &&
virgl_test_server_android --no-fork \
  --socket-path "$HOME/.local/share/loopy-native/gpu-probe.sock"
```

In another terminal, substitute the helper's **verified owned display** for `:20`, then run a bounded client. `LIBGL_ALWAYS_SOFTWARE=true` selects Mesa's software-screen entry point here, while `GALLIUM_DRIVER=virpipe` replaces its rendering driver with the vtest proxy; it does not imply the remote host uses software:

```sh
env DISPLAY=:20 LIBGL_ALWAYS_SOFTWARE=true GALLIUM_DRIVER=virpipe \
  VTEST_SOCKET_NAME="$HOME/.local/share/loopy-native/gpu-probe.sock" \
  timeout 10s glxinfo -B
```

Server-side custom socket can also use `VTEST_RENDERER_SOCKET_NAME`; client-side selection is `VTEST_SOCKET_NAME`. The CLI patch is the server authority; Mesa's [vtest connection source](https://gitlab.freedesktop.org/mesa/mesa/-/blob/mesa-26.2.4/src/gallium/winsys/virgl/vtest/virgl_vtest_socket.c) defines the client environment variable. Do not copy the embedded Loopy server's flags into this package or assume its patched ANGLE behavior matches Loopy's native host.

Use `--no-fork` only for serial one-client diagnostics: finish glxinfo before a bounded visual GL demo. Verify actual rendered pixels and the displayed X11 window separately. `virgl` in glxinfo identifies the proxy; acceptance also needs the server's underlying GL vendor/renderer, successful pixel output and rejection of software host renderers such as SwiftShader/llvmpipe. glxinfo capability text alone is not hardware acceptance. General concurrent GL applications need a managed server/client lifecycle; this fixed-action kit does not implement it.

Stop the foreground diagnostic server explicitly with its terminal's Ctrl+C, confirm termination, and remove only the diagnostic socket that invocation created. If initialization, socket transport, caps or pixel checks fail, retry a different supported ANGLE route only with a new owned server invocation; retain the reason. Return the client to the verified software route by dropping `VTEST_SOCKET_NAME`/virpipe and using `GALLIUM_DRIVER=llvmpipe LIBGL_ALWAYS_SOFTWARE=true`, with real renderer/pixel checks. The current helper already keeps its default software profile and does not persist these manual GPU variables.

## Verification contract and user next actions

Host regression tests cover fixed UUID/actions and bounds, real child-group timeout isolation, foreign/PID reuse ownership rejection, actual command-based X readiness probes, incomplete session rejection, bounded own-window evidence, installer preservation and preference compare/restore. Fetching verifies both companion byte hashes and signatures. These are source/package evidence, not proof of real native Android input or pixels.

On the owned disposable VM, record installed companion APK bytes/versions and Termux UID; prepare dependencies separately; then use the final Loopy APK's public RUN_COMMAND callback to start, validate ready, present the owned X11 Activity, open/type into a real xfce4-terminal and inspect an owned witness without elevating the runtime. Verify actual display pixels, duplicate start, doctor evidence, stopped cleanup and explicit missing-permission/failure fallback. Run the full current APK regression suite. Synthetic keyboard/mouse events remain distinct from physical hardware.

For the tablet: preserve the existing Termux source, review the installer, explicitly allow the command bridge, start native i3 and select input preferences only after opening its X11 window. Then validate keyboard layout/IME, Ctrl+Alt shortcuts, physical relative mouse/trackpad, capture Escape, app switching, reconnect, cold/warm startup, suspend/resume and a measured latency/power session. Record actual GL/Vulkan driver/device information before selecting a hardware GPU alternative; the model name alone does not establish its GPU.
