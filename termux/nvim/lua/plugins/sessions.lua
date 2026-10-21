if vim.g.vscode then return {} end

return {
  "AstroNvim/astrocore",
  opts = {
    sessions = {
      autosave = {
        last = true, -- 마지막 세션 저장
        cwd = true, -- 작업 디렉토리별 저장
      },
      ignore = {
        filetypes = { "gitcommit", "gitrebase", "neo-tree" },
      },
    },
    autocmds = {
      -- 프로젝트 진입 시 세션 자동 복원
      restore_session = {
        {
          event = "VimEnter",
          desc = "Restore previous directory session",
          nested = true,
          callback = function()
            -- VSCode에서는 실행 안함
            if vim.g.vscode then return end
            -- 인자 없이 nvim 실행 시에만 복원
            if vim.fn.argc(-1) == 0 then
              require("resession").load(vim.fn.getcwd(), { dir = "dirsession", silence_errors = true })
            end
          end,
        },
      },
    },
  },
}
