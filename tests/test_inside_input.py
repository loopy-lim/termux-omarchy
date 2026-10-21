"""Real pure input/geometry state; public literals only, no GTK or device."""
import types,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'android/assets/omarchy-bridge/inside_input.py'
def load():
 if not P.exists():return None
 m=types.ModuleType('inside_input_test');exec(compile(P.read_bytes(),str(P),'exec'),m.__dict__);return m
class InputTests(unittest.TestCase):
 def code(self):m=load();self.assertIsNotNone(m,'internal input state missing');return m
 def test_letterbox_current_resize_and_outside_drag_clamp(self):
  m=self.code();self.assertEqual(m.map_point(500,120,1000,240,320,240),(160,120))
  self.assertIsNone(m.map_point(100,120,1000,240,320,240))
  self.assertEqual(m.map_point(-50,1000,1000,240,320,240,True),(0,239))
  self.assertEqual(m.map_point(320,240,640,480,320,240),(160,120))
  with self.assertRaises(ValueError):m.map_point(float('nan'),1,10,10,2,2)
 def test_pair_and_base_triple_coords_are_strict_and_failure_has_no_position(self):
  m=self.code();self.assertEqual(m.coords((1.5,2.5)),(1.5,2.5));self.assertEqual(m.coords((True,1.5,2.5)),(1.5,2.5))
  self.assertIsNone(m.coords((False,0.0,0.0)))
  for v in (None,(1,2,3),(True,True,1),(float('inf'),1)):
   with self.subTest(type=type(v).__name__),self.assertRaises(ValueError):m.coords(v)
 def test_button_down_up_balances_and_outside_release_clamps(self):
  m=self.code();s=m.InputState([30]);s.focused=True
  self.assertEqual(s.button(1,True,160,120,320,240,320,240),dict(action='POINTER_BUTTON',x=160,y=120,code=1,pressed=True))
  self.assertIsNone(s.button(1,True,160,120,320,240,320,240))
  self.assertEqual(s.button(1,False,-5,400,320,240,320,240),dict(action='POINTER_BUTTON',x=0,y=239,code=1,pressed=False))
  self.assertIsNone(s.button(1,False,10,10,320,240,320,240))
 def test_key_hardware_offset_capability_and_repeat_are_balanced(self):
  m=self.code();s=m.InputState([30]);s.focused=True
  self.assertIsNone(s.key(31+8,True))
  self.assertEqual(s.key(30+8,True),dict(action='KEY',code=30,pressed=True))
  self.assertEqual(s.key(30+8,True),dict(action='KEY_REPEAT',code=30,pressed=True))
  self.assertEqual(s.key(30+8,False),dict(action='KEY',code=30,pressed=False))
  self.assertIsNone(s.key(30+8,False))
 def test_focus_loss_retires_all_and_never_replays_held_input(self):
  m=self.code();s=m.InputState([30]);s.focused=True;s.key(38,True);s.button(1,True,1,1,2,2,2,2)
  self.assertEqual(s.retire(),dict(action='RELEASE_ALL'))
  self.assertFalse(s.focused);self.assertIsNone(s.key(38,False));self.assertIsNone(s.move(1,1,2,2,2,2))
  s.focused=True;self.assertIsNone(s.key(38,False))
 def test_input_geometry_requires_the_actual_displayed_frame_epoch(self):
  m=self.code();g=dict(epoch=2,width=3,height=2,density=160)
  self.assertFalse(m.display_matches(None,g))
  self.assertFalse(m.display_matches({**g,'epoch':1},g))
  self.assertFalse(m.display_matches({**g,'width':2},g))
  self.assertTrue(m.display_matches(dict(g),g))
 def test_smooth_scroll_fraction_has_bounded_signed_detents(self):
  m=self.code();s=m.InputState([]);s.focused=True
  self.assertEqual(s.scroll(.25,-.5,1,1,2,2,2,2),dict(action='SCROLL',x=1,y=1,scroll_x=30,scroll_y=-60))
  self.assertIsNone(s.scroll(0,0,1,1,2,2,2,2))
  with self.assertRaises(ValueError):s.scroll(1001,0,1,1,2,2,2,2)
if __name__=='__main__':unittest.main()
