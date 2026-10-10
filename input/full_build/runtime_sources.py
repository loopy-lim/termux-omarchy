#!/usr/bin/env python3
"""Resolve actual app/loader runtime artifacts and fetch their official source JARs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent


def driver_module():
    spec = importlib.util.spec_from_file_location("runtime_source_driver", HERE / "driver.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def source_url(row):
    if any(not re.fullmatch(r"[A-Za-z0-9._-]+", row[key]) for key in ("group", "artifact", "version")):
        raise ValueError("unsafe-runtime-coordinate")
    base = ("https://dl.google.com/dl/android/maven2/" if row["group"].startswith("androidx.")
            else "https://repo.maven.apache.org/maven2/")
    coordinate = row["group"].replace(".", "/") + "/" + row["artifact"] + "/" + row["version"] + "/"
    return base + coordinate + row["artifact"] + "-" + row["version"] + "-sources.jar"


def pom_licenses(data):
    root = ET.fromstring(data)
    return [{"name": (entry.findtext("{*}name") or "").strip(),
             "url": (entry.findtext("{*}url") or "").strip()}
            for entry in root.findall("{*}licenses/{*}license")]


def inspect_source_jar(path, *, allow_empty=False):
    source_files, legal_files = 0, []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate-runtime-source-member")
        for entry in archive.infolist():
            name = entry.filename.rstrip("/")
            p = PurePosixPath(name)
            if (p.is_absolute() or ".." in p.parts or "\\" in name or "\x00" in name
                    or p.suffix.lower() in (".class", ".dex", ".apk", ".so", ".jks", ".keystore", ".key", ".p12", ".pfx")
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("unsafe-runtime-source-member: " + name)
            if entry.is_dir():
                continue
            if p.suffix in (".java", ".kt", ".kts", ".scala", ".c", ".h", ".cpp"):
                source_files += 1
            if re.fullmatch(r"(license|notice|copying|copyright)([._-].*)?", p.name, re.I):
                legal_files.append(name)
        if not source_files and not allow_empty:
            raise ValueError("runtime-source-code-missing")
        if archive.testzip() is not None:
            raise ValueError("runtime-source-jar-corrupt")
    return {"sourceFiles": source_files, "embeddedLegalFiles": legal_files}


def cached_artifact(base, row, suffix):
    directory = base / row["group"] / row["artifact"] / row["version"]
    paths = sorted(directory.glob("*/*" + suffix))
    if suffix != ".pom":
        paths = [p for p in paths if hashlib.sha256(p.read_bytes()).hexdigest() == row["sha256"]]
    if len(paths) != 1 or paths[0].is_symlink():
        raise ValueError("exact-cached-runtime-artifact-required: " + str(directory.name) + suffix)
    return paths[0]


def resolved_pom_licenses(data, cache, destination):
    parents, visited = [], set()
    licenses = pom_licenses(data)
    while not licenses and len(parents) < 8:
        parent = ET.fromstring(data).find("{*}parent")
        if parent is None:
            break
        row = {key: (parent.findtext("{*}" + field) or "").strip()
               for key, field in (("group", "groupId"), ("artifact", "artifactId"), ("version", "version"))}
        url = source_url(row).removesuffix("-sources.jar") + ".pom"
        coordinate = row["group"] + ":" + row["artifact"] + ":" + row["version"]
        if coordinate in visited:
            raise ValueError("runtime-license-parent-cycle")
        visited.add(coordinate)
        data = cached_artifact(cache, row, ".pom").read_bytes()
        relative = "license-parent-" + str(len(parents) + 1) + ".pom"
        (destination / relative).write_bytes(data)
        parents.append({"coordinate": coordinate, "pomURL": url, "pomPath": relative,
                        "pomSHA256": hashlib.sha256(data).hexdigest()})
        licenses = pom_licenses(data)
    return licenses, parents


def artifact_has_code(path):
    with zipfile.ZipFile(path) as archive:
        if any(name.endswith(".class") for name in archive.namelist()):
            return True
        if "classes.jar" in archive.namelist():
            with zipfile.ZipFile(io.BytesIO(archive.read("classes.jar"))) as classes:
                return any(name.endswith(".class") for name in classes.namelist())
    return False


def fetch_one(row, cache, destination, previous=None):
    row = dict(row)
    source = source_url(row)
    relative = row["group"] + "/" + row["artifact"] + "/" + row["version"]
    folder = destination / relative
    folder.mkdir(parents=True, exist_ok=previous is not None)
    pom = cached_artifact(cache, row, ".pom")
    (folder / "artifact.pom").write_bytes(pom.read_bytes())
    licenses, parents = resolved_pom_licenses(pom.read_bytes(), cache, folder)
    row.update(sourceURL=source, pomSHA256=hashlib.sha256(pom.read_bytes()).hexdigest(),
               licenses=licenses, licenseParents=parents, sourcePath=relative + "/sources.jar")
    binary = cached_artifact(cache, row, "." + row["extension"])
    row["runtimeContainsClasses"] = artifact_has_code(binary)
    try:
        target = folder / "sources.jar"
        if target.exists():
            content = target.read_bytes()
            if previous is None or hashlib.sha256(content).hexdigest() != previous.get("sourceSHA256"):
                raise ValueError("cached-runtime-source-pin-mismatch")
        else:
            request = urllib.request.Request(source, headers={"User-Agent": "Termux-Omarchy-source-closure/1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.geturl().split("/")[2] not in ("dl.google.com", "repo.maven.apache.org"):
                    raise ValueError("unexpected-runtime-source-redirect")
                content = response.read(32 * 1024 * 1024 + 1)
        if len(content) > 32 * 1024 * 1024:
            raise ValueError("oversized-runtime-source-jar")
        target.write_bytes(content)
        row.update(inspect_source_jar(target, allow_empty=not row["runtimeContainsClasses"]))
        row.update(sourceSHA256=hashlib.sha256(content).hexdigest(), sourceBytes=len(content), status="COMPLETE")
        if not row["licenses"] or any(not license["name"] or not license["url"] for license in row["licenses"]):
            row.update(status="MISSING", error="published-runtime-license-metadata-missing")
    except (OSError, ValueError, urllib.error.URLError, zipfile.BadZipFile) as error:
        row.update(status="MISSING", error=str(error))
    return row


def prepare(work, java_home, *, resume=False):
    driver = driver_module()
    work = Path(work).resolve()
    receipt = json.loads((work / "build-receipt.json").read_text())
    if receipt["status"] != "UNSIGNED_APK_BUILT_NOT_AUDITED" or receipt["signed"]:
        raise ValueError("successful-unsigned-source-build-required")
    if driver.sha(receipt["apk"]["path"]) != receipt["apk"]["sha256"]:
        raise ValueError("candidate-unsigned-apk-changed")
    destination = work / "runtime-source"
    previous = {}
    if resume:
        prior = json.loads((destination / "manifest.json").read_text())
        if prior["candidateUnsignedAPKSHA256"] != receipt["apk"]["sha256"]:
            raise ValueError("cached-runtime-source-candidate-mismatch")
        previous = {(r["group"], r["artifact"], r["version"]): r for r in prior["dependencies"]}
    destination.mkdir(exist_ok=resume)
    report = work / "runtime-artifacts.json"
    recorder = driver.Recorder(work)
    env = driver.build_environment(work, java_home)
    recorder.run("runtime-dependency-report", [work / "source/gradlew", "--no-daemon", "--console=plain", "--stacktrace",
        "--offline", "--init-script", HERE / "unsigned.init.gradle", "--init-script", HERE / "runtime-report.init.gradle",
        "-Pandroid.builder.sdkDownload=false", "-PtermuxOmarchyBuildVersion=" + driver.BUILD_VERSION,
        "-PtermuxOmarchyRuntimeOutput=" + str(report), "termuxOmarchyRuntimeDependencies"], cwd=work / "source", env=env)
    rows = json.loads(report.read_text())
    unique = {}
    for row in rows:
        key = (row["group"], row["artifact"], row["version"])
        if key in unique:
            if unique[key]["sha256"] != row["sha256"]:
                raise ValueError("multiple-runtime-variants-require-audit")
            unique[key]["configurations"].append(row["configuration"])
        else:
            unique[key] = {**row, "configurations": [row["configuration"]]}
            del unique[key]["configuration"]
    cache = work / "gradle/caches/modules-2/files-2.1"
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda row: fetch_one(row, cache, destination,
            previous.get((row["group"], row["artifact"], row["version"]))), unique.values()))
    value = {"schema": 1, "status": "COMPLETE" if all(row["status"] == "COMPLETE" for row in results) else "MISSING",
             "runtimeConfigurations": [":lorie-app:sharedUidDebugRuntimeClasspath", ":shell-loader:debugRuntimeClasspath"],
             "candidateUnsignedAPKSHA256": receipt["apk"]["sha256"], "runtimeReportControlSHA256": driver.sha(HERE / "runtime-report.init.gradle"),
             "runtimeSourceDriverSHA256": driver.sha(Path(__file__)),
             "dependencies": results, "buildToolSourcesIncluded": False}
    driver.write_json(destination / "manifest.json", value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-dir", type=Path, required=True)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="reuse only source JARs matching the previous manifest hashes")
    args = parser.parse_args()
    value = prepare(args.prepared_dir, args.java_home, resume=args.resume)
    print(json.dumps(value, indent=2))
    return 0 if value["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
