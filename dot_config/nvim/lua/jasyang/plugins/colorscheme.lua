return {
  {
    "catppuccin/nvim",
    name = "catppuccin",
    priority = 1000,
    config = function()
      require("catppuccin").setup({
        flavour = "mocha",
        integrations = {
          bufferline = true,
          cmp = true,
          gitsigns = true,
          indent_blankline = { enabled = true },
          mason = true,
          noice = true,
          notify = true,
          render_markdown = true,
          telescope = { enabled = true },
          treesitter = true,
          trouble = true,
          which_key = true,
        },
        highlight_overrides = {
          mocha = function(colors)
            return {
              WinSeparator       = { fg = colors.surface1 },
              WinSeparatorActive = { fg = colors.mauve },
              -- Telescope: background matches editor, subtle rounded border
              TelescopeNormal        = { bg = colors.base },
              TelescopeBorder        = { fg = colors.surface1, bg = colors.base },
              TelescopePromptNormal  = { bg = colors.base },
              TelescopePromptBorder  = { fg = colors.surface1, bg = colors.base },
              TelescopeResultsNormal = { bg = colors.base },
              TelescopeResultsBorder = { fg = colors.surface1, bg = colors.base },
              TelescopePreviewNormal = { bg = colors.base },
              TelescopePreviewBorder = { fg = colors.surface1, bg = colors.base },
              TelescopeTitle         = { fg = colors.mauve, bg = colors.base },
              TelescopePromptTitle   = { fg = colors.mauve, bg = colors.base },
              CursorLineNr           = { fg = colors.mauve, style = { "bold" } },
              FloatBorder             = { fg = colors.mauve, bg = colors.base },
              PmenuSel                = { fg = colors.base, bg = colors.mauve },
              Search                  = { fg = colors.base, bg = colors.mauve },
              IncSearch               = { fg = colors.base, bg = colors.mauve },
              TabLineSel              = { fg = colors.base, bg = colors.mauve },
            }
          end,
        },
      })
      vim.cmd([[colorscheme catppuccin]])

      -- match split accent to mauve theme
      -- Skip floating windows (Telescope, cmp, etc.): they have borders, not
      -- WinSeparators, and blindly setting winhighlight would clobber the
      -- Normal:Telescope*Normal mappings those plugins rely on.
      local group = vim.api.nvim_create_augroup("ActiveWinSeparator", { clear = true })
      local function is_floating()
        return vim.api.nvim_win_get_config(0).relative ~= ""
      end
      local function patch_winhighlight(win, active)
        local whl = vim.wo[win].winhighlight
        whl = whl:gsub(",?WinSeparator:[^,]*", ""):gsub("^,", "")
        if active then
          whl = whl == "" and "WinSeparator:WinSeparatorActive"
                           or whl .. ",WinSeparator:WinSeparatorActive"
        end
        vim.wo[win].winhighlight = whl
      end
      vim.api.nvim_create_autocmd({ "WinEnter", "BufWinEnter" }, {
        group = group,
        callback = function()
          if is_floating() then return end
          patch_winhighlight(0, true)
        end,
      })
      vim.api.nvim_create_autocmd("WinLeave", {
        group = group,
        callback = function()
          if is_floating() then return end
          patch_winhighlight(0, false)
        end,
      })
    end,
  },
}
