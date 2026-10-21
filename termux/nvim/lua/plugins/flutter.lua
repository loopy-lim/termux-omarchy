return {
  "nvim-flutter/flutter-tools.nvim",
  cond = not vim.g.vscode,
  opts = {
    debugger = {
      enabled = true,
      run_via_dap = true,
    },
    dev_log = {
      enabled = true,
      open_cmd = "tabedit",
    },
  },
}
