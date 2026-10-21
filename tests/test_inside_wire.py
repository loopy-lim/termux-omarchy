"""Pure owned internal-app wire boundaries; no GTK/device/JVM imports."""
import json,os,socket,struct,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];PATH=ROOT/'android/assets/omarchy-bridge/inside_wire.py'
def load():
 if not PATH.exists():return None
 m=types.ModuleType('inside_wire_test');m.__file__=str(PATH);exec(compile(PATH.read_bytes(),str(PATH),'exec'),m.__dict__);return m
S=dict(session='token-1',window='a'*32,generation=1)
T=dict(component='org.example/.Main',uid=10123)
G=dict(epoch=1,width=2,height=2,density=160)
L=dict(stamp=S,target=T,task_id=42,display_id=7)
def text(v):b=v.encode();return struct.pack('>H',len(b))+b
def stamp():return text('token-1')+text('a'*32)+struct.pack('>q',1)
def target():return text('org.example/.Main')+struct.pack('>i',10123)
def geometry():return struct.pack('>qiii',1,2,2,160)
def response(kind,meta,payload=b''):
 body=struct.pack('>IBBH',0x4c495231,1,kind,len(meta))+meta+payload
 return struct.pack('>i',len(body))+body
def grant():
 body=struct.pack('>IB',0x4c494731,1)+text('token-1')+struct.pack('>iiiiqq',10330,55,2000,99,123,1)
 return struct.pack('>I',len(body))+body
