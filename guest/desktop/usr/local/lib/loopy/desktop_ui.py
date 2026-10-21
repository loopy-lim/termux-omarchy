#!/usr/bin/python3
"""Real Sway menus and persistent theme preferences; no shell evaluation."""

import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time

COLOR_ROLES = ("background", "surface", "ink", "muted", "border", "accent",
               "red", "green", "yellow", "magenta", "cyan")
TOKEN = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
COMPONENT = re.compile(r"[A-Za-z][A-Za-z0-9_.]*/[A-Za-z0-9_.$]+")
HOME = Path.home()
IPC = Path("/run/loopy")
THEMES = Path("/usr/share/loopy/themes.json")
APPLICATIONS = Path("/usr/share/applications")
DEFAULTS = Path("/usr/share/loopy/defaults")
PREVIOUS_SWAY_DEFAULTS = {
    "a58e6a8dc2416e6a0ea176b80bd395832b38710972478f9d4ab5dee9d7756fbe",
    "0eef5f18310f00f6d032b49a7fe5fc8ac4cb9fad04e1ca0ab75680389481cb52",
    "b316cdca98255db5507762138a135c473ec3f02272fffa59014748a962fa634a",
    "96ad54570ee348c33b7c374e396859fce879abe012b558d42023d8b61cf1d6f5",
    "90d2d26872193dcd1641f65a30af9bbc3f4e8dcd5f12d0260a1387bfda5e5510",
    "548eea9b3900d6055b455518de53dbc0d639ee3bfa1ae65423df400a1550fc40",
    "413de6e20adc34fca795b0da7a237b1b99d5b464f6434bc6ac5c377dd572c651",
}
BLOCKED_LAUNCHERS = {"sh", "ash", "dash", "bash", "env", "python", "python3", "perl", "ruby",
                     "node", "busybox", "pkexec", "sudo", "doas", "su"}


def checked_token(value):
    if not TOKEN.fullmatch(value):
        raise ValueError("Invalid desktop session token")
    return value


def atomic_write(path, data):
    path = Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError("Desktop settings must not cross symlinks")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".loopy-", delete=False) as target:
        temporary = Path(target.name)
        try:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def initialize_defaults(home=HOME, defaults=DEFAULTS, previous=PREVIOUS_SWAY_DEFAULTS):
    """Upgrade only a known shipped Sway default; never overwrite user edits."""
    home, defaults = Path(home), Path(defaults)
    import shell_profile
    shell_profile.install(home)
    config = home / ".config/sway/config"
    source = defaults / "sway/config"
    if source.is_file() and not source.is_symlink() and source.stat().st_size <= 16384:
        new_config = source.read_bytes()
        if config.is_file() and not config.is_symlink() and config.stat().st_size <= 16384:
            if hashlib.sha256(config.read_bytes()).hexdigest() in previous:
                atomic_write(config, new_config)
        elif not config.exists() and not config.is_symlink() \
                and not any(parent.is_symlink() for parent in config.parents):
            config.parent.mkdir(parents=True, exist_ok=True)
            with config.open("xb") as target:
                target.write(new_config)
    foot, foot_default = home / ".config/foot/foot.ini", defaults / "foot/foot.ini"
    if foot_default.is_file() and not foot_default.is_symlink() and foot_default.stat().st_size <= 16384 \
            and foot.is_file() and not foot.is_symlink() and foot.stat().st_size <= 16384 \
            and hashlib.sha256(foot.read_bytes()).hexdigest() == "662d0d5d90191733434bb58269d510d936f5a07e676df442240a89c45569a226":
        atomic_write(foot, foot_default.read_bytes())
    sample = home / "Projects/hello.py"
    example = defaults / "Projects/hello.py"
    if example.is_file() and not example.is_symlink() and example.stat().st_size <= 16384 \
            and not sample.exists() and not sample.is_symlink() \
            and not any(parent.is_symlink() for parent in sample.parents):
        sample.parent.mkdir(parents=True, exist_ok=True)
        with sample.open("xb") as target:
            target.write(example.read_bytes())


def label(value):
    return " ".join(str(value).split())[:100]


