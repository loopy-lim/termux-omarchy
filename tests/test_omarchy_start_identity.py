"""A transient empty /proc cmdline must never enter the session journal."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'termux'))
import omarchy_runtime as runtime

class StartIdentityTests(unittest.TestCase):
    def test_waits_for_exec_before_publishing_supervisor(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);home=base/'home';prefix=base/'usr'
            home.mkdir();prefix.mkdir();r=runtime.Runtime(home,prefix)
            r.root.mkdir(mode=0o700,parents=True,exist_ok=True);r.short=base/'short'
            token=str(uuid.uuid4());published=[]
            def state():
                if not published:return None
                value=dict(published[-1])
                if value['processes']:value['phase']='ready'
                return value
            r.state=state;r.publish=lambda value:published.append(dict(value))
            r.installed=lambda:None;r.choose_display=lambda:':21'
            r.status=lambda request:{'status':'ready'}
            argv=[str(r.prefix/'bin/python3'),str(r.root/'omarchy_runtime.py'),'_supervise',token,':21']
            record={'pid':12345,'ppid':os.getpid(),'pgid':12345,'uid':os.getuid(),'starttime':'123','command':argv}
            class Child:
                pid=12345
                def poll(self):return None
            with patch.object(runtime,'prepare_start',return_value='boot'), \
                 patch.object(runtime,'proot_selection',return_value=None), \
                 patch.object(runtime.subprocess,'Popen',return_value=Child()), \
                 patch.object(runtime,'identity',side_effect=[dict(record,command=[]),dict(record,command=[]),record]):
                self.assertEqual(r.start(token)['status'],'ready')
            self.assertEqual(published[-1]['processes'][0]['command'],argv)
            self.assertFalse(any(v['processes'] and not v['processes'][0]['command'] for v in published))

if __name__=='__main__':unittest.main()
