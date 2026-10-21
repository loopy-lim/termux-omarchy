"""Run original upstream Lua bindings and the packaged final input profile in real Lua.

The hl boundary records registrations; Android execution separately checks real dispatch.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LUA = shutil.which('lua')

HARNESS = r'''
local binds = {}
local function dsp() return setmetatable({}, {__index=function(t,k) local v=dsp();rawset(t,k,v);return v end, __call=function() return {} end}) end
hl = {dsp=dsp()}
hl.dsp.focus=function(options) return {kind='focus',workspace=options.workspace} end
hl.dsp.window.move=function(options) return {kind='move',workspace=options.workspace,follow=options.follow} end
hl.config=function(options) assert(options.input.kb_options=='', 'Caps mapping was overwritten') end
hl.bind=function(keys,dispatcher) table.insert(binds,{keys=keys,dispatcher=dispatcher}) end
hl.unbind=function(keys) for i=#binds,1,-1 do if binds[i].keys==keys then table.remove(binds,i) end end end
o={bind=function(keys,description,dispatcher) hl.bind(keys,dispatcher) end}
dofile(arg[1])
local unaffected={}
for _,binding in ipairs(binds) do
 if not binding.keys:match('^SUPER %+ code:%d+$') and not binding.keys:match('^SUPER %+ SHIFT %+ code:%d+$') then
  unaffected[binding.keys]=binding.dispatcher
 end
end
dofile(arg[2])
for workspace=1,10 do
 local code='code:'..tostring(workspace+9)
 for _,shift in ipairs({false,true}) do
  local keys='SUPER + '..(shift and 'SHIFT + ' or '')..code
  local matches={}
  for _,binding in ipairs(binds) do if binding.keys==keys then table.insert(matches,binding.dispatcher) end end
  assert(#matches==1, 'duplicate or missing original keycode binding: '..keys)
  assert(matches[1].workspace==tostring(workspace), 'wrong workspace including number zero')
  assert(matches[1].kind==(shift and 'move' or 'focus'), 'wrong numeric shortcut action')
  if shift then assert(matches[1].follow==false, 'window move unexpectedly follows the window') end
 end
end
for keys,dispatcher in pairs(unaffected) do
 local preserved=false
 for _,binding in ipairs(binds) do if binding.keys==keys and binding.dispatcher==dispatcher then preserved=true end end
 assert(preserved,'unrelated upstream shortcut lost: '..keys)
end
print('20 unique original keycode bindings; silent moves; unrelated upstream bindings preserved')
'''


@unittest.skipUnless(LUA, 'real Lua interpreter required')
class OmarchyInputProfileTests(unittest.TestCase):
    def test_original_code_bindings_are_replaced_instead_of_duplicated(self):
        original = ROOT / 'build/omarchy-sources/omarchy/default/hypr/bindings/tiling.lua'
        self.assertTrue(original.is_file(), 'pinned original Omarchy bindings required')
        before = original.read_bytes()
        with tempfile.TemporaryDirectory(prefix='loopy-omarchy-input-') as directory:
            script = Path(directory) / 'verify.lua'
            script.write_text(HARNESS)
            result = subprocess.run([LUA, str(script), str(original),
                                     str(ROOT / 'android/assets/omarchy-bridge/tablet-input.lua')],
                                    capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(original.read_bytes(), before)
        self.assertIn('20 unique original keycode bindings', result.stdout)


if __name__ == '__main__':
    unittest.main()
