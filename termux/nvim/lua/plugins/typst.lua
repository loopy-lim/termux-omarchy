---@type LazySpec
return {
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      opts.ensure_installed = opts.ensure_installed or {}
      if not vim.tbl_contains(opts.ensure_installed, "typst") then table.insert(opts.ensure_installed, "typst") end
    end,
  },
  {
    "chomosuke/typst-preview.nvim",
    ft = "typst",
    version = "1.*",
    opts = {
      dependencies_bin = {
        tinymist = "tinymist",
      },
    },
    keys = {
      { "<Leader>tp", "<Cmd>TypstPreview<CR>", ft = "typst", desc = "Typst preview" },
      { "<Leader>ts", "<Cmd>TypstPreviewStop<CR>", ft = "typst", desc = "Stop Typst preview" },
      { "<Leader>tf", "<Cmd>TypstPreviewFollowCursorToggle<CR>", ft = "typst", desc = "Toggle Typst preview follow" },
    },
  },
}
