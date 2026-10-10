#!/usr/bin/env python3
"""Compile historical DEX tools with explicit pinned dependencies; no APK build."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
from tooling import java_tools


def main():
    pins = json.loads((ROOT / "manifests/input-toolchain.json").read_text())["dexJars"]
    value = os.environ.get("DEXLIB_CLASSPATH", "")
    paths = [Path(p) for p in value.split(os.pathsep) if p]
    actual = {p.name: p for p in paths}
    if len(actual) != len(paths) or set(actual) != {pin["file"] for pin in pins}:
        raise SystemExit("Set DEXLIB_CLASSPATH to exactly the six pinned JARs in manifests/input-toolchain.json")
    for pin in pins:
        path = actual[pin["file"]]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
            raise SystemExit("Dependency hash mismatch: " + pin["file"])
    tools = java_tools()
    sources = [*(ROOT / "input/patchers").glob("*.java"), *(HERE / "dex").glob("*.java"),
               *(HERE / "dex/fixtures").rglob("*.java"),
               ROOT / "input/src/com/termux/x11/input/LocalPinchZoom.java",
               ROOT / "input/src/com/termux/x11/input/PhysicalTouchpadMotion.java"]
    with tempfile.TemporaryDirectory(prefix="termux-omarchy-dex-tools-") as directory:
        subprocess.run([tools["javac"], "-cp", value, "-d", directory,
                        *map(str, sorted(sources))], check=True, timeout=60)
    print("PASS DEX tools compile; no DEX/APK inputs or runtime tests were executed")


if __name__ == "__main__":
    main()
