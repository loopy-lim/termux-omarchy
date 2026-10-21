"""A device cadence must reach all three nested compositors consistently."""
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'termux'))
import omarchy_commands as commands

class DisplayRefreshTests(unittest.TestCase):
    def test_default_and_selected_cadence_reach_every_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = types.SimpleNamespace(root=root, prefix=root/'prefix', short=root/'run', host=root/'host', env={})
            for cadence in (None, 120000, 90000):
                if cadence:
                    (root/'display-refresh.json').write_text(json.dumps({'schema':1, 'refreshMhz':cadence}))
                with patch.object(commands, 'selection', return_value=None):
                    rows = commands.commands(runtime, {'display':':1', 'token':'fixture'})
                expected = str(cadence or 60000)
                self.assertEqual(rows[1][1]['WESTON_X11_REFRESH_MHZ'], expected)
                self.assertIn('OMARCHY_REFRESH_MHZ='+expected, rows[2][0])
                self.assertIn('AQ_WAYLAND_REFRESH_MHZ='+expected, rows[2][0])

    def test_session_cadence_does_not_change_when_next_start_config_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = types.SimpleNamespace(root=root, prefix=root/'prefix', short=root/'run', host=root/'host', env={})
            (root/'display-refresh.json').write_text(json.dumps({'schema': 1, 'refreshMhz': 60000}))
            with patch.object(commands, 'selection', return_value=None):
                rows = commands.commands(runtime, {'display': ':1', 'token': 'fixture', 'requestedRefreshMhz': 120000})
            self.assertEqual(rows[1][1]['WESTON_X11_REFRESH_MHZ'], '120000')
            self.assertIn('AQ_WAYLAND_REFRESH_MHZ=120000', rows[2][0])

    def test_browser_present_override_does_not_leak_to_compositor(self):
        with patch.dict('os.environ', {'MESA_VK_WSI_PRESENT_MODE': 'mailbox', 'vblank_mode': '0'}, clear=True):
            env = commands.environment(Path('/home'), Path('/prefix'), Path('/host'))
        self.assertNotIn('MESA_VK_WSI_PRESENT_MODE', env)
        self.assertNotIn('vblank_mode', env)

    def test_invalid_and_shared_config_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); path=root/'display-refresh.json'
            for value in (True, '120000', 0, 240000):
                path.write_text(json.dumps({'schema':1, 'refreshMhz':value}))
                with self.assertRaises(ValueError): commands.display_refresh(root)
            path.write_text(json.dumps({'schema':1, 'refreshMhz':120000}));path.chmod(0o666)
            with self.assertRaises(ValueError): commands.display_refresh(root)

if __name__ == '__main__': unittest.main()
