"""Execute the real Omarchy helpers, upstream bindings, and personal Lua profile.

Only Hyprland's native registration, dispatcher, and timer boundaries are stubbed.
This verifies the Linux Alt+arrow output of KeyBridge's Caps+Alt fallback; Android
delivery, physical keys, and application caret behavior need separate validation.
"""
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
LUA = shutil.which('lua')
UPSTREAM = ROOT / 'build/omarchy-sources/omarchy'
PROFILE = ROOT / 'termux/profile/bindings.lua'
REPLAY = r'''
local registered, sent, timers = {}, {}, {}
local function native_dispatcher()
  return setmetatable({}, {
    __index = function(t, key)
      local child = native_dispatcher()
      rawset(t, key, child)
      return child
    end,
    __call = function() return function() end end,
  })
end
hl = { dsp = native_dispatcher() }
hl.bind = function(keys, action, options)
  registered[#registered + 1] = { keys = keys, action = action, options = options }
end
hl.unbind = function(keys)
  for i = #registered, 1, -1 do
    if registered[i].keys == keys then table.remove(registered, i) end
  end
end
hl.dispatch = function(action)
  assert(type(action) == 'function', 'dispatcher must be callable')
  action()
end
hl.dsp.send_key_state = function(args)
  local fields = 0
  for key in pairs(args) do
    assert(key == 'mods' or key == 'key' or key == 'state', 'unexpected dispatcher field')
    fields = fields + 1
  end
  assert(fields == 3, 'send_key_state requires mods/key/state')
  assert(type(args.mods) == 'string' and type(args.key) == 'string', 'string fields required')
  assert(args.state == 'down' or args.state == 'up', 'invalid key state')
  return function()
    sent[#sent + 1] = { mods = args.mods, key = args.key, state = args.state }
  end
end
hl.timer = function(callback, options)
  assert(type(callback) == 'function', 'timer callback required')
  assert(options.timeout == 50 and options.type == 'oneshot', 'bounded 50ms release required')
  timers[#timers + 1] = callback
end
package.path = arg[1] .. '/?.lua;' .. package.path
dofile(arg[1] .. '/default/hypr/helpers.lua')
dofile(arg[1] .. '/default/hypr/bindings/tiling.lua')
local upstream = {}
for i, binding in ipairs(registered) do upstream[i] = binding end
dofile(arg[2])

-- Preserve every real upstream binding, including both Alt+Tab dispatchers and
-- SUPER+arrows used for Meta+Caps+HJKL focus. No Shift extension is requested.
for _, original in ipairs(upstream) do
  local count = 0
  for _, binding in ipairs(registered) do
    if binding == original then count = count + 1 end
  end
  assert(count == 1, 'upstream binding removed or duplicated: ' .. original.keys)
end
for _, key in ipairs({ 'ALT + TAB', 'ALT + SHIFT + TAB',
                      'SUPER + LEFT', 'SUPER + RIGHT', 'SUPER + UP', 'SUPER + DOWN' }) do
  local before, after = 0, 0
  for _, binding in ipairs(upstream) do if binding.keys == key then before = before + 1 end end
  for _, binding in ipairs(registered) do if binding.keys == key then after = after + 1 end end
  assert(before > 0 and after == before, 'unrelated shortcut overridden: ' .. key)
end
for _, direction in ipairs({ 'LEFT', 'RIGHT', 'UP', 'DOWN' }) do
  for _, binding in ipairs(registered) do
    assert(binding.keys ~= 'ALT + SHIFT + ' .. direction, 'unrequested Shift binding')
  end
end
if arg[3] == 'preserve' then
  assert(#sent == 0 and #timers == 0, 'profile loading dispatched input')
  print('PASS upstream Alt+Tab and Meta+Caps focus preserved; no Shift override')
  return
end

local matches = {}
for _, binding in ipairs(registered) do
  if binding.keys == 'ALT + ' .. arg[3] then matches[#matches + 1] = binding.action end
end
assert(#matches == 1, 'expected exactly one Alt+' .. arg[3] .. ' navigation action, got ' .. #matches)
assert(type(matches[1]) == 'function', 'navigation action must be a Lua callback')
matches[1]()
assert(#sent == 1 and #timers == 1, 'one key down and one deferred release required')
assert(sent[1].mods == arg[4] and sent[1].key == arg[5] and sent[1].state == 'down', 'wrong key down')
timers[1]()
assert(#sent == 2, 'exactly one key up required')
assert(sent[2].mods == arg[4] and sent[2].key == arg[5] and sent[2].state == 'up', 'wrong key up')
print('PASS exactly once Alt+' .. arg[3] .. ' -> ' .. arg[4] .. '+' .. arg[5] .. ' down/up')
'''


class CapsNavigationBindingsTests(unittest.TestCase):
    def replay(self, direction, mods='', key=''):
        self.assertIsNotNone(LUA, 'real Lua interpreter required')
        for source in ('helpers.lua', 'bindings/tiling.lua'):
            self.assertTrue((UPSTREAM / 'default/hypr' / source).is_file(),
                            'pinned real Omarchy source required')
        result = subprocess.run(
            [LUA, '-', str(UPSTREAM), str(PROFILE), direction, mods, key],
            input=REPLAY, text=True, capture_output=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS ', result.stdout)

    def test_alt_caps_h_linux_alt_left_sends_home_down_and_up(self):
        self.replay('LEFT', '', 'Home')

    def test_alt_caps_l_linux_alt_right_sends_end_down_and_up(self):
        self.replay('RIGHT', '', 'End')

    def test_alt_caps_k_linux_alt_up_sends_ctrl_home_down_and_up(self):
        self.replay('UP', 'CTRL', 'Home')

    def test_alt_caps_j_linux_alt_down_sends_ctrl_end_down_and_up(self):
        self.replay('DOWN', 'CTRL', 'End')

    def test_alt_tab_and_meta_caps_focus_stay_upstream_without_shift_extension(self):
        self.replay('preserve')


if __name__ == '__main__':
    unittest.main()
