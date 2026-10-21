#!/usr/bin/env python3
"""Run an owned AQ fixture against Loopy's real parent in the scoped ARM VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import re
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.getuid() == 0 or not Path("/workspace/native/omarchy/tests/wayland_shm.cpp").is_file():
        parser.error("requires ordinary user in the dedicated ARM VM")
    library = args.library.resolve(strict=True)
    if library.parent != Path("/var/tmp") or not library.name.startswith("loopy-aquamarine-"):
        parser.error("library must be a scoped Aquamarine build")
    args.output.mkdir(parents=True, exist_ok=True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    flags = subprocess.check_output(["pkg-config", "--cflags", "--libs", "aquamarine", "hyprutils", "pixman-1", "libdrm"], text=True).split()
    with tempfile.TemporaryDirectory(prefix="lashm-") as directory:
        runtime = Path(directory)
        runtime.chmod(0o700)
        fixture = runtime / "fixture"
        subprocess.run(["c++", "-std=c++23", "/workspace/native/omarchy/tests/wayland_shm.cpp", *flags, "-o", str(fixture)], check=True, timeout=60)
        env = os.environ.copy()
        env.update(XDG_RUNTIME_DIR=directory, WAYLAND_DISPLAY="loopy-parent", LD_LIBRARY_PATH=str(library), WAYLAND_DEBUG="1")
        with (args.output / "parent.log").open("w") as log:
            parent = subprocess.Popen(["/var/tmp/loopy-omarchy-target/debug/examples/omarchy_parent", str(runtime / "loopy-parent"), "5", "pixel-fixture"], stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 2
                while not (runtime / "loopy-parent").exists():
                    if parent.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("parent did not start")
                    time.sleep(0.01)
                child = subprocess.run([str(fixture)], env=env, capture_output=True, text=True, timeout=4)
                (args.output / "fixture.log").write_text(child.stdout + child.stderr)
                parent.wait(timeout=7)
            finally:
                if parent.poll() is None:
                    parent.terminate()
                    parent.wait(timeout=3)
        parent_log = (args.output / "parent.log").read_text()
        frames = re.search(r"headless_frames=(\d+)", parent_log)
        identity = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        result = {"uid": os.getuid(), "fixture_exit": child.returncode, "parent_exit": parent.returncode,
                  "fixture_pixel_match": "fixture_pixel_match=true" in parent_log,
                  "parent_frames": int(frames[1]) if frames else 0, "protocol_error": "ProtocolError(" in parent_log,
                  "platform": "isolated Arch ARM64 VM", "library_sha256": identity(library / "libaquamarine.so.0.15.1"),
                  "fixture_binary_sha256": identity(fixture),
                  "fixture_source_sha256": identity("/workspace/native/omarchy/tests/wayland_shm.cpp"),
                  "parent_binary_sha256": identity("/var/tmp/loopy-omarchy-target/debug/examples/omarchy_parent"),
                  "probe_source_sha256": identity(__file__), "lock_sha256": identity("/workspace/third_party/omarchy.lock.json"),
                  "physical_device": False, "hardware_gpu": False, "omarchy_support_complete": False}
        (args.output / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
        return 0 if child.returncode == parent.returncode == 0 and result["fixture_pixel_match"] \
            and result["parent_frames"] > 0 and not result["protocol_error"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
