"""Mac semantics resolve against the actual focused Wayland application."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'guest/desktop/usr/local/lib/loopy'
sys.path.insert(0, str(LIB))
import desktop_actions as actions

class MacCommandTests(unittest.TestCase):
    def test_terminal_copy_and_paste_keep_ctrl_c_interrupt(self):
        # Exercise the job consumer, with only IPC/process boundary substituted.
        tree = {'nodes': [{'id': 5, 'focused': True, 'app_id': 'loopy-terminal'}]}
        with patch.object(actions.ui, 'sway', return_value=tree), patch.object(actions.mac_commands, 'loopy_chords') as transport:
            actions.execute({'action': 'edit', 'operation': 'copy'})
            self.assertEqual(transport.inject.call_args.args[0], [('c', ('ctrl', 'shift'))])
            actions.execute({'action': 'edit', 'operation': 'paste'})
            self.assertEqual(transport.inject.call_args.args[0], [('v', ('ctrl', 'shift'))])

    def test_generic_app_copy_redo_and_selected_line_navigation(self):
        tree = {'floating_nodes': [{'id': 6, 'focused': True, 'app_id': 'mousepad'}]}
        with patch.object(actions.ui, 'sway', return_value=tree), patch.object(actions.mac_commands, 'loopy_chords') as transport:
            actions.execute({'action': 'edit', 'operation': 'copy'})
            self.assertEqual(transport.inject.call_args.args[0], [('c', ('ctrl',))])
            actions.execute({'action': 'edit', 'operation': 'redo'})
            self.assertEqual(transport.inject.call_args.args[0], [('z', ('ctrl', 'shift'))])
            actions.execute({'action': 'edit', 'operation': 'select_linestart'})
            self.assertEqual(transport.inject.call_args.args[0], [('Home', ('shift',))])

    def test_no_focus_and_unknown_operations_fail_without_typing(self):
        with patch.object(actions.ui, 'sway', return_value={'nodes': []}), patch.object(actions.subprocess, 'run') as run:
            with self.assertRaises(ValueError): actions.execute({'action': 'edit', 'operation': 'copy'})
            with self.assertRaises(ValueError): actions.execute({'action': 'edit', 'operation': 'copy;kill'})
            run.assert_not_called()

if __name__ == '__main__': unittest.main()
