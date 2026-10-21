import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from tools.build_omarchy_graphics import extract_source, apply_guarded_patch, prepare


def archive(path, members):
    with tarfile.open(path, "w:gz") as writer:
        for name, content, kind in members:
            item = tarfile.TarInfo(name)
            item.type = kind
            item.size = len(content)
            writer.addfile(item, io.BytesIO(content))


class GraphicsPreparationTests(unittest.TestCase):
    def test_unsafe_archive_is_rejected_before_destination_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, kind in [("aquamarine-pin/../escape", tarfile.REGTYPE), ("aquamarine-pin/file", tarfile.SYMTYPE)]:
                archive(root / "source.gz", [(name, b"x", kind)])
                with self.assertRaises(ValueError):
                    extract_source(root / "source.gz", root / "candidate", "pin")
                self.assertFalse((root / "candidate").exists())

    def test_duplicate_archive_file_cannot_shadow_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive(root / "source.gz", [("aquamarine-pin/file", b"a", tarfile.REGTYPE), ("aquamarine-pin/file", b"b", tarfile.REGTYPE)])
            with self.assertRaises(ValueError):
                extract_source(root / "source.gz", root / "candidate", "pin")

    def test_hash_mismatch_never_applies_patch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "owned.cpp").write_text("private local work\n")
            patch = root / "fix.patch"
            patch.write_text("--- a/owned.cpp\n+++ b/owned.cpp\n@@ -1 +1 @@\n-old\n+new\n")
            digest = lambda value: hashlib.sha256(value).hexdigest()
            metadata = {"patch_sha256": digest(patch.read_bytes()), "files": {"owned.cpp": {
                "preimage_sha256": digest(b"old\n"), "patched_sha256": digest(b"new\n")}}}
            with self.assertRaises(ValueError):
                apply_guarded_patch(root, patch, metadata)
            self.assertEqual((root / "owned.cpp").read_text(), "private local work\n")

    def test_pinned_real_source_and_all_five_patches_prepare_identical_candidate(self):
        root = Path(__file__).resolve().parents[1]
        source = json.loads((root / "third_party/omarchy.lock.json").read_text())["graphics_sources"][0]
        if not (root / "build/omarchy-sources" / ("aquamarine-" + source["commit"] + ".tar.gz")).is_file():
            self.skipTest("requires downloaded pinned source archive")
        with tempfile.TemporaryDirectory() as folder:
            candidate = Path(folder) / "candidate"
            receipt = prepare(root / "third_party/omarchy.lock.json", root / "build/omarchy-sources", candidate)
            self.assertEqual(receipt["patches_applied"], 5)
            self.assertFalse(receipt["omarchy_support_complete"])
            expected = root / "build/omarchy-sources/aquamarine-cursor"
            for name in ("src/backend/Wayland.cpp", "include/aquamarine/backend/Wayland.hpp",
                         "src/allocator/Swapchain.cpp", "src/allocator/SHM.cpp", "CMakeLists.txt"):
                self.assertEqual((candidate / name).read_bytes(), (expected / name).read_bytes())
            with self.assertRaises(ValueError):
                prepare(root / "third_party/omarchy.lock.json", root / "build/omarchy-sources", candidate)


if __name__ == "__main__":
    unittest.main()
