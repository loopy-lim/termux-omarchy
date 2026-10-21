-- AstroCommunity: import any community modules here
-- We import this file in `lazy_setup.lua` before the `plugins/` folder.
-- This guarantees that the specs are processed before any user plugins.

-- VSCode 스타일 diff 색상: 좌측(이전 버전)은 빨강, 우측(현재 파일)은 초록 계열로 표시해요
local function apply_vscode_diff_hl(win, is_old_side)
  local groups = is_old_side
      and {
        "DiffAdd:VSCodeDiffDeleteLine",
        "DiffChange:VSCodeDiffDeleteLine",
        "DiffText:VSCodeDiffDeleteText",
        "DiffTextAdd:VSCodeDiffDeleteText",
        "DiffDelete:VSCodeDiffFiller",
      }
    or {
      "DiffAdd:VSCodeDiffAddLine",
      "DiffChange:VSCodeDiffAddLine",
      "DiffText:VSCodeDiffAddText",
      "DiffTextAdd:VSCodeDiffAddText",
      "DiffDelete:VSCodeDiffFiller",
    }
  vim.wo[win].winhl = table.concat(groups, ",")
end

-- 현재 탭에 띄운 gitsigns diff 창들을 VSCode 룩으로 스타일링하고, 이전 버전 창에서 q 로 닫을 수 있게 해요
local function style_inline_diff()
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    if vim.wo[win].diff then
      local buf = vim.api.nvim_win_get_buf(win)
      local is_old_side = vim.api.nvim_buf_get_name(buf):match("^gitsigns:") ~= nil
      apply_vscode_diff_hl(win, is_old_side)
      if is_old_side then
        vim.keymap.set("n", "q", "<C-w>c", { buffer = buf, nowait = true, desc = "Close diff" })
      end
    end
  end
end

-- 현재 탭에 남아 있는 이전 diff 의 스크래치 창을 정리해요 (diffopt 의 closeoff 가 diff 모드를 풀어줘요)
local function close_inline_diff()
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    local buf = vim.api.nvim_win_get_buf(win)
    if vim.api.nvim_buf_get_name(buf):match("^gitsigns:") then pcall(vim.api.nvim_win_close, win, true) end
  end
end

---@type LazySpec
return {
  "AstroNvim/astrocommunity",
  {
    "nvim-neo-tree/neo-tree.nvim",
    opts = {
      window = {
        position = "right",
      },
      filesystem = {
        filtered_items = {
          visible = true,
          hide_dotfiles = false,
          hide_gitignored = false,
        },
        window = {
          mappings = {
            ["r"] = function(state)
              if not state or not state.tree then
                vim.cmd "Neotree refresh"
                return
              end

              local ok, node = pcall(function() return state.tree:get_node() end)
              if not ok or not node or node.type == "message" then
                vim.cmd "Neotree refresh"
                return
              end

              require("neo-tree.sources.filesystem.commands").rename(state)
            end,
          },
        },
      },
      git_status = {
        window = {
          mappings = {
            ["<cr>"] = function(state)
              local node = state.tree and state.tree:get_node()
              if not node then return end
              if node.type ~= "file" then
                require("neo-tree.sources.git_status.commands").open(state)
                return
              end
              close_inline_diff()
              require("neo-tree.sources.git_status.commands").open(state)
              vim.schedule(function()
                local buf = vim.api.nvim_get_current_buf()
                local tries = 20
                -- gitsigns attach 가 비동기라서 attach 완료를 기다렸다가 diff 를 띄워요
                local function start_diff()
                  if not vim.api.nvim_buf_is_valid(buf) or vim.api.nvim_get_current_buf() ~= buf then return end
                  if vim.wo.diff then return end
                  if vim.b[buf].gitsigns_status_dict then
                    require("gitsigns").diffthis("HEAD")
                    vim.defer_fn(style_inline_diff, 80)
                  else
                    tries = tries - 1
                    if tries > 0 then vim.defer_fn(start_diff, 50) end
                  end
                end
                start_diff()
              end)
            end,
            ["D"] = function(state)
              local node = state.tree:get_node()
              local path = node:get_id()
              vim.cmd("DiffviewOpen -- " .. vim.fn.fnameescape(path))
            end,
            ["A"] = function()
              vim.cmd("DiffviewOpen")
            end,
          },
        },
      },
    },
  },
  { import = "astrocommunity.pack.lua" },
  { import = "astrocommunity.recipes.vscode" },
  { import = "astrocommunity.colorscheme.dracula-nvim" },
  { import = "astrocommunity.pack.typescript" },
  { import = "astrocommunity.pack.dart" },
  { import = "astrocommunity.search.grug-far-nvim" },
  { import = "astrocommunity.git.diffview-nvim" },
  {
    "sindrets/diffview.nvim",
    opts = {
      keymaps = {
        view = {
          { "n", "q", "<Cmd>DiffviewClose<CR>", { desc = "Close Diffview" } },
        },
        file_panel = {
          { "n", "q", "<Cmd>DiffviewClose<CR>", { desc = "Close Diffview" } },
        },
        file_history_panel = {
          { "n", "q", "<Cmd>DiffviewClose<CR>", { desc = "Close Diffview" } },
        },
      },
      hooks = {
        diff_buf_win_enter = function(_, winid, ctx)
          vim.wo[winid].foldcolumn = "0"
          if ctx.layout_name == "diff2_horizontal" then apply_vscode_diff_hl(winid, ctx.symbol == "a") end
        end,
      },
    },
  },
  { import = "astrocommunity.scrolling.vim-smoothie" },
}
