return {
  "rcarriga/nvim-dap-ui",
  cond = not vim.g.vscode,
  keys = {
    -- 아래 패널 (tray) 토글
    {
      "<D-j>",
      function() require("dapui").toggle("tray") end,
      desc = "Toggle DAP tray (bottom)",
    },
    -- 왼쪽 패널 (sidebar) 토글
    {
      "<D-S-b>",
      function() require("dapui").toggle("sidebar") end,
      desc = "Toggle DAP sidebar (left)",
    },
  },
}
