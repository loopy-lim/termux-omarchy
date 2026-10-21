return {
  "AstroNvim/astrocore",
  ---@type AstroCoreOpts
  opts = {
    -- 1. 옵션 설정: autoread 켜기
    options = {
      opt = {
        autoread = true,
      },
    },
    -- 2. 자동 명령(Autocmds) 설정: 더 적극적으로 변경사항 체크하기
    autocmds = {
      -- 그룹 이름 (임의 지정 가능)
      restore_file_changes = {
        {
          -- 이 이벤트들이 발생할 때마다 checktime 실행
          event = { "FocusGained", "BufEnter", "CursorHold", "CursorHoldI" },
          desc = "Reload files changed outside neovim",
          callback = function()
            -- 명령 모드('c')가 아닐 때만 체크 (입력 중 방해 금지)
            if vim.fn.mode() ~= "c" then vim.cmd "checktime" end
          end,
        },
        -- (선택) 변경 감지 시 알림 메시지 띄우기 (필요 없으면 이 부분 삭제)
        {
          event = { "FileChangedShellPost" },
          callback = function() vim.notify("File changed on disk. Buffer reloaded!", vim.log.levels.INFO) end,
        },
      },
    },
  },
}
