return {
  {
    "mrjones2014/smart-splits.nvim",
    opts = {
      multiplexer_integration = "tmux",
      ignored_filetypes = { "nofile", "quickfix", "prompt" },
    },
    keys = {
      {
        "<C-h>",
        function() require("smart-splits").move_cursor_left() end,
        desc = "Move to left split",
      },
      {
        "<C-j>",
        function() require("smart-splits").move_cursor_down() end,
        desc = "Move to lower split",
      },
      {
        "<C-k>",
        function() require("smart-splits").move_cursor_up() end,
        desc = "Move to upper split",
      },
      {
        "<C-l>",
        function() require("smart-splits").move_cursor_right() end,
        desc = "Move to right split",
      },
    },
  },
  {
    "folke/trouble.nvim",
    cmd = "Trouble",
    opts = {
      focus = true,
    },
    keys = {
      { "<leader>xx", "<cmd>Trouble diagnostics toggle focus=true<cr>", desc = "Diagnostics" },
      { "<leader>xX", "<cmd>Trouble diagnostics toggle filter.buf=0 focus=true<cr>", desc = "Buffer diagnostics" },
      { "<leader>cs", "<cmd>Trouble symbols toggle focus=true<cr>", desc = "Symbols" },
    },
  },
  {
    "stevearc/aerial.nvim",
    version = false,
    opts = {
      layout = {
        default_direction = "right",
        min_width = 28,
      },
      show_guides = false,
    },
    keys = {
      { "<leader>o", "<cmd>AerialToggle right<cr>", desc = "Toggle outline" },
    },
  },
}
