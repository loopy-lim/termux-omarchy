"""The signature helper must remain authentic and verification must still reject tampering."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'termux/vscode_signature_compat.py'
SOURCE = ROOT / 'build/diagnostics/termux-omarchy-vscode-signature-helper-host-20261009-01/vsce-sign-linux-arm64'

class SignatureCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), 'helper-only compatibility builder missing')
        spec = importlib.util.spec_from_file_location('vscode_signature_compat', MODULE)
        self.m = importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.original = SOURCE.read_bytes()

    def test_original_helper_is_preserved_and_output_creation_is_exclusive(self):
        with tempfile.TemporaryDirectory() as name:
            source = Path(name)/'native';source.write_bytes(self.original);source.chmod(0o755)
            before=(source.stat().st_ino,source.stat().st_mtime_ns);out=Path(name)/'candidate'
            row=self.m.build(source,out)
            self.assertEqual(source.read_bytes(),self.original)
            self.assertEqual((source.stat().st_ino,source.stat().st_mtime_ns),before)
            self.assertEqual((out/'vsce-sign').read_bytes(),self.m.wrapper_bytes())
            self.assertEqual((out/self.m.BACKUP_NAME).read_bytes(),self.original)
            self.assertEqual(row['signatureVerificationBypassed'],False)
            self.assertEqual(row['originalSHA256'],hashlib.sha256(self.original).hexdigest())
            with self.assertRaises(FileExistsError):self.m.build(source,out)

    def test_changed_helper_is_refused_before_creating_outputs(self):
        with tempfile.TemporaryDirectory() as name:
            for i,data in enumerate((self.original+b' ',self.original[:-1]+bytes([self.original[-1]^1]))):
                source=Path(name)/f'native{i}';source.write_bytes(data);out=Path(name)/f'out{i}'
                with self.assertRaises(ValueError):self.m.build(source,out)
                self.assertFalse(out.exists())

    def test_source_symlink_is_refused_without_output(self):
        with tempfile.TemporaryDirectory() as name:
            source=Path(name)/'native';source.symlink_to(SOURCE);out=Path(name)/'candidate'
            with self.assertRaises(ValueError):self.m.build(source,out)
            self.assertFalse(out.exists())

    def test_wrapper_is_a_valid_shell_program_with_fixed_child_scope(self):
        content=self.m.wrapper_bytes()
        result=subprocess.run(['/bin/sh','-n'],input=content,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(content.count(b'DOTNET_GCHeapHardLimit'),1)
        self.assertIn(b'exec '+self.m.ORIGINAL_GUEST_PATH.encode()+b' "$@"',content)
        self.assertNotIn(b'extensions.verifySignature',content)
        self.assertNotIn(b'--disable',content)

if __name__=='__main__':unittest.main()
