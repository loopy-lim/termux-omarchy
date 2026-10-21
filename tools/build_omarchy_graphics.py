#!/usr/bin/env python3
"""Prepare guarded Aquamarine sources; optionally build in the dedicated ARM VM.

Source preparation and ELF compilation never imply usable Android Omarchy/GPU.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.prepare_omarchy import load_lock, relative, verify_file


def extract_source(archive, destination, commit, *, project="aquamarine"):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Refuse to replace source destination")
    files, seen, total = [], set(), 0
    if project not in ("aquamarine", "Hyprland", "glaze", "udis86", "hyprland-protocols", "hyprtoolkit"):
        raise ValueError("Unsupported graphics source project")
    maximum_file = 64 * 1024**2 if project == "Hyprland" else 4 * 1024**2
    maximum_total = 256 * 1024**2 if project == "Hyprland" else 64 * 1024**2
    with tarfile.open(archive, "r:gz") as reader:
        for number, member in enumerate(reader):
            path = PurePosixPath(member.name)
            if number > 4096 or not path.parts or path.parts[0] != project + "-" + commit \
                    or path.is_absolute() or ".." in path.parts or "\\" in member.name:
                raise ValueError("Unsafe source archive path")
            if member.isdir():
                continue
            name = str(PurePosixPath(*path.parts[1:]))
            if not member.isfile() or len(path.parts) < 2 or name in seen \
                    or not 0 <= member.size <= maximum_file:
                raise ValueError("Unsafe or duplicate source archive file")
            seen.add(name)
            total += member.size
            if total > maximum_total:
                raise ValueError("Source archive exceeds budget")
            data = reader.extractfile(member).read()
            if len(data) != member.size:
                raise ValueError("Incomplete source archive")
            files.append((name, data, member.mode & 0o755))
    if not files:
        raise ValueError("Empty source archive")
    destination.mkdir()
    for name, data, mode in files:
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)


def apply_guarded_patch(source, patch, metadata, *, project="aquamarine"):
    source, patch = Path(source), Path(patch)
    if project not in ("aquamarine", "hyprland", "hyprtoolkit"):
        raise ValueError("Unsupported added module project")
    modules = ROOT / "native/omarchy" / project
    verify_file(patch, metadata["patch_sha256"])
    files = metadata.get("files") or {metadata["source_file"]: metadata}
    declared = set()
    for line in patch.read_text().splitlines():
        if line.startswith(("--- ", "+++ ")):
            marker = line[4:].split("\t", 1)[0]
            if not marker.startswith(("a/", "b/")):
                raise ValueError("Unexpected patch path")
            declared.add(relative(marker[2:]))
    if declared != set(files):
        raise ValueError("Patch changes unguarded files")
    for name, identity in files.items():
        verify_file(source / relative(name), identity["preimage_sha256"])
    added = metadata.get("added_files", {})
    for name, identity in added.items():
        verify_file(modules / relative(name), identity)
        if (source / name).exists() or (source / name).is_symlink():
            raise ValueError("Added module would replace existing source")
    result = subprocess.run(["patch", "-p1", "-F", "0", "--batch", "--input", str(patch.resolve())],
                            cwd=source, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError("Guarded patch application failed")
    for name, identity in files.items():
        verify_file(source / name, identity["patched_sha256"])
    for name in added:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((modules / name).read_bytes())


def prepare(lock_path, cache, destination):
    lock_path, cache, destination = Path(lock_path), Path(cache), Path(destination)
    lock = load_lock(lock_path)
    sources = [s for s in lock["graphics_sources"] if s["repo"] == "hyprwm/aquamarine"]
    if len(sources) != 1:
        raise ValueError("Aquamarine requires one immutable source")
    upstream = sources[0]
    archive = cache / ("aquamarine-" + upstream["commit"] + ".tar.gz")
    verify_file(archive, upstream["archive_sha256"])
    if destination.exists() or destination.is_symlink():
        raise ValueError("Refuse to overwrite existing candidate")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".aq-", dir=destination.parent) as temporary:
        candidate = Path(temporary) / "source"
        extract_source(archive, candidate, upstream["commit"])
        for entry in lock["graphics_patches"]:
            metadata_file = ROOT / relative(entry["metadata_file"])
            verify_file(metadata_file, entry["metadata_sha256"])
            metadata = json.loads(metadata_file.read_text())
            if metadata["upstream_commit"] != upstream["commit"]:
                raise ValueError("Patch upstream mismatch")
            apply_guarded_patch(candidate, ROOT / relative(entry["patch"]), metadata)
        receipt = {"architecture": "aarch64", "upstream": upstream,
                   "lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
                   "patches_applied": len(lock["graphics_patches"]), "patches": lock["graphics_patches"],
                   "source_files": {str(p.relative_to(candidate)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted(candidate.rglob("*")) if p.is_file()},
                   "status": "source-prepared", "omarchy_support_complete": False}
        (candidate / "loopy-source-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        candidate.rename(destination)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=ROOT / "build/omarchy-sources")
    parser.add_argument("--build", type=Path, help="optional dedicated VM build directory")
    args = parser.parse_args()
    if args.build and (os.getuid() == 0 or os.uname().machine != "aarch64" or ROOT != Path("/workspace")
                       or args.build.parent != Path("/var/tmp") or not args.build.name.startswith("loopy-aquamarine-")):
        parser.error("compilation requires ordinary user in the scoped ARM VM")
    receipt = prepare(ROOT / "third_party/omarchy.lock.json", args.cache, args.output)
    if args.build:
        subprocess.run(["cmake", "-S", str(args.output), "-B", str(args.build), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"], check=True)
        subprocess.run(["cmake", "--build", str(args.build), "--target", "aquamarine", "--parallel", "2"], check=True)
        binary = args.build / "libaquamarine.so.0.15.1"
        receipt.update(status="compiled-in-reference-vm", binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), uid=os.getuid())
        (args.output / "loopy-build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: receipt[k] for k in ("status", "patches_applied", "omarchy_support_complete")}))


if __name__ == "__main__":
    main()
