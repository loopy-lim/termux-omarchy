#!/usr/bin/env python3
"""Bounded real Hyprland/Aquamarine refresh regression in the owned ARM VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import tempfile
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stop(process):
    if process and process.poll() is None:
        if os.getpgid(process.pid) != process.pid:
            raise RuntimeError("owned process group changed")
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.getuid() == 0 or Path.cwd() != Path("/workspace") or os.uname().machine != "aarch64":
        parser.error("ordinary user in the scoped ARM VM required")
    for directory, prefix in ((args.build, "loopy-hyprland-"), (args.library, "loopy-aquamarine-")):
        if directory.parent != Path("/var/tmp") or not directory.name.startswith(prefix) or directory.is_symlink():
            parser.error("scoped Linux build directory required")
    binary = args.build / "Hyprland"
    controller = args.build / "hyprctl/hyprctl"
    library = args.library / "libaquamarine.so.0.15.1"
    for artifact in (binary, controller, library, args.parent):
        if not artifact.is_file():
            parser.error("missing artifact: " + str(artifact))
    if args.output.exists():
        parser.error("fresh output directory required")
    args.output.mkdir(parents=True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    result = {"platform": "isolated Arch ARM64 VM", "uid": os.getuid(),
              "physical_device": False, "hardware_gpu": False, "visual_acceptance": False,
              "status": "not-accepted", "stages": []}
    parent = child = None
    # Hyprland embeds its long commit-based signature in a Unix socket path.
    with tempfile.TemporaryDirectory(prefix="rfr-") as directory:
        runtime = Path(directory)
        runtime.chmod(0o700)
        for name in ("home", "config", "cache", "state", "data"):
            (runtime / name).mkdir()
        config = runtime / "hyprland.lua"
        config.write_text("hl.config({debug={disable_logs=false,enable_stdout_logs=true,vfr=false}})\n")
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(runtime / "home"),
               "USER": "loopy", "LOGNAME": "loopy", "LD_LIBRARY_PATH": str(args.library),
               "XDG_RUNTIME_DIR": directory, "WAYLAND_DISPLAY": "loopy-parent", "WAYLAND_DEBUG": "1",
               "AQ_SHM_ONLY": "1", "LIBGL_ALWAYS_SOFTWARE": "1", "HYPRLAND_NO_SD_NOTIFY": "1",
               "HYPRLAND_NO_SD_VARS": "1", "XDG_CONFIG_HOME": str(runtime / "config"),
               "XDG_CACHE_HOME": str(runtime / "cache"), "XDG_STATE_HOME": str(runtime / "state"),
               "XDG_DATA_HOME": str(runtime / "data")}
        try:
            with (args.output / "parent.log").open("w") as parent_log, (args.output / "hyprland.log").open("w") as child_log:
                parent = subprocess.Popen([str(args.parent), str(runtime / "loopy-parent"), "25"],
                                          stdin=subprocess.PIPE, text=True, stdout=parent_log,
                                          stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 2
                while not (runtime / "loopy-parent").is_socket():
                    if parent.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("owned parent not ready")
                    time.sleep(0.01)
                child = subprocess.Popen([str(binary), "--config", str(config)], env=env,
                                         stdout=child_log, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 8
                while not list(runtime.glob("hypr/*/.socket.sock")):
                    if child.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("owned Hyprland IPC not ready")
                    time.sleep(0.02)
                sockets = list(runtime.glob("hypr/*/.socket.sock"))
                if len(sockets) != 1:
                    raise RuntimeError("unexpected private IPC count")
                signature = sockets[0].parent.name

                def control(*arguments, structured=True):
                    command = [str(controller), "-i", signature]
                    if structured:
                        command.append("-j")
                    completed = subprocess.run([*command, *arguments],
                                               env=env, capture_output=True, text=True, timeout=2)
                    if completed.returncode:
                        raise RuntimeError("owned IPC failed: " + completed.stdout.strip()[:200])
                    return json.loads(completed.stdout) if structured else completed.stdout.strip()

                def monitors():
                    return control("monitors")

                def command(text):
                    parent.stdin.write(text + "\n")
                    parent.stdin.flush()

                def sample(sequence):
                    command("sample:" + str(sequence))
                    deadline = time.monotonic() + 1
                    while time.monotonic() < deadline:
                        text = (args.output / "parent.log").read_text()
                        match = re.search(r"sample sequence=" + str(sequence) + r" frames=(\d+) millis=(\d+)", text)
                        if match:
                            return {"frames": int(match[1]), "millis": int(match[2])}
                        time.sleep(0.01)
                    raise RuntimeError("parent sample not acknowledged")

                deadline = time.monotonic() + 3
                current = monitors()
                while not current and time.monotonic() < deadline:
                    time.sleep(0.02)
                    current = monitors()
                for index, rate in enumerate((120000, 60000, 144000, 120000)):
                    if index:
                        command("refresh:" + str(rate))
                    if index == 3:
                        # A requested nested mode cannot increase the parent's actual rate.
                        result["requested_144_reply"] = control(
                            "eval", "hl.monitor({output='',mode='640x360@144',position='auto',scale=1})",
                            structured=False)
                    deadline = time.monotonic() + 1.2
                    while time.monotonic() < deadline:
                        current = monitors()
                        if len(current) == 1 and abs(current[0].get("refreshRate", 0) * 1000 - rate) < 1:
                            break
                        time.sleep(0.03)
                    start = sample(index * 2 + 1)
                    time.sleep(1.0)
                    finish = sample(index * 2 + 2)
                    modes = [{k: monitor.get(k) for k in ("name", "width", "height", "refreshRate", "availableModes")}
                             for monitor in current]
                    stage = {"expected_millihz": rate, "monitors": modes, "start": start, "finish": finish,
                             "requested_millihz": 144000 if index == 3 else None,
                             "parent_frame_delta": finish["frames"] - start["frames"],
                             "mode_match": len(current) == 1 and current[0].get("width") == 640
                             and current[0].get("height") == 360
                             and abs(current[0].get("refreshRate", 0) * 1000 - rate) < 1}
                    result["stages"].append(stage)
                result["hyprland_alive"] = child.poll() is None
                stop(child)
                command("quit")
                parent.wait(timeout=3)
        except (RuntimeError, OSError, subprocess.SubprocessError, ValueError) as error:
            result["failure"] = str(error)
        finally:
            stop(child)
            stop(parent)
            result["parent_exit"] = parent.returncode if parent else None
    parent_text = (args.output / "parent.log").read_text()
    child_text = (args.output / "hyprland.log").read_text() if (args.output / "hyprland.log").exists() else ""
    callbacks = [int(value) for value in re.findall(r"wl_callback[#@]\d+\.done\((\d+)\)", child_text)]
    for stage in result["stages"]:
        stage["parent_frame_callbacks"] = sum(stage["start"]["millis"] <= value <= stage["finish"]["millis"]
                                               for value in callbacks)
    result["protocol_error"] = "ProtocolError(" in parent_text
    if len(result["stages"]) == 4 and all(stage["mode_match"] and stage["parent_frame_delta"] > 0
                                          and stage["parent_frame_callbacks"] > 0 for stage in result["stages"]) \
            and result.get("hyprland_alive") and result["parent_exit"] == 0 and not result["protocol_error"]:
        result["status"] = "parent-refresh-reference-passed"
    result["sha256"] = {"hyprland": digest(binary), "aquamarine": digest(library),
                        "parent": digest(args.parent), "probe": digest(Path(__file__)),
                        "parent_source": digest(Path(__file__).parent / "refresh_parent/src/main.rs")}
    (args.output / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return 0 if result["status"] == "parent-refresh-reference-passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
