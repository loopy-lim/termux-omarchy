local function open_in_vscode(args)
  local filepath = vim.fn.fnamemodify(args.file, ":p")
  if vim.fn.executable "loopy-vscode" ~= 1 then
    vim.notify("loopy-vscode is unavailable; keeping the buffer open", vim.log.levels.WARN)
    return
  end
  local job = vim.fn.jobstart({ "loopy-vscode", "-r", "--", filepath }, { detach = true })
  if job <= 0 then
    vim.notify("Unable to start loopy-vscode; keeping the buffer open", vim.log.levels.WARN)
    return
  end
  vim.notify("Opening in VS Code: " .. vim.fn.fnamemodify(filepath, ":t"), vim.log.levels.INFO)
end

local open_pdf_preview

local function require_image_plugin()
  local ok, image = pcall(require, "image")
  if ok then return image end

  local lazy_ok, lazy = pcall(require, "lazy")
  if lazy_ok then pcall(lazy.load, { plugins = { "image.nvim" } }) end

  ok, image = pcall(require, "image")
  if ok then return image end

  return nil, image
end

local function open_pdf_in_yazi(args)
  local filepath = vim.fn.fnamemodify(args.file, ":p")
  local helper = "loopy-open-in-yazi-window"

  if vim.env.TMUX ~= nil and vim.fn.executable(helper) == 1 and vim.fn.executable "yazi" == 1 then
    local result = vim.fn.system({ helper, filepath })
    if vim.v.shell_error == 0 then
      vim.schedule(function()
        if vim.api.nvim_buf_is_valid(args.buf) then vim.api.nvim_buf_delete(args.buf, { force = true }) end
      end)
      return
    end

    vim.notify("Failed to open PDF in yazi: " .. result, vim.log.levels.WARN)
  end

  open_pdf_preview(args)
end

local function open_media_in_yazi(args)
  local filepath = vim.fn.fnamemodify(args.file, ":p")
  local helper = "loopy-open-in-yazi-window"

  if vim.env.TMUX == nil or vim.fn.executable(helper) ~= 1 or vim.fn.executable "yazi" ~= 1 then return end

  local result = vim.fn.system({ helper, filepath })
  if vim.v.shell_error ~= 0 then
    vim.notify("Failed to open media in yazi: " .. result, vim.log.levels.WARN)
    return
  end

  vim.schedule(function()
    if vim.api.nvim_buf_is_valid(args.buf) then vim.api.nvim_buf_delete(args.buf, { force = true }) end
  end)
end

open_pdf_preview = function(args)
  local filepath = vim.fn.fnamemodify(args.file, ":p")

  vim.bo[args.buf].swapfile = false
  vim.bo[args.buf].buftype = "nowrite"
  vim.bo[args.buf].bufhidden = "wipe"
  vim.bo[args.buf].modifiable = true

  if vim.fn.executable "pdftoppm" ~= 1 then
    vim.api.nvim_buf_set_lines(args.buf, 0, -1, false, { "pdftoppm is required to preview PDF files in Neovim." })
    return
  end

  local image, image_error = require_image_plugin()
  if not image then
    vim.api.nvim_buf_set_lines(args.buf, 0, -1, false, {
      "image.nvim is required to preview PDF files in Neovim.",
      tostring(image_error),
    })
    return
  end

  local preview_dir = vim.fn.tempname()
  vim.fn.mkdir(preview_dir, "p")
  local prefix = preview_dir .. "/page"
  local result = vim.fn.system({ "pdftoppm", "-png", "-r", "120", filepath, prefix })
  if vim.v.shell_error ~= 0 then
    vim.api.nvim_buf_set_lines(args.buf, 0, -1, false, { "Failed to render PDF preview:", result })
    return
  end

  local pages = vim.fn.glob(prefix .. "-*.png", false, true)
  table.sort(pages)
  if vim.tbl_isempty(pages) then
    vim.api.nvim_buf_set_lines(args.buf, 0, -1, false, { "No PDF pages were rendered." })
    return
  end

  local lines = {}
  local page_rows = {}
  for index, _ in ipairs(pages) do
    page_rows[index] = #lines
    table.insert(lines, ("Page %d"):format(index))
    table.insert(lines, "")
  end

  vim.bo[args.buf].modifiable = true
  vim.api.nvim_buf_set_lines(args.buf, 0, -1, false, lines)
  vim.bo[args.buf].filetype = "pdf_image_preview"
  vim.bo[args.buf].modifiable = false
  vim.b[args.buf].pdf_preview_dir = preview_dir

  vim.api.nvim_create_autocmd("BufWipeout", {
    buffer = args.buf,
    once = true,
    callback = function() vim.fn.delete(preview_dir, "rf") end,
  })

  vim.schedule(function()
    if not vim.api.nvim_buf_is_valid(args.buf) then return end
    local win = vim.fn.bufwinid(args.buf)
    if win == -1 then return end
    for index, page in ipairs(pages) do
      local img = image.from_file(page, {
        window = win,
        buffer = args.buf,
        inline = true,
        with_virtual_padding = true,
        x = 0,
        y = page_rows[index],
      })
      if img then img:render() end
    end
  end)
end

-- Binary files are better handled by VS Code than terminal buffers.
vim.api.nvim_create_autocmd("BufReadCmd", {
  pattern = {
    "*.xlsx",
    "*.xls",
    "*.docx",
    "*.doc",
    "*.pptx",
    "*.ppt",
  },
  callback = open_in_vscode,
  desc = "Open binary files in VSCode",
})

vim.api.nvim_create_autocmd("BufReadCmd", {
  pattern = {
    "*.pdf",
  },
  callback = open_pdf_in_yazi,
  desc = "Open PDF files in yazi preview window",
})

vim.api.nvim_create_autocmd("BufReadCmd", {
  pattern = {
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.webp",
    "*.gif",
    "*.svg",
    "*.avif",
  },
  callback = open_media_in_yazi,
  desc = "Open image files in yazi preview window",
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
