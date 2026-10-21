"""Real OpenSSH exec-ACK scheduling race and bounded peer completion."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import test_ssh_fixture as legacy

ROOT, PYTHON, SSH = legacy.ROOT, legacy.PYTHON, legacy.SSH

# Delay only the callback's return, after the real fixture has signalled ready.
# This exposes the existing thread interleaving; no production timing is changed.
BOOTSTRAP = '''import argparse, importlib.util, json, threading
from pathlib import Path
import paramiko
spec=importlib.util.spec_from_file_location('real_fixture',SOURCE)
server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
timeline=[];lock=threading.Lock()
def event(transport):
 if not hasattr(transport,'test_closed'):transport.test_closed=threading.Event()
 return transport.test_closed
def note(transport,step,kind=None):
 with lock:
  if len(timeline)<100:timeline.append({'step':step,'active':transport.active,'type':kind})
check=server.FixtureRequest.check_channel_exec_request
close=paramiko.Transport.close
send=paramiko.Transport._send_user_message
packet=paramiko.Transport._send_message
def delayed(self,channel,command):
 accepted=check(self,channel,command)
 if accepted:
  note(channel.transport,'ready_before_callback_return')
  event(channel.transport).wait(.05)
  note(channel.transport,'callback_return')
 return accepted
def closing(self):
 try:return close(self)
 finally:event(self).set();note(self,'transport_closed')
def sending(self,data):
 note(self,'user_packet_attempt',data.asbytes()[0]);return send(self,data)
def actual_packet(self,data):
 note(self,'packet_send',data.asbytes()[0]);return packet(self,data)
server.FixtureRequest.check_channel_exec_request=delayed
paramiko.Transport.close=closing
paramiko.Transport._send_user_message=sending
paramiko.Transport._send_message=actual_packet
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);parser.add_argument('--lifetime',type=float)
args=parser.parse_args()
try:server.run(args.output,args.lifetime)
finally:
 with Path(TRACE).open('x') as output:json.dump(timeline,output)
'''

HOLDING_CLIENT = '''import base64,json,socket,sys,time
import paramiko
with open(sys.argv[1]) as endpoint:value=json.load(endpoint)
transport=paramiko.Transport(socket.create_connection(('127.0.0.1',value['port']),timeout=5))
try:
 transport.start_client(timeout=5)
 assert transport.get_remote_server_key().asbytes()==base64.b64decode(value['public_key'].split()[1])
 transport.auth_none('loopy-fixture')
 channel=transport.open_session(timeout=5);channel.settimeout(5)
 start=time.monotonic();channel.exec_command('loopy-remote-witness')
 data=b''
 while True:
  part=channel.recv(4096)
  if not part:break
  data+=part
 assert data==('LOOPY_REMOTE_SSH:'+value['nonce']+'\\n').encode()
 assert channel.recv_exit_status()==0
 # Intentionally leave the transport open after replying to SSH channel close.
 # A server which waits indefinitely for a cooperative client would hang here.
 until=start+5
 while transport.is_active() and time.monotonic()<until:time.sleep(.01)
 assert not transport.is_active(),'fixture did not bound peer-completion wait'
 print(json.dumps({'elapsed_seconds':time.monotonic()-start,'bytes':len(data)}))
finally:transport.close()
'''


@unittest.skipUnless(PYTHON.is_file() and SSH.is_file(), 'workspace SSH fixture venv and OpenSSH required')
class SshFixtureRaceTests(unittest.TestCase):
    def test_late_exec_ack_keeps_real_witness_and_foreign_rejections_intact(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            trace = directory / 'timeline.json'
            bootstrap = directory / 'server.py'
            bootstrap.write_text('SOURCE=' + repr(str(ROOT/'tools/ssh_test_server.py')) + '\nTRACE=' + repr(str(trace)) + '\n' + BOOTSTRAP)
            real_popen = subprocess.Popen

            def scheduled_popen(argv, *args, **kwargs):
                command = list(argv)
                if str(ROOT/'tools/ssh_test_server.py') in command:
                    command[1] = str(bootstrap)
                return real_popen(command, *args, **kwargs)

            with patch.object(legacy.subprocess, 'Popen', scheduled_popen):
                # All original OpenSSH exit0/exact nonce/auth/foreign/cleanup assertions remain.
                legacy.SshFixtureTests().test_actual_openssh_exchange_and_foreign_commands_are_rejected()
            events = json.loads(trace.read_text())
            self.assertTrue(any(item['step'] == 'ready_before_callback_return' for item in events))
            acknowledgements = [item for item in events if item['step'] == 'user_packet_attempt' and item['type'] == 99]
            self.assertTrue(acknowledgements)
            self.assertTrue(all(item['active'] for item in acknowledgements), 'exec success was attempted on a closed transport')
            self.assertTrue(any(item['step'] == 'packet_send' and item['type'] == 99 for item in events))

    def test_uncooperative_peer_does_not_hold_a_fixture_worker_forever(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            process = subprocess.Popen([str(PYTHON), str(ROOT/'tools/ssh_test_server.py'),
                '--output', str(directory/'server'), '--lifetime', '30'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                endpoint = directory/'server/endpoint.json'
                until = time.monotonic() + 5
                while not endpoint.exists() and process.poll() is None and time.monotonic() < until:
                    time.sleep(.05)
                self.assertTrue(endpoint.is_file(), 'owned SSH fixture did not publish readiness')
                result = subprocess.run([str(PYTHON), '-c', HOLDING_CLIENT, str(endpoint)],
                    capture_output=True, text=True, timeout=12)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertLess(json.loads(result.stdout)['elapsed_seconds'], 4)
            finally:
                process.terminate(); _, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stderr)
            receipt = json.loads((directory/'server/receipt.json').read_text())
            self.assertEqual(receipt['live_workers'], 0)
            self.assertTrue(receipt['listener_closed'])
            self.assertEqual(len([item for item in receipt['exchanges'] if item.get('authenticated')]), 1)


if __name__ == '__main__':
    unittest.main()
