"""Validate actual public registry wire traces without inspecting user input."""
import unittest
try:
    from tools import check_wayland_bindings as check
except ImportError:
    check = None


class WaylandBindingsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(check, 'Wayland binding evidence checker is missing')

    def test_captured_aquamarine_requests_above_parent_versions_are_reported(self):
        trace = '\n'.join([
            'wl_registry#2.global(1, "wl_compositor", 4)',
            ' -> wl_registry#2.bind(1, "wl_compositor", 6, new id [unknown]#4)',
            'wl_registry#2.global(3, "xdg_wm_base", 1)',
            ' -> wl_registry#2.bind(3, "xdg_wm_base", 6, new id [unknown]#6)',
            'wl_registry#2.global(5, "wl_seat", 5)',
            ' -> wl_registry#2.bind(5, "wl_seat", 9, new id [unknown]#7)'])
        result = check.validate(trace)
        self.assertFalse(result['valid'])
        self.assertEqual(len(result['violations']), 3)
        self.assertEqual(result['violations'][0]['advertised'], 4)

    def test_compatible_versions_pass_and_no_trace_can_never_pass(self):
        result = check.validate('wl_registry#2.global(1, "wl_compositor", 4)\n'
                                ' -> wl_registry#2.bind(1, "wl_compositor", 4, new id [unknown]#4)')
        self.assertTrue(result['valid'])
        self.assertFalse(check.validate('unrelated text')['valid'])

    def test_unadvertised_binding_cannot_reuse_another_registry_evidence(self):
        result = check.validate('wl_registry#2.global(1, "wl_compositor", 4)\n'
                                ' -> wl_registry#3.bind(1, "wl_compositor", 4, new id [unknown]#4)')
        self.assertFalse(result['valid'])


if __name__ == '__main__':
    unittest.main()
