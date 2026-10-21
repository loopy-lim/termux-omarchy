#!/usr/bin/env python3
"""Actual patched Hyprland/foot probe in an owned, private ARM VM session."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.probe_omarchy_shell import prepare_shell, shell_command, shell_ready

BUILD = Path("/var/tmp/loopy-hyprland-case-sensitive")
LIBRARY = Path("/var/tmp/loopy-aquamarine-configured")
PARENT = Path("/var/tmp/loopy-omarchy-target/debug/examples/omarchy_parent")


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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build", type=Path, default=BUILD)
    parser.add_argument("--library", type=Path, default=LIBRARY)
    parser.add_argument("--quickshell", action="store_true", help="run original pinned Omarchy shell in private HOME")
    args = parser.parse_args()
    if os.getuid() == 0 or not Path("/workspace/native/omarchy/tests/gles3_shm.cpp").is_file():
        parser.error("requires ordinary user in the scoped ARM VM")
    for directory, prefix in ((args.build, "loopy-hyprland-"), (args.library, "loopy-aquamarine-")):
        if directory.parent != Path("/var/tmp") or not directory.name.startswith(prefix) or directory.is_symlink():
            parser.error("requires scoped Linux filesystem build artifacts")
    binary, controller = args.build / "Hyprland", args.build / "hyprctl/hyprctl"
    for artifact in (binary, controller, PARENT, args.library / "libaquamarine.so.0.15.1"):
        if not artifact.is_file():
            parser.error("missing scoped build artifact: " + str(artifact))
    args.output.mkdir(parents=True, exist_ok=True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    result = {"uid": os.getuid(), "physical_device": False, "hardware_gpu": False,
              "omarchy_support_complete": False, "status": "not-accepted"}
    parent = child = client = shell = None
    with tempfile.TemporaryDirectory(prefix="lhls-") as directory:
        runtime = Path(directory)
        runtime.chmod(0o700)
        for name in ("config", "cache", "state", "data"):
            (runtime / name).mkdir()
        config = runtime / "hyprland.lua"
        config.write_text("hl.config({debug={disable_logs=false,enable_stdout_logs=true}})\n"
                          "for i=1,10 do local key=i%10; hl.bind('SUPER + '..key,hl.dsp.focus({workspace=i})); "
                          "hl.bind('SUPER + SHIFT + '..key,hl.dsp.window.move({workspace=i,follow=false})); end\n")
        foot_config = runtime / "foot.ini"
        foot_config.write_text("[main]\nfont=JetBrainsMono Nerd Font Mono:size=14\n[colors-dark]\nbackground=001122\nforeground=ffffff\n")
        font_config = runtime / "fonts.conf"
        font_config.write_text("<fontconfig><dir>/workspace/guest/desktop/usr/share/fonts/truetype</dir><cachedir>" + str(runtime / "cache/fontconfig") + "</cachedir></fontconfig>\n")
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LD_LIBRARY_PATH": str(args.library),
               "XDG_RUNTIME_DIR": directory, "WAYLAND_DISPLAY": "loopy-parent", "AQ_SHM_ONLY": "1",
               "LIBGL_ALWAYS_SOFTWARE": "1", "HYPRLAND_NO_SD_NOTIFY": "1", "HYPRLAND_NO_SD_VARS": "1",
               "XDG_CONFIG_HOME": str(runtime / "config"), "XDG_CACHE_HOME": str(runtime / "cache"),
               "XDG_STATE_HOME": str(runtime / "state"), "XDG_DATA_HOME": str(runtime / "data")}
        env["FONTCONFIG_FILE"] = str(font_config)
        # Retain the build VM's identity; never forward credentials or Mac HOME.
        for key in ("HOME", "USER", "LOGNAME"):
            if key in os.environ:
                env[key] = os.environ[key]
        result["hyprland"] = json.loads(subprocess.check_output([str(binary), "--version-json"], env=env, text=True, timeout=5))
        verified = subprocess.run([str(binary), "--verify-config", "--config", str(config)], env=env, capture_output=True, text=True, timeout=5)
        result["config_exit"] = verified.returncode
        try:
            with (args.output / "parent.log").open("w") as parent_log, (args.output / "hyprland.log").open("w") as child_log, (args.output / "foot.log").open("w") as client_log:
                parent = subprocess.Popen([str(PARENT), str(runtime / "loopy-parent"), "35" if args.quickshell else "20", "scene-fixture"], stdin=subprocess.PIPE, text=True, stdout=parent_log, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 2
                while not (runtime / "loopy-parent").exists():
                    if parent.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("owned parent did not start")
                    time.sleep(0.02)
                child = subprocess.Popen([str(binary), "--config", str(config)], env=env, stdout=child_log, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 8
                sockets = []
                while not sockets:
                    sockets = list(runtime.glob("hypr/*/.socket.sock"))
                    if child.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Hyprland IPC did not become ready")
                    time.sleep(0.05)
                signature = sockets[0].parent.name
                def control(*arguments, structured=True):
                    command = [str(controller), "-i", signature]
                    if structured:
                        command.append("-j")
                    completed = subprocess.run([*command, *arguments], env=env, capture_output=True, text=True, timeout=3)
                    if completed.returncode:
                        raise RuntimeError("owned IPC failed: " + completed.stdout.strip()[:200])
                    return json.loads(completed.stdout) if structured else completed.stdout.strip()
                monitors = control("monitors")
                deadline = time.monotonic() + 3
                while not monitors or any(m.get("width", 0) <= 0 or m.get("height", 0) <= 0 for m in monitors):
                    if child.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Hyprland output mode did not become ready")
                    time.sleep(0.05)
                    monitors = control("monitors")
                result["monitors"] = [{k: m.get(k) for k in ("name", "width", "height", "refreshRate", "scale")} for m in monitors]
                inner_socket = runtime / "wayland-1"
                if not inner_socket.exists():
                    matches = [p for p in runtime.glob("wayland-*") if p.is_socket()]
                    if len(matches) != 1:
                        raise RuntimeError("cannot identify owned inner Wayland socket")
                    inner_socket = matches[0]
                client_env = dict(env, WAYLAND_DISPLAY=inner_socket.name)
                input_marker = runtime / "owned-input.txt"
                input_after_shell = runtime / "owned-input-after-shell.txt"
                client = subprocess.Popen(["foot", "--config", str(foot_config), "--app-id", "loopy-owned-fixture", "--title", "Loopy owned probe", "/bin/sh", "-c", "printf 'LOOPY_OMARCHY_OWNED_FIXTURE\\n\\033[?1000h\\033[?1006h'; read -r reply; printf '%s' \"$reply\" > \"$1\"; printf '\\033[?1000l\\033[?1006l'; read -r waiting; printf '%s' \"$waiting\" > \"$2\"; read -r third", "loopy-fixture", str(input_marker), str(input_after_shell)], env=client_env, stdout=client_log, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 4
                clients = []
                while not clients or not clients[0].get("mapped", False):
                    clients = control("clients")
                    if client.poll() is not None or child.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("owned foot window did not map")
                    time.sleep(0.05)
                if len(clients) != 1 or clients[0].get("class") != "loopy-owned-fixture":
                    raise RuntimeError("unexpected client in private fixture")
                def inject(command):
                    parent.stdin.write(command + "\n")
                    parent.stdin.flush()
                inject("click")
                time.sleep(0.05)
                inject("type")
                deadline = time.monotonic() + 2
                while not input_marker.is_file() and time.monotonic() < deadline:
                    time.sleep(0.02)
                actual_input = input_marker.read_text() if input_marker.is_file() else ""
                result["synthetic_terminal_input"] = actual_input.endswith("loopy")
                result["synthetic_terminal_left_press_release"] = bool(re.fullmatch(
                    r"\x1b\[<0;\d+;\d+M\x1b\[<0;\d+;\d+mloopy", actual_input))
                keyboard = []
                for number in range(1, 11):
                    inject("workspace:" + str(number))
                    deadline = time.monotonic() + 0.4
                    while time.monotonic() < deadline and control("activeworkspace")["id"] != number:
                        time.sleep(0.01)
                    keyboard.append(control("activeworkspace")["id"] == number)
                result["synthetic_meta_all_workspaces"] = all(keyboard)
                control("dispatch", 'hl.dsp.window.move({workspace="10",follow=false,window=' + json.dumps("address:" + clients[0]["address"]) + '})', structured=False)
                moves = []
                for number in range(1, 11):
                    previous = control("clients")[0]["workspace"]["id"]
                    inject("workspace:" + str(previous))
                    time.sleep(0.05)
                    inject("move:" + str(number))
                    deadline = time.monotonic() + 0.4
                    while time.monotonic() < deadline and control("clients")[0]["workspace"]["id"] != number:
                        time.sleep(0.01)
                    moves.append(control("clients")[0]["workspace"]["id"] == number and control("activeworkspace")["id"] == previous)
                result["synthetic_meta_shift_all_moves_without_follow"] = all(moves)
                inject("workspace:10")
                time.sleep(0.05)
                inject("move:1")
                time.sleep(0.1)
                inject("workspace:1")
                time.sleep(0.05)
                inject("move:2")
                time.sleep(0.1)
                result["synthetic_meta_shift_move"] = control("clients")[0]["workspace"]["id"] == 2
                result["synthetic_move_without_follow"] = control("activeworkspace")["id"] == 1
                inject("workspace:2")
                time.sleep(0.05)
                address = clients[0]["address"]
                if not re.fullmatch(r"0x[0-9a-fA-F]+", address):
                    raise RuntimeError("unexpected owned window address")
                before_move = control("activeworkspace")["id"]
                control("dispatch", 'hl.dsp.window.move({workspace="2",follow=false,window=' + json.dumps("address:" + address) + '})', structured=False)
                moved = control("clients")[0]
                result["window_moved_to_workspace_2"] = moved["workspace"]["id"] == 2
                result["window_move_without_follow"] = control("activeworkspace")["id"] == before_move
                control("dispatch", 'hl.dsp.focus({workspace="2"})', structured=False)
                result["workspace_switch_to_2"] = control("activeworkspace")["id"] == 2
                result["owned_foot_mapped"] = bool(clients[0].get("mapped", True))
                result["hyprland_alive"] = child.poll() is None
                if args.quickshell:
                    shell_source, shell_env = prepare_shell(runtime, client_env, args.build, signature)
                    with (args.output / "quickshell.log").open("w") as shell_log:
                        shell = subprocess.Popen(shell_command(shell_source),
                                                 env=shell_env, stdout=shell_log, stderr=subprocess.STDOUT, start_new_session=True)
                        result["original_shell"] = shell_ready(shell, shell_source, shell_env, control)
                        inject("click")
                        time.sleep(0.05)
                        inject("type")
                        deadline = time.monotonic() + 2
                        while not input_after_shell.is_file() and time.monotonic() < deadline:
                            time.sleep(0.02)
                        result["input_after_shell_popups_closed"] = input_after_shell.is_file() and input_after_shell.read_text() == "loopy"
                        time.sleep(0.3)
                        stop(shell)
                time.sleep(0.3)
                stop(client); stop(child)
                parent.wait(timeout=37)
        except (RuntimeError, subprocess.SubprocessError, OSError, ValueError, KeyError) as error:
            result["failure"] = str(error)
        finally:
            stop(shell); stop(client); stop(child); stop(parent)
            for process, name in ((parent, "parent"), (child, "hyprland"), (client, "foot")):
                if process:
                    result[name + "_exit"] = process.returncode
    log = (args.output / "parent.log").read_text() if (args.output / "parent.log").exists() else ""
    for key in ("headless_frames", "scene_renders", "scene_changes"):
        match = re.search(key + r"=(\d+)", log)
        result[key] = int(match[1]) if match else 0
    result["scene_colored"] = "scene_colored=true" in log
    result["owned_terminal_background"] = "terminal_background=true" in log
    result["protocol_error"] = "ProtocolError(" in log
    if all(result.get(k) for k in ("owned_foot_mapped", "window_moved_to_workspace_2", "window_move_without_follow", "workspace_switch_to_2", "hyprland_alive", "scene_renders", "scene_colored", "owned_terminal_background", "synthetic_terminal_input", "synthetic_terminal_left_press_release", "synthetic_meta_all_workspaces", "synthetic_meta_shift_all_moves_without_follow", "synthetic_meta_shift_move", "synthetic_move_without_follow")) and not result["protocol_error"]:
        result["status"] = "owned-hyprland-foot-reference-passed"
    result["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    if args.quickshell:
        if result["status"] == "owned-hyprland-foot-reference-passed" and all(
                result.get("original_shell", {}).get(key) for key in ("ipc_ping", "bar_layer_mapped", "menu_opened", "menu_hidden", "osd_opened", "osd_hidden", "alive")) and result.get("input_after_shell_popups_closed"):
            result["status"] = "owned-original-omarchy-shell-reference-passed"
        else:
            result["status"] = "not-accepted"
    result["library_sha256"] = hashlib.sha256((args.library / "libaquamarine.so.0.15.1").read_bytes()).hexdigest()
    result["probe_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["parent_binary_sha256"] = hashlib.sha256(PARENT.read_bytes()).hexdigest()
    result["shell_probe_sha256"] = hashlib.sha256(Path(__file__).with_name("probe_omarchy_shell.py").read_bytes()).hexdigest()
    result["lock_sha256"] = hashlib.sha256(Path("/workspace/third_party/omarchy.lock.json").read_bytes()).hexdigest()
    (args.output / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "hyprland"}))
    return 0 if result["status"] in ("owned-hyprland-foot-reference-passed", "owned-original-omarchy-shell-reference-passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
