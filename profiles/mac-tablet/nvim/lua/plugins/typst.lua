---@type LazySpec
return {
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
