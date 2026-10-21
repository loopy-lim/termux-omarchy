"""Canonical GI scroll normalization and AST-extracted real View.event, no GTK/device."""
import ast
import enum
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'android/assets/omarchy-bridge/inside_input.py'
WINDOW = ROOT / 'android/assets/omarchy-bridge/inside_window.py'


def load_input():
    module = types.ModuleType('inside_scroll_input')
    exec(compile(INPUT.read_bytes(), str(INPUT), 'exec'), module.__dict__)
    return module


class Direction(enum.IntEnum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3
    SMOOTH = 4


class ScrollTests(unittest.TestCase):
    def normalizer(self):
        module = load_input()
        self.assertTrue(hasattr(module, 'scroll_delta'), 'GI scroll normalizer missing')
        return module.scroll_delta

    def test_actual_gtk_smooth_false_up_and_true_delta_are_not_a_discrete_failure(self):
        normalize = self.normalizer()
        self.assertEqual(normalize((False, Direction.UP), (True, .25, -.5)), (.25, -.5))
        self.assertEqual(normalize((False, Direction.UP), (True, 0., 0.)), (0., 0.))
        self.assertEqual(normalize((True, Direction.DOWN), (True, .25, -.5)), (.25, -.5))

    def test_discrete_enum_and_integer_values_are_four_exact_directions(self):
        normalize = self.normalizer()
        for direction, expected in ((Direction.UP, (0, -1)), (Direction.DOWN, (0, 1)),
                                    (Direction.LEFT, (-1, 0)), (Direction.RIGHT, (1, 0))):
            self.assertEqual(normalize((True, direction), (False, 0., 0.)), expected)
            self.assertEqual(normalize((True, int(direction)), (False, 0., 0.)), expected)

    def test_valid_non_scroll_never_maps_failed_up_to_scroll(self):
        normalize = self.normalizer()
        self.assertIsNone(normalize((False, Direction.UP), (False, 0., 0.)))
        with self.assertRaises(ValueError): normalize((True, Direction.SMOOTH), (False, 0., 0.))

    def test_invalid_gi_shapes_boolean_values_and_unknown_enums_fail_closed(self):
        normalize = self.normalizer()
        for direction in (None, (0, 0), (True,), (True, 0, 1), (True, True),
                          (True, 0.0), (False, 99), (True, -1)):
            with self.subTest(direction=direction), self.assertRaises(ValueError):
                normalize(direction, (False, 0., 0.))
        for deltas in (None, (True, 0), (1, 0., 0.), (True, True, 0.),
                       (True, 0., False), (True, 0., '1'), (True, 0., 1., 2.)):
            with self.subTest(deltas=deltas), self.assertRaises(ValueError):
                normalize((False, Direction.UP), deltas)

    def test_nonfinite_and_large_distance_refused_with_finite_boundary_supported(self):
        normalize = self.normalizer()
        for deltas in ((True, float('nan'), 0), (True, 0, float('inf')),
                       (True, -1000.01, 0), (True, 0, 1001), (False, float('nan'), 0)):
            with self.subTest(deltas=deltas), self.assertRaises(ValueError):
                normalize((False, Direction.UP), deltas)
        self.assertEqual(normalize((False, Direction.UP), (True, -1000., 1000.)), (-1000., 1000.))

    def test_real_canonical_event_method_emits_smooth_scroll_and_keeps_owned_guards(self):
        inputs = load_input()
        tree = ast.parse(WINDOW.read_bytes(), str(WINDOW))
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'event']
        self.assertEqual(len(methods), 1)
        checked = []; sent = []
        namespace = dict(inputs=inputs, Gdk=types.SimpleNamespace(ScrollDirection=Direction),
                         wire=types.SimpleNamespace(check_peer=lambda sock, identity: checked.append((sock, identity))))
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(WINDOW), 'exec'), namespace)
        state = inputs.InputState([]); state.focused = True
        geometry = dict(epoch=1, width=2, height=2, density=160)
        session = types.SimpleNamespace(input=state, geometry=geometry, send_input=sent.append)
        view = types.SimpleNamespace(session=session, image_geometry=dict(geometry), sock='owned', identity='same',
            area=types.SimpleNamespace(get_allocation=lambda: types.SimpleNamespace(width=2, height=2)),
            flush=lambda: None, unavailable=lambda: self.fail('valid smooth event became unavailable'))
        event = types.SimpleNamespace(get_coords=lambda: (True, 1., 1.),
            get_scroll_direction=lambda: (False, Direction.UP), get_scroll_deltas=lambda: (True, .25, -.5))
        self.assertTrue(namespace['event'](view, 'scroll', event))
        self.assertEqual(sent, [dict(action='SCROLL', x=1, y=1, scroll_x=30, scroll_y=-60)])
        self.assertEqual(checked, [('owned', 'same')])
        state.focused = False
        self.assertFalse(namespace['event'](view, 'scroll', event))
        self.assertEqual(len(sent), 1)
        state.focused = True; view.image_geometry['epoch'] = 0
        self.assertFalse(namespace['event'](view, 'scroll', event))
        self.assertEqual(len(sent), 1)


if __name__ == '__main__': unittest.main()
