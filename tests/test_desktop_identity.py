"""Desktop guest identity must work without PRoot's fake-root UID."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "guest/desktop/usr/local/lib/loopy/identity.py"


def load_identity():
    spec = importlib.util.spec_from_file_location("loopy_identity", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.etc = Path(self.temp.name).resolve() / "etc"
        self.etc.mkdir()
        (self.etc / "passwd").write_text("root:x:0:0:root:/root:/bin/sh\nother:x:500:500:Other:/home/other:/bin/sh\n")
        (self.etc / "group").write_text("root:x:0:root\nother:x:500:\n")

    def test_unknown_app_uid_is_added_once_without_touching_root(self):
        identity = load_identity()
        identity.ensure_identity(self.etc, 10224, 10224)
        passwd = (self.etc / "passwd").read_text()
        group = (self.etc / "group").read_text()
        self.assertIn("root:x:0:0:root:/root:/bin/sh\n", passwd)
        self.assertIn("loopy:x:10224:10224:Loopy Desktop:/root:/bin/bash\n", passwd)
        self.assertIn("loopy:x:10224:\n", group)
        stamp = ((self.etc / "passwd").stat().st_mtime_ns, (self.etc / "group").stat().st_mtime_ns)
        identity.ensure_identity(self.etc, 10224, 10224)
        self.assertEqual(stamp, ((self.etc / "passwd").stat().st_mtime_ns,
                                 (self.etc / "group").stat().st_mtime_ns))
        self.assertEqual(passwd, (self.etc / "passwd").read_text())

    def test_existing_uid_or_gid_name_is_preserved(self):
        identity = load_identity()
        with (self.etc / "passwd").open("a") as output:
            output.write("android:x:10224:10224:Existing:/home/android:/bin/sh\n")
        with (self.etc / "group").open("a") as output:
            output.write("android:x:10224:\n")
        before = ((self.etc / "passwd").read_bytes(), (self.etc / "group").read_bytes())
        identity.ensure_identity(self.etc, 10224, 10224)
        self.assertEqual(before, ((self.etc / "passwd").read_bytes(), (self.etc / "group").read_bytes()))

    def test_uid_zero_and_name_collision_fail_without_modification(self):
        identity = load_identity()
        before = (self.etc / "passwd").read_bytes()
        with self.assertRaises(ValueError):
            identity.ensure_identity(self.etc, 0, 0)
        self.assertEqual(before, (self.etc / "passwd").read_bytes())
        with (self.etc / "passwd").open("a") as output:
            output.write("loopy:x:999:999:Existing:/home/old:/bin/sh\n")
        with self.assertRaises(ValueError):
            identity.ensure_identity(self.etc, 10224, 10224)
        self.assertNotIn("loopy:x:10224", (self.etc / "passwd").read_text())

    def test_symlink_oversized_and_insecure_modes_fail_closed(self):
        identity = load_identity()
        passwd = self.etc / "passwd"
        original = passwd.read_bytes()
        passwd.unlink()
        passwd.symlink_to(self.etc / "group")
        with self.assertRaises(ValueError):
            identity.ensure_identity(self.etc, 10224, 10224)
        self.assertEqual((self.etc / "group").read_text(), "root:x:0:root\nother:x:500:\n")
        passwd.unlink()
        passwd.write_bytes(original + b"x" * 65536)
        with self.assertRaises(ValueError):
            identity.ensure_identity(self.etc, 10224, 10224)
        passwd.write_bytes(original)
        passwd.chmod(0o666)
        with self.assertRaises(ValueError):
            identity.ensure_identity(self.etc, 10224, 10224)

    def test_launcher_registers_uid_before_cache_and_dbus(self):
        launcher = SOURCE.parents[2] / "bin/loopy-desktop"
        script = launcher.read_text()
        self.assertLess(script.index("lib/loopy/identity.py"), script.index("/usr/local/bin/loopy-cache"))
        self.assertLess(script.index("lib/loopy/identity.py"), script.index("lib/loopy/graphics_session.py"))
        graphics = SOURCE.with_name("graphics_session.py").read_text()
        self.assertIn("os.execve('/usr/bin/dbus-run-session'", graphics)


if __name__ == "__main__":
    unittest.main()
