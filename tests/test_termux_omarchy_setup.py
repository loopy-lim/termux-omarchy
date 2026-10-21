"""Real setup CLI: invalid pinned inputs must fail before installing anything."""
import json
import ast
import contextlib
import fcntl
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / 'termux/omarchy_setup.py'
INPUTS = REPO / 'build/diagnostics/termux-omarchy-weston-host-20261009-01'
GUEST_INPUTS = REPO / 'build/diagnostics/termux-omarchy-guest-payload-20261009-01'
WORKFLOW_INPUTS = REPO / 'build/diagnostics/termux-omarchy-workflow-payload-20261009-02'
TOOLS_INPUTS = REPO / 'build/diagnostics/termux-omarchy-tools-payload-20261009-01'
PROOT_INPUTS = REPO / 'build/diagnostics/termux-omarchy-proot-private-runpath-build-20261009-01/arm64-v8a'
IME_INPUTS = REPO / 'build/deliverables/Omarchy-Hangul-input-packages-20261009-01'
IME_CONFIG = REPO / 'build/deliverables/Omarchy-Hangul-input-config-20261009-01'
FILES = ('omarchy.py', 'processes.py', 'omarchy_runtime.py', 'omarchy_resources.py',
         'omarchy_boot.py', 'omarchy_input.py', 'omarchy_audio.py', 'omarchy_android.py',
         'omarchy_android_client.py', 'omarchy_commands.py', 'omarchy_proot.py')


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'combined Termux Omarchy setup missing')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.home, self.prefix, self.sources = root / 'home', root / 'prefix', root / 'sources'
        for directory in (self.home, self.prefix, self.sources):
            directory.mkdir(mode=0o700)
        for name in FILES:
            shutil.copyfile(REPO / 'termux' / name, self.sources / name)
            (self.sources / name).chmod(0o600)
        self.payload, self.manifest = root / 'payload.tar', root / 'payload-manifest.json'
        for name, target in [('payload.tar', self.payload), ('payload-manifest.json', self.manifest)]:
            shutil.copyfile(INPUTS / name, target)
            target.chmod(0o600)
        self.guest_payload, self.guest_manifest = root / 'guest-payload.tar', root / 'guest-manifest.json'
        for target in (self.guest_payload, self.guest_manifest):
            shutil.copyfile(GUEST_INPUTS / target.name, target)
            target.chmod(0o600)
        self.workflow_payload, self.workflow_manifest = root / 'workflow-payload.tar', root / 'workflow-manifest.json'
        for target in (self.workflow_payload, self.workflow_manifest):
            shutil.copyfile(WORKFLOW_INPUTS / target.name, target)
            target.chmod(0o600)
        self.tools = root / 'tools'; self.tools.mkdir(mode=0o700)
        for source in TOOLS_INPUTS.iterdir():
            if source.name == 'tools-manifest.json' or source.name.endswith(('.pkg.tar.xz', '.pkg.tar.xz.sig')):
                shutil.copyfile(source, self.tools / source.name)
                (self.tools / source.name).chmod(0o600)
        self.proot = root / 'proot-guard'; self.proot.mkdir(mode=0o700)
        for name in ('proot', 'loader', 'libandroid-shmem.so'):
            shutil.copyfile(PROOT_INPUTS / name, self.proot / name)
            (self.proot / name).chmod(0o600)
        self.ime = root / 'korean-input'; self.ime.mkdir(mode=0o700)
        for source in IME_INPUTS.iterdir():
            if source.name == 'ime-manifest.json' or source.name.endswith(('.pkg.tar.xz', '.pkg.tar.xz.sig')):
                shutil.copyfile(source, self.ime / source.name)
                (self.ime / source.name).chmod(0o600)
        self.input_payload, self.input_manifest = root / 'input-config-payload.tar', root / 'input-config-manifest.json'
        for target in (self.input_payload, self.input_manifest):
            shutil.copyfile(IME_CONFIG / target.name, target); target.chmod(0o600)
        self.root = self.home / '.local/share/loopy-omarchy'

    def arguments(self):
        return ['--bundle', str(self.home / 'absent-bundle.tar'),
            '--sources', str(self.sources), '--weston-payload', str(self.payload),
            '--weston-manifest', str(self.manifest), '--guest-payload', str(self.guest_payload),
            '--guest-manifest', str(self.guest_manifest), '--workflow-payload', str(self.workflow_payload),
            '--workflow-manifest', str(self.workflow_manifest), '--tools-dir', str(self.tools),
            '--proot-dir', str(self.proot), '--input-dir', str(self.ime),
            '--input-payload', str(self.input_payload), '--input-manifest', str(self.input_manifest)]

    def tree_snapshot(self, root):
        return {str(p.relative_to(root)): (p.lstat().st_ino, p.lstat().st_mode,
                p.lstat().st_mtime_ns, os.readlink(p) if p.is_symlink() else
                (p.read_bytes() if p.is_file() else None))
                for p in [root, *sorted(root.rglob('*'))]}

    def run_setup(self, existing=False):
        env = dict(os.environ, HOME=str(self.home), PREFIX=str(self.prefix))
        env.pop('PYTHONPATH', None)
        before = self.tree_snapshot(self.home), self.tree_snapshot(self.prefix)
        result = subprocess.run([sys.executable, str(SOURCE), *self.arguments()], shell=False, env=env, capture_output=True,
            text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, '')
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual((self.tree_snapshot(self.home), self.tree_snapshot(self.prefix)), before)
        if not existing:
            self.assertFalse(self.root.exists())
            self.assertEqual(list(self.prefix.iterdir()), [])
        return report

    def prepare_existing(self):
        tree = ast.parse((REPO / 'termux/omarchy_install.py').read_text())
        values = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
                  if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                  and n.targets[0].id in ('HOST_FILES', 'RUNTIME_SHA', 'OUTER_SHA')}
        self.root.mkdir(parents=True, mode=0o700)
        self.rootfs = self.prefix / 'var/lib/proot-distro/containers/loopy-omarchy/rootfs'
        self.rootfs.mkdir(parents=True, mode=0o700)
        identity = lambda p: [p.stat().st_dev, p.stat().st_ino, p.stat().st_uid]
        import hashlib
        managed = {}
        for name, original in values['HOST_FILES'].items():
            target = self.root / name; target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(REPO/'third_party/cache/omarchy-android-c189d33/bundle'/original, target)
            target.chmod(0o600); managed[name] = hashlib.sha256(target.read_bytes()).hexdigest()
        for name in FILES:
            shutil.copyfile(self.sources/name, self.root/name); (self.root/name).chmod(0o600)
        row = dict(schema=1, phase='INSTALLED', uid=os.getuid(), root=identity(self.root),
            home=str(self.home), prefix=str(self.prefix), container='loopy-omarchy',
            bundle_sha256=values['OUTER_SHA'], container_identity=identity(self.rootfs.parent),
            rootfs_identity=identity(self.rootfs), managed_files=managed, runtime_files=values['RUNTIME_SHA'])
        for name, value in [('install.json', row), ('runtime-state.json', {'phase':'stopped','terminationConfirmed':True})]:
            (self.root/name).write_text(json.dumps(value)); (self.root/name).chmod(0o600)
        for name in ('install.lock','runtime-control.lock'):
            (self.root/name).write_bytes(b''); (self.root/name).chmod(0o600)
        receipt = REPO/'build/diagnostics/termux-omarchy-input-readonly-device-20261009-03/receipt.json'
        old = next(r['source'].encode() for r in json.loads(receipt.read_bytes())['inputConfigFiles']
                   if r['relative']=='.config/hypr/autostart.lua')
        target=self.rootfs/'home/omarchy/.config/hypr/autostart.lua'
        target.parent.mkdir(parents=True, mode=0o700); target.write_bytes(old); target.chmod(0o644)
        (self.home/'.zshrc').write_bytes(b'public personal profile')

    def test_changed_gpu_payload_is_refused_before_base_installation(self):
        with self.payload.open('ab') as stream:
            stream.write(b'public changed payload')
        self.assertEqual(self.run_setup()['stage'], 'host-validation')

    def test_changed_manifest_is_refused_before_base_installation(self):
        with self.manifest.open('ab') as stream:
            stream.write(b'public changed manifest')
        self.assertEqual(self.run_setup()['stage'], 'host-validation')

    def test_missing_launcher_dependency_is_refused_before_base_installation(self):
        (self.sources / 'omarchy_audio.py').unlink()
        report = self.run_setup()
        self.assertEqual(report['stage'], 'runtime-validation')
        self.assertEqual(report['reason'], 'omarchy-source-filesystem')

    def test_changed_guest_payload_is_refused_before_base_installation(self):
        with self.guest_payload.open('ab') as stream:
            stream.write(b'public changed guest payload')
        self.assertEqual(self.run_setup()['stage'], 'guest-validation')

    def test_changed_guest_manifest_is_refused_before_base_installation(self):
        with self.guest_manifest.open('ab') as stream:
            stream.write(b'public changed guest manifest')
        self.assertEqual(self.run_setup()['stage'], 'guest-validation')

    def test_changed_workflow_payload_is_refused_before_base_installation(self):
        with self.workflow_payload.open('ab') as stream:
            stream.write(b'public changed workflow payload')
        self.assertEqual(self.run_setup()['stage'], 'workflow-validation')

    def test_changed_workflow_manifest_is_refused_before_base_installation(self):
        with self.workflow_manifest.open('ab') as stream:
            stream.write(b'public changed workflow manifest')
        self.assertEqual(self.run_setup()['stage'], 'workflow-validation')

    def test_changed_tools_manifest_is_refused_before_base_installation(self):
        with (self.tools / 'tools-manifest.json').open('ab') as stream:
            stream.write(b'public changed tools manifest')
        self.assertEqual(self.run_setup()['stage'], 'tools-validation')

    def test_changed_package_signature_is_refused_before_base_installation(self):
        signature = next(self.tools.glob('*.sig'))
        with signature.open('ab') as stream:
            stream.write(b'public changed package signature')
        self.assertEqual(self.run_setup()['stage'], 'tools-validation')

    def test_changed_proot_is_refused_before_base_installation(self):
        with (self.proot/'proot').open('ab') as stream: stream.write(b'changed')
        self.assertEqual(self.run_setup()['stage'], 'proot-validation')

    def test_extra_private_proot_member_is_refused_before_base_installation(self):
        (self.proot/'unexpected').write_bytes(b'public extra')
        self.assertEqual(self.run_setup()['stage'], 'proot-validation')

    def test_changed_input_signature_is_refused_before_base_installation(self):
        with next(self.ime.glob('*.sig')).open('ab') as stream: stream.write(b'changed')
        self.assertEqual(self.run_setup()['stage'], 'input-validation')

    def test_changed_input_payload_is_refused_before_base_installation(self):
        with self.input_payload.open('ab') as stream: stream.write(b'changed')
        self.assertEqual(self.run_setup()['stage'], 'input-validation')

    def test_changed_input_manifest_is_refused_before_base_installation(self):
        with self.input_manifest.open('ab') as stream: stream.write(b'changed')
        self.assertEqual(self.run_setup()['stage'], 'input-validation')

    def test_personal_input_config_is_preserved_before_any_existing_component_write(self):
        self.prepare_existing()
        target=self.rootfs/'home/omarchy/.config/gtk-3.0/settings.ini'
        target.parent.mkdir(mode=0o700); target.write_bytes(b'public personal settings'); target.chmod(0o644)
        report=self.run_setup(existing=True)
        self.assertEqual(report['stage'],'existing-input-validation')
        self.assertEqual(report['reason'],'guest-user-file-changed')

    def test_old_runtime_is_not_migrated_by_fresh_setup(self):
        self.prepare_existing()
        (self.root/'omarchy_runtime.py').write_bytes(b'public earlier runtime')
        self.assertEqual(self.run_setup(existing=True)['stage'],'existing-runtime-validation')

    def test_missing_current_runtime_module_is_not_added_to_existing_install(self):
        self.prepare_existing(); (self.root/'omarchy_commands.py').unlink()
        self.assertEqual(self.run_setup(existing=True)['stage'],'existing-runtime-validation')

    def test_live_existing_session_is_preserved_before_guard_or_machine_id_work(self):
        self.prepare_existing()
        (self.root/'runtime-state.json').write_text(json.dumps({'phase':'ready'}))
        self.assertEqual(self.run_setup(existing=True)['stage'],'existing-runtime-validation')

    def test_existing_lock_contention_is_no_write(self):
        self.prepare_existing()
        for name in ('install.lock','runtime-control.lock'):
            with (self.root/name).open('r+') as lock:
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                self.assertEqual(self.run_setup(existing=True)['stage'],'existing-runtime-validation')

    def test_complete_existing_targets_are_validated_before_base_bundle_open(self):
        self.prepare_existing()
        self.assertEqual(self.run_setup(existing=True)['stage'],'base-installation')

    def test_fresh_orchestration_installs_real_guard_id_and_ime_then_reuses_them(self):
        # The macOS host substitutes the unrelated rootfs/Weston/guest/workflow
        # preparation and external pacman/GPG processes. New component installers,
        # every source validator, files, source pins, backups and journals are real.
        import test_termux_omarchy_tools as packages
        sys.path.insert(0, str(SOURCE.parent)); self.addCleanup(sys.path.remove, str(SOURCE.parent))
        spec=importlib.util.spec_from_file_location('tested_fresh_setup',SOURCE)
        setup=importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)
        prepared=False
        def prepare_base(*args, **kwargs):
            nonlocal prepared
            if not prepared:
                self.prepare_existing()
                for name in ('etc/pacman.conf','var/lib/pacman/sync/core.db','var/lib/pacman/sync/extra.db'):
                    p=self.rootfs/name; p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                    p.write_bytes(b'public immutable database'); p.chmod(0o600)
                etc=self.rootfs/'etc/machine-id'; etc.write_bytes(b''); etc.chmod(0o444)
                dbus=self.rootfs/'var/lib/dbus/machine-id'; dbus.parent.mkdir(mode=0o700)
                dbus.symlink_to('/etc/machine-id')
                prepared=True
            return json.loads((self.root/'install.json').read_bytes())
        actual_guest=setup.guest.install
        def guest_component(*args, **kwargs):
            if kwargs.get('component') is not None: return actual_guest(*args,**kwargs)
            return {'fixture':'unrelated-existing-guest-component'}
        def workflow_component(*args, **kwargs):
            self.assertRegex((self.rootfs/'etc/machine-id').read_bytes(),rb'^[a-f0-9]{32}\n$')
            self.assertEqual(json.loads((self.root/'machine-id-install.json').read_bytes())['phase'],'INSTALLED')
            return {'fixture':'unrelated-existing-workflow-component'}
        transports={}
        def transport(argv, **kwargs):
            stage=self.rootfs/argv[10].lstrip('/')
            korean='--korean-input' in argv
            if str(stage) not in transports:
                manifest='ime-manifest.json' if korean else 'tools-manifest.json'
                rows=json.loads((stage/manifest).read_bytes())['packages']
                transports[str(stage)]=packages.PackageCommands(stage,rows)
            with mock.patch.object(setup.tools.worker.os,'getuid',return_value=0):
                row=setup.tools.worker.execute(stage,korean_input=korean,install='--install' in argv,
                    before=argv[argv.index('--before')+1] if '--before' in argv else None,
                    runner=transports[str(stage)])
            return json.dumps(row)
        def run():
            output=io.StringIO()
            with contextlib.redirect_stdout(output): result=setup.main(self.arguments())
            row=json.loads(output.getvalue()); self.assertEqual(result,0,row)
            return row
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.dict(os.environ,HOME=str(self.home),PREFIX=str(self.prefix)))
            stack.enter_context(mock.patch.object(setup.base,'install',side_effect=prepare_base))
            stack.enter_context(mock.patch.object(setup.host,'install',return_value={'fixture':'existing-weston'}))
            stack.enter_context(mock.patch.object(setup.guest,'install',side_effect=guest_component))
            stack.enter_context(mock.patch.object(setup.workflow,'install',side_effect=workflow_component))
            stack.enter_context(mock.patch.object(setup.tools,'run_bounded',side_effect=transport))
            result=run()
            self.assertEqual(result['prootGuard']['phase'],'INSTALLED')
            self.assertEqual(result['input']['packages']['signaturesVerified'],7)
            self.assertEqual(result['input']['config']['filesVerified'],5)
            self.assertFalse(result['input']['physicalKoreanInputVerified'])
            self.assertFalse(result['fullDesktopConfigured'])
            self.assertEqual(set(p.name for p in (self.root/'proot-guard').iterdir()),
                             {'proot','loader','libandroid-shmem.so'})
            self.assertEqual(os.readlink(self.rootfs/'var/lib/dbus/machine-id'),'/etc/machine-id')
            self.assertNotIn((self.rootfs/'etc/machine-id').read_text().strip(),json.dumps(result))
            before=self.tree_snapshot(self.home),self.tree_snapshot(self.prefix)
            again=run()
            self.assertEqual(again,result)
            self.assertEqual((self.tree_snapshot(self.home),self.tree_snapshot(self.prefix)),before)


if __name__ == '__main__':
    unittest.main()
