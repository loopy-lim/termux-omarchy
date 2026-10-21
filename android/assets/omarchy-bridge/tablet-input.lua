-- Final tablet profile. Android already applies the user's KeyBridge modifier/Caps mapping.
-- The Android Wayland host composites the cursor independently from Linux frames.
hl.config({ input = { kb_options = "" }, cursor = { no_hardware_cursors = 2 } })

for workspace = 1, 10 do
  -- Upstream uses XKB keycodes 10..19, not the digit keysyms. Remove both forms
  -- before installing one action, including the physical zero key for workspace 10.
  local code = "code:" .. tostring(workspace + 9)
  local symbol = tostring(workspace % 10)
  for _, modifiers in ipairs({ "SUPER + ", "SUPER + SHIFT + " }) do
    hl.unbind(modifiers .. code)
    hl.unbind(modifiers .. symbol)
  end
  hl.bind("SUPER + " .. code, hl.dsp.focus({ workspace = tostring(workspace) }))
  hl.bind("SUPER + SHIFT + " .. code,
    hl.dsp.window.move({ workspace = tostring(workspace), follow = false }))
end
