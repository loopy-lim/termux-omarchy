# Termux Omarchy Distribution Implementation Plan

> **For agentic workers:** Execute the independent input-build and runtime-payload tasks in parallel; root integrates and verifies the release boundary.

**Goal:** Prepare an installable, legally attributable candidate from public source and pinned dependencies while preserving the current installation.

**Architecture:** Rebuild input from full upstream source, generate owned payloads deterministically, then admit only verified components to the installer/release candidate. Keep third-party acquisition separate from user-state changes.

**Tech Stack:** Python 3.12+, JDK/Gradle/Android SDK/NDK, Git, Termux, PRoot, Arch Linux ARM.

**Spec:** [Distribution design](../specs/2026-10-10-termux-distribution-design.md)

## Global constraints

- Never take personal profiles, credentials, account state or device journals as release inputs.
- Do not update or stop the current tablet session during host preparation.
- Preserve exact upstream source/license bytes and immutable dependency pins.
- No APK publication before the actual corresponding-source and signing review.
- Keep host, binary-build, installation and physical acceptance evidence distinct.

## Task 1: Full input source build

**Files:** New `public/termux-omarchy/input/full_build/`, new `tests/input/test_full_build.py` in the public repo; integration of input inventory after review.

- [ ] Fetch the exact upstream commit into an isolated directory and verify every recursive gitlink.
- [ ] Apply the already reviewed Java and native changes as source overlays, including the current lifecycle corrections.
- [ ] Test refusal of changed upstream content, dirty dependencies and missing toolchains before mutation.
- [ ] Attempt the full Android build using isolated caches; record exact build inputs and errors.
- [ ] Inventory corresponding source and inspect package ID, ABI and signing compatibility before any binary release.

## Task 2: Runtime payload preparation

**Files:** New `tools/prepare_runtime*`, `manifests/runtime-build.json`, `tests/runtime/test_payload_preparation.py` in the public repo.

- [ ] Derive source-to-target mappings from the maintained installer contracts and portable sources.
- [ ] Add real filesystem tests for deterministic tar bytes, exact members/modes, hash changes, symlinks and no-clobber publication.
- [ ] Produce payloads without private source paths or account settings; compare each generated member with the recorded source bytes.
- [ ] Identify native payload/package prerequisites that cannot be produced by the source payload builder.

## Task 3: Acquisition and release readiness

**Files:** New distribution manifest/checker/tests in the public repo after the two component interfaces are known.

- [ ] Record source, artifact, license and acquisition relationships for every required component.
- [ ] Check local/source-build inputs and reject unresolved gates before permitting a candidate release.
- [ ] Exercise the real installer in an isolated supported environment when all dependencies are available.
- [ ] Run full host checks, secret scan and independent review; update English and Korean guides with actual results.
- [ ] Publish only the scope supported by clean build, CI, source/signature inspection and device evidence; preserve alpha while gates remain unresolved.
