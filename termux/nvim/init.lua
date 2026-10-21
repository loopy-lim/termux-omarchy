-- Personal AstroNvim, with no implicit downloads in the Android guest.
vim.g.mapleader = " "
vim.g.maplocalleader = ","
local root = vim.fn.stdpath "data" .. "/lazy"
local lock = vim.fn.stdpath "config" .. "/lazy-lock.json"
local ok, plugins = pcall(function() return vim.json.decode(table.concat(vim.fn.readfile(lock), "\n")) end)
local missing = {}
if ok then
  for name, _ in pairs(plugins) do
    if not (vim.uv or vim.loop).fs_stat(root .. "/" .. name) then table.insert(missing, name) end
  end
end
if not ok or #missing > 0 then
  vim.opt.number = true
  vim.opt.relativenumber = false
  vim.opt.wrap = true
  vim.opt.autoread = true
  vim.keymap.set("n", "]b", "<Cmd>bnext<CR>", { desc = "Next buffer" })
  vim.keymap.set("n", "[b", "<Cmd>bprevious<CR>", { desc = "Previous buffer" })
  vim.keymap.set({ "n", "i" }, "<M-w>", "<Esc><Cmd>bdelete<CR>", { desc = "Close buffer" })
  for _, key in ipairs({ "h", "j", "k", "l" }) do
    vim.keymap.set("n", "<C-" .. key .. ">", "<C-w>" .. key, { desc = "Move to split" })
  end
  vim.schedule(function()
    vim.notify(("Personal config ready; %d locked plugin directories missing. Basic Neovim is active; no downloads were requested."):format(#missing), vim.log.levels.WARN)
  end)
  return
end
vim.opt.rtp:prepend(root .. "/lazy.nvim")
if not pcall(require, "lazy") then
  vim.notify("Unable to load the existing lazy.nvim; no download was requested", vim.log.levels.ERROR)
  return
end
require "lazy_setup"
require "polish"
