# Validation scope

[한국어](VALIDATION.ko.md) · [README](../README.md) · [Development](DEVELOPMENT.md)

This document separates the existing device experiment from the public source alpha. Raw private device logs, identifiers, screenshots and account data are not distributed.

## Existing device observations

The following were observed during development on one Lenovo Y900 test installation, not a fresh installation from this public repository:

| Area | Evidence boundary |
| --- | --- |
| Desktop | Native Weston → Arch ARM Hyprland → original Omarchy shell; bar/menu displayed |
| Trackpad | User accepted movement, two-finger scrolling followed by movement, physical click and Alt+Tab; later input changes retained the accepted path |
| Caps navigation | User accepted arrow mappings and Alt+Caps Home/End/document navigation |
| Workspaces | User accepted Caps+D/F repeated switching after all input observers were disconnected; initial failures and the first recovery cause remain unresolved |
| Directional focus | Meta+Caps+H/L accepted after OEM lock suppression; J/K were not part of that final physical test |
| OEM lock | User accepted that Meta+L kept Linux visible after the current-user setting change |
| GPU | Earlier native Zink/Turnip and guest Freedreno KGSL probes rendered pixels on Adreno; Chromium ANGLE/Vulkan rendered test content |
| Editor | VS Code window and remote connection observed; user synchronization retry kept the desktop running after process-policy changes |
| Language | User accepted physical Korean/English switching and input in Chromium |

Historical physical acceptance is not automatically transferred to new source edits, a new APK, another firmware, or a source-only installer. Some profile mappings remain intended/configured rather than individually reaccepted on the final artifact.

## Host validation

The source release's canonical check is `python3 tools/check_publication.py`. It runs inventory/syntax/link/publication checks and included runtime/input regression suites. GitHub CI repeats it from a clean checkout. A pinned Gitleaks scan checks recognizable credentials. Passing checks do not prove that no private information exists; the curated file list also receives manual review.

Initial source-alpha host checks on 2026-10-10 passed with Python 3.14 and JDK 17:

| Check | Result |
| --- | --- |
| Publication inventory | 170 text files; source syntax and local documentation links checked |
| Retained license texts | 6 byte/hash-verified copies |
| Runtime regressions | 33 tests passed |
| Input source/process/overlay | 9 tests passed |
| Keyboard handoff | 24 direct-listener + 29 accessibility cases passed |
| Trackpad scroll/lifecycle | 22 scroll cases + 16 lifecycle groups passed |
| Publication adversarial cases | 5 tests passed, including tracked hidden APK, symlink, credential, escaped link and changed license |
| Gitleaks | Version 8.30.1, no findings after one exact public keymap-checksum exception |

The input suite also requires the historical direct-listener and lifecycle baselines to fail in their known cases before the corrected source passes. Those expected failures are printed in the test log and are not current-source failures. DEX preservation tooling is supplied as source; compilation of its patch/test classes with pinned dependencies is separate from real DEX/APK execution.

## Alpha.2 build and delivery preparation

On 2026-10-10, the new candidate was built from the pinned upstream commit and
all 16 recursive native trees, with no historical APK, compilation stub or
signing key in the build source. Gradle executed 102 tasks and built four ABIs.
A second clean build from the extracted corresponding-source archive passed
offline using the documented SDK and exact external dependency caches.
Non-native APK payloads, including DEX, resources and manifest, matched; native
libraries varied across build paths, so APK byte reproducibility is not claimed.
The matching companion payload files were byte-identical in the rebuild.

The separate signing check verified the recorded public development certificate,
v2/v3 signatures, 16 KiB alignment, and all 440 unchanged unsigned payload entries.
The signed candidate SHA-256 is recorded in `manifests/input-sources.json`; it has
not received physical acceptance. A source-only offline guard rebuild reproduced
the three guard artifacts and source archive byte-for-byte, and the editable
talloc relinking route passed.

All 74 external pins were downloaded and checked. All 36 guest packages passed
detached-signature verification against the base rootfs trusted keyring. The
prepared Weston, guest, workflow and IME payloads passed the real installer
admission checks. Acquisition and fresh-only installation wrappers preserve
existing runtime/configuration/package state and require the exact companion and
APK. These are build and host checks, not fresh GUI installation evidence.

Current alpha.2 host checks passed with 237 text files, 8 retained license texts,
56 runtime source inventory entries and 111 input source inventory entries:

| Check | Result |
| --- | --- |
| Runtime and installation regressions | 92 passed |
| Input inventory/overlay/build-source regressions | 30 passed, including 21 complete-source build/export cases |
| Keyboard handoff | 24 direct-listener + 29 accessibility cases passed |
| Trackpad | 22 scroll cases + 16 lifecycle groups passed |
| Publication/download/guard/delivery regressions | 38 passed |
| Local installation kit | All 90 files assembled and accepted by the real read-only installer check |
| Gitleaks | 8.30.1, no findings; only three exact public-checksum exceptions |

The released APK source archive is `termux-x11-source.tar.gz` (18,052,499 bytes,
SHA-256 `eb5ed331fd96a36d6ad5ceed93d31cf7aa9bd57fc0c2f0766ddc9d8646430b89`).
Its 6,237 manifest entries include all 16 native source trees, 62 matching Java
runtime source JARs, 984 original AAR resource inputs, 38 module metadata files,
and retained licenses/POMs. Resource review found plain XML and original PNG
inputs, with no compiled resource/native/bundled-code gaps. Exact candidate and
source identities remain separate from physical acceptance.

## Open acceptance work

- Physically accept the exact new signed APK and source-built companion.
- Exercise the native dependency bootstrap and full apply path on a fresh device.
- Adapt and verify optional generic Caps remapper cooperation.
- Install and start the full desktop on a truly fresh Android/Termux environment.
- Measure input latency and sustained FPS; 60 Hz requested and 144 FPS target remain distinct from achieved performance.
- Investigate intermittent network loss, browser closure and session termination.
- Verify screen return, rotation, sleep/wake, reboot and long-duration workloads.
- Confirm audible playback, VS Code GPU status, application/extension behavior, and actual Notion/Figma editing.

These are gates for a stable fresh-device release. Alpha.2 provides experimental
build artifacts and installation code with `fullFreshInstallVerified: false`;
it does not transfer acceptance from the earlier private device installation.
