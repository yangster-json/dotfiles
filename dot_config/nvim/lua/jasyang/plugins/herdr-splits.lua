-- herdr's tmux.nvim counterpart: nav + resize across nvim splits and herdr
-- panes. only loads inside herdr, so tmux.nvim stays the tmux-side owner of
-- <C-hjkl> (see plugins/tmux.lua)
-- needs the herdr-side half: herdr plugin install lmilojevicc/herdr-splits.nvim
return {
  "lmilojevicc/herdr-splits.nvim",
  cond = vim.env.HERDR_ENV == "1",
  event = "VeryLazy",

  config = function()
    require("herdr-splits").setup({
      at_edge = "stop",        -- wrapping past an edge is disorienting with 3+ panes
      neovim_amount = 3,       -- matches the old resize-pane -L 3 binds
      ignored_filetypes = {
        "NvimTree",
        "Trouble",
        "quickfix",
      },
    })

    -- mirror the nav keys into terminal buffers so you can leave a claude or
    -- lazygit terminal, same reason tmux.lua does it
    local nav = {
      ["<C-h>"] = "move_cursor_left",
      ["<C-j>"] = "move_cursor_down",
      ["<C-k>"] = "move_cursor_up",
      ["<C-l>"] = "move_cursor_right",
    }
    for key, move in pairs(nav) do
      vim.keymap.set("t", key, function()
        require("herdr-splits")[move]()
      end, { desc = "Navigate out of terminal (" .. move .. ")" })
    end
  end,

  keys = {
    { "<C-h>", function() require("herdr-splits").move_cursor_left() end, desc = "Navigate left" },
    { "<C-j>", function() require("herdr-splits").move_cursor_down() end, desc = "Navigate down" },
    { "<C-k>", function() require("herdr-splits").move_cursor_up() end, desc = "Navigate up" },
    { "<C-l>", function() require("herdr-splits").move_cursor_right() end, desc = "Navigate right" },
    { "<M-h>", function() require("herdr-splits").resize_left() end, desc = "Resize left" },
    { "<M-j>", function() require("herdr-splits").resize_down() end, desc = "Resize down" },
    { "<M-k>", function() require("herdr-splits").resize_up() end, desc = "Resize up" },
    { "<M-l>", function() require("herdr-splits").resize_right() end, desc = "Resize right" },
  },
}
