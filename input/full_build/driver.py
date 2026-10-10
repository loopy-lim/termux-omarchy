#!/usr/bin/env python3
"""Prepare pinned complete source and attempt an isolated, unsigned Android build."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import struct
import subprocess
import sys
import tarfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_COMMIT = "6d3c6883265b4ec8092673e6d2d61ef86cab5405"
UPSTREAM_URL = "https://github.com/termux/termux-x11.git"
OVERLAY = "input/patches/termux-x11-input.patch"
NATIVE_NAMES = {"bzip2", "libepoxy", "libfontenc", "libtirpc", "libx11", "libxau",
                "libxcvt", "libxdmcp", "libxfont", "libxkbfile", "libxshmfence",
                "libxtrans", "pixman", "xkbcomp", "xorgproto", "xserver"}
SDK_COPY_DIRECTORIES = ("platforms/android-34", "build-tools/36.0.0", "cmake/3.22.1",
                        "cmdline-tools/latest")
NDK_PACKAGE = "ndk;29.0.14206865"
BUILD_VERSION = "1.03.01-6d3c688-input-source-alpha"
COMPANION_VERSION = "1.03.01+omarchy.input-alpha.1-0"
BUILD_PATCHES = {"loader-metadata.patch": ("shell-loader/build.gradle",
                  "3957d7edc8336e1478ce6447ba205856ad3910d81cb968779343cdcfcffda865"),
                 "native-build.patch": ("lorie/src/main/cpp/recipes/xkbcomp.cmake",
                  "8eb84e9bf1ed0d50e8380e7813abe475f5d51439a43bc45ab969d3a156f54da7"),
                 "companion-identity.patch": ("shell-loader/companion-package.gradle",
                  "20d4992d9b072330a9a412e0eb2e9ce986bfddc65387f80115267b2b10168e1b")}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def certificate_metadata(path=None):
    path = Path(path) if path is not None else Path(__file__).with_name("termux-public-certificate.txt")
    pem = path.read_text()
    if "PRIVATE KEY" in pem or not pem.startswith("-----BEGIN CERTIFICATE-----"):
        raise ValueError("public-certificate-required")
    try:
        der = ssl.PEM_cert_to_DER_cert(pem)
    except ValueError as error:
        raise ValueError("public-certificate-required") from error
    digest = hashlib.sha256(der).hexdigest()
    if digest != "b6da01480eefd5fbf2cd3771b8d1021ec791304bdd6c4bf41d3faabad48ee5e1":
        raise ValueError("public-certificate-pin-mismatch")
    value = 1
    for byte in der:
        value = (31 * value + (byte if byte < 128 else byte - 256)) & 0xffffffff
    value = value if value < 2**31 else value - 2**32
    patch = Path(__file__).with_name("loader-metadata.patch").read_text()
    if "def termuxPublicCertificateSignatureHash = " + str(value) not in patch:
        raise ValueError("loader-certificate-derived-hash-mismatch")
    return {"certificateSHA256": digest, "javaArraysHashCode": value, "privateKeyUsed": False}


def verify_inputs(root=ROOT):
    root = Path(root)
    inventory = json.loads((root / "manifests/input-sources.json").read_text())
    toolchain = json.loads((root / "manifests/input-toolchain.json").read_text())
    if inventory["upstream"]["commit"] != UPSTREAM_COMMIT:
        raise ValueError("upstream-pin-mismatch")
    path = root / OVERLAY
    rows = [row for row in inventory["files"] if row["path"] == OVERLAY]
    if (len(rows) != 1 or not path.is_file() or path.is_symlink()
            or sha(path) != rows[0]["sha256"] or path.stat().st_size != rows[0]["bytes"]):
        raise ValueError("overlay-hash-mismatch")
    full = toolchain["pinnedUpstreamFullBuild"]
    pins = full["submodules"]
    expected = {"lorie/src/main/cpp/" + name for name in NATIVE_NAMES}
    if (len(pins) != len(expected) or {row["path"] for row in pins} != expected
            or any(not re.fullmatch(r"[a-f0-9]{40}", row["commit"]) for row in pins)):
        raise ValueError("native-pin-set-mismatch")
    if full["androidGradlePlugin"] != "9.3.1" or full["ndk"] != NDK_PACKAGE.split(";")[1]:
        raise ValueError("full-build-toolchain-pin-mismatch")
    return {"upstreamCommit": UPSTREAM_COMMIT, "upstreamURL": UPSTREAM_URL,
            "overlaySHA256": sha(path), "nativePins": pins, "inventory": inventory}


def verify_gitlinks(tree, pins):
    rows = []
    for line in tree.splitlines():
        if line.startswith("160000 "):
            match = re.fullmatch(r"160000 commit ([a-f0-9]{40})\t(.+)", line)
            if not match:
                raise ValueError("native-gitlinks-mismatch")
            rows.append((match[2], match[1]))
    expected = {(row["path"], row["commit"]) for row in pins}
    if len(rows) != len(expected) or set(rows) != expected:
        raise ValueError("native-gitlinks-mismatch")


def build_environment(work, java_home, inherited=None):
    original = os.environ if inherited is None else inherited
    allowed = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT")
    env = {key: original[key] for key in allowed if key in original}
    env.update(JAVA_HOME=str(java_home), ANDROID_HOME=str(work / "sdk"),
               ANDROID_SDK_ROOT=str(work / "sdk"), GRADLE_USER_HOME=str(work / "gradle"),
               ANDROID_USER_HOME=str(work / "android-user"), GIT_TERMINAL_PROMPT="0",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               PYTHONDONTWRITEBYTECODE="1")
    env["PATH"] = str(Path(java_home) / "bin") + os.pathsep + env.get("PATH", os.defpath)
    return env


def copy_sdk(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if (source == destination or source in destination.parents or destination in source.parents):
        raise ValueError("sdk-source-destination-overlap")
    if destination.exists():
        raise FileExistsError(destination)
    if not (source / "licenses/android-sdk-license").is_file():
        raise ValueError("existing-sdk-license-required")
    for relative in SDK_COPY_DIRECTORIES:
        if not (source / relative).is_dir():
            raise ValueError("existing-sdk-package-required: " + relative)
    packages = list(SDK_COPY_DIRECTORIES)
    ndk_relative = "ndk/" + NDK_PACKAGE.split(";")[1]
    if (source / ndk_relative).is_dir():
        packages.append(ndk_relative)
    destination.mkdir(parents=True)
    metadata = {}
    for relative in packages:
        shutil.copytree(source / relative, destination / relative)
        properties = destination / relative / "source.properties"
        if properties.is_file():
            metadata[relative] = sha(properties)
    shutil.copytree(source / "licenses", destination / "licenses")
    licenses = {p.name: sha(p) for p in sorted((destination / "licenses").iterdir()) if p.is_file()}
    return {"copiedPackages": packages, "packageMetadataSHA256": metadata, "licenseSHA256": licenses,
            "acceptedNewLicenses": False, "hostSDKModified": False}


def native_patch_environment(work, env):
    patch = shutil.which("patch", path=env["PATH"])
    if patch is None:
        raise ValueError("POSIX-patch-required")
    controls = Path(work) / "controls"
    controls.mkdir(exist_ok=True)
    wrapper_source = Path(__file__).with_name("force_patch.sh")
    wrapper = controls / "patch"
    shutil.copyfile(wrapper_source, wrapper)
    wrapper.chmod(0o700)
    result = {**env, "TERMUX_OMARCHY_PATCH": patch,
              "PATH": str(controls) + os.pathsep + env["PATH"]}
    return result, {"executableSHA256": sha(patch), "wrapperSHA256": sha(wrapper),
                    "forceReverseProbe": True}


def inspect_unsigned_apk(path):
    path = Path(path)
    raw = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        signed = any(re.fullmatch(r"META-INF/[^/]+\.(?:RSA|DSA|EC|SF)", n, re.I) for n in names)
        central = archive.start_dir
        block = False
        if central >= 24 and raw[central - 16:central] == b"APK Sig Block 42":
            size = struct.unpack_from("<Q", raw, central - 24)[0]
            block = (24 <= size <= central - 8
                     and struct.unpack_from("<Q", raw, central - size - 8)[0] == size)
        if signed or block:
            raise ValueError("signed-apk-refused")
        if len(names) != len(set(names)) or not {"AndroidManifest.xml", "classes.dex"} <= set(names):
            raise ValueError("incomplete-apk")
        native = [n for n in names if re.fullmatch(r"lib/[^/]+/libXlorie\.so", n)]
        if not native:
            raise ValueError("native-library-missing")
        return {"path": str(path), "sha256": sha(path), "bytes": len(raw),
                "signed": False, "installableRelease": False,
                "nativeLibraries": {n: hashlib.sha256(archive.read(n)).hexdigest() for n in native}}


def inspect_companion(path):
    raw = Path(path).read_bytes()
    if not raw.startswith(b"!<arch>\n"):
        raise ValueError("invalid-companion-ar")
    members, offset = {}, 8
    while offset < len(raw):
        header = raw[offset:offset + 60]
        if len(header) != 60 or header[58:] != b"`\n":
            raise ValueError("invalid-companion-ar")
        name = header[:16].decode().strip().removesuffix("/")
        size = int(header[48:58])
        offset += 60
        if name in members or size < 0 or offset + size > len(raw):
            raise ValueError("invalid-companion-member")
        members[name] = raw[offset:offset + size]
        offset += size + size % 2
    if members.get("debian-binary") != b"2.0\n" or "data.tar.xz" not in members:
        raise ValueError("invalid-companion-deb")
    expected = {"bin/termux-x11": "0755", "bin/termux-x11-preference": "0755",
                "libexec/termux-x11/loader.apk": "0644"}
    payload = {}
    prefix = "data/data/com.termux/files/usr/"
    with tarfile.open(fileobj=io.BytesIO(members["data.tar.xz"]), mode="r:xz") as archive:
        for member in archive:
            if member.isdir():
                continue
            name = member.name.removeprefix("./")
            relative = name.removeprefix(prefix)
            mode = format(member.mode & 0o7777, "04o")
            if (not member.isfile() or relative not in expected or name != prefix + relative
                    or relative in payload or mode != expected[relative]):
                raise ValueError("unexpected-companion-payload: " + name)
            data = archive.extractfile(member).read()
            payload[relative] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                                 "archiveMode": mode, "installedMode": "0400" if relative.endswith(".apk") else mode}
    if set(payload) != set(expected):
        raise ValueError("incomplete-companion-payload")
    return payload


class Recorder:
    def __init__(self, work):
        self.work = Path(work)
        (self.work / "logs").mkdir(parents=True, exist_ok=True)
        self.steps = []

    def run(self, stage, argv, *, cwd, env=None, timeout=1800):
        log = self.work / "logs" / (stage + ".txt")
        row = {"stage": stage, "argv": [str(a) for a in argv],
               "log": str(log.relative_to(self.work)), "status": "RUNNING"}
        self.steps.append(row)
        print(stage + ": running", flush=True)
        started = time.monotonic()
        try:
            with log.open("wb") as output:
                result = subprocess.run(list(map(str, argv)), cwd=cwd, env=env,
                                        stdin=subprocess.DEVNULL, stdout=output,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            row["exitCode"] = result.returncode
            row["status"] = "PASS" if result.returncode == 0 else "FAILED"
        except (OSError, subprocess.TimeoutExpired) as error:
            row.update(status="FAILED", exitCode=None, error=type(error).__name__)
            raise RuntimeError(stage + ": " + type(error).__name__) from error
        finally:
            row["elapsedSeconds"] = round(time.monotonic() - started, 3)
        if result.returncode:
            raise RuntimeError(stage + ": exit " + str(result.returncode) + "; see " + str(log))
        print(stage + ": PASS", flush=True)
        return log.read_text(errors="replace")


def git(source, *arguments):
    return subprocess.check_output(["git", "-C", str(source), *arguments], text=True,
                                   env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1",
                                        "GIT_CONFIG_GLOBAL": os.devnull}).strip()


def audit_native(source, pins):
    verify_gitlinks(git(source, "ls-tree", "-r", "HEAD"), pins)
    rows = []
    for pin in pins:
        submodule = source / pin["path"]
        if git(submodule, "rev-parse", "HEAD") != pin["commit"]:
            raise ValueError("native-checkout-pin-mismatch: " + pin["path"])
        if git(submodule, "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"):
            raise ValueError("native-source-dirty-before-build: " + pin["path"])
        rows.append({**pin, "tree": git(submodule, "rev-parse", "HEAD^{tree}")})
    status = git(source, "submodule", "status", "--recursive")
    for line in status.splitlines():
        # strip() removes the first leading space only; the other state prefixes survive.
        if line[0] in "-+U":
            raise ValueError("recursive-submodule-unresolved")
    return {"roots": rows, "recursiveStatus": status}


def source_delta(source):
    tracked = git(source, "diff", "--name-only", "HEAD").splitlines()
    untracked = git(source, "ls-files", "--others", "--exclude-standard").splitlines()
    paths = sorted(set(tracked + untracked))
    return {name: sha(source / name) if (source / name).is_file() else None for name in paths}


def prepare(work, inputs, recorder, env):
    source = work / "source"
    recorder.run("clone-upstream", ["git", "clone", "--filter=blob:none", "--no-checkout",
                                   UPSTREAM_URL, source], cwd=work, env=env)
    recorder.run("checkout-upstream", ["git", "checkout", "--detach", UPSTREAM_COMMIT],
                 cwd=source, env=env)
    if git(source, "rev-parse", "HEAD") != UPSTREAM_COMMIT:
        raise ValueError("upstream-checkout-pin-mismatch")
    verify_gitlinks(git(source, "ls-tree", "-r", "HEAD"), inputs["nativePins"])
    recorder.run("recursive-native-fetch", ["git", "submodule", "update", "--init", "--recursive",
                                          "--jobs", "8", "--depth", "1"], cwd=source, env=env)
    native = audit_native(source, inputs["nativePins"])
    for row in inputs["inventory"]["files"]:
        prefix = "input/upstream/"
        if row["path"].startswith(prefix):
            path = source / row["path"][len(prefix):]
            if not path.is_file() or sha(path) != row["sha256"]:
                raise ValueError("upstream-reference-hash-mismatch: " + row["path"])
    recorder.run("apply-public-overlay", ["patch", "--batch", "--fuzz=0", "-p1", "-i", ROOT / OVERLAY],
                 cwd=source, env=env)
    for row in inputs["inventory"]["files"]:
        prefix = "input/src/"
        if row["path"].startswith(prefix):
            path = source / "lorie/src/main/java" / row["path"][len(prefix):]
            if not path.is_file() or sha(path) != row["sha256"]:
                raise ValueError("overlay-postimage-hash-mismatch: " + row["path"])
    for name, (target, digest) in BUILD_PATCHES.items():
        if sha(source / target) != digest:
            raise ValueError("build-patch-preimage-mismatch: " + target)
        recorder.run("apply-" + name.removesuffix(".patch"),
                     ["patch", "--batch", "--fuzz=0", "-p1", "-i", Path(__file__).with_name(name)],
                     cwd=source, env=env)
    # BSD patch may retain backup preimages; they are not additional source inputs.
    for target, digest in BUILD_PATCHES.values():
        backup = Path(str(source / target) + ".orig")
        if backup.exists():
            if sha(backup) != digest:
                raise ValueError("unexpected-build-patch-backup: " + target)
            backup.unlink()
    certificate = certificate_metadata()
    # Upstream's public untrusted private key is unnecessary for unsigned builds.
    (source / "lorie-app/testkey_untrusted.jks").unlink()
    result = {"schema": 1, "status": "PREPARED_NOT_BUILT", "upstreamCommit": UPSTREAM_COMMIT,
              "upstreamTree": git(source, "rev-parse", "HEAD^{tree}"),
              "overlaySHA256": inputs["overlaySHA256"], "native": native,
              "sourceDeltaSHA256": source_delta(source), "compileStubsCopied": False,
              "historicalBinaryInputsUsed": False, "correspondingSourceAudited": False,
              "certificateMetadata": certificate, "signingKeyRemoved": True,
              "buildPatchSHA256": {name: sha(Path(__file__).with_name(name)) for name in BUILD_PATCHES},
              "driverSHA256": sha(Path(__file__)), "unsignedInitSHA256": sha(Path(__file__).with_name("unsigned.init.gradle")),
              "patchWrapperSHA256": sha(Path(__file__).with_name("force_patch.sh"))}
    write_json(work / "prepared.json", result)
    return result


def build(work, inputs, recorder, env, sdk_source, install_missing):
    source = work / "source"
    prepared = json.loads((work / "prepared.json").read_text())
    if (prepared["status"] != "PREPARED_NOT_BUILT" or prepared["upstreamCommit"] != UPSTREAM_COMMIT
            or prepared["overlaySHA256"] != inputs["overlaySHA256"]
            or source_delta(source) != prepared["sourceDeltaSHA256"]):
        raise ValueError("prepared-source-changed")
    for key, name in (("driverSHA256", "driver.py"), ("unsignedInitSHA256", "unsigned.init.gradle"),
                      ("patchWrapperSHA256", "force_patch.sh")):
        if prepared[key] != sha(Path(__file__).with_name(name)):
            raise ValueError("prepared-build-controls-changed")
    if prepared["buildPatchSHA256"] != {name: sha(Path(__file__).with_name(name)) for name in BUILD_PATCHES}:
        raise ValueError("prepared-build-patches-changed")
    audit_native(source, inputs["nativePins"])
    for relative in (".gradle", "lorie/build", "lorie/.cxx", "lorie-app/build", "local.properties"):
        if (source / relative).exists():
            raise ValueError("clean-build-required: " + relative)
    return android_build(work, recorder, env, sdk_source, install_missing)


def android_build(work, recorder, env, sdk_source, install_missing, *, offline=False):
    """Build already verified source; shared by Git preparation and source archives."""
    source = work / "source"
    sdk = work / "sdk"
    copied = copy_sdk(sdk_source, sdk)
    write_json(work / "sdk-provenance.json", copied)
    ndk = sdk / "ndk" / NDK_PACKAGE.split(";")[1]
    if not ndk.is_dir():
        if not install_missing:
            raise ValueError("missing-pinned-ndk; use --install-missing with existing accepted licenses")
        recorder.run("download-pinned-ndk", [sdk / "cmdline-tools/latest/bin/sdkmanager",
                                           "--sdk_root=" + str(sdk), NDK_PACKAGE], cwd=work, env=env)
        after = {p.name: sha(p) for p in sorted((sdk / "licenses").iterdir()) if p.is_file()}
        if after != copied["licenseSHA256"]:
            raise ValueError("sdk-license-state-changed")
    properties = ndk / "source.properties"
    if (not properties.is_file()
            or not re.search(r"Pkg.Revision\s*=\s*29\.0\.14206865\s*$", properties.read_text(), re.M)):
        raise ValueError("pinned-ndk-install-incomplete")
    copied["packageMetadataSHA256"]["ndk/" + NDK_PACKAGE.split(";")[1]] = sha(properties)
    env, copied["nativePatchControl"] = native_patch_environment(work, env)
    write_json(work / "sdk-provenance.json", copied)
    recorder.run("java-version", [Path(env["JAVA_HOME"]) / "bin/java", "-version"], cwd=work, env=env)
    recorder.run("unsigned-gradle-build", [source / "gradlew", "--no-daemon", "--console=plain",
                 "--stacktrace", "--init-script", Path(__file__).with_name("unsigned.init.gradle"),
                 "-Pandroid.builder.sdkDownload=false", "-PtermuxOmarchyBuildVersion=" + BUILD_VERSION,
                 *(["--offline"] if offline else []),
                 ":lorie-app:assembleSharedUidDebug", ":shell-loader:buildCompanionPackage"],
                 cwd=source, env=env, timeout=3600)
    apks = sorted((source / "lorie-app/build/outputs/apk/sharedUid/debug").glob("*.apk"))
    if len(apks) != 1:
        raise ValueError("expected-one-source-built-apk")
    artifact = inspect_unsigned_apk(apks[0])
    companions = sorted((source / "shell-loader/build/outputs/companion").glob("*"))
    if not companions or not any(p.name.endswith(".deb") for p in companions):
        raise ValueError("companion-package-missing")
    return {"status": "UNSIGNED_APK_BUILT_NOT_AUDITED", "apk": artifact,
            "companions": [{"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in companions if p.is_file()],
            "buildVersion": BUILD_VERSION, "signed": False, "installed": False,
            "companionVersion": COMPANION_VERSION,
            "companionPayload": inspect_companion(next(p for p in companions if p.name.endswith(".deb"))),
            "published": False, "correspondingSourceAudited": False,
            "historicalAPKByteEquivalenceClaimed": False,
            "postBuildSourceStatus": git(source, "status", "--porcelain", "--ignore-submodules=none")
                    if (source / ".git").exists() else "archive tree; see source-manifest hashes"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "prepare", "build", "all"))
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--sdk-source", type=Path, default=os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME"))
    parser.add_argument("--java-home", type=Path, default=os.environ.get("JAVA_HOME"))
    parser.add_argument("--install-missing", action="store_true", help="download pinned NDK using already accepted SDK license copies; stdin remains closed")
    args = parser.parse_args()
    inputs = verify_inputs()
    if args.mode == "plan":
        print(json.dumps({k: v for k, v in inputs.items() if k != "inventory"}, indent=2))
        return 0
    if args.work_dir is None or args.java_home is None:
        parser.error("--work-dir and --java-home (or JAVA_HOME) are required")
    work = args.work_dir.expanduser().absolute()
    if work.resolve() == ROOT or ROOT in work.resolve().parents:
        parser.error("work directory must be outside the public source checkout")
    if args.mode in ("prepare", "all"):
        work.mkdir(parents=True, exist_ok=False)
    elif not (work / "prepared.json").is_file() or (work / "build-receipt.json").exists():
        parser.error("build requires a prepared source directory with no earlier build attempt")
    recorder = Recorder(work)
    env = build_environment(work, args.java_home.expanduser().resolve())
    receipt = {"schema": 1, "status": "RUNNING", "mode": args.mode,
               "upstreamCommit": UPSTREAM_COMMIT, "overlaySHA256": inputs["overlaySHA256"],
               "correspondingSourceAudited": False, "signed": False, "installed": False, "published": False}
    output = work / ("prepare-receipt.json" if args.mode == "prepare" else "build-receipt.json")
    try:
        if args.mode in ("prepare", "all"):
            receipt["preparation"] = prepare(work, inputs, recorder, env)
            receipt["status"] = "PREPARED_NOT_BUILT"
        if args.mode in ("build", "all"):
            if args.sdk_source is None:
                raise ValueError("--sdk-source (or ANDROID_SDK_ROOT) is required")
            receipt.update(build(work, inputs, recorder, env, args.sdk_source, args.install_missing))
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
        receipt.update(status="FAILED", error=str(error))
        print("FULL_SOURCE_BUILD_FAILED: " + str(error), file=sys.stderr)
    finally:
        receipt["steps"] = recorder.steps
        write_json(output, receipt)
    print("receipt: " + str(output), flush=True)
    return 1 if receipt["status"] == "FAILED" else 0


if __name__ == "__main__":
    sys.exit(main())
