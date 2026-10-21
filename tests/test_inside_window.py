"""Authenticated session and owned-payload lifecycle without GTK/socket/device execution."""
import copy,sys,types,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DIRECTORY=ROOT/'android/assets/omarchy-bridge'
def load():
 modules={}
 for name in ('inside_wire','inside_input','inside_window'):
  p=DIRECTORY/(name+'.py');m=types.ModuleType(name);m.__file__=str(p)
  if not p.exists():return None
  sys.modules[name]=m;exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);modules[name]=m
 return modules['inside_window']
T=dict(component='org.example/.Main',uid=10123);G=dict(epoch=1,width=2,height=2,density=160)
P=dict(app_uid=10330,app_pid=55,socket_dev=1,socket_ino=2)
HELLO=dict(type='HELLO',session='token-1',app_uid=10330,shell_uid=2000,shell_pid=99,birth=123,generation=1,caps=127,keys=[30,88])
GRANT=dict(type='GRANT',session='token-1',app_uid=10330,app_pid=55,shell_uid=2000,shell_pid=99,birth=123,generation=1)
class SessionTests(unittest.TestCase):
 def model(self):
  m=load();self.assertIsNotNone(m,'GTK internal-app session missing')
  return m.Session('token-1','a'*32,10330,T,P,G,clock=lambda:1)
 def reply(self,s,kind='ACK',focused=True,released=None):
  c=s.inflight;lease=s.task or dict(stamp=c['stamp'],target=T,task_id=42,display_id=7)
  return dict(type=kind,observation=dict(task=lease,top_uid=10123,visible=True,running=True,focused=focused),geometry=c['geometry'],request_sequence=c['sequence'],inputs_released=(c['action'] in ('RELEASE_ALL','RESIZE') or c['action']=='FOCUS' and not c['pressed']) if released is None else released)
 def granted(self,s):s.receive(copy.deepcopy(GRANT));return s
 def opened(self,s):self.granted(s);s.receive(copy.deepcopy(HELLO));s.receive(self.reply(s,'OPENED'));return s
 def drain(self,s):
  for _ in range(16):
   if s.inflight is None:return
   self.assertNotEqual(s.inflight['action'],'CLOSE');s.receive(self.reply(s))
  self.fail('unbounded command plan')
 def test_kernel_peer_and_authenticated_positive_birth_required_before_open(self):
  for change in ({'birth':0},{'shell_pid':100},{'shell_uid':1000},{'app_uid':2000},{'session':'foreign'}):
   s=self.granted(self.model())
   with self.assertRaises(ValueError):s.receive({**HELLO,**change})
   self.assertFalse(s.output.pending);self.assertIsNone(s.inflight)
  s=self.granted(self.model());s.receive(copy.deepcopy(HELLO));self.assertEqual(s.inflight['action'],'OPEN')
 def test_hello_without_binder_attested_grant_never_opens(self):
  s=self.model()
  with self.assertRaises(ValueError):s.receive(copy.deepcopy(HELLO))
  self.assertFalse(s.output.pending)
 def test_grant_binds_kernel_app_peer_and_hello_to_one_backend(self):
  for change in ({'app_uid':10331},{'app_pid':56},{'session':'foreign'},{'shell_uid':1000},{'birth':0},{'generation':0}):
   s=self.model()
   with self.subTest(change=change),self.assertRaises(ValueError):s.receive({**GRANT,**change})
   self.assertFalse(s.output.pending)
  for change in ({'shell_pid':100},{'birth':124},{'generation':2}):
   s=self.granted(self.model())
   with self.subTest(change=change),self.assertRaises(ValueError):s.receive({**HELLO,**change})
   self.assertFalse(s.output.pending)
  s=self.granted(self.model())
  with self.assertRaises(ValueError):s.receive(copy.deepcopy(GRANT))
 def test_target_policy_allows_system_uid_but_never_shell_self_or_foreign_user(self):
  m=load();self.assertIsNotNone(m)
  s=m.Session('token-1','a'*32,10330,{**T,'uid':1000},P,G,clock=lambda:1)
  self.assertEqual(s.target['uid'],1000)
  for uid in (2000,10330,100000):
   with self.subTest(uid=uid),self.assertRaises(ValueError):m.Session('token-1','a'*32,10330,{**T,'uid':uid},P,G)
 def test_focus_requires_exact_ack_and_false_ack_may_observe_actual_focused(self):
  s=self.opened(self.model());s.focus(True);self.assertFalse(s.input.focused)
  ack=self.reply(s);bad={**ack,'request_sequence':99}
  with self.assertRaises(ValueError):s.receive(bad)
  s.receive(ack);self.assertTrue(s.input.focused)
  s.focus(False);self.assertFalse(s.input.focused);self.assertEqual(s.inflight['action'],'RELEASE_ALL')
  s.receive(self.reply(s));self.assertEqual(s.inflight['action'],'FOCUS');self.assertFalse(s.inflight['pressed'])
  s.receive(self.reply(s,focused=True));self.assertFalse(s.input.focused);self.assertIsNone(s.inflight)
 def test_blur_drops_queued_input_and_refocus_waits_balanced_retirement(self):
  s=self.opened(self.model());s.focus(True);self.drain(s)
  s.send_input(dict(action='KEY',code=30,pressed=True));s.send_input(dict(action='KEY_REPEAT',code=30,pressed=True))
  s.focus(False);s.focus(True);self.assertEqual(len(s.inputs),0);self.assertFalse(s.input.focused)
  s.receive(self.reply(s));self.assertEqual(s.inflight['action'],'RELEASE_ALL');s.receive(self.reply(s))
  self.assertEqual(s.inflight['action'],'FOCUS');self.assertFalse(s.inflight['pressed']);self.drain(s);self.assertTrue(s.input.focused)
 def test_resize_old_frame_copied_and_exact_retired_without_display(self):
  s=self.opened(self.model());s.focus(True);self.drain(s);s.resize(3,2,160)
  frame=dict(type='FRAME',task=s.task,geometry=G,sequence=1,stride=8,bytes=16,format=1,data=b'\x01\x02\x03\xff'*4)
  seen=[];before=len(s.output.buffer)
  def copy_frame(row,display):seen.append((row['data'],display,len(s.output.buffer)))
  s.receive(frame,copy_frame);self.assertEqual(seen,[(frame['data'],False,before)]);self.assertIsNone(s.retirement.pending)
  self.assertGreater(len(s.output.buffer),before);self.drain(s);self.assertEqual((s.geometry['epoch'],s.geometry['width']),(2,3))
  with self.assertRaises(ValueError):s.receive({**frame,'sequence':2})
 def test_copy_failure_retains_old_payload_and_never_claims_release(self):
  s=self.opened(self.model());frame=dict(type='FRAME',task=s.task,geometry=G,sequence=1,stride=8,bytes=16,format=1,data=b'x'*16)
  before=len(s.output.buffer)
  def failure(*args):raise MemoryError()
  with self.assertRaises(MemoryError):s.receive(frame,failure)
  self.assertEqual(len(s.output.buffer),before);self.assertIsNotNone(s.retirement.pending)
  s.close();self.assertIsNotNone(s.retirement.pending)
 def resizing(self):
  s=self.opened(self.model());s.focus(True);self.drain(s);s.resize(3,2,160)
  s.receive(self.reply(s));s.receive(self.reply(s));self.assertEqual(s.inflight['action'],'RESIZE')
  return s
 def future_frame(self,s,sequence=1,data=None):
  return dict(type='FRAME',task=copy.deepcopy(s.task),geometry=copy.deepcopy(s.inflight['geometry']),sequence=sequence,
   stride=12,bytes=24,format=1,data=b'\x01\x02\x03\xff'*6 if data is None else data)
 def recorder(self,seen):
  return lambda row,display:seen.append((row['sequence'],row['data'],display,copy.deepcopy(row['geometry'])))
 def test_future_resize_frame_displays_owned_bytes_once_after_ack_without_new_frame(self):
  s=self.resizing();seen=[];payload=bytearray(b'\x01\x02\x03\xff'*6);frame=self.future_frame(s,data=payload)
  s.receive(frame,self.recorder(seen));self.assertFalse(seen[-1][2]);self.assertIsNone(s.retirement.pending)
  payload[:]=b'x'*24;frame['geometry']['width']=4;frame['task']['task_id']=43
  s.receive(self.reply(s),self.recorder(seen))
  self.assertEqual([(seq,data,display) for seq,data,display,_ in seen],[(1,b'\x01\x02\x03\xff'*6,False),(1,b'\x01\x02\x03\xff'*6,True)])
  self.assertEqual(seen[-1][3],dict(epoch=2,width=3,height=2,density=160));self.assertEqual(s.frame_sequence,1)
  self.assertIsNone(s.retirement.pending);self.assertEqual(s.inflight['action'],'FOCUS')
  self.drain(s);self.assertEqual(len(seen),2)
 def test_only_latest_future_resize_frame_displays_after_ack(self):
  s=self.resizing();seen=[]
  s.receive(self.future_frame(s),self.recorder(seen));s.receive(self.future_frame(s,2,b'y'*24),self.recorder(seen))
  s.receive(self.reply(s),self.recorder(seen));self.assertEqual([(x[0],x[2]) for x in seen],[(1,False),(2,False),(2,True)])
  self.assertEqual(seen[-1][1],b'y'*24);self.assertEqual(s.frame_sequence,2)
 def test_resize_cancel_and_return_to_same_size_never_resurrects_retired_frame(self):
  s=self.resizing();seen=[];s.receive(self.future_frame(s),self.recorder(seen))
  s.resize(4,2,160);s.resize(3,2,160);s.receive(self.reply(s),self.recorder(seen));self.drain(s)
  self.assertEqual([(x[0],x[2]) for x in seen],[(1,False)])
 def test_blur_clears_future_frame_and_rejects_later_retention_until_retired(self):
  s=self.resizing();seen=[];s.receive(self.future_frame(s),self.recorder(seen));s.focus(False)
  s.receive(self.future_frame(s,2),self.recorder(seen));s.focus(True)
  s.receive(self.reply(s),self.recorder(seen));self.drain(s)
  self.assertEqual([(x[0],x[2]) for x in seen],[(1,False),(2,False)])
 def test_close_clears_future_frame_and_does_not_retain_later_frame(self):
  s=self.resizing();seen=[];s.receive(self.future_frame(s),self.recorder(seen));s.close()
  s.receive(self.future_frame(s,2),self.recorder(seen));s.receive(self.reply(s),self.recorder(seen));self.drain_until_close(s)
  self.assertEqual([(x[0],x[2]) for x in seen],[(1,False),(2,False)])
 def test_future_resize_frame_still_requires_exact_lease_geometry_and_unique_sequence(self):
  s=self.resizing();seen=[];frame=self.future_frame(s)
  foreign=copy.deepcopy(frame);foreign['task']['stamp']['window']='b'*32
  bad_geometry=copy.deepcopy(frame);bad_geometry['geometry']['epoch']=3
  for bad in (foreign,bad_geometry):
   with self.assertRaises(ValueError):s.receive(bad,self.recorder(seen))
  self.assertEqual(seen,[]);s.receive(frame,self.recorder(seen))
  with self.assertRaises(ValueError):s.receive({**frame,'data':b'z'*24},self.recorder(seen))
  ack=self.reply(s)
  with self.assertRaises(ValueError):s.receive({**ack,'request_sequence':99},self.recorder(seen))
  self.assertEqual(len(seen),1);s.receive(ack,self.recorder(seen))
  with self.assertRaises(ValueError):s.receive(ack,self.recorder(seen))
  self.assertEqual([(x[0],x[2]) for x in seen],[(1,False),(1,True)]);self.assertEqual(seen[-1][1],frame['data'])
 def test_close_requires_exact_owned_resource_cleanup_and_no_pending_payload(self):
  s=self.opened(self.model());s.close();self.drain_until_close(s)
  closed=dict(type='CLOSED',stamp=s.stamp,task_id=42,display_id=7,task_removed=True,display_removed=True,inputs_released=True)
  with self.assertRaises(ValueError):s.receive({**closed,'task_id':43})
  with self.assertRaises(ValueError):s.receive({**closed,'inputs_released':False})
  s.receive(closed);self.assertEqual(s.state,'CLOSED')
 def drain_until_close(self,s):
  for _ in range(16):
   if s.inflight['action']=='CLOSE':return
   s.receive(self.reply(s))
  self.fail('close not reached')
 def test_cancel_before_task_never_opens_after_delayed_hello(self):
  s=self.model();s.close()
  with self.assertRaises(ValueError):s.receive(copy.deepcopy(HELLO))
  self.assertFalse(s.output.pending);self.assertIsNone(s.inflight);self.assertEqual(s.state,'ABANDONED')
  s=self.granted(self.model());s.receive(copy.deepcopy(HELLO));self.assertTrue(s.output.pending)
  s.close();self.assertFalse(s.output.pending);self.assertEqual(s.state,'ABANDONED')
  with self.assertRaises(ValueError):s.receive(dict(type='OPENED'))
 def test_input_overflow_and_deadline_fail_closed_without_replay(self):
  s=self.opened(self.model());s.focus(True);self.drain(s)
  s.send_input(dict(action='KEY',code=30,pressed=True))
  for _ in range(64):s.send_input(dict(action='KEY_REPEAT',code=30,pressed=True))
  with self.assertRaises(ValueError):s.send_input(dict(action='KEY_REPEAT',code=30,pressed=True))
  with self.assertRaises(ValueError):s.check_timeout(100)
if __name__=='__main__':unittest.main()
