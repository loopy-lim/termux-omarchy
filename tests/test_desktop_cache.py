"""Run the shipped cache initializer with bounded host stubs and real cache files."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "guest/desktop/usr/local/bin/loopy-cache"


class DesktopCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="loopy-cache-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "calls.txt"
        self.mime = self.root / "usr/share/mime"
        for name in ("usr/bin", "usr/share/glib-2.0/schemas", "usr/share/icons/Adwaita", "usr/share/mime/packages"):
            (self.root / name).mkdir(parents=True)
        (self.mime / "packages/freedesktop.org.xml").write_text("<mime-info/>")
        self.command("glib-compile-schemas", ":")
        self.command("gdk-pixbuf-query-loaders", "printf 'fixture loader cache\\n'")
        self.command("gtk-update-icon-cache", 'touch "$3/icon-theme.cache"')
        self.command("update-mime-database", 'touch "$1/mime.cache"')
        self.env = dict(os.environ, LOOPY_CACHE_ROOT=str(self.root), LOOPY_CACHE_LOG=str(self.log))

    def command(self, name, body):
        script = self.root / "usr/bin" / name
        script.write_text('#!/bin/sh\nset -eu\nprintf "%s\\t%s\\n" "' + name + '" "$*" >> "$LOOPY_CACHE_LOG"\n' + body + '\n')
        script.chmod(0o755)

    def run_cache(self):
        return subprocess.run(["/bin/sh", str(SCRIPT)], env=self.env, capture_output=True, text=True, timeout=5)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_missing_mime_cache_is_generated_from_shipped_xml(self):
        result = self.run_cache()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("update-mime-database\t" + str(self.mime), self.calls())
        self.assertTrue((self.mime / "mime.cache").is_file())
        self.assertTrue((self.root / "usr/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache").is_file())

    def test_existing_mime_cache_is_retained_on_next_start(self):
        (self.mime / "mime.cache").write_bytes(b"existing cache")
        result = self.run_cache()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(call.startswith("update-mime-database\t") for call in self.calls()))
        self.assertEqual((self.mime / "mime.cache").read_bytes(), b"existing cache")

    def test_failed_mime_generation_stops_cache_initialization(self):
        self.command("update-mime-database", "exit 42")
        result = self.run_cache()
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertFalse((self.mime / "mime.cache").exists())
        self.assertFalse(any(call.startswith("gdk-pixbuf-query-loaders\t") for call in self.calls()))

    def test_dynamic_wayland_input_module_cache_is_generated(self):
        self.command("gtk-query-immodules-3.0", "printf '\"/usr/lib/gtk-3.0/3.0.0/immodules/im-wayland.so\"\\n\"wayland\" \"Wayland\" \"gtk30\" \"/usr/share/locale\" \"*\"\\n'")
        result = self.run_cache()
        self.assertEqual(result.returncode, 0, result.stderr)
        cache = self.root / "usr/lib/gtk-3.0/3.0.0/immodules.cache"
        self.assertTrue(cache.is_file(), "GTK cannot discover shipped Wayland IM without its registry cache")
        self.assertIn('"wayland"', cache.read_text())
        self.assertFalse(cache.with_suffix(".cache.new").exists())

    def test_failed_input_module_query_preserves_previous_cache(self):
        cache = self.root / "usr/lib/gtk-3.0/3.0.0/immodules.cache"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"existing registry")
        self.command("gtk-query-immodules-3.0", "printf 'partial registry'; exit 42")
        result = self.run_cache()
        self.assertEqual(result.returncode, 42, "a failed query must stop startup before GTK silently uses simple IM")
        self.assertEqual(cache.read_bytes(), b"existing registry")


if __name__ == "__main__":
    unittest.main()
