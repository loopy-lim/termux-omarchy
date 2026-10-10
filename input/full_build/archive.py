#!/usr/bin/env python3
"""Export complete pinned prebuild sources, verify them, or rebuild without Git."""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = "SOURCE-MANIFEST.json"
KEY_SUFFIXES = {".jks", ".keystore", ".p12", ".pfx", ".key"}
STATE_NAMES = {".git", ".gradle", ".cxx", "build", "local.properties", "__pycache__"}


def driver_module():
    spec = importlib.util.spec_from_file_location("source_archive_driver", HERE / "driver.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def project_source_path(name):
    """Exclude release/runtime manifests whose source-archive hashes are circular."""
    safe_relative(name)
    return (name.startswith(("input/", "tests/input/", "legal/"))
            or name in ("LICENSE", "NOTICE.md", "manifests/input-sources.json", "manifests/input-toolchain.json"))


def safe_relative(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\x00" in name
            or "\\" in name or str(path) != name):
        raise ValueError("unsafe-source-path: " + name)
    return path


def excluded(name):
    path = safe_relative(name)
    # This exact original, hash-verified AAR metadata namespace contains "build";
    # arbitrary build directories remain forbidden, including inside Java sources.
    aar_metadata = (len(path.parts) == 11 and path.parts[0] == "java-runtime-sources"
                    and path.parts[-7:] == ("resource-inputs", "META-INF", "com", "android", "build", "gradle", "aar-metadata.properties"))
    state_names = STATE_NAMES - {"build"} if aar_metadata else STATE_NAMES
    return bool(state_names.intersection(path.parts) or path.suffix.lower() in KEY_SUFFIXES)


def destination_path(destination, name):
    base = Path(destination).resolve()
    path = base.joinpath(*safe_relative(name).parts)
    for parent in path.parents:
        if parent == base:
            break
        if parent.is_symlink():
            raise ValueError("source-symlink-parent-refused: " + name)
    return path


def export_git_tree(source, commit, destination):
    """Read Git blobs, never dirty native generated files or untracked files."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_TERMINAL_PROMPT": "0"}
    omitted = []
    entries = subprocess.check_output(["git", "-C", str(source), "ls-tree", "-r", "-z", commit], env=env)
    # Git archive honors export-ignore/export-subst attributes. Raw tracked blobs
    # preserve even original legal/source files marked for exclusion in releases.
    with subprocess.Popen(["git", "-C", str(source), "cat-file", "--batch"], env=env,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as reader:
        for entry in entries.split(b"\x00"):
            if not entry:
                continue
            header, raw_name = entry.split(b"\t", 1)
            mode, kind, oid = header.decode().split()
            name = raw_name.decode("utf-8")
            safe_relative(name)
            if kind == "commit":  # Native Gitlinks are exported separately.
                continue
            if excluded(name):
                omitted.append(name)
                continue
            reader.stdin.write(oid.encode() + b"\n")
            reader.stdin.flush()
            blob_header = reader.stdout.readline().decode().strip().split()
            if len(blob_header) != 3 or blob_header[:2] != [oid, "blob"]:
                raise ValueError("source-blob-unavailable: " + name)
            data = reader.stdout.read(int(blob_header[2]))
            if len(data) != int(blob_header[2]) or reader.stdout.read(1) != b"\n":
                raise ValueError("incomplete-source-blob: " + name)
            target = destination_path(destination, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if mode == "120000":
                link = data.decode("utf-8")
                if (PurePosixPath(link).is_absolute()
                        or not (target.parent / link).resolve().is_relative_to(destination.resolve())):
                    raise ValueError("unsafe-source-symlink: " + name)
                target.symlink_to(link)
            elif mode in ("100644", "100755"):
                target.write_bytes(data)
                target.chmod(0o755 if mode == "100755" else 0o644)
            else:
                raise ValueError("unsupported-source-entry: " + name)
        reader.stdin.close()
        if reader.wait() != 0:
            raise ValueError("source-blob-export-failed")
    return omitted


def apply_postimages(source, destination, delta):
    for name, digest in delta.items():
        target = destination_path(destination, name)
        original = destination_path(source, name)
        if digest is None:
            if original.exists() or original.is_symlink():
                raise ValueError("deleted-source-reappeared: " + name)
            if target.exists():
                target.unlink()
            continue
        if excluded(name) or original.is_symlink() or not original.is_file():
            raise ValueError("invalid-source-postimage: " + name)
        if hashlib.sha256(original.read_bytes()).hexdigest() != digest:
            raise ValueError("postimage-hash-mismatch: " + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        target.chmod(0o755 if original.stat().st_mode & 0o111 else 0o644)


def file_identity(path):
    if path.is_symlink():
        return {"type": "symlink", "target": os.readlink(path)}
    data = path.read_bytes()
    return {"type": "file", "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "executable": bool(path.stat().st_mode & 0o111)}


def tree_files(tree):
    result = {}
    for path in sorted(Path(tree).rglob("*")):
        if path.is_file() or path.is_symlink():
            name = path.relative_to(tree).as_posix()
            if name == MANIFEST:
                continue
            if excluded(name):
                raise ValueError("forbidden-source-entry: " + name)
            if path.is_symlink() and not path.resolve().is_relative_to(Path(tree).resolve()):
                raise ValueError("unsafe-source-symlink: " + name)
            result[name] = file_identity(path)
    return result


def write_manifest(tree, provenance):
    value = {"schema": 1, "provenance": provenance, "files": tree_files(tree)}
    (Path(tree) / MANIFEST).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return value


def verify_tree(tree):
    value = json.loads((Path(tree) / MANIFEST).read_text())
    actual = tree_files(tree)
    if value.get("schema") != 1 or set(actual) != set(value["files"]):
        raise ValueError("manifest-file-set-mismatch")
    for name, identity in actual.items():
        safe_relative(name)
        if identity != value["files"][name]:
            raise ValueError("manifest-content-mismatch: " + name)
    return value


def dependency_inventory(work):
    base = Path(work) / "gradle/caches/modules-2/files-2.1"
    return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(base.rglob("*")) if p.is_file() and not p.is_symlink()}


def copy_dependency_notices(work, destination):
    """Preserve published artifact POMs and embedded legal texts without binaries."""
    base = Path(work) / "gradle/caches/modules-2/files-2.1"
    destination = Path(destination)
    destination.mkdir()
    (destination / "README.txt").write_text(
        "Published POM metadata and embedded license/notice texts from the isolated build cache.\n"
        "This includes build-tool dependencies as well as application dependencies; presence\n"
        "does not assert that an artifact is packaged in the APK. See DEPENDENCIES.json for\n"
        "exact original artifact hashes. Native component notices stay in upstream sources.\n")
    legal = re.compile(r"(licenses?|notices?|copying|copyright|dependencies)([._-].*)?", re.I)

    def extract(data, relative, nested=False):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                if legal.fullmatch(PurePosixPath(entry.filename).name):
                    if entry.file_size > 10 * 1024 * 1024:
                        raise ValueError("oversized-dependency-notice")
                    target = destination_path(destination, relative + "/" + entry.filename)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(entry))
                elif not nested and entry.filename == "classes.jar":
                    extract(archive.read(entry), relative + "/classes.jar", nested=True)

    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(base).as_posix()
        if path.suffix == ".pom":
            target = destination_path(destination, "poms/" + relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        elif path.suffix in (".jar", ".aar"):
            extract(path.read_bytes(), "embedded/" + relative)


def copy_runtime_sources(work, destination, candidate):
    base = Path(work) / "runtime-source"
    value = json.loads((base / "manifest.json").read_text())
    if (value["status"] != "COMPLETE" or not value.get("resourceInputsAudited") or value.get("resourceInputGaps")
            or value["candidateUnsignedAPKSHA256"] != candidate
            or not value["dependencies"]):
        raise ValueError("complete-matching-runtime-sources-required")
    destination = Path(destination)
    destination.mkdir()
    shutil.copyfile(base / "manifest.json", destination / "manifest.json")
    for row in value["dependencies"]:
        relative = str(safe_relative(row["sourcePath"]))
        jar = destination_path(base, relative)
        pom = jar.with_name("artifact.pom")
        folder = PurePosixPath(relative).parent
        files = [(jar, row["sourceSHA256"], relative), (pom, row["pomSHA256"], str(folder / "artifact.pom"))]
        files.extend((destination_path(jar.parent, parent["pomPath"]), parent["pomSHA256"], str(folder / parent["pomPath"]))
                     for parent in row.get("licenseParents", []))
        metadata = row.get("moduleMetadata")
        if metadata:
            files.append((destination_path(jar.parent, metadata["path"]), metadata["sha256"], str(folder / metadata["path"])))
        for name, identity in row.get("resourceInputs", {}).get("files", {}).items():
            resource = str(folder / "resource-inputs" / safe_relative(name))
            files.append((destination_path(base, resource), identity["sha256"], resource))
        for path, digest, target_relative in files:
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("runtime-source-pin-mismatch: " + relative)
            target = destination_path(destination, target_relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    return value


BUILD_INSTRUCTIONS = """# Complete prepared source

This archive contains the exact upstream commit and all 16 native Gitlink source
trees, the prepared Java/CMake/loader changes, public build controls and original
component license/notice texts. Each component keeps its own license. The source
manifest records every file and native commit/tree; no signing key is included.
java-runtime-sources/ contains exact official source JARs and POM/license metadata
for the resolved app and loader runtime dependencies, with original artifact and
source hashes. It also preserves exact uncompiled runtime AAR manifests, resources,
assets, symbol/proguard/notice inputs and published module metadata. Compiled
resource/native/bundled-code gaps are rejected. External SDK, Gradle and build-tool
sources are not bundled. The build route rebuilds this app against pinned published
dependencies; it does not claim to rebuild every external library independently.
Native patch files are applied during CMake configuration using the included
direction-preserving patch wrapper. No historical APK is an input.

Verify after extraction (Python 3.9+, standard library only):

    python3 -B project/input/full_build/archive.py verify --tree "$PWD"

Rebuild into a NEW writable directory, outside this extracted source directory:

    python3 -B project/input/full_build/archive.py build --tree "$PWD" \\
      --work-dir /absolute/new-build --sdk-source /absolute/existing-android-sdk \\
      --java-home /absolute/jdk-21 --offline \\
      --gradle-cache-source /absolute/existing-gradle-cache

The SDK must already contain accepted licenses, platform android-34, build-tools
36.0.0, CMake 3.22.1, cmdline-tools/latest and NDK 29.0.14206865. Its packages and
accepted license copies are copied into the new directory; the original SDK is
never modified. The host needs Python, Git, POSIX patch, and bison for native code.
Gradle 9.7.1-all and exact Maven artifacts listed in DEPENDENCIES.json must already
be cached for --offline. General SDK/Gradle installations alone do not contain
all Maven dependencies. The cache copier reads only wrapper/dists and
caches/modules-2, never host Gradle properties or init scripts. Without --offline,
Gradle may download its pinned distribution and dependencies. Source rebuilding
requires no Git checkout or upstream source network access. The Git executable
is still used by upstream version probes, with CURRENT_COMMIT supplied explicitly. --install-missing may download
the pinned NDK only using existing accepted license copies, with closed stdin;
it never accepts new terms. Do not use that option for an offline build.

The result is an unsigned sharedUID APK plus its matching native companion package,
with a build receipt and hashes. Signing, installation and publication are separate
reviewed stages. The companion verifies the APK certificate against the public
Termux GitHub development certificate recorded in SIGNING.md; a differently signed
APK must not be paired with it. This archive contains only that PUBLIC certificate.
The archive manifest detects accidental changes; verify the archive SHA256 against
the separately published release receipt before trusting the source bundle.
"""


def create_archive(prepared_dir, output):
    driver = driver_module()
    prepared_dir, output = Path(prepared_dir).resolve(), Path(output).resolve()
    prepared = json.loads((prepared_dir / "prepared.json").read_text())
    receipt = json.loads((prepared_dir / "build-receipt.json").read_text())
    if receipt["status"] != "UNSIGNED_APK_BUILT_NOT_AUDITED" or receipt["signed"]:
        raise ValueError("successful-unsigned-source-build-required")
    if prepared["driverSHA256"] != driver.sha(HERE / "driver.py"):
        raise ValueError("archive-driver-must-match-build")
    for key, name in (("unsignedInitSHA256", "unsigned.init.gradle"), ("patchWrapperSHA256", "force_patch.sh")):
        if prepared[key] != driver.sha(HERE / name):
            raise ValueError("archive-controls-must-match-build")
    if prepared["buildPatchSHA256"] != {name: driver.sha(HERE / name) for name in driver.BUILD_PATCHES}:
        raise ValueError("archive-patches-must-match-build")
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="source-export-", dir=output.parent) as name:
        tree = Path(name) / "termux-omarchy-source"
        upstream = tree / "upstream"
        source = prepared_dir / "source"
        if driver.git(source, "rev-parse", "HEAD") != driver.UPSTREAM_COMMIT:
            raise ValueError("archive-upstream-pin-mismatch")
        omitted = export_git_tree(source, driver.UPSTREAM_COMMIT, upstream)
        apply_postimages(source, upstream, prepared["sourceDeltaSHA256"])
        for pin in prepared["native"]["roots"]:
            native = source / pin["path"]
            if (driver.git(native, "rev-parse", "HEAD") != pin["commit"]
                    or driver.git(native, "rev-parse", "HEAD^{tree}") != pin["tree"]):
                raise ValueError("archive-native-pin-mismatch: " + pin["path"])
            omitted.extend(pin["path"] + "/" + p for p in export_git_tree(native, pin["commit"], upstream / pin["path"]))
        names = set(driver.git(ROOT, "ls-files", "--cached").splitlines())
        inputs = driver.verify_inputs()
        names.update(row["path"] for row in inputs["inventory"]["files"])
        names.update(p.relative_to(ROOT).as_posix() for p in HERE.iterdir() if p.is_file())
        names.add("tests/input/test_full_build.py")
        for relative in sorted(names):
            if excluded(relative) or not project_source_path(relative):
                continue
            path = destination_path(ROOT, relative)
            if not path.is_file() or path.is_symlink():
                raise ValueError("project-source-unavailable: " + relative)
            target = destination_path(tree / "project", relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            target.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
        (tree / "BUILD.md").write_text(BUILD_INSTRUCTIONS)
        (tree / "DEPENDENCIES.json").write_text(json.dumps({"schema": 1,
            "gradleDistribution": "gradle-9.7.1-all.zip", "mavenCacheSHA256": dependency_inventory(prepared_dir)}, indent=2) + "\n")
        copy_dependency_notices(prepared_dir, tree / "dependency-notices")
        runtime_sources = copy_runtime_sources(prepared_dir, tree / "java-runtime-sources", receipt["apk"]["sha256"])
        provenance = {key: prepared[key] for key in ("upstreamCommit", "upstreamTree", "overlaySHA256", "native",
            "sourceDeltaSHA256", "certificateMetadata", "buildPatchSHA256", "driverSHA256", "unsignedInitSHA256", "patchWrapperSHA256")}
        provenance["native"] = {**prepared["native"], "roots": [
            {**row, "included": True} for row in prepared["native"]["roots"]]}
        provenance.update(signingKeysOmitted=omitted, nativeSources="pinned prebuild Git blobs; upstream CMake patches retained")
        provenance["build"] = {key: receipt[key] for key in ("buildVersion", "companionVersion", "companionPayload")}
        provenance["build"]["apk"] = {key: receipt["apk"][key] for key in ("sha256", "bytes", "nativeLibraries")}
        provenance["build"]["companions"] = [{"name": Path(row["path"]).name,
            "sha256": row["sha256"], "bytes": row["bytes"]} for row in receipt["companions"]]
        provenance["runtimeSources"] = {"dependencies": len(runtime_sources["dependencies"]),
            "manifestSHA256": driver.sha(prepared_dir / "runtime-source/manifest.json"), "status": "COMPLETE"}
        value = write_manifest(tree, provenance)
        verify_tree(tree)
        with output.open("xb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in sorted(tree.rglob("*")):
                    info = archive.gettarinfo(str(path), arcname="termux-omarchy-source/" + path.relative_to(tree).as_posix())
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ""
                    if path.is_file() and not path.is_symlink():
                        with path.open("rb") as reader:
                            archive.addfile(info, reader)
                    else:
                        archive.addfile(info)
    return {"path": str(output), "sha256": driver.sha(output), "bytes": output.stat().st_size,
            "sourceFiles": len(value["files"]), "nativeTrees": len(provenance["native"]["roots"]), "signingKeysIncluded": False}


def build_archive(tree, work, sdk_source, java_home, cache_source, offline, install_missing):
    driver = driver_module()
    tree, work = Path(tree).resolve(), Path(work).absolute()
    value = verify_tree(tree)
    if work.resolve().is_relative_to(tree) or tree.is_relative_to(work.resolve()):
        raise ValueError("archive-work-directory-overlap")
    if value["provenance"]["upstreamCommit"] != driver.UPSTREAM_COMMIT:
        raise ValueError("archive-upstream-pin-mismatch")
    for key, name in (("driverSHA256", "driver.py"), ("unsignedInitSHA256", "unsigned.init.gradle"),
                      ("patchWrapperSHA256", "force_patch.sh")):
        if value["provenance"][key] != driver.sha(HERE / name):
            raise ValueError("archive-controls-must-match-build")
    if value["provenance"]["buildPatchSHA256"] != {name: driver.sha(HERE / name) for name in driver.BUILD_PATCHES}:
        raise ValueError("archive-patches-must-match-build")
    work.mkdir(parents=True, exist_ok=False)
    shutil.copytree(tree / "upstream", work / "source", symlinks=True)
    if cache_source:
        cache_source = Path(cache_source).resolve()
        for relative in ("wrapper/dists", "caches/modules-2"):
            if (cache_source / relative).is_dir():
                shutil.copytree(cache_source / relative, work / "gradle" / relative)
    env = driver.build_environment(work, java_home)
    env["CURRENT_COMMIT"] = driver.UPSTREAM_COMMIT
    recorder = driver.Recorder(work)
    receipt = {"schema": 1, "status": "RUNNING", "sourceManifestSHA256": driver.sha(tree / MANIFEST),
               "offline": offline, "signed": False, "installed": False, "published": False}
    try:
        receipt.update(driver.android_build(work, recorder, env, sdk_source, install_missing, offline=offline))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        receipt.update(status="FAILED", error=str(error))
    finally:
        receipt["steps"] = recorder.steps
        driver.write_json(work / "build-receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("create", "verify", "build"))
    parser.add_argument("--prepared-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--tree", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--sdk-source", type=Path)
    parser.add_argument("--java-home", type=Path)
    parser.add_argument("--gradle-cache-source", type=Path)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--install-missing", action="store_true")
    args = parser.parse_args()
    if args.mode == "create":
        if args.prepared_dir is None or args.output is None:
            parser.error("create requires --prepared-dir and --output")
        result = create_archive(args.prepared_dir, args.output)
    elif args.mode == "verify":
        if args.tree is None:
            parser.error("verify requires --tree")
        result = {"status": "VERIFIED", "sourceFiles": len(verify_tree(args.tree)["files"])}
    else:
        if any(value is None for value in (args.tree, args.work_dir, args.sdk_source, args.java_home)):
            parser.error("build requires --tree, --work-dir, --sdk-source and --java-home")
        if args.offline and args.install_missing:
            parser.error("offline build cannot download the NDK")
        result = build_archive(args.tree, args.work_dir, args.sdk_source, args.java_home,
                               args.gradle_cache_source, args.offline, args.install_missing)
    print(json.dumps(result, indent=2))
    return 1 if result.get("status") == "FAILED" else 0


if __name__ == "__main__":
    sys.exit(main())
