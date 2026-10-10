# Portable guest source inputs

These reviewed text files build the guest audio/Android settings and Korean
input payloads. They contain no user rootfs, account state, SSH configuration,
editor plugins, or device journals. The builder reads these published files
and the shared public runtime sources; it does not read an installed guest or
an older payload archive.

The network and Bluetooth panels, QML module list, browser launcher and
Hyprland defaults derive from the Omarchy Android v0.1.1 guest. Its pinned
base bundle and component commit are recorded in
[the runtime prerequisites](../manifests/runtime-prerequisites.json).
The matching original file hashes remain the installer's `before` contracts.
The changes route unavailable guest hardware controls to Android, use the
owned audio endpoint, and adapt the nested graphics/browser session.

Omarchy-derived files are covered by the retained
[Omarchy MIT notice](../legal/licenses/omarchy-MIT.txt).
`AndroidSettings.qml`, the audio worker and its launcher, and the Korean input
configuration are Loopy adaptations published under the repository license.
The generated manifests preserve original hashes and target modes so the
installer continues to refuse changed user configuration.

Source preparation proves reproducible payload bytes. It does not establish
QML rendering, trusted package signatures, Android consent, GUI readiness, or
fresh-device installation acceptance.
