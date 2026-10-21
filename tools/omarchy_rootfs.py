"""Stream complete verified package payloads into a separate bounded Arch rootfs."""
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import tarfile
import tempfile

CONTROLS = {".PKGINFO", ".BUILDINFO", ".MTREE", ".INSTALL", ".CHANGELOG", ".SIGNATURE"}


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for data in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def checked_path(value):
    # Linux/Android use POSIX separators. systemd's literal '\\x2d' unit names
    # must remain unchanged; backslash is a filename character on these systems.
    if not value or len(value.encode()) > 4096 or any(c in value for c in "\0\n\r"):
        raise ValueError("invalid rootfs path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("rootfs path escapes its root")
    return path.as_posix()


def link_target(name, target, hard=False):
    if not target or any(c in target for c in "\0\n\r"):
        raise ValueError("invalid rootfs link")
    parts = [] if hard or target.startswith("/") else list(PurePosixPath(name).parent.parts)
    for part in PurePosixPath(target.lstrip("/")).parts:
        if part == "..":
            if not parts:
                raise ValueError("rootfs link escapes its root")
            parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts) or "."


class HashedInput:
    def __init__(self, source):
        self.source = source
        self.digest = hashlib.sha256()
        self.bytes = 0

    def read(self, size):
        data = self.source.read(size)
        self.digest.update(data)
        self.bytes += len(data)
        return data


class Payload:
    def __init__(self, writer, max_bytes, max_entries, replaced):
        self.writer, self.max_bytes, self.max_entries = writer, max_bytes, max_entries
        self.replaced, self.entries = replaced, {}
        self.bytes, self.seen = 0, 0

    def add(self, member, stream, owner, *, replacement=False):
        self.seen += 1
        if self.seen > self.max_entries * 4:
            raise ValueError("too many package members")
        name = checked_path(member.name)
        if name == "." and member.isdir():
            return
        if name == "." or member.size < 0 or member.size > 2 * 1024**3:
            raise ValueError("invalid or oversized rootfs member")
        kind = "file" if member.isfile() else "directory" if member.isdir() else \
               "symlink" if member.issym() else "hardlink" if member.islnk() else None
        if kind is None or kind != "file" and member.size:
            raise ValueError("unsupported rootfs member")
        entry = {"kind": kind, "mode": member.mode & 0o7777, "size": member.size, "owners": [owner]}
        old = self.entries.get(name)
        if kind == "file":
            old_bytes = old["size"] if old and replacement else 0
            if self.bytes - old_bytes + member.size > self.max_bytes:
                raise ValueError("rootfs exceeds its byte budget")
            hashed = HashedInput(stream)
            if old is None and (name not in self.replaced or replacement):
                self.writer.addfile(self.header(name, entry), hashed)
            else:
                for _ in iter(lambda: hashed.read(1024 * 1024), b""):
                    pass
            if hashed.bytes != member.size:
                raise ValueError("rootfs member size differs")
            entry["sha256"] = hashed.digest.hexdigest()
        elif kind in ("symlink", "hardlink"):
            target = link_target(name, member.linkname, kind == "hardlink")
            entry["target"] = target
            entry["link"] = target if kind == "hardlink" else posixpath.relpath(target, posixpath.dirname(name) or ".")
        if old:
            if replacement:
                if name not in self.replaced or old["kind"] != "file" or kind != "file":
                    raise ValueError("invalid declared file replacement")
                entry["replaces"] = {k: old[k] for k in ("sha256", "owners")}
                self.bytes -= old["size"]
                stream.seek(0)
                reread = HashedInput(stream)
                self.writer.addfile(self.header(name, entry), reread)
                if reread.bytes != member.size or reread.digest.hexdigest() != entry["sha256"]:
                    raise ValueError("replacement changed during preparation")
            elif {k: v for k, v in old.items() if k != "owners"} != {k: v for k, v in entry.items() if k != "owners"}:
                raise ValueError("conflicting package files: " + name)
            else:
                old["owners"].append(owner)
                return
        elif len(self.entries) >= self.max_entries:
            raise ValueError("rootfs exceeds its entry budget")
        elif kind == "directory":
            self.writer.addfile(self.header(name, entry))
        self.entries[name] = entry
        if kind == "file":
            self.bytes += member.size

    @staticmethod
    def header(name, entry):
        info = tarfile.TarInfo(name)
        info.mode, info.uid, info.gid, info.mtime = entry["mode"], 0, 0, 0
        info.uname = info.gname = "root"
        info.type = {"file": tarfile.REGTYPE, "directory": tarfile.DIRTYPE,
                     "symlink": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE}[entry["kind"]]
        info.size = entry["size"] if entry["kind"] == "file" else 0
        info.linkname = entry.get("link", "")
        return info

    def archive(self, path, owner, *, package=None, prefix=None):
        info_found = False
        with tarfile.open(path, "r:*") as archive:
            for member in archive:
                name = checked_path(member.name)
                if package and name in CONTROLS:
                    self.seen += 1
                    if self.seen > self.max_entries * 4 or not member.isfile() or member.size > 4 * 1024**2:
                        raise ValueError("invalid package control metadata")
                    if name == ".PKGINFO":
                        if info_found:
                            raise ValueError("duplicate package identity")
                        values = {}
                        for line in archive.extractfile(member).read().decode().splitlines():
                            key, separator, value = line.partition(" = ")
                            if separator and key in ("pkgname", "pkgver", "arch"):
                                if key in values:
                                    raise ValueError("duplicate package identity field")
                                values[key] = value
                        if values != {"pkgname": package["name"], "pkgver": package["version"], "arch": package["architecture"]}:
                            raise ValueError("package payload identity differs")
                        info_found = True
                    continue
                if prefix:
                    source_root, destination = prefix
                    parts = PurePosixPath(name).parts
                    if not parts or parts[0] != source_root:
                        raise ValueError("original source archive prefix differs")
                    member.name = destination + ("/" + "/".join(parts[1:]) if len(parts) > 1 else "")
                self.add(member, archive.extractfile(member) if member.isfile() else None, owner)
        if package and not info_found:
            raise ValueError("package payload has no identity")

    def local_file(self, name, path):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError("local rootfs input must be a regular file")
        member = tarfile.TarInfo(name)
        member.size, member.mode = path.stat().st_size, path.stat().st_mode & 0o7777
        with path.open("rb") as source:
            self.add(member, source, "reference-public-setup", replacement=name in self.replaced)

    def finish(self):
        for name, entry in self.entries.items():
            for parent in PurePosixPath(name).parents:
                known = self.entries.get(parent.as_posix())
                if known and known["kind"] != "directory":
                    raise ValueError("rootfs writes through a non-directory: " + name)
            if entry["kind"] == "hardlink":
                target = self.entries.get(entry["target"])
                if not target or target["kind"] != "file":
                    raise ValueError("invalid hardlink target")
                self.bytes += target["size"]
                if self.bytes > self.max_bytes:
                    raise ValueError("materialized hardlinks exceed storage budget")
        for name, entry in sorted(self.entries.items()):
            if entry["kind"] in ("symlink", "hardlink"):
                self.writer.addfile(self.header(name, entry))


