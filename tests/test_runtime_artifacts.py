"""Behavior tests for locked, atomic runtime downloads using a local HTTP fixture."""

from __future__ import annotations

import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

try:
    runtime = importlib.import_module("tools.fetch_runtime")
except ModuleNotFoundError:
    runtime = None


COMMIT = "e6a8b580a3376e842cca2e44327a99498d7fb6dc"
BASE = f"https://raw.githubusercontent.com/localdesktop/localdesktop.github.io/{COMMIT}/"
ALPINE = "https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/aarch64/"


def elf(machine: int = 183) -> bytes:
    header = bytearray(64)
    header[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<HHI", header, 16, 3, machine, 1)
    return bytes(header) + b"fixture native payload"


def rootfs(release: bytes = b"3.22.6\n") -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, body in (("bin/busybox", elf()), ("etc/alpine-release", release)):
            info = tarfile.TarInfo(name)
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    return output.getvalue()


def locked_artifact(name: str, body: bytes) -> dict:
    native = name != "rootfs.tar.gz"
    return {
        "name": name,
        "path": f"arm64-v8a/{name}" if native else name,
        "url": BASE + "assets/libs/arm64-v8a/" + name if native else ALPINE + "alpine-minirootfs-3.22.6-aarch64.tar.gz",
        "sha256": hashlib.sha256(body).hexdigest(),
        "size_bytes": len(body),
        "format": "elf-aarch64" if native else "alpine-minirootfs-aarch64",
        "license": "GPL-2.0-or-later" if native else "mixed; per-package licenses",
        "source": BASE + "patches/build-proot-android/" if native else ALPINE,
    }


class RuntimeArtifactTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(runtime, "The dependency downloader has not been implemented")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.output = self.directory / "runtime"
        self.lock_path = self.directory / "runtime.lock.json"
        self.payloads = {
            "libproot.so": elf(),
            "libproot_loader.so": elf() + b"loader",
            "rootfs.tar.gz": rootfs(),
        }
        self.lock = {"schema_version": 1, "artifacts": [
            locked_artifact(name, body) for name, body in self.payloads.items()
        ]}
        self.lock_path.write_text(json.dumps(self.lock), encoding="utf-8")
        self.patch_lock = patch.object(runtime, "LOCK_PATH", self.lock_path)
        self.patch_lock.start()
        self.addCleanup(self.patch_lock.stop)

    @contextlib.contextmanager
    def server(self, responses=None):
        responses = responses or self.payloads
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                name = self.path.rsplit("/", 1)[-1]
                if name.startswith("alpine-minirootfs"):
                    name = "rootfs.tar.gz"
                requests.append(name)
                body = responses.get(name)
                if body is None:
                    self.send_error(404)
                    return
                options = body if isinstance(body, dict) else {"body": body}
                if "redirect" in options:
                    self.send_response(302)
                    self.send_header("Location", options["redirect"])
                    self.end_headers()
                    return
                body = options["body"]
                self.send_response(200)
                if options.get("content_length", True):
                    self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        original_open = urllib.request.OpenerDirector.open

        def open_fixture(opener, request, *args, **kwargs):
            original = request.full_url if hasattr(request, "full_url") else request
            url = f"http://127.0.0.1:{http.server_port}/" + original.rsplit("/", 1)[-1]
            response = original_open(opener, url, *args, **kwargs)
            response.url = original
            return response

        try:
            with patch("urllib.request.OpenerDirector.open", new=open_fixture):
                yield requests
        finally:
            http.shutdown()
            http.server_close()
            thread.join()

    def test_missing_artifacts_are_downloaded_and_verified(self):
        with self.server() as requests:
            receipt = runtime.fetch_runtime(self.output)
        self.assertCountEqual(requests, self.payloads)
        self.assertEqual(len(receipt), 3)
        for entry in self.lock["artifacts"]:
            self.assertEqual((self.output / entry["path"]).read_bytes(), self.payloads[entry["name"]])

    def test_missing_upstream_artifact_fails_without_partial_install(self):
        with self.server({"libproot.so": self.payloads["libproot.so"]}):
            with self.assertRaises(runtime.ArtifactError):
                runtime.fetch_runtime(self.output)
        self.assertFalse((self.output / "arm64-v8a/libproot.so").exists())
        self.assertEqual(list(self.output.rglob("*.part")), [])

    def test_checksum_mismatch_fails_without_installing_any_artifact(self):
        corrupt = dict(self.payloads, **{"libproot_loader.so": b"x" * len(self.payloads["libproot_loader.so"])})
        with self.server(corrupt):
            with self.assertRaisesRegex(runtime.ArtifactError, "SHA-256"):
                runtime.fetch_runtime(self.output)
        self.assertFalse((self.output / "arm64-v8a/libproot.so").exists())
        self.assertFalse((self.output / "rootfs.tar.gz").exists())

    def test_failed_update_preserves_existing_verified_cache(self):
        with self.server():
            runtime.fetch_runtime(self.output)
        before = {entry["path"]: (self.output / entry["path"]).read_bytes() for entry in self.lock["artifacts"]}
        updated = elf() + b"new release"
        self.lock["artifacts"][0] = locked_artifact("libproot.so", updated)
        self.lock_path.write_text(json.dumps(self.lock), encoding="utf-8")
        with self.server():
            with self.assertRaises(runtime.ArtifactError):
                runtime.fetch_runtime(self.output)
        for name, body in before.items():
            self.assertEqual((self.output / name).read_bytes(), body)

    def test_upstream_http_error_closes_response(self):
        with self.server({"libproot.so": self.payloads["libproot.so"]}):
            with self.assertRaises(runtime.ArtifactError) as caught:
                runtime.fetch_runtime(self.output)
            self.assertIsInstance(caught.exception.__cause__, urllib.error.HTTPError)
            self.assertTrue(caught.exception.__cause__.fp.closed)

    def test_redirect_is_refused_before_following_an_unlocked_url(self):
        responses = dict(self.payloads)
        responses["libproot.so"] = {"redirect": "https://example.org/unlocked.so"}
        with self.server(responses) as requests:
            with self.assertRaisesRegex(runtime.ArtifactError, "Redirect"):
                runtime.fetch_runtime(self.output)
        self.assertEqual(requests, ["libproot.so"])
        self.assertFalse((self.output / "arm64-v8a/libproot.so").exists())

    def test_stream_without_content_length_is_still_bounded(self):
        responses = dict(self.payloads)
        responses["libproot.so"] = {"body": self.payloads["libproot.so"] + b"extra", "content_length": False}
        with self.server(responses):
            with self.assertRaisesRegex(runtime.ArtifactError, "size"):
                runtime.fetch_runtime(self.output)
        self.assertFalse((self.output / "arm64-v8a/libproot.so").exists())

    def test_verified_cache_is_reused_without_network(self):
        with self.server():
            runtime.fetch_runtime(self.output)
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("unexpected network")):
            receipt = runtime.fetch_runtime(self.output)
        self.assertEqual(len(receipt), 3)

    def test_rejects_wrong_elf_architecture_even_with_matching_checksum(self):
        body = elf(62)
        self.payloads["libproot.so"] = body
        self.lock["artifacts"][0] = locked_artifact("libproot.so", body)
        self.lock_path.write_text(json.dumps(self.lock), encoding="utf-8")
        with self.server():
            with self.assertRaisesRegex(runtime.ArtifactError, "AArch64"):
                runtime.fetch_runtime(self.output)
        self.assertFalse((self.output / "arm64-v8a/libproot.so").exists())

    def test_oversize_response_is_rejected_before_replacing_cache(self):
        corrupt = dict(self.payloads, **{"libproot.so": self.payloads["libproot.so"] + b"extra"})
        with self.server(corrupt):
            with self.assertRaisesRegex(runtime.ArtifactError, "size"):
                runtime.fetch_runtime(self.output)
        self.assertFalse((self.output / "arm64-v8a/libproot.so").exists())

    def test_rejects_non_https_sources_before_network(self):
        self.lock["artifacts"][0]["url"] = "http://example.org/libproot.so"
        self.lock_path.write_text(json.dumps(self.lock), encoding="utf-8")
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("unexpected network")):
            with self.assertRaisesRegex(runtime.ArtifactError, "HTTPS"):
                runtime.fetch_runtime(self.output)

    def test_rejects_unlocked_https_host_before_network(self):
        self.lock["artifacts"][0]["url"] = "https://example.org/libproot.so"
        self.lock_path.write_text(json.dumps(self.lock), encoding="utf-8")
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("unexpected network")):
            with self.assertRaisesRegex(runtime.ArtifactError, "immutable HTTPS"):
                runtime.fetch_runtime(self.output)

    def test_rejects_rootfs_version_even_with_matching_checksum(self):
        body = rootfs(b"3.22.5\n")
        self.payloads["rootfs.tar.gz"] = body
        self.lock["artifacts"][2] = locked_artifact("rootfs.tar.gz", body)
        self.lock_path.write_text(json.dumps(self.lock), encoding="utf-8")
        with self.server():
            with self.assertRaisesRegex(runtime.ArtifactError, "Alpine 3.22.6"):
                runtime.fetch_runtime(self.output)
        self.assertFalse((self.output / "rootfs.tar.gz").exists())

    def test_rejects_symlinked_native_destination(self):
        self.output.mkdir()
        outside = self.directory / "outside"
        outside.mkdir()
        (self.output / "arm64-v8a").symlink_to(outside, target_is_directory=True)
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("unexpected network")):
            with self.assertRaisesRegex(runtime.ArtifactError, "path"):
                runtime.fetch_runtime(self.output)
        self.assertEqual(list(outside.iterdir()), [])

    def test_rejects_destination_escape_before_network(self):
        self.lock["artifacts"][0]["path"] = "../escaped.so"
        self.lock_path.write_text(json.dumps(self.lock), encoding="utf-8")
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("unexpected network")):
            with self.assertRaisesRegex(runtime.ArtifactError, "path"):
                runtime.fetch_runtime(self.output)
        self.assertFalse((self.directory / "escaped.so").exists())


if __name__ == "__main__":
    unittest.main()
