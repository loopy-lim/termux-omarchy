-- Keep Omarchy's SUPER number workspaces, SHIFT moves, and ALT TAB cycle.
-- These callbacks stay inside the compositor; no shell/injector process per key.
local function send_once(mods, key)
  hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "down" }))
  hl.timer(function()
    hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "up" }))
  end, { timeout = 50, type = "oneshot" })
end

local function terminal_active()
  local window = hl.get_active_window()
  if not window then return false end
  for _, tag in ipairs(window.tags or {}) do
    if tag:gsub("%*$", "") == "terminal" then return true end
  end
  return false
end

-- Use the tablet's Alt key for the menu; dispatch to the live shell directly.
hl.unbind("SUPER + SPACE")
hl.unbind("ALT + SPACE")
o.bind("ALT + SPACE", "Omarchy menu", hl.dsp.global("omarchy:menu"))

o.bind("ALT + C", "Copy", function()
  if terminal_active() then send_once("CTRL", "Insert")
  else send_once("CTRL", "C") end
end)
o.bind("ALT + V", "Paste", function()
  if terminal_active() then send_once("SHIFT", "Insert")
  else send_once("CTRL", "V") end
end)

-- KeyBridge's Caps+Alt+H/J/K/L fallback emits Alt+arrows.
o.bind("ALT + LEFT", "Start of line", function() send_once("", "Home") end)
o.bind("ALT + RIGHT", "End of line", function() send_once("", "End") end)
o.bind("ALT + UP", "Start of document", function() send_once("CTRL", "Home") end)
o.bind("ALT + DOWN", "End of document", function() send_once("CTRL", "End") end)

-- The Android handoff emits evdev F13/F14 (183/184), hence XKB 191/192.
-- Bind the codes once: inet(evdev) may name them XF86Tools/XF86Launch5.
o.bind("code:191", "Previous workspace (Caps+D)", hl.dsp.focus({ workspace = "e-1" }))
o.bind("code:192", "Next workspace (Caps+F)", hl.dsp.focus({ workspace = "e+1" }))
