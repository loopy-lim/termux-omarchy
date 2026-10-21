"""Whole-package rootfs boundaries, without extracting into or importing a HOME."""
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

try:
    from tools import omarchy_rootfs as rootfs
except ImportError:
    rootfs = None
try:
    from tools import build_omarchy_rootfs as build
except ImportError:
    build = None


class OmarchyRootfsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(rootfs, "separate complete Arch rootfs builder is missing")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name)
        self.destination = self.cache / "bundle"

    def package(self, name, entries):
        path = self.cache / (name + ".pkg.tar.gz")
        with tarfile.open(path, "w:gz") as writer:
            metadata = f"pkgname = {name}\npkgver = 1-1\narch = aarch64\n".encode()
            info = tarfile.TarInfo(".PKGINFO"); info.size = len(metadata)
            writer.addfile(info, io.BytesIO(metadata))
            for entry_name, data, kind in entries:
                info = tarfile.TarInfo(entry_name); info.mode = 0o755 if entry_name.startswith("usr/bin/") else 0o644
                info.type = kind
                if kind == tarfile.REGTYPE:
                    info.size = len(data); writer.addfile(info, io.BytesIO(data))
                else:
                    if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                        info.linkname = data
                    writer.addfile(info)
        return {"name": name, "version": "1-1", "architecture": "aarch64",
                "filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size}

    def build(self, packages, **options):
        return rootfs.bundle(self.destination, packages, self.cache, compression="gzip", **options)

    def test_all_package_bytes_and_internal_links_survive_without_control_or_home_import(self):
        packages = [self.package("one", [("usr/bin/tool", b"public executable", tarfile.REGTYPE),
                                          ("bin", "usr/bin", tarfile.SYMTYPE)]),
                    self.package("two", [("usr/share/doc/two/readme", b"complete docs", tarfile.REGTYPE),
                                          ("usr/bin/alias", "/usr/bin/tool", tarfile.SYMTYPE)])]
        self.build(packages)
        with tarfile.open(self.destination / "rootfs.tar.gz") as archive:
            self.assertEqual(archive.extractfile("usr/bin/tool").read(), b"public executable")
            self.assertEqual(archive.extractfile("usr/share/doc/two/readme").read(), b"complete docs")
            self.assertEqual(archive.getmember("usr/bin/alias").linkname, "tool")
            self.assertEqual(archive.getmember("bin").linkname, "usr/bin")
            self.assertNotIn(".PKGINFO", archive.getnames())
            self.assertFalse(any(p.startswith("home/") for p in archive.getnames()))

    def test_hash_mismatch_cannot_publish_or_leave_a_partial_bundle(self):
        package = self.package("one", [("usr/bin/tool", b"original", tarfile.REGTYPE)])
        (self.cache / package["filename"]).write_bytes(b"tampered")
        with self.assertRaises(ValueError): self.build([package])
        self.assertFalse(self.destination.exists())
        self.assertFalse(list(self.cache.glob(".omarchy-rootfs-*")))

    def test_traversal_and_special_files_never_publish(self):
        for name, kind in [("../outside", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
                           ("dev/dangerous", tarfile.CHRTYPE)]:
            with self.subTest(name=name):
                package = self.package("one", [(name, b"unexpected", kind)])
                with self.assertRaises(ValueError): self.build([package])
                self.assertFalse(self.destination.exists())

    def test_a_later_symlink_cannot_redirect_an_earlier_package_file(self):
        packages = [self.package("one", [("usr/share/link/file", b"owned", tarfile.REGTYPE)]),
                    self.package("two", [("usr/share/link", "../../elsewhere", tarfile.SYMTYPE)])]
        with self.assertRaises(ValueError): self.build(packages)
        self.assertFalse(self.destination.exists())

    def test_conflicting_regular_files_cannot_silently_replace_each_other(self):
        packages = [self.package("one", [("usr/bin/tool", b"first", tarfile.REGTYPE)]),
                    self.package("two", [("usr/bin/tool", b"second", tarfile.REGTYPE)])]
        with self.assertRaises(ValueError): self.build(packages)
        self.assertFalse(self.destination.exists())

    def test_hardlink_materialization_is_counted_against_storage_budget(self):
        package = self.package("one", [("usr/bin/tool", b"x" * 64, tarfile.REGTYPE),
                                      ("usr/bin/alias", "usr/bin/tool", tarfile.LNKTYPE)])
        with self.assertRaises(ValueError): self.build([package], max_bytes=100)
        self.assertFalse(self.destination.exists())

    def test_missing_or_symlinked_hardlink_targets_are_rejected(self):
        package = self.package("one", [("usr/bin/tool", "missing", tarfile.SYMTYPE),
                                      ("usr/bin/alias", "usr/bin/tool", tarfile.LNKTYPE)])
        with self.assertRaises(ValueError): self.build([package])
        self.assertFalse(self.destination.exists())

    def test_relative_or_absolute_link_traversal_cannot_escape_rootfs(self):
        for target in ("../../../outside", "/../../outside"):
            with self.subTest(target=target):
                package = self.package("one", [("usr/bin/link", target, tarfile.SYMTYPE)])
                with self.assertRaises(ValueError): self.build([package])
                self.assertFalse(self.destination.exists())

    def test_entry_budget_does_not_publish_a_truncated_package_set(self):
        package = self.package("one", [("usr/bin/one", b"1", tarfile.REGTYPE),
                                      ("usr/bin/two", b"2", tarfile.REGTYPE),
                                      ("usr/bin/three", b"3", tarfile.REGTYPE)])
        with self.assertRaises(ValueError): self.build([package], max_entries=2)
        self.assertFalse(self.destination.exists())

    def test_linux_systemd_escaped_unit_filenames_are_preserved_literally(self):
        unit = "usr/lib/systemd/system/system-systemd\\x2dcryptsetup.slice"
        package = self.package("one", [(unit, b"[Unit]\n", tarfile.REGTYPE),
                                      ("usr/lib/systemd/system/alias.slice", "system-systemd\\x2dcryptsetup.slice", tarfile.SYMTYPE)])
        self.build([package])
        with tarfile.open(self.destination / "rootfs.tar.gz") as archive:
            self.assertEqual(archive.extractfile(unit).read(), b"[Unit]\n")
            self.assertEqual(archive.getmember("usr/lib/systemd/system/alias.slice").linkname,
                             "system-systemd\\x2dcryptsetup.slice")

    def test_declared_patch_override_is_hashed_and_other_conflicts_still_fail(self):
        package = self.package("one", [("usr/bin/tool", b"original", tarfile.REGTYPE)])
        patch = self.cache / "patched"; patch.write_bytes(b"patched executable")
        self.build([package], extras={"usr/bin/tool": patch}, replace={"usr/bin/tool"})
        with tarfile.open(self.destination / "rootfs.tar.gz") as archive:
            self.assertEqual(archive.extractfile("usr/bin/tool").read(), b"patched executable")
            self.assertEqual(archive.getnames().count("usr/bin/tool"), 1)

    def test_existing_bundle_is_preserved(self):
        self.destination.mkdir(); sentinel = self.destination / "sentinel"; sentinel.write_bytes(b"keep")
        package = self.package("one", [])
        with self.assertRaises(FileExistsError): self.build([package])
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_public_setup_export_excludes_machine_identity_credentials_and_home(self):
        self.assertIsNotNone(build, "scoped reference rootfs entry point is missing")
        vm = self.cache / "reference"
        metadata = vm / "var/lib/pacman/local/one-1-1"; metadata.mkdir(parents=True)
        for name, data in (("desc", b"%NAME%\none\n\n%VERSION%\n1-1\n"),
                           ("files", b"%FILES%\nusr/bin/tool\n"), ("mtree", b"public mtree")):
            (metadata / name).write_bytes(data)
        for name in ("home/loopy/.ssh/id_ed25519", "etc/machine-id", "etc/shadow", "etc/ssh/ssh_host_rsa_key"):
            path = vm / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b"private")
        cache = vm / "usr/share/glib-2.0/schemas/gschemas.compiled"
        cache.parent.mkdir(parents=True); cache.write_bytes(b"generated public schema")
        extras = build.package_setup_files(vm, [{"name": "one", "version": "1-1"}])
        self.assertEqual(set(extras), {"var/lib/pacman/local/one-1-1/desc", "var/lib/pacman/local/one-1-1/files",
                                      "var/lib/pacman/local/one-1-1/mtree", "usr/share/glib-2.0/schemas/gschemas.compiled"})

    def test_installed_metadata_identity_must_match_the_verified_package(self):
        self.assertIsNotNone(build, "scoped reference rootfs entry point is missing")
        vm = self.cache / "reference"; metadata = vm / "var/lib/pacman/local/one-1-1"; metadata.mkdir(parents=True)
        (metadata / "desc").write_text("%NAME%\ndifferent\n\n%VERSION%\n1-1\n")
        (metadata / "files").write_text("%FILES%\n"); (metadata / "mtree").write_bytes(b"public")
        with self.assertRaises(ValueError): build.package_setup_files(vm, [{"name": "one", "version": "1-1"}])


if __name__ == "__main__":
    unittest.main()
