# Installation and daily use

[한국어](INSTALL.ko.md) · [English README](../README.md)

## Distribution boundary

This source alpha is for inspection, regression testing and further development. It is **not a complete fresh-device installation release**. The historical setup bundle does not contain the latest input changes, and parts of the binary payload preparation are not reproducible from this checkout yet. Do not treat an older bundle as the current release.

The repository contains validated installation building blocks that check hashes, ownership, paths and existing state before writing. Missing inputs are a blocker, not a reason to disable those checks. Do not copy scripts into a live installation or replace its files manually: runtime ownership and recorded hashes must remain consistent.

## Required environment for future installation

- ARM64 Android and compatible Termux/Termux:X11 packages.
- Native Termux Python, PRoot-Distro and the native graphics/audio dependencies required by the pinned manifests.
- The pinned upstream Omarchy Android bundle and separately validated native/guest payloads.
- Matching Termux signing provenance when using a shared-UID Termux:X11 build.
- Physical keyboard/trackpad testing and Android consent for any optional input service.

The existing experiment uses the GitHub Termux signing family. Shared-UID APKs must have compatible signatures; mixing F-Droid, Google Play and GitHub packages is not a migration procedure. Back up existing Termux data before considering an installation-source change. The authoritative rules are in the [Termux installation guide](https://github.com/termux/termux-app#installation) and [Termux:X11 guide](https://github.com/termux/termux-x11).

See the tracked manifests and [input source notes](../input/README.md) for exact pins and outstanding build inputs. APKs and a complete root filesystem are deliberately absent from this release. The [development guide](DEVELOPMENT.md) explains how to close those gaps.

## Existing provisioned installation

Open Android **Termux**, then run `loopy-omarchy`. Run it from the native Termux shell, not a Foot terminal inside Linux or a separate PRoot login. It starts a stopped session or returns to the current one.

Use `loopy-omarchy status` and `loopy-omarchy doctor` for diagnosis. Save open work before `loopy-omarchy stop`. Returning from another Android app usually means reopening Termux:X11 or invoking the launcher again from foreground Termux. Automatic launch after an Android reboot is not verified.

If the pointer is not captured after returning, touch an empty part of the Linux display once. If Caps mappings alone fail, check that the configured KeyBridge input connection is active. Do not enable arbitrary accessibility services or write another device's private opt-in marker.

## Linux applications

On an installation that already contains the integration components, these commands run **inside Linux**:

| Purpose | Command |
| --- | --- |
| Chromium | `gtk-launch chromium` |
| User-installed VS Code integration | `loopy-vscode` |
| Notion web application window | `loopy-launch-webapp https://www.notion.so` |
| Figma web application window | `loopy-launch-webapp https://www.figma.com` |
| Remote connection menu | `omarchy-remote` |
| Android Wi-Fi settings | `omarchy-proot-settings wifi` |

Web application windows use Chromium with the browser chrome hidden; they are not embedded Android applications. Sign in directly on your device. Notion/Figma editing and every remote workflow are not part of the completed physical acceptance set.

For SSH development, create your own SSH alias, verify the server host key, and use your own authentication. A Tailscale connection must be available on Android if the server requires it. No server address, credential or SSH key is included here. VS Code and extensions must be obtained from their authorized upstream sources under their own terms.

The tested PRoot browser/editor integration needs sandbox compatibility compromises, including launch paths with `--no-sandbox`. PRoot is not a strong isolation boundary. Review the launcher source and use a remote development server for workloads requiring a full Linux security model.

## GPU and display sizing

The maintained profile separates native Weston Zink/Turnip from guest Mesa/Freedreno KGSL. Avoid setting a single global graphics override for both environments. GPU support depends on the actual SoC, Android kernel interface, driver build and application backend.

A renderer/device name alone is insufficient: confirm displayed pixels and application GPU status. The existing test device rendered pixels through native and guest Adreno paths, and Chromium used ANGLE/Vulkan. VS Code GPU status remains unknown; video codecs were software. A 60 Hz request does not establish sustained 60 FPS, and 144 FPS has not been accepted.

Keep logical scale, desktop pixel dimensions and browser/terminal zoom separate. The reviewed profile requests a 1.5 desktop scale; it is a starting point, not a universal tablet DPI. Future sizing changes must test window restoration, scrolling, screen edges and app return without modifying browser user data.
