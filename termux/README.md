# Native Termux i3 kit

This path runs Android Bionic Termux packages directly, without PRoot. The existing Alpine/Sway environment remains a separate runtime. Termux:X11 presents its own Android Activity and owns input while focused.

## Prepare

Use your existing supported Termux installation, or the pinned official companions fetched by `python3 tools/fetch_termux.py`. Do not replace a differently signed existing Termux install or clear its data. The default X11 APK is the standard variant; shared UID is an optional user choice described in the [research](../docs/research/termux-native-runtime.md).

Run [the self-contained setup script](../android/assets/loopy-termux-setup.sh) in the primary-user native Termux shell. It installs `x11-repo`, Python, `termux-x11-nightly`, i3, xfce4-terminal, Mousepad, PCManFM, dmenu, D-Bus, xdpyinfo and xprop. It preserves existing `~/.config/i3/config` and `~/.termux/termux.properties`. Its own config lives in `~/.local/share/loopy-native/i3.config`; subsequent setup preserves changes to that config and refuses to replace edited helpers.

The GTK3/VTE terminal supports Unicode and starts with `--disable-server` to keep each window in the owned session. This does not install a full XFCE desktop. Android system fonts are included in Termux fontconfig's search path; `fc-match ':lang=ko'` and an actual Korean text check verify available glyphs on the device before any font change.

The installer does not grant Loopy's Termux command permission or enable `allow-external-apps`. Both require the user's explicit setup through the Loopy preparation guidance. No storage, overlay, accessibility, root, or system setting grant is performed by this script.

## Fixed helper interface

Interpreter: `/data/data/com.termux/files/usr/bin/python3`.

Arguments: `/data/data/com.termux/files/home/.local/share/loopy-native/runtime.py`, then `start|stop|doctor|input|restore`, then a canonical request UUID. The Android bridge supplies these fixed arguments; the helper accepts no shell command. Each public invocation returns one schema-1 JSON object, at most 16 KiB, with action, request, status, Termux UID and display.

Start chooses an unclaimed display from `:20`–`:99`, creates one private process group, starts Termux:X11 with tag `loopy-native`, then i3 under `dbus-run-session`. Ready requires a real bounded X root property query, a valid WM property and all recorded supervisor/X11/WM child identities still alive. A short `xprop` query avoids rejecting a working display merely because verbose visual enumeration is large. `doctor` also queries bounded package versions and i3 window count, active window ID/PID and workspace; it does not report window titles. Readiness is not a GPU or displayed-pixel claim.

Window diagnostics exclude i3 dock/bar windows. `activeTerminalShellReady` checks a same-UID active window process for a direct child with the exact native `bash -l` command and a nonzero controlling TTY, then rechecks identities and parentage. Unknown, absent or unreadable metadata reports false. This default-terminal diagnostic does not change startup conditions for a custom i3 profile, or prove typed input/IME acceptance; those require actual input and a witness.

Duplicate start preserves the owned session. Stop rechecks the supervisor's PID/UID/group/start time/command and requests its cleanup. The live supervisor uses Linux subreaper ownership and process lineage to terminate and reap only verified descendants, including separate-session children. It confirms completion before exiting; missing identity or unfinished cleanup keeps the owner marker for explicit retry. It never uses process-name kills. Child standard streams are detached, so a completed start callback does not remain attached to the desktop lifetime. An exited or incomplete session returns an explicit failure; users can stop and retry. `stop` does not erase installed files or either runtime's user data.

Android may omit kernel child-list files. Their absence is optional discovery failure; direct child PID and PPID metadata still require strict identity verification. Completion requires both no tracked descendants and kernel `waitpid` reporting `ECHILD`, with Linux `__WALL` and default `SIGCHLD` disposition. An unreadable live child prevents completion; an empty scan alone cannot acknowledge cleanup.

If the supervisor vanishes before cleanup is confirmed, `doctor` reports failure and a new `start` retains the old marker. A recorded confirmed stopped session can start again. An externally killed owner requires a cleanup diagnosis before its evidence can be replaced.

