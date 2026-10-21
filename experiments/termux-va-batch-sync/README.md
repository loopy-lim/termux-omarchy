# Y900 VA shared-buffer sync experiment

Status: **experimental; not installed as the default driver**. The device has a separate `/opt/loopy-va-batch-candidate`. Chrome video drops did not improve enough to adopt it.

The patch targets Mesa `8c095276f525605c67c5212aabd8e42ef588790a`, `src/gallium/frontends/va/tva_bridge.c`. `source.json` records source/package hashes. It includes aggregate copy profiling and an opt-in shared NV12 buffer copy. Existing unrelated Mesa/VA quiet-log changes in the build are not supplied by this single-file patch.

Apply with `git apply mesa-tva-batch-sync.patch` from that exact source checkout. Build using the existing Android-container Mesa build configuration. Set `DMD_VA_BATCH_SYNC=1` for batching and `DMD_VA_PROFILE=1` for aggregate counters. This is not a standalone Mesa build/install recipe. The experiment does not modify the installed desktop launcher.

Both planes must export the same inode/device/size, fit inside the allocation, and not overlap. Map once and copy both planes inside one DMA-BUF START/END scope. Keep row padding intact. Retry EINTR/EAGAIN. Permanent START or END failures mark the codec broken under the existing pending mutex and prevent publishing successful frames. Unsupported layout/export/map cases fall back before writes. No persistent mapping or buffer ownership/fence contract is added.

Run on Linux:

```sh
python3 test_helper.py /path/to/patched/src/gallium/frontends/va/tva_bridge.c
```

The harness extracts the actual patched helpers, uses real temporary-file mmap/dup/fstat, mocks sync ioctl, and runs ASan/UBSan. It checks aliased padded planes, retries, fatal START/END, distinct objects, overlap, bounds, and opt-out. This does not simulate real DMA cache coherency or GPU fences. Device FFmpeg decoded-frame and Chrome composited-pixel checks are documented separately.

Results and remaining output-copy work: [research](../../docs/research/2026-10-12-y900-graphics-acceleration.md).
