-- Telescope live grep with glob pattern support
-- Usage examples:
--   "search term" --glob=*.dart      (only dart files)
--   "search term" --glob=*.{ts,tsx}  (only ts/tsx files)
--   "search term" --glob=!*.dart     (exclude dart files)
--   "search term" -t dart            (only dart file type)

---@type LazySpec
return {
  {
    "nvim-telescope/telescope.nvim",
    dependencies = {
      "nvim-telescope/telescope-live-grep-args.nvim",
    },
    opts = function(_, opts)
      local actions = require "telescope.actions"
      local lga_actions = require("telescope-live-grep-args.actions")
      opts.defaults = opts.defaults or {}
      opts.defaults.mappings = opts.defaults.mappings or {}
      opts.defaults.mappings.i = vim.tbl_extend("force", opts.defaults.mappings.i or {}, {
        ["<C-j>"] = actions.move_selection_next,
        ["<C-k>"] = actions.move_selection_previous,
        ["<C-l>"] = actions.select_default,
      })
      opts.defaults.mappings.n = vim.tbl_extend("force", opts.defaults.mappings.n or {}, {
        ["<C-j>"] = actions.move_selection_next,
        ["<C-k>"] = actions.move_selection_previous,
        ["<C-l>"] = actions.select_default,
      })
      opts.extensions = opts.extensions or {}
      opts.extensions.live_grep_args = {
        auto_quoting = true,
        mappings = {
          i = {
            ["<C-q>"] = lga_actions.quote_prompt(),
            ["<C-i>"] = lga_actions.quote_prompt({ postfix = " --iglob " }),
            ["<C-g>"] = lga_actions.quote_prompt({ postfix = " --glob " }),
          },
        },
      }
      return opts
    end,
    config = function(plugin, opts)
      require("astronvim.plugins.configs.telescope")(plugin, opts)
      require("telescope").load_extension("live_grep_args")
    end,
  },
  {
    "AstroNvim/astrocore",
    opts = {
      mappings = {
        n = {
          ["<Leader>/"] = {
            function()
              require("telescope").extensions.live_grep_args.live_grep_args({
                additional_args = { "--hidden", "--no-ignore" },
              })
            end,
            desc = "Search in all files",
          },
          ["<Leader>fw"] = {
            function() require("telescope").extensions.live_grep_args.live_grep_args() end,
            desc = "Find words (with glob support)",
          },
          ["<Leader>fW"] = {
            function()
              require("telescope").extensions.live_grep_args.live_grep_args({
                additional_args = { "--hidden", "--no-ignore" },
              })
            end,
            desc = "Find words in all files (with glob support)",
          },
        },
      },
    },
  },
}