The display uses `com.termux.x11/com.termux.x11.MainActivity` with Intent data `loopy-native`. Closing that Activity does not terminate the server; stop the Loopy-owned native session explicitly.

## Use

| Chord | Action |
| --- | --- |
| Ctrl+Alt+Enter | xfce4-terminal |
| Ctrl+Alt+Space or D | Application menu |
| Ctrl+Alt+E / F | Editor / files |
| Ctrl+Alt+H/J/K/L | Focus left/down/up/right |
| Ctrl+Alt+Shift+H/J/K/L | Move window |
| Ctrl+Alt+1–9 | Workspace |
| Ctrl+Alt+Shift+1–9 | Move to workspace |
| Ctrl+Alt+Tab | Tiled/floating focus |
| Ctrl+Alt+Shift+Space | Toggle floating |
| Ctrl+Alt+M | Fullscreen window |
| Ctrl+Alt+Shift+Q | Close focused window |

The optional `input` action snapshots seven Termux:X11 Boolean preferences. It sets `fullscreen`, `pointerCapture` and `pauseKeyInterceptingWithEsc` true; `hardwareKbdScancodesWorkaround`, `preferScancodes`, `showAdditionalKbd` and `showIMEWhileExternalConnected` false. Open the owned X11 window first and avoid another concurrent X11 window while applying or restoring: upstream's preference CLI has no tag selector. Separate per-window preference storage is rejected for manual setup. Accessibility is not granted by this action. Unmodified Escape releases upstream pointer capture.

This profile lets X11 handle hardware keys through its PreIME path before the Android IME. Printable unmodified keys use the upstream Unicode text path, while Ctrl/Alt/Meta shortcuts retain available raw scancodes; the upstream AltGr text exception remains. Software IME composition and `commitText` remain supported. Upstream still schedules a 50 ms fallback release for Delete/Ctrl/Shift when the normal key-up path is absent. OEM scancode behavior, multiple layouts and physical keyboard/IME behavior remain device checks. See the [pinned input sources and verification limits](../docs/research/termux-native-runtime.md#physical-input-and-explicit-preferences).

`restore` compares the observed current value with the recorded applied value and restores only matching owned keys. Later user changes and unowned keys are preserved; an older six-key snapshot cannot take ownership of the new seventh key. The stock CLI's read and write are separate commands, so this is not an atomic lock against concurrent external preference edits. Avoid editing X11 preferences during apply/restore. An incomplete apply keeps its snapshot for an explicit restore.

## Verification and limits

Run `python3 -m unittest discover -s tests -p 'test_termux_*.py'`, `python3 -m py_compile termux/*.py tools/fetch_termux.py`, and `bash -n android/assets/loopy-termux-setup.sh`. Regenerate the asset with `python3 termux/generate_setup.py` after any managed source/config change. The host tests exercise ownership rejection, actual detached child cleanup, missing kernel child lists, hidden-child termination refusal, fake executable X probes, installer preservation, JSON bounds and preference restoration. Android RUN_COMMAND callbacks, native visible pixels, injected input and stop/cleanup need the separate VM receipt; physical keyboard, trackpad, performance and OEM power behavior need device acceptance.

Subsequent exact-APK native acceptance is recorded in repository `docs/native-termux-validation.md`; this kit does not claim that pending validation has passed.

The default native profile sets `LIBGL_ALWAYS_SOFTWARE=true`. This is a conservative environment choice, not a GPU implementation or proof that every client selected software. Termux:X11's Android presentation and native Mesa application's rendering are separate evidence. Additional GPU paths and their prerequisites are in [guest GPU alternatives](../docs/research/guest-gpu-alternatives.md).

Companion provenance and upstream licenses are recorded in [NOTICE](NOTICE.md), [the lock](../third_party/termux.lock.json) and `build/termux/companions/receipt.json`. Package installation uses official repositories but installed package versions remain rolling; `doctor` records actual core package versions rather than claiming that APK pins froze apt packages.
