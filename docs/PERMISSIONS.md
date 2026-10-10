# Android permissions and policy

[README](../README.md) · [Installation](INSTALL.md)

## Keyboard ownership

Android reserves some shortcuts before an ordinary application receives them. A focused display surface alone cannot claim every hardware key. The experiment combines the Termux:X11 keyboard service, a reviewed KeyBridge mapping and explicit handoff logic. Accessibility/keyboard-service consent must be completed by the user in Android settings.

Input capture must release correctly when leaving the desktop and recover on return. The modified input helper is off by default and validates a reviewed configuration opt-in; merely installing the APK does not enable Caps mappings. Never copy a private opt-in marker from another installation as a general setup procedure.

## Privileged options

| Mechanism | What it can help with | Boundary |
| --- | --- | --- |
| Foreground app and keyboard service | Deliver supported hardware shortcuts | Android/OEM may reserve others |
| Accessibility service | Reviewed key remapping/capture | Explicit Android consent; sensitive access |
| ADB or an explicitly authorized Shizuku operation | Supported shell-level settings/policy | Not granted by normal APK installation |
| OEM settings | Device-specific shortcuts | Verify the actual firmware consumer and restoration |
| Root/custom OS | Deeper input and process policy control | Separate device-specific project; not required or delivered here |

This release does not auto-grant permissions, configure device ownership, flash firmware, or silently change global Android policy.

## Meta+L on the test firmware

The OEM code on the tested firmware reads the current user's `Settings.System` value `keyboard_combo_win_l`, defaults to enabled when absent, and skips its lock-triggering power-key injection when the value is `0`. The existing installation recorded the original absent row, changed this one value, read it back, and received physical-user acceptance that Meta+L no longer locked Android and Meta+Caps+H/L still focused Linux windows.

This setting affects the **whole current Android user**, not only the Linux display. It does not disable the power button's lock behavior. Suppressing the lock side effect does not prove that ordinary Meta+L reaches Linux. Reboot persistence and other firmware variants were not accepted.

No generic setter is included: first verify the actual firmware/API behavior, record the Android user and original value, then apply only an explicitly chosen change and verify physical behavior. If the row was originally absent, restoration removes the row; if it existed, restoration writes its saved value. Do not treat a matching model name or a successful settings write as evidence that the setting is supported.

## Process limits

Android can kill background child processes independently of a Linux tool's own limits. Editors, extensions, language servers and browser helpers can create many subprocesses even when launched from one terminal.

The test installation raised the relevant Android limit through an authorized shell operation. It survived a short workload with hundreds of descendants and a user retry of editor synchronization. That is not unlimited-process, memory-pressure or reboot proof. A normal APK cannot silently grant itself the required shell policy access. No such policy change is applied by this source release.

Future policy tooling must save the original values, verify support, read back the result and provide restoration. It must also diagnose low-memory kills, application errors and PRoot/session failures separately; increasing a process count does not repair every termination.

## Network, sound and Android applications

The guest uses Android networking. Wi-Fi selection belongs to Android settings rather than a guest NetworkManager controlling the radio. Android app/settings bridges use supported intents and must fail visibly when a service is unavailable.

Audio uses the native host bridge; a ready sink is not evidence of audible output. Keep microphone/capture consent separate from playback. Browser/editor accounts, SSH authentication and Tailscale login stay on the device and are not imported from the developer's profile.
