"""Catch the real KeyBridge synthetic-language-key loss in the packaged native table."""
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from tools import termux_x11_process as process

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/deliverables/LoopyOmarchy-TermuxX11-process-fix-20261009-01.apk'
LIBRARY = 'lib/arm64-v8a/libXlorie.so'
OFFSET = 411744


class TermuxX11LanguageTests(unittest.TestCase):
    def repair(self, data, **kwargs):
        method = getattr(process, 'patch_language_switch', None)
        self.assertTrue(callable(method), 'Synthetic language-switch native repair is missing')
        return method(data, **kwargs)

    def test_packaged_language_key_produces_linux_hangul_instead_of_reserved_x_code(self):
        with tempfile.TemporaryDirectory() as directory:
            supplied = os.environ.get('LOOPY_LANGUAGE_TEST_APK')
            apk = Path(supplied) if supplied else Path(directory) / 'language.apk'
            if not supplied:
                process.rewrite_apk(BASE, apk, language_switch=True)
            with zipfile.ZipFile(apk) as archive:
                native = archive.read(LIBRARY)
            linux_code, = struct.unpack_from('<I', native, OFFSET + 204 * 4)
            self.assertEqual(linux_code + 8, 130, 'KeyBridge language_switch must produce XKB Hangul')

    def test_real_native_repair_changes_only_the_synthetic_language_mapping(self):
        with zipfile.ZipFile(BASE) as archive:
            before = archive.read(LIBRARY)
        after = self.repair(before)
        self.assertEqual(struct.unpack_from('<I', after, OFFSET + 204 * 4)[0], 122)
        changed = [index for index, values in enumerate(zip(before, after)) if values[0] != values[1]]
        self.assertEqual(changed, [OFFSET + 204 * 4])
        self.assertEqual(len(before), len(after))

    def test_wrong_native_identity_and_already_modified_libraries_are_refused(self):
        with zipfile.ZipFile(BASE) as archive:
            native = archive.read(LIBRARY)
        self.assertTrue(callable(getattr(process, 'patch_language_switch', None)))
        repaired = self.repair(native)
        for untrusted in (native[:-1], b'not an ELF', repaired):
            with self.subTest(size=len(untrusted)), self.assertRaises(ValueError):
                self.repair(untrusted)

    def test_apk_language_repair_preserves_manifest_dex_graphics_and_all_other_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'unsigned.apk'
            process.rewrite_apk(BASE, target, expected_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest(),
                                language_switch=True)
            with zipfile.ZipFile(BASE) as original, zipfile.ZipFile(target) as candidate:
                kept = set(candidate.namelist())
                self.assertIn('AndroidManifest.xml', kept)
                self.assertEqual(process.component_processes(candidate.read('AndroidManifest.xml')),
                                 process.component_processes(original.read('AndroidManifest.xml')))
                changed = [name for name in kept if original.read(name) != candidate.read(name)]
                self.assertEqual(changed, [LIBRARY])
                self.assertEqual(struct.unpack_from('<I', candidate.read(LIBRARY), OFFSET + 204 * 4)[0], 122)
            with self.assertRaises(FileExistsError):
                process.rewrite_apk(BASE, target, expected_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest(),
                                    language_switch=True)

    def test_unknown_apk_is_rejected_without_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'unknown.apk'; source.write_bytes(b'unknown package')
            target = Path(directory) / 'candidate.apk'
            with self.assertRaises(ValueError):
                process.rewrite_apk(source, target, language_switch=True)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
