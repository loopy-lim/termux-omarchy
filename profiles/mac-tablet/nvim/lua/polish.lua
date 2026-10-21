-- Keep media previews in the native Wayland terminal instead of Mac wrappers.
local function open_in_yazi(args)
  local filepath = vim.fn.fnamemodify(args.file, ":p")
  if vim.fn.executable "foot" ~= 1 or vim.fn.executable "yazi" ~= 1 then
    vim.bo[args.buf].buftype = "nowrite"
    vim.api.nvim_buf_set_lines(args.buf, 0, -1, false, { "Open this file from the Files application." })
    return
  end
  local job = vim.fn.jobstart({ "foot", "--app-id=loopy-media-preview", "--title=File preview", "yazi", filepath }, { detach = true })
  if job > 0 then
    vim.schedule(function()
      if vim.api.nvim_buf_is_valid(args.buf) then vim.api.nvim_buf_delete(args.buf, { force = true }) end
    end)
  end
end

vim.api.nvim_create_autocmd("BufReadCmd", {
  pattern = { "*.pdf", "*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif", "*.svg", "*.avif", "*.xlsx", "*.xls", "*.docx", "*.doc", "*.pptx", "*.ppt" },
  callback = open_in_yazi,
  desc = "Open media in the tablet file browser",
})

local function set_tmux_nvim_server()
  if vim.env.TMUX == nil or vim.g.vscode then return end

  local server = vim.v.servername
  if server == nil or server == "" then return end

  vim.fn.system({ "tmux", "set-environment", "NVIM_SERVER", server })
  local pane = vim.env.TMUX_PANE or ""
  local window = ""
  if pane ~= "" then window = vim.fn.system({ "tmux", "display-message", "-p", "-t", pane, "#{window_id}" }):gsub("%s+$", "") end
  if window ~= "" then vim.fn.system({ "tmux", "set-environment", "NVIM_WINDOW", window }) end
  if pane ~= "" then vim.fn.system({ "tmux", "set-environment", "NVIM_PANE", pane }) end
end

local function unset_tmux_nvim_server()
  if vim.env.TMUX == nil or vim.g.vscode then return end

  local server = vim.v.servername
  if server == nil or server == "" then return end

  vim.fn.system({
    "zsh",
    "-lc",
    [=[current=$(tmux show-environment NVIM_SERVER 2>/dev/null | sed 's/^NVIM_SERVER=//'); if [[ "$current" == "$1" ]]; then tmux set-environment -u NVIM_SERVER; tmux set-environment -u NVIM_WINDOW; tmux set-environment -u NVIM_PANE; fi]=],
    "zsh",
    server,
  })
end

local tmux_nvim_server_group = vim.api.nvim_create_augroup("TmuxNvimServer", { clear = true })

vim.api.nvim_create_autocmd("VimEnter", {
  group = tmux_nvim_server_group,
  callback = set_tmux_nvim_server,
  desc = "Register current Neovim server in tmux",
})

vim.api.nvim_create_autocmd("VimLeavePre", {
  group = tmux_nvim_server_group,
  callback = unset_tmux_nvim_server,
  desc = "Unregister current Neovim server from tmux",
})

-- VSCode 스타일 diff: 폴딩 없이 전체 파일 표시, fold 거터 제거, 빈 영역은 빗금으로 표시해요
vim.opt.diffopt:append { "context:99999", "foldcolumn:0" }
vim.opt.fillchars:append { diff = "╱" }

-- VSCode-Neovim keybindings
if vim.g.vscode then
  -- ]b - 다음 에디터(탭)
  vim.keymap.set("n", "]b", function()
    vim.fn.VSCodeNotify("workbench.action.nextEditor")
  end, { desc = "Next buffer" })

  -- [b - 이전 에디터(탭)
  vim.keymap.set("n", "[b", function()
    vim.fn.VSCodeNotify("workbench.action.previousEditor")
  end, { desc = "Previous buffer" })

  -- gD - Declaration으로 이동
  vim.keymap.set("n", "gD", function()
    vim.fn.VSCodeNotify("editor.action.revealDeclaration")
  end, { desc = "Go to declaration" })
end
