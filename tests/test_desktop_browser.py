"""The Linux browser route and its process-local software rendering policy."""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "guest/desktop/usr/local/bin/loopy-browser"
BACKEND = "/usr/bin/python3"
BROWSER_SCRIPT = "/usr/local/lib/loopy/browser.py"
UI_PATH = ROOT / "guest/desktop/usr/local/lib/loopy/desktop_ui.py"
spec = importlib.util.spec_from_file_location("browser_desktop_ui", UI_PATH)
ui = importlib.util.module_from_spec(spec)
old_bytecode = sys.dont_write_bytecode
try:
    sys.dont_write_bytecode = True
    spec.loader.exec_module(ui)
finally:
    sys.dont_write_bytecode = old_bytecode


class DesktopBrowserTests(unittest.TestCase):
    def test_linux_browser_menu_launches_the_browser_wrapper_as_argv(self):
        def choose_browser(entries, _title):
            return next(entry for entry in entries if entry.get("app") == "browser")

        with patch.dict(os.environ, {"LOOPY_SESSION": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}), \
                patch.object(ui, "android_entries", return_value=[]), \
                patch.object(ui, "choose", side_effect=choose_browser), \
                patch.object(ui.subprocess, "Popen") as launched:
            ui.menu()
        launched.assert_called_once_with(["/usr/local/bin/loopy-browser"])

    def test_wrapper_exec_keeps_home_and_literal_arguments_and_scopes_cpu_policy(self):
        self.assertTrue(WRAPPER.is_file(), "Linux browser wrapper is missing")
        self.assertEqual(WRAPPER.stat().st_mode & 0o777, 0o755)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            home = folder / "persistent-home"
            home.mkdir()
            profile = home / "existing-profile"
            profile.write_text("keep my browser settings", encoding="utf-8")
            output = folder / "browser.json"
            backend = folder / "fixture browser"
            backend.write_text(
                "#!" + sys.executable + "\n"
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "Path(os.environ['BROWSER_TEST_RESULT']).write_text(json.dumps({\n"
                " 'argv': sys.argv[1:], 'pid': os.getpid(),\n"
                " 'environment': {key: os.environ.get(key) for key in\n"
                " ('HOME', 'XDG_DATA_HOME', 'GDK_BACKEND',\n"
                " 'WEBKIT_DISABLE_COMPOSITING_MODE', 'WEBKIT_DISABLE_DMABUF_RENDERER')}\n"
                "}))\n"
                "sys.exit(19)\n", encoding="utf-8")
            backend.chmod(0o755)
            # The host lacks the pinned ARM64 binary. Only the copied fixture
            # script's fixed executable is substituted; production has no override.
            script = WRAPPER.read_text(encoding="utf-8")
            self.assertEqual(script.count(BACKEND), 1)
            fixture = folder / "loopy-browser"
            fixture.write_text(script.replace(BACKEND, shlex.quote(str(backend))), encoding="utf-8")
            fixture.chmod(0o755)
            marker = folder / "must-not-exist"
            arguments = ["https://example.com/a?x=hello world", "$(touch " + str(marker) + ")", "; exit 0"]
            environment = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / "data"),
                               GDK_BACKEND="parent-display", WEBKIT_DISABLE_COMPOSITING_MODE="0",
                               WEBKIT_DISABLE_DMABUF_RENDERER="0", BROWSER_TEST_RESULT=str(output))
            process = subprocess.Popen([str(fixture)] + arguments, env=environment)
            self.assertEqual(process.wait(timeout=5), 19)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["pid"], process.pid)
            self.assertEqual(result["argv"], [BROWSER_SCRIPT] + arguments)
            self.assertEqual(result["environment"], {
                "HOME": str(home), "XDG_DATA_HOME": str(home / "data"),
                "GDK_BACKEND": "wayland", "WEBKIT_DISABLE_COMPOSITING_MODE": "1",
                "WEBKIT_DISABLE_DMABUF_RENDERER": "1"})
            self.assertEqual(environment["GDK_BACKEND"], "parent-display")
            self.assertEqual(profile.read_text(encoding="utf-8"), "keep my browser settings")
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
