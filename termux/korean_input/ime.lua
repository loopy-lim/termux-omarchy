-- Keep native GTK Wayland text input; enable the X11 and Qt input frontends.
hl.env("XMODIFIERS", "@im=fcitx")
hl.env("QT_IM_MODULE", "fcitx")
hl.env("SDL_IM_MODULE", "fcitx")
-- This event runs once per compositor start, not on configuration reload.
-- Keep Fcitx in the session process tree and do not replace another instance.
hl.on("hyprland.start", function()
  hl.exec_cmd("fcitx5 -D")
end)
