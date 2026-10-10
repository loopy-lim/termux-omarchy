"""Adversarial publication checks on disposable source trees."""
import contextlib
import importlib.util
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("publication_check", ROOT / "tools/check_publication.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class PublicationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = (Path(self.temporary.name) / "source").resolve()
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns(
            ".git", "__pycache__", ".venv", "build", "cache", "dist", "local"))
        self.previous = checker.ROOT
        checker.ROOT = self.root

    def tearDown(self):
        checker.ROOT = self.previous
        self.temporary.cleanup()

    def inspect(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return checker.inspect_sources()

    def test_tracked_apk_in_ignored_directory_is_rejected(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        payload = self.root / "build/hidden.apk"
        payload.parent.mkdir()
        payload.write_bytes(b"unexpected binary")
        subprocess.run(["git", "-C", str(self.root), "add", "-f", "build/hidden.apk"],
                       check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, "excluded distribution file: build/hidden.apk"):
            self.inspect()

    def test_credential_pattern_reports_location_without_value(self):
        value = "gh" + "p_" + "X" * 40
        (self.root / "accidental.txt").write_text(value)
        with self.assertRaises(ValueError) as error:
            self.inspect()
        self.assertIn("github-token: accidental.txt:1", str(error.exception))
        self.assertNotIn(value, str(error.exception))

    def test_document_link_cannot_escape_the_repository(self):
        (self.root / "escape.md").write_text("[outside](../outside.md)\n")
        (self.root.parent / "outside.md").write_text("outside the release\n")
        with self.assertRaisesRegex(ValueError, "broken/local external link: escape.md"):
            self.inspect()

    def test_symlink_source_is_rejected(self):
        (self.root / "alias.py").symlink_to(self.root / "installer/verify.py")
        with self.assertRaisesRegex(ValueError, "non-regular source: alias.py"):
            self.inspect()

    def test_changed_license_copy_fails_its_catalog(self):
        license_file = self.root / "legal/licenses/termux-x11-GPL-3.0.txt"
        license_file.write_bytes(license_file.read_bytes() + b"changed\n")
        with self.assertRaisesRegex(ValueError, "retained license changed"):
            checker.verify_notices()


if __name__ == "__main__":
    unittest.main()
