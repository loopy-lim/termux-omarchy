#!/usr/bin/env python3
"""Portable host suite. No Android SDK, network, APKs, installation or device calls."""
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    commands = [[sys.executable, "-B", str(ROOT / "input/build.py"), "--check"],
                [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(HERE), "-p", "test_*.py"],
                [sys.executable, "-B", str(HERE / "handoff/run_direct_host.py"), "--baseline"],
                [sys.executable, "-B", str(HERE / "handoff/run_direct_host.py")],
                [sys.executable, "-B", str(HERE / "handoff/run_accessibility_regression.py")],
                [sys.executable, "-B", str(HERE / "scroll/run_scroll.py")],
                [sys.executable, "-B", str(HERE / "lifecycle/run_lifecycle.py"), "--baseline"],
                [sys.executable, "-B", str(HERE / "lifecycle/run_lifecycle.py")]]
    for command in commands:
        subprocess.run(command, env=env, check=True, timeout=60)
    print("PASS input host suite; framework/Activity/JNI boundaries remain explicit stubs")


if __name__ == "__main__":
    main()
