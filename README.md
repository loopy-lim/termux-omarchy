# Termux Omarchy

[한국어](README.ko.md) · [Installation](docs/INSTALL.md) · [Distribution](docs/DISTRIBUTION.md) · [Development](docs/DEVELOPMENT.md) · [License inventory](legal/README.md)

A Wayland desktop experiment for Android tablets, built around Termux, Hyprland and the Omarchy desktop environment. The focus is practical keyboard and trackpad use, GPU rendering, and a familiar terminal workflow.

**Status: experimental binary delivery, [v0.1.0-alpha.2](https://github.com/loopy-lim/termux-omarchy/releases/tag/v0.1.0-alpha.2).** This release provides pinned runtime assets, a source-built Termux:X11 APK and its matching companion, with corresponding source archives. Users do not need an Android NDK. The candidate has **not passed fresh-device GUI acceptance**; `fullFreshInstallVerified` remains `false`.

The supported installation target is native ARM64 Termux from the matching GitHub signing family, under Android's primary user, on API 28+ with an accessible Adreno KGSL device. This is a fresh desktop installation path, not a migration for the earlier private installation. Read the [installation guide](docs/INSTALL.md) before applying assets.

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
- Pinned acquisition and fresh-only installation tools, payload manifests, license notices and corresponding source archives.

Personal profiles, SSH targets, passwords, browser data, extensions, signing keys, screenshots and raw device logs are excluded. Git contains source and checks. Binary delivery is separate through release assets and pinned upstream downloads.

## Download the experimental installation assets

Start in the Android **Termux app's native shell** with its existing trusted, signed APT sources. The first step installs Git/Python only if missing; it does not run a broad upgrade. Use a new absolute asset path inside Termux home:

```sh
if ! command -v git >/dev/null; then
  pkg install git
fi
if ! command -v python3 >/dev/null; then
  pkg install python
fi
cd "$HOME"
git clone --branch v0.1.0-alpha.2 --depth 1 https://github.com/loopy-lim/termux-omarchy.git termux-omarchy-alpha2
cd termux-omarchy-alpha2
python3 -B installer/verify.py
python3 -B tools/acquire_distribution.py --plan
export OMARCHY_ASSETS="$HOME/termux-omarchy-v0.1.0-alpha.2-assets"
python3 -B tools/acquire_distribution.py --output "$OMARCHY_ASSETS"
```

Acquisition downloads 88 pinned files and copies 2 verified local manifests into a 90-file tree. It does not install, unpack or grant permissions. An existing or partial output directory is preserved and refused. Follow [the installation steps](docs/INSTALL.md) to install the exact APK through Android consent, prepare missing native dependencies, and explicitly apply the assets.

## Start the installed desktop

In the **Android Termux app's own shell**, run:

```sh
loopy-omarchy start
loopy-omarchy status
loopy-omarchy doctor
```

These commands become available after the explicit installation steps. Cloning or downloading alone does not install the launcher. The installer does not start the runtime automatically.

| Command | Purpose |
| --- | --- |
| `loopy-omarchy start` | Start, or return to the existing session |
| `loopy-omarchy status` | Show session state |
| `loopy-omarchy doctor` | Inspect runtime prerequisites |
| `loopy-omarchy stop` | Stop the owned session after saving your work |

See [installation and daily use](docs/INSTALL.md) for prerequisites and [permissions](docs/PERMISSIONS.md) for Android input restrictions.

## Keyboard workflow

These are the intended mappings for the reviewed profile. Caps mappings require an optional, explicitly configured KeyBridge service and input handoff. A generic portable KeyBridge configuration remains unresolved, and the helper defaults off; Caps mappings are not enabled by the standard installation or Lua profile alone.

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

The complete exported APK source built offline for all four Android ABIs. The guard's offline source rebuild produced byte-identical binaries. These build results do not establish Android installation, input delivery or GUI acceptance for the release candidate.

Remaining limits include untested fresh-device bootstrap/GUI acceptance, intermittent network/session failures observed in development, unverified long-duration/reboot behavior, and software video codecs in the observed Chromium path. VS Code GPU acceleration and every extension's behavior remain unverified. Sustained 60/144 FPS and input latency have not been measured or accepted. The [validation record](docs/VALIDATION.md) separates host checks from physical acceptance.

## Develop

Host checks require Python 3.12+, zsh and JDK 17+.

```sh
python3 -B tools/check_publication.py
```

Run this in the source checkout. Host checks do not install anything on Android. Read the [development guide](docs/DEVELOPMENT.md) for component checks and [distribution preparation](docs/DISTRIBUTION.md) for rebuilding the release inputs.

## License and upstream projects

Original project glue and input modifications are licensed under [GPL-3.0-only](LICENSE), with upstream licenses and copyright notices retained for copied components. See [NOTICE](NOTICE.md) and the [component inventory](legal/README.md) for scope and exceptions.

This is an independent experiment. It is not an official release of Omarchy, Hyprland, Termux, Lenovo, Chromium or Microsoft. Their names identify the components being integrated; no endorsement is implied.
