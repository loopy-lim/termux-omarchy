-- 저장 전에 순서대로 적용할 코드 액션 종류예요. source.fixAll 이 eslint/ts 의 fixAll 을 모두 포함해요
local CODE_ACTION_KINDS = { "source.fixAll", "source.organizeImports" }

local FILETYPES = {
  astro = true,
  javascript = true,
  javascriptreact = true,
  typescript = true,
  typescriptreact = true,
  json = true,
  jsonc = true,
  css = true,
  scss = true,
}

-- kind 에 해당하는 코드 액션을 모든 LSP 클라이언트에 동기로 요청해서 선택 메뉴 없이 바로 적용해요
local function apply_code_actions_sync(buf, kind)
  for _, client in ipairs(vim.lsp.get_clients { bufnr = buf, method = "textDocument/codeAction" }) do
    local params = {
      textDocument = { uri = vim.uri_from_bufnr(buf) },
      range = {
        start = { line = 0, character = 0 },
        ["end"] = { line = vim.api.nvim_buf_line_count(buf), character = 0 },
      },
      context = { only = { kind }, diagnostics = {} },
    }
    local response = client:request_sync("textDocument/codeAction", params, 1000, buf)

    for _, action in ipairs(response and response.result or {}) do
      if not action.disabled then
        if not action.edit and client:supports_method("codeAction/resolve") then
          local resolved = client:request_sync("codeAction/resolve", action, 1000, buf)
          action = resolved and resolved.result or action
        end
        if action.edit then vim.lsp.util.apply_workspace_edit(action.edit, client.offset_encoding) end
        local command = type(action.command) == "table" and action.command or action
        if type(command.command) == "string" then
          client:request_sync("workspace/executeCommand", command, 1000, buf)
        end
      end
    end
  end
end

---@type LazySpec
return {
  {
    "AstroNvim/astrocore",
    ---@type AstroCoreOpts
    opts = {
      autocmds = {
        lint_code_actions_on_save = {
          {
            event = "BufWritePre",
            desc = "Apply lint fixes and organize imports before save",
            callback = function(args)
              if not FILETYPES[vim.bo[args.buf].filetype] then return end
              if vim.b[args.buf].lint_on_save == false then return end

              for _, kind in ipairs(CODE_ACTION_KINDS) do
                apply_code_actions_sync(args.buf, kind)
              end
            end,
          },
        },
      },
    },
  },
}
