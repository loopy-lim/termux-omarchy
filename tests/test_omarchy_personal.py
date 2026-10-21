"""The profile preserves personal files and modifies only reviewed desktop settings."""
import configparser
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pty
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
NEW = REPO / 'termux/omarchy_personal.py'
FOOT = '[main]\nfont=Public Font:size=9\npad=14x14\n\n[key-bindings]\nclipboard-copy=Control+Insert\nclipboard-paste=Shift+Insert\n\n[scrollback]\nlines=10000\n'
BINDINGS = '-- Personal menu override\no.bind("SUPER + SPACE", "Menu", "public-menu")\n'


class PersonalProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='omarchy-personal-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / 'home'; self.home.mkdir(mode=0o700)
        self.bundle = self.base / 'source'; self.bundle.mkdir(mode=0o700)
        for name in ('zshrc', 'tmux.conf', 'bindings.lua', 'git.zsh', 'git.plugin.zsh'):
            (self.bundle / name).write_text('# public profile fixture\n')
        for name, text in (('.config/foot/foot.ini', FOOT), ('.config/hypr/bindings.lua', BINDINGS)):
            path = self.home / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.expected = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in
                         (('.config/foot/foot.ini', FOOT), ('.config/hypr/bindings.lua', BINDINGS))}
        source = NEW if NEW.exists() else REPO / 'guest/desktop/usr/local/lib/loopy/shell_profile.py'
        spec = importlib.util.spec_from_file_location('personal_profile_test', source)
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)

    def install(self):
        if NEW.exists(): return self.module.install(self.home, self.bundle, self.expected)
        self.module.install(self.home, self.bundle)
        return {}

    def test_terminal_keys_and_zsh_are_installed_without_changing_size_or_scrollback(self):
        # Catches overwriting unrelated Foot settings or missing Alt font shortcuts.
        self.install()
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.home / '.config/foot/foot.ini')
        self.assertEqual(config.get('key-bindings', 'font-decrease', fallback=None),
                         'Control+minus Mod1+minus Mod1+KP_Subtract')
        self.assertIn('Mod1+plus', config.get('key-bindings', 'font-increase'))
        self.assertEqual(config.get('main', 'shell'), '/usr/bin/zsh')
        self.assertEqual(config.get('main', 'font'), 'Public Font:size=9')
        self.assertEqual(config.get('main', 'pad'), '14x14')
        self.assertEqual(config.get('scrollback', 'lines'), '10000')

    def test_existing_personal_rc_files_are_preserved_byte_for_byte(self):
        for name in ('.zshrc', '.tmux.conf'): (self.home / name).write_bytes(b'public custom config\n')
        self.install()
        for name in ('.zshrc', '.tmux.conf'):
            self.assertEqual((self.home / name).read_bytes(), b'public custom config\n')

    def test_original_foot_and_bindings_are_backed_up_before_replacement(self):
        value = self.install()
        self.assertIsNotNone(value.get('backup'))
        backup = Path(value['backup'])
        self.assertEqual((backup / 'foot.ini').read_text(), FOOT)
        self.assertEqual((backup / 'bindings.lua').read_text(), BINDINGS)
        journal = json.loads((backup / 'receipt.json').read_text())
        self.assertEqual(journal['status'], 'applied')

    def test_changed_foot_is_rejected_before_installing_profile_files(self):
        (self.home / '.config/foot/foot.ini').write_text(FOOT + '# user edit\n')
        with self.assertRaises(ValueError): self.install()
        self.assertFalse((self.home / '.local/share/loopy-omarchy-profile').exists())
        self.assertEqual((self.home / '.config/hypr/bindings.lua').read_text(), BINDINGS)

    def test_symlink_config_cannot_modify_an_external_file(self):
        outside = self.base / 'outside.ini'; outside.write_text(FOOT)
        foot = self.home / '.config/foot/foot.ini'; foot.unlink(); foot.symlink_to(outside)
        with self.assertRaises((ValueError, OSError)): self.install()
        self.assertEqual(outside.read_text(), FOOT)
        self.assertEqual((self.home / '.config/hypr/bindings.lua').read_text(), BINDINGS)

    def test_duplicate_foot_sections_are_rejected_before_writes(self):
        foot = self.home / '.config/foot/foot.ini'; foot.write_text(FOOT + '[main]\nshell=/bin/bash\n')
        self.expected['.config/foot/foot.ini'] = hashlib.sha256(foot.read_bytes()).hexdigest()
        with self.assertRaises(ValueError): self.install()
        self.assertEqual((self.home / '.config/hypr/bindings.lua').read_text(), BINDINGS)

    def test_repeated_install_does_not_duplicate_hyprland_profile_include(self):
        self.install(); first = (self.home / '.config/hypr/bindings.lua').read_bytes()
        self.install()
        self.assertEqual((self.home / '.config/hypr/bindings.lua').read_bytes(), first)
        self.assertIn(b'loopy-omarchy-profile/bindings.lua', first)

    def test_owned_source_upgrade_keeps_the_previous_bytes_in_a_new_backup(self):
        first = self.install()
        (self.bundle / 'tmux.conf').write_bytes(b'# revised public profile\n')
        second = self.install()
        self.assertNotEqual(first['backup'], second['backup'])
        self.assertEqual((Path(second['backup']) / 'profile/tmux.conf').read_bytes(),
                         b'# public profile fixture\n')
        self.assertEqual((self.home / '.local/share/loopy-omarchy-profile/tmux.conf').read_bytes(),
                         b'# revised public profile\n')

    def test_user_edits_to_installed_source_are_not_replaced_by_upgrade(self):
        self.install()
        target = self.home / '.local/share/loopy-omarchy-profile/tmux.conf'
        target.write_bytes(b'# user edit\n')
        (self.bundle / 'tmux.conf').write_bytes(b'# replacement\n')
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(target.read_bytes(), b'# user edit\n')

    def test_real_zsh_profile_starts_with_missing_optional_tools_and_git_alias_works(self):
        for name in ('zshrc', 'tmux.conf', 'bindings.lua', 'git.zsh', 'git.plugin.zsh'):
            (self.bundle / name).write_bytes((REPO / 'termux/profile' / name).read_bytes())
        self.install()
        repository = self.home / 'public-repo'; repository.mkdir()
        env = dict(HOME=str(self.home), ZDOTDIR=str(self.home), PATH='/usr/bin:/bin',
                   TERM='xterm-256color', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null')
        subprocess.run(['/usr/bin/git', 'init', '-q', str(repository)], env=env, check=True,
                       capture_output=True, timeout=5)
        (repository / 'public.txt').write_text('public fixture\n')
        result = subprocess.run(['/bin/zsh', '-fic',
            'source "$HOME/.zshrc"; cd "$HOME/public-repo"; eval "gst --short"; print SHELL_READY'],
            env=env, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertIn('?? public.txt', result.stdout)
        self.assertIn('SHELL_READY', result.stdout)

    def test_real_tmux_alt_digit_input_selects_all_ten_windows(self):
        command = shutil.which('tmux')
        self.assertIsNotNone(command, 'tmux is required for the profile integration check')
        for name in ('zshrc', 'tmux.conf', 'bindings.lua', 'git.zsh', 'git.plugin.zsh'):
            (self.bundle / name).write_bytes((REPO / 'termux/profile' / name).read_bytes())
        xdg = self.home / '.config/tmux/tmux.conf'; xdg.parent.mkdir()
        xdg.write_text('set -g prefix C-Space\nset -sg escape-time 10\n')
        self.expected['.config/tmux/tmux.conf'] = hashlib.sha256(xdg.read_bytes()).hexdigest()
        try:
            self.install()
        except ValueError:
            self.fail('The reviewed Omarchy XDG tmux config must load the personal override')
        with tempfile.TemporaryDirectory(prefix='omarchy-tmux-', dir='/private/tmp') as folder:
            sock = str(Path(folder) / 's')
            env = dict(os.environ, HOME=str(self.home), TERM='xterm-256color',
                       XDG_CONFIG_HOME=str(self.home / '.config'))
            def tmux(*args):
                return subprocess.run([command, '-S', sock, *args], env=env,
                                      capture_output=True, text=True, timeout=5, check=True)
            master = slave = None; client = None
            try:
                tmux('new-session', '-d', '-s', 'public-check', '/bin/sh -c "sleep 60"')
                self.assertEqual(tmux('show-options', '-gv', 'prefix').stdout.strip(), 'C-a')
                self.assertEqual(tmux('show-options', '-sv', 'escape-time').stdout.strip(), '0')
                for index in range(2, 11):
                    tmux('new-window', '-d', '-t', f'public-check:{index}', '/bin/sh -c "sleep 60"')
                master, slave = pty.openpty()
                client = subprocess.Popen([command, '-S', sock, 'attach', '-t', 'public-check'],
                                          env=env, stdin=slave, stdout=slave, stderr=slave)
                deadline = time.monotonic() + 3
                while not tmux('list-clients', '-F', '#{client_tty}').stdout.strip():
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.02)
                for digit, wanted in ((b'2', '2'), (b'0', '10'), (b'1', '1'), (b'3', '3'),
                                      (b'4', '4'), (b'5', '5'), (b'6', '6'), (b'7', '7'),
                                      (b'8', '8'), (b'9', '9')):
                    os.write(master, b'\x1b' + digit)
                    deadline = time.monotonic() + 2
                    while True:
                        actual = tmux('display-message', '-p', '#{window_index}').stdout.strip()
                        if actual == wanted: break
                        self.assertLess(time.monotonic(), deadline, f'Alt+{digit.decode()}: {actual}')
                        time.sleep(.02)
            finally:
                subprocess.run([command, '-S', sock, 'kill-server'], env=env,
                               capture_output=True, timeout=5)
                if client is not None:
                    client.wait(timeout=5)
                for fd in (master, slave):
                    if fd is not None: os.close(fd)


if __name__ == '__main__': unittest.main()
