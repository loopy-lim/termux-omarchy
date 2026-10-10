# Attribution and distribution scope

Termux Omarchy is an independent source and binary integration project. It is not an official release
of, or endorsed by, Omarchy, Termux, Termux:X11, PRoot, Arch Linux ARM, Hyprland,
Aquamarine, Weston, Mesa, Google, Microsoft, Notion, or Figma. Project names are
used to identify compatibility and upstream sources; this repository grants no
rights to their names, logos, or other trademarks.

Copyright 2026 loopy-lim and contributors. Original project integration code,
local additions, and original patches are licensed under GNU GPL-3.0-only as
set out in the root [LICENSE](LICENSE). Local source modifications were made
during October 2026; the input/runtime provenance and modification notices
identify affected files. Copied upstream material retains its own copyright
and license notices, including these per-file exceptions:

- Termux:X11-derived input source and native reference files: GNU GPL version 3,
  with the Chromium BSD notices retained for the gesture/input classes and the
  GPL-2.0-or-later notice retained for `InputXKB.c`.
- Omarchy-derived launch wrappers, guest shell QML, look-and-feel and inherited
  workflow templates: MIT, copyright David Heinemeier Hansson.
- Oh My Zsh Git helpers: MIT, copyright Robby Russell and contributors.
- The source-built guard uses PRoot (GPL-2.0-or-later), talloc
  (LGPL-3.0-or-later), and libandroid-shmem (BSD-3-Clause). Local guard patches
  use GPL-3.0-only; the combined guard is conveyed under GPL-3.0-only.

Full applicable texts, source pins, file scope, and known provenance boundaries
are recorded in [legal/README.md](legal/README.md). The root license does not
replace those notices or license unrelated runtime packages.

The alpha.2 delivery candidate has 15 project-hosted assets: four runtime
payload archives and their four manifests, three guard binaries, the modified
Termux:X11 APK, its matching native companion package, and two corresponding-source
archives for the APK/companion and guard. Exact file sizes and hashes are sealed
in the release inventory and build receipts. The source Git tree keeps build
controls and source; generated binary assets are distributed separately.

The runtime payloads contain project guest/workflow/input configuration and 87
unmodified regular files from the pinned Weston 14.0.2-3 package. Weston retains
its MIT/X.org copyright text at `weston-host/share/doc/weston/copyright`, plus
the notices in included headers and protocols. The root GPL license does not
replace those terms or license other native prerequisites.

The APK/companion and guard source archives retain their recursive native
dependencies, local changes, build controls and applicable notices. The APK
source route also requires the exact packaged Maven runtime sources; artifact
hashes and POM metadata alone do not contain those sources. The guard source
archive supports editing and relinking talloc. The Git checkout alone is not a
substitute for these exact-version source archives.

The Omarchy rootfs and Arch Linux ARM packages are acquired from their original
publishers and are not rehosted in this project's releases. A locally prepared
installation kit can copy those separately downloaded originals. Termux and
other native prerequisites retain their own distribution channels and terms.
Chrome, Visual Studio Code, Notion, Figma, extension payloads, private signing
keys, user accounts and user profile data are not included in project releases.
Example profiles and the generated Fcitx input profile are project configuration,
not copies of a user's home directory.
