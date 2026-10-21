"""Real local sockets and files exercise compositor ownership and stale input fencing."""
import json
import inspect
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from test_omarchy_actions import module, OwnedSocket

BOOTSTRAP = r'''import os, pathlib, sys, time
root, ident, signature = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
sys.path.insert(0, sys.argv[4])
import session_actions as worker
real_path = pathlib.Path
def mapped(value):
    value = str(value)
    if value == '/run/loopy': return root
    if value == '/run/loopy/o00000001': return root / 'runtime'
    return real_path(value)
worker.Path = mapped
def watch(queue):
    (root / ('started-' + ident)).write_text(str(queue.started_ns))
    while not (root / 'consume').exists(): time.sleep(.01)
    queue.consume()
    while not (root / 'finish').exists(): time.sleep(.01)
worker.Worker.watch = watch
os.environ.update(XDG_RUNTIME_DIR='/run/loopy/o00000001',
    HYPRLAND_INSTANCE_SIGNATURE=signature, LOOPY_SESSION='owned', WAYLAND_DISPLAY='wayland-new')
worker.main()
'''

OLD_OWNER = r'''import pathlib, sys, time
root, signature = pathlib.Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, sys.argv[3])
import session_actions as worker
with worker.Worker(root, 'owned', None) as queue:
    queue.display = worker.configure_input(root / 'runtime', 'owned', 'wayland-old')
    queue.ready(signature)
    lifetime = worker.CompositorLifetime(root / 'old' / '.socket.sock')
    try:
        (root / 'old-started').write_text('ready')
        while lifetime.alive(.05): pass
    finally: lifetime.close()
'''


