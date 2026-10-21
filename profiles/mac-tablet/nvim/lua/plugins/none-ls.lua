-- Customize None-ls sources

---@type LazySpec
return {
  "nvimtools/none-ls.nvim",
  opts = function(_, config)
    local null_ls = require "null-ls"

    config.sources = {
      null_ls.builtins.formatting.stylua,
      null_ls.builtins.formatting.prettierd.with {
        filetypes = {
          "astro",
          "css",
          "html",
          "javascript",
          "javascriptreact",
          "json",
          "jsonc",
          "markdown",
          "scss",
          "typescript",
          "typescriptreact",
          "yaml",
        },
      },
    }
    config.on_init = function(client)
      client.supports_method = function(method)
        return method == "textDocument/formatting" or method == "textDocument/rangeFormatting"
      end
    end
    return config -- return final config table
  end,
}
