"""Portable source checks; these tests do not execute Android or build an APK."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "input/build.py"


class SourceContractTests(unittest.TestCase):
    def test_inventory_verifies_promoted_sources(self):
        self.assertTrue(ENTRYPOINT.is_file(), "portable source entrypoint missing")
        spec = importlib.util.spec_from_file_location("input_build", ENTRYPOINT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = module.check_sources(ROOT)
        self.assertEqual(report["status"], "SOURCE_INVENTORY_VERIFIED")
        self.assertFalse(report["correspondingSourceComplete"])
        self.assertFalse(report["apkRebuildVerified"])

    def test_build_fails_closed_without_creating_outputs(self):
        result = subprocess.run([sys.executable, "-B", str(ENTRYPOINT), "--build"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("APK_BUILD_BLOCKED", result.stderr)
        self.assertIn("native-source-closure", result.stderr)
        self.assertFalse((ROOT / "input/artifact").exists())

    def test_current_helper_and_all_predecessor_patchers_present(self):
        manifest = json.loads((ROOT / "manifests/input-sources.json").read_text())
        self.assertEqual(manifest["upstream"]["commit"],
                         "6d3c6883265b4ec8092673e6d2d61ef86cab5405")
        expected = {"termux_x11_process.py", "PatchZoomDex.java", "PatchScrollDex.java",
                    "PatchLifecycleDex.java", "PatchHandoffDex.java"}
        self.assertTrue(expected <= {p.name for p in (ROOT / "input/patchers").iterdir()})
        helper = ROOT / "input/src/com/termux/x11/utils/KeyBridgeHandoff.java"
        self.assertEqual(hashlib.sha256(helper.read_bytes()).hexdigest(),
                         "2efc5f42701641e9f0b1bba63367b086423db39f3016e56cef47e4c1f4985304")

    def test_input_distribution_contains_no_machine_paths_or_binary_artifacts(self):
        forbidden_suffixes = {".apk", ".so", ".dex", ".class", ".jar", ".jks", ".keystore", ".pyc"}
        for directory in (ROOT / "input", ROOT / "tests/input"):
            for path in directory.rglob("*"):
                if not path.is_file():
                    continue
                self.assertNotIn(path.suffix, forbidden_suffixes, str(path.relative_to(ROOT)))
                self.assertFalse(path.is_symlink(), str(path.relative_to(ROOT)))
                text = path.read_text()
                # Keep the test itself portable while detecting former machine paths.
                self.assertNotIn("/" + "Users/", text, str(path.relative_to(ROOT)))
                self.assertNotIn("/" + "Applications/", text, str(path.relative_to(ROOT)))
        self.assertFalse(any((ROOT / "input").rglob("*.opt-in")))


if __name__ == "__main__":
    unittest.main()
