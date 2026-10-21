# Official companion provenance

The companions are unmodified official upstream release artifacts. `tools/fetch_termux.py` verifies their pinned byte size, SHA-256 and APK signature before creating a receipt; it does not build, install or execute them. The public upstream debug signing key is not sufficient provenance by itself: retain the pinned upstream byte hashes and URLs.

| Component | Upstream source snapshot | License record |
| --- | --- | --- |
| Termux app v0.118.3 | [5b657c6adf4304e5198951ce815fe0205dcac29c](https://github.com/termux/termux-app/tree/5b657c6adf4304e5198951ce815fe0205dcac29c) | [Upstream license declaration](licenses/termux-app-LICENSE.md): GPL-3.0-only with listed component exceptions |
| Termux:X11 standard nightly APK, 2026-10-05 | [e85aa491a99ee78e3569dba477e12ca4d79148e4](https://github.com/termux/termux-x11/tree/e85aa491a99ee78e3569dba477e12ca4d79148e4) | [Upstream GPL-3.0 text](licenses/termux-x11-LICENSE); Xorg/library submodules keep their individual notices |
| Termux package recipes inspected | [7945fdb5a62d773e98cae56f2e43438d859f9009](https://github.com/termux/termux-packages/tree/7945fdb5a62d773e98cae56f2e43438d859f9009) | Each package recipe declares its upstream source, license and checksums |

Complete component sources and submodule revisions are maintained by the linked official repositories and release pages. These source links and license copies do not assert that source archives for every APK dependency have been bundled. Preserve upstream notices and corresponding-source obligations when redistributing companions or a modified embedded fork. Loopy's public Intent integration imports no Termux:X11 Java/native code into Loopy.

APK byte/signature details: [third_party/termux.lock.json](../third_party/termux.lock.json). Generated verification receipt: `build/termux/companions/receipt.json`. Optional shared-UID APK metadata is recorded separately and is not the default downloaded companion.
