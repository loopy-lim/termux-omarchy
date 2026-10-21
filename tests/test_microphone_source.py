"""Owned Pulse source lifecycle and rejected private-channel requests; no microphone recording."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'android/assets/omarchy-bridge/microphone_source.py'
TOKEN = 'session-current'
A = 'a' * 32
B = 'b' * 32


class MicrophoneSourceTests(unittest.TestCase):
    def load(self):
        self.assertTrue(SOURCE.is_file(), 'No session-owned real PipeWire source endpoint')
        spec = importlib.util.spec_from_file_location('microphone_source_case', SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def fixture(self, base):
        directory = base / 'audio'; directory.mkdir(mode=0o700)
        session = directory / 'session'; session.write_text(TOKEN + '\n'); session.chmod(0o600)
        pactl = base / 'pactl'
        pactl.write_text('''#!/usr/bin/env python3
import json,pathlib,sys,time
base=pathlib.Path(__file__).parent
with (base/'commands').open('a') as log: log.write(json.dumps(sys.argv[1:])+'\\n')
if (base/'stall').exists(): time.sleep(10)
if sys.argv[1]=='load-module':
 p=base/'next';n=int(p.read_text()) if p.exists() else 40;p.write_text(str(n+1));print(n)
elif sys.argv[1]=='unload-module':
 if (base/'fail-unload').exists(): raise SystemExit(4)
elif sys.argv[1:] == ['-f','json','list','sources']:
 state=(base/'source-state').read_text() if (base/'source-state').exists() else 'SUSPENDED'
 print(json.dumps([{'name':'loopy_android_microphone','state':state,'mute':(base/'muted').exists()}]))
else: raise SystemExit(3)
''')
        pactl.chmod(0o700)
        return directory, str(pactl)

    def activation(self, directory, value):
        owned = directory / ('mic-' + value); owned.mkdir(mode=0o700)
        os.mkfifo(owned / 'input.pcm', 0o600)
        return owned

    def request(self, directory, action='start', activation=A, token=TOKEN):
        request = directory / 'microphone-request.json'
        request.write_text(json.dumps({'action': action, 'session': token, 'activation': activation}))
        request.chmod(0o600)

    def commands(self, base):
        path = base / 'commands'
        return [args for line in path.read_text().splitlines()
                if (args := json.loads(line))[0] in ('load-module','unload-module')] if path.exists() else []

    def test_current_fifo_publishes_real_source_and_only_unloads_owned_id(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); directory, pactl = self.fixture(base); owned = self.activation(directory, A)
            endpoint = module.Endpoint(directory, {}, pactl)
            endpoint.tick(); self.assertEqual(self.commands(base), [], 'off session loaded source')
            self.request(directory); endpoint.tick(); endpoint.tick()
            self.assertEqual(self.commands(base), [[
                'load-module', 'module-pipe-source', 'file=' + str(owned/'input.pcm'),
                'source_name=loopy_android_microphone', 'format=s16le', 'rate=48000',
                'channels=1', 'channel_map=mono']])
            state = json.loads((directory/'microphone-state.json').read_text())
            self.assertEqual(state, {'session': TOKEN, 'activation': A, 'state': 'armed', 'epoch': 0})
            self.assertEqual(stat.S_IMODE((directory/'microphone-state.json').stat().st_mode), 0o600)
            self.request(directory, 'stop'); endpoint.tick(); endpoint.close()
            self.assertEqual(self.commands(base)[1:], [['unload-module', '40']])
            self.assertEqual(json.loads((directory/'microphone-state.json').read_text())['state'], 'off')
            self.assertTrue((owned/'input.pcm').is_fifo(), 'guest removed Android-owned FIFO')

    def test_stale_stop_cannot_unload_successor_activation(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); directory, pactl = self.fixture(base)
            self.activation(directory, A); self.activation(directory, B)
            endpoint = module.Endpoint(directory, {}, pactl)
            self.request(directory); endpoint.tick(); self.request(directory, activation=B); endpoint.tick()
            self.request(directory, 'stop', A); endpoint.tick()
            self.assertEqual(self.commands(base)[1], ['unload-module', '40'])
            self.assertEqual(len(self.commands(base)), 3, 'stale stop unloaded successor')
            self.assertEqual(json.loads((directory/'microphone-state.json').read_text())['activation'], B)
            endpoint.close(); self.assertEqual(self.commands(base)[-1], ['unload-module', '41'])

    def test_stale_token_malformed_or_public_request_cannot_spawn_source(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); directory, pactl = self.fixture(base); self.activation(directory, A)
            endpoint = module.Endpoint(directory, {}, pactl)
            for action, activation, token in [('start', A, 'old'), ('exec', A, TOKEN),
                                              ('start', '../outside', TOKEN), ('start', A, TOKEN+'\n')]:
                self.request(directory, action, activation, token); endpoint.tick()
            self.request(directory); (directory/'microphone-request.json').chmod(0o644); endpoint.tick()
            self.assertEqual(self.commands(base), [])

    def test_running_unmuted_consumer_gates_epoch_and_idle_or_mute_rearms(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);directory,pactl=self.fixture(base);self.activation(directory,A)
            endpoint=module.Endpoint(directory,{},pactl);endpoint.refresh_seconds=0
            self.request(directory);endpoint.tick()
            def state():return json.loads((directory/'microphone-state.json').read_text())
            self.assertEqual((state()['state'],state().get('epoch')),('armed',0))
            (base/'source-state').write_text('RUNNING');endpoint.tick()
            self.assertEqual((state()['state'],state()['epoch']),('running',1))
            (base/'muted').write_text('');endpoint.tick()
            self.assertEqual((state()['state'],state()['epoch']),('armed',1))
            (base/'muted').unlink();endpoint.tick()
            self.assertEqual((state()['state'],state()['epoch']),('running',2))
            (base/'source-state').write_text('IDLE');endpoint.tick()
            self.assertEqual((state()['state'],state()['epoch']),('armed',2))
            endpoint.close()

    def test_failed_unload_retains_identity_and_never_acknowledges_off_before_retry(self):
        module=self.load()
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);directory,pactl=self.fixture(base);self.activation(directory,A)
            endpoint=module.Endpoint(directory,{},pactl);self.request(directory);endpoint.tick()
            (base/'fail-unload').write_text('');self.request(directory,'stop');endpoint.tick()
            self.assertNotEqual(json.loads((directory/'microphone-state.json').read_text())['state'],'off')
            before=len(self.commands(base))
            (base/'fail-unload').unlink();endpoint.tick()
            self.assertEqual(len(self.commands(base)),before+1,'lost owned module identity before retry')
            self.assertEqual(self.commands(base)[-1],['unload-module','40'])
            self.assertEqual(json.loads((directory/'microphone-state.json').read_text())['state'],'off')
            endpoint.close()
            endpoint.close()

    def test_redirected_fifo_and_request_cannot_escape_private_directory(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); directory, pactl = self.fixture(base); owned = self.activation(directory, A)
            outside = base/'keep'; outside.write_text('preserved')
            (owned/'input.pcm').unlink(); (owned/'input.pcm').symlink_to(outside)
            endpoint = module.Endpoint(directory, {}, pactl); self.request(directory); endpoint.tick()
            (directory/'microphone-request.json').unlink(); (directory/'microphone-request.json').symlink_to(outside)
            endpoint.tick(); self.assertEqual(self.commands(base), []); self.assertEqual(outside.read_text(), 'preserved')
            endpoint.close()

    def test_timeout_is_bounded_and_does_not_publish_ready(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); directory, pactl = self.fixture(base); self.activation(directory, A)
            endpoint = module.Endpoint(directory, {}, pactl, timeout=.1)
            (base/'stall').write_text(''); self.request(directory)
            start = time.monotonic(); endpoint.tick()
            self.assertLess(time.monotonic()-start, .8)
            self.assertEqual(json.loads((directory/'microphone-state.json').read_text())['state'], 'unavailable')
            endpoint.close()

    def test_redirected_or_public_session_rejected_before_commands(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); directory, pactl = self.fixture(base)
            directory.chmod(0o755)
            with self.assertRaises((OSError, ValueError)): module.Endpoint(directory, {}, pactl)
            directory.chmod(0o700); session = directory/'session'; session.unlink()
            outside=base/'keep';outside.write_text(TOKEN+'\n');outside.chmod(0o600);session.symlink_to(outside)
            with self.assertRaises((OSError, ValueError)): module.Endpoint(directory, {}, pactl)
            self.assertEqual(self.commands(base), [])


if __name__ == '__main__': unittest.main()
