# Inside Lossless Frames Implementation Plan

> **For agentic workers:** Execute source tasks in this session with ROOT owning all tests, compiler, SDK and device execution. Agents may edit their assigned sources and review files.

**Goal:** Reduce the bytes that block Android inside input without changing owned task, focus, pixel or retirement semantics.

**Architecture:** Explicit OPEN_ZLIB11 opts into response FRAME_ZLIB7. Standard zlib payloads carry decoded frame metadata and one encoded length; readers normalize strictly to existing RGBA FRAME. Legacy OPEN/FRAME bytes remain exact.

**Tech Stack:** Java17 Deflater/Inflater, Android API36 broker, Python zlib, GTK3 native Wayland.

**Spec:** `docs/superpowers/specs/2026-10-08-inside-lossless-frames.md`

**Current evidence:** Final source freeze, host03 128 tests, host benchmark02, ARM64 SDK build and independent packaging comparison are complete. The candidate is not installed; ae2 and the retained user Chromium window remain. [Candidate report](../../validation/2026-10-08-inside-lossless-current.md). ROOT observed the initial focused RED in tool outputs: five tests with three feature failures, then six tests with four failures after adding compressed Session admission, and the separate missing Delivery / fake-clock overload failures. Those early outputs were not saved as local receipts. The later host01 compatibility failures are preserved separately.

## Global Constraints

- Legacy VERSION1, capabilities127 and FRAME4 byte layout remain unchanged.
- All UID/session/peer/birth/geometry/focus and exact frame retirement checks remain.
- Only ROOT executes tests, JDK, SDK, ADB or runtime. Each module stays below500 lines.
- Current user Chromium window,124 settings hashes, profiles and roles are preserved. Do not install over an active user session without a current saved-work decision.
- No Git repository: do not initialize, commit or push.

## Task1: Bounded codec and wire contract

**Files:** create `AndroidInsideFrameCodec.java`, `AndroidInsideFrameDelivery.java`, `tests/java/AndroidInsideFrameCodecTests.java`, `tests/java/AndroidInsideFrameDeliveryTests.java`, `tests/test_inside_frame_codec.py`; modify `AndroidInsideWire.java` and `inside_wire.py`.

**Interfaces:** `byte[] deflate(byte[] rgba)` returns a shorter zlib payload or null; `byte[] inflate(byte[] payload, int expected)` returns exactly expected original bytes or throws IOException. `Message.frame(Frame, byte[], boolean compact)` opts in; existing overload retains FRAME4. Reader/Decoder output remains canonical FRAME with original bytes.

- [x] ROOT writes tests using literal pixel fixtures and independently assembled FRAME_ZLIB7 headers. Include corruption, dictionary, truncated, extra stream, output too large/small, raw fallback and legacy byte preservation.
- [x] Run `python3 -B -m unittest discover -s tests -p 'test_inside_frame_codec.py' -v`; confirm feature-specific RED before sources change.
- [x] Implement codec with `Deflater(Deflater.BEST_SPEED)` and strict bounded `Inflater`; finally end native codec state. Check25ms attempt budget between64KiB input/16KiB output chunks and fall back to raw when expired; fake-clock tests cover expiry/rollback. Add response7 encoded_size and normalization, and fresh witness after compression before frame offer.
- [x] Run the same command and existing wire tests; require GREEN without skips.

## Task2: Explicit per-connection admission

**Files:** modify `AndroidInsideProtocol.java`, `AndroidInsideBrokerPolicy.java`, `AndroidInsideShell.java`, `inside_window.py`, `inside_wire.py`; test actual Java policy and Python Session plus View AST harness.

**Interfaces:** `Action.opens()` matches OPEN and OPEN_ZLIB. Session accepts `compressed=False`; View opts in. Broker chooses compressed response only for the admitted new-open connection.

- [x] Write tests that feed OPEN11 bytes through real Java decode and policy READY→OPENING→ACTIVE; invalid resources, duplicate OPEN, stale generation and no automatic retry remain rejected. Python Session must keep default OPEN1 and opt-in OPEN11 through OPENED/focus/frame/resize/close.
- [x] Run focused tests to see RED before admission changes.
- [x] Implement all open resource/resolve/policy/deadline/OPENED checks through the same open predicate. Shell retains immutable connection choice and calls the new Message.frame overload.
- [x] Run existing inside policy, Session and initial geometry tests; preserve guards and legacy behavior.

## Task3: Packaging and honest performance evidence

**Files:** fresh diagnostics receipt and immutable deliverable directory; update current candidate validation documentation.

- [x] Measure actual Java codec+Writer payload reduction on a public structured RGBA fixture and incompressible fixture. Verify Python decompressed pixels hash equals original.
- [x] ROOT runs related `test_inside*.py` and `test_android_inside*.py`, Java wire/policy/session suites. Independently review source behavior.
- [x] Build with the currently pinned rootfs/native candidates using `tools/build_android.py`; compare packaged assets and unchanged native hashes. Preserve the installed ae2 evidence as historical.
- [ ] Keep installation pending while the intentionally retained user Chromium session is active. Only update after a current saved-work authorization or verified absence of user work. Subsequent device trial must use new APK identity and same geometry, and separately measure codec/transmit/ACK timings.
- [x] Report implementation/build independently from device performance and physical60/144fps acceptance. Keep full Omarchy goal active.
