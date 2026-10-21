"""The installed shared-UID APK must keep the activity and key service together."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

try:
    from tools import termux_x11_process as process
except ImportError:
    process = None

FIXTURE = Path(__file__).parent / 'fixtures/termux-x11-process/AndroidManifest.xml.bin'
MAIN = 'com.termux.x11.MainActivity'
KEYS = 'com.termux.x11.utils.KeyInterceptor'


class TermuxX11ProcessTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(process, 'The shared-UID input service process repair is missing')
        self.manifest = FIXTURE.read_bytes()

    def test_repair_joins_key_service_to_actual_activity_without_changing_other_components(self):
        before = process.component_processes(self.manifest)
        self.assertEqual(before[MAIN], 'com.termux')
        self.assertEqual(before[KEYS], 'com.termux.x11')
        repaired = process.patch(self.manifest)
        after = process.component_processes(repaired)
        self.assertEqual(after, {**before, KEYS: 'com.termux'})
        self.assertEqual(len(repaired), len(self.manifest) + 20)
        self.assertEqual(process.patch(repaired), repaired)

    def test_unrelated_shared_uid_and_broken_binary_xml_are_refused(self):
        unrelated = self.manifest.replace(b'com.termux', b'com.ternux').replace(
            'com.termux'.encode('utf-16le'), 'com.ternux'.encode('utf-16le'))
        self.assertNotEqual(unrelated, self.manifest)
        for data in (self.manifest[:-1], self.manifest + b'x', b'not XML', unrelated):
            with self.subTest(data_length=len(data)), self.assertRaises(ValueError):
                process.patch(data)

    def test_apk_rewrite_preserves_every_payload_and_removes_only_original_signatures(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'original.apk'
            candidate = Path(directory) / 'candidate.apk'
            payload = {'classes.dex': b'original executable', 'lib/arm64-v8a/libXlorie.so': b'original graphics',
                       'assets/license.txt': b'original license', 'META-INF/services/example': b'original metadata'}
            with zipfile.ZipFile(original, 'w') as archive:
                archive.writestr('AndroidManifest.xml', self.manifest)
                for name, data in payload.items(): archive.writestr(name, data)
                archive.writestr('META-INF/CERT.RSA', b'old signature')
                archive.writestr('META-INF/CERT.SF', b'old signature file')
                archive.writestr('META-INF/MANIFEST.MF', b'old digest list')
            sha = hashlib.sha256(original.read_bytes()).hexdigest()
            process.rewrite_apk(original, candidate, expected_sha256=sha)
            with zipfile.ZipFile(candidate) as archive:
                self.assertEqual(set(archive.namelist()), {*payload, 'AndroidManifest.xml'})
                for name, data in payload.items(): self.assertEqual(archive.read(name), data)
                self.assertEqual(process.component_processes(archive.read('AndroidManifest.xml'))[KEYS], 'com.termux')
            original_bytes = original.read_bytes()
            with self.assertRaises((ValueError, FileExistsError)):
                process.rewrite_apk(original, candidate, expected_sha256=sha)
            self.assertEqual(original.read_bytes(), original_bytes)

    def test_bad_apk_identity_is_refused_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'original.apk'; source.write_bytes(b'untrusted bytes')
            target = Path(directory) / 'candidate.apk'
            with self.assertRaises(ValueError):
                process.rewrite_apk(source, target, expected_sha256='0' * 64)
            self.assertFalse(target.exists())


if __name__ == '__main__': unittest.main()
