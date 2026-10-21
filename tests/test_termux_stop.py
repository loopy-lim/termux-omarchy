"""Owned stop must reap descendants, including ones that change session/group."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOKEN = '693ed2ef-74d1-44b5-bc10-337f4719011d'

# macOS has no /proc. This substitutes only kernel enumeration/identity;
# the supervisor, process trees, sessions, signals and heartbeats remain real.
KERNEL_SHIM = '''
import json, time
from pathlib import Path
def publish():
    record = {'pid':os.getpid(),'ppid':os.getppid(),'pgid':os.getpgrp(),'uid':os.getuid(),
              'starttime':STARTED,'command':[EXECUTABLE,*sys.argv]}
    path = PROCDIR / (str(os.getpid())+'.json')
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record)); temporary.replace(path)
def snapshot(proc=None):
    for child in OWN_CHILDREN: child.poll()
    found = {}
    for path in PROCDIR.glob('*.json'):
        record = json.loads(path.read_text()); pid = record['pid']
        try: os.kill(pid,0)
        except ProcessLookupError: continue
        found[pid] = record
    return found
def identity(pid, proc=None, strict=False):
    return snapshot().get(pid)
def child_ids(pid, proc=None):
    if not CHILD_LISTS: return None
    return [p['pid'] for p in snapshot().values() if p['ppid']==pid]
'''


def load_runtime():
    sys.path.insert(0, str(ROOT / 'termux'))
    spec = importlib.util.spec_from_file_location('stop_runtime', ROOT / 'termux/runtime.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class StopTests(unittest.TestCase):
    def setUp(self):
        for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGCHLD):
            self.addCleanup(signal.signal,sig,signal.getsignal(sig))
        self.runtime = load_runtime()
        self.addCleanup(sys.path.remove, str(ROOT / 'termux'))
        import processes
        self.processes = processes
        self.temp = tempfile.TemporaryDirectory(prefix='loopy-stop-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home, self.prefix = self.base / 'home', self.base / 'usr'
        self.home.mkdir(); (self.prefix / 'bin').mkdir(parents=True)
        (self.prefix / 'bin/python3').symlink_to(sys.executable)
        self.session = self.runtime.Runtime(self.home, self.prefix)
        self.groups = []
        self.addCleanup(self.clean_groups)
        self.procdir = self.base / 'proc'; self.procdir.mkdir()
        self.children = []
        if sys.platform != 'linux':
            scope = {'subprocess':subprocess,'os':os,'sys':sys,'PROCDIR':self.procdir,
                     'STARTED':str(time.time_ns()),'OWN_CHILDREN':self.children,'CHILD_LISTS':True}
            exec(KERNEL_SHIM, scope)
            for module in (self.runtime, self.processes):
                self.enterContext(patch.object(module, 'identity', scope['identity']))
            # Added enumeration is substituted at the same kernel boundary.
            self.kernel_snapshot = scope['snapshot']
            if hasattr(self.processes, 'snapshot'):
                self.enterContext(patch.object(self.processes, 'snapshot', scope['snapshot']))
            if hasattr(self.processes, 'child_ids'):
                self.enterContext(patch.object(self.processes, 'child_ids', scope['child_ids']))

    def clean_groups(self):
        for group in self.groups:
            try: os.killpg(group, signal.SIGKILL)
            except (ProcessLookupError, PermissionError): pass

    def reap(self, child):
        try: os.killpg(child.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError): pass
        child.wait(timeout=3)

    def executable(self, name, body):
        path = self.prefix / 'bin' / name
        path.write_text('#!' + sys.executable + '\n' + self.kernel_setup() + body)
        path.chmod(0o700)

    def kernel_setup(self, executable=None):
        if sys.platform == 'linux': return ''
        return ('import os,sys\n'+KERNEL_SHIM+
                f'PROCDIR=Path({str(self.procdir)!r});STARTED=str(time.time_ns());OWN_CHILDREN=[]\n'
                f'EXECUTABLE={str(executable or sys.executable)!r};CHILD_LISTS={getattr(self,"child_lists",True)!r}\npublish()\n')

    def running_descendant(self, detached, child_lists=True):
        self.child_lists=child_lists
        beat, pid = self.base / 'heartbeat', self.base / 'descendant.pid'
        worker = self.base / 'worker.py'
        worker.write_text(self.kernel_setup()+'import os,signal,time\nfrom pathlib import Path\n'
                          'signal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
                          f'Path({str(pid)!r}).write_text(str(os.getpid()))\n'
                          f'while True:\n Path({str(beat)!r}).write_text(str(time.time_ns()))\n time.sleep(.02)\n')
        self.executable('termux-x11', 'import sys,json,time\nfrom pathlib import Path\n'
                        f'Path({str(self.base/"server-argv.json")!r}).write_text(json.dumps(sys.argv))\n'
                        'while True: time.sleep(.1)\n')
        self.executable('i3', 'import subprocess,time\n'
                        f'subprocess.Popen([{sys.executable!r},{str(worker)!r}],start_new_session={detached!r})\n'
                        'while True: time.sleep(.1)\n')
        self.executable('dbus-run-session', 'import subprocess,sys,time\n'
                        'subprocess.Popen(sys.argv[2:])\nwhile True: time.sleep(.1)\n')
        self.executable('xdpyinfo', 'print("display ready")\n')
        self.executable('xprop', 'print("_NET_SUPPORTING_WM_CHECK(WINDOW): window id # 0x123")\n')
        wrapper = (self.kernel_setup(self.prefix/'bin/python3')+'import os,sys,subprocess\nfrom pathlib import Path\n'
                   f'sys.path.insert(0,{str(ROOT / "termux")!r})\nimport runtime,processes\n')
        if sys.platform != 'linux':
            wrapper += '\nruntime.identity=processes.identity=identity\n'
            wrapper += 'if hasattr(processes,"snapshot"): processes.snapshot=snapshot\n'
            wrapper += 'if hasattr(processes,"child_ids"): processes.child_ids=child_ids\n'
            wrapper += 'if hasattr(processes,"enable_subreaper"): runtime.enable_subreaper=processes.enable_subreaper=lambda: None\n'
        elif not child_lists:
            wrapper += 'processes.child_ids=lambda pid: None\n'
        wrapper += 'runtime.supervise(runtime.Runtime(Path(os.environ["HOME"]),Path(os.environ["PREFIX"])),sys.argv[2],sys.argv[3])\n'
        helper = self.session.root / 'runtime.py'; helper.write_text(wrapper)
        argv = [str(self.prefix / 'bin/python3'), str(helper), '_supervise', TOKEN, ':20']
        leader = subprocess.Popen(argv, env=self.session.env, start_new_session=True,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.groups.append(leader.pid)
        self.children.append(leader)
        self.addCleanup(self.reap, leader)
        record = None; until = time.monotonic() + 3
        while record is None and time.monotonic() < until:
            record = self.runtime.identity(leader.pid)
        self.assertIsNotNone(record, 'supervisor identity unavailable')
        self.session.path.write_text(json.dumps({'schema':1,'uid':os.getuid(),'token':TOKEN,
                                                'display':':20','phase':'starting','processes':[record]}))
        until = time.monotonic() + 8
        while time.monotonic() < until:
            state = self.session.state()
            if state['phase'] == 'ready' and beat.exists(): break
            self.assertIsNone(leader.poll(), 'supervisor exited during setup')
            time.sleep(.05)
        self.assertEqual(self.session.state()['phase'], 'ready', self.session.state())
        self.assertTrue(beat.exists(), 'descendant did not initialize')
        descendant = int(pid.read_text())
        if detached: self.groups.append(descendant)
        time.sleep(.35)  # Let ownership enumeration observe the live child tree.
        return beat, leader, descendant

    def assert_stop(self, detached, child_lists=True):
        beat, leader, descendant = self.running_descendant(detached,child_lists)
        sentinel = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'], start_new_session=True)
        self.groups.append(sentinel.pid)
        self.children.append(sentinel)
        if sys.platform != 'linux':
            (self.procdir/(str(sentinel.pid)+'.json')).write_text(json.dumps({
                'pid':sentinel.pid,'ppid':os.getpid(),'pgid':sentinel.pid,'uid':os.getuid(),
                'starttime':'1','command':[sys.executable,'-c','import time;time.sleep(30)']}))
        self.addCleanup(self.reap, sentinel)
        response = self.session.stop(TOKEN)
        before = beat.read_text(); time.sleep(.12); after = beat.read_text()
        self.assertEqual(before, after, 'stop accepted while owned descendant heartbeat continues')
        self.assertEqual(response['status'], 'stopped')
        self.assertTrue(response['evidence']['terminationConfirmed'])
        self.assertFalse(self.session.path.exists())
        self.assertIsNotNone(leader.poll(), 'ownership anchor survived successful stop')
        self.assertIsNone(sentinel.poll(), 'stop signalled an unrelated same-UID session')
        self.assertNotEqual(descendant, sentinel.pid)

    def test_stop_reaps_term_ignoring_child_in_owned_group(self):
        self.assert_stop(False)

    def test_stop_reaps_term_ignoring_child_in_detached_session(self):
        self.assert_stop(True)

    def test_owned_x_server_does_not_reset_when_readiness_client_disconnects(self):
        self.running_descendant(False)
        args=json.loads((self.base/'server-argv.json').read_text())
        self.assertIn('-noreset',args,'owned X server resets between short readiness connections')

    def test_missing_kernel_child_lists_still_reaps_detached_session(self):
        self.assert_stop(True,False)

    def test_lost_anchor_keeps_marker_and_cannot_claim_stopped(self):
        record = {'pid':123,'pgid':123,'uid':os.getuid(),'starttime':'100',
                  'command':[str(self.prefix/'bin/python3'),str(self.session.root/'runtime.py'),
                             '_supervise',TOKEN,':20']}
        self.session.path.write_text(json.dumps({'schema':1,'uid':os.getuid(),'token':TOKEN,
                                                'display':':20','phase':'ready','processes':[record]}))
        with patch.object(self.runtime,'identity',return_value=None):
            with self.assertRaisesRegex(ValueError, 'anchor|confirm|owner'):
                self.session.stop(TOKEN)
        self.assertTrue(self.session.path.exists(), 'uncertain cleanup discarded ownership marker')

    def fake_proc(self, pid, ppid, group, command, uid=None, start='100'):
        directory = self.procdir / str(pid); directory.mkdir(exist_ok=True)
        directory.joinpath('status').write_text('Uid:\t'+' '.join([str(os.getuid() if uid is None else uid)]*4))
        fields = [str(ppid),str(group),*(['0']*16),start,'0']
        directory.joinpath('stat').write_text(str(pid)+' (worker (owned)) S '+' '.join(fields))
        directory.joinpath('cmdline').write_bytes(b'\0'.join(x.encode() for x in command)+b'\0')
        task = directory/'task'/str(pid); task.mkdir(parents=True,exist_ok=True)
        for parent in self.procdir.iterdir():
            if parent.name.isdigit():
                children = [p.name for p in self.procdir.iterdir() if p.name.isdigit()
                            and self.processes.parse_stat((p/'stat').read_text())['ppid']==int(parent.name)]
                (parent/'task'/parent.name/'children').write_text(' '.join(children))
        return directory

    def test_lineage_excludes_same_uid_foreign_group_and_other_uid(self):
        pid = os.getpid()
        self.fake_proc(pid,os.getppid(),pid,['supervisor'])
        self.fake_proc(100001,pid,100001,['terminal'])
        self.fake_proc(100002,100001,100002,['detached-shell'])
        self.fake_proc(100003,100000,100003,['foreign-terminal'])
        self.fake_proc(100004,100000,100004,['other-uid'],uid=os.getuid()+1)
        # Obtain the real parser despite macOS kernel substitution in setUp.
        spec = importlib.util.spec_from_file_location('kernel_processes',ROOT/'termux/processes.py')
        original = importlib.util.module_from_spec(spec); spec.loader.exec_module(original)
        with patch.object(self.processes,'identity',side_effect=lambda p,**kw:original.identity(p,self.procdir,**kw)), \
                patch.object(self.processes,'snapshot',side_effect=lambda:original.snapshot(self.procdir)):
            if hasattr(original,'child_ids'):
                self.enterContext(patch.object(self.processes,'child_ids',side_effect=lambda p:original.child_ids(p,self.procdir)))
            owner = self.processes.OwnedProcesses()
            self.assertEqual({p['pid'] for p in owner.refresh()},{100001,100002})
            # Reparented known descendants remain owned; unrelated processes do not.
            self.fake_proc(100002,1,100002,['detached-shell'])
            self.assertEqual({p['pid'] for p in owner.refresh()},{100001,100002})

    def test_unreadable_live_identity_cannot_be_treated_as_exit(self):
        spec = importlib.util.spec_from_file_location('strict_processes',ROOT/'termux/processes.py')
        original = importlib.util.module_from_spec(spec); spec.loader.exec_module(original)
        directory = self.fake_proc(100001,os.getpid(),100001,['terminal'])
        read = Path.read_bytes
        def denied(path):
            if path == directory/'cmdline': raise PermissionError('hidden live process')
            return read(path)
        with patch.object(Path,'read_bytes',denied):
            with self.assertRaisesRegex(ValueError,'identity.*verified'):
                original.identity(100001,self.procdir,strict=True)

    def test_recycled_or_changed_command_identity_is_never_signalled(self):
        expected = {'pid':100001,'pgid':100001,'uid':os.getuid(),'starttime':'100','command':['terminal']}
        sent = []
        for replacement in (dict(expected,starttime='101'),dict(expected,command=['foreign']),
                            dict(expected,uid=os.getuid()+1)):
            with patch.object(self.processes,'identity',return_value=replacement), \
                    patch.object(self.processes.os,'kill',side_effect=lambda pid,sig:sent.append(pid)):
                with self.assertRaisesRegex(ValueError,'identity changed') as raised:
                    self.processes.signal_process(expected,signal.SIGKILL)
                self.assertEqual(getattr(raised.exception,'identity_changed_fields',None),
                                 tuple(key for key in ('pid','pgid','uid','starttime','command')
                                       if expected.get(key)!=replacement.get(key)))
        self.assertEqual(sent,[],'foreign identity received an owned cleanup signal')

    def terminate_with_identity_change(self, change):
        import shutil
        pid=os.getpid();self.fake_proc(pid,os.getppid(),pid,['supervisor'])
        child=self.fake_proc(100001,pid,100001,['before-exec'])
        foreign=self.fake_proc(100002,100000,100002,['foreign-process'])
        spec=importlib.util.spec_from_file_location('exec_race_kernel',ROOT/'termux/processes.py')
        kernel=importlib.util.module_from_spec(spec);spec.loader.exec_module(kernel)
        signal_actual=self.processes.signal_process;attempts=[];signals=[]
        def signal_then_exec(record,sig):
            attempts.append(tuple(record['command']))
            if len(attempts)==1:
                self.fake_proc(100001,pid,100001,['after-exec'],start='101' if change=='birth' else '100')
            return signal_actual(record,sig)
        def kill(owned_pid,sig):
            self.assertEqual(owned_pid,100001,'same-UID unrelated process was signalled')
            signals.append((owned_pid,sig));shutil.rmtree(child)
        with patch.object(self.processes,'identity',side_effect=lambda p,**kw:kernel.identity(p,self.procdir,**kw)), \
                patch.object(self.processes,'snapshot',side_effect=lambda:kernel.snapshot(self.procdir)), \
                patch.object(self.processes,'child_ids',side_effect=lambda p:kernel.child_ids(p,self.procdir)), \
                patch.object(self.processes,'reap_children',side_effect=lambda:not child.exists()), \
                patch.object(self.processes.os,'kill',side_effect=kill), \
                patch.object(self.processes,'signal_process',side_effect=signal_then_exec):
            owned=self.processes.OwnedProcesses();owned.register(100001)
            if change=='birth':
                with self.assertRaisesRegex(ValueError,'identity changed'):owned.terminate()
            else:owned.terminate()
        self.assertTrue(foreign.exists(),'unrelated same-UID process metadata was removed')
        return child,attempts,signals

    def test_owned_termination_refreshes_lineage_after_a_command_only_exec_race(self):
        child,attempts,signals=self.terminate_with_identity_change('command')
        self.assertFalse(child.exists())
        self.assertEqual(attempts,[('before-exec',),('after-exec',)])
        self.assertEqual(signals,[(100001,signal.SIGTERM)])

    def test_owned_termination_still_refuses_pid_birth_replacement(self):
        child,attempts,signals=self.terminate_with_identity_change('birth')
        self.assertTrue(child.exists());self.assertEqual(signals,[])
        self.assertEqual(attempts,[('before-exec',)])

    def test_subreaper_unavailable_prevents_children_from_starting(self):
        response = []
        class Prctl:
            def __call__(self,*args): return 1
        library = type('Library',(),{'prctl':Prctl()})()
        with patch.object(self.processes.ctypes,'CDLL',return_value=library):
            with self.assertRaisesRegex(ValueError,'ownership unavailable'):
                self.processes.enable_subreaper()
        owner = {'pid':os.getpid(),'pgid':os.getpid(),'uid':os.getuid(),'starttime':'100',
                 'command':[str(self.prefix/'bin/python3'),str(self.session.root/'runtime.py'),'_supervise',TOKEN,':20']}
        state = {'schema':1,'uid':os.getuid(),'token':TOKEN,'display':':20','phase':'starting','processes':[owner]}
        self.session.path.write_text(json.dumps(state))
        with patch.object(self.runtime,'enable_subreaper',side_effect=ValueError('ownership unavailable')), \
                patch.object(self.runtime.os,'getpgrp',return_value=os.getpid()), \
                patch.object(self.runtime.subprocess,'Popen',side_effect=lambda *a,**kw:response.append(a)):
            self.runtime.supervise(self.session,TOKEN,':20')
        self.assertEqual(response,[],'failed ownership acquisition still spawned desktop children')
        stopped = self.session.state()
        self.assertEqual(stopped['phase'],'stopped','zero-child startup failure stranded an unconfirmed marker')
        self.assertTrue(stopped['terminationConfirmed'])

    def test_cleanup_retry_request_is_not_lost_after_failed_marker(self):
        owner = {'pid':os.getpid(),'pgid':os.getpid(),'uid':os.getuid(),'starttime':'100',
                 'command':[str(self.prefix/'bin/python3'),str(self.session.root/'runtime.py'),'_supervise',TOKEN,':20']}
        self.session.path.write_text(json.dumps({'schema':1,'uid':os.getuid(),'token':TOKEN,'display':':20',
                                                'phase':'starting','processes':[owner]}))
        class RetryEvent:
            active = False
            def set(self): self.active=True
            def clear(self): self.active=False
            def wait(self,timeout=None):
                if not self.active: raise AssertionError('cleanup discarded the queued retry request')
                return True
        class Owned:
            failed = False
            def terminate(self):
                if not self.failed:
                    self.failed=True
                    raise ValueError('temporary identity read failure')
        owned=Owned(); owned.owner=owner
        atomic=self.runtime.atomic_json
        def publish(path,state):
            atomic(path,state)
            if state.get('terminationConfirmed') is False:
                signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
        with patch.object(self.runtime,'enable_subreaper',return_value=None), \
                patch.object(self.runtime,'OwnedProcesses',return_value=owned), \
                patch.object(self.runtime.os,'getpgrp',return_value=os.getpid()), \
                patch.object(self.runtime.threading,'Event',return_value=RetryEvent()), \
                patch.object(self.runtime,'atomic_json',side_effect=publish), \
                patch.object(self.runtime.subprocess,'Popen',side_effect=ValueError('failed X startup')):
            self.runtime.supervise(self.session,TOKEN,':20')
        self.assertTrue(self.session.state()['terminationConfirmed'])

    def test_hidden_untracked_direct_child_cannot_be_false_empty_cleanup(self):
        pid=os.getpid(); self.fake_proc(pid,os.getppid(),pid,['supervisor'])
        child=self.fake_proc(100001,pid,100001,['hidden-terminal'])
        spec=importlib.util.spec_from_file_location('hidden_processes',ROOT/'termux/processes.py')
        original=importlib.util.module_from_spec(spec); spec.loader.exec_module(original)
        read=Path.read_text
        def denied(path,*args,**kwargs):
            if path==child/'status': raise PermissionError('hidden direct child')
            return read(path,*args,**kwargs)
        with patch.object(Path,'read_text',denied), \
                patch.object(self.processes,'identity',side_effect=lambda p,**kw:original.identity(p,self.procdir,**kw)), \
                patch.object(self.processes,'snapshot',side_effect=lambda:original.snapshot(self.procdir)):
            if hasattr(original,'child_ids'):
                self.enterContext(patch.object(self.processes,'child_ids',side_effect=lambda p:original.child_ids(p,self.procdir)))
            owned=self.processes.OwnedProcesses()
            with self.assertRaisesRegex(ValueError,'identity.*verified'):
                owned.refresh()

    def test_optional_child_file_absence_and_denial_use_compatible_discovery(self):
        pid=os.getpid(); directory=self.fake_proc(pid,os.getppid(),pid,['supervisor'])
        spec=importlib.util.spec_from_file_location('optional_processes',ROOT/'termux/processes.py')
        original=importlib.util.module_from_spec(spec); spec.loader.exec_module(original)
        path=directory/'task'/str(pid)/'children'; path.unlink()
        self.assertIsNone(original.child_ids(pid,self.procdir),'optional child API absence blocked readable owner')
        path.write_text('')
        read=Path.read_text
        def denied(file,*args,**kwargs):
            if file==path: raise PermissionError('optional child API denied')
            return read(file,*args,**kwargs)
        with patch.object(Path,'read_text',denied):
            self.assertIsNone(original.child_ids(pid,self.procdir))

    def test_hidden_child_waitpid_prevents_false_termination_confirmation(self):
        # A real owned child is alive but intentionally absent from /proc discovery.
        child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
        self.addCleanup(lambda: (child.kill(),child.wait(timeout=3)))
        owner={'pid':os.getpid(),'ppid':os.getppid(),'pgid':os.getpid(),'uid':os.getuid(),
               'starttime':'100','command':['supervisor']}
        with patch.object(self.processes,'identity',return_value=owner), \
                patch.object(self.processes,'snapshot',return_value={os.getpid():owner}), \
                patch.object(self.processes,'child_ids',return_value=None), \
                patch.object(self.processes.time,'monotonic',side_effect=[0,0,3,4,4,7]), \
                patch.object(self.processes,'signal_process',side_effect=AssertionError('unknown child was signalled')):
            owned=self.processes.OwnedProcesses()
            with self.assertRaisesRegex(ValueError,'termination not confirmed'):
                owned.terminate()
        self.assertIsNone(child.poll(),'unidentified child received a cleanup signal')

    def test_reaping_distinguishes_live_child_from_kernel_no_children(self):
        child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
        self.addCleanup(lambda: (child.poll() is None and child.kill(),child.wait(timeout=3)))
        self.assertIs(self.processes.reap_children(),False,'live child was treated as absent')
        child.kill(); child.wait(timeout=3)
        self.assertIs(self.processes.reap_children(),True,'kernel ECHILD was not accepted')

    def test_registered_direct_child_is_found_when_proc_listing_omits_it(self):
        owner={'pid':os.getpid(),'ppid':os.getppid(),'pgid':os.getpid(),'uid':os.getuid(),
               'starttime':'100','command':['supervisor']}
        child={'pid':100001,'ppid':os.getpid(),'pgid':100001,'uid':os.getuid(),
               'starttime':'101','command':['x-server']}
        with patch.object(self.processes,'identity',side_effect=lambda pid,**kw:owner if pid==os.getpid() else child), \
                patch.object(self.processes,'snapshot',return_value={os.getpid():owner}), \
                patch.object(self.processes,'child_ids',return_value=None):
            owned=self.processes.OwnedProcesses(); owned.register(100001)
            self.assertEqual([p['pid'] for p in owned.refresh()],[100001])
            foreign=dict(child,ppid=99999)
            with patch.object(self.processes,'identity',return_value=foreign):
                with self.assertRaisesRegex(ValueError,'spawned child identity'):
                    owned.register(100002)

    def test_linux_wait_includes_non_sigchld_clone_children(self):
        # Kernel contract: __WALL includes clone children, normal wait excludes them.
        def wait(pid,flags):
            if flags & 0x40000000: raise ChildProcessError()
            return (0,0)
        for platform in ('linux','android'):
            with patch.object(self.processes.sys,'platform',platform),patch.object(self.processes.os,'waitpid',side_effect=wait):
                self.assertIs(self.processes.reap_children(),True,platform)

    def dead_marker(self, confirmed):
        owner={'pid':123,'pgid':123,'uid':os.getuid(),'starttime':'100',
               'command':[str(self.prefix/'bin/python3'),str(self.session.root/'runtime.py'),'_supervise',TOKEN,':20']}
        state={'schema':1,'uid':os.getuid(),'token':TOKEN,'display':':20','processes':[owner],
               'phase':'stopped' if confirmed else 'failed','terminationConfirmed':confirmed}
        self.session.path.write_text(json.dumps(state))
        return state

    def test_start_cannot_overwrite_lost_owner_with_unconfirmed_cleanup(self):
        previous=self.dead_marker(False)
        for name in ('termux-x11','i3','xprop','dbus-run-session','xfce4-terminal'):
            self.executable(name,'raise SystemExit(1 if __import__("sys").argv[0].endswith("xprop") else 0)\n')
        (self.session.root/'runtime.py').write_text('import time\ntime.sleep(10)\n')
        (self.session.root/'i3.config').write_text('# setup exists\n')
        outcome=None
        with patch.object(self.runtime,'identity',return_value=None):
            try: outcome=self.session.start('2479ab71-aa85-47e9-8e4c-79bc9f7c2b2d')
            except ValueError: pass
        self.assertTrue(self.session.path.exists(),'new start discarded an unconfirmed old marker')
        self.assertEqual(json.loads(self.session.path.read_text()),previous)
        self.assertIsNone(outcome,'start accepted an unconfirmed lost owner')

    def test_doctor_does_not_report_stopped_for_unconfirmed_lost_owner(self):
        previous=self.dead_marker(False)
        with patch.object(self.runtime,'identity',return_value=None):
            response=self.session.doctor(TOKEN)
        self.assertEqual(response['status'],'failed','owner exit alone was treated as complete cleanup')
        self.assertFalse(response['xReady']); self.assertFalse(response['wmReady'])
        self.assertEqual(json.loads(self.session.path.read_text()),previous)

    def test_confirmed_stopped_marker_allows_start_preparation_and_stop(self):
        self.dead_marker(True)
        with patch.object(self.runtime,'identity',return_value=None):
            self.assertEqual(self.session.doctor(TOKEN)['status'],'stopped')
            # Missing packages are a preparation failure, not an ownership refusal.
            response=self.session.start('2479ab71-aa85-47e9-8e4c-79bc9f7c2b2d')
            self.assertEqual(response['status'],'failed')
            self.assertIn('setup/packages',response['reason'])
            self.assertEqual(self.session.stop(TOKEN)['status'],'stopped')
        self.assertFalse(self.session.path.exists())


if __name__ == '__main__':
    unittest.main()
