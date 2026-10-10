# Distribution preparation

[한국어](DISTRIBUTION.ko.md) · [Installation](INSTALL.md) · [Permissions](PERMISSIONS.md)

`v0.1.0-alpha.2` offers experimental binary delivery separately from the source
Git tree. **No fresh-device GUI acceptance has been completed for the candidate;
`fullFreshInstallVerified` remains `false`.** Source/build checks, APK signatures,
Android permissions and physical acceptance are separate evidence.

## Acquire released assets without an NDK

Use the pinned tag and native ARM64 primary-user Termux environment described in
[installation](INSTALL.md), with Git and native Python 3 already available. From
that source checkout:

```sh
python3 -B installer/verify.py
python3 -B tools/acquire_distribution.py --plan
export OMARCHY_ASSETS="$HOME/termux-omarchy-v0.1.0-alpha.2-assets"
python3 -B tools/acquire_distribution.py --output "$OMARCHY_ASSETS"
python3 -B installer/install.py --check --assets "$OMARCHY_ASSETS"
```

The catalog has 15 project release artifacts and 74 external inputs. The final
tree omits the build-only Weston `.deb`: acquisition downloads 88 files and
copies 2 hash-checked local package manifests, producing exactly 90 files.
Project artifacts include the runtime payloads, guard binaries, exact APK and
companion, and both corresponding-source archives. External runtime inputs are
the pinned base bundle and 29 tool/7 IME package-and-signature pairs.

The output must be a new absolute path under an owned directory; Termux home is
suitable. Existing and partial output is preserved and refused. No acquisition
command installs, unpacks, starts the desktop or grants Android permissions.
Plan for at least 8 GiB free as a preparation margin, not a measured peak.
Continue with [APK consent, missing native dependencies and explicit fresh
application](INSTALL.md); a successful asset check alone is not installation.

## Maintainer route: prepare the 74 external build inputs

Run all host commands below from this repository's root. Use Python 3.12+ and a
new private directory outside the source checkout. This creates a canonical path
on both macOS and Linux; existing mismatched files are refused rather than replaced.

```sh
export PREP_DIR="$(python3 -B -c 'from pathlib import Path; import tempfile; print(Path(tempfile.mkdtemp(prefix="termux-omarchy-dist-")).resolve())')"
mkdir -m 700 "$PREP_DIR/downloads"
python3 -B installer/verify.py
python3 -B tools/fetch_dependencies.py --check
python3 -B - <<'PY'
import json, os, subprocess, sys
from pathlib import Path
catalog = {name: row for name, row in
           json.loads(Path('manifests/downloads.json').read_text())['artifacts'].items()
           if row['purpose'] != 'project-release-artifact'}
assert len(catalog) == 74
for artifact in sorted(catalog):
    subprocess.run([sys.executable, '-B', 'tools/fetch_dependencies.py',
                    '--fetch', artifact, '--directory', os.environ['PREP_DIR'] + '/downloads'],
                   check=True)
PY
```

These external inputs are the Omarchy Android 0.1.1 base bundle, Weston host package,
29 guest tool packages, 7 IME packages, and each guest package's detached
signature. All 74 pinned downloads were acquired and their size/SHA-256 checked
during release preparation (1,223,199,036 bytes, about 1.14 GiB). This is not the
total installation size or a measured peak. Availability can change; a failure must be
resolved by reviewing the pin, not substituting a newer package. Repeating the
loop validates and reuses matching local files. The downloader does not unpack,
execute, install, or cryptographically verify package signatures.

## Prepare the runtime payloads

```sh
python3 -B tools/prepare_runtime_payloads.py --check \
  --weston-deb "$PREP_DIR/downloads/weston_14.0.2-3_aarch64.deb"
python3 -B tools/prepare_runtime_payloads.py \
  --output "$PREP_DIR/runtime" \
  --weston-deb "$PREP_DIR/downloads/weston_14.0.2-3_aarch64.deb"
```

This creates the pinned manifests and deterministic payload archives for 15
workflow files, 87 native Weston files, 11 guest integration files, and 5 IME
configuration files. Generated files consume reviewed public sources and the
pinned Weston package. No private profile or existing root filesystem is an
input. `preparation.json` is written only after the artifacts are durable. An
existing output directory is refused; preserve a failed attempt and choose a
new output path. Neither command installs or starts the runtime.

## Build the PRoot guard

Supply Android NDK **27.1.12297006** as `GUARD_NDK_ROOT`, plus `make` and `patch`.
The guard targets Android ARM64 API 28 and requires that runtime API or later.
This builder fetches three separately locked public source archives; they are
not part of the 74-file runtime catalog.

```sh
python3 -B native/guard/build.py --check
python3 -B native/guard/build.py --prepare --output "$PREP_DIR/guard-source"
python3 -B native/guard/build.py --build \
  --ndk "$GUARD_NDK_ROOT" --output "$PREP_DIR/guard-build"
```

Keep `arm64-v8a/proot`, `arm64-v8a/loader`, `arm64-v8a/libandroid-shmem.so`,
`receipt.json`, and `guard-corresponding-source.tar.gz` together. The source
archive and license notices must accompany guard binary distribution. Its
included builder also supports offline rebuilding and modified-library
relinking; see [the guard instructions](../native/guard/README.md).
`BUILT` confirms compilation and ELF checks, with no device runtime claim. The
release guard passed an offline corresponding-source rebuild with byte-identical
binaries.

## Build the Android input application from complete source

This is a fresh unsigned build path, separate from historical APK reconstruction.
Review [the build prerequisites](../input/full_build/README.md) first. Supply
`ANDROID_SDK_ROOT` and a compatible `JAVA_HOME`; the SDK must already contain the
listed platform, build tools, CMake, command-line tools and accepted licenses.
The driver uses Android NDK **29.0.14206865**, distinct from the guard's NDK.

