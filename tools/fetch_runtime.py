#!/usr/bin/env python3
"""Fetch immutable Android runtime inputs without executing downloaded content."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "third_party/runtime.lock.json"
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
SOCKET_TIMEOUT_SECONDS = 30
DOWNLOAD_TIMEOUT_SECONDS = 180
EXPECTED_PATHS = {
    "libproot.so": "arm64-v8a/libproot.so",
    "libproot_loader.so": "arm64-v8a/libproot_loader.so",
    "rootfs.tar.gz": "rootfs.tar.gz",
}
NATIVE_URL = re.compile(
    r"https://raw\.githubusercontent\.com/localdesktop/localdesktop\.github\.io/"
    r"[0-9a-f]{40}/assets/libs/arm64-v8a/libproot(?:_loader)?\.so\Z"
)
ROOTFS_URL = (
    "https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/aarch64/"
    "alpine-minirootfs-3.22.6-aarch64.tar.gz"
)


class ArtifactError(ValueError):
    """A locked artifact could not be obtained or verified."""


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        response.close()
        raise ArtifactError(f"Redirect refused for locked HTTPS source: {request.full_url}")


def load_lock() -> list[dict]:
    try:
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ArtifactError(f"Cannot read runtime lock: {error}") from error
    if not isinstance(lock, dict) or lock.get("schema_version") != 1:
        raise ArtifactError("Unsupported runtime lock schema")
    artifacts = lock.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(EXPECTED_PATHS):
        raise ArtifactError("Runtime lock must contain the three required artifacts")
    seen = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ArtifactError("Invalid runtime artifact record")
        name = artifact.get("name")
        if name not in EXPECTED_PATHS or name in seen:
            raise ArtifactError(f"Unknown or duplicate runtime artifact: {name}")
        seen.add(name)
        if artifact.get("path") != EXPECTED_PATHS[name]:
            raise ArtifactError(f"Invalid artifact path: {artifact.get('path')}")
        url = artifact.get("url", "")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ArtifactError("Runtime sources must use locked HTTPS URLs")
        native = name != "rootfs.tar.gz"
        if (native and not NATIVE_URL.fullmatch(url)) or (not native and url != ROOTFS_URL):
            raise ArtifactError(f"Source is not an allowed immutable HTTPS artifact: {url}")
        if native and url.rsplit("/", 1)[-1] != name:
            raise ArtifactError("Source filename does not match the artifact path")
        digest = artifact.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ArtifactError(f"Invalid SHA-256 for {name}")
        size = artifact.get("size_bytes")
        if type(size) is not int or not 0 < size <= MAX_ARTIFACT_BYTES:
            raise ArtifactError(f"Invalid bounded artifact size for {name}")
        expected_format = "elf-aarch64" if native else "alpine-minirootfs-aarch64"
        if artifact.get("format") != expected_format:
            raise ArtifactError(f"Invalid artifact format for {name}")
        for field in ("source", "license"):
            if not isinstance(artifact.get(field), str) or not artifact[field].strip():
                raise ArtifactError(f"Missing {field} provenance for {name}")
    return artifacts


def verify_elf(header: bytes, name: str) -> None:
    if (len(header) < 64 or header[:7] != b"\x7fELF\x02\x01\x01"
            or struct.unpack_from("<H", header, 18)[0] != 183
            or struct.unpack_from("<H", header, 16)[0] not in (2, 3)):
        raise ArtifactError(f"Expected ELF64 little-endian AArch64 executable: {name}")


def verify_rootfs(path: Path) -> None:
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            def member(name):
                try:
                    return archive.getmember("./" + name)
                except KeyError:
                    return archive.getmember(name)

            executable = member("bin/busybox")
            release = member("etc/alpine-release")
            if not executable.isfile() or not release.isfile() or release.size > 128:
                raise ArtifactError("Rootfs must contain busybox and Alpine release files")
            with archive.extractfile(executable) as source:
                verify_elf(source.read(64), "rootfs bin/busybox")
            with archive.extractfile(release) as source:
                if source.read().strip() != b"3.22.6":
                    raise ArtifactError("Rootfs does not match Alpine 3.22.6")
    except (OSError, tarfile.TarError, KeyError) as error:
        raise ArtifactError(f"Invalid Alpine rootfs archive: {error}") from error


def verify_artifact(path: Path, artifact: dict) -> None:
    if path.is_symlink() or not path.is_file():
        raise ArtifactError(f"Missing regular artifact: {path}")
    if path.stat().st_size != artifact["size_bytes"]:
        raise ArtifactError(f"Artifact size mismatch: {artifact['name']}")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    if digest.hexdigest() != artifact["sha256"]:
        raise ArtifactError(f"SHA-256 mismatch: {artifact['name']}")
    if artifact["format"] == "elf-aarch64":
        with path.open("rb") as source:
            verify_elf(source.read(64), artifact["name"])
    else:
        verify_rootfs(path)


def download_artifact(artifact: dict, destination: Path) -> None:
    request = urllib.request.Request(
        artifact["url"], headers={"User-Agent": "loopy-desktop-runtime-fetch/1"}
    )
    opener = urllib.request.build_opener(RejectRedirects())
    started = time.monotonic()
    try:
        with opener.open(request, timeout=SOCKET_TIMEOUT_SECONDS) as response:
            if response.geturl() != artifact["url"]:
                raise ArtifactError("Response escaped the locked HTTPS URL")
            length = response.headers.get("Content-Length")
            if length is not None and int(length) != artifact["size_bytes"]:
                raise ArtifactError(f"Download size mismatch: {artifact['name']}")
            total = 0
            with destination.open("xb") as target:
                while True:
                    if time.monotonic() - started > DOWNLOAD_TIMEOUT_SECONDS:
                        raise ArtifactError(f"Download time limit exceeded: {artifact['name']}")
                    chunk = response.read1(min(CHUNK_BYTES, artifact["size_bytes"] + 1 - total))
                    if time.monotonic() - started > DOWNLOAD_TIMEOUT_SECONDS:
                        raise ArtifactError(f"Download time limit exceeded: {artifact['name']}")
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > artifact["size_bytes"]:
                        raise ArtifactError(f"Download size limit exceeded: {artifact['name']}")
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
    except (OSError, ValueError, urllib.error.URLError) as error:
        if isinstance(error, urllib.error.HTTPError):
            error.close()
        if isinstance(error, ArtifactError):
            raise
        raise ArtifactError(f"Download failed for {artifact['name']}: {error}") from error
    verify_artifact(destination, artifact)


def fetch_runtime(output: Path | None = None) -> list[dict]:
    """Verify the whole input set before replacing any cached artifact."""
    artifacts = load_lock()
    output = (output or ROOT / "build/runtime").expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    destinations = {}
    for artifact in artifacts:
        destination = output / artifact["path"]
        if not destination.parent.resolve().is_relative_to(output) or destination.is_symlink():
            raise ArtifactError(f"Artifact path escapes output or is a symlink: {destination}")
        destinations[artifact["name"]] = destination
    pending = []
    with tempfile.TemporaryDirectory(prefix=".fetch-", dir=output) as temporary:
        stage = Path(temporary)
        for artifact in artifacts:
            destination = destinations[artifact["name"]]
            try:
                verify_artifact(destination, artifact)
            except ArtifactError:
                downloaded = stage / (artifact["name"] + ".part")
                download_artifact(artifact, downloaded)
                pending.append((downloaded, destination, artifact))
        for downloaded, destination, artifact in pending:
            destination.parent.mkdir(parents=True, exist_ok=True)
            downloaded.chmod(0o755 if artifact["format"] == "elf-aarch64" else 0o644)
            os.replace(downloaded, destination)
    return [{
        "name": artifact["name"], "path": str(destinations[artifact["name"]]),
        "sha256": artifact["sha256"], "size_bytes": artifact["size_bytes"],
        "format": artifact["format"], "source": artifact["source"], "license": artifact["license"],
    } for artifact in artifacts]


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and verify pinned ARM64 runtime files")
    parser.add_argument("--output", type=Path, help="Output directory (default: build/runtime)")
    args = parser.parse_args()
    try:
        receipt = fetch_runtime(args.output)
    except (ArtifactError, OSError) as error:
        print(f"Runtime fetch failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"schema_version": 1, "artifacts": receipt}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
