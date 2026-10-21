"""The guest desktop bridge: safe menu, clipboard, actions, status and theming."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

UI_PATH = Path(__file__).resolve().parents[1] / "guest/desktop/usr/local/lib/loopy/desktop_ui.py"
CLIP_PATH = UI_PATH.with_name("desktop_clipboard.py")
ACTION_PATH = UI_PATH.with_name("desktop_actions.py")


def load_helper(path):
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    old = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old
    return module


ui = load_helper(UI_PATH)
clip = load_helper(CLIP_PATH)
actions = load_helper(ACTION_PATH)


class DesktopGuestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()

    def test_android_launch_requests_accept_only_catalogued_components(self):
        self.assertIsNotNone(ui, "The desktop application menu has not been implemented")
        token = "12345678-1234-1234-1234-123456789abc"
        (self.directory / ("apps-" + token + ".tsv")).write_text("dev.example/.Main\tExample\ninvalid;command\tUnsafe\n")
        entries = ui.android_entries(self.directory, token)
        self.assertEqual([(e["label"], e["component"]) for e in entries], [("Android · Example", "dev.example/.Main")])
        ui.write_request(self.directory, token, "launch", "dev.example/.Main")
        self.assertEqual((self.directory / ("request-" + token)).read_text(), "launch\tdev.example/.Main\n")
        with self.assertRaises(ValueError):
            ui.write_request(self.directory, token, "launch", "dev.other/.Main")
        with self.assertRaises(ValueError):
            ui.write_request(self.directory, "../escape", "browser")
        with self.assertRaises(ValueError):
            ui.write_request(self.directory, token, "eval", "id")

    def test_window_switcher_uses_actual_sway_leaf_ids(self):
        self.assertIsNotNone(ui, "The desktop window switcher has not been implemented")
        tree = {"type": "root", "nodes": [{"type": "workspace", "name": "2", "nodes": [
            {"type": "con", "id": 41, "app_id": "foot", "name": "Editor", "nodes": []}],
            "floating_nodes": [{"type": "con", "id": 42, "app_id": "files", "name": "Files\nInjected", "nodes": []}]}]}
        windows = ui.window_entries(tree)
        self.assertEqual([e["id"] for e in windows], [41, 42])
        self.assertTrue(all("\n" not in e["label"] for e in windows))
        self.assertEqual(ui.focus_command(41), "[con_id=41] focus")
        with self.assertRaises(ValueError):
            ui.focus_command("41]; exec bad")

    def test_editor_and_files_launch_graphical_programs_and_keep_cli_tools_separate(self):
        self.assertIsNotNone(ui, "The desktop application menu has not been implemented")
        self.assertTrue(hasattr(ui, "application_command"), "Graphical application commands have not been implemented")
        self.assertEqual(ui.application_command("editor", self.directory), ["mousepad", "--disable-server"])
        self.assertEqual(ui.application_command("files", self.directory)[0], "thunar")
        self.assertEqual(ui.application_command("code", self.directory)[-1], "nvim")
        self.assertEqual(ui.application_command("cli-files", self.directory)[-2], "yazi")
        self.assertEqual(ui.application_command("browser", self.directory), ["/usr/local/bin/loopy-browser"])
        self.assertEqual(ui.application_command("code-ide", self.directory), ["geany", str(self.directory / "Projects/hello.py")])
        with self.assertRaises(ValueError):
            ui.application_command("arbitrary-shell", self.directory)

    def test_installed_desktop_entries_use_argv_and_ignore_shell_wrappers(self):
        apps, binaries = self.directory / "applications", self.directory / "bin"
        apps.mkdir()
        binaries.mkdir()
        for name in ("geany", "sh"):
            program = binaries / name
            program.write_text("#!/bin/sh\nexit 0\n")
            program.chmod(0o755)
        (apps / "geany.desktop").write_text("[Desktop Entry]\nType=Application\nName=Code IDE\nExec=geany --new-instance %F\n")
        (apps / "unsafe.desktop").write_text("[Desktop Entry]\nType=Application\nName=Unsafe\nExec=sh -c 'touch /tmp/unsafe'\n")
        (apps / "embedded.desktop").write_text("[Desktop Entry]\nType=Application\nName=Embedded\nExec=geany --file=%f\n")
        self.assertEqual(ui.installed_applications(apps, binaries),
                         [{"label": "Code IDE", "argv": [str(binaries / "geany"), "--new-instance"]}])

    def test_persistent_home_replaces_only_known_default_and_creates_missing_sample(self):
        product_defaults = Path(__file__).resolve().parents[1] / "guest/desktop/usr/share/loopy/defaults"
        product_root = Path(__file__).resolve().parents[1] / "guest/desktop/root"
        self.assertEqual((product_defaults / "sway/config").read_bytes(), (product_root / ".config/sway/config").read_bytes())
        self.assertEqual((product_defaults / "Projects/hello.py").read_bytes(), (product_root / "Projects/hello.py").read_bytes())
        home, defaults = self.directory / "home", self.directory / "defaults"
        (home / ".config/sway").mkdir(parents=True)
        (defaults / "sway").mkdir(parents=True)
        (defaults / "Projects").mkdir()
        old = b"old shipped config\n"
        config = home / ".config/sway/config"
        config.write_bytes(old)
        (defaults / "sway/config").write_bytes(b"new shipped config\n")
        (defaults / "Projects/hello.py").write_bytes(b"print('example')\n")
        ui.initialize_defaults(home, defaults, {hashlib.sha256(old).hexdigest()})
        self.assertEqual(config.read_bytes(), b"new shipped config\n")
        self.assertEqual((home / "Projects/hello.py").read_bytes(), b"print('example')\n")
        config.write_bytes(b"user config\n")
        (home / "Projects/hello.py").write_bytes(b"private code\n")
        ui.initialize_defaults(home, defaults, {hashlib.sha256(old).hexdigest()})
        self.assertEqual(config.read_bytes(), b"user config\n")
        self.assertEqual((home / "Projects/hello.py").read_bytes(), b"private code\n")

    def test_theme_tokens_update_generated_configs_without_overwriting_user_settings(self):
        self.assertIsNotNone(ui, "Desktop theme settings have not been implemented")
        themes = {"slate": {key: "112233" for key in ui.COLOR_ROLES},
                  "light": {key: "ddeeff" for key in ui.COLOR_ROLES}}
        base = self.directory / ".config/foot/foot.ini"
        base.parent.mkdir(parents=True)
        base.write_text("[main]\nfont=Custom Mono:size=15\n")
        user = self.directory / ".config/sway/user.conf"
        user.parent.mkdir(parents=True)
        user.write_text("gaps inner 13\n")
        ui.apply_theme("light", self.directory, themes)
        self.assertEqual(user.read_text(), "gaps inner 13\n")
        self.assertEqual(base.read_text(), "[main]\nfont=Custom Mono:size=15\n")
        self.assertIn("Custom Mono:size=15", (self.directory / ".config/loopy/foot.ini").read_text())
        self.assertIn("set $background #ddeeff", (self.directory / ".config/loopy/theme").read_text())
        self.assertEqual(json.loads((self.directory / ".config/loopy/preferences.json").read_text())["theme"], "light")
        with self.assertRaises(ValueError):
            ui.apply_theme("arbitrary", self.directory, themes)

    def test_launcher_uses_selected_theme_without_running_typed_menu_commands(self):
        result = type("Result", (), {"stdout": "typed; unsafe", "returncode": 0})()
        themes = {"forest": {key: "123456" for key in ui.COLOR_ROLES}}
        theme_file = self.directory / "themes.json"
        theme_file.write_text(json.dumps(themes))
        with patch.object(ui, "HOME", self.directory), patch.object(ui, "THEMES", theme_file):
            ui.apply_theme("forest", self.directory, themes)
            with patch.object(ui.subprocess, "run", return_value=result) as run:
                self.assertIsNone(ui.choose([{"label": "Editor"}], "Apps"))
            arguments = run.call_args.args[0]
            self.assertIn("-N", arguments)
            self.assertEqual(arguments[arguments.index("-N") + 1], "123456")
            self.assertIn("-l", arguments)

    def test_clipboard_records_are_bounded_atomic_and_clearable(self):
        self.assertIsNotNone(clip, "The inner desktop clipboard exporter has not been implemented")
        path = self.directory / "clip-guest-session"
        self.assertTrue(clip.publish(path, "한글".encode()))
        self.assertEqual(clip.read_text(path), "한글")
        self.assertTrue(clip.publish(path, "한글".encode()))
        self.assertFalse(clip.publish(path, b"x" * 65537))
        self.assertEqual(clip.read_text(path), "한글")
        self.assertTrue(clip.publish(path, b""))
        self.assertEqual(clip.read_text(path), "")
        path.unlink()
        path.symlink_to(self.directory / "outside")
        with self.assertRaises(ValueError):
            clip.publish(path, b"unsafe")

    def test_action_jobs_preserve_unicode_as_arguments_and_reject_untrusted_commands(self):
        self.assertIsNotNone(actions, "The persistent desktop action worker has not been implemented")
        job = {"action": "input", "text": "한글; $(touch /tmp/unsafe)", "backspaces": 2}
        with patch.object(actions.loopy_input, "inject") as inject:
            actions.execute(job)
            inject.assert_called_once_with(text="한글; $(touch /tmp/unsafe)", backspaces=2)
        for app in ("browser", "code-ide", "code", "cli-files"):
            self.assertEqual(actions.validate_command({"action": "launch", "app": app})["app"], app)
        invalid = [{"action": "input", "text": "x" * 4097, "backspaces": 0},
                   {"action": "input", "text": "ok", "backspaces": 65},
                   {"action": "launch", "app": "sh -c unsafe"},
                   {"action": "workspace", "target": "1; exec unsafe"},
                   {"action": "modifier", "name": "CTRL"},
                   {"action": "theme", "name": "arbitrary"}]
        for item in invalid:
            with self.assertRaises(ValueError):
                actions.validate_command(item)

    def test_action_queue_orders_jobs_and_survives_invalid_files_without_leaking_text(self):
        token = "12345678-1234-1234-1234-123456789abc"
        prefix = "command-" + token + "-"
        (self.directory / (prefix + "0000000000000001.json")).mkdir()
        second = self.directory / (prefix + "0000000000000002.json")
        tenth = self.directory / (prefix + "0000000000000010.json")
        second.write_text(json.dumps({"action": "input", "text": "second", "backspaces": 0}))
        tenth.write_text(json.dumps({"action": "input", "text": "tenth", "backspaces": 0}))
        bad = self.directory / (prefix + "0000000000000011.json")
        bad.write_text("invalid private text")
        stale = self.directory / "command-87654321-4321-4321-4321-cba987654321-0000000000000003.json"
        stale.write_text("another session")
        recorded = []
        with patch.object(actions, "execute", side_effect=lambda job: recorded.append(job["text"])):
            actions.consume(self.directory, token)
        self.assertEqual(recorded, ["second", "tenth"])
        self.assertFalse(second.exists() or tenth.exists() or bad.exists())
        self.assertTrue(stale.exists())
        error = (self.directory / ("error-" + token + ".log")).read_text()
        self.assertNotIn("private text", error)
        self.assertLessEqual(len(error.encode()), 2048)

    def test_status_reads_only_the_bounded_session_language_and_current_modifier(self):
        token = "12345678-1234-1234-1234-123456789abc"
        self.assertTrue(hasattr(ui, "status_text"), "The status line language indicator is missing")
        language = self.directory / ("language-" + token)
        language.write_text("한\n")
        ui.set_modifier("META", self.directory)
        text = ui.status_text(self.directory, token, self.directory, "12:34")
        self.assertIn("한", text)
        self.assertIn("Meta+Space", text)
        language.write_text("EN\nunsafe\n" + "x" * 32)
        text = ui.status_text(self.directory, token, self.directory, "12:34")
        self.assertIn("EN", text)
        self.assertNotIn("unsafe", text)
        language.unlink()
        language.symlink_to(self.directory / "outside-language")
        self.assertIn("EN", ui.status_text(self.directory, token, self.directory, "12:34"))

    def test_both_watchers_use_the_busybox_applet_when_no_standalone_inotifyd_exists(self):
        token = "12345678-1234-1234-1234-123456789abc"
        class Process:
            def __init__(self):
                self.stdout, self.stopped = io.StringIO(""), False
            def poll(self):
                return 0 if self.stopped else None
            def terminate(self):
                self.stopped = True
            def wait(self, timeout=None):
                return 0

        for helper in (actions, clip):
            with self.subTest(worker=helper.__name__):
                calls, processes = [], []
                def popen(argv, **kwargs):
                    if argv[0] == "inotifyd":
                        raise FileNotFoundError("Pinned rootfs has no standalone inotifyd")
                    calls.append(argv)
                    process = Process()
                    processes.append(process)
                    return process
                with patch.object(helper.subprocess, "Popen", side_effect=popen), patch.object(helper.signal, "signal"), \
                     patch.dict(os.environ, {"LOOPY_SESSION": token}), patch.object(actions.ui, "IPC", self.directory), \
                     patch.object(clip, "paths", return_value=(self.directory / "android", self.directory / "guest")):
                    helper.watch()
                self.assertIn(["/bin/busybox", "inotifyd", "-", str(self.directory) + ":yw"], calls)
                self.assertTrue(all(process.stopped for process in processes))


if __name__ == "__main__":
    unittest.main()
