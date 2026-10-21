"""Desktop-sized PID trees retain exact identity checks and a finite ceiling."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

class ProcessCapacityTests(unittest.TestCase):
    def setUp(self):
        path=Path(__file__).resolve().parents[1]/'termux/processes.py'
        spec=importlib.util.spec_from_file_location('desktop_capacity_processes',path)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.owner=dict(pid=os.getpid(),ppid=os.getppid(),pgid=os.getpid(),uid=os.getuid(),starttime='1',command=['supervisor'])

    def records(self,count):
        return {pid:dict(self.owner,pid=pid,ppid=self.owner['pid'],pgid=pid,starttime=str(pid),command=['public-child']) for pid in range(100000,100000+count)}

    def refresh(self,count):
        rows=self.records(count);rows[self.owner['pid']]=self.owner
        with mock.patch.object(self.m,'identity',side_effect=lambda pid,**kw:rows.get(pid)), mock.patch.object(self.m,'snapshot',return_value=rows), mock.patch.object(self.m,'child_ids',return_value=None):
            return self.m.OwnedProcesses().refresh()

    def test_1024_owned_descendants_are_a_supported_desktop_workload(self):
        self.assertEqual(len(self.refresh(1024)),1024)

    def test_4096_descendants_are_allowed_but_a_runaway_tree_is_refused(self):
        self.assertEqual(len(self.refresh(4096)),4096)
        with self.assertRaisesRegex(ValueError,'descendant count exceeds bound'):self.refresh(4097)

    def test_optional_kernel_children_uses_same_pid_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            proc=Path(temp);task=proc/'123/task/123';task.mkdir(parents=True)
            (task/'children').write_text(' '.join(str(pid) for pid in range(10000,11024)))
            self.assertEqual(len(self.m.child_ids(123,proc)),1024)
            (task/'children').write_text(' '.join(str(pid) for pid in range(10000,14097)))
            with self.assertRaisesRegex(ValueError,'descendant count exceeds bound'):self.m.child_ids(123,proc)

if __name__=='__main__':unittest.main()
