#!/usr/bin/env python3
"""Verify the source inventory; APK reconstruction deliberately fails closed."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "manifests/input-sources.json"


def check_sources(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root / MANIFEST).read_text())
    seen = set()
    for row in manifest["files"]:
        name = row["path"]
        relative = PurePosixPath(name)
        if (relative.is_absolute() or ".." in relative.parts or name in seen
                or not (name.startswith("input/") or name.startswith("tests/input/"))):
            raise ValueError("invalid-inventory-path")
        seen.add(name)
        path = root / relative
        if any(part.is_symlink() for part in [path, *path.parents] if part != root.parent):
            raise ValueError("source-symlink-refused: " + name)
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError("source-file-missing-or-too-large: " + name)
        raw = path.read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("source-hash-mismatch: " + name)
        if b"\0" in raw:
            raise ValueError("binary-source-refused: " + name)
        raw.decode("utf-8")
    actual = {str(p.relative_to(root)) for directory in (root / "input", root / "tests/input")
              for p in directory.rglob("*") if p.is_file()}
    if actual != seen:
        raise ValueError("source-inventory-set-mismatch")
    if manifest["correspondingSourceComplete"] or manifest["apkRebuildVerified"]:
        raise ValueError("unverified-source-closure-claim")
    return {"status": "SOURCE_INVENTORY_VERIFIED", "files": len(seen),
            "correspondingSourceComplete": False, "apkRebuildVerified": False,
            "gaps": manifest["buildGaps"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="verify text sources; no network or output files")
    mode.add_argument("--build", action="store_true", help="report unresolved APK build blockers and exit 2")
    args = parser.parse_args()
    try:
        report = check_sources()
    except (OSError, ValueError, KeyError, UnicodeError) as error:
        print("SOURCE_CHECK_FAILED: " + str(error), file=sys.stderr)
        return 1
    if args.build:
        print("APK_BUILD_BLOCKED: this source-only developer alpha does not reconstruct the installed APK.",
              file=sys.stderr)
        for gap in report["gaps"]:
            print("- " + gap["id"] + ": " + gap["detail"], file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
