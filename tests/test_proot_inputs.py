"""Do not package a stale or untraceable locally patched runtime."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from proot_inputs import CompatError, select_proot


class ProotInputTests(unittest.TestCase):
    def fixture(self, root):
        inputs = {"native/proot-compat/0001.patch": b"patch", "tools/build_proot_compat.py": b"builder",
                  "third_party/runtime.lock.json": b"lock"}
        for relative, data in inputs.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        binary = root / "build/proot-compat/arm64-v8a/libproot.so"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"derived proot")
        loader = binary.with_name("libproot_loader.so")
        loader.write_bytes(b"derived loader")
        receipt = {"schema_version": 1,
                   "inputs": {name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()},
                   "artifact": {"path": str(binary.relative_to(root)), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                                "bytes": binary.stat().st_size},
                   "loader_artifact": {"path": str(loader.relative_to(root)), "sha256": hashlib.sha256(loader.read_bytes()).hexdigest(),
                                       "bytes": loader.stat().st_size}}
        file = root / "build/proot-compat/build-receipt.json"
        file.write_text(json.dumps(receipt))
        return binary, file

    def test_original_runtime_used_only_when_no_patch_is_owned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            original = root / "original.so"
            self.assertEqual(select_proot(root, original), (original, []))

    def test_valid_derived_runtime_includes_receipt_and_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            binary, receipt = self.fixture(root)
            selected, inputs = select_proot(root, root / "original.so")
            self.assertEqual(selected, binary)
            self.assertIn(receipt, inputs)
            self.assertIn(root / "native/proot-compat/0001.patch", inputs)

    def test_missing_receipt_never_silently_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _, receipt = self.fixture(root)
            receipt.unlink()
            with self.assertRaises(CompatError): select_proot(root, root / "original.so")

    def test_changed_patch_or_binary_rejected(self):
        for changed in ("native/proot-compat/0001.patch", "build/proot-compat/arm64-v8a/libproot.so", "build/proot-compat/arm64-v8a/libproot_loader.so"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                self.fixture(root)
                (root / changed).write_bytes(b"changed")
                with self.assertRaises(CompatError): select_proot(root, root / "original.so")

    def test_symlink_or_outside_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            binary, receipt = self.fixture(root)
            binary.unlink()
            binary.symlink_to(receipt)
            with self.assertRaises(CompatError): select_proot(root, root / "original.so")
            data = json.loads(receipt.read_text())
            data["artifact"]["path"] = "../outside.so"
            receipt.write_text(json.dumps(data))
            with self.assertRaises(CompatError): select_proot(root, root / "original.so")


if __name__ == "__main__": unittest.main()
