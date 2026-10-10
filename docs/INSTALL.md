# Installation and daily use

[한국어](INSTALL.ko.md) · [English README](../README.md)

## Experimental installation scope

[v0.1.0-alpha.2](https://github.com/loopy-lim/termux-omarchy/releases/tag/v0.1.0-alpha.2) provides a pinned binary delivery path. **The candidate has not passed fresh-device GUI acceptance; `fullFreshInstallVerified` remains `false`.** No NDK or Android SDK is needed to acquire and apply the released assets.

Requirements:

- Android API 28+ on ARM64, under Android's primary user, with a Termux-accessible Adreno `/dev/kgsl-3d0` device.
- Native Termux from the matching **GitHub signing family**, using existing trusted, signed Termux APT sources. The first step prepares Git and native Python 3 if missing.
- Fresh desktop state: no earlier managed runtime, PRoot container, launcher or mismatched Termux:X11 companion.
- Android installation consent and a physical keyboard/trackpad for acceptance checks.

Plan for at least 8 GiB of free space for downloads and the unpacked guest. This is a planning margin, not a measured peak requirement.

F-Droid, Google Play and GitHub signing families are not interchangeable. A signature conflict is a blocker; do not uninstall or clear application data to force compatibility. Existing private desktop state and unexpected companion versions/files are preserved and refused. This release does not provide a migration procedure. See the [Termux installation guide](https://github.com/termux/termux-app#installation) and [Termux:X11 guide](https://github.com/termux/termux-x11).

## 1. Acquire the exact release inputs

Run in the **Android Termux app's native shell**, not inside Linux or PRoot. The initial package command is only for missing Git/Python and does not request a broad package upgrade:

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

The output must be a new absolute path under an owned directory; Termux home is suitable. The tool downloads 88 pinned files and copies 2 verified local manifests into the exact 90-file asset tree. It does not unpack or install them. Existing and partial directories are refused without removal; keep a failed attempt and choose a new path. Keep the full asset tree in native Termux storage so ownership and permission checks remain meaningful.

Hashes identify reviewed bytes, not trusted signers. Native APT uses its existing trusted keys; guest packages require valid detached signatures against the guest's existing trusted keyring. The tools do not disable signature checks or import arbitrary keys.

## 2. Install the exact APK through Android

Save work before changing Termux:X11: installing an application that shares Termux's UID can interrupt its processes. If an earlier desktop or mismatched companion exists, stop and review it before changing anything.

Request Android's installer for the exact acquired APK:

```sh
termux-open --view --content-type application/vnd.android.package-archive "$OMARCHY_ASSETS/input/termux-x11.apk"
```

This opens Android's consent flow; it does not approve installation automatically. Review the prompt and allow installation from this source if requested and intended. It does not require exposing Termux home or granting shared-storage access. Preserve application data and stop on any package/certificate conflict. The installer later checks the installed base APK's exact hash against this release; another nightly APK is not a substitute.

The public upstream development signing identity is not an exclusive publisher identity. Matching it allows shared-UID compatibility but does not authenticate this fork as an official Termux release. The APK and the source-built companion must stay paired. See [the signing notes](../input/full_build/SIGNING.md).

## 3. Prepare missing native dependencies

Return to the native Termux shell. If Android restarted it, return to the source directory and restore the asset path:

```sh
cd "$HOME/termux-omarchy-alpha2"
export OMARCHY_ASSETS="$HOME/termux-omarchy-v0.1.0-alpha.2-assets"
python3 -B installer/native.py --check
# Run only to install the reported missing native dependencies:
python3 -B installer/native.py --apply
python3 -B installer/native.py --check
```

The explicit apply refreshes signed APT metadata, adds the official X11 repository package if missing, and installs missing dependencies. Existing package versions are constrained; upgrades and removals are refused. PRoot-Distro 5.8 and reviewed 5.9.0 are supported. There is no full upgrade, global PIP install, APK install or automatic service start. A dependency conflict needs review rather than bypassing these guards. The exact release companion is handled by the asset installer, not a generic repository nightly.

## 4. Apply fresh desktop assets

```sh
python3 -B installer/install.py --check --assets "$OMARCHY_ASSETS"
python3 -B installer/install.py --apply --assets "$OMARCHY_ASSETS"
```

The check validates the source and complete local asset tree. Apply additionally verifies native context, API/KGSL access, required packages, the exact installed APK and fresh state. It installs only the audited local companion when absent, or accepts its exact reviewed version/files; another companion is preserved and refused. It then installs the desktop components and launcher. Unexpected hashes, ownership, symlinks and existing desktop state are blockers.

`installed-components` means the component installation finished. It does not mean a window appeared or that physical acceptance passed. The installer does not start the desktop, grant Android permissions, enable accessibility, change OEM policy or import personal profiles. Do not overwrite component files manually or remove existing state to bypass a refusal.

## 5. Start and check the desktop

```sh
loopy-omarchy start
loopy-omarchy status
loopy-omarchy doctor
```

Complete any intended Android keyboard/input-method or accessibility consent explicitly in Android settings. Generic KeyBridge/Caps configuration is unresolved and optional; its helper defaults off. The standard installation does not enable those mappings or copy a private opt-in marker.

On the target device, check displayed GPU output, audible playback, keyboard press/release and Hangul input, physical click, movement → two-finger scroll → release → movement, app return, and normal stop/start. OEM shortcuts and background process policy are separate choices with saved original values and restoration; see [permissions](PERMISSIONS.md). Fresh candidate GUI acceptance, sustained 60/144 FPS, measured latency and reboot behavior remain unverified.

## Daily use

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
