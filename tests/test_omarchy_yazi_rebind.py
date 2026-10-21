"""Linux kernel peer credentials for Yazi's unlink/rebind DDS socket lifecycle."""
import importlib.util
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / 'termux/omarchy_resources.py').is_file():
    ROOT = Path(__file__).resolve().parent

LISTENER = '''import os,select,socket,sys
s=socket.socket(socket.AF_UNIX);s.bind(sys.argv[1]);s.listen(8)
print('READY',flush=True)
while True:
 ready,_,_=select.select([s,sys.stdin],[],[],10)
 if sys.stdin in ready: break
 if s in ready:
  c,_=s.accept();c.close()
'''


@unittest.skipUnless(hasattr(socket, 'SO_PEERCRED') and Path('/proc/self/stat').exists(),
                     'requires real Linux SO_PEERCRED and /proc; run on the Android device')
class YaziRebindTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / 'termux'))
        self.addCleanup(sys.path.remove, str(ROOT / 'termux'))
        spec = importlib.util.spec_from_file_location('yazi_resources', ROOT / 'termux/omarchy_resources.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        from processes import identity
        self.identity = identity
        self.temp = tempfile.TemporaryDirectory(prefix='yr-', dir=os.environ.get('TMPDIR', '/tmp'))
        self.addCleanup(self.temp.cleanup)
        self.short = Path(self.temp.name).resolve()
        (self.short / 'owner.json').write_text('{}')
        self.prefix = self.short / 'absent-prefix'
        self.value = {'runtime': self.module.row(self.short)[:3], 'display': ':98'}
        self.children = []
        self.addCleanup(self.close_children)

    def listener(self, path):
        path.parent.mkdir(exist_ok=True)
        p = subprocess.Popen([sys.executable, '-c', LISTENER, str(path)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
        self.children.append(p)
        self.assertTrue(select.select([p.stdout], [], [], 3)[0], 'listener did not become ready')
        self.assertEqual(p.stdout.readline().strip(), 'READY')
        r = self.identity(p.pid, strict=True)
        self.assertEqual(r['ppid'], os.getpid())
        self.assertEqual(r['command'][0], sys.executable)
        return p, r

    def close_children(self):
        for p in self.children:
            if p.poll() is None:
                p.stdin.close()
            p.wait(timeout=3)
            for stream in (p.stdout, p.stderr):
                stream.close()

    def capture(self, records):
        return self.module.capture(self.short, self.prefix, self.value, [], runtime_records=records)

    def replace(self, relative='yazi+1000/.dds.sock'):
        path = self.short / relative
        first, record = self.listener(path)
        self.module.capture(self.short, self.prefix, self.value, [])
        old = self.module.row(path)
        first.stdin.close(); first.wait(timeout=3)
        path.unlink()
        replacement, record = self.listener(path)
        self.assertNotEqual(self.module.row(path)[1], old[1])
        return path, old, replacement, record

    def test_owned_yazi_can_replace_its_dds_socket_and_later_retire(self):
        path, old, replacement, record = self.replace()
        try:
            self.capture([record])
        except ValueError as error:
            self.fail(f'Authenticated session DDS rebind must keep Linux running: {error}')
        self.assertEqual(self.value['resources']['runtime:yazi+1000/.dds.sock'], self.module.row(path))
        replacement.stdin.close(); replacement.wait(timeout=3)
        self.module.cleanup(self.short, self.prefix, self.value)
        self.assertFalse(path.exists())
        self.assertTrue((self.short / 'owner.json').exists())

    def test_same_uid_listener_outside_owned_records_is_rejected(self):
        path, old, replacement, record = self.replace()
        with self.assertRaises(ValueError): self.capture([])
        self.assertEqual(self.value['resources']['runtime:yazi+1000/.dds.sock'], old)
        with self.assertRaises(ValueError): self.module.cleanup(self.short, self.prefix, self.value)
        self.assertTrue(path.is_socket())

    def test_stale_process_identity_cannot_authenticate_a_new_dds_socket(self):
        path, old, replacement, record = self.replace()
        record = dict(record, starttime=str(int(record['starttime']) + 1))
        with self.assertRaises(ValueError): self.capture([record])
        self.assertEqual(self.value['resources']['runtime:yazi+1000/.dds.sock'], old)

    def test_unreachable_replacement_is_not_authenticated(self):
        path, old, replacement, record = self.replace()
        replacement.stdin.close(); replacement.wait(timeout=3)
        with self.assertRaises(ValueError): self.capture([record])
        self.assertEqual(self.value['resources']['runtime:yazi+1000/.dds.sock'], old)

    def test_group_write_change_is_not_a_normal_rebind(self):
        path, old, replacement, record = self.replace()
        path.chmod(0o620)
        with self.assertRaises(ValueError): self.capture([record])
        self.assertEqual(self.value['resources']['runtime:yazi+1000/.dds.sock'], old)

    def test_yazi_listener_cannot_replace_a_core_wayland_socket(self):
        path, old, replacement, record = self.replace(relative='wayland-1')
        with self.assertRaises(ValueError): self.capture([record])
        self.assertEqual(self.value['resources']['runtime:wayland-1'], old)

    def test_symlink_at_dds_path_is_never_followed_or_accepted(self):
        path = self.short / 'yazi+1000/.dds.sock'
        child, record = self.listener(path)
        self.module.capture(self.short, self.prefix, self.value, [])
        old = self.module.row(path)
        child.stdin.close(); child.wait(timeout=3); path.unlink()
        outside = self.short.parent / (self.short.name + '-outside')
        outside.write_text('public external marker')
        self.addCleanup(outside.unlink)
        path.symlink_to(outside)
        with self.assertRaises(ValueError): self.capture([record])
        self.assertEqual(self.value['resources']['runtime:yazi+1000/.dds.sock'], old)
        self.assertEqual(outside.read_text(), 'public external marker')


if __name__ == '__main__':
    unittest.main()
