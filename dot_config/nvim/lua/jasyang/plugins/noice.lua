return {
  "folke/noice.nvim",
  event = "VeryLazy",
  dependencies = {
    "MunifTanjim/nui.nvim",
    "rcarriga/nvim-notify",
  },
  config = function()
    require("notify").setup({
      background_colour = "#000000",
      top_down = false,
    })

    require("noice").setup({
      routes = {
        {
          filter = { event = "lsp", kind = "progress" },
          opts = { skip = true },
        },
        {
          filter = {
            event = "notify",
            find = "deprecated",
          },
          opts = { skip = true },
        },
        {
          filter = {
            event = "msg_show",
            find = "deprecated",
          },
          opts = { skip = true },
        },
      },
      lsp = {
        override = {
          ["vim.lsp.util.convert_input_to_markdown_lines"] = true,
          ["vim.lsp.util.stylize_markdown"] = true,
          ["cmp.entry.get_documentation"] = true,
        },
      },
      presets = {
        bottom_search = true,
        long_message_to_split = true,
        lsp_doc_border = true,
      },
      views = {
        cmdline_popup = {
          position = { row = "100%", col = "50%" },
          size = { width = 60, height = "auto" },
        },
        cmdline_popupmenu = {
          relative = "editor",
          position = { row = "90%", col = "50%" },
          size = { width = 60, height = 10 },
        },
      },
    })
  end,
}
