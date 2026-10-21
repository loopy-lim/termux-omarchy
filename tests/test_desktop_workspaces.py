"""Numbered desktop workspaces and focus-pinned moves."""
import unittest
from unittest.mock import patch
from tests.test_desktop_guest import actions


class DesktopWorkspaceTests(unittest.TestCase):
    def test_ten_numbered_workspaces_and_moves_pin_the_focused_container(self):
        tree = {"id": 27, "focused": True, "app_id": "owned-fixture"}
        for number in range(1, 11):
            with patch.object(actions.ui, "sway", return_value=tree) as sway:
                actions.execute({"action": "workspace", "target": str(number)})
                sway.assert_called_once_with("workspace number " + str(number))
            with patch.object(actions.ui, "sway", return_value=tree) as sway:
                actions.execute({"action": "move-workspace", "target": str(number)})
                self.assertEqual(sway.call_args_list[-1].args, ("[con_id=27] move container to workspace number " + str(number),))
        for target in ("0", "11", "next", "1; exec unsafe", 1, []):
            with self.assertRaises(ValueError):
                actions.validate_command({"action": "move-workspace", "target": target})
        with patch.object(actions.ui, "sway", return_value={}) as sway:
            with self.assertRaises(ValueError): actions.execute({"action": "move-workspace", "target": "10"})
            sway.assert_called_once_with("get_tree", query=True)
