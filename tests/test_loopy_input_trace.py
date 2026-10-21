"""Type-only input diagnostics from actual public input and independent Unix peer."""
import json
import os
import unittest
from unittest.mock import patch
import test_loopy_ime as fixture


class InputTraceTests(unittest.TestCase):
    def setUp(self):
        self.harness = fixture.LoopyImeTests('test_long_unicode_is_atomic_and_scalar_bounded_without_key_per_character')
        self.harness.setUp(); self.helper = self.harness.helper
        self.path = self.harness.directory / ('input-trace-' + fixture.TOKEN + '.json')

    def tearDown(self): self.harness.tearDown()

    def trace(self):
        self.assertTrue(self.path.is_file(), 'completed job has no bounded backend diagnostic')
        data = self.path.read_bytes(); self.assertLessEqual(len(data), 16384)
        value = json.loads(data); self.assertEqual(value['schema'], 1)
        self.assertEqual(value['token'], fixture.TOKEN)
        return value

    def test_atomic_trace_contains_serials_and_counts_without_typed_contents(self):
        peer = self.harness.start(); self.helper.inject('sensitive한😀')
        value = self.trace(); record = value['jobs'][-1]
        self.assertEqual((record['backend'], record['reason'], record['result']), ('atomic', 'active', 'ok'))
        self.assertEqual((record['utf8_bytes'], record['codepoints']), (16, 11))
        self.assertEqual(record['counts']['im_text'], 1); self.assertEqual(record['counts'].get('vk_pairs', 0), 0)
        self.assertTrue(record['final']['active']); self.assertFalse(record['wire_closed'])
        self.assertNotIn('sensitive', self.path.read_text()); self.assertNotIn('😀', self.path.read_text())
        self.assertEqual(peer.text, 'sensitive한😀'); self.assertEqual(self.path.stat().st_uid, os.getuid())

    def test_recent_job_history_keeps_sixteen_under_the_shared_file_budget(self):
        self.harness.start()
        for _ in range(20): self.helper.inject('한')
        value = self.trace(); self.assertEqual(len(value['jobs']), 16)
        self.assertEqual([job['sequence'] for job in value['jobs']], list(range(5, 21)))

    def test_failed_prefix_reports_transport_failure_without_replay(self):
        peer = self.harness.start(fault='disconnect')
        with self.assertRaises(OSError): self.helper.inject('private')
        record = self.trace()['jobs'][-1]
        # The disconnect can surface during recv or send. Both are OS transport
        # failures; keep the no-replay, closed-wire and content checks below.
        self.assertIn(record['result'], ('OSError', 'BrokenPipeError', 'ConnectionResetError'))
        self.assertTrue(record['wire_closed'])
        self.assertEqual(record['counts']['im_text'], 1); self.assertEqual(peer.commits, ['private'])
        self.assertNotIn('private', self.path.read_text())

    def test_queued_done_trace_distinguishes_latest_state_from_request_serial(self):
        peer = self.harness.start(fault='queued-context'); self.helper.inject('가' * 1365)
        record = self.trace()['jobs'][-1]
        requests = [event['serial'] for event in record['timeline'] if event['kind'] == 'im-text']
        self.assertEqual(requests, [1, 3]); self.assertEqual(record['counts']['im_text'], 2)
        self.assertEqual(record['counts']['im_done'], 4); self.assertEqual(peer.text, '가' * 1365)

    def test_diagnostic_write_failure_does_not_change_delivery_or_remove_foreign_target(self):
        self.path.mkdir(); peer = self.harness.start(); self.helper.inject('한')
        self.assertEqual(peer.text, '한'); self.assertTrue(self.path.is_dir())
        self.assertEqual(list(self.harness.directory.glob('input-trace-*.new')), [])

    def test_diagnostic_cleanup_denial_cannot_turn_delivered_input_into_failure(self):
        self.path.mkdir(); peer = self.harness.start()
        unlink = os.unlink
        def deny_trace(name, *args, **kwargs):
            if str(name).startswith(str(self.harness.directory / 'input-trace-')): raise PermissionError
            return unlink(name, *args, **kwargs)
        with patch.object(self.helper.loopy_input_trace.os, 'unlink', side_effect=deny_trace):
            try: self.helper.inject('한')
            except PermissionError: self.fail('diagnostic cleanup masked a successful input job')
        self.assertEqual(peer.text, '한'); self.assertTrue(self.path.is_dir())

    def test_many_control_operations_have_bounded_timeline_and_complete_counters(self):
        peer = self.harness.start(mode='foot'); self.helper.inject('a\n' * 200)
        record = self.trace()['jobs'][-1]
        self.assertLessEqual(len(record['timeline']), 16); self.assertGreater(record['timeline_omitted'], 0)
        self.assertEqual(record['counts']['im_text'], 200); self.assertEqual(record['counts']['vk_pairs'], 200)
        self.assertEqual(len(peer.commits), 200)


if __name__ == '__main__': unittest.main()
