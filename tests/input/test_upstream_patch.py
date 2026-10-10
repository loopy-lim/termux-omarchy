"""Apply intended source deltas to a pinned subset; this is not an Android build."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class UpstreamPatchTests(unittest.TestCase):
    def test_patch_applies_and_production_java_bytes_match(self):
        self.assertIsNotNone(shutil.which("patch"), "POSIX patch is required for this host test")
        with tempfile.TemporaryDirectory(prefix="termux-omarchy-patch-") as directory:
            tree = Path(directory) / "source"
            shutil.copytree(ROOT / "input/upstream", tree)
            with (ROOT / "input/patches/termux-x11-input.patch").open() as patch:
                result = subprocess.run(["patch", "-p1", "--batch"], cwd=tree, stdin=patch,
                                        capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for path in (ROOT / "input/src").rglob("*.java"):
                expected = tree / "lorie/src/main/java" / path.relative_to(ROOT / "input/src")
                self.assertEqual(expected.read_bytes(), path.read_bytes(), str(path.relative_to(ROOT)))
            activity = (tree / "lorie/src/main/java/com/termux/x11/MainActivity.java").read_text()
            self.assertEqual(activity.count("KeyBridgeHandoff.sendKeyEvent(this, mInputHandler, e)"), 1)
            self.assertEqual(activity.count("(v, k, e) -> mInputHandler.sendKeyEvent(e)"), 1,
                             "extra toolbar fallback should stay unchanged")
            shared = (tree / "lorie-app/src/sharedUid/AndroidManifest.xml").read_text()
            self.assertIn('<service android:name="com.termux.x11.utils.KeyInterceptor" android:process="com.termux" />', shared)
            header = (tree / "lorie/src/main/cpp/lorie/lorie.h").read_text()
            self.assertEqual(header.count("[ 204  /* ANDROID_KEYCODE_LANGUAGE_SWITCH */] = KEY_HANGEUL"), 1)


if __name__ == "__main__":
    unittest.main()
