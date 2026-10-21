-- Satellite: 스크롤바 + viewport + 진단/검색/git 마커
return {
  "lewis6991/satellite.nvim",
  event = "VeryLazy",
  opts = {
    current_only = false,
    winblend = 50,
    zindex = 40,
    excluded_filetypes = { "neo-tree", "toggleterm", "TelescopePrompt" },
    width = 2,
    handlers = {
      cursor = {
        enable = true,
        symbols = { "=" },
      },
      search = {
        enable = true,
      },
      diagnostic = {
        enable = true,
        signs = { "-", "=", "=" },
        min_severity = vim.diagnostic.severity.HINT,
      },
      gitsigns = {
        enable = true,
        signs = {
          add = "|",
          change = "|",
          delete = "-",
        },
      },
      marks = {
        enable = true,
        show_builtins = false,
      },
    },
  },
  keys = {
    { "<leader>us", "<cmd>SatelliteToggle<cr>", desc = "Toggle satellite" },
  },
}
