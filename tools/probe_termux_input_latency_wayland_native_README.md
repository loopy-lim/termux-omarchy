# Native Wayland input baseline

This diagnostic adds no packages and changes no runtime, graphics, input, or desktop configuration.
It uses the installed Termux Bionic `libwayland-client.so` to connect directly to the current
guest Hyprland compositor. The client itself runs outside PRoot: this isolates the compositor
path, and does not measure the PRoot cost inside a normal guest application.

Build with the separate `probe_termux_input_latency_wayland_build.py`. It verifies all six
public device-copied header/library files, the cached xdg-shell XML, and the Cargo.lock
crate checksum before compiling. Full xdg-shell interface message tables are mechanically
derived from that pinned XML; its MIT copyright and permission notice are retained in
`xdg-shell-protocol.c`. Existing X11/GTK fixture sources and their collector remain unchanged.

ROOT may deploy the exact artifact and the original common module plus the new frame adapter
into a fresh owned private job. Keep the process through a retained `Popen` with a new session;
do not invoke the desktop supervisor's start or stop operation. Preserve the existing Android
context and use the existing Termux `PREFIX/lib` for the native dynamic loader.

Literal arguments are:

```text
probe-input-latency-wayland --nonce <32-lowerhex> --session <current-session-uuid>
  --display <absolute-current-Hyprland-Wayland-socket> --expect-uid 10323
  --server-pid <verified-Hyprland-peer-PID> --server-birth <verified-starttime>
  --seconds 40
```

The socket is the Hyprland client socket under the owned short runtime, not Weston's
`wayland-omarchy` socket. ROOT must verify the live runtime/session marker, socket identity,
and peer lineage before launch, and fence them again after the trial. The client verifies
its own UID/PID/birth/session and the exact socket peer UID/PID/birth. It creates only its
own SHM buffers and `xdg_toplevel`, with app-id/title `loopy-latency-<nonce>`.

READY follows the first configure and initial frame callback. Before injecting fixed public
input, ROOT must independently match the sole nonce app-id, native PID/birth, visible client
geometry and focus using the current compositor's metadata. Client keyboard/pointer callbacks
record events only while the corresponding seat focus is the owned surface. Key codes, keymap
bytes, coordinates, node text and other windows are never recorded.

The window is 640×420 logical pixels and its SHM buffer is 640×420. With desktop scale1.25,
its physical area differs from the 640×420 native X11 client. The two SHM buffers are rewritten
only after their exact `wl_buffer.release`; at most one frame callback is outstanding. Pending
public event IDs are coalesced into that frame; at most2048 events and60seconds are accepted.

After reaping the exact process, use `probe_termux_input_latency_frame.collect(capture, identity)`
on its immutable owned0600 capture. Require nonzero key/button/motion events for this trial.
The adapter preserves the original collector's strict identity/field/order/bounds checks and
labels the backend `wayland-frame-callback`, callback `wl_surface.frame-done`.

`frame.done` schedules a next frame; it is not a physical presentation timestamp or proof that
GPU work has completed. Native X11's XSync and this callback have different meanings. Compare
arrival gaps for matched injection schedules, and report each callback distribution separately.
Physical latency and physical FPS remain unmeasured. Reap, confirm nonce-window absence,
and restore the prior exact live focus before declaring cleanup successful.
