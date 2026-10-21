"""The private AHB driver may affect only the native compositor."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'termux'))
from omarchy_commands import native_graphics, environment

class NativeGraphicsTests(unittest.TestCase):
    def test_missing_selection_preserves_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            env={'VK_ICD_FILENAMES':'original'}
            native_graphics(Path(tmp),env)
            self.assertEqual(env,{'VK_ICD_FILENAMES':'original'})

    def test_verified_selection_and_tampered_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=root/'graphics-ahb';d.mkdir(mode=0o700)
            (d/'libvulkan_freedreno.so').write_bytes(b'test binary')
            (d/'icd.json').write_text(json.dumps({'ICD':{'library_path':str(d/'libvulkan_freedreno.so')}}))
            files=('libvulkan_freedreno.so','icd.json')
            for n in files:(d/n).chmod(0o600)
            (d/'selection.json').write_text(json.dumps({'schema':1,'sha256':{n:hashlib.sha256((d/n).read_bytes()).hexdigest() for n in files}}))
            env={};native_graphics(root,env)
            self.assertEqual(env['LOOPY_X11_AHB'],'1')
            self.assertEqual(env['VK_ICD_FILENAMES'],str(d/'icd.json'))
            (d/'libvulkan_freedreno.so').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'integrity'):native_graphics(root,{})

    def test_preload_does_not_leak_into_base_environment(self):
        from unittest.mock import patch
        with patch.dict(os.environ,{'LD_PRELOAD':'native-only','LOOPY_X11_AHB':'1'}):
            env=environment(Path('/home'),Path('/prefix'),Path('/host'))
        self.assertNotIn('LD_PRELOAD',env)
        self.assertNotIn('LOOPY_X11_AHB',env)

if __name__=='__main__':unittest.main()
