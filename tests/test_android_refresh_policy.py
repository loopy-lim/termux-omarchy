import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('refresh_policy', Path(__file__).resolve().parents[1] / 'tools/android_refresh_policy.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RefreshPolicyTests(unittest.TestCase):
    def setUp(self):
        self.state = {'min_refresh_rate': '120.0', 'peak_refresh_rate': '120.0'}
        self.writes = []

    def shell(self, args):
        self.assertEqual(args[:3], ['settings', '--user', '10'])
        action, namespace, key = args[3:6]
        self.assertEqual(namespace, 'system')
        if action == 'get':
            return self.state[key]
        self.writes.append(args)
        self.state[key] = 'null' if action == 'delete' else args[6]
        return ''

    def test_release_and_restore_preserve_peak_and_exact_previous_value(self):
        before = dict(self.state)
        self.assertEqual(m.release_minimum(self.shell, 10, before)['min_refresh_rate'], 'null')
        self.assertEqual(m.restore_minimum(self.shell, 10, before), before)
        self.assertEqual([x[5] for x in self.writes], ['min_refresh_rate'] * 2)
        m.restore_minimum(self.shell, 10, before)
        self.assertEqual(len(self.writes), 2)

    def test_changed_user_settings_are_not_overwritten(self):
        before = dict(self.state)
        self.state['min_refresh_rate'] = '90.0'
        with self.assertRaisesRegex(ValueError, 'changed'):
            m.release_minimum(self.shell, 10, before)
        with self.assertRaisesRegex(ValueError, 'changed'):
            m.restore_minimum(self.shell, 10, before)
        self.assertEqual(self.writes, [])

    def test_other_peak_after_release_blocks_restore(self):
        before = dict(self.state)
        m.release_minimum(self.shell, 10, before)
        self.state['peak_refresh_rate'] = '144.0'
        with self.assertRaisesRegex(ValueError, 'changed'):
            m.restore_minimum(self.shell, 10, before)
        self.assertEqual(len(self.writes), 1)

    def test_silent_rejected_device_write_is_not_success(self):
        before = dict(self.state)
        def denied(args):
            if args[3] == 'delete':
                return ''
            return self.shell(args)
        with self.assertRaisesRegex(ValueError, 'unconfirmed'):
            m.release_minimum(denied, 10, before)


if __name__ == '__main__':
    unittest.main()
