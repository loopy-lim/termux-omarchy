"""Pure timing and public probe-identity contracts; no GUI or device access."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'tools/probe_termux_input_latency_common.py'
IDENTITY = dict(nonce='a' * 32, session='12345678-1234-4234-8234-123456789abc',
                uid=10323, pid=4201, birth=81123, sid=4201)


class LatencyTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'bounded timing collector is not implemented')
        spec = importlib.util.spec_from_file_location('probe_latency_test', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def ready(self, backend='x11-xsync'):
        return dict(type='READY', schema=1, **IDENTITY, backend=backend,
                    width=640, height=420, window=42 if backend == 'x11-xsync' else None)

    def collector(self, backend='x11-xsync'):
        obj = self.m.Collector(IDENTITY)
        obj.receive(self.ready(backend))
        return obj

    def event(self, seq, arrival, source, kind='key_down'):
        return dict(type='EVENT', id=seq, kind=kind, arrival_ns=arrival, source_ms=source)

    def test_nearest_rank_quantiles_use_real_samples_and_empty_is_unknown(self):
        self.assertEqual(self.m.stats([]), dict(count=0, p50_ms=None, p95_ms=None, max_ms=None))
        result = self.m.stats([float(n) for n in range(1, 21)])
        self.assertEqual(result, dict(count=20, p50_ms=10.0, p95_ms=19.0, max_ms=20.0))
        with self.assertRaises(ValueError): self.m.stats([float('nan')])
        with self.assertRaises(ValueError): self.m.stats([-1])

    def test_crossed_nonce_session_pid_birth_uid_and_sid_are_refused(self):
        for key, changed in [('nonce', 'b' * 32), ('session', '12345678-1234-4234-8234-123456789abd'),
                             ('pid', 4202), ('birth', 81124), ('uid', 10324), ('sid', 4202)]:
            with self.subTest(key=key):
                obj = self.m.Collector(IDENTITY)
                with self.assertRaises(ValueError): obj.receive(dict(self.ready(), **{key: changed}))
        with self.assertRaises(ValueError): self.m.Collector(dict(IDENTITY, nonce='../unsafe'))
        with self.assertRaises(ValueError): self.m.Collector(dict(IDENTITY, birth=True))

    def test_no_private_fields_or_unknown_event_types_are_admitted(self):
        for extra in ({'key': 'private-character'}, {'x': 120}, {'title': 'private-window'}):
            with self.subTest(extra=tuple(extra)):
                obj = self.collector()
                with self.assertRaises(ValueError): obj.receive(dict(self.event(1, 1_000_000, 10), **extra))
        obj = self.collector()
        with self.assertRaises(ValueError): obj.receive(self.event(1, 1_000_000, 10, 'private-key'))
        with self.assertRaises(ValueError): obj.receive(dict(type='ERROR', message='private exception'))

    def test_event_gaps_uint32_wrap_and_callback_delays_are_separate(self):
        obj = self.collector()
        obj.receive(self.event(1, 1_000_000_000, 0xfffffff8))
        obj.receive(dict(type='PAINT', ids=[1], complete_ns=1_004_000_000))
        obj.receive(self.event(2, 1_020_000_000, 12))
        obj.receive(dict(type='PAINT', ids=[2], complete_ns=1_026_000_000))
        obj.receive(dict(type='DONE', reason='deadline', window_destroyed=True))
        report = obj.result()
        self.assertEqual(report['kinds']['key_down']['arrival_gap_ms']['p50_ms'], 20.0)
        self.assertEqual(report['kinds']['key_down']['source_gap_ms']['p50_ms'], 20.0)
        self.assertEqual(report['kinds']['key_down']['event_to_callback_ms']['max_ms'], 6.0)
        self.assertEqual(report['callback_kind'], 'XSync-request-processed')
        self.assertFalse(report['physical_latency_measured'])
        self.assertFalse(report['physical_fps_measured'])

    def test_coalesced_after_paint_is_counted_once_per_event_and_missing_stays_unknown(self):
        obj = self.collector('wayland-after-paint')
        obj.receive(self.event(1, 1_000_000_000, 10, 'motion'))
        obj.receive(self.event(2, 1_001_000_000, 11, 'motion'))
        obj.receive(dict(type='PAINT', ids=[1, 2], complete_ns=1_008_000_000))
        obj.receive(self.event(3, 1_020_000_000, 30, 'motion'))
        obj.receive(dict(type='DONE', reason='own-close', window_destroyed=True))
        result = obj.result()
        self.assertEqual(result['paint_callbacks'], 1)
        self.assertEqual(result['unpainted_events'], 1)
        self.assertEqual(result['kinds']['motion']['event_to_callback_ms']['count'], 2)
        self.assertEqual(result['callback_kind'], 'GdkFrameClock-after-paint')

    def test_duplicate_sequence_unknown_paint_and_clock_regression_fail_closed(self):
        rows = [self.event(3, 1_000_000_000, 10),
                dict(type='PAINT', ids=[1], complete_ns=1_000_000_000)]
        for row in rows:
            with self.subTest(row=row['type']):
                obj = self.collector()
                with self.assertRaises(ValueError): obj.receive(row)
        obj = self.collector(); obj.receive(self.event(1, 1_000_000_000, 10))
        with self.assertRaises(ValueError): obj.receive(self.event(2, 999_000_000, 11))
        with self.assertRaises(ValueError): obj.receive(dict(type='PAINT', ids=[1], complete_ns=999_000_000))
        obj.receive(dict(type='PAINT', ids=[1], complete_ns=1_001_000_000))
        with self.assertRaises(ValueError): obj.receive(dict(type='PAINT', ids=[1], complete_ns=1_002_000_000))

    def test_incomplete_lifetime_cannot_be_reported_as_clean(self):
        obj = self.collector()
        with self.assertRaises(ValueError): obj.result()
        obj.receive(dict(type='DONE', reason='deadline', window_destroyed=False))
        self.assertFalse(obj.result()['window_destroyed'])
        with self.assertRaises(ValueError): obj.receive(self.event(1, 1_000_000, 1))

    def test_own_birth_check_tolerates_changed_cpu_fields_but_refuses_reused_identity(self):
        def proc(cpu, birth):
            words = ['S'] + ['0'] * 18 + [str(birth)] + ['0'] * 8
            words[11] = str(cpu)
            return ('4201 (public fixture) ' + ' '.join(words) + '\n').encode()
        with mock.patch.object(self.m.os, 'getpid', return_value=4201), \
             mock.patch.object(self.m.os, 'getsid', return_value=4201), \
             mock.patch.object(self.m.Path, 'read_bytes', side_effect=[proc(1, 81123), b'Uid:\t10323\t10323\t10323\t10323\n', proc(2, 81123)]):
            try: actual = self.m.own_identity(IDENTITY['nonce'], IDENTITY['session'])
            except ValueError: self.fail('stable PID/birth was rejected when CPU fields changed')
            self.assertEqual(actual, IDENTITY)
        with mock.patch.object(self.m.os, 'getpid', return_value=4201), \
             mock.patch.object(self.m.os, 'getsid', return_value=4201), \
             mock.patch.object(self.m.Path, 'read_bytes', side_effect=[proc(1, 81123), b'Uid:\t10323\t10323\t10323\t10323\n', proc(2, 81124)]):
            with self.assertRaises(ValueError): self.m.own_identity(IDENTITY['nonce'], IDENTITY['session'])


if __name__ == '__main__': unittest.main()
