"""Offline checks of full-source build boundaries; no Android build or device calls."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "input/full_build/driver.py"


def module():
    if not DRIVER.is_file():
        raise AssertionError("full-source build driver is missing")
    spec = importlib.util.spec_from_file_location("full_build_driver", DRIVER)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def archive_module():
    path = ROOT / "input/full_build/archive.py"
    if not path.is_file():
        raise AssertionError("corresponding-source archive helper is missing")
    spec = importlib.util.spec_from_file_location("full_build_archive", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def runtime_module():
    path = ROOT / "input/full_build/runtime_sources.py"
    if not path.is_file():
        raise AssertionError("runtime source helper is missing")
    spec = importlib.util.spec_from_file_location("runtime_sources", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def resource_module():
    path = ROOT / "input/full_build/resource_inputs.py"
    if not path.is_file():
        raise AssertionError("runtime resource input helper is missing")
    spec = importlib.util.spec_from_file_location("resource_inputs", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class FullBuildTests(unittest.TestCase):
    def test_public_overlay_hash_is_checked_before_network_or_output(self):
        driver = module()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for relative in ("manifests/input-sources.json", "manifests/input-toolchain.json",
                             "input/patches/termux-x11-input.patch"):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            self.assertEqual(driver.verify_inputs(root)["upstreamCommit"], driver.UPSTREAM_COMMIT)
            with (root / "input/patches/termux-x11-input.patch").open("a") as stream:
                stream.write("\nchanged\n")
            with self.assertRaisesRegex(ValueError, "overlay-hash-mismatch"):
                driver.verify_inputs(root)

    def test_wrong_upstream_or_incomplete_native_pins_are_refused(self):
        driver = module()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            shutil.copytree(ROOT / "manifests", root / "manifests")
            shutil.copytree(ROOT / "input/patches", root / "input/patches")
            path = root / "manifests/input-sources.json"
            data = json.loads(path.read_text())
            data["upstream"]["commit"] = "0" * 40
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "upstream-pin-mismatch"):
                driver.verify_inputs(root)
            shutil.copyfile(ROOT / "manifests/input-sources.json", path)
            path = root / "manifests/input-toolchain.json"
            data = json.loads(path.read_text())
            data["pinnedUpstreamFullBuild"]["submodules"].pop()
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "native-pin-set-mismatch"):
                driver.verify_inputs(root)

    def test_native_gitlinks_must_match_exact_commit_and_path(self):
        driver = module()
        pins = [{"path": "lorie/src/main/cpp/test", "commit": "a" * 40}]
        tree = "160000 commit " + "a" * 40 + "\tlorie/src/main/cpp/test\n"
        driver.verify_gitlinks(tree, pins)
        for bad in (tree.replace("a" * 40, "b" * 40), tree + tree, ""):
            with self.subTest(tree=bad), self.assertRaisesRegex(ValueError, "native-gitlinks-mismatch"):
                driver.verify_gitlinks(bad, pins)

    def test_build_environment_isolates_sdk_and_cache_and_drops_injected_options(self):
        driver = module()
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            env = driver.build_environment(base, base / "jdk", {
                "PATH": "/usr/bin", "HOME": "/home/example", "GRADLE_USER_HOME": "/host/cache",
                "ANDROID_HOME": "/host/sdk", "JAVA_TOOL_OPTIONS": "-javaagent:untrusted.jar",
                "ANDROID_SDK_ROOT": "/host/sdk", "GRADLE_OPTS": "untrusted",
                "SECRET_TOKEN": "synthetic-secret",
            })
            self.assertEqual(env["ANDROID_HOME"], str(base / "sdk"))
            self.assertEqual(env["ANDROID_SDK_ROOT"], str(base / "sdk"))
            self.assertEqual(env["GRADLE_USER_HOME"], str(base / "gradle"))
            self.assertEqual(env["ANDROID_USER_HOME"], str(base / "android-user"))
            self.assertEqual(env["HOME"], "/home/example")
            for key in ("JAVA_TOOL_OPTIONS", "GRADLE_OPTS", "SECRET_TOKEN"):
                self.assertNotIn(key, env)

    def test_sdk_copy_never_modifies_source_and_never_accepts_licenses(self):
        driver = module()
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            source, destination = base / "host-sdk", base / "attempt/sdk"
            for relative in driver.SDK_COPY_DIRECTORIES:
                path = source / relative
                path.mkdir(parents=True)
                (path / "source.properties").write_text("synthetic-package\n")
            license_path = source / "licenses/android-sdk-license"
            license_path.parent.mkdir()
            license_path.write_text("synthetic accepted hash\n")
            before = hashlib.sha256(license_path.read_bytes()).hexdigest()
            receipt = driver.copy_sdk(source, destination)
            self.assertEqual(hashlib.sha256(license_path.read_bytes()).hexdigest(), before)
            self.assertEqual((destination / "licenses/android-sdk-license").read_bytes(), license_path.read_bytes())
            self.assertEqual(receipt["licenseSHA256"]["android-sdk-license"], before)
            self.assertFalse(receipt["acceptedNewLicenses"])
            with self.assertRaises(FileExistsError):
                driver.copy_sdk(source, destination)
            with self.assertRaisesRegex(ValueError, "sdk-source-destination-overlap"):
                driver.copy_sdk(source, source / "nested")

    def test_unsigned_artifacts_are_distinct_from_installable_releases(self):
        driver = module()
        with tempfile.TemporaryDirectory() as name:
            apk = Path(name) / "synthetic.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"synthetic manifest")
                archive.writestr("classes.dex", b"synthetic dex")
                archive.writestr("lib/arm64-v8a/libXlorie.so", b"synthetic elf")
            artifact = driver.inspect_unsigned_apk(apk)
            self.assertFalse(artifact["signed"])
            self.assertFalse(artifact["installableRelease"])
            with zipfile.ZipFile(apk, "a") as archive:
                archive.writestr("META-INF/CERT.RSA", b"synthetic signature")
            with self.assertRaisesRegex(ValueError, "signed-apk-refused"):
                driver.inspect_unsigned_apk(apk)

    def test_signing_magic_inside_an_asset_is_not_a_signing_block(self):
        driver = module()
        with tempfile.TemporaryDirectory() as name:
            apk = Path(name) / "synthetic.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"synthetic manifest")
                archive.writestr("classes.dex", b"synthetic dex")
                archive.writestr("lib/arm64-v8a/libXlorie.so", b"synthetic elf")
                archive.writestr("assets/example.txt", b"APK Sig Block 42")
            self.assertFalse(driver.inspect_unsigned_apk(apk)["signed"])

    def test_existing_exact_ndk_is_copied_into_an_isolated_sdk(self):
        driver = module()
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            source, destination = base / "host-sdk", base / "attempt/sdk"
            for relative in driver.SDK_COPY_DIRECTORIES:
                path = source / relative
                path.mkdir(parents=True)
                (path / "source.properties").write_text("synthetic-package\n")
            (source / "licenses").mkdir()
            (source / "licenses/android-sdk-license").write_text("synthetic accepted hash\n")
            ndk_relative = "ndk/" + driver.NDK_PACKAGE.split(";")[1]
            ndk = source / ndk_relative
            ndk.mkdir(parents=True)
            (ndk / "source.properties").write_text("Pkg.Revision = 29.0.14206865\n")
            receipt = driver.copy_sdk(source, destination)
            self.assertTrue((destination / ndk_relative / "source.properties").is_file())
            self.assertIn(ndk_relative, receipt["copiedPackages"])
            self.assertIn(ndk_relative, receipt["packageMetadataSHA256"])

    def test_native_patch_probe_does_not_auto_reverse_an_unpatched_source(self):
        driver = module()
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            target = base / "example.txt"
            target.write_text("alpha\n")
            patch = base / "example.patch"
            patch.write_text("--- a/example.txt\n+++ b/example.txt\n@@ -1 +1 @@\n-alpha\n+beta\n")
            env, identity = driver.native_patch_environment(base, {"PATH": os.environ["PATH"]})
            command = ["patch", "-p1", "-d", str(base), "-i", str(patch)]
            before = subprocess.run([*command, "-R", "--dry-run"], env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True)
            self.assertNotEqual(before.returncode, 0, "unpatched source must not look reverse-applicable")
            self.assertEqual(target.read_text(), "alpha\n")
            applied = subprocess.run([*command, "-N"], env=env, stdin=subprocess.DEVNULL,
                                     capture_output=True, text=True)
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            self.assertEqual(target.read_text(), "beta\n")
            after = subprocess.run([*command, "-R", "--dry-run"], env=env, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True)
            self.assertEqual(after.returncode, 0)
            self.assertTrue(identity["forceReverseProbe"])

    def test_loader_signature_metadata_is_derived_from_public_certificate_only(self):
        driver = module()
        metadata = driver.certificate_metadata()
        self.assertEqual(metadata["certificateSHA256"],
                         "b6da01480eefd5fbf2cd3771b8d1021ec791304bdd6c4bf41d3faabad48ee5e1")
        self.assertEqual(metadata["javaArraysHashCode"], -611922116)
        with tempfile.TemporaryDirectory() as name:
            pem = Path(name) / "certificate.pem"
            pem.write_text("-----BEGIN " + "PRIVATE KEY-----\nsynthetic\n-----END " + "PRIVATE KEY-----\n")
            with self.assertRaisesRegex(ValueError, "public-certificate-required"):
                driver.certificate_metadata(pem)

    def test_failed_command_records_actual_exit_without_claiming_a_build(self):
        driver = module()
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            recorder = driver.Recorder(base)
            with self.assertRaisesRegex(RuntimeError, "fixture-failure"):
                recorder.run("fixture-failure", ["sh", "-c", "exit 7"], cwd=base)
            self.assertEqual(recorder.steps[0]["exitCode"], 7)
            self.assertEqual(recorder.steps[0]["status"], "FAILED")
            self.assertTrue((base / recorder.steps[0]["log"]).is_file())

    def test_archive_export_uses_committed_sources_and_verified_postimages_only(self):
        helper = archive_module()
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            source = base / "git-source"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            for relative, content in (("source.c", "original\n"), ("LICENSE", "license text\n"),
                                      (".gitattributes", "LICENSE export-ignore\n"),
                                      ("example.jks", "synthetic key container\n")):
                (source / relative).write_text(content)
            subprocess.run(["git", "-C", str(source), "add", "."], check=True)
            subprocess.run(["git", "-C", str(source), "-c", "user.name=Source Test",
                            "-c", "user.email=source-test@example.invalid", "commit", "-qm", "fixture"], check=True)
            commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
            (source / "source.c").write_text("prepared overlay\n")
            (source / "private-untracked.txt").write_text("synthetic private data\n")
            destination = base / "export"
            helper.export_git_tree(source, commit, destination)
            self.assertEqual((destination / "source.c").read_text(), "original\n")
            self.assertTrue((destination / "LICENSE").is_file())
            self.assertFalse((destination / "example.jks").exists())
            self.assertFalse((destination / "private-untracked.txt").exists())
            digest = hashlib.sha256((source / "source.c").read_bytes()).hexdigest()
            helper.apply_postimages(source, destination, {"source.c": digest})
            self.assertEqual((destination / "source.c").read_text(), "prepared overlay\n")
            with self.assertRaisesRegex(ValueError, "postimage-hash-mismatch"):
                helper.apply_postimages(source, destination, {"source.c": "0" * 64})

    def test_source_manifest_refuses_tampering_extra_files_and_traversal(self):
        helper = archive_module()
        with tempfile.TemporaryDirectory() as name:
            tree = Path(name)
            (tree / "LICENSE").write_text("synthetic license\n")
            helper.write_manifest(tree, {"upstreamCommit": "a" * 40})
            helper.verify_tree(tree)
            (tree / "extra.txt").write_text("unrecorded\n")
            with self.assertRaisesRegex(ValueError, "manifest-file-set-mismatch"):
                helper.verify_tree(tree)
            (tree / "extra.txt").unlink()
            (tree / "LICENSE").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "manifest-content-mismatch"):
                helper.verify_tree(tree)
            for path in ("../escape", "/absolute", "nested/../escape"):
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "unsafe-source-path"):
                    helper.safe_relative(path)

    def test_companion_payload_receipt_pins_scripts_loader_and_permissions(self):
        driver = module()
        with tempfile.TemporaryDirectory() as name:
            data = io.BytesIO()
            prefix = "./data/data/com.termux/files/usr/"
            with tarfile.open(fileobj=data, mode="w:xz") as archive:
                for relative, mode in (("bin/termux-x11", 0o755), ("bin/termux-x11-preference", 0o755),
                                       ("libexec/termux-x11/loader.apk", 0o644)):
                    content = relative.encode()
                    entry = tarfile.TarInfo(prefix + relative)
                    entry.size, entry.mode = len(content), mode
                    archive.addfile(entry, io.BytesIO(content))
            members = {"debian-binary": b"2.0\n", "data.tar.xz": data.getvalue()}
            raw = b"!<arch>\n"
            for member, content in members.items():
                header = f"{member + '/':<16}{0:<12}{0:<6}{0:<6}{'100644':<8}{len(content):<10}`\n".encode()
                raw += header + content + (b"\n" if len(content) % 2 else b"")
            path = Path(name) / "companion.deb"
            path.write_bytes(raw)
            payload = driver.inspect_companion(path)
            self.assertEqual(set(payload), {"bin/termux-x11", "bin/termux-x11-preference", "libexec/termux-x11/loader.apk"})
            self.assertEqual(payload["bin/termux-x11"]["archiveMode"], "0755")
            self.assertEqual(payload["libexec/termux-x11/loader.apk"]["installedMode"], "0400")
            self.assertEqual(payload["bin/termux-x11"]["sha256"], hashlib.sha256(b"bin/termux-x11").hexdigest())

    def test_dependency_notices_preserve_legal_texts_without_cached_binaries(self):
        helper = archive_module()
        with tempfile.TemporaryDirectory() as name:
            work = Path(name)
            base = work / "gradle/caches/modules-2/files-2.1/example/library/1/hash"
            base.mkdir(parents=True)
            (base / "library.pom").write_text("<project>synthetic metadata</project>\n")
            with zipfile.ZipFile(base / "library.jar", "w") as archive:
                archive.writestr("META-INF/LICENSE.txt", b"synthetic legal text\n")
                archive.writestr("example/Library.class", b"synthetic class\n")
                archive.writestr("example/dependencies/Helper.class", b"synthetic class\n")
            destination = work / "notices"
            helper.copy_dependency_notices(work, destination)
            self.assertEqual((destination / "embedded/example/library/1/hash/library.jar/META-INF/LICENSE.txt").read_bytes(),
                             b"synthetic legal text\n")
            self.assertTrue((destination / "poms/example/library/1/hash/library.pom").is_file())
            self.assertFalse(any(path.suffix == ".class" for path in destination.rglob("*")))

    def test_runtime_sources_use_official_exact_coordinates_and_declared_licenses(self):
        helper = runtime_module()
        row = {"group": "androidx.example", "artifact": "example", "version": "1.2.3"}
        self.assertEqual(helper.source_url(row),
                         "https://dl.google.com/dl/android/maven2/androidx/example/example/1.2.3/example-1.2.3-sources.jar")
        row["group"] = "org.example"
        self.assertEqual(helper.source_url(row),
                         "https://repo.maven.apache.org/maven2/org/example/example/1.2.3/example-1.2.3-sources.jar")
        licenses = helper.pom_licenses(b'<project xmlns="http://maven.apache.org/POM/4.0.0"><licenses><license>'
                                     b'<name>Apache 2.0</name><url>https://www.apache.org/licenses/LICENSE-2.0</url>'
                                     b'</license></licenses></project>')
        self.assertEqual(licenses, [{"name": "Apache 2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0"}])

    def test_source_export_excludes_release_manifests_to_avoid_archive_hash_cycles(self):
        helper = archive_module()
        self.assertFalse(helper.excluded("java-runtime-sources/androidx.activity/activity/1/resource-inputs/META-INF/com/android/build/gradle/aar-metadata.properties"))
        self.assertTrue(helper.excluded("upstream/lorie/build/generated/Example.java"))
        self.assertTrue(helper.excluded("java-runtime-sources/example/library/1/build/generated/Example.java"))
        for name in ("input/full_build/driver.py", "tests/input/test_full_build.py", "LICENSE", "NOTICE.md",
                     "legal/licenses/termux-x11-GPL-3.0.txt", "manifests/input-sources.json", "manifests/input-toolchain.json"):
            self.assertTrue(helper.project_source_path(name), name)
        for name in ("manifests/distribution.json", "manifests/downloads.json", "manifests/runtime-sources.json",
                     "runtime/bootstrap.sh", "tests/runtime/test_install.py"):
            self.assertFalse(helper.project_source_path(name), name)

    def test_runtime_source_jars_require_source_and_refuse_binary_or_unsafe_members(self):
        helper = runtime_module()
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "library-sources.jar"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("example/Library.kt", b"// synthetic source\n")
                archive.writestr("META-INF/LICENSE", b"synthetic license\n")
            self.assertEqual(helper.inspect_source_jar(path)["sourceFiles"], 1)
            with zipfile.ZipFile(path, "a") as archive:
                archive.writestr("../escape.java", b"synthetic source\n")
            with self.assertRaisesRegex(ValueError, "unsafe-runtime-source-member"):
                helper.inspect_source_jar(path)

    def test_runtime_license_inheritance_keeps_parent_pom_identity(self):
        helper = runtime_module()
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            cache = base / "cache"
            parent = cache / "org.example/parent/1/hash/parent-1.pom"
            parent.parent.mkdir(parents=True)
            parent.write_text('<project><licenses><license><name>Apache 2.0</name>'
                              '<url>https://www.apache.org/licenses/LICENSE-2.0</url></license></licenses></project>')
            child = b'<project><parent><groupId>org.example</groupId><artifactId>parent</artifactId><version>1</version></parent></project>'
            output = base / "sources"
            output.mkdir()
            licenses, parents = helper.resolved_pom_licenses(child, cache, output)
            self.assertEqual(licenses[0]["name"], "Apache 2.0")
            self.assertEqual(parents[0]["pomSHA256"], hashlib.sha256(parent.read_bytes()).hexdigest())
            self.assertEqual((output / parents[0]["pomPath"]).read_bytes(), parent.read_bytes())

    def test_archive_runtime_sources_are_bound_to_candidate_and_verified_hashes(self):
        helper = archive_module()
        with tempfile.TemporaryDirectory() as name:
            work = Path(name)
            base = work / "runtime-source/org.example/library/1"
            base.mkdir(parents=True)
            (base / "sources.jar").write_bytes(b"synthetic source container")
            (base / "artifact.pom").write_bytes(b"synthetic pom")
            (base / "artifact.module").write_bytes(b"synthetic module metadata")
            resource = base / "resource-inputs/res/values/strings.xml"
            resource.parent.mkdir(parents=True)
            resource.write_bytes(b"<resources />\n")
            row = {"sourcePath": "org.example/library/1/sources.jar",
                   "sourceSHA256": hashlib.sha256((base / "sources.jar").read_bytes()).hexdigest(),
                   "pomSHA256": hashlib.sha256((base / "artifact.pom").read_bytes()).hexdigest()}
            row["moduleMetadata"] = {"path": "artifact.module", "sha256": hashlib.sha256((base / "artifact.module").read_bytes()).hexdigest()}
            row["resourceInputs"] = {"files": {"res/values/strings.xml": {"sha256": hashlib.sha256(resource.read_bytes()).hexdigest()}}}
            (work / "runtime-source/manifest.json").write_text(json.dumps({"status": "COMPLETE",
                "resourceInputsAudited": True, "resourceInputGaps": [],
                "candidateUnsignedAPKSHA256": "a" * 64, "dependencies": [row]}))
            helper.copy_runtime_sources(work, work / "export", "a" * 64)
            self.assertEqual((work / "export/org.example/library/1/resource-inputs/res/values/strings.xml").read_bytes(), resource.read_bytes())
            with self.assertRaisesRegex(ValueError, "complete-matching-runtime-sources-required"):
                helper.copy_runtime_sources(work, work / "wrong-candidate", "b" * 64)
            (base / "sources.jar").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "runtime-source-pin-mismatch"):
                helper.copy_runtime_sources(work, work / "tampered", "a" * 64)

    def test_aar_input_export_preserves_resources_and_detects_compiled_or_native_gaps(self):
        helper = resource_module()
        with tempfile.TemporaryDirectory() as name:
            work = Path(name)
            aar = work / "library.aar"
            with zipfile.ZipFile(aar, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"<manifest />\n")
                archive.writestr("res/values/strings.xml", b"<resources />\n")
                archive.writestr("R.txt", b"int string example 0\n")
                archive.writestr("classes.jar", b"synthetic compiled container")
            report = helper.export_aar_inputs(aar, work / "resources")
            self.assertFalse(report["gaps"])
            self.assertEqual((work / "resources/res/values/strings.xml").read_bytes(), b"<resources />\n")
            self.assertNotIn("classes.jar", report["files"])
            self.assertEqual(report["files"]["R.txt"]["sha256"], hashlib.sha256(b"int string example 0\n").hexdigest())
            with zipfile.ZipFile(aar, "a") as archive:
                archive.writestr("jni/arm64-v8a/libexample.so", b"synthetic native")
                archive.writestr("res/layout/binary.xml", b"\x03\x00\x08\x00binary xml")
            report = helper.export_aar_inputs(aar, work / "gaps")
            self.assertEqual({r["reason"] for r in report["gaps"]}, {"native-source-required", "preferred-resource-source-required"})


if __name__ == "__main__":
    unittest.main()
