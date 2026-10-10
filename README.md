# Termux Omarchy

[한국어](README.ko.md) · [Installation](docs/INSTALL.md) · [Development](docs/DEVELOPMENT.md) · [License inventory](legal/README.md)

A Wayland desktop experiment for Android tablets, built around Termux, Hyprland and the Omarchy desktop environment. The focus is practical keyboard and trackpad use, GPU rendering, and a familiar terminal workflow.

**Status: source-only developer alpha.** This repository preserves the runtime, input fixes and configuration developed on one Lenovo Y900 test device. It does **not** currently provide a complete installer for a new tablet or a downloadable modified APK. Read the [installation boundary](docs/INSTALL.md) before using any installation code.

## How it works

```text
Android
  Termux + Termux:X11 (presentation and Android input)
    native Weston (Wayland host, Zink/Turnip graphics)
      Arch Linux ARM through PRoot
        Hyprland (Wayland window manager) + Omarchy shell
          Foot, Chromium/Xwayland, user-installed development tools
```

Hyprland manages the Linux windows. Termux:X11 presents the nested desktop on Android; this is not a direct Android Wayland display driver. PRoot shares the Android kernel and does not provide a separate Linux kernel, systemd boot or direct Wi-Fi device ownership.

## What is included

- Owned-session runtime control, bounded subprocess handling, installation validation and recovery code.
- The latest portable shell, tmux and Hyprland workflow sources.
- Source for the Termux:X11 keyboard handoff and trackpad gesture/lifecycle patches, with regression checks and provenance notes.
- Explicit source and payload manifests, license notices, and a development checklist for completing reproducible distribution.

Personal profiles, SSH targets, passwords, browser data, extensions, signing keys, screenshots and raw device logs are excluded. APKs, root filesystems and third-party package binaries are not distributed here.

## Open an already provisioned desktop

In the **Android Termux app's own shell**, run:

```sh
loopy-omarchy
```

This command belongs to a separately provisioned installation. Cloning this source repository does not install it.

| Command | Purpose |
| --- | --- |
| `loopy-omarchy start` | Start, or return to the existing session |
| `loopy-omarchy status` | Show session state |
| `loopy-omarchy doctor` | Inspect runtime prerequisites |
| `loopy-omarchy stop` | Stop the owned session after saving your work |

See [installation and daily use](docs/INSTALL.md) for prerequisites and [permissions](docs/PERMISSIONS.md) for Android input restrictions.

## Keyboard workflow

These are the intended mappings for the reviewed profile. Caps mappings also require a compatible, explicitly configured KeyBridge service and the input handoff; they are not enabled by the Lua profile alone.

| Keys | Action |
| --- | --- |
| Alt+Space | Omarchy menu |
| Alt+Tab / Alt+Shift+Tab | Switch Linux windows |
| Meta+1…0 / Meta+Shift+1…0 | Select workspace / move a window |
| Caps+H/J/K/L | Arrow keys |
| Caps+D / Caps+F | Previous / next existing workspace |
| Meta+Caps+H/J/K/L | Focus a window in that direction |
| Alt+Caps+H/L | Home / End |
| Alt+Caps+K/J | Ctrl+Home / Ctrl+End |
| Alt+C / Alt+V | Copy / paste through the profile's application mappings |
| Alt+- / Alt++ (or Alt+=) | Foot font size down / up |
| Alt+1…0 | tmux window selection |

The Android Meta+L lock shortcut is a separate OEM policy issue. A setting was verified on the test firmware; it is not automatically applied to other devices. See [permissions and policy](docs/PERMISSIONS.md).

## Verification and limits

On the existing test installation, the user confirmed trackpad movement after scrolling, physical click, Alt+Tab, Caps workspace switching, Home/End navigation, and suppression of the OEM Meta+L lock shortcut. Earlier graphics probes rendered pixels using Adreno GPU paths. These observations do not establish a fresh-install guarantee, all-application compatibility, sustained 60/144 FPS, or measured input latency.

Current limitations include incomplete fresh-device bootstrap, incomplete modified-APK build closure, intermittent network/session failures under investigation, unverified long-duration/reboot behavior, and software video codecs in the observed Chromium path. VS Code GPU acceleration and every extension's behavior remain unverified. The [validation record](docs/VALIDATION.md) separates host checks from physical acceptance.

## Develop

Host checks require Python 3.12+, zsh and JDK 17+.

```sh
git clone https://github.com/loopy-lim/termux-omarchy.git
cd termux-omarchy
python3 tools/check_publication.py
```

The host checks do not install anything on Android. Read the [development guide](docs/DEVELOPMENT.md) for component tests and the steps required before distributing binaries.

## License and upstream projects

Original project glue and input modifications are licensed under [GPL-3.0-only](LICENSE), with upstream licenses and copyright notices retained for copied components. See [NOTICE](NOTICE.md) and the [component inventory](legal/README.md) for scope and exceptions.

This is an independent experiment. It is not an official release of Omarchy, Hyprland, Termux, Lenovo, Chromium or Microsoft. Their names identify the components being integrated; no endorsement is implied.
