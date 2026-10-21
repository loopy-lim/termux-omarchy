"""Pinned real watchdog processes; host dependency adapters do not replace its loop."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import tarfile
import time
import unittest
from unittest import mock

from tools import prepare_omarchy_watchdog as prepare

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/omarchy-watchdog'
PATCH = ROOT / 'native/omarchy/patches/hyprland-gpu-recovery.patch'
METADATA = PATCH.with_suffix('.json')

ADAPTERS = {
 'hyprutils/memory/WeakPtr.hpp': r'''#pragma once
#include <memory>
#include <utility>
namespace Hyprutils::Memory {
template<class T> using CSharedPointer=std::shared_ptr<T>;
template<class T> using CWeakPointer=std::weak_ptr<T>;
template<class T> using CUniquePointer=std::unique_ptr<T>;
template<class T,class... A> auto makeUnique(A&&... a){return std::make_unique<T>(std::forward<A>(a)...);}
}''',
 'hyprutils/memory/Atomic.hpp': r'''#pragma once
#include "WeakPtr.hpp"
namespace Hyprutils::Memory { template<class T> using CAtomicSharedPointer=std::shared_ptr<T>; }''',
 'hyprutils/cli/Logger.hpp': r'''#pragma once
#include <array>
#include <format>
#include <string>
#include <vector>
#include <cstdio>
namespace Hyprutils::CLI {
enum { LOG_CRIT,LOG_WARN,LOG_DEBUG,LOG_ERR }; class CLogger {};
class CLoggerConnection { public:
 CLoggerConnection(CLogger&){} void setName(const char*){} void setLogLevel(int){}
 template<class... A> void log(int,std::format_string<A...> f,A&&... a){
  auto s=std::format(f,std::forward<A>(a)...); std::fprintf(stderr,"%s\n",s.c_str());
 }
}; }''',
 'hyprutils/os/FileDescriptor.hpp': r'''#pragma once
#include <fcntl.h>
#include <unistd.h>
#include <utility>
namespace Hyprutils::OS {
class CFileDescriptor {
 int fd=-1; public:
 CFileDescriptor()=default; CFileDescriptor(int n):fd(n){} ~CFileDescriptor(){if(fd>=0)close(fd);}
 CFileDescriptor(const CFileDescriptor&)=delete;
 CFileDescriptor(CFileDescriptor&& o):fd(std::exchange(o.fd,-1)){}
 CFileDescriptor& operator=(CFileDescriptor&& o){if(fd>=0)close(fd);fd=std::exchange(o.fd,-1);return *this;}
 int get() const{return fd;} int getFlags() const{return fcntl(fd,F_GETFD);}
 void setFlags(int f){fcntl(fd,F_SETFD,f);} bool isReadable() const{return (fcntl(fd,F_GETFL)&O_ACCMODE)!=O_WRONLY;}
}; }''',
 'hyprutils/os/Process.hpp': '#pragma once\n#include <format>\n',
 'NixAdapter.cpp': r'''#include "helpers/Nix.hpp"
namespace Nix {
std::expected<void,std::string> nixEnvironmentOk(){return {};}
bool shouldUseNixGL(){return false;}
}''',
}

CHILD = r'''import json,os,resource,signal,sys,time
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
fd=int(sys.argv[sys.argv.index('--watchdog-fd')+1])
path=os.environ['LOOPY_TEST_LOG']
try:
 with open(path) as f: number=len(f.readlines())+1
except FileNotFoundError: number=1
with open(path,'a') as f:
 f.write(json.dumps({'pid':os.getpid(),'args':sys.argv[1:],
  'env':dict(os.environ)})+'\n'); f.flush()
mode=os.environ['LOOPY_TEST_MODE']
if mode=='startup': sys.exit(7)
os.write(fd,b'vax\n')
if mode=='cancel': time.sleep(30)
if mode=='repeat' and number<3: sys.exit(9)
if mode=='signal' and number==1: os.kill(os.getpid(),signal.SIGABRT)
if mode in ('recover','software') and number==1: sys.exit(9)
os.write(fd,b'end\n')
sys.exit(0)
'''


class OmarchyWatchdogProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='loopy-watchdog-test-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.work = Path(cls.directory.name)
        cls.source = cls.work / 'source'
        identities = json.loads((FIXTURE / 'upstream.json').read_text())
        for name, digest in identities['files'].items():
            if hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() != digest:
                raise AssertionError('Pinned watchdog fixture changed: ' + name)
        shutil.copytree(FIXTURE, cls.source)
        # Initial TDD run uses the identical original loop; implementation adds this patch.
        if METADATA.exists():
            prepare.apply_recovery_patch(cls.source, PATCH, json.loads(METADATA.read_text()))
        cls.adapters = cls.work / 'adapters'
        for name, content in ADAPTERS.items():
            target = cls.adapters / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        cls.binary = cls.work / 'start-hyprland'
        compiled = subprocess.run([shutil.which('c++'), '-std=c++23', '-pthread', '-Wno-c++11-narrowing', '-include', 'csignal',
            '-I' + str(cls.adapters), '-I' + str(cls.source / 'start/src'),
            str(cls.source / 'start/src/main.cpp'), str(cls.source / 'start/src/core/Instance.cpp'),
            str(cls.adapters / 'NixAdapter.cpp'), '-o', str(cls.binary)],
            capture_output=True, text=True, timeout=30)
        if compiled.returncode:
            raise AssertionError(compiled.stderr)
        cls.child = cls.work / 'child'
        cls.child.write_text('#!' + sys.executable + '\n' + CHILD)
        cls.child.chmod(0o700)

    def start(self, mode, *, gpu=True, route=None):
        log = self.work / (self.id().split('.')[-1] + str(time.monotonic_ns()) + '.jsonl')
        env = {'PATH': os.defpath, 'LOOPY_SESSION': 'current-1', 'LOOPY_TEST_LOG': str(log),
               'LOOPY_TEST_MODE': mode, 'LIBGL_ALWAYS_SOFTWARE': '1',
               'QT_QUICK_BACKEND': 'software', 'LOOPY_TEST_KEEP': 'owned-session'}
        if gpu:
            env.update(GALLIUM_DRIVER='virpipe', VTEST_SOCKET_NAME=route or '/run/loopy/virgl-current-1.sock',
                       EGL_PLATFORM='surfaceless')
        child = subprocess.Popen([str(self.binary), '--path', str(self.child), '--no-nixgl'],
            env=env, cwd=self.work, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True)
        return child, log

    def finish(self, child, log):
        try:
            _, errors = child.communicate(timeout=6)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
            self.fail('Owned watchdog did not complete within 6 seconds')
        launches = [json.loads(line) for line in log.read_text().splitlines()]
        return child.returncode, launches, errors

    def assert_software(self, launch):
        env = launch['env']
        for variable in ('GALLIUM_DRIVER', 'VTEST_SOCKET_NAME', 'EGL_PLATFORM'):
            self.assertNotIn(variable, env, 'GPU route leaked into software retry')
        self.assertEqual(env['LIBGL_ALWAYS_SOFTWARE'], '1')
        self.assertEqual(env['QT_QUICK_BACKEND'], 'software')
        self.assertEqual(env['LOOPY_TEST_KEEP'], 'owned-session')
        self.assertEqual(env['LOOPY_SESSION'], 'current-1')
        self.assertIn('--safe-mode', launch['args'])

    def test_first_abnormal_gpu_exit_retries_real_child_with_software_environment(self):
        code, launches, errors = self.finish(*self.start('recover'))
        self.assertEqual(code, 0, errors)
        self.assertEqual(len(launches), 2)
        self.assertEqual(launches[0]['env']['GALLIUM_DRIVER'], 'virpipe')
        self.assert_software(launches[1])

    def test_second_abnormal_exit_stops_at_two_real_launches(self):
        code, launches, errors = self.finish(*self.start('repeat'))
        self.assertEqual(len(launches), 2, errors)
        self.assertEqual(code, 1)
        self.assert_software(launches[1])

    def test_signaled_gpu_child_uses_the_same_original_watchdog_classification(self):
        code, launches, errors = self.finish(*self.start('signal'))
        self.assertEqual(code, 0, errors)
        self.assertEqual(len(launches), 2)
        self.assert_software(launches[1])

    def test_clean_and_startup_failure_preserve_original_exit_contract(self):
        for mode in ('normal', 'startup'):
            with self.subTest(mode=mode):
                child, log = self.start(mode)
                code, launches, errors = self.finish(child, log)
                self.assertEqual(code, 0, errors)
                self.assertEqual(len(launches), 1)
                self.assertEqual(launches[0]['env']['GALLIUM_DRIVER'], 'virpipe')

    def test_initial_software_and_foreign_route_keep_original_restart_behavior(self):
        for gpu, route in ((False, None), (True, '/run/loopy/virgl-stale.sock'),
                           (True, '/tmp/virgl-current-1.sock')):
            with self.subTest(gpu=gpu, route=route):
                child, log = self.start('software', gpu=gpu, route=route)
                code, launches, errors = self.finish(child, log)
                self.assertEqual(code, 0, errors)
                self.assertEqual(len(launches), 2)
                self.assertEqual(launches[0]['env'], launches[1]['env'])

    def test_wrapper_cancellation_terminates_owned_child_without_retry(self):
        child, log = self.start('cancel')
        deadline = time.monotonic() + 4
        while not log.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        child.terminate()
        code, launches, errors = self.finish(child, log)
        self.assertEqual(code, 0, errors)
        self.assertEqual(len(launches), 1)
        with self.assertRaises(ProcessLookupError):
            os.kill(launches[0]['pid'], 0)


class OmarchyWatchdogSourceGuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='loopy-watchdog-guard-',
            dir='/private/tmp' if sys.platform == 'darwin' else None)
        self.addCleanup(self.directory.cleanup)
        self.work = Path(self.directory.name)
        self.archive = self.work / 'upstream.tar.gz'
        self.write_archive()
        self.patch = self.work / 'recovery.patch'
        self.patch.write_bytes(PATCH.read_bytes())
        self.metadata_path = self.work / 'recovery.json'
        self.metadata = json.loads(METADATA.read_text())
        self.metadata['upstream_archive_sha256'] = prepare.sha(self.archive)
        self.metadata_path.write_text(json.dumps(self.metadata))
        self.modules = self.work / 'modules'
        for name in self.metadata['added_files']:
            target = self.modules / Path(name).name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((prepare.MODULES / Path(name).name).read_bytes())
        self.destination = self.work / 'candidate'
        # Synthetic archive contains exact licensed source preimages. Production pins
        # are never edited; test-local identities let every downstream guard execute.
        fixture = mock.patch.multiple(prepare, PATCH=self.patch, METADATA=self.metadata_path,
            MODULES=self.modules, ARCHIVE_SHA256=prepare.sha(self.archive),
            METADATA_SHA256=prepare.sha(self.metadata_path))
        fixture.start()
        self.addCleanup(fixture.stop)

    def write_archive(self, *, changed=None):
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name in json.loads((FIXTURE / 'upstream.json').read_text())['files']:
                if name == changed:
                    copy = self.work / 'changed.cpp'
                    copy.write_bytes((FIXTURE / name).read_bytes() + b'// source drift\n')
                    archive.add(copy, arcname='Hyprland-' + prepare.COMMIT + '/' + name)
                else:
                    archive.add(FIXTURE / name, arcname='Hyprland-' + prepare.COMMIT + '/' + name)

    def test_complete_candidate_inventory_and_producer_are_verified(self):
        receipt = prepare.prepare(self.archive, self.destination)
        self.assertEqual(receipt, prepare.verify_candidate(self.destination))
        self.assertEqual(len(receipt['source_files']), 11)
        for key in ('compiled', 'packaged', 'android_gui_accepted'):
            self.assertIs(receipt[key], False)
        original = (FIXTURE / 'start/src/core/Instance.cpp').read_bytes()
        self.assertEqual((self.destination / 'start/src/core/Instance.cpp').read_bytes(), original)
        self.assertEqual(receipt['producer_sha256'], prepare.sha(prepare.__file__))

    def test_metadata_patch_and_policy_drift_never_publish_a_candidate(self):
        policy = self.modules / 'LoopyGpuRecovery.hpp'
        for target in (self.metadata_path, self.patch, policy):
            with self.subTest(input=target.name):
                original = target.read_bytes()
                target.write_bytes(original + b'\n')
                with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                    prepare.prepare(self.archive, self.destination)
                self.assertFalse(self.destination.exists())
                target.write_bytes(original)

    def test_source_preimage_drift_is_rejected_even_with_matching_archive_digest(self):
        self.write_archive(changed='start/src/main.cpp')
        self.metadata['upstream_archive_sha256'] = prepare.sha(self.archive)
        self.metadata_path.write_text(json.dumps(self.metadata))
        with mock.patch.multiple(prepare, ARCHIVE_SHA256=prepare.sha(self.archive),
                                 METADATA_SHA256=prepare.sha(self.metadata_path)):
            with self.assertRaisesRegex(ValueError, 'source preimage mismatch'):
                prepare.prepare(self.archive, self.destination)
        self.assertFalse(self.destination.exists())

    def test_existing_candidate_and_redirected_paths_are_preserved(self):
        prepare.prepare(self.archive, self.destination)
        witness = self.destination / 'owned-witness'
        witness.write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'Refuse to replace'):
            prepare.prepare(self.archive, self.destination)
        self.assertEqual(witness.read_text(), 'preserve')
        link = self.work / 'redirect'
        link.symlink_to(self.destination, target_is_directory=True)
        for destination in (link, link / 'new'):
            with self.subTest(destination=destination):
                with self.assertRaisesRegex(ValueError, 'Refuse'):
                    prepare.prepare(self.archive, destination)
        self.assertFalse((self.destination / 'new').exists())
        archive_link = self.work / 'archive-link'
        archive_link.symlink_to(self.archive)
        with self.assertRaisesRegex(ValueError, 'redirected'):
            prepare.prepare(archive_link, self.work / 'other-candidate')

    def test_consumer_rejects_redirected_candidate_ancestor(self):
        prepare.prepare(self.archive, self.destination)
        parent_link = self.work / 'linked-parent'
        parent_link.symlink_to(self.work, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'redirected'):
            prepare.verify_candidate(parent_link / self.destination.name)

    def test_consumer_rejects_producer_dependency_drift(self):
        prepare.prepare(self.archive, self.destination)
        original_sha = prepare.sha
        def changed_dependency(path):
            if Path(path).name == 'build_omarchy_graphics.py':
                return '0' * 64
            return original_sha(path)
        with mock.patch.object(prepare, 'sha', side_effect=changed_dependency):
            with self.assertRaisesRegex(ValueError, 'receipt identity mismatch'):
                prepare.verify_candidate(self.destination)

    def test_consumer_rejects_modified_sources_receipts_and_extra_inputs(self):
        prepare.prepare(self.archive, self.destination)
        source = self.destination / 'start/src/main.cpp'
        original = source.read_bytes()
        source.write_bytes(original + b'// modified\n')
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            prepare.verify_candidate(self.destination)
        source.write_bytes(original)
        receipt_path = self.destination / prepare.RECEIPT
        original_receipt = receipt_path.read_bytes()
        receipt = json.loads(original_receipt)
        receipt['producer_sha256'] = '0' * 64
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'receipt identity mismatch'):
            prepare.verify_candidate(self.destination)
        receipt_path.write_bytes(original_receipt)
        (self.destination / 'start/src/untracked.cpp').write_text('// undeclared input')
        with self.assertRaisesRegex(ValueError, 'inventory mismatch'):
            prepare.verify_candidate(self.destination)


if __name__ == '__main__':
    unittest.main()
