import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('tablet_profile', Path(__file__).resolve().parents[1] / 'profiles/mac-tablet/install.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


class TabletProfileTests(unittest.TestCase):
    def snapshot(self, root, entries):
        archive = root / 'snapshot.tar.gz'
        with tarfile.open(archive, 'w:gz') as output:
            for name, data, kind in entries:
                member = tarfile.TarInfo(name)
                member.size, member.type = len(data), kind
                output.addfile(member, io.BytesIO(data))
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_install_is_idempotent_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            archive, sha = self.snapshot(root, [('.config/nvim/init.lua', b'config', tarfile.REGTYPE)])
            home = root / 'home'
            self.assertEqual(profile.install(archive, sha, home, 'config')['created'], 1)
            self.assertEqual(profile.install(archive, sha, home, 'config')['created'], 0)
            (home / '.config/nvim/init.lua').write_bytes(b'custom')
            with self.assertRaises(FileExistsError): profile.install(archive, sha, home, 'config')
            self.assertEqual((home / '.config/nvim/init.lua').read_bytes(), b'custom')

    def test_invalid_later_member_prevents_any_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for bad in ('../escape', '.config/nvim/../../escape', '/.config/nvim/escape'):
                archive, sha = self.snapshot(root, [('.config/nvim/init.lua', b'config', tarfile.REGTYPE), (bad, b'x', tarfile.REGTYPE)])
                with self.assertRaises(ValueError): profile.install(archive, sha, root / 'home', 'config')
                self.assertFalse((root / 'home').exists())

    def test_wrong_hash_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            archive, sha = self.snapshot(root, [('.config/nvim/init.lua', b'config', tarfile.REGTYPE)])
            with self.assertRaises(ValueError): profile.install(archive, '0' * 64, root / 'home', 'config')
            (root / 'target').mkdir()
            (root / 'home').symlink_to(root / 'target')
            with self.assertRaises(ValueError): profile.install(archive, sha, root / 'home', 'config')
            archive, sha = self.snapshot(root, [('.config/nvim/init.lua', b'', tarfile.SYMTYPE)])
            with self.assertRaises(ValueError): profile.install(archive, sha, root / 'fresh', 'config')

    def test_plugin_namespace_cannot_replace_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            archive, sha = self.snapshot(root, [('.config/nvim/init.lua', b'x', tarfile.REGTYPE)])
            with self.assertRaises(ValueError): profile.install(archive, sha, root / 'home', 'plugins')
            archive, sha = self.snapshot(root, [('lazy/lazy.nvim/lua/lazy/init.lua', b'source', tarfile.REGTYPE)])
            self.assertEqual(profile.install(archive, sha, root / 'home', 'plugins')['created'], 1)
            self.assertEqual((root / 'home/.local/share/nvim/lazy/lazy.nvim/lua/lazy/init.lua').read_bytes(), b'source')

    def test_only_the_shipped_alternative_init_is_retired_with_a_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            archive, sha = self.snapshot(root, [('.config/nvim/init.lua', b'config', tarfile.REGTYPE)])
            home = root / 'home'
            legacy = home / '.config/nvim/init.vim'
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b'shipped')
            with patch.object(profile, 'SHIPPED_INIT_VIM', hashlib.sha256(b'shipped').hexdigest()):
                self.assertTrue(profile.install(archive, sha, home, 'config')['shipped_init_vim_backed_up'])
            self.assertFalse(legacy.exists())
            self.assertEqual(legacy.with_name('init.vim.loopy-before-mac-profile').read_bytes(), b'shipped')

    def test_custom_alternative_init_blocks_the_whole_config_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            archive, sha = self.snapshot(root, [('.config/nvim/init.lua', b'config', tarfile.REGTYPE)])
            home = root / 'home'
            legacy = home / '.config/nvim/init.vim'
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b'custom')
            with self.assertRaises(FileExistsError): profile.install(archive, sha, home, 'config')
            self.assertEqual(legacy.read_bytes(), b'custom')
            self.assertFalse(legacy.with_name('init.lua').exists())
