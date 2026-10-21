"""Fresh parentage can authorize an exec missed by the procfs snapshot."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'termux'))
import processes as m

class ExecRaceTests(unittest.TestCase):
    def run_refresh(self,parent):
        owner={'pid':500,'ppid':1,'pgid':500,'uid':os.getuid(),'starttime':'10','command':['supervisor']}
        old=dict(owner,pid=501,ppid=500,starttime='11',command=['before-exec'])
        fresh=dict(old,ppid=parent,command=['after-exec'])
        tracker=m.OwnedProcesses.__new__(m.OwnedProcesses)
        tracker.owner=owner;tracker.known={501:old};tracker.spawned=set();tracker.child_lists_available=True
        with patch.object(m,'identity',side_effect=lambda pid,**kw:{500:owner,501:fresh}.get(pid)), \
             patch.object(m,'snapshot',return_value={500:owner}), \
             patch.object(m,'child_ids',return_value=None), \
             patch.object(tracker,'reap_adopted_zombies'):
            return tracker.refresh()
    def test_exec_missed_by_snapshot_is_revalidated_against_live_parent(self):
        self.assertEqual(self.run_refresh(500)[0]['command'],['after-exec'])
    def test_termination_retries_transient_snapshot_without_signalling_it(self):
        tracker=m.OwnedProcesses.__new__(m.OwnedProcesses)
        with patch.object(tracker,'refresh',side_effect=[ValueError('native descendant identity changed'),[]]), \
             patch.object(m,'reap_children',side_effect=[False,True]), \
             patch.object(m,'signal_process') as send:
            tracker.terminate()
        send.assert_not_called()

    def test_persistent_ambiguity_still_fails_without_signalling(self):
        tracker=m.OwnedProcesses.__new__(m.OwnedProcesses)
        with patch.object(tracker,'refresh',side_effect=ValueError('native descendant identity changed')), \
             patch.object(m,'reap_children',return_value=False), \
             patch.object(m.time,'monotonic',side_effect=[0,3]), \
             patch.object(m,'signal_process') as send:
            with self.assertRaisesRegex(ValueError,'descendant identity changed'):tracker.terminate()
        send.assert_not_called()

    def test_changed_identity_without_live_owned_parent_is_refused(self):
        with self.assertRaisesRegex(ValueError,'descendant identity changed'):self.run_refresh(999)

if __name__=='__main__':unittest.main()
