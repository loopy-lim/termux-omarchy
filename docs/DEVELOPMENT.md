# Development

[한국어](DEVELOPMENT.ko.md) · [README](../README.md)

## Working model

Keep Android presentation/input, native Termux services, PRoot guest setup and application integration as separate components. A change to one component must not silently replace another component's user data or permission policy.

| Directory | Responsibility |
| --- | --- |
| `runtime/` | Session ownership, start/stop, native/guest environments and bounded installation modules |
| `profiles/` | Portable workflow templates; no personal credentials or server targets |
| `installer/` | Source/assets verification, native prerequisites and fresh-only application |
| `input/` | Termux:X11 input modification source, patch stages and host tests |
| `manifests/` | Pinned source hashes, provenance and distribution boundaries |
| `tests/` | Host regression tests |
| `legal/` | Retained upstream licenses and component inventory |
| `tools/` | Publication checks, pinned acquisition and deterministic payload preparation |
| `guest/` | Reviewed portable guest adapters and IME configuration |
| `native/guard/` | Locked PRoot guard build and corresponding-source export |

## Verify a checkout

Use Python 3.12 or newer, zsh, and JDK 17 or newer with `java` and `javac` on `PATH`. The canonical host check is:

```sh
python3 -B tools/check_publication.py
```

It checks source inventory, syntax, documentation links, publication boundaries and the included regression suites. It does not install software, grant Android permissions, contact a development server or interact with a tablet. The GitHub workflow runs the same host checks. A separate pinned Gitleaks scan checks for recognizable secrets.

Source manifests are review records, not a substitute for code review or signatures. When updating maintained source, update the relevant manifest intentionally after reviewing the diff. Do not make a validator refresh its own expected hashes during validation.

## Make a change

1. Reproduce the failure at the narrowest useful boundary. Distinguish Android delivery, X11 input, Wayland dispatch and application handling.
2. Add a regression that would detect the failure, then implement the bounded change.
3. Re-run the affected host checks and the full publication check before committing.
4. Test the exact candidate on a device when the behavior involves Android, input, graphics or process policy. Keep the candidate hash, test conditions and result together.
5. Update English documentation first and the Korean companion in the same change. Mark unverified scope explicitly.

Use temporary directories and synthetic data for host tests. Avoid recording ordinary typed text, account tokens or unrelated screen content. Physical input acceptance should cover movement → two-finger scroll → release → movement, physical click, app return and the affected shortcuts with observers disconnected.

## Runtime invariants

- Never delete a user's Termux home, browser profile, editor state or dotfiles to recover a session.
- Refuse unexpected ownership, symlink targets, changed hashes, partially installed state and uncertain process identity.
- Signal only the owned session and verified child identities. Do not use broad `pkill` or `killall` for recovery.
- Separate startup requests from readiness evidence. A successful command exit is not proof that a window appeared.
- Keep native and guest graphics environments separate. Global driver overrides can break a working path.
- Keep permission requests and OEM policy changes explicit and reversible. Ordinary APK installation does not grant shell/root capabilities.

## Current build and delivery evidence

`v0.1.0-alpha.2` separates the source Git tree from experimental binary release assets. The final installation tree has 90 files: 88 pinned downloads and 2 checked local package manifests. Fifteen downloads are project release artifacts; 73 are upstream runtime inputs. The upstream Weston `.deb` is an additional build-only download, not part of the final tree. See [distribution preparation](DISTRIBUTION.md).

The complete exported Termux:X11 source archive built offline for `arm64-v8a`, `armeabi-v7a`, `x86` and `x86_64`, without fetching Git source. The PRoot guard rebuilt offline with byte-identical binaries. These are source/build results; Android installation, live JNI input, GUI behavior and fresh-device acceptance of the candidate remain separate. `fullFreshInstallVerified` is `false`.

The historical DEX reconstruction tools remain for audit and intentionally retain their old-artifact blocker. They are not the alpha.2 build route. Use [the complete-source driver](../input/full_build/README.md), its exported archive and [the guard builder](../native/guard/README.md) for fresh builds. Native API 28 guard builds use NDK 27.1.12297006; the APK build uses NDK 29.0.14206865. Offline APK builds also need the exact SDK, Gradle distribution and Maven dependency cache described in the archive.

For every new candidate:

- Keep upstream/submodule identities, local patches, toolchains and dependency inputs pinned. Never consume an old APK, native object, private profile or earlier receipt as a source-build input.
- Audit packaged DEX/JNI, package ID, manifest, source notices and certificate compatibility. Preserve the unsigned payload identity across reviewed signing, and pair the APK with its exact source-built companion.
- Publish complete corresponding source and notices alongside the binaries. Keep each component's license scope; a top-level upstream link is insufficient for modified source.
- Record installation and physical results against the exact candidate hash after the user saves work. Existing tablet observations do not transfer to a rebuilt APK.

## Fresh-device acceptance still required

The download tool requires no NDK and never installs. Native preparation explicitly adds missing signed-APT dependencies without upgrades/removals. The fresh asset installer checks native ARM64 primary-user Termux, API 28+, accessible Adreno KGSL, the exact installed APK and fresh desktop state. A private runtime/container/launcher or mismatched companion is preserved and refused; this is not a migration path. Missing or changed inputs must remain blockers.

Test the dependency bootstrap in a fresh environment, then GUI readiness, actual GPU pixels, sound, ordinary keys and Hangul, trackpad scroll recovery, app launch/return, normal stop/start and Android restart. Generic KeyBridge/Caps configuration is unresolved, optional and off by default; do not include it in generic acceptance without reviewing its configuration. A reused rootfs with existing dependencies does not establish fresh installation support.

## Release process

Publish experimental alphas with a clear scope, immutable tag and checksums. Keep caches, APKs, package archives, keys and raw device evidence out of Git. Release assets are separate from the source tree and require source/license review and a clean build.

Run host verification and a secret scan on a clean checkout, inspect the complete file list, verify license coverage and local documentation links, then compare the pushed Git SHA with the tested commit. CI completion, physical acceptance and long-duration testing are separate evidence levels.

Record known failures honestly. Priorities include fresh-device acceptance, measured input latency and the intermittent network/session failures observed during development. A refresh-rate request is not sustained 60/144 FPS evidence; long-duration, reboot, application GPU and every remote workflow remain separate checks.