def bundle(destination, packages, cache, *, extras=None, replace=None, source=None,
           compression="zstd", max_bytes=12 * 1024**3, max_entries=300000, progress=None):
    destination, cache = Path(destination), Path(cache)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("refuse to overwrite a rootfs bundle")
    extras, replace = extras or {}, set(replace or ())
    if not replace <= set(extras) or max_bytes <= 0 or max_entries <= 0:
        raise ValueError("invalid rootfs bundle policy")
    names = set()
    for package in packages:
        filename = checked_path(package["filename"])
        path = cache / filename
        if "/" in filename or package["name"] in names or path.is_symlink() or not path.is_file() \
                or path.stat().st_size != package["size_bytes"] or digest_file(path) != package["sha256"]:
            raise ValueError("package cache identity differs")
        names.add(package["name"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".omarchy-rootfs-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        archive = staging / ("rootfs.tar.zst" if compression == "zstd" else "rootfs.tar.gz")
        with archive.open("xb") as raw:
            if compression == "zstd":
                from compression import zstd
                compressed = zstd.open(raw, "wb", options={zstd.CompressionParameter.compression_level: 8,
                                                          zstd.CompressionParameter.nb_workers: 2})
            elif compression == "gzip":
                compressed = gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0)
            else:
                raise ValueError("unsupported bundle compression")
            with compressed, tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as writer:
                payload = Payload(writer, max_bytes, max_entries, replace)
                for index, package in enumerate(packages, 1):
                    payload.archive(cache / package["filename"], package["name"], package=package)
                    if progress:
                        progress(index, len(packages), payload.bytes, len(payload.entries))
                if source:
                    payload.archive(source["path"], "original-omarchy-source", prefix=source["prefix"])
                for name, path in sorted(extras.items()):
                    if name in payload.entries and name not in replace:
                        raise ValueError("local file replacement was not declared")
                    payload.local_file(name, path)
                payload.finish()
            raw.flush(); os.fsync(raw.fileno())
        manifest = {"schema_version": 1, "files": payload.entries}
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, separators=(",", ":")) + "\n")
        receipt = {"status": "packaged-reference-rootfs", "packages": len(packages),
                   "package_names": sorted(names), "entries": len(payload.entries),
                   "materialized_bytes": payload.bytes, "archive": archive.name,
                   "archive_bytes": archive.stat().st_size, "archive_sha256": digest_file(archive),
                   "manifest_sha256": digest_file(manifest_path), "format": "PAX tar + " + compression,
                   "physical_device": False, "hardware_gpu": False, "omarchy_support_complete": False}
        (staging / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("bundle appeared during preparation")
        staging.rename(destination)
    return receipt