def android_entries(directory, token):
    checked_token(token)
    catalog = Path(directory) / ("apps-" + token + ".tsv")
    if catalog.is_symlink() or not catalog.is_file() or catalog.stat().st_size > 256 * 1024:
        return []
    entries, seen = [], set()
    for line in catalog.read_text(encoding="utf-8").splitlines()[:500]:
        parts = line.split("\t")
        if len(parts) != 2 or not COMPONENT.fullmatch(parts[0]) or parts[0] in seen:
            continue
        seen.add(parts[0])
        entries.append({"label": "Android · " + label(parts[1]), "component": parts[0]})
    return entries


def write_request(directory, token, action, component=""):
    checked_token(token)
    if action not in ("browser", "settings", "launch"):
        raise ValueError("Unsupported Android request")
    if action == "launch":
        if component not in {e["component"] for e in android_entries(directory, token)}:
            raise ValueError("Android component is outside the session catalog")
    elif component:
        raise ValueError("Unexpected Android component")
    text = action + ("\t" + component if component else "") + "\n"
    atomic_write(Path(directory) / ("request-" + token), text.encode())


def window_entries(tree, workspace=""):
    workspace = label(tree.get("name", "")) if tree.get("type") == "workspace" else workspace
    result = []
    identifier = tree.get("id")
    if type(identifier) is int and identifier > 0 and (tree.get("app_id") or tree.get("window")):
        result.append({"id": identifier, "label": f"[{workspace}] {label(tree.get('name') or tree.get('app_id'))}"})
    for child in tree.get("nodes", []) + tree.get("floating_nodes", []):
        result.extend(window_entries(child, workspace))
    return result


def focus_command(identifier):
    if type(identifier) is not int or identifier <= 0:
        raise ValueError("Invalid Sway container id")
    return f"[con_id={identifier}] focus"


def apply_theme(name, home, themes):
    if name not in themes:
        raise ValueError("Unknown desktop theme")
    palette = themes[name]
    if set(palette) != set(COLOR_ROLES) or not all(re.fullmatch("[0-9a-fA-F]{6}", c) for c in palette.values()):
        raise ValueError("Invalid desktop theme tokens")
    home, generated = Path(home), Path(home) / ".config/loopy"
    theme = "\n".join(f"set ${role} #{palette[role]}" for role in COLOR_ROLES) + "\n"
    atomic_write(generated / "theme", theme.encode())
    foot = configparser.ConfigParser(interpolation=None)
    base = home / ".config/foot/foot.ini"
    if base.is_symlink():
        raise ValueError("User terminal settings must not be a symlink")
    foot.read(base)
    if not foot.has_section("main"):
        foot.add_section("main")
    if not foot.has_section("colors"):
        foot.add_section("colors")
    foot.set("colors", "background", palette["background"])
    foot.set("colors", "foreground", palette["ink"])
    roles = ("surface", "red", "green", "yellow", "accent", "magenta", "cyan", "ink")
    for i, role in enumerate(roles):
        foot.set("colors", "regular" + str(i), palette[role])
        foot.set("colors", "bright" + str(i), palette["muted"] if i == 0 else palette[role])
    if not foot.has_section("cursor"):
        foot.add_section("cursor")
    foot.set("cursor", "color", palette["background"] + " " + palette["ink"])
    import io
    output = io.StringIO()
    foot.write(output)
    atomic_write(generated / "foot.ini", output.getvalue().encode())
    css = (f"window, .background {{ background-color: #{palette['surface']}; color: #{palette['ink']}; }}\n"
           f"headerbar, .titlebar {{ background: #{palette['background']}; color: #{palette['ink']}; }}\n"
           f"selection, button:checked {{ background: #{palette['accent']}; color: #{palette['background']}; }}\n")
    atomic_write(generated / "gtk.css", css.encode())
    preferences = read_preferences(home)
    preferences["theme"] = name
    atomic_write(generated / "preferences.json", (json.dumps(preferences) + "\n").encode())
    set_modifier(preferences.get("modifier", "CTRL_ALT"), home)
    user = home / ".config/sway/user.conf"
    if not user.exists():
        atomic_write(user, b"# Your Sway overrides are preserved across theme changes.\n")


