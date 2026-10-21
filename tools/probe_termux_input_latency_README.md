# Termux X11 / guest Wayland input timing fixtures

This is an isolated diagnostic, not a runtime or GPU-policy change. ROOT alone deploys, starts and injects device events. Native ARM64 compilation and pure host tests do not prove device input acceptance.

Both clients draw a public dark green/blue 640×420 client area with a fixed pale center square. Width/height are client coordinates; GTK fractional output scaling can change physical pixel size. Pin the current output geometry/scale separately when comparing them.

## Native X11

Artifact: `build/diagnostics/termux-omarchy-input-latency-native-build-20261009-03/probe-input-latency-x11`. It is an Android API28 AArch64 PIE using system libc/libdl and `dlopen("libX11.so")` from the existing Termux prefix. No library or user profile is installed or modified by the build.

ROOT must first bind the current runtime token, actual X11 display, live X socket inode and `SO_PEERCRED` PID/UID/birth to the runtime's owned X11 lineage. The socket peer can differ from the launcher's PID; pass the actual socket peer. Do not guess from a process name. Preserve the live desktop and record its focus for recovery.

Launch through actual Termux UID10323, with the existing `$PREFIX/lib` discoverable, in a fresh owned directory and session. Redirect stdout to a new mode0600 capture file and stderr to a separate bounded file. Literal argument list:

```
probe-input-latency-x11 --nonce <fresh-32-lowercase-hex> --session <current-runtime-UUID> --display <:20..99> --expect-uid 10323 --server-pid <X-socket-peer-PID> --server-birth <exact-proc-starttime> --seconds 30
```

The client creates its own session if necessary, verifies the X server peer, creates and raises one new window, and sets input focus only to that window. `READY` gives its PID/birth/SID, public nonce, and exact X window ID. Match these to the retained process and the window's `_NET_WM_PID`/`LOOPY_LATENCY_NONCE` before injecting. It does not enumerate other X windows. Closing or timeout destroys only that window; no server stop, socket unlink, settings change, or process-name kill occurs.

## Guest GTK3 Wayland

Copy `probe_termux_input_latency_wayland.py` and `probe_termux_input_latency_common.py` together into a new owned diagnostic directory visible to the existing guest. Requirements: guest Python3, PyGObject, GTK3, PyGObject Cairo integration, and the existing Wayland connection. Nothing installs these packages automatically. A missing dependency emits only `latency-fixture-unavailable` and is not a passing comparison.

Use the existing managed PRoot guard and the active Hyprland session environment; do not launch a second compositor or new D-Bus session. Keep `GDK_BACKEND=wayland`, the active socket/runtime directory and current GPU environment. Literal guest argument list:

```
/usr/bin/python probe_termux_input_latency_wayland.py --nonce <different-fresh-32-hex> --session <same-runtime-UUID> --expect-guest-uid 1000 --expect-native-uid 10323 --seconds 30
```

The native UID is read from `/proc/self/status`, separately from PRoot's simulated guest UID. `READY` must match the retained native PID/birth/SID. Require exactly one mapped client with that PID and the fixed public `Loopy latency <nonce>` title, then focus only that client. No private client titles, account data, URLs, or text are read.

## Controlled input and collection

Use the same fixed sequence for both clients: click within the center square, fixed public test-key down/up pairs, then bounded pointer movements within the fixture. Never send typing to an unverified or unfocused window. The clients record only event-kind enums and numeric time values. They never output key codes, characters, modifiers, pointer coordinates, surrounding windows or pixels. Only events delivered to the focused fixture are admitted. A maximum of 2048 events or 60 seconds bounds each run.

The line protocol is `READY`, consecutive `EVENT`, one or more `PAINT`, and `DONE`. `PAINT.ids` can contain multiple coalesced GTK events. ROOT must retain the actual child process, independently confirm its exit/reap and disappearance of its own window, restore the prior desktop focus, and require the current runtime token/owned compositor processes remain unchanged. `DONE.window_destroyed` alone is not OS-process retirement proof. No unknown scope resources may be removed.

After the child exits, collect the immutable owned0600 capture file with the **independently recorded** identity; do not trust an arbitrary file's READY row as the source of expected authority:

```
python3 probe_termux_input_latency_common.py --capture <owned-capture> --nonce <expected> --session <expected> --uid 10323 --pid <retained-native-PID> --birth <expected> --sid <expected>
```

Output is p50/p95/max for app-arrival gaps, source timestamp gaps, and event-to-callback durations, split by fixed event kind. Root's trial must explicitly require nonzero intended key/button/motion counts and `unpainted_events==0`; an empty report is not successful input acceptance.

**Measurement limits:** source timestamps and app CLOCK_MONOTONIC are not calibrated to each other, so no cross-clock one-way latency is calculated. ADB/injected events may have artificial timestamps. Source inter-event gaps and app inter-event gaps are separate. Native `XSync` means X requests were processed; GTK `after-paint` means the GTK drawing phase finished. Neither is physical scan-out or Android-to-glass latency, and they are different callback endpoints. Native per-event focus/peer validation and XSync add measurement overhead. Compare each path's gap distributions first; do not subtract the two callback means to invent a physical latency estimate. No glFinish, fence, polling, PHY, accessibility, or runtime policy is changed.

## Host verification

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_termux_input_latency.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/probe_termux_input_latency_build.py --output <fresh-build-directory>
```

The builder verifies the copied installed X11 header/library receipt and records source/compiler/ELF hashes. X11 header licenses remain in the captured upstream headers; no X11 library is bundled or redistributed. All fixture code is repository-owned. Existing diagnostics/build receipts remain immutable.
