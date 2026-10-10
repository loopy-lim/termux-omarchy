# Input modification notices

Local input changes were made for Termux Omarchy by **loopy-lim and
contributors, October 2026**. They are distributed under the original-project
GPL-3.0-only terms, subject to the retained upstream/per-file notices and the
repository legal inventory. This notice accompanies the exact reviewed source
bytes so their provenance hashes remain useful. It is not an assertion that a
complete corresponding-source Android rebuild has been verified.

| File or group | Modification date | Local modification |
| --- | --- | --- |
| `src/com/termux/x11/input/TouchInputHandler.java` | 2026-10-09 | Touchscreen-only local pinch; physical scroll recovery; raw MOVE and terminal lifecycle guards |
| `src/com/termux/x11/input/LocalPinchZoom.java` | 2026-10-09 | New touchscreen source policy |
| `src/com/termux/x11/input/PhysicalTouchpadMotion.java` | 2026-10-09 | New physical touchpad MOVE and final UP/CANCEL policies |
| `src/com/termux/x11/utils/KeyInterceptor.java` | 2026-10-09 | Replace one Activity handleKey call with the optional handoff helper |
| `src/com/termux/x11/utils/KeyBridgeHandoff.java` | 2026-10-10 | New scoped Caps cooperation, paired release ownership and common direct-listener legacy handling |
| `history/zoom/TouchInputHandler.java` | 2026-10-09 | Historical touchscreen-only pinch stage |
| `history/scroll/TouchInputHandler.java` and `PhysicalTouchpadMotion.java` | 2026-10-09 | Historical onScroll-only recovery stage |
| `history/handoff-accessibility-only/KeyBridgeHandoff.java` | 2026-10-09 | Historical helper without direct listener hook; retained only as a failing test baseline |
| `patchers/termux_x11_process.py` | 2026-10-09 | New pinned binary XML process repair and arm64 language fallback repair |
| `patchers/PatchZoomDex.java`, `PatchScrollDex.java`, `PatchLifecycleDex.java` | 2026-10-09 | New bounded, identity-pinned DEX patch stages |
| `patchers/PatchHandoffDex.java` | 2026-10-10 | New two-call same-width DEX substitution and helper-only merge |
| `patches/termux-x11-input.patch` | 2026-10-10 | Source equivalent of maintained input changes, sharedUid service process and native language fallback delta |
| `compile-stubs/` | 2026-10-10 | Compilation signatures only, excluded from packaged classes |
| `build.py`, documentation, `tests/input/` | 2026-10-10 | Portable source checks and adapted host replays; outputs moved to temporary directories, private paths/receipts removed |

`upstream/` files are unmodified snapshots at Termux:X11 commit
`6d3c6883265b4ec8092673e6d2d61ef86cab5405`, with public source URLs and individual
hashes recorded in `manifests/input-sources.json` at the repository root. Their
original copyright and license notices remain in place. In particular, the
Chromium-derived Java files retain their BSD-style headers, and `InputXKB.c`
retains its GPL-2.0-or-later notice.
