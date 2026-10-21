"""Stream a new complete image from a pinned prior image and declared files."""
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
from tools.omarchy_rootfs import HashedInput, checked_path, digest_file, link_target


class HashingReader(io.RawIOBase):
    def __init__(self, source):
        self.source = source
        self.digest = hashlib.sha256()

    def readable(self):
        return True

    def readinto(self, buffer):
        data = self.source.read(len(buffer))
        buffer[:len(data)] = data
        self.digest.update(data)
        return len(data)


def metadata(member):
    name = checked_path(member.name)
    if name != member.name or name == "." or member.size < 0 or member.size > 2 * 1024**3:
        raise ValueError("noncanonical or oversized image entry")
    kind = "file" if member.isfile() else "directory" if member.isdir() else \
           "symlink" if member.issym() else "hardlink" if member.islnk() else None
    if kind is None or kind != "file" and member.size:
        raise ValueError("unsupported image entry")
    value = {"kind": kind, "mode": member.mode & 0o7777, "size": member.size}
    if kind in ("symlink", "hardlink"):
        value.update(link=member.linkname, target=link_target(name, member.linkname, kind == "hardlink"))
    return name, value


def materialized_bytes(entries):
    total = 0
    for name, entry in entries.items():
        for parent in PurePosixPath(name).parents:
            known = entries.get(parent.as_posix())
            if known and known["kind"] != "directory":
                raise ValueError("image path writes through a non-directory")
        if entry["kind"] == "file":
            total += entry["size"]
        elif entry["kind"] == "hardlink":
            target = entries.get(entry["target"])
            if not target or target["kind"] != "file":
                raise ValueError("image hardlink target is not a regular file")
            total += target["size"]
    return total


def repack(base, destination, replacements, *, expected_archive_sha256,
           expected_manifest_sha256, compression="zstd", progress=None):
    base, destination = Path(base), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("existing image version is preserved")
    receipt_path, manifest_path = base / "receipt.json", base / "manifest.json"
    for path in (base, receipt_path, manifest_path):
        if path.is_symlink() or not path.exists():
            raise ValueError("regular pinned base image required")
    old = json.loads(receipt_path.read_text())
    if old.get("status") != "packaged-reference-rootfs" or old.get("archive") not in ("rootfs.tar.zst", "rootfs.tar.gz") \
            or old.get("archive_sha256") != expected_archive_sha256 \
            or old.get("manifest_sha256") != expected_manifest_sha256:
        raise ValueError("base image receipt differs from expected identity")
    archive = base / old["archive"]
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size != old["archive_bytes"] \
            or digest_file(archive) != expected_archive_sha256 or manifest_path.stat().st_size > 160 * 1024**2:
        raise ValueError("base image bytes differ")
    raw_manifest = manifest_path.read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest() != expected_manifest_sha256:
        raise ValueError("base manifest bytes differ")
    original = json.loads(raw_manifest)["files"]
    if len(original) != old["entries"] or materialized_bytes(original) != old["materialized_bytes"] \
            or len(old["package_names"]) != old["packages"]:
        raise ValueError("base image inventory differs")
    if not replacements:
        raise ValueError("an explicit image update is required")
    paths, changes = {}, {}
    for name, path in replacements.items():
        if checked_path(name) != name or name not in original or original[name]["kind"] != "file":
            raise ValueError("only declared existing regular files may be updated")
        path = Path(path)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024**3:
            raise ValueError("regular bounded replacement required")
        paths[name] = path
        changes[name] = {"before_sha256": original[name]["sha256"], "sha256": digest_file(path),
                         "bytes": path.stat().st_size, "mode": original[name]["mode"]}
    entries = copy.deepcopy(original)
    for name, change in changes.items():
        entries[name].update(sha256=change["sha256"], size=change["bytes"])
    total = materialized_bytes(entries)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".omarchy-update-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        output = staging / ("rootfs.tar.zst" if compression == "zstd" else "rootfs.tar.gz")
        with archive.open("rb") as source, output.open("xb") as sink:
            hashed_source = HashingReader(source)
            if old["archive"].endswith(".zst"):
                from compression import zstd
                decoded = zstd.open(hashed_source, "rb")
            else:
                decoded = gzip.GzipFile(fileobj=hashed_source, mode="rb")
            if compression == "zstd":
                from compression import zstd
                encoded = zstd.open(sink, "wb", options={zstd.CompressionParameter.compression_level: 8,
                                                         zstd.CompressionParameter.nb_workers: 2})
            elif compression == "gzip":
                encoded = gzip.GzipFile(fileobj=sink, mode="wb", filename="", mtime=0)
            else:
                raise ValueError("unsupported image compression")
            seen = set()
            with decoded, encoded, tarfile.open(fileobj=decoded, mode="r|") as reader, \
                    tarfile.open(fileobj=encoded, mode="w|", format=tarfile.PAX_FORMAT) as writer:
                for member in reader:
                    name, value = metadata(member)
                    if name in seen or name not in original or any(original[name].get(k) != v for k, v in value.items()):
                        raise ValueError("actual image entry differs from the pinned manifest: " + name)
                    seen.add(name)
                    if value["kind"] == "file":
                        old_file = HashedInput(reader.extractfile(member))
                        if name not in paths:
                            writer.addfile(member, old_file)
                        else:
                            while old_file.read(1024 * 1024):
                                pass
                        if old_file.bytes != member.size or old_file.digest.hexdigest() != original[name]["sha256"]:
                            raise ValueError("actual base file bytes differ: " + name)
                        if name in paths:
                            changed = copy.copy(member)
                            changed.pax_headers = dict(member.pax_headers)
                            changed.pax_headers.pop("size", None)
                            changed.size = changes[name]["bytes"]
                            with paths[name].open("rb") as content:
                                current = HashedInput(content)
                                writer.addfile(changed, current)
                            if current.bytes != changed.size or current.digest.hexdigest() != changes[name]["sha256"]:
                                raise ValueError("replacement changed while packaging: " + name)
                    else:
                        writer.addfile(member)
                    if progress and (len(seen) == 1 or len(seen) % 25000 == 0):
                        progress(len(seen), len(original))
                # Verify all compressed bytes, including padding beyond tar's EOF.
                while data := reader.fileobj.read(1024 * 1024):
                    if any(data):
                        raise ValueError("nonzero bytes after the image tar terminator")
                if seen != set(original) or hashed_source.digest.hexdigest() != expected_archive_sha256:
                    raise ValueError("base stream is incomplete or changed during packaging")
        manifest = staging / "manifest.json"
        manifest.write_text(json.dumps({"schema_version": 1, "files": entries}, indent=2) + "\n")
        result = dict(old)
        result.update(archive=output.name, archive_bytes=output.stat().st_size, archive_sha256=digest_file(output),
                      manifest_sha256=digest_file(manifest), materialized_bytes=total, format="PAX tar + " + compression,
                      base_archive_sha256=expected_archive_sha256, base_manifest_sha256=expected_manifest_sha256,
                      updated_files=changes, repacker_sha256=digest_file(Path(__file__)),
                      physical_device=False, hardware_gpu=False, omarchy_support_complete=False)
        (staging / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("image destination appeared during packaging; preserved")
        staging.rename(destination)
    return result
