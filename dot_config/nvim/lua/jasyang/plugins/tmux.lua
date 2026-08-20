return {
  "aserowy/tmux.nvim",

  cond = vim.env.HERDR_ENV ~= "1",

  config = function()
    require("tmux").setup({
      copy_sync = {

        enable = true,

        ignore_buffers = { empty = false },

        redirect_to_clipboard = true,

        register_offset = 0,

        sync_clipboard = true,

        sync_registers = true,

        sync_registers_keymap_put = true,

        sync_registers_keymap_reg = true,

        sync_deletes = true,

        sync_unnamed = true,
      },
    })

    local nav = {
      ["<C-h>"] = "move_left",
      ["<C-j>"] = "move_bottom",
      ["<C-k>"] = "move_top",
      ["<C-l>"] = "move_right",
    }
    for key, move in pairs(nav) do
      vim.keymap.set("t", key, function()
        require("tmux")[move]()
      end, { desc = "Navigate out of terminal (" .. move .. ")" })
    end
  end
}
