#!/usr/bin/env python3
"""Reproduce the pinned Hyprland candidate; compilation is scoped ARM VM evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.build_omarchy_graphics import apply_guarded_patch, extract_source
from tools.prepare_omarchy import load_lock, relative, verify_file

DEPENDENCIES = {
    "stephenberry/glaze": "subprojects/loopy-glaze",
    "canihavesomecoffee/udis86": "subprojects/udis86",
    "hyprwm/hyprland-protocols": "subprojects/hyprland-protocols",
}


def archive_for(cache, identity):
    commit, repo = identity["commit"], identity["repo"]
    if not re.fullmatch("[0-9a-f]{40}", commit) or identity["archive_url"] != \
            "https://codeload.github.com/" + repo + "/tar.gz/" + commit:
        raise ValueError("Requires an immutable official source archive")
    size = identity.get("archive_bytes")
    if not isinstance(size, int) or not 0 < size <= 64 * 1024**2:
        raise ValueError("Source archive requires a bounded size")
    archive = cache / (repo.rsplit("/", 1)[1].lower() + "-" + commit + ".tar.gz")
    verify_file(archive, identity["archive_sha256"], size)
    return archive


def prepare(lock_path, cache, destination):
    lock_path, cache, destination = Path(lock_path), Path(cache), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Refuse to overwrite existing candidate")
    lock = load_lock(lock_path)
    sources = [s for s in lock["graphics_sources"] if s["repo"] == "hyprwm/Hyprland"]
    if len(sources) != 1 or not lock.get("hyprland_patches"):
        raise ValueError("Hyprland requires one immutable source and guarded patches")
    upstream = sources[0]
    archive = archive_for(cache, upstream)
    gitlinks = {entry["path"]: entry["sha"] for entry in upstream["gitlinks"]}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".hl-", dir=destination.parent) as temporary:
        candidate = Path(temporary) / "source"
        extract_source(archive, candidate, upstream["commit"], project="Hyprland")
        inputs = {}
        for entry in lock["hyprland_patches"]:
            metadata_path = ROOT / relative(entry["metadata_file"])
            verify_file(metadata_path, entry["metadata_sha256"])
            metadata = json.loads(metadata_path.read_text())
            if entry["upstream_commit"] != upstream["commit"] or \
                    metadata["upstream_commit"] != upstream["commit"]:
                raise ValueError("Patch upstream mismatch")
            apply_guarded_patch(candidate, ROOT / relative(entry["patch"]), metadata, project="hyprland")
            for identity in metadata["build_inputs"]:
                repo = identity["repo"]
                if repo not in DEPENDENCIES or repo in inputs:
                    raise ValueError("Unsupported or duplicate build dependency")
                target = candidate / DEPENDENCIES[repo]
                if repo == "stephenberry/glaze":
                    if identity.get("tag") != "v7.2.0":
                        raise ValueError("Requires upstream compatible Glaze 7.2.0")
                elif gitlinks.get(DEPENDENCIES[repo]) != identity["commit"]:
                    raise ValueError("Dependency differs from the exact upstream gitlink")
                if target.is_dir() and not target.is_symlink() and not any(target.iterdir()):
                    target.rmdir()
                target.parent.mkdir(parents=True, exist_ok=True)
                extract_source(archive_for(cache, identity), target, identity["commit"],
                               project=repo.rsplit("/", 1)[1])
                if not (target / "LICENSE").is_file():
                    raise ValueError("Missing build dependency license")
                inputs[repo] = identity
        if set(inputs) != set(DEPENDENCIES):
            raise ValueError("Missing exact Hyprland build dependencies")
        receipt = {"architecture": "aarch64", "upstream_commit": upstream["commit"],
                   "upstream": upstream, "lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
                   "patches_applied": len(lock["hyprland_patches"]), "patches": lock["hyprland_patches"],
                   "build_inputs": list(inputs.values()), "status": "source-prepared",
                   "omarchy_support_complete": False,
                   "source_files": {str(p.relative_to(candidate)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted(candidate.rglob("*")) if p.is_file()}}
        (candidate / "loopy-source-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        candidate.rename(destination)
    return receipt


def validate_build_paths(output, build):
    if os.getuid() == 0 or os.uname().sysname != "Linux" or os.uname().machine != "aarch64" \
            or ROOT != Path("/workspace"):
        raise ValueError("Compilation requires ordinary user in the scoped ARM VM")
    for path in (output, build):
        if path.parent != Path("/var/tmp") or not path.name.startswith("loopy-hyprland-") \
                or path.exists() or path.is_symlink():
            raise ValueError("Requires fresh private Linux filesystem source/build directories")
    if output == build:
        raise ValueError("Source and build directories must differ")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=ROOT / "build/omarchy-sources")
    parser.add_argument("--build", type=Path, help="optional fresh dedicated ARM VM build directory")
    args = parser.parse_args()
    if args.build:
        validate_build_paths(args.output, args.build)
    receipt = prepare(ROOT / "third_party/omarchy.lock.json", args.cache, args.output)
    if args.build:
        environment = dict(os.environ, GIT_COMMIT_HASH=receipt["upstream_commit"],
                           GIT_BRANCH="loopy-shm", GIT_DIRTY="dirty", GIT_TAG="v0.56.2-loopy-shm")
        commands = [
            ["cmake", "-S", str(args.output), "-B", str(args.build), "-G", "Ninja",
             "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_CXX_SCAN_FOR_MODULES=OFF",
             "-DFETCHCONTENT_SOURCE_DIR_GLAZE=" + str(args.output / DEPENDENCIES["stephenberry/glaze"])],
            ["cmake", "--build", str(args.build), "--target", "Hyprland", "hyprctl", "--parallel", "2"],
        ]
        for command in commands:
            subprocess.run(command, check=True, env=environment)
        binaries = {name: args.build / path for name, path in
                    (("Hyprland", "Hyprland"), ("hyprctl", "hyprctl/hyprctl"))}
        receipt.update(status="compiled-in-reference-vm", uid=os.getuid(), build_commands=commands,
                       binaries={name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                                 for name, path in binaries.items()})
        (args.output / "loopy-build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "upstream_commit", "patches_applied", "omarchy_support_complete")}))


if __name__ == "__main__":
    main()
