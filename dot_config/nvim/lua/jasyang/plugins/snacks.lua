-- vim.ui.input / vim.ui.select (replaces archived dressing.nvim)
return {
  "folke/snacks.nvim",
  priority = 1000,
  lazy = false,
  opts = {
    input = { enabled = true },
    picker = { enabled = true, ui_select = true },
  },
}
