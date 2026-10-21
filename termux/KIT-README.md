# Loopy native Termux setup kit — 2026-10-06

This kit installs an owned native Termux i3/X11 desktop without PRoot. It does not contain companion APKs, install them on a device, grant permissions or claim native Android runtime/physical-device acceptance. Follow-up exact-APK evidence belongs to the repository document `docs/native-termux-validation.md`.

## Installation order

1. Preserve your existing Termux data and install source. Do not replace a differently signed existing app or clear its data. For a fresh setup, obtain the official companions in [the lock](third_party/termux.lock.json).
2. Install Termux and open it once to finish bootstrap. Install the **standard** Termux:X11 APK. The optional shared-UID variant requires compatible GitHub-signed Termux and is not this kit's default.
3. In the primary Android user's native Termux shell, manually paste the contents of [android/assets/loopy-termux-setup.sh](android/assets/loopy-termux-setup.sh), or run that reviewed file with Termux's `bash` after copying it into Termux. The script includes every helper/config; no download of Loopy helper source is needed.
4. The script installs official X11 dependencies and writes only `~/.local/share/loopy-native`. It preserves existing i3/Termux settings and edited owned configuration. Allow package network access and wait for completion; installed apt package versions are rolling, while companion bytes are pinned.
5. Through Loopy's explicit setup guidance, grant Loopy `com.termux.permission.RUN_COMMAND` and manually enable `allow-external-apps=true` in Termux's properties if you choose to use the bridge. The installer performs neither action. Use Loopy's native start/doctor/stop buttons, then open tag `loopy-native` in Termux:X11.
6. Input preferences are optional. Open the owned X11 window first, apply the preset explicitly and restore it explicitly. Subsequent user edits are preserved. Accessibility remains separate opt-in.

The setup requires ordinary primary-user `com.termux` with prefix `/data/data/com.termux/files/usr`; it is not a relocatable Linux package set or a work-profile installation. Native i3 starts xfce4-terminal with `--disable-server`; Ctrl+Alt+Enter opens another terminal, Ctrl+Alt+Space opens dmenu, Ctrl+Alt+E/F opens editor/files and Ctrl+Alt+1–9 selects a workspace.

The explicit input preset owns seven Boolean preferences: `fullscreen`, `pointerCapture` and `pauseKeyInterceptingWithEsc` true; `hardwareKbdScancodesWorkaround`, `preferScancodes`, `showAdditionalKbd` and `showIMEWhileExternalConnected` false. X11 gets hardware keys through PreIME before the Android IME; printable keys prefer Unicode text while modifier shortcuts retain available raw scancodes. Software IME composition/`commitText` stays intact. Upstream's 50 ms Delete/Ctrl/Shift key-release fallback remains; physical OEM scancodes and multiple layouts need separate checks.

Restore only writes owned keys whose observed values still match the applied snapshot, preserving subsequent user changes. Read/write are separate stock CLI requests; avoid concurrent preference edits during the transaction. Old six-key snapshots do not own the seventh key, and partial apply retains its snapshot for explicit restore. The manual VM keyboard diagnosis is separate from the fresh final APK's public RUN_COMMAND/profile UI acceptance.

The supervisor supports Android kernels without `/proc` child-list files: direct child PID and PPID identity checks remain strict, and cleanup requires no tracked descendants plus kernel `waitpid` returning `ECHILD`. Unverified live children retain a failed cleanup marker; an empty process scan cannot claim stopped.

## Obtain and verify companions

The automated downloader is for a development host with Python and **Android SDK build-tools 36.1.0** (apksigner and Java). On macOS, its default SDK path is `~/Library/Android/sdk`. From this extracted kit:

```sh
python3 tools/fetch_termux.py --sdk "$HOME/Library/Android/sdk"
```

On Linux/other hosts, pass the actual SDK directory with `--sdk`; the tool creates `build/termux/companions`, verifies pinned bytes and APK signer, and writes a fresh receipt. It does not install or execute the APKs. Existing wrong-hash cached files are preserved and rejected. The included `provenance/companion-download-receipt.json` records verification in the source workspace, not verification of your later local download.

Without the SDK, manually download the exact official URLs in the lock with a browser and compare SHA-256/size before installation; use a host with apksigner to verify the locked certificate. A manual download alone is not signature verification. If the rolling nightly URL no longer matches the lock, preserve the mismatch and obtain the intended official release artifact; do not update the hash merely to accept new bytes.

| Official companion | Bytes | SHA-256 |
| --- | --- | --- |
| Termux v0.118.3 ARM64 | 35,106,607 | `72fdb596045116bf5ba1b5bdf5b26fddb9acc0bd074ad9f2da9eb0ae85e83a4e` |
| Standard Termux:X11 2026-10-05 | 14,693,940 | `dde066f1d1510ffe45fcfa019c8baf0236d6115265e83e9418b7a10c83e349b0` |

Both pinned official APKs have signer SHA-256 `b6da01480eefd5fbf2cd3771b8d1021ec791304bdd6c4bf41d3faabad48ee5e1`. The public debug key is not origin proof by itself; retain the upstream byte hash/URL evidence. Sources and full included license notices are in [termux/NOTICE.md](termux/NOTICE.md).

## Scope and files

`termux/` contains helper modules, i3 configuration, installer/generator and instructions; `android/assets/` contains the self-contained setup; `tools/` contains the verified host downloader; `third_party/` contains companion pins; `provenance/` contains download and source-hash manifests. No APK is embedded. The repository's broader research/test/validation references in `termux/README.md` are follow-up documents, not bundled runtime dependencies or acceptance evidence.

The default profile selects software client rendering. Termux:X11's Android GLES presentation is separate from native Mesa/VirGL client hardware acceleration. This kit enables neither a general hardware GPU default nor global Android keyboard ownership. Actual display pixels, callback UID/nonce, native input, process cleanup and physical performance must be validated separately. See repository `docs/research/termux-native-runtime.md` for the official-source opt-in native VirGL diagnostic procedure and its limits.
