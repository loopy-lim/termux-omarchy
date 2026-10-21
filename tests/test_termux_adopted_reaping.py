import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'termux/processes.py'
spec = importlib.util.spec_from_file_location('adopted_processes', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AdoptedReapingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.proc = Path(self.temp.name)
        self.owner = module.OwnedProcesses.__new__(module.OwnedProcesses)
        self.owner.owner = {'pid': 500, 'uid': os.getuid()}
        self.owner.spawned = {502}
    def tearDown(self):
        self.temp.cleanup()
    def entry(self, pid, parent, state):
        p = self.proc / str(pid);p.mkdir()
        (p/'stat').write_text(f'{pid} (name with ) parentheses) {state} {parent} 0 0')
    def test_reaps_only_dead_adoptees_and_preserves_popen_exit_status(self):
        self.entry(501,500,'Z');self.entry(502,500,'Z')
        self.entry(503,500,'S');self.entry(504,999,'Z')
        with patch.object(module.os,'waitpid',return_value=(501,0)) as wait:
            self.owner.reap_adopted_zombies(self.proc)
        self.assertEqual([call.args[0] for call in wait.call_args_list],[501])
        self.assertTrue(wait.call_args.args[1] & os.WNOHANG)
    def test_concurrent_reap_is_harmless(self):
        self.entry(501,500,'Z')
        with patch.object(module.os,'waitpid',side_effect=ChildProcessError):
            self.owner.reap_adopted_zombies(self.proc)
    def test_missing_procfs_is_host_only_noop(self):
        with patch.object(module.os,'waitpid') as wait:
            self.owner.reap_adopted_zombies(self.proc/'absent')
        wait.assert_not_called()

if __name__=='__main__':unittest.main()
