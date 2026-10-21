#!/usr/bin/env python3
"""Independently read every image member and verify original Omarchy scope."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import tarfile


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def verify_original_source(source, entries):
    paths = [p for p in source.rglob("*") if p.is_file() or p.is_symlink()]
    for path in paths:
        entry = entries.get("usr/share/omarchy/" + path.relative_to(source).as_posix())
        if not entry:
            raise ValueError("original Omarchy source is absent: " + str(path.relative_to(source)))
        if path.is_symlink():
            # Git records the link text, not the bytes of the linked PNG.
            if entry["kind"] != "symlink" or entry["link"] != str(path.readlink()):
                raise ValueError("original Omarchy symlink differs: " + str(path.relative_to(source)))
        else:
            actual = entries.get(entry["target"]) if entry["kind"] == "hardlink" else entry
            if not actual or actual["kind"] != "file" or actual["sha256"] != digest(path):
                raise ValueError("original Omarchy source differs: " + str(path.relative_to(source)))
    return len(paths)


def verify(directory, *, expected_archive_sha256, expected_manifest_sha256, progress=None):
    directory = Path(directory)
    receipt = json.loads((directory / "receipt.json").read_text())
    archive, manifest_path = directory / receipt["archive"], directory / "manifest.json"
    if receipt["archive"] not in ("rootfs.tar.zst", "rootfs.tar.gz") or archive.is_symlink() or manifest_path.is_symlink() \
            or digest(archive) != expected_archive_sha256 or digest(manifest_path) != expected_manifest_sha256 \
            or receipt["archive_sha256"] != expected_archive_sha256 or receipt["manifest_sha256"] != expected_manifest_sha256 \
            or archive.stat().st_size != receipt["archive_bytes"]:
        raise ValueError("image does not match its pinned verification inputs")
    entries = json.loads(manifest_path.read_text())["files"]
    if len(entries) != receipt["entries"]:
        raise ValueError("image manifest count differs")
    seen, files, links, total, packages, provenance = set(), 0, 0, 0, {}, None
    if archive.name.endswith(".zst"):
        from compression import zstd
        decoded = zstd.open(archive, "rb")
    else:
        decoded = gzip.open(archive, "rb")
    with decoded, tarfile.open(fileobj=decoded, mode="r|") as reader:
        for member in reader:
            name = member.name
            path = PurePosixPath(name)
            if not name or path.is_absolute() or ".." in path.parts or name != path.as_posix() \
                    or name in seen or name not in entries:
                raise ValueError("unexpected, duplicate or unsafe actual image path")
            expected = entries[name]
            kind = "file" if member.isreg() else "directory" if member.isdir() else \
                   "symlink" if member.issym() else "hardlink" if member.islnk() else None
            if kind != expected["kind"] or member.size != expected["size"] or member.mode & 0o7777 != expected["mode"]:
                raise ValueError("actual image header differs: " + name)
            seen.add(name)
            for parent in path.parents:
                if parent.as_posix() in entries and entries[parent.as_posix()]["kind"] != "directory":
                    raise ValueError("image redirects a file through a non-directory")
            if kind == "file":
                hashed, size = hashlib.sha256(), 0
                capture = name == "usr/share/loopy/omarchy-reference-provenance.json" \
                    or name.startswith("var/lib/pacman/local/") and name.endswith("/desc")
                if capture and member.size > 1024**2:
                    raise ValueError("oversized public image metadata")
                data = bytearray() if capture else None
                stream = reader.extractfile(member)
                while chunk := stream.read(1024 * 1024):
                    hashed.update(chunk); size += len(chunk)
                    if data is not None:
                        data.extend(chunk)
                if size != member.size or hashed.hexdigest() != expected["sha256"]:
                    raise ValueError("actual file bytes differ: " + name)
                files += 1; total += size
                if name == "usr/share/loopy/omarchy-reference-provenance.json":
                    provenance = json.loads(data)
                elif data is not None:
                    fields = {lines[0]: lines[1:] for block in data.decode().split("\n\n") if (lines := block.splitlines())}
                    if len(fields.get("%NAME%", [])) != 1 or len(fields.get("%VERSION%", [])) != 1:
                        raise ValueError("invalid actual Pacman identity")
                    package = fields["%NAME%"][0]
                    if package in packages:
                        raise ValueError("duplicate actual Pacman package")
                    packages[package] = fields["%VERSION%"][0]
            elif kind in ("symlink", "hardlink"):
                links += 1
                if member.linkname != expected["link"]:
                    raise ValueError("actual image link differs")
                target = posixpath.normpath(member.linkname if kind == "hardlink" else posixpath.join(str(path.parent), member.linkname))
                if target.startswith("/") or target == ".." or target.startswith("../") or target != expected["target"]:
                    raise ValueError("actual link target escapes or differs")
                if kind == "hardlink":
                    linked = entries.get(target)
                    if not linked or linked["kind"] != "file":
                        raise ValueError("actual hardlink target is not a file")
                    total += linked["size"]
            elif kind != "directory":
                raise ValueError("unsupported actual image entry")
            if progress and len(seen) % 25000 == 0:
                progress(len(seen), len(entries))
        while chunk := reader.fileobj.read(1024 * 1024):
            if any(chunk):
                raise ValueError("unexpected bytes after actual tar terminator")
    if seen != set(entries) or total != receipt["materialized_bytes"]:
        raise ValueError("incomplete actual image inventory")
    return {"status": "all-rootfs-bytes-and-links-verified", "entries": len(seen), "regular_files": files,
            "links": links, "materialized_bytes": total, "archive_sha256": expected_archive_sha256,
            "manifest_sha256": expected_manifest_sha256, "packages": receipt["packages"],
            "actual_pacman_packages": packages, "public_provenance": provenance}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.output.exists() or args.output.is_symlink():
        raise FileExistsError("existing independent verification is preserved")
    receipt = json.loads((args.bundle / "receipt.json").read_text())
    result = verify(args.bundle, expected_archive_sha256=receipt["archive_sha256"],
                    expected_manifest_sha256=receipt["manifest_sha256"],
                    progress=lambda count, total: print(json.dumps({"entries_verified": count, "total": total}), flush=True))
    entries = json.loads((args.bundle / "manifest.json").read_text())["files"]
    lock = json.loads((root / "third_party/omarchy.lock.json").read_text())
    source = root / "build/omarchy-sources/omarchy"
    source_files = verify_original_source(source, entries)
    manual = len(list((source / "manual").rglob("*.md")))
    qml = len(list((source / "shell").rglob("*.qml")))
    if source_files != lock["omarchy_source"]["git_blobs_verified"] or manual != 51 or qml != 119:
        raise ValueError("original source scope differs")
    expected_packages = json.loads((root / "docs/validation/2026-10-06-omarchy/runtime-packages-verified.json").read_text())["packages"]
    if result["actual_pacman_packages"] != {p["name"]: p["version"] for p in expected_packages}:
        raise ValueError("actual complete package inventory differs")
    reference = json.loads((args.reference / "receipt.json").read_text())
    for name, path in (("Hyprland", "usr/bin/Hyprland"), ("hyprctl", "usr/bin/hyprctl"),
                       ("libaquamarine.so.0.15.1", "usr/lib/libaquamarine.so.0.15.1")):
        if entries[path]["sha256"] != reference["files"][name]["sha256"] \
                or digest(args.reference / name) != reference["files"][name]["sha256"]:
            raise ValueError("current reproduced image binary differs")
    provenance = result.pop("public_provenance")
    if not provenance or provenance["original_requests"] != lock["requested"] \
            or provenance["patched_binary_receipt_sha256"] != digest(args.reference / "receipt.json") \
            or provenance["user_home_imported"] or provenance["machine_private_data_imported"]:
        raise ValueError("current full-image public provenance differs")
    result.pop("actual_pacman_packages")
    result.update(original_source_files=source_files, original_manual_files=manual, original_qml_files=qml,
                  patched_binaries_match=True, user_home_imported=False, physical_device=False,
                  hardware_gpu=False, omarchy_support_complete=False, verifier_sha256=digest(Path(__file__)))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
