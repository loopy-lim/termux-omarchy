import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'termux'))
import omarchy_graphics_install as installer

class GraphicsInstallTests(unittest.TestCase):
    def test_running_session_has_no_side_effects_then_stopped_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();root.chmod(0o700)
            driver=root/'driver';driver.write_bytes(b'verified fixture');driver.chmod(0o600)
            (root/'runtime-control.lock').touch(mode=0o600)
            state=root/'runtime-state.json';state.write_text(json.dumps({'phase':'ready'}));state.chmod(0o600)
            digest=hashlib.sha256(driver.read_bytes()).hexdigest()
            with patch.object(installer,'DRIVER_SHA',digest),patch.object(installer,'RUNTIME_SHA',{}):
                with self.assertRaisesRegex(ValueError,'stop-desktop'):installer.install(root,driver)
                self.assertFalse((root/'graphics-ahb').exists())
                self.assertFalse((root/'graphics-ahb-staging').exists())
                state.write_text(json.dumps({'phase':'stopped','terminationConfirmed':True}))
                self.assertEqual(installer.install(root,driver)['status'],'INSTALLED')
                self.assertEqual(installer.install(root,driver)['status'],'ALREADY_INSTALLED')
                (root/'graphics-ahb/libvulkan_freedreno.so').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'existing-driver'):installer.install(root,driver)

if __name__=='__main__':unittest.main()