class WireTests(unittest.TestCase):
 def code(self):m=load();self.assertIsNotNone(m,'internal-app wire module missing');return m
 def test_open_bytes_match_independent_big_endian_fixture_and_reject_bool_uid(self):
  m=self.code();v=dict(stamp=S,sequence=1,action='OPEN',target=T,task_id=0,display_id=0,geometry=G,x=0,y=0,code=0,pressed=False)
  body=struct.pack('>IBB',0x4c495031,1,1)+stamp()+struct.pack('>q',1)+target()+struct.pack('>ii',0,0)+geometry()+struct.pack('>iiiB',0,0,0,0)
  self.assertEqual(m.command(v),struct.pack('>i',len(body))+body)
  with self.assertRaises(ValueError):m.command({**v,'target':{**T,'uid':True}})
 def test_fragmented_hello_decodes_actual_authority_and_strict_keys(self):
  m=self.code();meta=text('token-1')+struct.pack('>iiiqqiH',10330,2000,99,123,1,127,2)+struct.pack('>HH',30,88)
  packet=grant()+response(1,meta);d=m.Decoder();out=[]
  for b in packet:out+=d.feed(bytes([b]))
  self.assertEqual(len(out),2);self.assertEqual(out[0]['type'],'GRANT');self.assertEqual(out[1]['type'],'HELLO')
  self.assertEqual((out[1]['shell_uid'],out[1]['shell_pid'],out[1]['birth'],out[1]['keys']),(2000,99,123,[30,88]))
  with self.assertRaises(ValueError):m.Decoder().feed(grant()+response(1,meta[:-2]+struct.pack('>H',30)))
 def test_frame_layout_payload_and_nonframe_trailing_bytes_are_bounded(self):
  m=self.code();meta=stamp()+target()+struct.pack('>ii',42,7)+geometry()+struct.pack('>qiqi',1,8,16,1)
  payload=b'\x01\x02\x03\xff'*4;row=m.Decoder().feed(grant()+response(4,meta,payload))[1]
  self.assertEqual((row['sequence'],row['stride'],row['data']),(1,8,payload))
  for data in (response(4,meta,payload[:-1]),response(4,meta,payload+b'x'),struct.pack('>i',67112969),response(6,struct.pack('>qB',0,12),b'x')):
   with self.subTest(length=len(data)),self.assertRaises(ValueError):m.Decoder().feed(grant()+data)
 def test_partial_output_never_duplicates_packet_or_blocks_on_eagain(self):
  m=self.code();writer=m.Output();writer.put(b'abcdefgh');received=bytearray()
  class Socket:
   calls=0
   def send(self,data):
    self.calls+=1
    if self.calls==2:raise BlockingIOError()
    n=min(2,len(data));received.extend(data[:n]);return n
  s=Socket();writer.flush(s);self.assertEqual(bytes(received),b'ab')
  writer.flush(s);self.assertEqual(bytes(received),b'abcdefgh');self.assertFalse(writer.pending)
 def test_old_borrowed_payload_survives_resize_until_exact_release(self):
  m=self.code();pending=m.Retirement();frame=dict(type='FRAME',task=L,geometry=G,sequence=1,stride=8,bytes=16,format=1,data=b'x'*16)
  pending.accept(frame)
  with self.assertRaises(ValueError):pending.accept({**frame,'sequence':2})
  wrong={**frame,'geometry':{**G,'epoch':2}}
  with self.assertRaises(ValueError):pending.copied(wrong)
  body=struct.pack('>IB',0x4c494131,1)+stamp()+target()+struct.pack('>ii',42,7)+geometry()+struct.pack('>q',1)
  self.assertEqual(pending.copied(frame),struct.pack('>i',len(body))+body)
  pending.accept({**frame,'sequence':2})
  with self.assertRaises(ValueError):pending.copied(frame)
 def test_catalog_requires_fresh_owned_three_columns_and_canonical_component_encoding(self):
  m=self.code()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apps-token-1.tsv';p.write_text('org.example/.Main\tPublic label\t10123\n')
   self.assertEqual(m.catalog(d,'token-1','b3JnLmV4YW1wbGUvLk1haW4'),T)
   p.write_text('org.example/.Main\tPublic label\n')
   with self.assertRaises(ValueError):m.catalog(d,'token-1','b3JnLmV4YW1wbGUvLk1haW4')
   p.unlink();p.symlink_to('/etc/passwd')
   with self.assertRaises((OSError,ValueError)):m.catalog(d,'token-1','b3JnLmV4YW1wbGUvLk1haW4')
 def test_java_strict_scroll_and_shell_uid_values_match(self):
  m=self.code();v=dict(stamp=S,sequence=2,action='SCROLL',target=T,task_id=42,display_id=7,geometry=G,x=1,y=1,code=0,pressed=False,scroll_x=0,scroll_y=0)
  with self.assertRaises(ValueError):m.command(v)
  with self.assertRaises(ValueError):m.command({**v,'scroll_x':120,'target':{**T,'uid':2000}})
  bad=text('token-1')+struct.pack('>iiiqqiH',2000,2000,99,123,1,127,0)
  with self.assertRaises(ValueError):m.Decoder().feed(grant()+response(1,bad))
 def test_live_socket_identity_revalidation_never_uses_app_denied_proc(self):
  m=self.code()
  class Socket:
   uid=10330;pid=55
   def fileno(self):return fd
   def getsockopt(self,*unused):return struct.pack('3i',self.pid,self.uid,2000)
  left,right=socket.socketpair()
  self.addCleanup(left.close);self.addCleanup(right.close)
  with patch.object(m.socket,'SO_PEERCRED',17,create=True),patch.object(m.os,'getuid',return_value=10330):
   fd=left.fileno();s=Socket();identity=m.socket_identity(s,55)
   m.check_peer(s,identity);s.uid=1000
   with self.assertRaises(ValueError):m.check_peer(s,identity)
   s.uid=10330;s.pid=100
   with self.assertRaises(ValueError):m.check_peer(s,identity)
   s.pid=55
   with self.assertRaises(ValueError):m.check_peer(s,{**identity,'socket_ino':identity['socket_ino']+1})
 def test_grant_is_mandatory_first_packet_and_fragmented_exactly(self):
  m=self.code();hello=response(1,text('token-1')+struct.pack('>iiiqqiH',10330,2000,99,123,1,127,0))
  with self.assertRaises(ValueError):m.Decoder().feed(hello)
  d=m.Decoder();out=[]
  for b in grant()+hello:out+=d.feed(bytes([b]))
  self.assertEqual([row['type'] for row in out],['GRANT','HELLO'])
  self.assertEqual((out[0]['app_uid'],out[0]['app_pid'],out[0]['shell_uid'],out[0]['birth']),(10330,55,2000,123))
  with self.assertRaises(ValueError):d.feed(grant())
  d=m.Decoder()
  with self.assertRaises(ValueError):d.feed(grant()[:-1]+b'\x00')
 def test_connect_requires_current_app_pid_and_only_app_hub_endpoint(self):
  m=self.code();left,right=socket.socketpair();self.addCleanup(left.close);self.addCleanup(right.close)
  class Socket:
   pid=55;closed=False;names=[]
   def fileno(self):return left.fileno()
   def getsockopt(self,*args):return struct.pack('3i',self.pid,10330,10330)
   def settimeout(self,value):self.timeout=value
   def setblocking(self,value):self.blocking=value
   def connect(self,name):self.names.append(name)
   def close(self):self.closed=True
  s=Socket()
  with patch.object(m.socket,'SO_PEERCRED',17,create=True),patch.object(m.os,'getuid',return_value=10330),patch.object(m.socket,'socket',return_value=s) as create,patch.dict(m.os.environ,{'LOOPY_ANDROID_PID':'55'}):
   sock,identity=m.connect('token-1');self.assertIs(sock,s)
   self.assertEqual((s.names,s.timeout,s.blocking,identity['app_pid']),(['\0loopy-inside-app-token-1'],2,False,55))
   s.pid=56
   with self.assertRaises(ValueError):m.connect('token-1')
   self.assertTrue(s.closed)
   for value in ('','0','+55','55x','2147483648'):
    create.reset_mock()
    with patch.dict(m.os.environ,{'LOOPY_ANDROID_PID':value}),self.assertRaises(ValueError):m.connect('token-1')
    create.assert_not_called()
 def test_birth_parser_handles_parentheses_and_rejects_mismatched_pid(self):
  m=self.code();data='99 (own (shell)) S '+' '.join(['0']*18+['123'])
  self.assertEqual(m.birth(data,99),123)
  with self.assertRaises(ValueError):m.birth(data,100)
if __name__=='__main__':unittest.main()
