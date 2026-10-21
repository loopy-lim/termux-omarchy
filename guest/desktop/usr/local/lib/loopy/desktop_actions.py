#!/usr/bin/python3
"""Consume ordered, bounded desktop jobs inside the existing PRoot session."""

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parent))
import desktop_ui as ui
import loopy_input
import mac_commands

APPLICATIONS = {"terminal", "editor", "files", "monitor", "launcher", "overview",
                "browser", "code-ide", "code", "cli-files", "remote", "remote-desktop"}
THEME_NAMES = {"slate", "forest", "paper"}
MODIFIERS = {"CTRL_ALT": "Ctrl+Mod1", "META": "Mod4", "ALT": "Mod1"}
IME_KEYS = {"Return", "BackSpace", "Delete", "Tab", "Escape", "Up", "Down", "Left", "Right", "Home", "End", "Prior", "Next"}
WINDOWS = {"fullscreen": "fullscreen toggle", "floating": "floating toggle",
           "focus-left": "focus left", "focus-right": "focus right", "focus-up": "focus up", "focus-down": "focus down",
           "resize-grow-width": "resize grow width 24 px", "resize-shrink-width": "resize shrink width 24 px",
           "resize-grow-height": "resize grow height 24 px", "resize-shrink-height": "resize shrink height 24 px", "close": "kill",
           "scale-100": "output * scale 1", "scale-125": "output * scale 1.25", "scale-150": "output * scale 1.5",
           "scale-175": "output * scale 1.75", "scale-200": "output * scale 2"}


def validate_command(job):
    if not isinstance(job, dict) or type(job.get("action")) is not str:
        raise ValueError("Invalid desktop command record")
    action = job["action"]
    fields = {"input": {"action", "text", "backspaces"}, "launch": {"action", "app"},
              "workspace": {"action", "target"}, "move-workspace": {"action", "target"},
              "theme": {"action", "name"}, "modifier": {"action", "name"},
              "ime-key": {"action", "key"}, "window": {"action", "operation"}, "edit": {"action", "operation"}}
    if action not in fields or set(job) != fields[action]:
        raise ValueError("Unsupported desktop command fields")
    if action == "input":
        if type(job["text"]) is not str or "\0" in job["text"] or len(job["text"].encode()) > 4096:
            raise ValueError("Input text exceeds its UTF-8 limit")
        if type(job["backspaces"]) is not int or not 0 <= job["backspaces"] <= 64:
            raise ValueError("Invalid input deletion count")
    elif action == "launch" and job["app"] not in APPLICATIONS:
        raise ValueError("Application is outside the desktop allowlist")
    elif action == "workspace" and (type(job["target"]) is not str or job["target"] not in {"next", "prev", *map(str, range(1, 11))}):
        raise ValueError("Invalid desktop workspace")
    elif action == "move-workspace" and (type(job["target"]) is not str or job["target"] not in set(map(str, range(1, 11)))):
        raise ValueError("Invalid desktop workspace")
    elif action == "theme" and job["name"] not in THEME_NAMES:
        raise ValueError("Unknown desktop theme")
    elif action == "modifier" and job["name"] not in MODIFIERS:
        raise ValueError("Unknown desktop modifier")
    elif action == "ime-key" and (type(job["key"]) is not str or job["key"] not in IME_KEYS):
        raise ValueError("Unknown IME key")
    elif action == "window" and (type(job["operation"]) is not str or job["operation"] not in WINDOWS):
        raise ValueError("Unknown window operation")
    elif action == "edit" and (type(job["operation"]) is not str or job["operation"] not in mac_commands.OPERATIONS):
        raise ValueError("Unknown Mac command")
    return job


def setting_current(action, name):
    # initialize has already generated these files before the action worker starts.
    # Reconnecting Android should not disrupt existing clients with two no-op reloads.
    if ui.read_preferences(ui.HOME).get(action) != name:
        return False
    generated = ui.HOME / ".config/loopy"
    required = ("modifier",) if action == "modifier" else ("theme", "foot.ini", "gtk.css", "modifier")
    return all((generated / name).is_file() and not (generated / name).is_symlink() for name in required)


def execute(job):
    validate_command(job)
    if job["action"] == "input":
        if job["text"] or job["backspaces"]:
            loopy_input.inject(text=job["text"], backspaces=job["backspaces"])
    elif job["action"] == "ime-key":
        loopy_input.inject(key=job["key"])
    elif job["action"] == "window":
        ui.sway(WINDOWS[job["operation"]])
    elif job["action"] == "edit":
        mac_commands.execute(job["operation"], ui.sway)
    elif job["action"] == "launch":
        # Menus own their own event loop so the command queue remains responsive.
        subprocess.Popen(["python3", str(Path(__file__).with_name("desktop_ui.py")), job["app"]])
    elif job["action"] == "workspace":
        target = job["target"]
        ui.sway("workspace " + target if target in ("next", "prev") else "workspace number " + target)
    elif job["action"] == "move-workspace":
        window = mac_commands.focused(ui.sway("get_tree", query=True))
        if not window or type(window.get('id')) is not int or window['id'] <= 0:
            raise ValueError("Workspace move has no focused application")
        ui.sway("[con_id=%d] move container to workspace number %s" % (window['id'], job['target']))
    elif job["action"] == "theme":
        if setting_current("theme", job["name"]):
            return
        ui.apply_theme(job["name"], ui.HOME, json.loads(ui.THEMES.read_text()))
        ui.sway("reload")
    elif job["action"] == "modifier":
        if setting_current("modifier", job["name"]):
            return
        ui.set_modifier(job["name"], ui.HOME)
        ui.sway("reload")


def consume(directory, token):
    pattern = re.compile(r"command-" + re.escape(ui.checked_token(token)) + r"-\d{16}\.json")
    jobs = sorted(path for path in Path(directory).glob("command-" + token + "-*.json") if pattern.fullmatch(path.name))
    error_file = Path(directory) / ("error-" + token + ".log")
    for path in jobs[:128]:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
                raise ValueError("Invalid or oversized desktop job file")
            with path.open("rb") as source:
                data = source.read(16385)
            if len(data) > 16384:
                raise ValueError("Desktop job exceeds its limit")
            execute(json.loads(data))
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
            # Do not put typed text or clipboard contents in error reports.
            message = "Desktop command failed: " + type(error).__name__
            if isinstance(error, subprocess.CalledProcessError):
                message += " (exit " + str(error.returncode) + ")"
            try:
                ui.atomic_write(error_file, (message + "\n").encode()[:2048])
            except (OSError, ValueError):
                pass
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def watch():
    directory, token = ui.IPC, ui.checked_token(os.environ["LOOPY_SESSION"])
    notifier = subprocess.Popen(["/bin/busybox", "inotifyd", "-", str(directory) + ":yw"], stdout=subprocess.PIPE, text=True)

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        consume(directory, token)
        for event in notifier.stdout:
            if "command-" + token + "-" in event:
                consume(directory, token)
    finally:
        notifier.terminate()
        try:
            notifier.wait(timeout=3)
        except subprocess.TimeoutExpired:
            notifier.kill()
            notifier.wait()
        notifier.stdout.close()


if __name__ == "__main__":
    try:
        watch()
    except KeyboardInterrupt:
        pass
