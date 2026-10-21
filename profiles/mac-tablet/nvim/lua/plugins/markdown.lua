return {
  "MeanderingProgrammer/render-markdown.nvim",
  ft = { "markdown", "mdx" },
  dependencies = {
    "nvim-treesitter/nvim-treesitter",
    "nvim-tree/nvim-web-devicons",
  },
  config = function(_, opts)
    local query = require "vim.treesitter.query"

    local aliases = {
      ex = "elixir",
      pl = "perl",
      sh = "bash",
      ts = "typescript",
      uxn = "uxntal",
    }

    local function first_node(captures, id)
      local node = captures[id]
      if type(node) == "table" then node = node[1] end
      return node
    end

    query.add_directive("set-lang-from-info-string!", function(captures, _, bufnr, pred, metadata)
      local node = first_node(captures, pred[2])
      if not node then return end

      local alias = vim.treesitter.get_node_text(node, bufnr):lower()
      local filetype = vim.filetype.match { filename = "a." .. alias }
      metadata["injection.language"] = filetype or aliases[alias] or alias
    end, { force = true, all = false })

    require("render-markdown").setup(opts)
  end,
  opts = {
    heading = {
      enabled = true,
      icons = { "# ", "## ", "### ", "#### ", "##### ", "###### " },
    },
    code = {
      enabled = true,
      sign = false,
      width = "full",
    },
    checkbox = {
      enabled = true,
    },
  },
}
