"""A new frame-callback diagnostic keeps the original timing parser boundaries."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WaylandFrameTiming(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        self.addCleanup(sys.path.remove, str(ROOT / 'tools'))
        source = ROOT / 'tools/probe_termux_input_latency_frame.py'
        if not source.exists(): source = ROOT / 'tools/probe_termux_input_latency_common.py'
        spec = importlib.util.spec_from_file_location('frame_tested', source)
        self.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.m)
        self.identity = dict(nonce='a'*32, session='11111111-2222-4333-8444-555555555555',
                             uid=10323, pid=123, birth=456, sid=123)
        self.ready = dict(type='READY', schema=1, backend='wayland-frame-callback', width=640,
                          height=420, window=None, **self.identity)

    def test_native_frame_done_is_accepted_and_honestly_named(self):
        obj = self.m.Collector(self.identity)
        try: obj.receive(self.ready)
        except ValueError: self.fail('native wl_surface.frame callback transport was rejected')
        obj.receive(dict(type='EVENT', id=1, kind='key_down', arrival_ns=1000000, source_ms=20))
        obj.receive(dict(type='PAINT', ids=[1], complete_ns=6000000))
        obj.receive(dict(type='DONE', reason='deadline', window_destroyed=True))
        result = obj.result()
        self.assertEqual(result['backend'], 'wayland-frame-callback')
        self.assertEqual(result['callback_kind'], 'wl_surface.frame-done')
        self.assertEqual(result['kinds']['key_down']['event_to_callback_ms']['p50_ms'], 5)
        self.assertFalse(result['physical_latency_measured'])
        self.assertFalse(result['physical_fps_measured'])

    def test_unexpected_input_content_and_wrong_identity_remain_refused(self):
        for update in ({'nonce':'b'*32}, {'text':'private'}, {'window':10}):
            with self.subTest(update=list(update)):
                with self.assertRaises(ValueError):
                    self.m.Collector(self.identity).receive(dict(self.ready, **update))


if __name__ == '__main__': unittest.main()
