return {
  "nvim-lualine/lualine.nvim",
  dependencies = { "nvim-tree/nvim-web-devicons", "catppuccin/nvim" },
  config = function()
    local lualine = require("lualine")
    local lazy_status = require("lazy.status")
    local C = require("catppuccin.palettes").get_palette("mocha")

    local catppuccin_theme = {
      normal = {
        a = { bg = C.mauve,     fg = C.base, gui = "bold" },
        b = { bg = C.surface0,  fg = C.mauve },
        c = { bg = C.surface0,  fg = C.text },
        y = { bg = C.maroon,    fg = C.base, gui = "bold" },
        z = { bg = C.rosewater, fg = C.base, gui = "bold" },
      },
      insert = {
        a = { bg = C.mauve,     fg = C.base, gui = "bold" },
        b = { bg = C.surface0,  fg = C.mauve },
        y = { bg = C.maroon,    fg = C.base, gui = "bold" },
        z = { bg = C.rosewater, fg = C.base, gui = "bold" },
      },
      terminal = {
        a = { bg = C.mauve,     fg = C.base, gui = "bold" },
        b = { bg = C.surface0,  fg = C.mauve },
        y = { bg = C.maroon,    fg = C.base, gui = "bold" },
        z = { bg = C.rosewater, fg = C.base, gui = "bold" },
      },
      command = {
        a = { bg = C.mauve,     fg = C.base, gui = "bold" },
        b = { bg = C.surface0,  fg = C.mauve },
        y = { bg = C.maroon,    fg = C.base, gui = "bold" },
        z = { bg = C.rosewater, fg = C.base, gui = "bold" },
      },
      visual = {
        a = { bg = C.mauve,     fg = C.base, gui = "bold" },
        b = { bg = C.surface0,  fg = C.mauve },
        y = { bg = C.maroon,    fg = C.base, gui = "bold" },
        z = { bg = C.rosewater, fg = C.base, gui = "bold" },
      },
      replace = {
        a = { bg = C.mauve,     fg = C.base, gui = "bold" },
        b = { bg = C.surface0,  fg = C.mauve },
        y = { bg = C.maroon,    fg = C.base, gui = "bold" },
        z = { bg = C.rosewater, fg = C.base, gui = "bold" },
      },
      inactive = {
        a = { bg = C.mantle, fg = C.mauve },
        b = { bg = C.mantle, fg = C.surface0, gui = "bold" },
        c = { bg = C.mantle, fg = C.overlay0 },
      },
    }

    lualine.setup({
      options = {
        theme = catppuccin_theme,
        section_separators = { left = "", right = "" },
        component_separators = { left = "", right = "" },
      },
      sections = {
        lualine_x = {
          {
            lazy_status.updates,
            cond = lazy_status.has_updates,
            color = { fg = "#ff9e64" },
          },
          { "filetype" },
        },
        lualine_y = {
          {
            function()
              return "󰉋 " .. vim.fn.fnamemodify(vim.fn.getcwd(), ":t")
            end,
          },
        },
        lualine_z = {
          { "location" },
        },
      },
    })
  end,
}
