#!/usr/bin/env python3
"""Build isolated refresh components; never promote APK or image inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "build/omarchy-refresh-20261008"
OLD_SOURCE = Path("/var/tmp/loopy-hyprland-reproduced-source")
OLD_BUILD = Path("/var/tmp/loopy-hyprland-reproduced-build")
HL_BUILD = Path("/var/tmp/loopy-hyprland-parent-refresh-20261008")
AQ_BUILD = Path("/var/tmp/loopy-aquamarine-parent-refresh-20261008")
AQ_SOURCE = Path("/var/tmp/loopy-aquamarine-parent-refresh-source-20261008")
HL_SOURCE = Path("/var/tmp/loopy-hyprland-parent-refresh-source-20261008")
BASE_HYPRLAND = "7d65f7ea3c4c53f624b2dc43928c3b7271f1c90ee1d65ae232ce99190e00a600"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_tree(directory, files):
    if directory.is_symlink() or not directory.is_dir() or not 1 <= len(files) <= 8192:
        raise ValueError("bounded regular source directory required")
    for name, expected in files.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or str(relative) != name:
            raise ValueError("source inventory must remain relative")
        path = directory / relative
        if path.is_symlink() or not path.is_file() or path.resolve() != directory.resolve() / relative or digest(path) != expected:
            raise ValueError("source identity differs: " + name)


def prepare_candidate(destination):
    sys.path.insert(0, str(ROOT))
    from tools.build_omarchy_graphics import prepare as aq_prepare, apply_guarded_patch
    from tools.build_hyprland_rootless import prepare as hl_prepare
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("completed candidate preserved")
    with tempfile.TemporaryDirectory(prefix=".refresh-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        for component, prepare in (("aquamarine", aq_prepare), ("hyprland", hl_prepare)):
            source = stage / (component + "-source")
            data = prepare(ROOT / "third_party/omarchy.lock.json", ROOT / "build/omarchy-sources", source)
            patch = ROOT / ("native/omarchy/patches/" + component + "-parent-refresh.patch")
            metadata = patch.with_suffix(".json")
            item = json.loads(metadata.read_text())
            apply_guarded_patch(source, patch, item, project=component)
            item.update(metadata_file=str(metadata.relative_to(ROOT)), metadata_sha256=digest(metadata), patch=str(patch.relative_to(ROOT)))
            data["patches"].append(item)
            data["patches_applied"] = len(data["patches"])
            record = source / "loopy-source-receipt.json"
            data["source_files"] = {str(p.relative_to(source)): digest(p) for p in sorted(source.rglob("*")) if p.is_file() and p != record}
            record.write_text(json.dumps(data, indent=2) + "\n")
        stage.rename(destination)
    return {"status": "source-prepared", "output": str(destination)}


def vm_guard():
    if ROOT != Path("/workspace") or os.uname().machine != "aarch64" or os.getuid() != 501 \
            or Path("/etc/hostname").read_text().strip() != "loopy-omarchy-build":
        raise ValueError("named owned ARM VM and ordinary uid501 required")


def receipt(component, commands, private_source, build, binary_names, extra=None):
    source = CANDIDATE / (component + "-source")
    source_record = source / "loopy-source-receipt.json"
    data = json.loads(source_record.read_text())
    verify_tree(private_source, data["source_files"])
    # Generated protocols are build inputs too; record their actual compiled bytes.
    generated = 0
    for path in sorted(private_source.rglob("*")):
        if path.is_symlink():
            raise ValueError("compiled source tree contains a symlink")
        if not path.is_file() or path.name == "loopy-source-receipt.json":
            continue
        relative = path.relative_to(private_source)
        destination = source / relative
        if destination.exists():
            if digest(destination) != digest(path):
                raise ValueError("compiled source changed after preparation: " + str(relative))
        else:
            generated += 1
            if generated > 512 or relative.parts[0] != "protocols" or path.suffix not in (".cpp", ".hpp") or path.stat().st_size > 4 * 1024**2:
                raise ValueError("unlisted compiled input is not a bounded generated protocol")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    data["source_files"] = {str(p.relative_to(source)): digest(p) for p in sorted(source.rglob("*"))
                            if p.is_file() and p != source_record}
    source_record.write_text(json.dumps(data, indent=2) + "\n")
    binaries = {}
    target = CANDIDATE / "components"
    target.mkdir(exist_ok=True)
    for name, relative in binary_names.items():
        path = build / relative
        destination = target / name
        if destination.exists():
            raise FileExistsError("completed component preserved: " + str(destination))
        shutil.copyfile(path, destination)
        destination.chmod(0o755)
        binaries[name] = {"path": str(destination.relative_to(ROOT)), "sha256": digest(destination),
                          "bytes": destination.stat().st_size}
    result = dict(data, status="compiled-in-reference-vm", architecture="aarch64", build_exit=0,
                  uid=os.getuid(), producer_sha256=digest(__file__), build_commands=commands,
                  binaries=binaries, physical_device=False, hardware_gpu=False, visual_acceptance=False,
                  compiled_source=str(private_source), compiled_build=str(build), recorded_at=time.time())
    result.update(extra or {})
    path = CANDIDATE / (component + "-build-receipt.json")
    with path.open("x") as output:
        output.write(json.dumps(result, indent=2) + "\n")
    return result


def aquamarine_commands():
    source = AQ_SOURCE
    return source, [
        ["cmake", "-S", str(source), "-B", str(AQ_BUILD), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"],
        ["cmake", "--build", str(AQ_BUILD), "--target", "aquamarine", "--parallel", "2"],
    ]


def build_hyprland():
    source = CANDIDATE / "hyprland-source"
    data = json.loads((source / "loopy-source-receipt.json").read_text())
    baseline = json.loads((ROOT / "build/deliverables/Omarchy-2026-10-07-arm64-cursor-resolve-reference/build-receipt.json").read_text())
    verify_tree(OLD_SOURCE, baseline["source_files"])
    verify_tree(source, data["source_files"])
    differences = [name for name, value in data["source_files"].items() if baseline["source_files"].get(name) != value]
    if differences != ["src/output/Monitor.cpp"] or digest(OLD_BUILD / "Hyprland") != BASE_HYPRLAND:
        raise ValueError("isolated incremental build requires exact one-file baseline")
    if not HL_BUILD.exists():
        shutil.copytree(OLD_BUILD, HL_BUILD, symlinks=True)
    link = shlex.split(subprocess.check_output(["ninja", "-t", "commands", "Hyprland"], cwd=OLD_BUILD, text=True).splitlines()[-1])
    if link[:2] != [":", "&&"] or link[-2:] != ["&&", ":"]:
        raise ValueError("unexpected captured link command")
    link = link[2:-2]
    subprocess.run(link, cwd=HL_BUILD, check=True)
    if digest(HL_BUILD / "Hyprland") != BASE_HYPRLAND:
        raise ValueError("copied object archive does not reproduce exact baseline")
    archive_before = digest(HL_BUILD / "libhyprland_lib.a")
    private = HL_SOURCE
    if private.exists():
        verify_tree(private, data["source_files"])
    else:
        shutil.copytree(source, private)
    # The reference compiler generated protocol headers outside its source receipt.
    # Copy only that bounded generated inventory into the new private source tree.
    generated = {}
    for path in sorted((OLD_SOURCE / "protocols").iterdir()):
        relative = str(path.relative_to(OLD_SOURCE))
        if relative in baseline["source_files"]:
            continue
        if path.is_symlink() or not path.is_file() or path.suffix not in (".hpp", ".cpp") or path.stat().st_size > 4 * 1024**2:
            raise ValueError("unexpected generated baseline protocol input")
        destination = private / relative
        if destination.exists() and digest(destination) != digest(path):
            raise ValueError("generated protocol input changed")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        generated[relative] = digest(path)
    records = json.loads((OLD_BUILD / "compile_commands.json").read_text())
    matches = [record for record in records if record["file"] == str(OLD_SOURCE / "src/output/Monitor.cpp")]
    if len(matches) != 1:
        raise ValueError("one captured Monitor compile command required")
    compile_command = shlex.split(matches[0]["command"])
    compile_command = [part.replace(str(OLD_SOURCE), str(private)) for part in compile_command]
    pch = compile_command.index("-include")
    del compile_command[pch:pch + 2]
    compile_command[compile_command.index("-c") + 1] = str(private / "src/output/Monitor.cpp")
    # Compile the changed translation unit fresh; copied PCH paths cannot mix trees.
    object_file = matches[0]["output"].removeprefix(str(OLD_BUILD) + "/")
    commands = [compile_command, ["ar", "r", "libhyprland_lib.a", object_file], link]
    log_path = CANDIDATE / "hyprland-build.log"
    if log_path.exists():
        for attempt in range(1, 10):
            backup = CANDIDATE / ("hyprland-build-attempt%02d.log" % attempt)
            if not backup.exists():
                log_path.rename(backup)
                break
        else:
            raise ValueError("bounded build attempts exhausted")
    with log_path.open("x") as log:
        for command in commands:
            subprocess.run(command, cwd=HL_BUILD, stdout=log, stderr=subprocess.STDOUT, check=True)
    if digest(HL_BUILD / "Hyprland") == BASE_HYPRLAND:
        raise ValueError("candidate did not change baseline")
    verify_tree(OLD_SOURCE, baseline["source_files"])
    return receipt("hyprland", commands, private, HL_BUILD, {"Hyprland": "Hyprland"},
                   {"incremental": True, "baseline_relink_sha256": BASE_HYPRLAND,
                    "reused_archive_sha256": archive_before,
                    "baseline_build_receipt_sha256": digest(ROOT / "build/deliverables/Omarchy-2026-10-07-arm64-cursor-resolve-reference/build-receipt.json"),
                    "captured_compile_commands_sha256": digest(OLD_BUILD / "compile_commands.json")})


def main():
    global CANDIDATE, HL_BUILD, AQ_BUILD, AQ_SOURCE, HL_SOURCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=("aquamarine", "hyprland"))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--output", type=Path, default=CANDIDATE)
    parser.add_argument("--record-existing-aquamarine", action="store_true",
                        help="record the separately completed exact fresh CMake build")
    args = parser.parse_args()
    candidate = args.output.absolute()
    if candidate.parent != ROOT / "build" or candidate.parent.resolve() != ROOT.resolve() / "build" or \
            not candidate.name.startswith("omarchy-refresh-") or not 1 <= len(candidate.name) <= 64 or candidate.is_symlink():
        parser.error("separate regular workspace build/omarchy-refresh-* directory required")
    if candidate != CANDIDATE:
        HL_BUILD = Path("/var/tmp/loopy-hyprland-" + candidate.name)
        AQ_BUILD = Path("/var/tmp/loopy-aquamarine-" + candidate.name)
        HL_SOURCE = HL_BUILD.with_name(HL_BUILD.name + "-source")
        AQ_SOURCE = AQ_BUILD.with_name(AQ_BUILD.name + "-source")
        CANDIDATE = candidate
    if args.prepare_only:
        if args.component or args.record_existing_aquamarine:
            parser.error("source preparation cannot build or record a component")
        print(json.dumps(prepare_candidate(candidate)))
        return
    if not args.component:
        parser.error("--component required for a VM build")
    vm_guard()
    if args.component == "hyprland":
        if args.record_existing_aquamarine:
            parser.error("Aquamarine recording option cannot apply to Hyprland")
        result = build_hyprland()
    else:
        private, commands = aquamarine_commands()
        if not args.record_existing_aquamarine:
            if private.exists() or AQ_BUILD.exists():
                raise FileExistsError("fresh Aquamarine source/build required")
            shutil.copytree(CANDIDATE / "aquamarine-source", private)
            with (CANDIDATE / "aquamarine-build.log").open("x") as log:
                for command in commands:
                    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        result = receipt("aquamarine", commands, private, AQ_BUILD,
                         {"libaquamarine.so.0.15.1": "libaquamarine.so.0.15.1"})
    print(json.dumps({key: result[key] for key in ("status", "binaries", "physical_device")}))


if __name__ == "__main__":
    main()