```sh
python3 -B input/full_build/driver.py plan
python3 -B input/full_build/driver.py prepare --work-dir "$PREP_DIR/input-source"
python3 -B input/full_build/driver.py all \
  --work-dir "$PREP_DIR/input-build" \
  --sdk-source "$ANDROID_SDK_ROOT" --java-home "$JAVA_HOME" --install-missing
```

`--install-missing` allows the pinned NDK download using existing license
acceptance. It does not accept new terms or modify the supplied SDK. Every build
attempt needs a new work directory. Inspect the actual build receipt: only
`UNSIGNED_APK_BUILT_NOT_AUDITED` establishes unsigned output. For a new candidate,
review source/licenses, packaged DEX/JNI, matching companion metadata and signing
before delivery. Never install an unsigned artifact or use compilation stubs as
application code. The released APK is a separately signed candidate, not this
driver's unsigned output.

Export complete corresponding source after the successful build:

```sh
python3 -B input/full_build/archive.py create \
  --prepared-dir "$PREP_DIR/input-build" \
  --output "$PREP_DIR/termux-x11-source.tar.gz"
```

The exported source archive passed offline builds for all four Android ABIs.
Its `BUILD.md` describes rebuilding without Git source fetch; offline Gradle
resolution still needs the exact distribution/dependency cache and SDK/NDK.
This build evidence does not establish candidate GUI or physical input acceptance.

The shared-UID application requires the **GitHub Termux signing family** and a
compatible certificate. F-Droid and Google Play installations are not
interchangeable. The upstream development identity is public and untrusted;
matching it does not authenticate this fork as an upstream release. See
[the signing identity notes](../input/full_build/SIGNING.md). Do not uninstall,
clear data, or change an existing package's shared UID to force compatibility.

## Check native Termux prerequisites

Run these only in the primary Android user's **native ARM64 Termux shell**,
with native Python 3 already installed, from a verified copy of this source.
The checker refuses a Linux guest shell, another Android user, and a traced
process. The guard raises the desktop runtime's minimum to Android API 28.

```sh
python3 -B installer/native.py --check
# Explicitly install the reported missing native packages:
python3 -B installer/native.py --apply
python3 -B installer/native.py --check
```

The apply command uses existing APT keys and signed metadata, enables the
official X11 repository package if absent, and installs missing graphics,
audio, X11, Weston dependencies and PRoot-Distro packages. It simulates the
transaction first, constrains every installed package to its current version,
and refuses removals or upgrades. PRoot-Distro 5.8 and reviewed 5.9.0 are
supported; future versions require review. There is no full upgrade, global
PIP install, service launch, APK installation, or personal configuration import.
If old dependency constraints cannot be satisfied, stop and review the plan.
The matching Termux:X11 companion is handled separately by the final delivery
assets together with its exact APK. Native prerequisites do not install an
arbitrary repository nightly companion. The runtime still requires its
`termux-x11` executable after component installation.

## Trust and Android consent

A SHA-256 pin proves agreement with a reviewed byte identity. It does not prove
who signed a package. Downloaded `.sig` files must still validate against the
guest's already trusted Arch Linux ARM keyring; the installer requires trusted
signatures and does not import arbitrary keys or disable signature checks.
Native APT trust and APK certificate compatibility are separate checks.

Before accepting a device installation:

1. Review the exact signed APK, its source/build receipt, companion and
   certificate. Verify compatibility with the installed Termux family and
   preserve application data. The runtime assets must match that exact APK.
2. Complete any requested Android installation, keyboard/input-method and
   accessibility consent in Android settings. Enable only the reviewed service
   and mapping you intend to use. Caps-remapper cooperation defaults off; another
   device's opt-in marker or mapping is not a portable configuration.
3. Treat OEM shortcut policy, background process limits and any ADB/Shizuku
   operation as separate explicit choices. Record original values, verify the
   current firmware consumer, and retain a restoration path. The preparation
   tools do not grant these privileges or change Android policy.
4. Test startup, stop/restart, app return, pointer capture, key press/release,
   touchpad scrolling, Hangul input, displayed GPU output and audible playback
   on the target device. A build receipt or JNI success value cannot replace
   these checks. See [the permission boundaries](PERMISSIONS.md).

## Assemble reviewed local inputs

The maintainer route can assemble the same closed tree from local inputs. Set
`SIGNED_INPUT_APK` and `INPUT_COMPANION_DEB` to the absolute paths of the reviewed
signed APK and matching source-built companion:

```sh
python3 -B tools/prepare_distribution.py \
  --downloads "$PREP_DIR/downloads" --payloads "$PREP_DIR/runtime" \
  --guard "$PREP_DIR/guard-build" --apk "$SIGNED_INPUT_APK" \
  --companion "$INPUT_COMPANION_DEB" \
  --apk-source "$PREP_DIR/termux-x11-source.tar.gz" \
  --output "$PREP_DIR/installation-assets"
python3 -B installer/install.py --check --assets "$PREP_DIR/installation-assets"
```

The assembler accepts only the exact hashes in `manifests/distribution.json`.
An independent APK build can differ in bytes and needs a reviewed new candidate;
do not refresh expected hashes automatically. Keep source archives and notices
available alongside every distributed binary version. Use the [installation
guide](INSTALL.md) for explicit native preparation, Android consent and fresh-only
apply. Runtime start, Android grants and physical acceptance are never implied
by a packaging receipt. Keep `fullFreshInstallVerified: false` until fresh-device
acceptance is actually completed.
