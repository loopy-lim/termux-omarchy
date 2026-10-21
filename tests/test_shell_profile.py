"""Profile installation preserves user data and the terminal selects installed zsh."""
from pathlib import Path
import sys
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1] / 'guest/desktop/usr/local/lib/loopy'
sys.path.insert(0, str(LIB))
import shell_profile
import desktop_ui


class ShellProfileTests(unittest.TestCase):
    def test_missing_profiles_are_created_once_and_custom_profiles_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); source = root / 'source'; source.mkdir()
            (source / 'zshrc').write_text('fixture'); (source / 'tmux.conf').write_text('fixture')
            home = root / 'home'; shell_profile.install(home, source)
            self.assertEqual((home / '.zshrc').read_text(), 'source /usr/share/loopy/shell/zshrc\n')
            (home / '.zshrc').write_text('my existing profile\n')
            shell_profile.install(home, source)
            self.assertEqual((home / '.zshrc').read_text(), 'my existing profile\n')
            target = home / '.tmux.conf'; target.unlink(); target.symlink_to(home / 'missing')
            shell_profile.install(home, source); self.assertTrue(target.is_symlink())
            self.assertFalse((home / 'missing').exists())

    def test_symlink_home_cannot_install_into_a_different_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); target = root / 'target'; target.mkdir()
            link = root / 'link'; link.symlink_to(target)
            with self.assertRaises(ValueError): shell_profile.install(link)
            self.assertEqual(list(target.iterdir()), [])

    def test_desktop_terminal_uses_zsh_login_without_shell_evaluation(self):
        self.assertEqual(desktop_ui.application_command('terminal')[-2:], ['zsh', '-l'])
