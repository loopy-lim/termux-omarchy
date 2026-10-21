-- Apply after personal/community specs: external tools need explicit installation.
local function manual_tools(_, opts)
  opts.ensure_installed = {}
  opts.automatic_installation = false
  opts.automatic_enable = false
  opts.auto_install = false
  opts.sync_install = false
end
return {
  { "williamboman/mason.nvim", opts = { max_concurrent_installers = 1 } },
  { "williamboman/mason-lspconfig.nvim", opts = manual_tools },
  { "jay-babu/mason-null-ls.nvim", opts = manual_tools },
  { "jay-babu/mason-nvim-dap.nvim", opts = manual_tools },
  { "nvim-treesitter/nvim-treesitter", opts = manual_tools, build = false },
  { "vhyrro/luarocks.nvim", enabled = false },
  { "nvim-telescope/telescope-fzf-native.nvim", enabled = false },
  { "chomosuke/typst-preview.nvim", opts = { dependencies_bin = { tinymist = "tinymist", websocat = "websocat" } } },
}
