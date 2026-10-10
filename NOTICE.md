# Attribution and distribution scope

Termux Omarchy is an independent source project. It is not an official release
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
- Omarchy-derived launch wrappers: MIT, copyright David Heinemeier Hansson.
- Oh My Zsh Git helpers: MIT, copyright Robby Russell and contributors.

Full applicable texts, source pins, file scope, and known provenance boundaries
are recorded in [legal/README.md](legal/README.md). The root license does not
replace those notices or license unrelated runtime packages.

This source alpha contains no APK, root filesystem, compiled native graphics
library, browser, editor, extension package, signing key, or user profile data.
External runtime downloads and user-installed applications remain separate
components under their own terms. Chrome, Visual Studio Code, Notion, and Figma
are not redistributed here.

The source inventory is not a complete corresponding-source package for a
binary release. Publishing an APK, rootfs, package archive, or bundled runtime
requires a separate inventory of the exact shipped bytes, their licenses,
modifications, build inputs, and applicable source/relinking material.
