# Validation scope

[README](../README.md) · [Development](DEVELOPMENT.md)

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

## Open acceptance work

- Complete clean-source APK build and corresponding-source distribution.
- Complete all pinned payload acquisition/build inputs and native dependency bootstrap.
- Install and start the full desktop on a truly fresh Android/Termux environment.
- Measure input latency and sustained FPS; 60 Hz requested and 144 FPS target remain distinct from achieved performance.
- Investigate intermittent network loss, browser closure and session termination.
- Verify screen return, rotation, sleep/wake, reboot and long-duration workloads.
- Confirm audible playback, VS Code GPU status, application/extension behavior, and actual Notion/Figma editing.

These are release gates for a future installable binary distribution. They do not block inspection or testing of this clearly scoped source alpha.
