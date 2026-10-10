# Source-built PRoot guard

This builder creates the ARM64 PRoot executable, its separate ARM64 loader,
and `libandroid-shmem.so` for the supervised Termux desktop runtime. It does
not install or start anything. No historical executable or object file is a
build input.

The source baseline is Termux PRoot commit
`7266fb3e8516535682f5a9c8f3a7e70f6506eddb`, talloc 2.4.3, and
libandroid-shmem commit `7f0bd7e25dbdd146265aff7c6a890029e374622d` (0.7).
`sources.lock.json` records their public URLs, archive sizes and SHA-256
values, plus the checksums of local patches and configuration inputs.

Requirements: Python 3.9+, `make`, `patch`, and Android NDK
`27.1.12297006` on macOS or Linux. The compiler target is Android ARM64 API 28.
The NDK is supplied separately and is never modified. Every output directory
must be new; an existing directory is refused.

```sh
python3 -B native/guard/build.py --check
python3 -B native/guard/build.py --prepare --output /tmp/guard-source-new
python3 -B native/guard/build.py --build \
  --ndk "$ANDROID_NDK_HOME" --output /tmp/guard-build-new
```

The build emits `arm64-v8a/proot`, `arm64-v8a/loader`,
`arm64-v8a/libandroid-shmem.so`, `receipt.json`, `build.log`, and
`guard-corresponding-source.tar.gz`. The receipt describes the actual newly
built bytes and the compiler tools. A failed fetch, checksum, patch, compiler,
or ELF check fails the build explicitly; no fallback binary is used.

## Corresponding source and offline rebuild

Ship `guard-corresponding-source.tar.gz` beside the native binaries. It contains:

- All three complete upstream source archives, and their extracted sources.
- The applied PRoot patches, this builder, source lock, and feature preset.
- The upstream licenses and the GPL version 3 text.
- A source manifest listing every bundled file and its SHA-256 value.

After extracting that archive, rebuild with the included original archives:

```sh
python3 -B guard-source/builder/build.py --build \
  --source-cache guard-source/archives \
  --ndk "$ANDROID_NDK_HOME" --output /tmp/guard-offline-new
```

This command does not fetch sources. It validates the cached archives, applies
the bundled patches, and compiles fresh objects. An NDK and host build tools
are still required. Preserve the source archive for every distributed binary
version; a link to a moving upstream branch is insufficient provenance.

## Changes and configuration

The project changes, dated 2026-10-10, are:

- An opt-in `PROOT_EXITKILL=1` ptrace exitkill mode and the missing string header
  declaration in PRoot's ashmem compatibility extension.
- Generation of talloc's `config.h` from the bundled, reviewed Android API 28
  feature preset. The preset contains no private source directory. The builder
  compiles target/ABI assertions before talloc; it does not run host-native Waf
  feature detection or reuse a generated header from an installed runtime.
- Fresh generation of `loader-info.c` from the new loader's symbol offsets.
  The optional ARM32 loader is omitted for this ARM64 runtime.
- A private `$ORIGIN` library search path, 16 KB ELF load alignment, and an
  explicit Termux temporary-directory definition for libandroid-shmem.

The loader's build source remains upstream's ARM64 loader. The builder checks
that it has no dynamic dependency and that PRoot needs only the private shared
memory library and Android's `libdl.so` and `libc.so`. These are package checks;
they do not establish on-device runtime acceptance.

## Modify talloc and relink

PRoot links talloc statically. All PRoot application source and the talloc
source are supplied so recipients can rebuild with a modified library. Copy
`guard-source/source` to a new directory, change the talloc sources there, and
run the explicit relink route:

```sh
cp -R guard-source/source /tmp/guard-edited-source
# Edit /tmp/guard-edited-source/talloc/talloc.c or talloc.h as needed.
python3 -B guard-source/builder/build.py --build \
  --source-cache guard-source/archives \
  --relink-source /tmp/guard-edited-source \
  --ndk "$ANDROID_NDK_HOME" --output /tmp/guard-relinked-new
```

The edited directory must contain only the three source directories `proot`,
`talloc`, and `android-shmem`, without symbolic links or prior build output.
This explicit mode records `sourceInputMode: editable-source`, retains the
baseline sources, includes the modified sources in a new corresponding-source
archive, and computes new binary hashes. The modified source must remain
compatible with the documented target; configuration changes can be made in
the included builder and re-pinned in its source lock.

## Licenses

PRoot is GPL-2.0-or-later; this combined build is conveyed under GPL-3.0-only,
consistent with the project's local modifications. PRoot's original
later-version permission remains intact for its upstream material.
talloc is LGPL-3.0-or-later. libandroid-shmem is BSD-3-Clause. Their original
copyright notices, license texts, source files, and local modification notices
are retained in the source archive. Keep the libandroid-shmem BSD notice with
binary distribution documentation as well. These components come with the
warranty terms in their respective license texts.
