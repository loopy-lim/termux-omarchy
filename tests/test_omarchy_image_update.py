"""Versioned whole-image updates preserve payloads and reject incomplete input."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from tools import omarchy_rootfs

try:
    from tools import omarchy_image_update as update
except ImportError:
    update = None
try:
    from tools import verify_omarchy_image as verifier
except ImportError:
    verifier = None


class OmarchyImageUpdateTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(update, "versioned complete-image update is missing")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        archive = self.root / "one.pkg.tar.gz"
        with tarfile.open(archive, "w:gz") as writer:
            for name, data in ((".PKGINFO", b"pkgname = one\npkgver = 1-1\narch = aarch64\n"),
                               ("usr/bin/Hyprland", b"old compositor"),
                               ("usr/share/omarchy/docs/keyboard.md", b"original manual")):
                info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o755
                writer.addfile(info, io.BytesIO(data))
            info = tarfile.TarInfo("usr/bin/hard"); info.type = tarfile.LNKTYPE
            info.linkname = "usr/bin/Hyprland"; writer.addfile(info)
            info = tarfile.TarInfo("usr/bin/link"); info.type = tarfile.SYMTYPE
            info.linkname = "Hyprland"; writer.addfile(info)
        package = {"name": "one", "version": "1-1", "architecture": "aarch64", "filename": archive.name,
                   "sha256": omarchy_rootfs.digest_file(archive), "size_bytes": archive.stat().st_size}
        self.base = self.root / "old"
        self.old = omarchy_rootfs.bundle(self.base, [package], self.root, compression="gzip")
        self.replacement = self.root / "Hyprland"; self.replacement.write_bytes(b"real replacement compositor")
        self.destination = self.root / "new"

    def repack(self, **kwargs):
        return update.repack(self.base, self.destination, {"usr/bin/Hyprland": self.replacement},
                             expected_archive_sha256=self.old["archive_sha256"],
                             expected_manifest_sha256=self.old["manifest_sha256"], compression="gzip", **kwargs)

    def test_complete_payload_and_links_survive_and_old_version_is_unchanged(self):
        before = {p.name: p.read_bytes() for p in self.base.iterdir()}
        result = self.repack()
        with tarfile.open(self.destination / "rootfs.tar.gz") as reader:
            self.assertEqual(reader.extractfile("usr/bin/Hyprland").read(), self.replacement.read_bytes())
            self.assertEqual(reader.extractfile("usr/share/omarchy/docs/keyboard.md").read(), b"original manual")
            self.assertEqual(reader.extractfile("usr/bin/hard").read(), self.replacement.read_bytes())
            self.assertEqual(reader.getmember("usr/bin/link").linkname, "Hyprland")
            self.assertEqual(len(reader.getnames()), self.old["entries"])
        self.assertEqual(result["materialized_bytes"], 2 * len(self.replacement.read_bytes()) + len(b"original manual"))
        self.assertEqual(result["package_names"], ["one"])
        self.assertEqual({p.name: p.read_bytes() for p in self.base.iterdir()}, before)

    def test_tampered_archive_cannot_publish_or_leave_staging(self):
        with (self.base / "rootfs.tar.gz").open("ab") as output: output.write(b"unexpected trailing bytes")
        with self.assertRaises(ValueError): self.repack()
        self.assertFalse(self.destination.exists())
        self.assertFalse(list(self.root.glob(".omarchy-update-*")))

    def test_actual_zstd_decoder_and_encoder_preserve_the_complete_stream(self):
        first = update.repack(self.base, self.destination, {"usr/bin/Hyprland": self.replacement},
                              expected_archive_sha256=self.old["archive_sha256"],
                              expected_manifest_sha256=self.old["manifest_sha256"])
        second = self.root / "second"
        result = update.repack(self.destination, second, {"usr/bin/Hyprland": self.replacement},
                               expected_archive_sha256=first["archive_sha256"],
                               expected_manifest_sha256=first["manifest_sha256"])
        from compression import zstd
        with zstd.open(second / "rootfs.tar.zst", "rb") as stream, tarfile.open(fileobj=stream, mode="r|") as reader:
            files = {m.name: reader.extractfile(m).read() for m in reader if m.isfile()}
        self.assertEqual(files["usr/bin/Hyprland"], self.replacement.read_bytes())
        self.assertEqual(files["usr/share/omarchy/docs/keyboard.md"], b"original manual")
        self.assertEqual(result["entries"], self.old["entries"])

    def test_wrong_manifest_file_digest_is_rejected_even_with_matching_manifest_hash(self):
        path = self.base / "manifest.json"; content = json.loads(path.read_text())
        content["files"]["usr/share/omarchy/docs/keyboard.md"]["sha256"] = "0" * 64
        path.write_text(json.dumps(content))
        self.old["manifest_sha256"] = omarchy_rootfs.digest_file(path)
        receipt = self.base / "receipt.json"; value = json.loads(receipt.read_text())
        value["manifest_sha256"] = self.old["manifest_sha256"]; receipt.write_text(json.dumps(value))
        with self.assertRaises(ValueError): self.repack()
        self.assertFalse(self.destination.exists())
        self.assertFalse(list(self.root.glob(".omarchy-update-*")))

    def test_replacements_cannot_add_files_or_change_link_kind(self):
        for name in ("missing", "../outside", "usr/bin/link"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                update.repack(self.base, self.destination, {name: self.replacement},
                              expected_archive_sha256=self.old["archive_sha256"],
                              expected_manifest_sha256=self.old["manifest_sha256"], compression="gzip")
        self.assertFalse(self.destination.exists())

    def test_existing_destination_and_redirected_replacement_are_preserved(self):
        self.destination.mkdir(); (self.destination / "keep").write_bytes(b"saved")
        with self.assertRaises(FileExistsError): self.repack()
        self.assertEqual((self.destination / "keep").read_bytes(), b"saved")
        self.destination.joinpath("keep").unlink(); self.destination.rmdir()
        self.replacement.unlink(); self.replacement.symlink_to(self.base / "receipt.json")
        with self.assertRaises(ValueError): self.repack()
        self.assertFalse(self.destination.exists())

    def test_independent_verifier_checks_every_file_and_link(self):
        self.assertIsNotNone(verifier, "independent complete-image verification is missing")
        result = verifier.verify(self.base, expected_archive_sha256=self.old["archive_sha256"],
                                 expected_manifest_sha256=self.old["manifest_sha256"])
        self.assertEqual(result["entries"], self.old["entries"])
        self.assertEqual(result["regular_files"], 2)
        self.assertEqual(result["links"], 2)
        self.assertEqual(result["materialized_bytes"], self.old["materialized_bytes"])
        manifest = self.base / "manifest.json"; content = json.loads(manifest.read_text())
        content["files"]["usr/share/omarchy/docs/keyboard.md"]["sha256"] = "0" * 64
        manifest.write_text(json.dumps(content))
        value = json.loads((self.base / "receipt.json").read_text())
        value["manifest_sha256"] = omarchy_rootfs.digest_file(manifest)
        (self.base / "receipt.json").write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            verifier.verify(self.base, expected_archive_sha256=self.old["archive_sha256"],
                            expected_manifest_sha256=value["manifest_sha256"])

    def test_original_git_symlink_is_preserved_as_a_link_and_wrong_target_is_rejected(self):
        self.assertTrue(hasattr(verifier, "verify_original_source"), "original Git symlink validation is missing")
        source = self.root / "source"; source.mkdir()
        (source / "icon.png").write_bytes(b"original icon")
        (source / "link.png").symlink_to("icon.png")
        entries = {"usr/share/omarchy/icon.png": {"kind": "file", "sha256": hashlib.sha256(b"original icon").hexdigest()},
                   "usr/share/omarchy/link.png": {"kind": "symlink", "link": "icon.png"}}
        self.assertEqual(verifier.verify_original_source(source, entries), 2)
        entries["usr/share/omarchy/link.png"]["link"] = "different.png"
        with self.assertRaises(ValueError): verifier.verify_original_source(source, entries)


if __name__ == "__main__":
    unittest.main()
