"""Real compressed wire pixels and cross-language codec/admission behavior."""
import importlib.util
import os
from pathlib import Path
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
def wire():
    path = ROOT/'android/assets/omarchy-bridge/inside_wire.py'
    spec = importlib.util.spec_from_file_location('compact_test_wire', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
def text(value):
    raw = value.encode('ascii'); return struct.pack('>H',len(raw))+raw
def grant():
    body = struct.pack('>IB',0x4c494731,1)+text('token-1')+struct.pack('>iiiiqq',10330,55,2000,99,123,1)
    return struct.pack('>i',len(body))+body
def compressed(payload, sequence=1, declared=64):
    stamp = text('token-1')+text('a'*32)+struct.pack('>q',1)
    target = text('org.example/.Main')+struct.pack('>i',10123)
    metadata = stamp+target+struct.pack('>iiqiii',42,7,1,4,4,160)
    metadata += struct.pack('>qiqiq',sequence,16,declared,1,len(payload))
    body = struct.pack('>IBBH',0x4c495231,1,7,len(metadata))+metadata+payload
    return struct.pack('>i',len(body))+body

class CompactWireTests(unittest.TestCase):
    def test_opt_in_session_keeps_authenticated_open_focus_frame_and_close_lifecycle(self):
        import test_inside_window as fixture
        module=fixture.load(); g=dict(epoch=1,width=4,height=4,density=160)
        try: session=module.Session('token-1','a'*32,10330,fixture.T,fixture.P,g,clock=lambda:1,compressed=True)
        except TypeError as failure: self.fail('compressed Session admission missing: '+str(failure))
        legacy=module.Session('token-1','a'*32,10330,fixture.T,fixture.P,g,clock=lambda:1)
        for value in (legacy,session):
            value.receive(dict(fixture.GRANT)); value.receive(dict(fixture.HELLO))
        self.assertEqual(legacy.inflight['action'],'OPEN'); self.assertEqual(session.inflight['action'],'OPEN_ZLIB')
        lease=dict(stamp=session.stamp,target=fixture.T,task_id=42,display_id=7)
        def reply(kind='ACK'):
            command=session.inflight; action=command['action']
            session.receive(dict(type=kind,observation=dict(task=lease,top_uid=10123,visible=True,running=True,focused=True),
                geometry=command['geometry'],request_sequence=command['sequence'],
                inputs_released=action in ('RELEASE_ALL','RESIZE') or action=='FOCUS' and not command['pressed']))
        reply('OPENED'); session.focus(True); reply(); self.assertTrue(session.input.focused)
        original=b'\x12\x34\x56\xff'*16; decoder=wire().Decoder()
        row=decoder.feed(grant()+compressed(zlib.compress(original,1)))[1]; seen=[]
        session.receive(row,lambda frame,display:seen.append((frame['data'],display)))
        self.assertEqual(seen,[(original,True)]); self.assertIsNone(session.retirement.pending)
        session.close(); reply(); reply(); self.assertEqual(session.inflight['action'],'CLOSE')
        session.receive(dict(type='CLOSED',stamp=session.stamp,task_id=42,display_id=7,
            task_removed=True,display_removed=True,inputs_released=True))
        self.assertEqual(session.state,'CLOSED'); self.assertFalse(session.input.focused)

    def test_fragmented_zlib_pixels_normalize_to_exact_original_frame_and_release(self):
        original = b'\x12\x34\x56\xff'*16
        packet = grant()+compressed(zlib.compress(original,1)); decoder=wire().Decoder(); rows=[]
        try:
            for value in packet: rows += decoder.feed(bytes([value]))
        except ValueError as failure:
            self.fail('valid compressed FRAME rejected: '+str(failure))
        decoder.finish(); self.assertEqual(len(rows),2)
        row=rows[1]; self.assertEqual(row['type'],'FRAME'); self.assertEqual(row['data'],original)
        self.assertEqual((row['bytes'],row['stride'],row['format']),(64,16,1))
        module=wire(); retirement=module.Retirement(); retirement.accept(row)
        released=retirement.copied(row)
        self.assertEqual(struct.unpack_from('>IB',released,4),(0x4c494131,1))
        self.assertIsNone(retirement.pending)
    def test_bad_streams_cannot_fall_back_to_raw_or_allocate_declared_extra_pixels(self):
        original=b'\x12\x34\x56\xff'*16; good=zlib.compress(original,1)
        corrupt=good[:-1]+bytes([good[-1]^1])
        dictionary=zlib.compressobj(zdict=b'public dictionary'); dictionary=dictionary.compress(original)+dictionary.flush()
        for payload in (good[:-1],good+b'x',good+good,corrupt,dictionary,
                        zlib.compress(b'x'*65,1),zlib.compress(b'x'*63,1),b'x'*64):
            with self.subTest(payload_length=len(payload)),self.assertRaises(ValueError):
                wire().Decoder().feed(grant()+compressed(payload))
    def test_expanded_batch_is_rejected_before_returning_two_borrowed_frames(self):
        payload=zlib.compress(b'x'*64,1)
        with self.assertRaises(ValueError): wire().Decoder().feed(grant()+compressed(payload)+compressed(payload,2))
    def test_zlib_open_bytes_are_explicit_and_legacy_open_is_unchanged(self):
        module=wire(); value=dict(stamp=dict(session='token-1',window='a'*32,generation=1),sequence=1,
            action='OPEN',target=dict(component='org.example/.Main',uid=10123),task_id=0,display_id=0,
            geometry=dict(epoch=1,width=4,height=4,density=160),x=0,y=0,code=0,pressed=False)
        legacy=module.command(value); desired=bytearray(legacy); desired[9]=11
        try: encoded=module.command({**value,'action':'OPEN_ZLIB'})
        except ValueError as failure: self.fail('explicit compressed OPEN rejected: '+str(failure))
        self.assertEqual(encoded,bytes(desired)); self.assertEqual(legacy[9],1)
        with self.assertRaises(ValueError): module.command({**value,'action':'OPEN_ZLIB','task_id':42,'display_id':7})
