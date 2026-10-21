"""Exercise builder publication with isolated toolchains; no product builds."""
import hashlib
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
FLAGS = ["-Wl,-z,max-page-size=16384", "-Wl,-z,common-page-size=16384"]

# A compiler boundary double records the actual link invocation and emits a
# hand-constructed ARM64 ELF. Its two page properties independently depend on
# the two flags, so omitting either produces an unacceptable artifact.
TOOL = r'''import json, os, pathlib, shlex, struct, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if name == "rustc":
    print("rustc fixture")
    sys.exit(0)
if name == "llvm-readelf":
    print("1: 0000000000001000 0 FUNC GLOBAL DEFAULT 1 _start")
    print("2: 0000000000001020 0 FUNC GLOBAL DEFAULT 1 pokedata_workaround")
    sys.exit(0)
if name in ("llvm-strip", "llvm-ar"):
    sys.exit(0)
if name == "cargo":
    encoded = os.environ.get("CARGO_ENCODED_RUSTFLAGS")
    flags = encoded.split("\x1f") if encoded is not None else shlex.split(
        os.environ.get("RUSTFLAGS", os.environ.get(
            "CARGO_TARGET_AARCH64_LINUX_ANDROID_RUSTFLAGS", "")))
    args = [value.removeprefix("link-arg=") for value in flags]
    output = pathlib.Path(os.environ["CARGO_TARGET_DIR"]) / (
        "aarch64-linux-android/release/libloopy_wayland.so")
else:
    output = pathlib.Path(args[args.index("-o") + 1])
with open(os.environ["TEST_LINK_LOG"], "a") as log:
    log.write(json.dumps({"output": str(output), "argv": args}) + "\n")
align = 16384 if "-Wl,-z,max-page-size=16384" in args else 4096
end = 16384 if "-Wl,-z,common-page-size=16384" in args else 8192
if os.environ.get("TEST_BAD_ELF") == "load": align = 4096
if os.environ.get("TEST_BAD_ELF") == "relro": end = 8192
if os.environ.get("TEST_BAD_LOADER") and output.name == "loader": end = 8192
data = bytearray(256)
data[:6] = b"\x7fELF\x02\x01"
struct.pack_into("<HH", data, 16, 2 if output.name == "loader" else 3, 183)
struct.pack_into("<Q", data, 32, 64)
struct.pack_into("<HHH", data, 52, 64, 56, 2)
struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0, 0, 256, 16384, align)
struct.pack_into("<IIQQQQQQ", data, 120, 0x6474e552, 4, 0, 0, 0, 0, end, 1)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(data)
changed = os.environ.get("TEST_MUTATE_PATH")
if changed:
    path = pathlib.Path(changed)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(path.read_bytes() + b"changed" if path.exists() else b"added")
'''

# The pinned upstream loader uses LOADER_LDFLAGS, bypassing LDFLAGS. Keep that
# distinction while using actual make to exercise how the builder supplies LD.
MAKEFILE = '''CC ?= gcc
LD = $(CC)
LDFLAGS += -ltalloc -Wl,-z,noexecstack
LOADER_LDFLAGS += -static -nostdlib -Wl,-Ttext=0x200000,--rosegment,-z,noexecstack
proot:
\t$(LD) -o $@ $(LDFLAGS)
loader/loader:
\t$(LD) -o $@ $(LOADER_LDFLAGS)
'''


