"""Portable workflow templates; no device, account, editor, or SSH state.

Foot and Tmux defaults and launch helpers are adapted from Omarchy (MIT).
The retained Omarchy notice is in legal/licenses/omarchy-MIT.txt.
These are source inputs, parsed as literals by the payload builder.
"""

TEMPLATES = {
    'foot': r'''[main]
include=~/.local/state/omarchy/current/theme/foot.ini
term=xterm-256color
font=JetBrainsMono Nerd Font:size=9
pad=14x14
initial-window-mode=windowed
workers=0
shell=/usr/bin/zsh

[scrollback]
lines=10000
multiplier=7.0

[cursor]
style=block
blink=no

[key-bindings]
clipboard-copy=Control+Insert Control+Shift+c XF86Copy Mod1+c
primary-paste=none
clipboard-paste=Shift+Insert Control+Shift+v XF86Paste Mod1+v
font-decrease=Control+minus Mod1+minus Mod1+KP_Subtract
font-increase=Control+plus Control+equal Mod1+plus Mod1+equal Mod1+KP_Add
font-reset=Control+0

[text-bindings]
# CSI-u preserves Shift+Return and Alt+Shift+Return for terminal applications.
\x1b[13;2u=Shift+Return
\x1b[13;4u=Mod1+Shift+Return
''',
    'bindings-loader': '''-- Omarchy loads its defaults before these portable tablet overrides.
dofile(os.getenv("HOME") .. "/.local/share/loopy-omarchy-profile/bindings.lua")
''',
    'tmux-loader': '''# Portable Tmux defaults adapted from Omarchy (MIT).
set -g prefix C-Space
set -g prefix2 C-b
bind C-Space send-prefix
bind q source-file ~/.config/tmux/tmux.conf \\; display "Configuration reloaded"
bind -N "Show Tmux keybindings" ? display-popup -E -w 80% -h 70% -T "Tmux keybindings" "omarchy-menu-tmux-keybindings --print | less -R"
setw -g mode-keys vi
bind -T copy-mode-vi v send -X begin-selection
bind -T copy-mode-vi y send -X copy-selection-and-cancel
bind -n M-Enter split-window -v -c "#{pane_current_path}"
bind -n M-S-Enter split-window -h -c "#{pane_current_path}"
bind -n M-Escape kill-pane
bind h split-window -v -c "#{pane_current_path}"
bind v split-window -h -c "#{pane_current_path}"
bind x kill-pane
bind -n C-M-Left select-pane -L
bind -n C-M-Right select-pane -R
bind -n C-M-Up select-pane -U
bind -n C-M-Down select-pane -D
bind -n C-M-S-Left resize-pane -L 5
bind -n C-M-S-Down resize-pane -D 5
bind -n C-M-S-Up resize-pane -U 5
bind -n C-M-S-Right resize-pane -R 5
bind r command-prompt -I "#W" "rename-window -- '%%'"
bind c new-window -c "#{pane_current_path}"
bind k kill-window
bind -n M-1 select-window -t 1
bind -n M-2 select-window -t 2
bind -n M-3 select-window -t 3
bind -n M-4 select-window -t 4
bind -n M-5 select-window -t 5
bind -n M-6 select-window -t 6
bind -n M-7 select-window -t 7
bind -n M-8 select-window -t 8
bind -n M-9 select-window -t 9
bind -n M-Left select-window -t -1
bind -n M-Right select-window -t +1
bind -n M-S-Left swap-window -t -1 \\; select-window -t -1
bind -n M-S-Right swap-window -t +1 \\; select-window -t +1
bind R command-prompt -I "#S" "rename-session -- '%%'"
bind C new-session -c "#{pane_current_path}"
bind K kill-session
bind P switch-client -p
bind N switch-client -n
bind -n M-Up switch-client -p
bind -n M-Down switch-client -n
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",*:RGB"
set -g mouse on
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on
set -g history-limit 50000
set -g focus-events on
set -g set-clipboard on
set -g allow-passthrough on
setw -g aggressive-resize on
set -g detach-on-destroy off
set -g extended-keys on
set -g extended-keys-format csi-u
set -ag terminal-features "xterm-kitty:extkeys"
set -as terminal-features ",*:clipboard"
set -sg escape-time 10
set -g status-position top
set -g status-interval 5
set -g status-left-length 30
set -g status-right-length 50
set -g window-status-separator ""
set -gw automatic-rename on
set -gw automatic-rename-format '#{b:pane_current_path}'
set -g set-titles on
set -g set-titles-string '#h:#W'
set -g status-style "bg=default,fg=default"
set -g status-left "#[fg=black,bg=blue,bold] #S #[bg=default] "
set -g status-right "#[fg=blue]#{?pane_in_mode,COPY ,}#{?client_prefix,PREFIX ,}#{?window_zoomed_flag,ZOOM ,}#[fg=brightblack]#h "
set -g window-status-format "#[fg=brightblack] #I:#W "
set -g window-status-current-format "#[fg=blue,bold] #I:#W "
set -g pane-border-style "fg=brightblack"
set -g pane-active-border-style "fg=blue"
set -g message-style "bg=default,fg=blue"
set -g message-command-style "bg=default,fg=blue"
set -g mode-style "bg=blue,fg=black"
setw -g clock-mode-colour blue
source-file ~/.local/share/loopy-omarchy-profile/tmux.conf
''',
    'tmux-home-loader': 'source-file ~/.local/share/loopy-omarchy-profile/tmux.conf\n',
    'zsh-loader': 'source "$HOME/.local/share/loopy-omarchy-profile/zshrc"\n',
    'launch-or-focus': r'''#!/bin/bash
# Adapted from Omarchy (MIT); Lua focus dispatch for the Android/PRoot runtime.
if (($# == 0)); then
  printf '%s\n' 'Usage: omarchy-launch-or-focus window-pattern [launch-command]' >&2
  exit 2
fi
WINDOW_PATTERN="$1"
LAUNCH_COMMAND="${2:-"uwsm-app -- $WINDOW_PATTERN"}"
WINDOW_ADDRESS=$(hyprctl clients -j | jq -r --arg p "$WINDOW_PATTERN" '.[]|select((.class|test("\\b" + $p + "\\b";"i")) or (.title|test("\\b" + $p + "\\b";"i")))|.address' | head -n1)
if [[ -n $WINDOW_ADDRESS ]]; then
  hyprctl dispatch "hl.dsp.focus({ window = \"address:$WINDOW_ADDRESS\" })" >/dev/null 2>&1 || hyprctl dispatch focuswindow "address:$WINDOW_ADDRESS"
else
  eval exec setsid "$LAUNCH_COMMAND"
fi
''',
    'launch-or-focus-tui': r'''#!/bin/bash
# Adapted from Omarchy (MIT); preserve each TUI argument through the focus helper.
if [[ ${1:-} == --app-id=* ]]; then
  APP_ID="${1#--app-id=}"
  COMMAND_INDEX=2
else
  APP_ID="org.omarchy.${1##*/}"
  COMMAND_INDEX=1
fi
if [[ $# -lt $COMMAND_INDEX || -z ${!COMMAND_INDEX} ]]; then
  printf '%s\n' 'Usage: omarchy-launch-or-focus-tui [--app-id=<app-id>] command [args...]' >&2
  exit 2
fi
printf -v LAUNCH_COMMAND '%q ' omarchy-launch-tui "$@"
exec omarchy-launch-or-focus "$APP_ID" "$LAUNCH_COMMAND"
''',
}
