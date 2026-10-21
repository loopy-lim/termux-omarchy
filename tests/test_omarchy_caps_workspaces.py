"""Real Lua profile loading; registration and key matching are host stubs.

The matching seam models Hyprland's XKB code (evdev + 8) or keysym match.
It does not run Hyprland, JNI, Android dispatch, or physical keyboard input.
"""
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'termux/profile/bindings.lua'
LUA = shutil.which('lua')
REPLAY = r'''
local registered = {}
hl = {
  unbind = function() end,
  dsp = {
    global = function(name) return { kind = "global", name = name } end,
    focus = function(args) return { kind = "focus", workspace = args.workspace } end,
  },
}
o = { bind = function(key, description, action)
  registered[#registered + 1] = { key = key, action = action }
end }
assert(loadfile(arg[1]))()
local code, sym, expected = tonumber(arg[2]), arg[3], arg[4]
local matches = {}
for _, bind in ipairs(registered) do
  -- No modifiers are pressed. The production profile's ALT bindings cannot match.
  local boundCode = bind.key:match("^code:(%d+)$")
  if (boundCode and tonumber(boundCode) == code) or bind.key == sym then
    matches[#matches + 1] = bind.action
  end
end
assert(#matches == 1, string.format("code=%d sym=%s: expected exactly one dispatcher, got %d", code, sym, #matches))
assert(type(matches[1]) == "table" and matches[1].kind == "focus", "wrong dispatcher")
assert(matches[1].workspace == expected, "wrong workspace direction")
print(string.format("PASS code=%d sym=%s workspace=%s exactly once", code, sym, expected))
'''


class CapsWorkspaceBindingsTests(unittest.TestCase):
    def replay(self, code, symbol, workspace):
        self.assertIsNotNone(LUA, 'real Lua interpreter required')
        result = subprocess.run(
            [LUA, '-', str(PROFILE), str(code), symbol, workspace], input=REPLAY,
            text=True, capture_output=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('exactly once', result.stdout)

    def test_caps_d_code191_with_standard_xf86_symbol(self):
        self.replay(191, 'XF86Tools', 'e-1')

    def test_caps_d_code191_with_f13_symbol_without_double_dispatch(self):
        self.replay(191, 'F13', 'e-1')

    def test_caps_f_code192_with_standard_xf86_symbol(self):
        self.replay(192, 'XF86Launch5', 'e+1')

    def test_caps_f_code192_with_f14_symbol_without_double_dispatch(self):
        self.replay(192, 'F14', 'e+1')


if __name__ == '__main__':
    unittest.main()
