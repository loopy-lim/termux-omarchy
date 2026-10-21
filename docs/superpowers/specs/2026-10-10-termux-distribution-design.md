# Termux Omarchy distribution design

The user has authorized completing install and binary delivery preparation for
the public `loopy-lim/termux-omarchy` project. The existing source alpha remains
available while the next candidate is prepared. Publishing a source alpha did
not establish a fresh-device installation or rebuild the modified input APK.

## Deliverables

1. Build the current input changes from the full pinned upstream Termux:X11
   source and exact recursive dependencies. Historical APK patching is evidence
   of prior experiments, not an input to the new binary build.
2. Reproduce owned runtime/workflow payloads from the public source. Retain
   separate native, guest, configuration and package provenance.
3. Acquire third-party inputs only through pinned sources with verified length
   and SHA-256; do not rehost an unreviewed rootfs or proprietary application.
4. Prepare a release candidate only when source closure, hashes, signing policy,
   installation preflight and required validation evidence agree. Failure must
   preserve user state and leave the published alpha unchanged.

## Components and boundaries

`input/full_build/` owns upstream acquisition, source overlays, Android build
inputs and build evidence. `tools/prepare_runtime*` owns deterministic public
runtime payload generation. A distribution manifest records exact inputs,
license/source relationships and readiness gates. Installation remains explicit
and refuses absent, changed, unsupported or partially installed inputs.

The native Termux shell starts the desktop; PRoot hosts Arch Linux ARM with
Hyprland/Omarchy. Native Weston and guest Mesa graphics environments remain
separate. The currently used tablet and its Android policies are preserved while
build/install preparation runs on the host.

## Validation

Host tests cover deterministic output, hostile filesystem/archive inputs,
changed dependency hashes, preserved existing state and fail-closed behavior.
The full input APK needs a successful clean source build, source/license
inventory, package/signature inspection, and exact-artifact device acceptance.
A fresh runtime candidate needs isolated installation and GUI readiness; prior
user acceptance is not reused as acceptance of a new candidate.

## Release decision

Unsigned/source artifacts, signed APKs, native packages and complete installation
are distinct deliverables. A missing SDK, upstream source, trusted signature or
device test is a concrete unresolved gate. Record it; do not replace the gate
with a readiness claim. English remains the primary public documentation and
Korean is updated alongside it.
