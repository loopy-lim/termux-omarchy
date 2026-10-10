"""Synthetic binary XML fixtures; no shipped APK, native library or device input."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("process_patch", ROOT / "input/patchers/termux_x11_process.py")
process = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(process)


def synthetic_manifest():
    """Only the binary XML subset used by this parser; not Android parser proof."""
    words = [process.ANDROID, "manifest", "application", "activity", "service",
             "package", "sharedUserId", "name", "process", "com.termux.x11",
             "com.termux", process.MAIN, process.KEYS]
    index = {word: n for n, word in enumerate(words)}
    offsets, encoded = [], bytearray()
    for word in words:
        raw = word.encode()
        assert len(word) < 128 and len(raw) < 128
        offsets.append(len(encoded))
        encoded.extend(bytes([len(word), len(raw)]) + raw + b"\0")
    start = 28 + 4 * len(words)
    size = (start + len(encoded) + 3) & ~3
    pool = (struct.pack("<HHIIIIII", 1, 28, size, len(words), 0, 0x100, start, 0)
            + struct.pack("<" + "I" * len(words), *offsets) + encoded)
    pool += b"\0" * (size - len(pool))

    def node(tag, attrs):
        data = bytearray()
        for namespace, key, value in attrs:
            data.extend(struct.pack("<IIIHBBI", process.NONE if namespace is None else index[namespace],
                                    index[key], index[value], 8, 0, 3, index[value]))
        size = 36 + len(data)
        return (struct.pack("<HHIII", 0x102, 16, size, 1, process.NONE)
                + struct.pack("<IIHHHHHH", process.NONE, index[tag], 20, 20, len(attrs), 0, 0, 0) + data)

    rows = [node("manifest", [(None, "package", "com.termux.x11"),
                              (process.ANDROID, "sharedUserId", "com.termux")]),
            node("application", []),
            node("activity", [(process.ANDROID, "name", process.MAIN),
                              (process.ANDROID, "process", "com.termux")]),
            node("service", [(process.ANDROID, "name", process.KEYS)])]
    body = pool + b"".join(rows)
    return struct.pack("<HHI", 3, 8, len(body) + 8) + body


class ProcessPatchTests(unittest.TestCase):
    def test_only_key_service_process_changes_and_patch_is_idempotent(self):
        before = synthetic_manifest()
        processes = process.component_processes(before)
        self.assertEqual(processes[process.KEYS], "com.termux.x11")
        after = process.patch(before)
        self.assertEqual(process.component_processes(after), {**processes, process.KEYS: "com.termux"})
        self.assertEqual(len(after), len(before) + 20)
        self.assertEqual(process.patch(after), after)

    def test_unrelated_or_malformed_manifest_is_refused(self):
        data = synthetic_manifest()
        for fixture in (data[:-1], data + b"x", b"invalid XML", data.replace(b"com.termux", b"com.ternux")):
            with self.subTest(length=len(fixture)), self.assertRaises(ValueError):
                process.patch(fixture)

    def test_unsigned_rewrite_preserves_other_payloads_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "synthetic.zip", Path(directory) / "unsigned.zip"
            payload = {"classes.dex": b"synthetic non-executable fixture", "assets/test.txt": b"keep"}
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("AndroidManifest.xml", synthetic_manifest())
                for name, data in payload.items():
                    archive.writestr(name, data)
                archive.writestr("META-INF/CERT.SF", b"synthetic signature")
            original = source.read_bytes()
            identity = hashlib.sha256(original).hexdigest()
            process.rewrite_apk(source, target, expected_sha256=identity)
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(set(archive.namelist()), {*payload, "AndroidManifest.xml"})
                for name, data in payload.items():
                    self.assertEqual(archive.read(name), data)
            with self.assertRaises(FileExistsError):
                process.rewrite_apk(source, target, expected_sha256=identity)
            self.assertEqual(source.read_bytes(), original)

    def test_unpinned_apk_or_native_bytes_fail_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "untrusted.zip", Path(directory) / "unsigned.zip"
            source.write_bytes(b"not the pinned input")
            with self.assertRaises(ValueError):
                process.rewrite_apk(source, target, expected_sha256="0" * 64)
            self.assertFalse(target.exists())
        with self.assertRaises(ValueError):
            process.patch_language_switch(b"not the pinned ARM64 ELF")


if __name__ == "__main__":
    unittest.main()
