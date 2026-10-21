"""Settings synchronization must not reload an already configured compositor."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'guest/desktop/usr/local/lib/loopy/desktop_actions.py'
spec = importlib.util.spec_from_file_location('desktop_settings_actions', HELPER)
actions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actions)
ui = actions.ui
THEMES = ROOT / 'guest/desktop/usr/share/loopy/themes.json'


class DesktopSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.palette = json.loads(THEMES.read_text())
        ui.apply_theme('slate', self.home, self.palette)
        self.addCleanup(patch.stopall)
        patch.object(ui, 'HOME', self.home).start()
        patch.object(ui, 'THEMES', THEMES).start()
        self.sway = patch.object(ui, 'sway').start()

    def test_matching_initialized_settings_do_not_reload_sway(self):
        actions.execute({'action': 'modifier', 'name': 'CTRL_ALT'})
        actions.execute({'action': 'theme', 'name': 'slate'})
        self.sway.assert_not_called()

    def test_changed_modifier_and_theme_apply_then_reload(self):
        actions.execute({'action': 'modifier', 'name': 'META'})
        self.assertEqual((self.home / '.config/loopy/modifier').read_text(), 'set $mod Mod4\n')
        self.sway.assert_called_once_with('reload')
        self.sway.reset_mock()
        actions.execute({'action': 'theme', 'name': 'forest'})
        self.assertEqual(ui.read_preferences(self.home)['theme'], 'forest')
        self.sway.assert_called_once_with('reload')

    def test_missing_generated_settings_are_repaired(self):
        (self.home / '.config/loopy/modifier').unlink()
        actions.execute({'action': 'modifier', 'name': 'CTRL_ALT'})
        self.sway.assert_called_once_with('reload')
        self.sway.reset_mock()
        (self.home / '.config/loopy/gtk.css').unlink()
        actions.execute({'action': 'theme', 'name': 'slate'})
        self.assertTrue((self.home / '.config/loopy/gtk.css').is_file())
        self.sway.assert_called_once_with('reload')
