#!/usr/bin/env python3
"""Install a verified explicit profile only in the named Arch ARM reference VM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.prepare_omarchy import audit, fetch_transaction, load_lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transaction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    hostname = Path("/etc/hostname")
    if ROOT != Path("/workspace") or os.getuid() != 0 or os.uname().machine != "aarch64" \
            or not hostname.is_file() or hostname.read_text().strip() != "loopy-omarchy-build":
        parser.error("requires root in the named scoped Arch ARM reference VM")
    if args.output.exists() or args.output.is_symlink():
        parser.error("refuse to overwrite an installation receipt")
    prepared = json.loads(args.transaction.read_text())
    if prepared.get("status") != "packages-verified" or prepared.get("unresolved"):
        parser.error("requires a complete verified package transaction")
    lock_path = ROOT / "third_party/omarchy.lock.json"
    lock = load_lock(lock_path)
    cache = ROOT / "build/omarchy-sources"
    transaction = audit(lock, cache, profile=prepared["profile"])
    if transaction["unresolved"] or transaction["packages"] != prepared["packages"] \
            or transaction["requested"] != prepared["requested"]:
        parser.error("prepared transaction differs from the exact current lock")
    signatures = fetch_transaction(transaction, cache)
    paths = [str(cache / "packages" / item["filename"]) for item in transaction["packages"]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    log_path = args.output.with_suffix(".log")
    if log_path.exists():
        parser.error("refuse to overwrite an installation log")
    with log_path.open("x") as log:
        subprocess.run(["pacman", "-U", "--needed", "--noconfirm", *paths],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    installed = []
    for item in transaction["packages"]:
        identity = subprocess.check_output(["pacman", "-Q", item["name"]], text=True).strip()
        if identity != item["name"] + " " + item["version"]:
            raise RuntimeError("installed package version differs from the verified transaction")
        installed.append(identity)
    receipt = {"status": "installed-in-reference-vm", "profile": prepared["profile"],
               "uid": os.getuid(), "packages": installed, "verified_signatures": signatures,
               "transaction_sha256": hashlib.sha256(args.transaction.read_bytes()).hexdigest(),
               "lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
               "installer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "physical_device": False, "hardware_gpu": False, "omarchy_support_complete": False}
    with args.output.open("x") as output:
        output.write(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "profile": receipt["profile"], "packages": len(installed)}))


if __name__ == "__main__":
    main()