def read_preferences(home=HOME):
    try:
        path = Path(home) / ".config/loopy/preferences.json"
        if path.is_symlink() or path.stat().st_size > 4096:
            raise ValueError("Invalid desktop preferences file")
        preferences = json.loads(path.read_text())
        return preferences if isinstance(preferences, dict) else {}
    except (OSError, ValueError):
        return {}


def set_modifier(name, home=HOME):
    modifiers = {"CTRL_ALT": "Ctrl+Mod1", "META": "Mod4", "ALT": "Mod1"}
    if name not in modifiers:
        raise ValueError("Unknown desktop modifier")
    generated = Path(home) / ".config/loopy"
    preferences = read_preferences(home)
    preferences["modifier"] = name
    atomic_write(generated / "modifier", ("set $mod " + modifiers[name] + "\n").encode())
    atomic_write(generated / "preferences.json", (json.dumps(preferences) + "\n").encode())


def sway(command, query=False):
    argv = ["swaymsg", "-s", os.environ["SWAYSOCK"]]
    argv += ["-r", "-t", command] if query else [command]
    result = subprocess.run(argv, check=True, capture_output=True, text=True, timeout=10)
    if len(result.stdout.encode()) > 8 * 1024 * 1024:
        raise ValueError("Sway response exceeds its limit")
    return json.loads(result.stdout) if query else None


def choose(entries, prompt):
    if not entries:
        return None
    lines = [f"{i + 1:02d}  {entry['label']}" for i, entry in enumerate(entries)]
    themes = json.loads(THEMES.read_text())
    palette = themes.get(read_preferences(HOME).get("theme"), next(iter(themes.values())))
    colors = [argument for flag, role in (("-N", "surface"), ("-n", "ink"), ("-M", "accent"),
              ("-m", "background"), ("-S", "accent"), ("-s", "background")) for argument in (flag, palette[role])]
    result = subprocess.run(["wmenu", "-i", "-p", prompt, "-f", "Noto Sans CJK KR 13", "-l", "12"] + colors,
                            input="\n".join(lines) + "\n", text=True, capture_output=True)
    selected = result.stdout.strip()
    return entries[lines.index(selected)] if result.returncode == 0 and selected in lines else None


def application_command(app, home=HOME):
    shared = Path("/mnt/shared")
    folder = str(shared if shared.is_dir() else home)
    graphical = {"editor": ["mousepad", "--disable-server"], "files": ["thunar", folder],
                 "browser": ["/usr/local/bin/loopy-browser"], "remote": ["/usr/local/bin/loopy-remote"],
                 "remote-desktop": ["/usr/local/bin/loopy-remote-desktop"],
                 "code-ide": ["geany", str(Path(home) / "Projects/hello.py")]}
    if app in graphical:
        return graphical[app]
    commands = {"terminal": ["zsh", "-l"], "code": ["nvim"],
                "cli-files": ["yazi", folder], "monitor": ["btop"]}
    if app not in commands:
        raise ValueError("Unknown Linux application")
    return ["foot", "--config", str(Path(home) / ".config/loopy/foot.ini"), "-a", "loopy-" + app] + commands[app]


def installed_applications(directory=APPLICATIONS, bin_directory=Path("/usr/bin")):
    """Read bounded system .desktop entries; never evaluate Exec through a shell."""
    applications, binaries = Path(directory), Path(bin_directory)
    entries = []
    for path in sorted(applications.glob("*.desktop"))[:256]:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
            continue
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            parser.read_string(path.read_text(encoding="utf-8"))
            item = parser["Desktop Entry"]
            if item.get("Type") != "Application" or item.getboolean("Hidden", fallback=False) \
                    or item.getboolean("NoDisplay", fallback=False) or item.getboolean("Terminal", fallback=False):
                continue
            argv = shlex.split(item["Exec"])
            if not argv or any("%" in value and value not in ("%f", "%F", "%u", "%U") for value in argv):
                continue
            executable = Path(argv[0]) if argv[0].startswith("/") else binaries / argv[0]
            if executable.parent != binaries or executable.name in BLOCKED_LAUNCHERS \
                    or not executable.is_file() or not os.access(executable, os.X_OK):
                continue
            command = [str(executable)] + [value for value in argv[1:] if value not in ("%f", "%F", "%u", "%U")]
            entries.append({"label": label(item["Name"]), "argv": command})
        except (OSError, UnicodeError, ValueError, KeyError, configparser.Error):
            continue
    return entries


