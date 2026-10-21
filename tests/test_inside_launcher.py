"""Internal Android launch actions retain the actual Wayland client argv boundary."""
import base64
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'android/assets/omarchy-bridge/hyprland_actions.py'
spec = importlib.util.spec_from_file_location('inside_launch_actions', path)
actions = importlib.util.module_from_spec(spec)
exec(compile(path.read_text(), str(path), 'exec'), actions.__dict__)


class InsideLauncherTests(unittest.TestCase):
    def test_component_becomes_only_the_fixed_inside_client_argument(self):
        component = 'dev.fixture.app/dev.fixture.app.MainActivity'
        encoded = base64.urlsafe_b64encode(component.encode('ascii')).decode().rstrip('=')
        command = '/usr/bin/python -B /usr/share/loopy/omarchy-bridge/inside_window.py --component ' + encoded
        self.assertEqual(actions.action({'action': 'android-inside', 'component': component}),
                         'hl.dsp.exec_cmd(' + json.dumps(command) + ')')

    def test_untyped_extra_and_injected_components_never_launch(self):
        for value in ['x/y;reboot', 'x/$(reboot)', 'x/`reboot`', '../x/y', 'x/y\n', 1, 'x/' + 'y' * 512]:
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                actions.action({'action': 'android-inside', 'component': value})
        with self.assertRaises(ValueError):
            actions.action({'action': 'android-inside', 'component': 'x/y', 'uid': 12345})
