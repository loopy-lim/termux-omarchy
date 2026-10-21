import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class RefreshBuildPreparationTests(unittest.TestCase):
    def test_fresh_candidate_prepares_both_guarded_patch_chains_and_preserves_existing_result(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="omarchy-refresh-test-", dir=root / "build") as temporary:
            candidate = Path(temporary)
            candidate.rmdir()
            command = [sys.executable, str(root / "tools/build_omarchy_refresh.py"),
                       "--prepare-only", "--output", str(candidate)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            for component, count in (("aquamarine", 6), ("hyprland", 6)):
                receipt = json.loads((candidate / (component + "-source") / "loopy-source-receipt.json").read_text())
                self.assertEqual(receipt["status"], "source-prepared")
                self.assertEqual(receipt["patches_applied"], count)
                self.assertTrue(receipt["source_files"])
            original = (candidate / "aquamarine-source/loopy-source-receipt.json").read_bytes()
            again = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual((candidate / "aquamarine-source/loopy-source-receipt.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
