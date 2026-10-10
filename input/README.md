# Input source: developer alpha

This directory preserves the reviewed Java input changes and the complete known
patch sequence used for a local Termux:X11 experiment. It contains source and
host fixtures. It does not contain an APK, native library, signing key, opt-in
marker, captured input, device receipt or user configuration.

**A new source-built experimental APK and matching companion are provided by
the alpha.2 release.** The full-source builder compiles all four ABIs and its
separate corresponding-source archive supports an offline clean rebuild. This
is independent of the historical installed APK: byte equivalence and physical
acceptance of the new candidate have not been established. Read the
[complete build instructions](full_build/README.md),
[signing identity](full_build/SIGNING.md), and
[distribution guide](../docs/DISTRIBUTION.md).

## Check the source and run host tests

From the repository root:

```sh
python3 -B input/build.py --check
python3 -B tests/input/run_host.py
```

Requirements: Python 3.12+, JDK 17+ (`JAVA_HOME` or `java` and `javac` on `PATH`),
and POSIX `patch`. The default suite uses temporary directories and needs no
Android SDK, APK, network or device. It runs the 24 direct-listener cases, the
29 accessibility cases, 22 scroll cases, 16 lifecycle groups, synthetic manifest
tests, source-overlay checks and explicit failing historical replay baselines.

The real helper and pinned KeyInterceptor source are compiled. The lifecycle
test extracts production method bodies verbatim and uses the real pinned Swipe,
Tap and Trackpad strategy sources. Android GestureDetector, scheduling, Activity
routing, rendering, capture and native effects are host stubs. These tests do not
prove Android dispatch, JNI delivery, physical input or long-run stability.

`input/compile-stubs/` contains app API signatures for compiling the helper
against an Android SDK. They are never application implementations and must
never be merged into an APK. `tests/input/` fixtures likewise must not ship in
an Android application.

## Maintained source delta

