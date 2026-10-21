"""Remote actions must reach genuine clients in the existing Omarchy session."""
from pathlib import Path
import tempfile
import unittest

from tests.test_omarchy_actions import OwnedSocket, module


class OmarchyRemoteTests(unittest.TestCase):
    def test_native_remote_actions_dispatch_connection_tools(self):
        ipc = module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='loopy-remote-ipc-', dir='/tmp') as directory:
            path = Path(directory) / 'ctl'
            peer = OwnedSocket(path, [[b'ok']] * 2)
            try:
                client = ipc.Hyprland(path)
                client.execute({'action': 'launch', 'app': 'remote'})
                client.execute({'action': 'launch', 'app': 'remote-desktop'})
            finally:
                peer.close()
            self.assertEqual(peer.requests, [
                'dispatch hl.dsp.exec_cmd("/usr/bin/python /usr/share/loopy/omarchy-bridge/remote_bridge.py ssh")',
                'dispatch hl.dsp.exec_cmd("/usr/bin/python /usr/share/loopy/omarchy-bridge/remote_bridge.py desktop")',
            ])


if __name__ == '__main__':
    unittest.main()
