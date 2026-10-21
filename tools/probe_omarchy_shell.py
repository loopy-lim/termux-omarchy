"""Owned original Omarchy/Quickshell reference session, with a private HOME."""
import json
from pathlib import Path
import shutil
import subprocess
import time

SOURCE = Path("/workspace/build/omarchy-sources/omarchy")


def prepare_shell(runtime, client_environment, build, signature):
    if not (SOURCE / "shell/shell.qml").is_file():
        raise RuntimeError("missing pinned original Omarchy shell")
    home = runtime / "shell-home"
    home.mkdir(mode=0o700)
    source = home / ".local/share/omarchy"
    shutil.copytree(SOURCE, source, symlinks=True)
    config = home / ".config"
    config.mkdir()
    theme_state = home / ".local/state/omarchy/current"
    theme_state.mkdir(parents=True)
    theme_state.joinpath("theme.name").write_text("tokyo-night\n")
    shutil.copytree(source / "themes/tokyo-night", theme_state / "theme")
    theme_state.joinpath("background").symlink_to(theme_state / "theme/backgrounds/0-winding-road.webp")
    environment = dict(client_environment, HOME=str(home), XDG_CONFIG_HOME=str(config),
                       OMARCHY_PATH=str(source), HYPRLAND_INSTANCE_SIGNATURE=signature,
                       PATH=str(build / "hyprctl") + ":" + str(source / "bin") + ":/usr/bin:/bin",
                       QT_QPA_PLATFORM="wayland")
    return source, environment


def shell_command(source):
    # All these processes belong to the fixture's private process group/runtime.
    launcher = ('pipewire & for ((i=0;i<100;i++)); do '
                '[[ -S "$XDG_RUNTIME_DIR/pipewire-0" ]] && break; sleep .05; done; '
                'wireplumber & exec quickshell "$@"')
    return ["dbus-run-session", "--", "bash", "-c", launcher, "loopy-owned-shell", "-n", "-p", str(source / "shell")]


def shell_ready(process, source, environment, control):
    def call(*arguments):
        reply = subprocess.run(["quickshell", "ipc", "-n", "-p", str(source / "shell"),
                                "call", "--", *arguments],
                               env=environment, capture_output=True, text=True, timeout=2)
        if reply.returncode:
            raise RuntimeError("original shell action IPC failed")
        return reply.stdout.strip()

    def has_layer(namespace, present=True):
        deadline = time.monotonic() + 2
        while process.poll() is None and time.monotonic() < deadline:
            matches = []
            for monitor in control("layers").values():
                for level, layer in monitor.get("levels", {}).items():
                    matches.extend((int(level), item) for item in layer if item.get("namespace") == namespace)
            # Original OverlayWindow deliberately parks closed surfaces at 1x1
            # on the bottom layer; mere namespace presence does not mean open.
            showing = any(item.get("w", 0) > 1 and item.get("h", 0) > 1 and level >= 2 for level, item in matches)
            parked = any(item.get("w") == 1 and item.get("h") == 1 and level == 1 for level, item in matches)
            if (present and showing) or (not present and parked and not showing):
                return True
            time.sleep(0.03)
        return False

    deadline = time.monotonic() + 8
    last = "original shell IPC not ready"
    while process.poll() is None and time.monotonic() < deadline:
        response = subprocess.run(["quickshell", "ipc", "-n", "-p", str(source / "shell"),
                                   "call", "--", "shell", "ping"],
                                  env=environment, capture_output=True, text=True, timeout=2)
        if response.returncode == 0 and response.stdout.strip() == "ok":
            plugins = subprocess.run(["quickshell", "ipc", "-n", "-p", str(source / "shell"),
                                      "call", "--", "shell", "listPlugins"],
                                     env=environment, capture_output=True, text=True, timeout=2)
            if plugins.returncode:
                raise RuntimeError("original shell plugin IPC failed")
            values = json.loads(plugins.stdout)
            bar = has_layer("omarchy-bar")
            menu_reply = call("shell", "summon", "omarchy.menu", '{"menu":"root"}')
            menu = menu_reply == "ok" and has_layer("omarchy-menu")
            call("shell", "hide", "omarchy.menu")
            menu_hidden = has_layer("omarchy-menu", present=False)
            osd_reply = call("shell", "summon", "omarchy.osd", '{"message":"Loopy owned fixture","duration":0}')
            osd = osd_reply == "ok" and has_layer("omarchy-osd")
            call("shell", "hide", "omarchy.osd")
            osd_hidden = has_layer("omarchy-osd", present=False)
            return {"ipc_ping": True, "registered_plugin_count": len(values),
                    "registered_plugin_ids": sorted(item["id"] for item in values),
                    "bar_layer_mapped": bar, "menu_opened": menu, "menu_hidden": menu_hidden,
                    "osd_opened": osd, "osd_hidden": osd_hidden,
                    "alive": process.poll() is None}
        last = (response.stdout + response.stderr).strip()[:180] or last
        time.sleep(0.15)
    raise RuntimeError("original Omarchy shell failed: " + last)
