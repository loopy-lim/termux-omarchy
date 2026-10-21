"""Android settings handoff: authentication, fixed actions and honest results."""
import importlib.util
import inspect
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
import uuid

REPO = Path(__file__).resolve().parents[1]


def load(test, name):
    path = REPO / 'termux' / (name + '.py')
    test.assertTrue(path.is_file(), 'Android settings handoff has not been implemented')
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


class AndroidSettingsTests(unittest.TestCase):
    def setUp(self):
        self.token, self.nonce = str(uuid.uuid4()), str(uuid.uuid4())
        self.key = bytes(range(32))

    def request(self, action='wifi'):
        return {'schema': 1, 'token': self.token, 'nonce': self.nonce, 'action': action}

    def test_signed_request_tampering_and_previous_session_are_rejected(self):
        module = load(self, 'omarchy_android_client')
        packet = module.encode(self.request(), self.key)
        self.assertEqual(module.decode(packet, self.key, self.token), self.request())
        for altered, key, token in ((packet.replace(b'"wifi"', b'"desktop"'), self.key, self.token),
                                    (packet, b'x' * 32, self.token),
                                    (packet, self.key, str(uuid.uuid4()))):
            with self.assertRaises(ValueError): module.decode(altered, key, token)

    def test_duplicate_fields_and_unbounded_packet_are_rejected(self):
        module = load(self, 'omarchy_android_client')
        packet = module.encode(self.request(), self.key)
        duplicate = packet.replace(b'"schema":1', b'"schema":1,"schema":1')
        for value in (duplicate, b'x' * 4097):
            with self.assertRaises(ValueError): module.decode(value, self.key, self.token)

    def test_video_urls_validate_without_desktop_display_fields(self):
        module = load(self, 'omarchy_android_client')
        value = module.video_fields('https://www.youtube.com/watch?v=aqz')
        self.assertEqual(value, {'url': 'https://www.youtube.com/watch?v=aqz'})
        self.assertIn('video', module.ACTIONS)
        for url in ('--start-fullscreen', 'file:///etc/passwd', 'javascript:alert(1)',
                    'https://user:password@example.com', 'http://example.com/' + 'x' * 2048, ''):
            with self.subTest(url=url[:40]), self.assertRaises(ValueError):
                module.video_fields(url)

    def test_video_request_carries_only_the_fixed_field_set(self):
        client = load(self, 'omarchy_android_client')
        served = load(self, 'omarchy_android')
        request = {'schema': 1, 'token': self.token, 'nonce': self.nonce, 'action': 'video',
                   'url': 'https://example.com/v'}
        self.assertEqual(set(request), {'schema', 'token', 'nonce', 'action', 'url'})
        with self.assertRaises(ValueError):
            served.handle(dict(request, action='video'), '/prefix', {}, lambda *a, **kw: None)

    def test_only_fixed_public_settings_actions_can_reach_android(self):
        module = load(self, 'omarchy_android')
        for action in ('shell', 'grant', 'wifi;id', 'package', '', 1):
            calls = []
            with self.assertRaises(ValueError):
                module.handle(self.request(action), '/prefix', {}, lambda *a, **kw: calls.append(a))
            self.assertEqual(calls, [], 'invalid action reached an Android process')

    def test_wifi_success_reports_acceptance_without_claiming_foreground_switch(self):
        module = load(self, 'omarchy_android')
        def run(args, **kwargs):
            self.assertEqual(args, ['/prefix/bin/am', 'start', '-a', 'android.settings.panel.action.WIFI'])
            self.assertLessEqual(kwargs['timeout'], 8)
            return 'Starting: Intent { act=android.settings.WIFI_SETTINGS }\n'
        reply = module.handle(self.request(), '/prefix', {}, run)
        self.assertEqual(reply, dict(self.request(), status='accepted', reason='android-launch-requested'))

    def test_service_arguments_match_the_actual_process_command_and_reject_other_sessions(self):
        module = load(self, 'omarchy_android')
        self.assertTrue(callable(getattr(module,'service_arguments',None)),'service argument validation is missing')
        args=['_serve',self.token,':20','1234','4567']
        self.assertEqual(module.service_arguments(args),(self.token,':20',1234,'4567'))
        for bad in (args+['ignored'],args[:-1],['_serve',self.token,':0','1234','4567'],
                    ['_serve',self.token,':20','1','4567'],['_serve',self.token,':20','1234','-1']):
            with self.assertRaises(ValueError): module.service_arguments(bad)

    def test_zero_exit_android_error_and_unknown_output_are_not_success(self):
        module = load(self, 'omarchy_android')
        for output in ('Error: Activity not found\n', 'Starting: Intent {}\nError: SecurityException\n', '',
                       'Warning: Activity not started, its current task has been brought to the front\n'):
            result = module.handle(self.request(), '/prefix', {}, lambda *a, **kw: output)
            self.assertEqual(result['status'], 'unavailable')

    def test_failure_does_not_leak_child_output_and_ping_never_starts_activity(self):
        module = load(self, 'omarchy_android')
        def fail(*args, **kwargs): raise ValueError('private account path')
        result = module.handle(self.request(), '/prefix', {}, fail)
        self.assertEqual(result['reason'], 'android-launch-unavailable')
        ping = module.handle(self.request('ping'), '/prefix', {}, fail)
        self.assertEqual(ping['status'], 'ready')
        self.assertNotIn('private', json.dumps(result))

    def test_request_with_extra_arguments_is_rejected_before_any_launch(self):
        module = load(self, 'omarchy_android')
        with self.assertRaises(ValueError):
            module.handle(dict(self.request(), argv=['sh', '-c', 'id']), '/prefix', {}, lambda *a, **kw: '')

    def test_client_rejects_signed_reply_to_another_request(self):
        module = load(self, 'omarchy_android_client')
        wrong = dict(self.request(), nonce=str(uuid.uuid4()), status='accepted', reason='android-launch-requested')
        with self.assertRaises(ValueError): module.validate_reply(wrong, self.request())

    def test_socket_frames_have_a_deadline_and_a_strict_size_bound(self):
        module = load(self, 'omarchy_android_client')
        for data in (b'x' * 4097, b''):
            left, right = socket.socketpair()
            try:
                right.sendall(data); right.shutdown(socket.SHUT_WR)
                with self.assertRaises(ValueError): module.receive(left)
            finally: left.close(); right.close()

    def test_incomplete_frame_expires_without_waiting_for_peer_to_close(self):
        module = load(self, 'omarchy_android_client')
        import inspect
        self.assertIn('timeout',inspect.signature(module.receive).parameters,'frame has no absolute deadline')
        left,right=socket.socketpair()
        try:
            right.sendall(b'{')
            with self.assertRaises(TimeoutError): module.receive(left,timeout=.03)
        finally:left.close();right.close()

    def test_recent_duplicate_nonce_is_rejected_but_service_does_not_exhaust_after_normal_use(self):
        module = load(self, 'omarchy_android')
        self.assertTrue(callable(getattr(module,'Nonces',None)),'bounded deduplication is missing')
        window=module.Nonces()
        window.accept(self.nonce)
        with self.assertRaises(ValueError):window.accept(self.nonce)
        for _ in range(5000):window.accept(str(uuid.uuid4()))
        with self.assertRaises(ValueError):window.accept(window.values[-1])
        self.assertLessEqual(len(window.values),4096)

    def test_existing_android_directory_is_preserved_including_symlink_target(self):
        module = load(self, 'omarchy_android')
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            short = Path(temp) / 'lr';short.mkdir(mode=0o700)
            item=short.stat();value={'schema':1,'token':self.token,'uid':os.getuid(),
                                    'root':[1,2,os.getuid()],'runtime':[item.st_dev,item.st_ino,item.st_uid]}
            (short/'owner.json').write_text(json.dumps(value));(short/'owner.json').chmod(0o600)
            foreign=Path(temp)/'foreign';foreign.mkdir();(foreign/'cookie').write_bytes(b'preserve')
            (short/'android').symlink_to(foreign)
            runtime=SimpleNamespace(short=short,root=Path(temp),prefix=Path(temp)/'usr')
            with self.assertRaises(ValueError): module.prepare(runtime,value)
            self.assertEqual((foreign/'cookie').read_bytes(),b'preserve')

    def test_client_refuses_public_cookie_and_does_not_open_socket(self):
        module = load(self, 'omarchy_android_client')
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);(base/'cookie').write_bytes(self.key);(base/'cookie').chmod(0o644)
            (base/'lease.json').write_text(json.dumps({'schema':1,'token':self.token,'uid':os.getuid(),'serverPid':os.getpid()}))
            (base/'lease.json').chmod(0o600)
            with self.assertRaises(ValueError): module.call('wifi',base)

    def test_video_freeze_lease_replaces_stale_and_refuses_live_owner(self):
        module = load(self, 'omarchy_android')
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            short = Path(temp) / 'lr'; short.mkdir(mode=0o700)
            video = module.VideoDirect('/prefix', self.token, {'pid': os.getpid()}, short)
            with patch.object(video, 'running', return_value=False):
                video.freeze()
                self.assertTrue(video.lease_active())
                self.assertEqual((short / video.LEASE).stat().st_mode & 0o777, 0o600)
                before = (short / video.LEASE).stat().st_ino
                video.freeze()  # A lease without a live playback owner cannot be ours.
                self.assertNotEqual((short / video.LEASE).stat().st_ino, before)
            with patch.object(video, 'running', return_value=True):
                with self.assertRaises(ValueError): video.freeze()
            self.assertTrue(video.lease_active())
            video.thaw()
            self.assertFalse(video.lease_active())
            video.thaw()  # Idempotent.

    def test_video_freeze_lease_survives_only_a_live_service_and_is_secretive(self):
        module = load(self, 'omarchy_android')
        with tempfile.TemporaryDirectory() as temp:
            short = Path(temp) / 'lr'; short.mkdir(mode=0o700)
            video = module.VideoDirect('/prefix', self.token, {'pid': os.getpid()}, short)
            self.assertEqual(video.lease_path().parent, short)
            self.assertEqual(video.LEASE, 'video-direct.lease')
            # The lease is an existence signal only: no contents to leak, owner-checked mode.
            source = inspect.getsource(module.VideoDirect.freeze)
            self.assertIn('O_NOFOLLOW', source)
            self.assertIn('O_EXCL', source)

    def test_graphical_status_survives_unavailable_android_settings_service(self):
        module=load(self,'omarchy_runtime')
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            home,prefix=Path(temp)/'home',Path(temp)/'usr';home.mkdir();prefix.mkdir()
            runtime=module.Runtime(home,prefix)
            value={'schema':1,'token':self.token,'phase':'ready','display':':20',
                   'processes':[{'pid':i} for i in range(2,6)],'hyprland':{'pid':6}}
            runtime.state=lambda:value;runtime.x_ready=lambda display:True;runtime.hypr_ready=lambda rows:rows[0]
            with patch.object(module,'identity',return_value={'pid':6}),patch.object(module,'same_identity',return_value=True), \
                    patch.object(module,'live_peer',return_value=True),patch.object(module,'audio_ready',return_value=True):
                result=runtime.status(str(uuid.uuid4()))
            self.assertEqual(result['status'],'ready')
            self.assertFalse(result.get('androidSettingsReady','missing'), 'unavailable bridge is not reported')


if __name__ == '__main__': unittest.main()
