"""The Android scroll preference remains the only inversion point after upgrades."""

import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


PRODUCT = Path(__file__).resolve().parents[1]
LIB = PRODUCT / "guest/desktop/usr/local/lib/loopy"
sys.path.insert(0, str(LIB))
DEFAULTS = PRODUCT / "guest/desktop/usr/share/loopy/defaults"
spec = importlib.util.spec_from_file_location("desktop_ui_scroll_migration",
    PRODUCT / "guest/desktop/usr/local/lib/loopy/desktop_ui.py")
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class ScrollMigrationTests(unittest.TestCase):
    def test_only_shipped_sway_configs_gain_single_layer_scroll_policy(self):
        current = (DEFAULTS / "sway/config").read_bytes()
        self.assertTrue(b"input type:pointer natural_scroll disabled\n" in current)
        self.assertFalse(b"status_command " in current)
        self.assertTrue(b"tray_output none\n" in current)
        self.assertEqual(current, (PRODUCT / "guest/desktop/root/.config/sway/config").read_bytes())
        historical = (("base", "90d2d26872193dcd1641f65a30af9bbc3f4e8dcd5f12d0260a1387bfda5e5510"),
                      ("extension", "548eea9b3900d6055b455518de53dbc0d639ee3bfa1ae65423df400a1550fc40"),
                      ("scroll", "413de6e20adc34fca795b0da7a237b1b99d5b464f6434bc6ac5c377dd572c651"))
        with tempfile.TemporaryDirectory() as temporary:
            for name, expected_sha in historical:
                old = (PRODUCT / "tests/fixtures" / ("sway-2026-10-05-" + name + ".conf")).read_bytes()
                self.assertEqual(hashlib.sha256(old).hexdigest(), expected_sha)
                home = Path(temporary).resolve() / name
                config = home / ".config/sway/config"
                config.parent.mkdir(parents=True)
                config.write_bytes(old)
                ui.initialize_defaults(home, DEFAULTS)
                self.assertEqual(config.read_bytes(), current, name)
                custom = current + b"# user keeps custom bindings\n"
                config.write_bytes(custom)
                ui.initialize_defaults(home, DEFAULTS)
                self.assertEqual(config.read_bytes(), custom, name)


if __name__ == "__main__":
    unittest.main()