class WorkerLifetimeTests(unittest.TestCase):
    @staticmethod
    def wait_for(condition, description, seconds=3):
        end = time.monotonic() + seconds
        while not condition() and time.monotonic() < end: time.sleep(.01)
        if not condition(): raise AssertionError(description)

    def test_overlapping_recovery_callbacks_wait_for_old_flock_then_one_successor_consumes_fresh_job(self):
        worker = module('session_actions')
        old_signature, new_signature = 'abcdef0_1_1', 'abcdef0_2_2'
        with tempfile.TemporaryDirectory(prefix='hl-handoff-', dir='/tmp') as folder:
            root = Path(folder); runtime = root / 'runtime'; runtime.mkdir()
            old = root / 'old'; old.mkdir()
            ipc = runtime / 'hypr' / new_signature; ipc.mkdir(parents=True)
            children, sockets, old_peer = [], [], None
            control = OwnedSocket(ipc / '.socket.sock', [[b'{}'], [b'ok']])
            try:
                for path in (runtime/'wayland-old', runtime/'wayland-new', old/'.socket2.sock', ipc/'.socket2.sock'):
                    endpoint = socket.socket(socket.AF_UNIX); endpoint.bind(str(path)); endpoint.listen(4); sockets.append(endpoint)
                owner = subprocess.Popen([sys.executable, '-B', '-c', OLD_OWNER, str(root), old_signature,
                    str(Path(worker.__file__).parent)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                children.append(owner); old_peer, _ = sockets[2].accept()
                self.wait_for(lambda: (root/'old-started').exists(), 'old real flock owner did not start')
                stale = root/'command-owned-0000000000000001.json'
                stale.write_text(json.dumps({'action':'workspace','target':'9','created_ns':time.monotonic_ns()}))
                for ident in ('a', 'b'):
                    children.append(subprocess.Popen([sys.executable, '-B', '-c', BOOTSTRAP, str(root), ident,
                        new_signature, str(Path(worker.__file__).parent)], stdout=subprocess.PIPE, stderr=subprocess.PIPE))
                # Both one-shot callbacks overlap the old owner; neither may disappear in that gap.
                time.sleep(.25)
                for child in children[1:]:
                    self.assertIsNone(child.poll(), 'new compositor callback exited while old generation held flock')
                fresh = root/'command-owned-0000000000000002.json'
                fresh.write_text(json.dumps({'action':'workspace','target':'3','created_ns':time.monotonic_ns()}))
                old_peer.close(); old_peer = None; owner.wait(timeout=2)
                self.wait_for(lambda: len(list(root.glob('started-*'))) == 1, 'no unique successor became ready')
                winner = list(root.glob('started-*'))[0].name[-1]
                loser = children[2 if winner == 'a' else 1]
                loser.wait(timeout=2); self.assertEqual(loser.returncode, 0, loser.stderr.read().decode())
                ready = json.loads((root/'actions-owned.ready.json').read_text())
                self.assertEqual(ready['signature'], new_signature)
                self.assertEqual((runtime/'display-owned').read_text(), 'wayland-new\n')
                (root/'consume').touch()
                self.wait_for(lambda: not fresh.exists(), 'successor did not consume job queued during handoff')
                self.assertFalse(stale.exists()); self.assertFalse((root/'error-owned.log').exists())
                self.assertEqual(control.requests.count("dispatch hl.dsp.focus({workspace='3'})"), 1)
                self.assertFalse(any("workspace='9'" in request for request in control.requests))
                # Original-config reload is a duplicate, not a second job consumer.
                duplicate = subprocess.Popen([sys.executable, '-B', '-c', BOOTSTRAP, str(root), 'reload',
                    new_signature, str(Path(worker.__file__).parent)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                children.append(duplicate); duplicate.wait(timeout=2)
                self.assertEqual(duplicate.returncode, 0, duplicate.stderr.read().decode())
                self.assertFalse((root/'started-reload').exists())
                (root/'finish').touch()
                for child in children: child.wait(timeout=2)
                self.assertFalse((root/'actions-owned.ready.json').exists())
                self.assertFalse((runtime/'display-owned').exists())
            finally:
                if old_peer is not None: old_peer.close()
                for child in children:
                    if child.poll() is None: child.kill()
                    child.communicate(timeout=2)
                for endpoint in sockets: endpoint.close()
                control.close()

    def test_closed_lifetime_stops_batch_after_current_costly_job_and_preserves_pending_records(self):
        worker = module('session_actions')
        with tempfile.TemporaryDirectory(prefix='hl-batch-', dir='/tmp') as folder:
            root = Path(folder); server = socket.socket(socket.AF_UNIX); server.bind(str(root/'.socket2.sock')); server.listen(1)
            entered, release, calls, failures = threading.Event(), threading.Event(), [], []
            class Commands:
                def execute(self, job):
                    calls.append(job['target']); entered.set(); release.wait(2)
            lifetime = worker.CompositorLifetime(root/'.socket.sock'); peer, _ = server.accept()
            try:
                with worker.Worker(root, 'owned', Commands()) as queue:
                    queue.ready('old')
                    for number in (1, 2, 3):
                        (root/('command-owned-%016d.json' % number)).write_text(json.dumps(
                            {'action':'workspace','target':str(number),'created_ns':time.monotonic_ns()}))
                    def consume():
                        try:
                            options = {'lifetime':lifetime} if 'lifetime' in inspect.signature(queue.consume).parameters else {}
                            queue.consume(**options)
                        except BaseException as error: failures.append(error)
                    pending = threading.Thread(target=consume); pending.start()
                    self.assertTrue(entered.wait(1)); peer.close(); release.set(); pending.join(timeout=1)
                    self.assertFalse(pending.is_alive(), 'dead compositor retained owner through pending input batch')
                    self.assertEqual(failures, []); self.assertEqual(calls, ['1'], 'dead generation dispatched more queued jobs')
                    self.assertFalse((root/'command-owned-0000000000000001.json').exists())
                    self.assertTrue((root/'command-owned-0000000000000002.json').exists())
                    self.assertTrue((root/'command-owned-0000000000000003.json').exists())
            finally:
                release.set(); peer.close(); lifetime.close(); server.close()

    def test_handoff_deadline_and_dead_requested_compositor_preserve_owner(self):
        worker = module('session_actions')
        with tempfile.TemporaryDirectory(prefix='hl-handoff-bound-', dir='/tmp') as folder:
            root = Path(folder); server = socket.socket(socket.AF_UNIX)
            server.bind(str(root/'.socket2.sock')); server.listen(4)
            peers = []
            try:
                with worker.Worker(root, 'owned', None) as owner:
                    owner.ready('old')
                    original = (root/'actions-owned.ready.json').read_bytes()
                    started = time.monotonic()
                    with self.assertRaises(TimeoutError):
                        worker.Worker(root, 'owned', worker.Hyprland(root/'.socket.sock'), signature='new', handoff_seconds=.1)
                    self.assertLess(time.monotonic()-started, .5)
                    peers.append(server.accept()[0])
                    self.assertEqual(peers[-1].recv(1), b'', 'timed-out contender leaked its event connection')
                    self.assertEqual((root/'actions-owned.ready.json').read_bytes(), original)
                    failures = []
                    def acquire():
                        try:
                            with worker.Worker(root, 'owned', worker.Hyprland(root/'.socket.sock'),
                                    signature='new', handoff_seconds=1):
                                failures.append(AssertionError('dead requested compositor took ownership'))
                        except BaseException as error: failures.append(error)
                    pending = threading.Thread(target=acquire); pending.start()
                    peer, _ = server.accept(); peer.close(); pending.join(timeout=.5)
                    self.assertFalse(pending.is_alive(), 'dead requested compositor retained a waiting callback')
                    self.assertEqual(len(failures), 1); self.assertIsInstance(failures[0], ConnectionError)
                    self.assertEqual((root/'actions-owned.ready.json').read_bytes(), original)
                    with self.assertRaises(BlockingIOError): worker.Worker(root, 'owned', None)
                with worker.Worker(root, 'owned', None): pass
            finally:
                for peer in peers: peer.close()
                server.close()

    def test_same_generation_and_invalid_readiness_never_replace_lock_owner(self):
        worker = module('session_actions')
        with tempfile.TemporaryDirectory(prefix='hl-handoff-record-', dir='/tmp') as folder:
            root = Path(folder); server = socket.socket(socket.AF_UNIX)
            server.bind(str(root/'.socket2.sock')); server.listen(4)
            try:
                with worker.Worker(root, 'owned', None) as owner:
                    owner.ready('same'); marker = root/'actions-owned.ready.json'
                    original = marker.read_bytes()
                    with self.assertRaises(BlockingIOError):
                        worker.Worker(root, 'owned', worker.Hyprland(root/'.socket.sock'), signature='same')
                    with server.accept()[0] as peer: self.assertEqual(peer.recv(1), b'')
                    self.assertEqual(marker.read_bytes(), original)
                    for data in (b'keep malformed readiness', json.dumps({'token':'owned','signature':'new','pid':True,
                            'uid':os.getuid()}).encode()):
                        marker.write_bytes(data)
                        with self.assertRaises(ValueError):
                            worker.Worker(root, 'owned', worker.Hyprland(root/'.socket.sock'), signature='new')
                        with server.accept()[0] as peer: self.assertEqual(peer.recv(1), b'')
                        self.assertEqual(marker.read_bytes(), data)
                    preserved = root/'preserved'; marker.rename(preserved); marker.symlink_to(preserved)
                    with self.assertRaises(OSError):
                        worker.Worker(root, 'owned', worker.Hyprland(root/'.socket.sock'), signature='new')
                    with server.accept()[0] as peer: self.assertEqual(peer.recv(1), b'')
                    self.assertTrue(marker.is_symlink()); self.assertEqual(preserved.read_bytes(), data)
            finally: server.close()

    def test_readiness_growing_past_bound_during_read_is_rejected_and_preserved(self):
        worker = module('session_actions')
        with tempfile.TemporaryDirectory(prefix='hl-handoff-grow-', dir='/tmp') as folder:
            root = Path(folder)
            with worker.Worker(root, 'owned', None) as owner:
                owner.ready('same'); marker = root/'actions-owned.ready.json'; initial = marker.read_bytes()
                oversized = initial + b' ' * (1025-len(initial)); fdopen = os.fdopen
                class GrowingRead:
                    def __init__(self, fd, mode): self.source = fdopen(fd, mode)
                    def __enter__(self): return self
                    def __exit__(self, *args): self.source.close()
                    def fileno(self): return self.source.fileno()
                    def read(self, count):
                        marker.write_bytes(oversized)
                        return self.source.read(count)
                with patch.object(worker.os, 'fdopen', GrowingRead):
                    with self.assertRaises(ValueError): owner._ready_signature()
                self.assertEqual(marker.read_bytes(), oversized)

    def test_compositor_exit_after_lock_acquisition_cannot_publish_readiness(self):
        worker = module('session_actions')
        with tempfile.TemporaryDirectory(prefix='hl-handoff-publish-', dir='/tmp') as folder:
            root = Path(folder); server = socket.socket(socket.AF_UNIX)
            server.bind(str(root/'.socket2.sock')); server.listen(1)
            try:
                with worker.Worker(root, 'owned', worker.Hyprland(root/'.socket.sock'), signature='new') as queue:
                    with server.accept()[0]: pass
                    with self.assertRaises(ConnectionError): queue.ready('new')
                    self.assertFalse((root/'actions-owned.ready.json').exists())
                    self.assertFalse((root/'actions-owned.generation.json').exists())
                    self.assertFalse((root/'ready-owned').exists())
                with worker.Worker(root, 'owned', None): pass
            finally: server.close()

    def test_event_connection_observes_exit_without_waiting_for_another_command(self):
        ipc = module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='hl-life-', dir='/tmp') as folder:
            path = Path(folder) / '.socket2.sock'
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(path)); server.listen(1)
                lifetime = ipc.CompositorLifetime(path.with_name('.socket.sock'))
                try:
                    peer, _ = server.accept()
                    with peer:
                        self.assertTrue(lifetime.alive())
                        peer.sendall(b'workspace>>2\n')
                        self.assertTrue(lifetime.alive(.05))
                    self.assertFalse(lifetime.alive(.05))
                finally:
                    lifetime.close()
                link = path.with_name('elsewhere'); path.rename(link); path.symlink_to(link)
                with self.assertRaises(ValueError): ipc.CompositorLifetime(path.with_name('.socket.sock'))

    def test_display_binding_releases_its_marker_but_preserves_a_replacement(self):
        worker = module('session_actions')
        with tempfile.TemporaryDirectory(prefix='hl-display-', dir='/tmp') as folder:
            root = Path(folder); marker = root / 'display-owned'
            previous = worker.loopy_input.IPC_ROOT
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                    server.bind(str(root / 'wayland-1'))
                    binding = worker.configure_input(root, 'owned', 'wayland-1')
                    self.assertTrue(callable(getattr(binding, 'close', None)), 'display binding has no owner cleanup')
                    binding.close(); binding.close()
                    self.assertFalse(marker.exists(), 'old compositor display marker survived')
                    binding = worker.configure_input(root, 'owned', 'wayland-1')
                    replacement = root / 'replacement'; replacement.write_text('new owner\n')
                    replacement.replace(marker)
                    binding.close()
                    self.assertEqual(marker.read_text(), 'new owner\n')
            finally:
                worker.loopy_input.IPC_ROOT = previous

    def test_first_start_accepts_queued_jobs_but_replacement_rejects_old_input(self):
        worker, ipc = module('session_actions'), module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='hl-generation-', dir='/tmp') as folder:
            root = Path(folder); peer = OwnedSocket(root / 'ctl', [[b'ok']] * 3)
            command = root / 'command-owned-0000000000000001.json'
            def enqueue(target, created):
                command.write_text(json.dumps({'action': 'workspace', 'target': target, 'created_ns': created}))
            try:
                submitted = time.monotonic_ns()
                with worker.Worker(root, 'owned', ipc.Hyprland(root / 'ctl')) as queue:
                    queue.ready('first'); enqueue('1', submitted); queue.consume()
                    self.assertFalse((root / 'error-owned.log').exists(), 'valid startup input was rejected')
                # A worker-only restart on the same compositor retains pending input.
                with worker.Worker(root, 'owned', ipc.Hyprland(root / 'ctl')) as queue:
                    queue.ready('first'); enqueue('2', submitted); queue.consume()
                with worker.Worker(root, 'owned', ipc.Hyprland(root / 'ctl')) as queue:
                    queue.ready('replacement'); enqueue('9', submitted); queue.consume()
                    self.assertFalse((root / 'error-owned.log').exists(), 'retired input opened the error UI')
                    for invalid in (True, None, -1, 2**63, time.monotonic_ns() + 10**12):
                        enqueue('9', invalid); queue.consume()
                    enqueue('3', time.monotonic_ns()); queue.consume()
                self.assertFalse(command.exists())
            finally:
                peer.close()
            self.assertEqual(peer.requests, ["dispatch hl.dsp.focus({workspace='%s'})" % v for v in ('1', '2', '3')])

    def test_retired_generation_is_quiet_and_fresh_record_in_same_batch_dispatches(self):
        worker, ipc = module('session_actions'), module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='hl-retired-', dir='/tmp') as folder:
            root = Path(folder); peer = OwnedSocket(root / 'ctl', [[b'ok']] * 2)
            try:
                with worker.Worker(root, 'owned', None) as first:
                    first.ready('old')
                with worker.Worker(root, 'owned', ipc.Hyprland(root / 'ctl')) as queue:
                    queue.ready('replacement')
                    error = root / 'error-owned.log'
                    other = root / 'command-other-0000000000000001.json'
                    other.write_bytes(b'KEEP_OTHER_SESSION')
                    for batch in range(2):
                        if batch:
                            error.write_bytes(b'Desktop command failed: OSError\n')
                            error.chmod(0o600)
                            before = error.stat()
                        stale = root / 'command-owned-0000000000000001.json'
                        fresh = root / 'command-owned-0000000000000002.json'
                        stale.write_text(json.dumps({'action':'workspace','target':'9',
                            'created_ns':queue.minimum_ns - 1}))
                        fresh.write_text(json.dumps({'action':'workspace','target':'3',
                            'created_ns':time.monotonic_ns()}))
                        self.assertEqual(queue.consume(), 2)
                        self.assertFalse(stale.exists()); self.assertFalse(fresh.exists())
                        if batch:
                            after = error.stat()
                            self.assertEqual(error.read_bytes(), b'Desktop command failed: OSError\n')
                            self.assertEqual((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns))
                        else:
                            self.assertFalse(error.exists(), 'retired input published a user-visible failure')
                    self.assertEqual(other.read_bytes(), b'KEEP_OTHER_SESSION')
            finally: peer.close()
            self.assertIsNone(peer.error)
            self.assertEqual(peer.requests, ["dispatch hl.dsp.focus({workspace='3'})"] * 2)

    def test_invalid_generation_timestamp_and_malformed_record_still_report_without_input(self):
        worker, ipc = module('session_actions'), module('hyprland_actions')
        with tempfile.TemporaryDirectory(prefix='hl-invalid-time-', dir='/tmp') as folder:
            root = Path(folder); command = root / 'command-owned-0000000000000001.json'
            error = root / 'error-owned.log'
            with worker.Worker(root, 'owned', None) as first:
                first.ready('old')
            with worker.Worker(root, 'owned', ipc.Hyprland(root / 'never-open')) as queue:
                queue.ready('replacement')
                invalid = [True, False, None, 'PRIVATE_TYPED_SENTINEL', 1.5, -1, 0, 2**63,
                    2**63 - 1, time.monotonic_ns() + 10**12]
                records = [json.dumps({'action':'workspace','target':'9','created_ns':created})
                    for created in invalid]
                records += [json.dumps({'action':'workspace','target':'9'}),
                    '{PRIVATE_TYPED_SENTINEL', '[]', json.dumps({'action':'workspace',
                    'target':'PRIVATE_TYPED_SENTINEL','created_ns':time.monotonic_ns()})]
                for record in records:
                    with self.subTest(record=record):
                        command.write_text(record)
                        self.assertEqual(queue.consume(), 1)
                        self.assertFalse(command.exists())
                        label = b'JSONDecodeError' if record == '{PRIVATE_TYPED_SENTINEL' else b'ValueError'
                        self.assertEqual(error.read_bytes(), b'Desktop command failed: ' + label + b'\n')
                        error.unlink()

    def test_corrupt_or_redirected_generation_is_preserved(self):
        worker = module('session_actions')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); marker = root / 'actions-owned.generation.json'
            marker.write_bytes(b'keep user data')
            with worker.Worker(root, 'owned', None) as queue:
                with self.assertRaises(ValueError): queue.ready('replacement')
            self.assertEqual(marker.read_bytes(), b'keep user data')
            target = root / 'saved'; marker.rename(target); marker.symlink_to(target)
            with worker.Worker(root, 'owned', None) as queue:
                with self.assertRaises((OSError, ValueError)): queue.ready('replacement')
            self.assertTrue(marker.is_symlink())
            self.assertEqual(target.read_bytes(), b'keep user data')


if __name__ == '__main__':
    unittest.main()
