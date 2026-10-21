"""Historical setup08 payloads and filesystem boundaries; no current-bundle claim."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / 'tools/package_termux_omarchy_setup.py'
CATALOG = REPO / 'third_party/termux-omarchy-setup-20261009-08.lock.json'
FROZEN_ARCHIVE = REPO / 'build/deliverables/LoopyOmarchy-Termux-native-setup-20261009-08.tar.gz'
FROZEN_ARCHIVE_SHA = 'e6e1c4805d3be31a4f22efb31b2e5b73a1d3ae51604ea7bb4ff208dc75335d0f'
ADVANCED_RUNTIME_SOURCES = ('omarchy_install.py', 'omarchy_resources.py', 'omarchy_runtime.py', 'processes.py')


class PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # These four sources advanced after setup08. Cache only their approved small members,
        # so historical packaging tests do not silently become tests of a new runtime bundle.
        catalog = json.loads(CATALOG.read_bytes())
        digest = hashlib.sha256()
        with FROZEN_ARCHIVE.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != FROZEN_ARCHIVE_SHA:
            raise AssertionError('historical setup08 archive SHA mismatch')
        cls.frozen_runtime = {}
        with tarfile.open(FROZEN_ARCHIVE, 'r:gz') as archive:
            for name in ADVANCED_RUNTIME_SOURCES:
                member = archive.getmember(catalog['kit'] + '/' + name)
                row = catalog['files'][name]
                if not member.isfile() or member.size != row['bytes']:
                    raise AssertionError('historical setup08 member type/size: ' + name)
                content = archive.extractfile(member).read()
                if len(content) != row['bytes'] or hashlib.sha256(content).hexdigest() != row['sha256']:
                    raise AssertionError('historical setup08 member SHA: ' + name)
                cls.frozen_runtime[name] = content

    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'fresh setup packager missing')
        spec = importlib.util.spec_from_file_location('tested_setup_packager', SOURCE)
        self.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name).resolve()
        self.repo = self.directory / 'repo'; self.repo.mkdir(mode=0o700)
        self.output = self.directory / 'setup08'
        self.catalog = json.loads(CATALOG.read_bytes())
        for name, row in self.catalog['files'].items():
            path = self.repo / row['source']; path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            source = REPO / row['source']
            if name in self.frozen_runtime and hashlib.sha256(source.read_bytes()).hexdigest() != row['sha256']:
                path.write_bytes(self.frozen_runtime[name])
            else:
                shutil.copyfile(source, path)
            path.chmod(0o600)

    def package(self):
        return self.m.package(self.repo, self.output)

    def rejected(self):
        with self.assertRaises((ValueError, OSError)):
            self.package()
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()), ['repo'])

    def source(self, name):
        return self.repo / self.catalog['files'][name]['source']

    def test_changed_current_source_is_refused_before_output_creation(self):
        with self.source('omarchy_setup.py').open('ab') as stream: stream.write(b'\n# changed\n')
        self.rejected()

    def test_changed_pinned_catalog_is_refused_before_output_creation(self):
        path = self.repo / 'tampered-catalog.json'
        catalog = dict(self.catalog, kit='unreviewed-new-kit')
        path.write_bytes(json.dumps(catalog).encode()); path.chmod(0o600)
        with mock.patch.object(self.m, 'CATALOG', path): self.rejected()

    def test_missing_runtime_module_is_refused_before_output_creation(self):
        self.source('omarchy_commands.py').unlink(); self.rejected()

    def test_changed_native_guard_is_refused_before_output_creation(self):
        with self.source('proot-guard/proot').open('ab') as stream: stream.write(b'changed')
        self.rejected()

    def test_changed_input_signature_is_refused_before_output_creation(self):
        name=next(n for n in self.catalog['files'] if n.startswith('korean-input/') and n.endswith('.sig'))
        with self.source(name).open('ab') as stream: stream.write(b'changed')
        self.rejected()

    def test_changed_payload_or_component_manifest_is_refused_before_output_creation(self):
        for name in ('payload.tar','guest-manifest.json','workflow-payload.tar','input-config-manifest.json'):
            path=self.source(name); before=path.read_bytes(); path.write_bytes(before+b'changed')
            self.rejected(); path.write_bytes(before)

    def test_historical_setup08_workflow_packages_pinned_profile_and_preserves_other_members(self):
        _, data, _ = self.m.validate(self.repo)
        previous = REPO / 'build/diagnostics/termux-omarchy-workflow-payload-20261009-01'
        with tarfile.open(fileobj=io.BytesIO(data['workflow-payload.tar']), mode='r:') as archive:
            members = {row.name: archive.extractfile(row).read() for row in archive}
        # setup08 keeps its reviewed F13/F14 snapshot; current bindings.lua advances separately.
        changed = 'guest/home/omarchy/.local/share/loopy-omarchy-profile/bindings.lua'
        self.assertEqual(hashlib.sha256(members[changed]).hexdigest(),
                         '1a8af509d9f543fba57dbf3cfa81aabfdf7c3397eb23fa96f98744cd86f66bb3')
        for name in ('zshrc', 'tmux.conf', 'git.zsh', 'git.plugin.zsh'):
            self.assertEqual(members['guest/home/omarchy/.local/share/loopy-omarchy-profile/' + name],
                             (REPO / 'termux/profile' / name).read_bytes(), name)
        with tarfile.open(previous / 'workflow-payload.tar', 'r:') as archive:
            originals = {row.name: archive.extractfile(row).read() for row in archive}
        self.assertEqual(set(members), set(originals))
        self.assertEqual({name: content for name, content in members.items() if name != changed},
                         {name: content for name, content in originals.items() if name != changed})
        manifest = json.loads(data['workflow-manifest.json'])
        original_manifest = json.loads((previous / 'workflow-manifest.json').read_bytes())
        path = changed[len('guest/'):]
        self.assertEqual(manifest['files'][path]['before'], original_manifest['files'][path]['before'])
        self.assertEqual(manifest['files'][path]['mode'], original_manifest['files'][path]['mode'])
        self.assertEqual({name: row for name, row in manifest['files'].items() if name != path},
                         {name: row for name, row in original_manifest['files'].items() if name != path})

    def test_source_symlink_hardlink_and_writable_file_are_refused(self):
        target=self.source('omarchy_setup.py'); data=target.read_bytes()
        outside=self.directory/'outside'; outside.write_bytes(data); outside.chmod(0o600)
        target.unlink(); target.symlink_to(outside)
        with self.assertRaises((ValueError,OSError)): self.package()
        self.assertEqual(outside.read_bytes(),data); target.unlink(); target.write_bytes(data); target.chmod(0o600)
        outside.unlink(); os.link(target,outside)
        with self.assertRaises((ValueError,OSError)): self.package()
        outside.unlink(); target.chmod(0o666); self.rejected()

    def test_parent_directory_symlink_is_refused(self):
        parent=self.source('omarchy_setup.py').parent
        real=parent.with_name('real-termux'); parent.rename(real); parent.symlink_to(real)
        self.rejected()

    def test_existing_directory_archive_checksum_or_receipt_is_never_replaced(self):
        for suffix in ('','.tar.gz','.tar.gz.sha256','.packaging.json'):
            path=Path(str(self.output)+suffix)
            if not suffix: path.mkdir(mode=0o700); (path/'personal').write_bytes(b'public previous')
            else: path.write_bytes(b'public previous')
            before=path.lstat()
            with self.assertRaises((ValueError,OSError)): self.package()
            self.assertEqual(path.lstat(),before)
            if not suffix: self.assertEqual((path/'personal').read_bytes(),b'public previous'); shutil.rmtree(path)
            else: self.assertEqual(path.read_bytes(),b'public previous'); path.unlink()

    def test_output_created_after_preflight_is_not_replaced_at_publication(self):
        publish = self.m.publish
        def collision(fd, source, target):
            self.output.mkdir(mode=0o700)
            (self.output / 'personal').write_bytes(b'public concurrent output')
            return publish(fd, source, target)
        with mock.patch.object(self.m, 'publish', collision):
            with self.assertRaises(OSError): self.package()
        self.assertEqual(list(self.output.iterdir()), [self.output / 'personal'])
        self.assertEqual((self.output / 'personal').read_bytes(), b'public concurrent output')
        self.assertFalse(Path(str(self.output) + '.packaging.json').exists())
        stages = list(self.directory.glob('.fresh-setup-stage-*'))
        self.assertEqual(len(stages), 1)
        self.assertEqual(stages[0].stat().st_mode & 0o777, 0o700)

    def test_complete_kit_contains_closed_sources_exact_manifests_and_no_device_claim(self):
        result=self.package()
        self.assertEqual(result['status'],'packaged-verified-bytes')
        self.assertEqual(result['kit'], 'LoopyOmarchy-Termux-native-setup-20261009-08')
        self.assertEqual((self.output/'source-catalog.json').read_bytes(), CATALOG.read_bytes())
        self.assertFalse(result['fullDesktopConfigured'])
        self.assertFalse(result['freshDeviceInstallVerified'])
        manifest=json.loads((self.output/'manifest.json').read_bytes())
        self.assertEqual(manifest['componentCounts'],{'sourceFiles':21,'runtimeFiles':11,'privateProotFiles':3,
            'westonFiles':87,'guestFiles':11,'workflowFiles':15,'developerPackages':29,'inputPackages':7,'inputConfigFiles':5})
        self.assertNotIn('omarchy_runtime_update.py',manifest['files'])
        self.assertEqual(set(p.name for p in (self.output/'proot-guard').iterdir()),{'proot','loader','libandroid-shmem.so'})
        for name,row in manifest['files'].items():
            path=self.output/name; data=path.read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),row['sha256'])
            self.assertEqual(len(data),row['bytes'])
            self.assertEqual(path.stat().st_mode & 0o777,row['mode'])
        bundle=json.loads((self.output/'external-bundle.json').read_bytes())
        self.assertEqual(bundle['bytes'],1181941760)
        self.assertTrue(bundle['url'].startswith('https://github.com/BlackFireAlex/omarchy-android/releases/'))
        self.assertFalse((self.output/'bundle.tar').exists())
        for name in ('install.json','machine-id-install.json','runtime-update.json','runtime-state.json'):
            self.assertFalse((self.output/name).exists())
        sums=(self.output/'SHA256SUMS').read_text().splitlines()
        for line in sums:
            expected,name=line.split('  ',1)
            self.assertEqual(hashlib.sha256((self.output/name).read_bytes()).hexdigest(),expected)
        archive=Path(str(self.output)+'.tar.gz')
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),result['archiveSHA256'])
        with tarfile.open(archive,'r:gz') as tar:
            self.assertTrue(all(row.isfile() or row.isdir() for row in tar))
            rows=[row for row in tar if row.isfile()]
            self.assertEqual(len(rows),result['archiveFileCount'])
            for row in rows:
                self.assertEqual(row.uid,0); self.assertEqual(row.gid,0); self.assertEqual(row.mtime,0)
                self.assertEqual(tar.extractfile(row).read(),(self.output/Path(row.name).relative_to(self.m.KIT)).read_bytes())

    def test_repeated_build_is_byte_reproducible_and_preserves_previous_kit(self):
        first=self.package(); archive=Path(str(self.output)+'.tar.gz'); before=archive.read_bytes()
        first_directory=self.output
        self.output=self.directory/'other-name'
        second=self.package()
        self.assertEqual(first['archiveSHA256'],second['archiveSHA256'])
        self.assertEqual(Path(str(self.output)+'.tar.gz').read_bytes(),before)
        self.assertEqual((first_directory/'manifest.json').read_bytes(),(self.output/'manifest.json').read_bytes())

    def test_packed_default_setup_rejects_missing_external_bundle_without_creating_install(self):
        self.package()
        home,prefix=self.directory/'home',self.directory/'prefix'
        home.mkdir(mode=0o700); prefix.mkdir(mode=0o700)
        env=dict(os.environ,HOME=str(home),PREFIX=str(prefix),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run([sys.executable,str(self.output/'omarchy_setup.py'),'--bundle',str(home/'absent.tar')],
            env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertEqual(json.loads(result.stdout)['stage'],'base-installation')
        self.assertEqual(list(home.iterdir()),[]); self.assertEqual(list(prefix.iterdir()),[])


if __name__ == '__main__': unittest.main()
