return {
  {
    "3rd/image.nvim",
    enabled = not vim.g.vscode,
    lazy = false,
    build = false,
    opts = {
      backend = "kitty", -- kitty 또는 ueberzug
      processor = "magick_cli",
      integrations = {
        markdown = {
          enabled = false,
          clear_in_insert_mode = false,
          download_remote_images = true,
          only_render_image_at_cursor = false,
          filetypes = { "markdown", "vimwiki" },
        },
        asciidoc = { enabled = false },
        typst = { enabled = false },
        neorg = { enabled = false },
        syslang = { enabled = false },
        html = { enabled = false },
        css = { enabled = false },
        org = { enabled = false },
      },
      max_width = nil,
      max_height = nil,
      max_width_window_percentage = nil,
      max_height_window_percentage = 50,
      window_overlap_clear_enabled = true,
      window_overlap_clear_ft_ignore = { "cmp_menu", "cmp_docs", "" },
      editor_only_render_when_focused = false,
      tmux_show_only_in_active_window = false,
      hijack_file_patterns = {},
    },
  },
}
