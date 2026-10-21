#!/usr/bin/env python3
"""Keep source files readable; report files exceeding the agreed 500-line limit."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", "build", "target", "__pycache__"}
SUFFIXES = {".java", ".py", ".rs", ".c", ".h", ".cpp", ".hpp", ".xkb", ".sh"}


def main():
    files = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        # Pinned upstream shell sources and the exported Mac prompt are payloads.
        shell = ("guest", "desktop", "usr", "share", "loopy", "shell")
        if relative.parts[:7] == shell + ("powerlevel10k",) or relative.parts == shell + ("p10k.zsh",):
            continue
        # Validation records contain verbatim upstream source, not local modules.
        if path.relative_to(ROOT).parts[:2] == ("docs", "validation"):
            continue
        if any(part in SKIP for part in path.relative_to(ROOT).parts) or not path.is_file():
            continue
        if path.relative_to(ROOT).parts[0] == "guest" and path.suffix in {".ttf", ".otf"}:
            continue
        if (path.suffix in SUFFIXES or path.parent == ROOT / "dev"
            or (path.relative_to(ROOT).parts[0] == "guest" and path.suffix != ".md")):
            files.append((len(path.read_text(encoding="utf-8").splitlines()), path))
    over = [(count, path) for count, path in files if count > 500]
    for count, path in over:
        print(f"{path.relative_to(ROOT)}: {count} lines (limit 500)", file=sys.stderr)
    largest = max(files, default=(0, ROOT), key=lambda item: item[0])
    print(f"Checked {len(files)} source files; largest {largest[0]} lines: {largest[1].relative_to(ROOT)}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
