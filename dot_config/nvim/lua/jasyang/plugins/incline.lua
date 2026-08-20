return {
  "b0o/incline.nvim",
  dependencies = { "nvim-tree/nvim-web-devicons" },
  event = "VeryLazy",
  config = function()
    local devicons = require("nvim-web-devicons")
    local C = require("catppuccin.palettes").get_palette("mocha")
    require("incline").setup({
      highlight = {
        groups = {
          InclineNormal   = { guibg = C.surface0 },
          InclineNormalNC = { guibg = C.surface0 },
        },
      },
      render = function(props)
        local filename = vim.fn.fnamemodify(vim.api.nvim_buf_get_name(props.buf), ":t")
        if filename == "" then
          filename = "[No Name]"
        end
        local ft_icon, ft_color = devicons.get_icon_color(filename)
        local modified = vim.bo[props.buf].modified
        return {
          ft_icon and { " ", ft_icon, " ", guifg = ft_color } or "",
          { filename, gui = modified and "bold,italic" or "bold" },
          modified and { "  ", guifg = "#ff9e64" } or "",
          " ",
        }
      end,
      window = {
        padding = 0,
        margin = { vertical = 0, horizontal = 1 },

        overlap = { borders = false },
      },
    })
  end,
}
