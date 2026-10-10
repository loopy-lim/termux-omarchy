# Component licenses and publication boundary

Reviewed for the initial source alpha on 2026-10-10. This inventory describes
what is copied into this repository and what is only referenced by the runtime
design. It is not a statement that a future binary distribution has satisfied
every component's distribution terms.

## Source copied into this repository

Original integration code and examples use the root [LICENSE](../LICENSE).
The following upstream notices remain applicable to copied material. Full
license copies are kept only for components whose source is copied here.
Unless a file notice states otherwise, original local modifications use the
project's GPL-3.0-only terms. An MIT/BSD entry below identifies inherited
upstream material; it does not relicense original project modifications under
MIT/BSD. Unmodified upstream copies retain their upstream terms.

| Material | Pinned upstream source | License and retained text |
| --- | --- | --- |
| Termux:X11 input source, baseline/history copies, build definitions, and selected native reference files under `input/` | [`termux/termux-x11` at `6d3c6883265b4ec8092673e6d2d61ef86cab5405`](https://github.com/termux/termux-x11/tree/6d3c6883265b4ec8092673e6d2d61ef86cab5405) | Upstream root GNU GPL v3: [original LICENSE](https://github.com/termux/termux-x11/blob/6d3c6883265b4ec8092673e6d2d61ef86cab5405/LICENSE), [local verbatim copy](licenses/termux-x11-GPL-3.0.txt). File-level notices also apply. |
| Chromium-origin `TouchInputHandler.java`, `TapGestureDetector.java`, `SwipeDetector.java`, and `InputStrategyInterface.java`, including copied history/baseline versions | Retained source headers identify The Chromium Authors, 2013 or 2015. Exact original Chromium code revisions have not been reconstructed. | Preserve those headers and BSD-style notices. Official Chromium license texts at releases [`31.0.1650.63`](https://chromium.googlesource.com/chromium/src/+/refs/tags/31.0.1650.63/LICENSE) and [`119.0.6045.105`](https://chromium.googlesource.com/chromium/src/+/refs/tags/119.0.6045.105/LICENSE); local verbatim copies for [2013](licenses/chromium-BSD-3-Clause.txt) and [2015](licenses/chromium-2015-BSD-3-Clause.txt). These are license-text references, not claims that copied Java files originated from those exact releases. |
| `input/upstream/lorie/src/main/cpp/lorie/InputXKB.c` | [Pinned Termux:X11 source file](https://github.com/termux/termux-x11/blob/6d3c6883265b4ec8092673e6d2d61ef86cab5405/lorie/src/main/cpp/lorie/InputXKB.c) | Its header specifies GPL-2.0-or-later and copyright TightVNC Team, Red Hat, and Pierre Ossman for Cendio AB. [Local GPL v2 text](licenses/GPL-2.0.txt); the header's later-version option remains intact. |
| `runtime/omarchy-launch-webapp`, its `runtime/loopy-launch-webapp` copy, and `runtime/omarchy-launch-tui` | Omarchy launch-wrapper ancestry; reviewed base bundle references [`basecamp/omarchy` at `158e8cfb3a03f7b390e4213eaf15edcea0dfaa98`](https://github.com/basecamp/omarchy/tree/158e8cfb3a03f7b390e4213eaf15edcea0dfaa98). Local changes support the nested Android session. | MIT, copyright David Heinemeier Hansson: [original LICENSE](https://github.com/basecamp/omarchy/blob/158e8cfb3a03f7b390e4213eaf15edcea0dfaa98/LICENSE), [local verbatim copy](licenses/omarchy-MIT.txt). This pin identifies the reviewed reference; it does not claim the modified wrappers are unchanged upstream files. |
| `profiles/git.zsh`, `profiles/git.plugin.zsh` | [`ohmyzsh/ohmyzsh` at `74965c96098134b192f00084f966b4b02438a739`](https://github.com/ohmyzsh/ohmyzsh/tree/74965c96098134b192f00084f966b4b02438a739); copied files match the pinned upstream bytes | MIT, copyright Robby Russell and contributors: [original LICENSE.txt](https://github.com/ohmyzsh/ohmyzsh/blob/74965c96098134b192f00084f966b4b02438a739/LICENSE.txt), [local verbatim copy](licenses/oh-my-zsh-MIT.txt). |

The remaining example profile files are project integration examples, not a
copy of a user's home directory. Powerlevel10k, fonts, personal Neovim settings,
SSH configuration, credentials, histories, and private synchronization data are
not included. Optional sourcing of a user-installed tool does not include that
tool's source or binary.

`license-sources.json` records the primary URL, extraction where needed, and
SHA-256 of each license text. The input and runtime provenance records separately identify
copied source files and local modifications.

## Referenced runtime components: not bundled source or binaries

These are reviewed dependency pins, not a bill of materials for a shipped
rootfs. The referenced Omarchy Android bundle is
[`BlackFireAlex/omarchy-android` at `c189d33bf34a7a50fad3ff46bbd97e5c29b48910`](https://github.com/BlackFireAlex/omarchy-android/tree/c189d33bf34a7a50fad3ff46bbd97e5c29b48910),
release `v0.1.1`; its [MIT license](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/LICENSE)
covers that project's code, not every package in its rootfs.

| Component | Reviewed reference | Primary license evidence |
| --- | --- | --- |
| Termux app | `v0.118.3`, source `5b657c6adf4304e5198951ce815fe0205dcac29c` | [LICENSE.md](https://github.com/termux/termux-app/blob/5b657c6adf4304e5198951ce815fe0205dcac29c/LICENSE.md): GPL-3.0-only with listed component exceptions. No Termux app APK is included. |
| Official Termux:X11 APK baseline | Source reference `e85aa491a99ee78e3569dba477e12ca4d79148e4` | [GPL v3 LICENSE](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/LICENSE); Xorg, native libraries, and other source files retain their own notices. The APK baseline and copied Java ancestry are separate pins. |
| PRoot lifetime-guard reference | [`termux/proot` at `7266fb3e8516535682f5a9c8f3a7e70f6506eddb`](https://github.com/termux/proot/tree/7266fb3e8516535682f5a9c8f3a7e70f6506eddb) | [COPYING](https://github.com/termux/proot/blob/7266fb3e8516535682f5a9c8f3a7e70f6506eddb/COPYING) and [source header](https://github.com/termux/proot/blob/7266fb3e8516535682f5a9c8f3a7e70f6506eddb/src/tracee/event.c): GPL-2.0-or-later. This alpha includes original verification wrappers, not PRoot source, patches, loader, or binaries. |
| Weston nested X11 backend | Bundle source pin `015b3b4d4c05da44a22349ea6e651d1a8f678c59`; referenced host package `14.0.2-3` | [COPYING at the source pin](https://gitlab.freedesktop.org/wayland/weston/-/blob/015b3b4d4c05da44a22349ea6e651d1a8f678c59/COPYING): MIT/X.org notice; inspect file-specific notices as well. The package version alone does not establish a complete matching source/build record. |
| Hyprland | Bundle source pin `5c9377c15f85c50648f35ca5a213754f95b93ca0` | [LICENSE](https://github.com/hyprwm/Hyprland/blob/5c9377c15f85c50648f35ca5a213754f95b93ca0/LICENSE): BSD-3-Clause. Dependencies and bundled third-party files retain their notices. |
| Aquamarine | Bundle source pin `a79fb21b2e2a82dd061a6d071802bcf38bd5c383` | [LICENSE](https://github.com/hyprwm/aquamarine/blob/a79fb21b2e2a82dd061a6d071802bcf38bd5c383/LICENSE): BSD-3-Clause. |
| Mesa Android-container fork | Bundle source pin [`lfdevs/mesa-for-android-container` at `98f3d6229d61452cef80f8563af7c56ae599dc14`](https://github.com/lfdevs/mesa-for-android-container/tree/98f3d6229d61452cef80f8563af7c56ae599dc14) | [License overview](https://github.com/lfdevs/mesa-for-android-container/blob/98f3d6229d61452cef80f8563af7c56ae599dc14/docs/license.rst): mainly MIT, with per-file terms and [license texts](https://github.com/lfdevs/mesa-for-android-container/tree/98f3d6229d61452cef80f8563af7c56ae599dc14/licenses). The bundle manifest summarizes MIT, BSD-3-Clause, and SGI-B-2.0; do not apply one license to every driver. |
| Wayland | Referenced rootfs package `1.26.0-1`; upstream `1.26.0` | [COPYING](https://gitlab.freedesktop.org/wayland/wayland/-/blob/1.26.0/COPYING): MIT notice, with per-file notices. |
| libepoxy | Referenced rootfs package `1.5.10-3`; upstream `1.5.10` | [COPYING](https://github.com/anholt/libepoxy/blob/1.5.10/COPYING): MIT notices and the additional Khronos notice recorded by upstream. |
| Vulkan loader | Referenced rootfs package `1.4.357.0-1`; upstream `v1.4.357` | [LICENSE.txt](https://github.com/KhronosGroup/Vulkan-Loader/blob/v1.4.357/LICENSE.txt): primarily Apache-2.0, with listed exceptions. |
| Optional VirGL research path | `virglrenderer-1.3.0`, separate from the nested session's required build | [COPYING](https://gitlab.freedesktop.org/virgl/virglrenderer/-/blob/virglrenderer-1.3.0/COPYING): MIT and Mesa ancestry; inspect file notices. No VirGL binary or source is included. |

The bundle's component list labels its own Termux:X11 reference as MIT. That
summary is not used as the license for this project's copied Termux:X11 source:
the actual pinned upstream root LICENSE is GPL v3, with file-level notices
preserved. Dependency pins identify reviewed references; they do not prove source
equivalence of every binary in a third-party bundle or installed system.

## Source publication and future binary releases

For this source alpha, retain upstream copyright/license notices and the
recorded modification provenance. The GPL v3 [source-distribution sections
4 and 5](https://www.gnu.org/licenses/gpl-3.0.html) and the included MIT/BSD
texts describe the applicable source notices and conditions.

Before publishing a modified APK, include the exact corresponding source and
build/install scripts required by the applicable GPL terms, including inherited
Java/native changes and relevant submodules. A patch description plus a binary
hash does not establish that complete source set. This repository's current
source alpha does not close every native/binary rebuild input, and is not an
APK release. See GPL v3 [section 6](https://www.gnu.org/licenses/gpl-3.0.html)
for object-code distribution terms.

Before publishing a rootfs or package bundle, inventory the exact shipped
packages, retain their notices, and provide the source and other materials
required by each applicable license. In particular, a PRoot or statically
linked dependency release needs its own exact source/build and applicable
GPL/LGPL assessment; the root project license cannot replace package terms.
Keep source availability tied to the actual released versions. A link to a
moving upstream branch is not a complete release-source record.

No proprietary Chrome, Visual Studio Code, Notion, Figma, extension marketplace
payload, user account, or synchronization content is distributed here. The
repository can describe launching user-installed applications; those
applications retain their own terms. Chromium-origin input source is distinct
from redistributing the Chrome browser.

Names identify compatibility. No upstream affiliation, endorsement, trademark
license, GPU certification, or complete upstream desktop feature parity is
asserted. This inventory records source evidence and open release boundaries;
it does not declare all future distributions legally cleared.
