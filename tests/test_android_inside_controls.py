"""Exercise fixed native-controls requests through the real private atomic transport."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'android/assets/omarchy-bridge/platform_action.py'
spec=importlib.util.spec_from_file_location('inside_platform_test',path)
platform=importlib.util.module_from_spec(spec)
exec(compile(path.read_bytes(),str(path),'exec'),platform.__dict__)

class InsideControlsTests(unittest.TestCase):
    def test_current_catalog_opens_only_fixed_native_panel(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);(directory/'apps-current.tsv').write_text('a/b\tPublic\t10346\n')
            platform.request(tmp,'current','inside-backend')
            self.assertEqual((directory/'request-current').read_bytes(),b'inside-backend\n')
            self.assertEqual((directory/'request-current').stat().st_mode & 0o777,0o600)
            self.assertEqual(sorted(p.name for p in directory.iterdir()),['apps-current.tsv','request-current'])
    def test_backend_panel_requires_current_catalog_and_no_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);(directory/'apps-current.tsv').write_text('')
            for token,argument in [('other',None),('current','request-permission'),('current','shell'),('../wrong',None)]:
                with self.subTest(token=token,argument=argument),self.assertRaises(ValueError):platform.request(tmp,token,'inside-backend',argument)
            self.assertFalse((directory/'request-current').exists())
    def test_backend_catalog_cannot_be_redirected_or_unbounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);(directory/'foreign').write_text('');catalog=directory/'apps-current.tsv';catalog.symlink_to('foreign')
            with self.assertRaises((OSError,ValueError)):platform.request(tmp,'current','inside-backend')
            catalog.unlink();catalog.write_bytes(b'x'*65537)
            with self.assertRaises(ValueError):platform.request(tmp,'current','inside-backend')
            self.assertFalse((directory/'request-current').exists())