Upstream: [Termux:X11 at 6d3c6883265b4ec8092673e6d2d61ef86cab5405](https://github.com/termux/termux-x11/tree/6d3c6883265b4ec8092673e6d2d61ef86cab5405).
Selected exact upstream files are in `upstream/`; this is not a complete checkout.
[The source inventory](../manifests/input-sources.json) records their URLs and
hashes, historical binary identities, current source hashes and remaining gaps.
[Modification notices](MODIFICATIONS.md) identify the local changes and dates.
Existing upstream copyright and license headers are retained; see the repository
NOTICE and legal inventory for per-file exceptions.

[The source overlay](patches/termux-x11-input.patch) expresses these changes:

1. Put KeyInterceptor in the same `com.termux` process as MainActivity in the
   **sharedUid variant only**. A service in a separate process cannot share the
   static MainActivity instance used by this pinned implementation.
2. Map Android `LANGUAGE_SWITCH` 204 to Linux `KEY_HANGEUL` 122 in the native
   fallback table. The historical binary repair changed only the arm64 library;
   the source overlay would affect every ABI built from that header.
3. Restrict local canvas pinch zoom to touchscreen input.
4. Resume physical touchpad single-finger cursor motion after multi-finger
   scrolling, including when Android GestureDetector declines `onScroll`.
5. Clear physical touchpad terminal latches after detector processing on final
   UP/CANCEL, preserving three-to-one swipe completion and held-button release.
6. Add optional cooperation with one explicitly attested Caps remapper setup,
   plus legacy virtual software key 183/184 compatibility at both the
   accessibility call and the common Activity listener. Ordinary direct keys
   retain their original single handler call and event object.

For source inspection, obtain the full upstream checkout at the exact commit,
initialize its pinned submodules, and apply `patch -p1` with this overlay as
standard input from that checkout. The supplied patch test exercises the same
operation against the included source subset and checks the resulting Java
bytes. Follow that commit's upstream build documentation for the Android build.
The new build exercises Android Gradle Plugin 9.3.1, Gradle 9.7.1, NDK
29.0.14206865 and CMake 3.22.1. It fixes the date/commit-derived version to an
explicit fork identity, uses the certificate-only companion metadata, and
records full native source and dependency pins. Build outputs and keys remain
outside Git. The source archive contains all recursive native sources and
applicable dependency source/notices; its build instructions identify external
SDK and toolchain requirements.

## Historical DEX tools and reconstruction gaps

The historical binary patchers are retained for review:

| Stage | Tool | Input identity |
| --- | --- | --- |
| Shared process / Hangul | `patchers/termux_x11_process.py` | Exact APK and arm64 ELF/table SHA pins |
| Touchscreen pinch | `patchers/PatchZoomDex.java` | Original DEX SHA pin |
| Touchpad scroll | `patchers/PatchScrollDex.java` | Zoom-patched DEX SHA pin |
| Touchpad lifecycle | `patchers/PatchLifecycleDex.java` | Scroll-patched DEX SHA pin |
| Both key entry points | `patchers/PatchHandoffDex.java` | Lifecycle-patched DEX SHA pin |

Each Java patcher accepts `input.dex helper.dex output.dex`; it refuses an
unexpected baseline or an existing output. The final patcher replaces exactly
two same-width calls and accepts only compiled KeyBridgeHandoff family classes,
rejecting compilation stubs. The predecessor policies must be compiled in order:
LocalPinchZoom, historical scroll PhysicalTouchpadMotion, final
PhysicalTouchpadMotion, then KeyBridgeHandoff.

The source-only DEX preservation tests are in `tests/input/dex/`. With the
explicit dependency classpath described in
[the toolchain manifest](../manifests/input-toolchain.json), compile the patchers
and tests using:

```sh
python3 -B tests/input/compile_dex_tools.py
```

Set `DEXLIB_CLASSPATH` to the six pinned dependency JARs. This command validates
their hashes and compiles into a temporary directory; it does not patch an APK.
Running the DEX tests additionally requires the exact reviewed original/patched
DEX files and separately compiled policy/helper DEX. Those binary inputs and
the original APK are deliberately absent. No historical device evidence is
regenerated or treated as a result of this source checkout.

```sh
python3 -B input/build.py --build
```

This legacy command intentionally exits 2 and describes **historical APK byte
reconstruction** gaps. For the new source path use
`python3 -B input/full_build/driver.py plan`; the complete build and source
export are documented separately. No historical device evidence is transferred
to the new artifact, and no compilation stub is packaged.

## Caps remapper opt-in

The retained helper defaults off. Its source pins one reviewed historical mapping snapshot
and exact remapper service names; the hash is an attestation, not a live read of
another application's configuration. No current private marker is distributed,
created or installed. No personal TOML or remapper service APK is bundled. Generic users
must review a compatible mapping and build their adapted source; copying a device
marker is not a generic setup procedure. An enabled service entry does not prove a remapper is
connected or processing events.

The intended reviewed layer maps Caps+H/J/K/L to arrows, Caps+D/F to legacy
virtual software 183/184 outputs, and Caps+digits/minus/equal to function keys.
This is a design example, not a universal keyboard setting. A developer adopting
another remapper must review its mapping, emitted virtual event signature and
paired release behavior, then adapt the helper's service/configuration pins and
tests before defining an explicit opt-in. The source does not silently enable
accessibility services or modify another application's settings.

The verified JNI argument convention is Linux evdev scan code first, Android
key code second: `(183, 0, down)` becomes XKB code 191 and `(184, 0, down)` becomes
192. Their symbols depend on the XKB layout; the accompanying compositor profile
uses numeric code bindings. JNI returning `true` is **not delivery proof**; the
upstream native method returns true even without a usable connection. Android Meta+L policy is outside these input patches; see
[the permissions notes](../docs/PERMISSIONS.md) for the separately verified
firmware-specific setting.

The historical package uses `com.termux.x11` with shared UID `com.termux` and
requires a compatible Termux signing identity. The upstream sharedUid variant
documents compatibility with GitHub Termux, not F-Droid or Google Play variants.
No signing material or general installation guarantee is supplied here.
