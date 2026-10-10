# Component licenses and alpha.2 distribution scope

Reviewed on 2026-10-10 for the alpha.2 source and binary delivery candidate.
This inventory distinguishes copied source, project-hosted assets and separately
acquired runtime dependencies. Build/source/package verification and fresh-device
acceptance remain separate evidence; see the exact release inventory and receipts.

## Source copied into this repository

Original integration code and examples use the root [LICENSE](../LICENSE).
The following upstream notices remain applicable to copied material. Full
license copies are retained for copied source; Weston also retains its package
copyright text inside the generated native payload.
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

The copied Omarchy MIT scope also covers `guest/shell/**`,
`guest/looknfeel.lua`, `guest/omarchy-launch-browser`, and inherited workflow
strings in `tools/prepare_runtime_templates.py`. These use the same reviewed
Omarchy ancestry and [MIT notice](licenses/omarchy-MIT.txt); original local
changes remain GPL-3.0-only.

The public guard builder additionally uses these exact source components:

| Material | Pinned source | License and distribution material |
| --- | --- | --- |
| PRoot and `native/guard/patches/` | [`termux/proot` at `7266fb3e8516535682f5a9c8f3a7e70f6506eddb`](https://github.com/termux/proot/tree/7266fb3e8516535682f5a9c8f3a7e70f6506eddb) | Upstream GPL-2.0-or-later; [GPL v2 text](licenses/GPL-2.0.txt). Original local patches are GPL-3.0-only; the combined guard is conveyed under GPL-3.0-only. |
| Statically linked talloc | [talloc 2.4.3](https://download.samba.org/pub/talloc/talloc-2.4.3.tar.gz), exact archive pinned by the guard builder | [Verbatim LGPL-3.0-or-later LICENSE](licenses/talloc-LGPL-3.0-or-later.txt). The complete source archive and editable-source route permit modification and relinking; the root license does not remove the LGPL conditions. |
| libandroid-shmem | [`termux/libandroid-shmem` at `7f0bd7e25dbdd146265aff7c6a890029e374622d`](https://github.com/termux/libandroid-shmem/tree/7f0bd7e25dbdd146265aff7c6a890029e374622d) | [Verbatim BSD-3-Clause LICENSE](licenses/libandroid-shmem-BSD-3-Clause.txt), also retained in the complete source archive. |

Generated APK/companion and guard binaries are paired with separately exported
corresponding-source archives. The Git checkout alone is not a substitute for
those exact-version archives. Their builders retain recursive upstream sources,
local changes, build controls and applicable per-file notices. The APK archive
requires sources for the exact Maven runtime libraries packaged into its classes;
artifact pins, POM metadata and license texts alone do not supply that source.
The guard source route supports changing and relinking talloc. General host
tools and the Android SDK/toolchain are separately documented build prerequisites.

The APK build uses external NDK `29.0.14206865`. The inspected candidate contains
only four ABI copies of `libXlorie.so`; it does not package `libc++_shared.so`.
All four declare only Android platform libraries as dynamic dependencies
(`libGLESv2`, `libandroid`, `libmediandk`, `liblog`, `libm`, `libz`, `libEGL`,
`libc`). Its native build controls use `-nostdlib++` and disable C++ exceptions
and RTTI. This records the inspected compiler/platform boundary.

`license-sources.json` records the primary URL, extraction where needed, and
SHA-256 of each license text. The input and runtime provenance records separately identify
copied source files and local modifications.

## Project-hosted binary candidate

The alpha.2 release scope is 15 owned assets. `manifests/distribution.json` and
the exact build receipts identify the sealed bytes; the Git tree contains their
source and preparation controls rather than generated binaries.

| Assets | Count | Applicable scope and retained materials |
| --- | --- | --- |
| Guest, workflow, input configuration and native Weston payload archives, each with its manifest | 8 | Project configuration uses the source licenses above. The Weston payload contains exactly 87 regular package files; its bytes match the pinned public package, with installation modes recorded separately. |
| PRoot guard, its loader and libandroid-shmem | 3 | GPL/LGPL/BSD components and relinking route described above; exact clean-build source accompanies them. |
| Modified Termux:X11 APK and matching `termux-x11-nightly` companion `.deb` | 2 | GPL v3 plus inherited component exceptions. The companion has only the two launch scripts and loader APK; its sole `postinst` sets loader mode 0400. Package control/targets/scripts and installed bytes/modes are checked before and after explicit fresh installation. |
| APK/companion and guard corresponding-source archives | 2 | Recursive native source trees, original notices, local changes and build/install controls; packaged Maven runtime source is part of the APK source requirement. No private signing key or host SDK/cache is included. |

Weston is acquired from the pinned
[`lfdevs/anland-termux` release 5.13.3 package](https://github.com/lfdevs/anland-termux/releases/download/5.13.3/weston_14.0.2-3_aarch64.deb),
version `14.0.2-3`, SHA-256
`25d1c5ee4013e14097d6e37a3227d6fcef8f43d6d7a2dd0ee130a77e1af31c8a`.
The preparation step preserves its file bytes, including all installed headers,
protocols, image assets and `share/doc/weston/copyright`. That copyright file is
1394 bytes, SHA-256
`fdb65868f65d0fbdb05c2d3b779e10ce9969fa0c4b9262ba4f260e87086ab860`,
and matches upstream [Weston 14.0.2 COPYING](https://gitlab.freedesktop.org/wayland/weston/-/blob/14.0.2/COPYING).
It retains the upstream MIT/X.org grant, listed copyright holders and warranty
terms. Included header/protocol notices remain in their original files. Weston
is a separate permissively licensed executable/library package; the project GPL
license does not relicense it. This review establishes preservation of the
publisher's notices, not an independent reconstruction of every fork build input.
The bundle's source pin `015b3b4d4c05da44a22349ea6e651d1a8f678c59` is a reviewed
reference and is not asserted to be the exact source of this host package.

The APK/companion uses the public Termux GitHub development certificate for the
required shared-UID compatibility. This identity does not authenticate a unique
publisher. It is a separate trust/distribution boundary from source availability;
see [SIGNING.md](../input/full_build/SIGNING.md). Builds and static verification
do not establish a fresh installation or a physical-device acceptance result.

## Separately acquired runtime dependencies

These are reviewed dependency pins, not a bill of materials for a shipped
rootfs. The referenced Omarchy Android bundle is
[`BlackFireAlex/omarchy-android` at `c189d33bf34a7a50fad3ff46bbd97e5c29b48910`](https://github.com/BlackFireAlex/omarchy-android/tree/c189d33bf34a7a50fad3ff46bbd97e5c29b48910),
release `v0.1.1`; its [MIT license](https://github.com/BlackFireAlex/omarchy-android/blob/c189d33bf34a7a50fad3ff46bbd97e5c29b48910/LICENSE)
covers that project's code, not every package in its rootfs.

| Component | Reviewed reference | Primary license evidence |
| --- | --- | --- |
| Termux app | `v0.118.3`, source `5b657c6adf4304e5198951ce815fe0205dcac29c` | [LICENSE.md](https://github.com/termux/termux-app/blob/5b657c6adf4304e5198951ce815fe0205dcac29c/LICENSE.md): GPL-3.0-only with listed component exceptions. No Termux app APK is included. |
| Official Termux:X11 APK baseline | Source reference `e85aa491a99ee78e3569dba477e12ca4d79148e4` | [GPL v3 LICENSE](https://github.com/termux/termux-x11/blob/e85aa491a99ee78e3569dba477e12ca4d79148e4/LICENSE); Xorg, native libraries, and other source files retain their own notices. The APK baseline and copied Java ancestry are separate pins. |
| PRoot lifetime guard | Same pinned PRoot source as the guard entry above | [COPYING](https://github.com/termux/proot/blob/7266fb3e8516535682f5a9c8f3a7e70f6506eddb/COPYING): GPL-2.0-or-later. The Git tree contains patches and a clean builder; generated binaries and complete source archives are separate artifacts. |
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

The rootfs, Arch packages and their signatures are downloaded from the original
publishers. They may be copied into a user's local installation kit, but are not
rehosted as project release assets. Native Termux prerequisites are obtained
through the user's existing signed APT repositories. Their own package notices,
licenses and publisher source channels remain applicable.

## Source and binary release evidence

For the source tree and source archives, retain upstream copyright/license notices and the
recorded modification provenance. The GPL v3 [source-distribution sections
4 and 5](https://www.gnu.org/licenses/gpl-3.0.html) and the included MIT/BSD
texts describe the applicable source notices and conditions.

The modified APK and guard release require the exact corresponding source and
build/install scripts required by the applicable GPL terms, including inherited
Java/native changes and relevant submodules. A patch description plus a binary
hash does not establish that complete source set. The full build driver exports
that set as a separate corresponding-source archive; verify the archive against
the exact released binary's build receipt. See GPL v3 [section 6](https://www.gnu.org/licenses/gpl-3.0.html)
for object-code distribution terms.

The two source archives are versioned release assets and must remain available
with their corresponding binary downloads. A link to a moving upstream branch
does not replace the actual released versions' source/build materials.

No proprietary Chrome, Visual Studio Code, Notion, Figma, extension marketplace
payload, user account, or synchronization content is distributed here. The
repository can describe launching user-installed applications; those
applications retain their own terms. Chromium-origin input source is distinct
from redistributing the Chrome browser.

Names identify compatibility. No upstream affiliation, endorsement, trademark
license, GPU certification, or complete upstream desktop feature parity is
asserted. This inventory records source evidence and open release boundaries;
it does not declare all future distributions legally cleared.
