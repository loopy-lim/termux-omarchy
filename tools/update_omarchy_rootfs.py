#!/usr/bin/env python3
"""Package the current reproduced Hyprland in a new complete Omarchy version."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.omarchy_image_update import repack
from tools.omarchy_rootfs import digest_file

BASE = ROOT / "build/deliverables/Omarchy-2026-10-07-arm64-rootfs"
REFERENCE = ROOT / "build/deliverables/Omarchy-2026-10-07-arm64-output-orientation-reference"
OUTPUT = ROOT / "build/deliverables/Omarchy-2026-10-07-arm64-output-orientation-rootfs"
OLD_ARCHIVE = "1c4bcab5564c613a3dcc40b564d76183431c70b0c76af2ecad6a8bc5ae2ad66e"
OLD_MANIFEST = "4dae31a22076512d40b8a839d8750b18874baa5dee0e090319d94b1fb81a0ac2"
PROVENANCE = "usr/share/loopy/omarchy-reference-provenance.json"


def main():
    if OUTPUT.exists() or OUTPUT.is_symlink():
        raise FileExistsError("completed or existing version preserved; inspect its receipt")
    old = json.loads((BASE / "receipt.json").read_text())
    verified = json.loads((ROOT / "docs/validation/2026-10-06-omarchy/rootfs-bytes-verified.json").read_text())
    lock = json.loads((ROOT / "third_party/omarchy.lock.json").read_text())
    reference = json.loads((REFERENCE / "receipt.json").read_text())
    if old["archive_sha256"] != OLD_ARCHIVE or old["manifest_sha256"] != OLD_MANIFEST \
            or old["packages"] != 921 or old["entries"] != 254715 \
            or verified["status"] != "all-rootfs-bytes-and-links-verified" \
            or verified["archive_sha256"] != OLD_ARCHIVE or verified["manifest_sha256"] != OLD_MANIFEST \
            or verified["original_manual_files"] != 51 or verified["original_qml_files"] != 119 \
            or reference["lock_sha256"] != digest_file(ROOT / "third_party/omarchy.lock.json") \
            or reference["build_exit"] != 0 or reference["architecture"] != "aarch64" \
            or lock["scope_counts"] != {"package_requests": 158, "manual_chapters": 51, "qml_files": 119}:
        raise ValueError("complete base/current reproduced binary evidence differs")
    prepared = ROOT / "build/omarchy-sources/hyprland-output-orientation"
    for name, expected in reference["source_files"].items():
        path = prepared / name
        if path.is_symlink() or not path.is_file() or digest_file(path) != expected:
            raise ValueError("reproduced compositor source changed: " + name)
    paths = {"Hyprland": "usr/bin/Hyprland", "hyprctl": "usr/bin/hyprctl"}
    for name in (*paths, "libaquamarine.so.0.15.1"):
        path, identity = REFERENCE / name, reference["files"][name]
        if path.is_symlink() or path.stat().st_size != identity["bytes"] or digest_file(path) != identity["sha256"]:
            raise ValueError("reproduced binary changed: " + name)
    manifest = json.loads((BASE / "manifest.json").read_text())["files"]
    if manifest["usr/lib/libaquamarine.so.0.15.1"]["sha256"] != reference["files"]["libaquamarine.so.0.15.1"]["sha256"]:
        raise ValueError("candidate requires a different Aquamarine ABI")
    if shutil.disk_usage(OUTPUT.parent).free < old["archive_bytes"] + 320 * 1024**2:
        raise ValueError("insufficient space for a separate whole-image version")
    print(json.dumps({"stage": "verified-current-source-and-binaries", "source_files": len(reference["source_files"]),
                      "preserved_original_packages": 921, "base_archive_sha256": OLD_ARCHIVE}), flush=True)
    from compression import zstd
    with tempfile.TemporaryDirectory(prefix="loopy-omarchy-public-provenance-") as temporary:
        original = None
        with zstd.open(BASE / "rootfs.tar.zst", "rb") as stream, tarfile.open(fileobj=stream, mode="r|") as archive:
            for member in archive:
                if member.name != PROVENANCE:
                    continue
                if not member.isfile() or member.size > 1024**2:
                    raise ValueError("bounded regular original provenance required")
                content = archive.extractfile(member).read()
                if hashlib.sha256(content).hexdigest() != manifest[PROVENANCE]["sha256"]:
                    raise ValueError("original provenance bytes differ")
                original = json.loads(content)
                break
        if original is None or original["original_requests"] != lock["requested"] \
                or original["user_home_imported"] or original["machine_private_data_imported"]:
            raise ValueError("original full-scope provenance differs")
        original.update(lock_sha256=digest_file(ROOT / "third_party/omarchy.lock.json"),
                        patched_binary_receipt_sha256=digest_file(REFERENCE / "receipt.json"),
                        base_archive_sha256=OLD_ARCHIVE, base_manifest_sha256=OLD_MANIFEST,
                        update_builder_sha256=digest_file(Path(__file__)),
                        image_repacker_sha256=digest_file(Path(__file__).with_name("omarchy_image_update.py")),
                        current_binary_files=reference["files"], current_hyprland_source_files=reference["source_files"])
        metadata = Path(temporary) / "provenance.json"
        metadata.write_text(json.dumps(original, indent=2) + "\n")
        replacements = {target: REFERENCE / name for name, target in paths.items()}
        replacements[PROVENANCE] = metadata
        result = repack(BASE, OUTPUT, replacements, expected_archive_sha256=OLD_ARCHIVE,
                        expected_manifest_sha256=OLD_MANIFEST,
                        progress=lambda count, total: print(json.dumps({"stage": "copying-complete-image",
                                                                       "entries": count, "total": total}), flush=True))
    print(json.dumps({k: v for k, v in result.items() if k != "package_names"}), flush=True)


if __name__ == "__main__":
    main()
