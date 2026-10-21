"""Exercise real config bytes and filesystem installs; substitute only PRoot."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'termux/omarchy_personal_nvim_guest.py'
PAYLOAD = ROOT / 'termux/nvim'


class PersonalNvimTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'personal Nvim guest worker is missing')
        spec = importlib.util.spec_from_file_location('personal_nvim_test', SOURCE)
        self.worker = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.worker)
        self.temp = tempfile.TemporaryDirectory(prefix='personal-nvim-'); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'; self.home.mkdir(mode=0o700)
        self.payload = self.root / 'payload'; shutil.copytree(PAYLOAD, self.payload)
        for path in self.payload.rglob('*'):
            path.chmod(0o700 if path.is_dir() else 0o600)

    def execute(self, **kwargs):
        return self.worker.execute(self.payload, self.home, **kwargs)

    def test_preflight_is_readonly_and_reports_missing_plugins(self):
        before = list(self.home.iterdir())
        row = self.execute()
        self.assertEqual(row['status'], 'verified')
        self.assertEqual(row['configState'], 'absent')
        self.assertFalse(row['configWrites']); self.assertFalse(row['networkRequested'])
        self.assertEqual(row['lockedPlugins'], 81); self.assertEqual(row['missingPlugins'], 81)
        self.assertEqual(list(self.home.iterdir()), before)

    def test_reviewed_install_creates_exact_config_and_repeats_readonly(self):
        row = self.execute(install=True, before=self.execute()['beforeSHA256'])
        self.assertEqual(row['status'], 'installed'); self.assertTrue(row['configWrites'])
        target = self.home / '.config/nvim'
        for name, entry in self.worker.Payload(self.payload).manifest['files'].items():
            self.assertEqual(hashlib.sha256((target / name).read_bytes()).hexdigest(), entry['sha256'])
        init = target / 'init.lua'; before = (init.read_bytes(), init.stat().st_ino, init.stat().st_mtime_ns)
        row = self.execute(install=True, before=self.execute()['beforeSHA256'])
        self.assertEqual(row['configState'], 'managed'); self.assertFalse(row['configWrites'])
        self.assertEqual((init.read_bytes(), init.stat().st_ino, init.stat().st_mtime_ns), before)

    def test_config_publication_is_atomic_and_cannot_replace_an_appearing_directory(self):
        from unittest import mock
        self.assertTrue(hasattr(self.worker, 'publish_directory'), 'atomic directory publication is missing')
        calls = []; actual = self.worker.publish_directory
        def publish(fd, temporary, name):
            self.assertFalse((self.home / '.config/nvim').exists())
            self.assertTrue((self.home / '.config' / temporary / 'lua/plugins/astrocore.lua').is_file())
            calls.append(name); return actual(fd, temporary, name)
        with mock.patch.object(self.worker, 'publish_directory', side_effect=publish):
            self.execute(install=True, before=self.execute()['beforeSHA256'])
        self.assertEqual(calls, ['nvim'])
        other = self.root / 'other-home'; other.mkdir(mode=0o700)
        def appearing(fd, temporary, name):
            target = other / '.config/nvim'; target.mkdir(mode=0o700)
            (target / 'user.lua').write_bytes(b'-- appeared after staging\n')
            return actual(fd, temporary, name)
        with mock.patch.object(self.worker, 'publish_directory', side_effect=appearing):
            before = self.worker.execute(self.payload, other)['beforeSHA256']
            with self.assertRaisesRegex(ValueError, 'personal-nvim-install-uncertain'):
                self.worker.execute(self.payload, other, install=True, before=before)
        self.assertEqual((other / '.config/nvim/user.lua').read_bytes(), b'-- appeared after staging\n')
        self.assertFalse((other / '.config/nvim/init.lua').exists())

    def test_existing_config_is_preserved_without_receipt_or_changes(self):
        target = self.home / '.config/nvim'; target.mkdir(parents=True, mode=0o700)
        init = target / 'init.lua'; init.write_bytes(b'-- personal bytes\n')
        before = (init.read_bytes(), init.stat().st_ino, init.stat().st_mtime_ns)
        row = self.execute(install=True, before=self.execute()['beforeSHA256'])
        self.assertEqual(row['status'], 'preserved-existing'); self.assertFalse(row['configWrites'])
        self.assertEqual((init.read_bytes(), init.stat().st_ino, init.stat().st_mtime_ns), before)
        self.assertFalse((self.home / self.worker.OWNER).exists())

    def test_config_appearing_after_review_is_preserved(self):
        digest = self.execute()['beforeSHA256']
        target = self.home / '.config/nvim'; target.mkdir(parents=True)
        (target / 'init.lua').write_bytes(b'-- appeared\n')
        with self.assertRaisesRegex(ValueError, 'personal-nvim-review-changed'):
            self.execute(install=True, before=digest)
        self.assertEqual((target / 'init.lua').read_bytes(), b'-- appeared\n')

    def test_payload_tamper_or_symlink_refuses_install(self):
        path = self.payload / 'lua/community.lua'; original = path.read_bytes()
        path.write_bytes(original + b'-- changed\n')
        with self.assertRaises(ValueError): self.execute()
        path.unlink(); outside = self.root / 'outside'; outside.write_bytes(original); path.symlink_to(outside)
        with self.assertRaises((OSError, ValueError)): self.execute()
        self.assertFalse((self.home / '.config').exists())

    def test_symlink_config_parent_refuses_without_external_writes(self):
        outside = self.root / 'outside'; outside.mkdir()
        (self.home / '.config').symlink_to(outside)
        with self.assertRaises((OSError, ValueError)): self.execute(install=True, before='0' * 64)
        self.assertEqual(list(outside.iterdir()), [])

    def test_edit_or_extra_file_in_managed_config_is_preserved_and_refused(self):
        self.execute(install=True, before=self.execute()['beforeSHA256'])
        extra = self.home / '.config/nvim/local-user.lua'; extra.write_bytes(b'-- user extra\n')
        with self.assertRaisesRegex(ValueError, 'personal-nvim-owned-config-changed'): self.execute()
        self.assertEqual(extra.read_bytes(), b'-- user extra\n'); extra.unlink()
        path = self.home / '.config/nvim/init.lua'; path.write_bytes(b'-- local edit\n')
        with self.assertRaisesRegex(ValueError, 'personal-nvim-owned-config-changed'): self.execute()
        self.assertEqual(path.read_bytes(), b'-- local edit\n')

    def test_interrupted_owner_is_retained_and_retry_refused(self):
        owner = self.home / self.worker.OWNER; owner.parent.mkdir(parents=True, mode=0o700)
        owner.write_text('{"schema":1,"phase":"INSTALLING"}'); owner.chmod(0o600)
        before = owner.read_bytes()
        with self.assertRaisesRegex(ValueError, 'personal-nvim-install-uncertain'): self.execute()
        self.assertEqual(owner.read_bytes(), before)

    def test_offline_startup_works_with_no_plugins_and_does_not_spawn_git(self):
        nvim = shutil.which('nvim'); self.assertIsNotNone(nvim)
        self.execute(install=True, before=self.execute()['beforeSHA256'])
        commands = self.root / 'bin'; commands.mkdir()
        marker = self.root / 'git-called'
        git = commands / 'git'; git.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nexit 42\n'); git.chmod(0o700)
        env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'),
                   XDG_DATA_HOME=str(self.home / '.local/share'), XDG_STATE_HOME=str(self.home / '.local/state'),
                   XDG_CACHE_HOME=str(self.home / '.cache'), PATH=str(commands) + ':/usr/bin:/bin')
        result = subprocess.run([nvim, '--headless', '+lua print("OFFLINE_READY")', '+qa!'],
                                env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('OFFLINE_READY', result.stderr + result.stdout)
        self.assertFalse(marker.exists()); self.assertFalse((self.home / '.local/share/nvim/lazy').exists())

    def test_lua_loads_and_resource_options_override_automatic_installers(self):
        nvim = shutil.which('nvim'); self.assertIsNotNone(nvim)
        script = self.root / 'verify.lua'
        script.write_text('''
local root = assert(vim.env.PERSONAL_NVIM_PAYLOAD)
for _, path in ipairs(vim.fn.glob(root .. "/**/*.lua", false, true)) do assert(loadfile(path)) end
local captured
package.preload.lazy = function() return { setup = function(spec, opts) captured = opts end } end
assert(loadfile(root .. "/lua/lazy_setup.lua"))()
assert(captured.concurrency == 1 and captured.install.missing == false)
assert(captured.checker.enabled == false and captured.change_detection.enabled == false)
local specs = assert(loadfile(root .. "/lua/plugins/zzz_android.lua"))()
local by_name = {}; for _, spec in ipairs(specs) do by_name[spec[1]] = spec end
for _, name in ipairs({"williamboman/mason-lspconfig.nvim", "jay-babu/mason-null-ls.nvim", "jay-babu/mason-nvim-dap.nvim", "nvim-treesitter/nvim-treesitter"}) do
  local opts = { ensure_installed = { "must-not-install" }, automatic_installation = true, auto_install = true }
  by_name[name].opts(nil, opts)
  assert(#opts.ensure_installed == 0 and opts.automatic_installation == false and opts.auto_install == false)
end
assert(by_name["vhyrro/luarocks.nvim"].enabled == false)
print("CONFIG_OPTIONS_READY")
''')
        env = dict(os.environ, PERSONAL_NVIM_PAYLOAD=str(self.payload), HOME=str(self.home))
        result = subprocess.run([nvim, '--headless', '-u', 'NONE', '-l', str(script)], env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('CONFIG_OPTIONS_READY', result.stdout + result.stderr)




class PersonalNvimInstallerTests(unittest.TestCase):
    def setUp(self):
        from unittest import mock
        import test_termux_omarchy_nvim_tools as existing
        self.fixture = existing.NeovimInstallerTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        source = SOURCE.with_name('omarchy_personal_nvim_install.py')
        self.assertTrue(source.is_file(), 'personal Nvim native installer is missing')
        spec = importlib.util.spec_from_file_location('personal_nvim_install_test', source)
        self.host = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.host)
        self.home, self.prefix, self.managed, self.rootfs = (getattr(self.fixture, k)
            for k in ('home', 'prefix', 'managed', 'rootfs'))
        shutil.rmtree(self.rootfs / 'home/omarchy/.config/nvim')
        self.fixture.preserved = [p for p in self.fixture.preserved if '.config/nvim/' not in str(p)]
        self.fixture.before = {str(p): self.fixture.before[str(p)] for p in self.fixture.preserved}
        self.calls = []
        def transport(argv, **kwargs):
            self.calls.append((argv, kwargs['env']))
            self.assertEqual(argv[1:5], ['login', '--isolated', '--user', 'omarchy'])
            split = argv.index('--'); stage = self.rootfs / argv[split + 4].lstrip('/')
            return json.dumps(self.host.worker.execute(stage, self.rootfs / 'home/omarchy',
                install='--install' in argv, before=argv[argv.index('--before') + 1] if '--before' in argv else None))
        patch = mock.patch.object(self.host, 'run_bounded', side_effect=transport)
        patch.start(); self.addCleanup(patch.stop)

    def test_native_preflight_has_no_stage_or_journal_writes(self):
        before = sorted(str(p.relative_to(self.rootfs)) for p in self.rootfs.rglob('*'))
        row = self.host.preflight(PAYLOAD, self.home, self.prefix)
        self.assertEqual(row['configState'], 'absent'); self.assertFalse(row['configWrites'])
        self.assertEqual(sorted(str(p.relative_to(self.rootfs)) for p in self.rootfs.rglob('*')), before)
        self.assertFalse((self.managed / self.host.JOURNAL).exists()); self.assertFalse(self.calls)
        self.fixture.assert_preserved()

    def test_native_install_guards_runtime_and_uses_separate_journal(self):
        row = self.host.install(PAYLOAD, self.home, self.prefix)
        self.assertEqual(row['phase'], 'INSTALLED'); self.assertTrue(row['configWrites'])
        self.assertTrue((self.rootfs / 'home/omarchy/.config/nvim/init.lua').is_file())
        self.fixture.assert_preserved()
        for args, env in self.calls:
            self.assertEqual(env['PD_PROOT_BIN'], str(self.managed / 'proot-guard/proot'))
            self.assertIn('PROOT_EXITKILL=1', args); self.assertIn('TMPDIR=/tmp', args)
            self.assertIn('PROOT_TMP_DIR=' + str(self.prefix / 'tmp'), args)
        before = (self.managed / self.host.JOURNAL).stat().st_mtime_ns
        self.host.install(PAYLOAD, self.home, self.prefix)
        self.assertEqual((self.managed / self.host.JOURNAL).stat().st_mtime_ns, before)

    def test_native_full_install_writes_only_reviewed_source_plugins_and_config(self):
        directory = ROOT / 'build/diagnostics/termux-omarchy-personal-nvim-plugin-payload-20261009-01'
        old = self.rootfs / 'home/omarchy/.local/share/nvim/lazy/personal.lua'
        old.unlink(); old.parent.rmdir(); self.fixture.preserved.remove(old); self.fixture.before.pop(str(old))
        row = self.host.install(PAYLOAD, self.home, self.prefix, plugin_directory=directory)
        self.assertEqual(row['phase'], 'INSTALLED'); self.assertEqual(row['missingPlugins'], 0)
        self.assertEqual(row['pluginResult']['plugins'], 81)
        self.assertTrue(row['pluginResult']['pluginWrites'])
        self.assertFalse(row['pluginResult']['networkRequested']); self.assertFalse(row['pluginResult']['buildScriptsRun'])
        self.fixture.assert_preserved()

    def test_ready_session_install_keeps_all_runtime_identities_and_rejects_nvim(self):
        from unittest import mock
        records = [{'pid': 200 + i, 'ppid': 1, 'pgid': 200 + i, 'uid': os.getuid(),
                    'tty_nr': 0, 'starttime': str(800 + i), 'command': ['/usr/bin/runtime-' + str(i)]}
                   for i in range(5)]
        state = dict(self.fixture.state, phase='ready', terminationConfirmed=False, processes=records[:4],
                     hyprland=records[4], token='public-session', display=':20')
        self.fixture.write(self.managed / 'runtime-state.json', json.dumps(state).encode())
        before = (self.managed / 'runtime-state.json').read_bytes()
        with mock.patch.object(self.host, 'identity', create=True, side_effect=lambda pid, **kwargs: records[pid - 200]), \
             mock.patch.object(self.host, 'snapshot', create=True, return_value={r['pid']: r for r in records}):
            row = self.host.install(PAYLOAD, self.home, self.prefix)
        self.assertEqual(row['phase'], 'INSTALLED'); self.assertEqual(row['runtimePhase'], 'ready')
        self.assertEqual((self.managed / 'runtime-state.json').read_bytes(), before)
        chrome = dict(records[0], command=['/usr/bin/chromium --app=https://example.test/nvim'])
        with mock.patch.object(self.host, 'identity', create=True, side_effect=lambda pid, **kwargs: records[pid - 200]), \
             mock.patch.object(self.host, 'snapshot', create=True, return_value={chrome['pid']: chrome}):
            self.assertEqual(self.host.install(PAYLOAD, self.home, self.prefix)['phase'], 'INSTALLED')
        for command in (['/usr/bin/nvim', 'public-file'], ['nvim /tmp/file'],
                        ['/usr/bin/nvim.real /tmp/file'], ['"/usr/bin/nvim" "/tmp/file name"']):
            nvim = dict(records[0], command=command)
            with self.subTest(command=command), \
                 mock.patch.object(self.host, 'identity', create=True, side_effect=lambda pid, **kwargs: records[pid - 200]), \
                 mock.patch.object(self.host, 'snapshot', create=True, return_value={nvim['pid']: nvim}):
                with self.assertRaisesRegex(ValueError, 'personal-nvim-editor-active'):
                    self.host.install(PAYLOAD, self.home, self.prefix)


    def test_native_running_runtime_refuses_before_stage_and_guest(self):
        state = dict(self.fixture.state, phase='ready', terminationConfirmed=False)
        self.fixture.write(self.managed / 'runtime-state.json', json.dumps(state).encode())
        before = list((self.rootfs / 'opt').iterdir()) if (self.rootfs / 'opt').exists() else []
        with self.assertRaisesRegex(ValueError, 'personal-nvim-runtime-active'):
            self.host.install(PAYLOAD, self.home, self.prefix)
        self.assertFalse(self.calls); self.assertFalse((self.managed / self.host.JOURNAL).exists())
        self.assertEqual(list((self.rootfs / 'opt').iterdir()) if (self.rootfs / 'opt').exists() else [], before)

    def test_native_existing_user_config_is_preserved_and_recorded(self):
        path = self.rootfs / 'home/omarchy/.config/nvim/init.lua'; self.fixture.write(path, b'-- user config\n')
        row = self.host.install(PAYLOAD, self.home, self.prefix)
        self.assertEqual(row['phase'], 'PRESERVED'); self.assertFalse(row['configWrites'])
        self.assertEqual(path.read_bytes(), b'-- user config\n')
        self.assertFalse((self.rootfs / 'home/omarchy' / self.host.worker.OWNER).exists())


class PersonalNvimPluginSourcesTests(unittest.TestCase):
    def setUp(self):
        source = SOURCE.with_name('omarchy_personal_nvim_plugins.py')
        self.assertTrue(source.is_file(), 'pinned personal plugin installer is missing')
        sys.path.insert(0, str(SOURCE.parent)); self.addCleanup(sys.path.remove, str(SOURCE.parent))
        spec = importlib.util.spec_from_file_location('personal_nvim_plugins_test', source)
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.directory = ROOT / 'build/diagnostics/termux-omarchy-personal-nvim-plugin-payload-20261009-01'
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve() / 'home'; self.home.mkdir(mode=0o700)

    def test_exact_source_archive_has_all_81_commits_and_no_native_binaries(self):
        payload = self.module.Payload(self.directory)
        lock = json.loads((PAYLOAD / 'lazy-lock.json').read_bytes())
        self.assertEqual({n: r['commit'] for n, r in payload.manifest['plugins'].items()},
                         {n: r['commit'] for n, r in lock.items()})
        self.assertFalse(any(n.endswith(('.so', '.dylib', '.dll')) for n in payload.manifest['files']))

    def test_source_only_install_preserves_empty_parent_and_is_readonly_on_retry(self):
        target = self.home / '.local/share/nvim'; target.mkdir(parents=True, mode=0o700)
        before = target.stat().st_ino
        row = self.module.install(self.directory, self.home)
        self.assertEqual(row['status'], 'installed'); self.assertEqual(row['plugins'], 81)
        self.assertEqual(target.stat().st_ino, before)
        lazy = target / 'lazy/lazy.nvim/lua/lazy/init.lua'; self.assertTrue(lazy.is_file())
        before = (lazy.stat().st_ino, lazy.stat().st_mtime_ns)
        row = self.module.install(self.directory, self.home)
        self.assertFalse(row['pluginWrites']); self.assertEqual((lazy.stat().st_ino, lazy.stat().st_mtime_ns), before)

    def test_existing_plugin_directory_is_preserved_without_adoption(self):
        target = self.home / '.local/share/nvim/lazy/personal'; target.mkdir(parents=True, mode=0o700)
        path = target / 'init.lua'; path.write_bytes(b'-- user plugin\n')
        row = self.module.install(self.directory, self.home)
        self.assertEqual(row['status'], 'preserved-existing'); self.assertFalse(row['pluginWrites'])
        self.assertEqual(path.read_bytes(), b'-- user plugin\n')
        self.assertFalse((self.home / self.module.OWNER).exists())

    def test_full_personal_astronvim_starts_from_pinned_sources_without_downloads(self):
        self.module.install(self.directory, self.home)
        worker = self.module.files
        worker.execute(PAYLOAD, self.home, install=True,
                       before=worker.execute(PAYLOAD, self.home)['beforeSHA256'])
        nvim = shutil.which('nvim'); self.assertIsNotNone(nvim)
        commands = self.home.parent / 'bin'; commands.mkdir()
        marker = self.home.parent / 'download-called'
        for name in ('git', 'curl', 'wget', 'luarocks', 'make'):
            path = commands / name
            path.write_text('#!/bin/sh\ncase "$*" in *--version*) echo "git version 2.49.0"; exit 0;; *rev-parse*) exit 1;; esac\nprintf "%s %s\\n" "' + name + '" "$*" >> "' + str(marker) + '"\nexit 42\n')
            path.chmod(0o700)
        env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'),
                   XDG_DATA_HOME=str(self.home / '.local/share'), XDG_STATE_HOME=str(self.home / '.local/state'),
                   XDG_CACHE_HOME=str(self.home / '.cache'), PATH=str(commands) + ':/usr/bin:/bin', TMUX='')
        env.pop('TMUX', None); env.pop('LAZY', None)
        command = 'lua vim.defer_fn(function() print("ASTRO_ACTIVE=" .. tostring(package.loaded.astrocore ~= nil)); print("NVIM_ERROR=" .. vim.v.errmsg); vim.cmd("qa!") end, 1200)'
        public = self.home / 'public.lua'; public.write_text('local greeting = \"hello\"\nprint(greeting)\n')
        result = subprocess.run([nvim, '--headless', str(public), '-c', command], env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('ASTRO_ACTIVE=true', result.stdout + result.stderr)
        self.assertNotIn('Error detected', result.stderr)
        self.assertNotIn('Failed to', result.stderr)
        self.assertFalse(marker.exists(), marker.read_text() if marker.exists() else '')

    def test_user_edit_to_owned_plugin_is_retained_and_refused(self):
        self.module.install(self.directory, self.home)
        path = self.home / '.local/share/nvim/lazy/lazy.nvim/lua/lazy/init.lua'
        path.write_bytes(b'-- local edit\n')
        with self.assertRaisesRegex(ValueError, 'personal-nvim-plugin-changed'):
            self.module.install(self.directory, self.home)
        self.assertEqual(path.read_bytes(), b'-- local edit\n')


if __name__ == '__main__': unittest.main()
