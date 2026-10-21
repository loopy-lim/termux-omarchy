-- claudecode.nvim - Claude Code CLI integration for Neovim
-- https://github.com/coder/claudecode.nvim

---@type LazySpec
return {
  {
    "coder/claudecode.nvim",
    dependencies = {
      "folke/snacks.nvim",
    },
    config = true,
    cmd = { "ClaudeCode", "ClaudeCodeFocus", "ClaudeCodeSend" },
  },
}
