# Development

[한국어](DEVELOPMENT.ko.md) · [README](../README.md)

## Working model

Keep Android presentation/input, native Termux services, PRoot guest setup and application integration as separate components. A change to one component must not silently replace another component's user data or permission policy.

| Directory | Responsibility |
| --- | --- |
| `runtime/` | Session ownership, start/stop, native/guest environments and bounded installation modules |
| `profiles/` | Portable workflow templates; no personal credentials or server targets |
| `installer/` | Source verification and explicit payload preflight |
| `input/` | Termux:X11 input modification source, patch stages and host tests |
| `manifests/` | Pinned source hashes, provenance and distribution boundaries |
| `tests/` | Host regression tests |
| `legal/` | Retained upstream licenses and component inventory |
| `tools/` | Publication checks |

## Verify a checkout

Use Python 3.12 or newer, zsh, and JDK 17 or newer with `java` and `javac` on `PATH`. The canonical host check is:

```sh
python3 tools/check_publication.py
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

## Input source and builds

Read [input/README.md](../input/README.md) before using the patch tooling. The retained work includes DEX-level patch stages against a pinned historical APK. The input host suite verifies behavior and source seams; it is **not** a verified rebuild of that APK from a fresh upstream checkout.

Before shipping a modified APK, complete all of the following:

- Pin the full upstream source and recursive submodules, Android/native toolchains, build scripts and dependency inputs.
- Express the maintained input changes as reviewable upstream source changes or a fully reproducible patch pipeline.
- Build from a clean checkout without private files, old build receipts or locally cached APK prerequisites.
- Verify package ID, manifest, signing family, byte/source provenance and Android installation compatibility.
- Provide the complete corresponding source and required notices with access equivalent to the binary distribution. A link to only the top-level upstream repository is not the full source closure for a modified APK.
- Install without clearing app data only after the user saves affected work; then verify physical input and normal stop/start on the exact artifact.

No modified APK is published with this source alpha. Do not advertise the historical accepted artifact as reproducible from this checkout.

## Complete fresh-device installation

The installer intentionally refuses absent/unpinned inputs. Complete pinned acquisition or source builds for the native Weston payload, PRoot guard, guest adapters, workflow payload, optional IME/development packages and compatible input APK before describing the project as installable.

Test the full native dependency bootstrap on a new isolated environment. Then test GUI readiness, GPU pixels, keyboard/Caps mappings, trackpad scroll recovery, app launch, display restoration, normal stop/start and Android restart. A reused rootfs with pre-existing native dependencies does not establish fresh-device support.

## Release process

Publish source alphas with a clear scope, immutable tag and checksums. Keep caches, APKs, package archives, keys and raw device evidence out of Git. Binaries require their own source/license review and a clean build; never attach them merely because a local device ran them.

Run host verification and a secret scan on a clean checkout, inspect the complete file list, verify license coverage and local documentation links, then compare the pushed Git SHA with the tested commit. CI completion, physical acceptance and long-duration testing are separate evidence levels.

Record known failures honestly. Useful release work includes closing installer/build gaps, reducing measured input latency and investigating network/session failures; it does not include inflating a refresh-rate request into an FPS claim.
