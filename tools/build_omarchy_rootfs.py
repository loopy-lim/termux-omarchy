#!/usr/bin/env python3
"""Package the complete verified Arch runtime in the scoped reference VM only."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.omarchy_rootfs import bundle, checked_path, digest_file
from tools.prepare_omarchy import load_lock, verify_file

PUBLIC_SETUP = (
    "etc/ld.so.cache", "var/lib/pacman/local/ALPM_DB_VERSION",
    "etc/ca-certificates/extracted/tls-ca-bundle.pem",
    "usr/share/glib-2.0/schemas/gschemas.compiled",
    "usr/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache",
    "usr/lib/gtk-3.0/3.0.0/immodules.cache", "usr/lib/gtk-4.0/4.0.0/immodules.cache",
    "usr/share/applications/mimeinfo.cache",
)


def package_setup_files(root, packages):
    root, files = Path(root), {}
    def add(path):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024**2:
            raise ValueError("public setup input is not a bounded regular file")
        relative = path.relative_to(root)
        for parent in relative.parents:
            if (root / parent).is_symlink():
                raise ValueError("public setup path redirects outside its scope")
        files[relative.as_posix()] = path
    for package in packages:
        name = checked_path(package["name"] + "-" + package["version"])
        if "/" in name:
            raise ValueError("invalid installed package path")
        directory = root / "var/lib/pacman/local" / name
        desc = directory / "desc"
        if not desc.is_file() or desc.is_symlink() or desc.stat().st_size > 1024**2:
            raise ValueError("missing installed package metadata")
        fields = desc.read_text().split("\n\n")
        values = {lines[0]: lines[1:] for field in fields if (lines := field.splitlines())}
        if values.get("%NAME%") != [package["name"]] or values.get("%VERSION%") != [package["version"]]:
            raise ValueError("installed package metadata identity differs")
        for name in ("desc", "files", "mtree"):
            add(directory / name)
        if (directory / "install").exists():
            add(directory / "install")
    for name in PUBLIC_SETUP:
        path = root / name
        if path.exists():
            add(path)
    icons = root / "usr/share/icons"
    if icons.is_dir():
        for path in sorted(icons.glob("*/icon-theme.cache")):
            add(path)
    mime = root / "usr/share/mime"
    if mime.is_dir():
        for path in sorted(mime.rglob("*")):
            if path.is_file() or path.is_symlink():
                add(path)
    if sum(path.stat().st_size for path in files.values()) > 128 * 1024**2:
        raise ValueError("public package setup metadata exceeds its budget")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transaction", type=Path, required=True)
    parser.add_argument("--installed", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    hostname = Path("/etc/hostname")
    if ROOT != Path("/workspace") or os.uname().machine != "aarch64" or os.getuid() == 0 \
            or not hostname.is_file() or hostname.read_text().strip() != "loopy-omarchy-build":
        parser.error("requires ordinary user in the named scoped Arch ARM reference VM")
    output = args.output_directory
    if output.parent != ROOT / "build/deliverables" or output.exists() or output.is_symlink():
        parser.error("requires a new, separate reference deliverable directory")
    lock_path = ROOT / "third_party/omarchy.lock.json"
    lock = load_lock(lock_path)
    prepared, installed = json.loads(args.transaction.read_text()), json.loads(args.installed.read_text())
    if prepared.get("status") != "packages-verified" or prepared.get("profile") != "runtime" \
            or prepared.get("architecture") != "aarch64" or prepared.get("unresolved") \
            or prepared.get("requested") != lock["profiles"]["runtime"] \
            or prepared.get("original_request_count") != len(lock["requested"]) \
            or not set(lock["requested"]) <= set(prepared["requested"]):
        parser.error("requires the complete verified original-plus-base runtime profile")
    identities = [p["name"] + " " + p["version"] for p in prepared["packages"]]
    if installed.get("status") != "installed-in-reference-vm" or installed.get("profile") != "runtime" \
            or installed.get("packages") != identities \
            or installed.get("lock_sha256") != digest_file(lock_path) \
            or installed.get("transaction_sha256") != digest_file(args.transaction):
        parser.error("installed reference transaction identity differs")
    actual = set(subprocess.check_output(["pacman", "-Q"], text=True).splitlines())
    if not set(identities) <= actual:
        parser.error("live installed package versions differ")
    cache = ROOT / "build/omarchy-sources"
    source = lock["omarchy_source"]
    archive = cache / source["archive_file"]
    verify_file(archive, source["archive_sha256"], source["archive_bytes"])
    extras = package_setup_files(Path("/"), prepared["packages"])
    reference = ROOT / "build/deliverables/Omarchy-2026-10-07-arm64-reference"
    binary_receipt = json.loads((reference / "receipt.json").read_text())
    patches = {"Hyprland": "usr/bin/Hyprland", "hyprctl": "usr/bin/hyprctl",
               "libaquamarine.so.0.15.1": "usr/lib/libaquamarine.so.0.15.1"}
    for name, destination in patches.items():
        path, identity = reference / name, binary_receipt["files"][name]
        verify_file(path, identity["sha256"], identity["bytes"])
        extras[destination] = path
    for path in sorted((reference / "licenses").rglob("*")):
        if path.is_file():
            extras["usr/share/licenses/loopy-omarchy-reference/" + path.relative_to(reference / "licenses").as_posix()] = path
    reserve = prepared["download_bytes"] + 256 * 1024**2
    if shutil.disk_usage(output.parent).free < reserve:
        parser.error("insufficient space for a separate compressed complete runtime")
    provenance = {"original_requests": lock["requested"], "original_request_count": len(lock["requested"]),
                  "lock_sha256": digest_file(lock_path), "transaction_sha256": digest_file(args.transaction),
                  "installed_receipt_sha256": digest_file(args.installed), "source_archive_sha256": source["archive_sha256"],
                  "patched_binary_receipt_sha256": digest_file(reference / "receipt.json"),
                  "patched_paths": patches, "public_setup_files": sorted(extras),
                  "user_home_imported": False, "machine_private_data_imported": False,
                  "builder_sha256": digest_file(Path(__file__)),
                  "archive_builder_sha256": digest_file(Path(__file__).with_name("omarchy_rootfs.py"))}
    def progress(index, total, size, entries):
        if index == 1 or index % 25 == 0 or index == total:
            print(json.dumps({"packages": index, "total": total, "materialized_bytes": size, "entries": entries}), flush=True)
    with tempfile.TemporaryDirectory(prefix="loopy-rootfs-public-") as temporary:
        record = Path(temporary) / "provenance.json"
        record.write_text(json.dumps(provenance, indent=2) + "\n")
        extras["usr/share/loopy/omarchy-reference-provenance.json"] = record
        result = bundle(output, prepared["packages"], cache / "packages", extras=extras, replace=set(extras),
                        source={"path": archive, "prefix": ("omarchy-" + source["commit"], "usr/share/omarchy")},
                        progress=progress)
    print(json.dumps({k: v for k, v in result.items() if k != "package_names"}), flush=True)


if __name__ == "__main__":
    main()
