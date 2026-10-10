# Complete-source build preparation

This driver reconstructs a new Android build from the complete pinned upstream
source and the public input overlay. It does not reconstruct the historical
signed APK bytes. The existing `input/build.py --build` remains a historical
reconstruction blocker; this separate path records a fresh source-build attempt.

No old APK, DEX, native library, compilation stub, private signing key, device
configuration, remapper marker or device receipt is an input. Preparation fetches
Termux:X11 `6d3c6883265b4ec8092673e6d2d61ef86cab5405` and its pinned recursive
submodules, checks the exact native gitlinks and preserved upstream references,
applies the hash-checked public overlay with zero fuzz, and checks the maintained
Java postimages. Native patches included by upstream CMake remain part of that
upstream source tree.

Three additional source patches keep this path self-contained: shell-loader derives
its compatibility metadata from the pinned public certificate rather than opening
a signing keystore, and xkbcomp uses a quote-only X11 include path so its internal
`Xlocale.h` does not shadow Android NDK 29's system `xlocale.h`. The included patch
wrapper forces reverse probes to respect their direction on macOS and GNU patch.
Preparation removes the upstream public test keystore before compilation.
The companion keeps its existing package name but uses fork attribution and the
fixed version `1.03.01+omarchy.input-alpha.1-0`; its receipt pins both wrapper
scripts and the loader APK, including their installed permissions.

## Commands

Run these from the repository root. Use a new absolute work directory outside
this public source checkout. Outputs and logs stay in that work directory.

```sh
python3 -B input/full_build/driver.py plan
python3 -B -m unittest discover -s tests/input -p test_full_build.py

python3 -B input/full_build/driver.py all \
  --work-dir /tmp/termux-omarchy-source-attempt-01 \
  --sdk-source "$ANDROID_SDK_ROOT" \
  --java-home "$JAVA_HOME" \
  --install-missing
```

`prepare` fetches and audits source without requiring an Android SDK.
`build` accepts a work directory previously completed by `prepare`, with no
earlier build attempt. `all` performs both in a new directory. A failed build
requires a new preparation; the driver does not reuse stale build outputs.

The build requires a JDK compatible with the pinned Gradle 9.7.1 and AGP 9.3.1,
POSIX `patch`, Git, Python, and Bison. Upstream's workflow selects JDK 17; the
complete build was also exercised with JDK 21. Native compilation uses Android NDK 29.0.14206865 and CMake
3.22.1. The upstream Gradle wrapper has its own SHA-256 distribution lock.

The provided SDK must already contain:

- `platforms/android-34`
- `build-tools/36.0.0`
- `cmake/3.22.1`
- `cmdline-tools/latest`
- previously accepted `licenses/android-sdk-license`

Those package directories and existing license files are copied into a new SDK
directory under the attempt. Gradle and Android user caches are isolated there
as well. The supplied SDK is read only. The driver does not run `sdkmanager
--licenses`, send affirmative input, or accept new license terms.
`--install-missing` permits a download of the exact pinned NDK using those
existing license copies; the subprocess receives closed standard input and the
driver checks that license files are unchanged. If a new license is required,
the attempt fails. Automatic SDK downloads by Gradle are disabled.

## Outputs and evidence

`prepared.json` records upstream and native tree identities, the public overlay
hash, source changes and driver controls. `sdk-provenance.json` records the SDK
packages copied and hashes of existing license files. Each command has a log and
its actual exit status. `prepare-receipt.json` or `build-receipt.json` records
failure as failure; partial downloads and successful host tests are never APK
build evidence.

The Gradle initialization script disables application signing before variant
creation. `termux-public-certificate.txt` contains only the public X509 certificate;
the driver verifies its SHA-256 and derives the loader's Java certificate hash.
The build source contains no signing keystore and no signing task is requested.
After a successful build, the driver rejects APKs containing a JAR signature or
an Android APK signing block. Its output is an **unsigned validation artifact**
and a companion package. It is not an installable public release.

This attempt uses the explicit version
`1.03.01-6d3c688-input-source-alpha`, retaining upstream version code 15. It does
not impersonate the date-derived historical version. The common Java input
changes apply to all built ABIs; the native Hangul source change also applies to
every built ABI, unlike the historical arm64-only binary repair.

A successful command produces `UNSIGNED_APK_BUILT_NOT_AUDITED`. Corresponding
source/legal review, packaged DEX/JNI behavior checks, matching companion/signing
identity, installation checks and current physical-device acceptance remain
separate gates. The driver never signs, installs, publishes, enables an
accessibility service or creates an opt-in marker.

## Corresponding-source archive

After the exact build succeeds, export its prepared source:

```sh
python3 -B input/full_build/runtime_sources.py \
  --prepared-dir /tmp/termux-omarchy-source-attempt-01 \
  --java-home "$JAVA_HOME"
python3 -B input/full_build/resource_inputs.py \
  --prepared-dir /tmp/termux-omarchy-source-attempt-01
python3 -B input/full_build/archive.py create \
  --prepared-dir /tmp/termux-omarchy-source-attempt-01 \
  --output /tmp/termux-omarchy-complete-source.tar.gz
```

The exporter reads pinned Git blobs for upstream and all 16 native repositories,
then verifies and copies the recorded prepared source postimages. Native generated
files are regenerated by the preserved upstream CMake patches. It includes every
tracked upstream component's original license/notice files, the public overlay,
build controls, dependency identities and instructions. Signing keys, SDKs,
personal paths, Git databases and generated build state are omitted. Component
licenses remain distinct; this is not a blanket GPL relicensing claim.

The runtime-source helper resolves the exact app and loader runtime artifact
graphs offline from the completed build, then fetches matching source JARs only
from official Google Maven or Maven Central endpoints. It records original runtime
artifact hashes, source URL/size/hash, published POM licenses and source/legal file
counts. Missing sources or license metadata prevent a complete source archive.
Build-tool dependency sources are excluded; their pinned binaries and published
legal metadata are documented separately. The archive includes those complete
runtime source JARs and POMs, along with the native component source trees.
The resource helper preserves each runtime AAR's original uncompiled manifest,
XML/image resources, assets, symbols, proguard/annotation/notices and available
published module metadata, with per-file hashes and exact AAR provenance. Binary
XML, compiled resource tables, native libraries or bundled compiled JARs require
their corresponding source and block completion. Published `classes.jar` is covered
by the matching source JAR; `lint.jar` is an external build tool.

The documented rebuild compiles this application against its pinned published
dependencies. Runtime Java/Kotlin sources and original resource inputs are retained
for review and modification; this archive does not claim to independently rebuild
every external dependency library or the Android/Gradle toolchain.

The exported public project is limited to input source/build controls/tests,
their two input manifests, and the project license/legal notices. Delivery and
runtime manifests are excluded to keep archive hashes from referring to themselves.

The extracted archive's `BUILD.md` gives a verified prepared-source build route
that requires no Git source fetch. An offline build additionally requires the
exact cached Gradle distribution and Maven dependencies, plus the installed SDK
and NDK. A general SDK/Gradle installation alone is insufficient for offline Maven
resolution. The helper can copy only Gradle distribution/dependency caches into
the isolated build directory; host properties and init scripts are never copied.
