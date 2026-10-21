"""A compiler hardlink must resolve to exact bytes from the frozen ARM image."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from tools import build_omarchy_watchdog as build


class WatchdogBuildSysrootTests(unittest.TestCase):
    def test_rootfs_hardlink_pins_actual_compiler_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            compiler = Path(folder) / 'c++'
            compiler.write_bytes(b'actual pinned compiler')
            name = str(compiler.resolve()).removeprefix('/')
            target = name + '-target'
            digest = hashlib.sha256(compiler.read_bytes()).hexdigest()
            manifest = {name: {'kind': 'hardlink', 'target': target},
                        target: {'kind': 'file', 'size': compiler.stat().st_size, 'sha256': digest}}
            self.assertEqual(build.rootfs_identity(compiler, manifest)['sha256'], digest)
            compiler.write_bytes(b'changed compiler')
            with self.assertRaises(ValueError):
                build.rootfs_identity(compiler, manifest)

    def test_cycle_or_escaping_manifest_target_cannot_supply_a_sysroot_input(self):
        with tempfile.TemporaryDirectory() as folder:
            compiler = Path(folder) / 'c++'
            compiler.write_bytes(b'compiler')
            name = str(compiler.resolve()).removeprefix('/')
            for target in (name, '../outside', '/absolute'):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    build.rootfs_identity(compiler, {name: {'kind': 'hardlink', 'target': target}})


if __name__ == '__main__':
    unittest.main()
