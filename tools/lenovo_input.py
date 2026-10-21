#!/usr/bin/env python3
"""Inspect or explicitly change four Lenovo TB570 OEM Win shortcuts, preserving originals."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile

KEYS = ("keyboard_combo_win_e", "keyboard_combo_win_i", "keyboard_combo_win_s", "keyboard_combo_win_number")
SETTINGS = ["/system/bin/settings", "--user", "0"]


class InputError(Exception):
    """An unsupported device, conflicting state, or failed settings command."""


class ADBRunner:
    def __init__(self, serial, adb="adb"):
        if not serial or "\0" in serial:
            raise InputError("An explicit ADB serial is required")
        self.serial, self.adb = serial, adb

    def shell(self, arguments):
        # adb shell joins its remote arguments. Quote each fixed command/value so
        # a saved Settings value remains data even if it contains shell syntax.
        command = [self.adb, "-s", self.serial, "shell", shlex.join(arguments)]
        try:
            result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise InputError(f"ADB command failed: {error}") from error
        if result.returncode:
            raise InputError(f"ADB command failed: {result.stderr.strip()[:500]}")
        return result.stdout


def read_settings(runner):
    settings = {key: {"present": False, "value": None} for key in KEYS}
    seen = set()
    for line in runner.shell(SETTINGS + ["list", "system"]).splitlines():
        key, separator, value = line.partition("=")
        if key not in KEYS or not separator:
            continue
        if key in seen or len(value.encode("utf-8")) > 4096 or "\0" in value:
            raise InputError(f"Cannot safely snapshot Settings row {key}")
        seen.add(key)
        settings[key] = {"present": True, "value": value}
    return settings


def inspect(runner):
    manufacturer = runner.shell(["/system/bin/getprop", "ro.product.manufacturer"]).strip()
    model = runner.shell(["/system/bin/getprop", "ro.product.model"]).strip()
    qemu = runner.shell(["/system/bin/getprop", "ro.kernel.qemu"]).strip()
    supported = (manufacturer.casefold() == "lenovo"
                 and re.fullmatch(r"(?:Lenovo )?TB570[A-Za-z0-9_-]*", model, re.IGNORECASE) is not None
                 and qemu in ("", "0"))
    return {"device": {"serial": runner.serial, "manufacturer": manufacturer, "model": model,
                       "qemu": qemu, "settings_user": 0},
            "supported": supported, "settings": read_settings(runner)}


def require_device(report):
    if not report["supported"]:
        raise InputError("Writes require a non-emulated Lenovo TB570 device")


def atomic_snapshot(path, snapshot):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".lenovo-input-", delete=False) as file:
            temporary = Path(file.name)
            json.dump(snapshot, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        # Link publishes a complete file atomically and refuses to replace originals.
        os.link(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as error:
        raise InputError(f"Snapshot not published; device unchanged: {error}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def disable(runner, snapshot_path, dry_run=False):
    current = inspect(runner)
    require_device(current)
    planned = [key for key in KEYS if current["settings"][key] != {"present": True, "value": "0"}]
    snapshot = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                "device": current["device"], "settings": current["settings"],
                "expected_disabled": "0"}
    if not dry_run:
        atomic_snapshot(snapshot_path, snapshot)
        for key in planned:
            if read_settings(runner)[key] != current["settings"][key]:
                raise InputError(f"Settings changed before disable: {key}; snapshot retained")
            runner.shell(SETTINGS + ["put", "system", key, "0"])
        if any(row != {"present": True, "value": "0"} for row in read_settings(runner).values()):
            raise InputError("Disable verification failed; snapshot retained for restore")
    return {"operation": "disable", "dry_run": dry_run, "device": current["device"],
            "snapshot": str(snapshot_path), "keys_to_change": planned}


def load_snapshot(path):
    path = Path(path)
    try:
        info = path.stat()
        if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_size > 64 * 1024:
            raise InputError("Snapshot must be a regular JSON file below 64KiB")
        with path.open("r", encoding="utf-8") as file:
            text = file.read(64 * 1024 + 1)
        if len(text.encode("utf-8")) > 64 * 1024:
            raise InputError("Snapshot exceeds 64KiB")
        snapshot = json.loads(text)
    except (OSError, ValueError) as error:
        raise InputError(f"Cannot read snapshot: {error}") from error
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1 or snapshot.get("expected_disabled") != "0":
        raise InputError("Unsupported snapshot schema")
    rows, device = snapshot.get("settings"), snapshot.get("device")
    if not isinstance(rows, dict) or set(rows) != set(KEYS) or not isinstance(device, dict) or device.get("settings_user") != 0:
        raise InputError("Snapshot must contain exactly the four owned Settings rows for user 0")
    for row in rows.values():
        if not isinstance(row, dict) or set(row) != {"present", "value"} or type(row["present"]) is not bool:
            raise InputError("Invalid Settings snapshot row")
        value = row["value"]
        if row["present"]:
            if not isinstance(value, str) or "\0" in value or "\n" in value or len(value.encode("utf-8")) > 4096:
                raise InputError("Invalid original Settings value")
        elif value is not None:
            raise InputError("An absent original row must have no value")
    return snapshot


def restore(runner, snapshot_path, dry_run=False):
    current = inspect(runner)
    require_device(current)
    snapshot = load_snapshot(snapshot_path)
    for field in ("serial", "manufacturer", "model", "settings_user"):
        if snapshot["device"].get(field) != current["device"].get(field):
            raise InputError("Snapshot belongs to a different device or Settings user")
    original = snapshot["settings"]
    planned = []
    # Preflight every row first: a later conflict cannot cause partial restoration.
    for key in KEYS:
        row = current["settings"][key]
        if row == original[key]:
            continue
        if row != {"present": True, "value": "0"}:
            raise InputError(f"Restore conflict: {key} changed after disable; device unchanged")
        planned.append(key)
    if not dry_run:
        for key in planned:
            if read_settings(runner)[key] != {"present": True, "value": "0"}:
                raise InputError(f"Restore conflict: {key} changed during restore")
            row = original[key]
            args = ["put", "system", key, row["value"]] if row["present"] else ["delete", "system", key]
            runner.shell(SETTINGS + args)
        if read_settings(runner) != original:
            raise InputError("Restore verification failed; snapshot retained")
    return {"operation": "restore", "dry_run": dry_run, "device": current["device"],
            "snapshot": str(snapshot_path), "keys_to_change": planned}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "disable", "restore"), nargs="?", default="inspect")
    parser.add_argument("--serial", required=True, help="Explicit physical ADB serial; never inferred")
    parser.add_argument("--snapshot", type=Path, help="Original-state JSON, e.g. build/lenovo-input/device.json")
    parser.add_argument("--dry-run", action="store_true", help="Read actual state and show the plan without writing")
    parser.add_argument("--adb", default="adb", help="ADB executable")
    args = parser.parse_args(argv)
    if args.command != "inspect" and args.snapshot is None:
        parser.error("disable/restore require an explicit --snapshot path")
    try:
        runner = ADBRunner(args.serial, args.adb)
        result = inspect(runner) if args.command == "inspect" else (
            disable(runner, args.snapshot, args.dry_run) if args.command == "disable"
            else restore(runner, args.snapshot, args.dry_run))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except InputError as error:
        print(f"lenovo-input: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
