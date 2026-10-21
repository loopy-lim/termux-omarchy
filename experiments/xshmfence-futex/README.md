# Private native futex libxshmfence

Official Termux libxshmfence1.3.3-r1 builds with `--disable-futex`. Its pthread shared layout differs from the guest futex layout (one int32_t). This library is scoped to native Chromium talking to guest Xwayland; **do not replace the system library or inject it into native Weston / Termux:X11**.

Sources:

- [Termux recipe](https://github.com/termux/termux-packages/blob/master/packages/libxshmfence/build.sh)
- [X.Org1.3.3 source](https://www.x.org/releases/individual/lib/libxshmfence-1.3.3.tar.xz), SHA256 `d4a4df096aba96fea02c029ee3a44e11a47eb7f7213c1a729be83e85ec3fde10`

## Build

Python3.12+ and Android NDK r27 are required. The output must be a new directory. No download, device access or system installation is performed.

```sh
python3 experiments/xshmfence-futex/build.py \
  --archive build/xshmfence-futex-20261012/libxshmfence-1.3.3.tar.xz \
  --cc /PATH/TO/ndk/27.1.12297006/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android29-clang \
  --include build/x11-copy-20261012/sysroot/include \
  --out /PATH/TO/NEW/OUTPUT
```

The script verifies the upstream archive, rejects links/traversal during extraction, compiles the library and probe, and records exact commands, compiler version, source/output SHA256 in build.json. A local NDK27.1/API29 reproduction produced library SHA256 `ffd9e69982a4937fe6ce3c23379fb6fd3980660c2b63cfee2b57cc2d34f4e87c`, matching the parent's working candidate. The probe compiled without warnings. This is build evidence, not a device interoperability result.

## Two-ABI probe

Compile interop.c once with the NDK (build.py does this), and once inside the guest with `cc -O2 -Wall -Wextra interop.c -ldl -o xshmfence-interop`. No xshmfence headers are needed; each executable dlopens the exact absolute library path supplied in argv. Both endpoints first call the real library allocator and require an allocated size of4. A pthread implementation fails this gate rather than touching incompatible synchronization state.

Create a unique mode0700 directory owned by the test UID, with a file path visible to native and guest views. Initialize once:

```text
native-probe /absolute/private/libxshmfence.so init /native/path/fence
```

The file is created O_EXCL/O_NOFOLLOW, mode0600, exactly4 bytes. Existing files are never truncated. Endpoint opens verify regular file, owner, mode, size and single hardlink. Same bytes must be visible through both filesystem paths; no copying between the views.

Run these four pairs (each20cycles):

| Waiter | Signaller | Mode |
| --- | --- | --- |
| native bionic + private library | guest glibc + installed library | before |
| native bionic + private library | guest glibc + installed library | after |
| guest glibc + installed library | native bionic + private library | before |
| guest glibc + installed library | native bionic + private library | after |

`run-pair.py` accepts two JSON command argv arrays. Prefixes may be existing execution wrappers that retain stdin/stdout. Arrays must end in `LIBRARY wait FILE before|after` or `LIBRARY signal FILE before|after`. Paths for each endpoint may differ but must map to the same inode. Example for two executables on one host:

```sh
python3 experiments/xshmfence-futex/run-pair.py --mode before \
  --wait-command '["/path/native-probe","/path/native-lib.so","wait","/path/fence","before"]' \
  --signal-command '["/path/guest-probe","/path/guest-lib.so.1","signal","/path/fence","before"]'
```

For before-mode the driver waits for the signal call to finish before permitting await. For after-mode the signaller waits until the shared futex word becomes-1 (the waiter's published waiting state) before triggering; this proves the waiter reached its wait algorithm, though a scheduler may delay its actual syscall. Every cycle verifies await/query/reset. Each worker has a60-second alarm and the driver a60-second deadline. Cleanup terminates only its own subprocess handles; remote workers retain their own alarm. Do not reuse a file after a failed pair without confirming all test workers have exited; initialize a fresh unique file for the next attempt. A successful pair leaves the word reset for reuse.

The test validates shared layout and wake/reset protocol, not GPU dma-buf fences. Keep the actual browser loaded-library receipt, physical RGB/frame-ID output, resize/reuse and Present progression checks.

## Validated evidence and limits

The device cross-ABI receipt now passes all four pairs:80cycles total. The old native library fails the allocation-layout gate with96bytes versus the required4. See [fence-interop.json](../../build/diagnostics/termux-omarchy-performance-20261012/fence-interop.json).

The final strict4K workload used native Chromium155, YouTube1080p60, Web Code20 actual native-input saves(371–390), local preview, and signed-in Notion idle. Over182.74seconds it recorded10,965frames/87drops (**0.7934%**), with all20 saves successful. [Strict receipt](../../build/diagnostics/termux-omarchy-performance-20261012/webcode12-youtube-long.json), [validation and packaging limits](../../docs/validation/2026-10-12-native-fence-desktop.md).

Video decoding remains FFmpeg software decoding. This is not zero latency, zero dropped frames, active Notion editing, remote SSH acceptance, or unlimited-duration stability. The earlier25-second local1518frame/8drop(0.527%) sample remains a shorter supporting result.

Do not cite pre-futex zero-drop counters: physical presentation was frozen. Also do not cite webcode11's broad PASS as20-edit acceptance: that harness omitted the actual editor success check. Its independent physical RGB gate is valid, but the strict workload result is webcode12.

The scoped [reproducibility manifest](../../docs/validation/2026-10-12-native-fence-reproducibility.json) hashes the current sources, local graphics artifacts and validation receipts. Memory sampling recorded minima of693,296KiB MemAvailable and2,237,816KiB SwapFree over160samples. Subsequent production stop/start and same-profile browser reopening are recorded separately in the validation note; they do not imply a completed generic installer or all customization acceptance.
