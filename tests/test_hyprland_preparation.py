import json
from pathlib import Path
import tempfile
import unittest

from tools.build_hyprland_rootless import prepare


class HyprlandPreparationTests(unittest.TestCase):
    def test_actual_archive_patch_and_exact_build_dependencies_reproduce(self):
        root = Path(__file__).resolve().parents[1]
        lock = json.loads((root / "third_party/omarchy.lock.json").read_text())
        source = next(s for s in lock["graphics_sources"] if s["repo"] == "hyprwm/Hyprland")
        cache = root / "build/omarchy-sources"
        if not (cache / ("hyprland-" + source["commit"] + ".tar.gz")).is_file():
            self.skipTest("requires downloaded immutable sources")
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "candidate"
            receipt = prepare(root / "third_party/omarchy.lock.json", cache, output)
            self.assertEqual(receipt["upstream_commit"], source["commit"])
            self.assertFalse(receipt["omarchy_support_complete"])
            expected = root / "build/omarchy-sources/hyprland-shm"
            for name in ("src/render/OpenGL.cpp", "src/output/Monitor.cpp"):
                self.assertEqual((output / name).read_bytes(), (expected / name).read_bytes())
            for name in ("src/render/gl/LoopyShmReadback.cpp", "src/render/gl/LoopyShmReadback.hpp"):
                self.assertEqual((output / name).read_bytes(), (root / "native/omarchy/hyprland" / name).read_bytes())
            self.assertTrue((output / "subprojects/udis86/LICENSE").is_file())
            self.assertTrue((output / "subprojects/hyprland-protocols/LICENSE").is_file())
            self.assertTrue((output / "subprojects/loopy-glaze/LICENSE").is_file())
            with self.assertRaises(ValueError):
                prepare(root / "third_party/omarchy.lock.json", cache, output)


if __name__ == "__main__":
    unittest.main()
