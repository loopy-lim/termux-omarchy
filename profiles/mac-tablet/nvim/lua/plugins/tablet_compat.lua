-- Keep the Mac UI/keymaps; activate integrations only when Linux tools exist.
return {
  { "vhyrro/luarocks.nvim", enabled = false },
  { "3rd/image.nvim", enabled = false },
  { "MeanderingProgrammer/render-markdown.nvim", enabled = pcall(vim.treesitter.language.add, "markdown") },
  { "coder/claudecode.nvim", enabled = vim.fn.executable "claude" == 1 },
  { "andweeb/presence.nvim", enabled = vim.fn.executable "Discord" == 1 },
  { "nvim-treesitter/nvim-treesitter", opts = function(_, opts)
    opts.auto_install = false
    opts.ensure_installed = {}
  end },
  { "williamboman/mason-lspconfig.nvim", opts = function(_, opts)
    opts.ensure_installed = {}
    opts.automatic_installation = false
  end },
  { "jay-babu/mason-null-ls.nvim", opts = function(_, opts)
    opts.ensure_installed = {}
    opts.automatic_installation = false
  end },
  { "jay-babu/mason-nvim-dap.nvim", opts = function(_, opts)
    opts.ensure_installed = {}
    opts.automatic_installation = false
  end },
  { "chomosuke/typst-preview.nvim", enabled = vim.fn.executable "tinymist" == 1 },
  { "WhoIsSethDaniel/mason-tool-installer.nvim", enabled = false },
}
