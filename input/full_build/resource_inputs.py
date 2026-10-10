#!/usr/bin/env python3
"""Retain the exact uncompiled inputs distributed inside runtime AAR dependencies."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import zipfile

HERE = Path(__file__).resolve().parent


def runtime_module():
    spec = importlib.util.spec_from_file_location("runtime_resource_sources", HERE / "runtime_sources.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def export_aar_inputs(path, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    files, gaps, excluded = {}, [], []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate-aar-input")
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            name = entry.filename
            p = PurePosixPath(name)
            if (p.is_absolute() or ".." in p.parts or "\\" in name or "\x00" in name
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000
                    or p.suffix.lower() in (".jks", ".keystore", ".key", ".p12", ".pfx")):
                raise ValueError("unsafe-aar-input: " + name)
            data = archive.read(entry)
            reason = None
            if p.suffix.lower() in (".so", ".a", ".dll", ".dylib"):
                reason = "native-source-required"
            elif p.suffix.lower() in (".flat", ".arsc") or (p.suffix.lower() == ".xml" and data.startswith(b"\x03\x00\x08\x00")):
                reason = "preferred-resource-source-required"
            elif p.suffix.lower() in (".jar", ".class", ".dex"):
                if name not in ("classes.jar", "lint.jar"):
                    reason = "bundled-code-source-required"
                excluded.append(name)
                if reason is None:
                    continue
            if reason:
                gaps.append({"entry": name, "reason": reason, "sha256": hashlib.sha256(data).hexdigest()})
                continue
            target = destination.joinpath(*p.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            files[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    return {"files": files, "gaps": gaps, "excludedCompiledEntries": excluded}


def prepare(work):
    runtime = runtime_module()
    work = Path(work).resolve()
    base = work / "runtime-source"
    value = json.loads((base / "manifest.json").read_text())
    if value["status"] != "COMPLETE":
        raise ValueError("complete-runtime-java-source-manifest-required")
    if value.get("resourceInputsAudited"):
        raise ValueError("runtime-resource-inputs-already-prepared")
    cache = work / "gradle/caches/modules-2/files-2.1"
    gaps, aar_count, total_files = [], 0, 0
    for row in value["dependencies"]:
        folder = base / row["group"] / row["artifact"] / row["version"]
        module_dir = cache / row["group"] / row["artifact"] / row["version"]
        modules = sorted(module_dir.glob("*/*.module"))
        if len(modules) > 1:
            raise ValueError("multiple-runtime-module-metadata-files")
        if modules:
            data = modules[0].read_bytes()
            (folder / "artifact.module").write_bytes(data)
            row["moduleMetadata"] = {"path": "artifact.module", "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data), "url": runtime.source_url(row).removesuffix("-sources.jar") + ".module"}
        if row["extension"] != "aar":
            continue
        artifact = runtime.cached_artifact(cache, row, ".aar")
        report = export_aar_inputs(artifact, folder / "resource-inputs")
        row["resourceInputs"] = report
        row["resourceInputs"]["sourceAARSHA256"] = row["sha256"]
        row["resourceInputs"]["sourceAARURL"] = runtime.source_url(row).removesuffix("-sources.jar") + ".aar"
        aar_count += 1
        total_files += len(report["files"])
        gaps.extend({"coordinate": row["group"] + ":" + row["artifact"] + ":" + row["version"], **gap}
                    for gap in report["gaps"])
    value.update(resourceInputsAudited=True, runtimeAARs=aar_count, runtimeResourceInputFiles=total_files,
                 resourceInputGaps=gaps, resourceInputDriverSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 status="COMPLETE" if not gaps else "MISSING")
    (base / "manifest.json").write_text(json.dumps(value, indent=2) + "\n")
    return {"status": value["status"], "runtimeAARs": aar_count, "resourceInputFiles": total_files,
            "moduleMetadataFiles": sum("moduleMetadata" in row for row in value["dependencies"]), "gaps": gaps,
            "manifestSHA256": hashlib.sha256((base / "manifest.json").read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-dir", type=Path, required=True)
    args = parser.parse_args()
    value = prepare(args.prepared_dir)
    print(json.dumps(value, indent=2))
    return 0 if value["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