def installed_menu():
    entry = choose(installed_applications(), "Linux apps")
    if entry:
        subprocess.Popen(entry["argv"])


def launch(app):
    if app == "launcher":
        menu()
    elif app == "overview":
        overview()
    else:
        subprocess.Popen(application_command(app))


def overview():
    entry = choose(window_entries(sway("get_tree", query=True)), "Windows")
    if entry:
        sway(focus_command(entry["id"]))


def workspaces():
    existing = sway("get_workspaces", query=True)
    entries = [{"label": f"Workspace {n}" + (" · active" if any(w.get("num") == n and w.get("focused") for w in existing) else ""),
                "number": n} for n in range(1, 11)]
    entry = choose(entries, "Workspaces")
    if entry:
        sway("workspace number " + str(entry["number"]))


def themes_menu():
    themes = json.loads(THEMES.read_text())
    entry = choose([{"label": name.title(), "name": name} for name in themes], "Themes")
    if entry:
        apply_theme(entry["name"], HOME, themes)
        sway("reload")


def menu():
    token = checked_token(os.environ["LOOPY_SESSION"])
    entries = [{"label": name, "app": app} for name, app in (
        ("Terminal", "terminal"), ("Files · shared folder", "files"), ("Editor", "editor"),
        ("Linux browser · Loopy Browser", "browser"), ("Code IDE · Geany", "code-ide"),
        ("Code · Neovim", "code"), ("CLI files · Yazi", "cli-files"), ("System monitor", "monitor"))]
    entries += [{"label": "Other Linux apps", "menu": "installed"},
                {"label": "Window overview", "menu": "overview"}, {"label": "Workspaces", "menu": "workspaces"},
                {"label": "Themes", "menu": "themes"}, {"label": "GPU alternatives / check", "menu": "graphics"},
                {"label": "Android Browser", "action": "browser"},
                {"label": "Android Settings", "action": "settings"}]
    entries += [{**e, "action": "launch"} for e in android_entries(IPC, token)]
    entry = choose(entries, "Loopy Desktop")
    if not entry:
        return
    if "app" in entry:
        launch(entry["app"])
    elif "menu" in entry:
        {"installed": installed_menu, "overview": overview, "workspaces": workspaces,
         "themes": themes_menu, "graphics": lambda: subprocess.Popen(
             ["foot", "/usr/local/bin/loopy-graphics"])}[entry["menu"]]()
    else:
        write_request(IPC, token, entry["action"], entry.get("component", ""))


def status_text(directory, token, home, clock):
    path = Path(directory) / ("language-" + checked_token(token))
    language = "EN"
    try:
        if not path.is_symlink() and path.is_file() and path.stat().st_size <= 16:
            with path.open("rb") as source:
                content = source.read(17).decode("utf-8").strip()
            if content in ("EN", "한"):
                language = content
    except (OSError, ValueError):
        pass
    modifier = {"CTRL_ALT": "Ctrl+Alt", "META": "Meta", "ALT": "Alt"}.get(
        read_preferences(home).get("modifier"), "Ctrl+Alt")
    return f"Loopy Desktop  |  {language}  |  Apps: {modifier}+Space  ·  Windows: {modifier}+Tab  ·  Workspaces: 1–9  |  {clock}"


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "launcher"
    if action == "initialize":
        initialize_defaults()
        themes = json.loads(THEMES.read_text())
        selected = read_preferences().get("theme", "slate")
        apply_theme(selected if selected in themes else "slate", HOME, themes)
    elif action in ("terminal", "editor", "files", "monitor", "code", "cli-files", "browser", "code-ide", "remote", "remote-desktop"):
        launch(action)
    elif action in ("launcher", "overview", "workspaces", "themes"):
        {"launcher": menu, "overview": overview, "workspaces": workspaces, "themes": themes_menu}[action]()
    elif action == "status":
        token = checked_token(os.environ["LOOPY_SESSION"])
        while True:
            print(status_text(IPC, token, HOME, time.strftime("%H:%M")), flush=True)
            time.sleep(1)
    else:
        raise ValueError("Unknown desktop menu")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"Desktop action failed: {error}", file=sys.stderr)
        sys.exit(1)