class NativeBuildAlignmentTests(unittest.TestCase):
    def fixture(self, *, bad=None, mutate=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        name = "build_proot_compat"
        spec = importlib.util.spec_from_file_location(name, REPO / "tools" / (name + ".py"))
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        builder.ROOT = root
        for relative in ("tools/" + name + ".py", "tools/android_elf.py"):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((REPO / relative).read_bytes())
        builder.__file__ = str(root / "tools" / (name + ".py"))
        ndk = root / "ndk/27.1.12297006"
        ndk.mkdir(parents=True)
        (ndk / "source.properties").write_text("Pkg.Revision = 27.1.12297006\n")
        bin_dir = ndk / "toolchains/llvm/prebuilt/darwin-x86_64/bin"
        bin_dir.mkdir(parents=True)
        for executable in ("aarch64-linux-android28-clang", "aarch64-linux-android21-clang",
                           "llvm-ar", "llvm-strip", "llvm-objcopy", "llvm-objdump",
                           "llvm-readelf", "cargo", "rustc"):
            path = bin_dir / executable
            path.write_text("#!" + sys.executable + "\n" + TOOL)
            path.chmod(0o755)
        if sys.platform != "darwin":
            (bin_dir.parents[1] / "linux-x86_64").symlink_to(bin_dir.parent, target_is_directory=True)
        log = root / "links.jsonl"
        env = {"ANDROID_NDK_HOME": str(ndk), "TEST_LINK_LOG": str(log),
               "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
               "RUSTFLAGS": "-C link-arg=-Wl,-z,max-page-size=4096",
               "CARGO_ENCODED_RUSTFLAGS": "-C\x1flink-arg=-Wl,-z,max-page-size=4096"}
        if bad:
            env["TEST_BAD_ELF"] = bad
        builder.BUILD = root / "build/proot-compat"
        builder.LOCK = root / "third_party/runtime.lock.json"
        patch_dir = root / "native/proot-compat"
        patch_dir.mkdir(parents=True)
        patch_paths = []
        for name in builder.PATCH_NAMES:
            path = patch_dir / name
            if path == patch_dir / builder.PATCH_NAMES[0]:
                path.write_text("--- a/src/tracee/event.c\n+++ b/src/tracee/event.c\n"
                                "@@ -1 +1 @@\n-old\n+patched\n")
            else:
                path.write_text("--- a/src/tracee/event.c\n+++ b/src/tracee/event.c\n"
                                "@@ -1,0 +2 @@\n+extra\n")
            patch_paths.append(path)
        builder.LOCK.parent.mkdir(parents=True)
        builder.LOCK.write_text("{}\n")
        source = root / "upstream/proot"
        (source / "src/tracee").mkdir(parents=True)
        (source / "src/loader").mkdir()
        (source / "src/tracee/event.c").write_text("old\n")
        (source / "src/tracee/seccomp.c").write_text("seccomp\n")
        (source / "src/GNUmakefile").write_text(MAKEFILE)
        talloc = root / "upstream/talloc"
        talloc.mkdir()
        for relative in ("talloc.c", "talloc.h"):
            (talloc / relative).write_text("source\n")
        builder.checkout_pinned_source = lambda: (source, talloc)
        # The fixture pins its own upstream bytes; the reviewed real-world hash
        # belongs to the vendored tree the lambda replaces.
        builder.EVENT_SHA256 = hashlib.sha256((source / "src/tracee/event.c").read_bytes()).hexdigest()
        changed = patch_paths[0]
        output = builder.BUILD / "arm64-v8a/libproot.so"
        receipt = builder.BUILD / "build-receipt.json"
        invoke = builder.main
        if mutate:
            env["TEST_MUTATE_PATH"] = str(changed)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"previous accepted artifact")
        receipt.write_text("previous accepted receipt")
        return builder, root, env, output, receipt, log, invoke

    def test_all_real_link_paths_get_both_page_options_and_verified_receipts(self):
        builder, root, env, output, receipt, log, invoke = self.fixture()
        with patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()):
            invoke()
        self.assertEqual(struct.unpack_from("<Q", output.read_bytes(), 112)[0], 16384)
        self.assertEqual(struct.unpack_from("<Q", output.read_bytes(), 160)[0], 16384)
        links = [json.loads(line) for line in log.read_text().splitlines()]
        targets = [link for link in links if "-c" not in link["argv"]]
        for link in targets:
            for flag in FLAGS:
                self.assertIn(flag, link["argv"], link["output"])
        self.assertEqual({Path(link["output"]).name for link in targets}, {"proot", "loader"})
        loader = output.with_name("libproot_loader.so")
        self.assertEqual(struct.unpack_from("<Q", loader.read_bytes(), 112)[0], 16384)
        data = json.loads(receipt.read_text())
        inputs = data.get("sources_sha256", data.get("inputs", {}))
        self.assertIn("tools/android_elf.py", inputs)
        self.assertEqual(inputs["tools/android_elf.py"], hashlib.sha256(
            (root / "tools/android_elf.py").read_bytes()).hexdigest())
        self.assertEqual(data["elf"]["page_size"], 16384)

    def test_bad_load_or_relro_is_rejected_without_replacing_previous_outputs(self):
        for defect in ("load", "relro"):
            with self.subTest(defect=defect):
                _, _, env, output, receipt, _, invoke = self.fixture(bad=defect)
                with patch.dict(os.environ, env), self.assertRaises((ValueError, RuntimeError)):
                    invoke()
                self.assertEqual(output.read_bytes(), b"previous accepted artifact")
                self.assertEqual(receipt.read_text(), "previous accepted receipt")

    def test_source_change_during_link_is_rejected_before_publication(self):
        _, _, env, output, receipt, _, invoke = self.fixture(mutate="changed")
        with patch.dict(os.environ, env), self.assertRaisesRegex(RuntimeError, "[Ss]ource.*chang"):
            invoke()
        self.assertEqual(output.read_bytes(), b"previous accepted artifact")
        self.assertEqual(receipt.read_text(), "previous accepted receipt")

    def test_verifier_change_during_link_also_invalidates_all_builder_receipts(self):
        _, root, env, output, receipt, _, invoke = self.fixture()
        env["TEST_MUTATE_PATH"] = str(root / "tools/android_elf.py")
        with patch.dict(os.environ, env), self.assertRaisesRegex(RuntimeError, "[Ss]ource.*chang"):
            invoke()
        self.assertEqual(output.read_bytes(), b"previous accepted artifact")
        self.assertEqual(receipt.read_text(), "previous accepted receipt")

    def test_upstream_change_during_proot_link_keeps_previous_artifacts(self):
        _, root, env, output, receipt, _, invoke = self.fixture()
        env["TEST_MUTATE_PATH"] = str(root / "upstream/talloc/talloc.c")
        with patch.dict(os.environ, env), self.assertRaisesRegex(RuntimeError, "[Ss]ource.*chang"):
            invoke()
        self.assertEqual(output.read_bytes(), b"previous accepted artifact")
        self.assertEqual(receipt.read_text(), "previous accepted receipt")

    def test_loader_only_bad_relro_keeps_both_previous_proot_artifacts(self):
        _, _, env, output, receipt, _, invoke = self.fixture()
        loader = output.with_name("libproot_loader.so")
        loader.write_bytes(b"previous accepted loader")
        env["TEST_BAD_LOADER"] = "1"
        with patch.dict(os.environ, env), self.assertRaisesRegex(ValueError, "GNU_RELRO"):
            invoke()
        self.assertEqual(output.read_bytes(), b"previous accepted artifact")
        self.assertEqual(loader.read_bytes(), b"previous accepted loader")
        self.assertEqual(receipt.read_text(), "previous accepted receipt")


if __name__ == "__main__":
    unittest.main()
