import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('display', Path(__file__).parents[1] / 'termux/omarchy_display.py')
display = importlib.util.module_from_spec(spec)
spec.loader.exec_module(display)


class DisplayTests(unittest.TestCase):
    def test_profile_roundtrip_keeps_other_settings(self):
        source = '-- user settings\nlocal omarchy_monitor_scale = 1.25\nhl.env("GDK_SCALE", "1")\n'
        flags = '--use-angle=vulkan\n--load-extension=/custom\n'
        high = display.transform(source, flags, 2.5)
        self.assertEqual(display.transform(*high, 2.5), high)
        low = display.transform(*high, 1.25)
        self.assertIn('local omarchy_monitor_scale = 1.25\n', low[0])
        self.assertIn('-- user settings', low[0])
        self.assertIn(flags, low[1])
        self.assertEqual(low[1].count('--force-device-scale-factor='), 1)

    def test_ambiguous_custom_config_is_not_rewritten(self):
        for source in ('', 'local omarchy_monitor_scale = 1\nlocal omarchy_monitor_scale = 2\n'):
            with self.assertRaises(ValueError):
                display.transform(source, '', 2.5)
