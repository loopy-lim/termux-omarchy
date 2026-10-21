"""Session-scoped app and web actions exercise the actual atomic request transport."""
import base64
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('platform_action', ROOT/'android/assets/omarchy-bridge/platform_action.py')
platform=importlib.util.module_from_spec(spec)
exec(compile(Path(spec.origin).read_text(), spec.origin, "exec"), platform.__dict__)

class AndroidPlatformTests(unittest.TestCase):
    def test_catalog_launch_uses_exact_component_and_atomic_current_session_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);component='notion.id/notion.id.MainActivity'
            (directory/'apps-current.tsv').write_text(component+'\tNotion\n')
            encoded=base64.urlsafe_b64encode(component.encode()).decode().rstrip('=')
            platform.request(tmp,'current','launch',encoded)
            self.assertEqual((directory/'request-current').read_text(),'launch\t'+component+'\n')
            with self.assertRaises(ValueError): platform.request(tmp,'other','launch',encoded)
            with self.assertRaises(ValueError): platform.request(tmp,'current','launch','Zm9yZWlnbi9BY3Rpdml0eQ')
    def test_web_url_is_not_shell_interpreted_or_redirected_to_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            url='https://www.notion.so/?view=home&from=loopy'
            platform.request(tmp,'current','web',url)
            self.assertEqual((Path(tmp)/'request-current').read_text(),'web\t'+url+'\n')
            for bad in ['file:///private','intent://x','https://user:password@notion.so/','https://','https://example.com/\nlaunch\tx/y']:
                with self.subTest(bad=bad), self.assertRaises(ValueError): platform.request(tmp,'current','web',bad)
    def test_symlink_catalog_and_invalid_tokens_never_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'foreign').write_text('a/b\tExample\n');(root/'apps-current.tsv').symlink_to(root/'foreign')
            with self.assertRaises(OSError): platform.request(tmp,'current','launch','YS9i')
            with self.assertRaises(ValueError): platform.request(tmp,'../wrong','wifi')
            self.assertFalse((root/'request-current').exists())
