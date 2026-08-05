return {
  "aserowy/tmux.nvim",

  config = function()
    require("tmux").setup({
      copy_sync = {
        -- enables copy sync. by default, all registers are synchronized.
        -- to control which registers are synced, see the `sync_*` options.
        enable = true,

        -- ignore specific tmux buffers e.g. buffer0 = true to ignore the
        -- first buffer or named_buffer_name = true to ignore a named tmux
        -- buffer with name named_buffer_name :)
        ignore_buffers = { empty = false },

        -- TMUX >= 3.2: all yanks (and deletes) will get redirected to system
        -- clipboard by tmux
        redirect_to_clipboard = true,

        -- offset controls where register sync starts
        -- e.g. offset 2 lets registers 0 and 1 untouched
        register_offset = 0,

        -- overwrites vim.g.clipboard to redirect * and + to the system
        -- clipboard using tmux. If you sync your system clipboard without tmux,
        -- disable this option!
        sync_clipboard = true,

        -- synchronizes registers *, +, unnamed, and 0 till 9 with tmux buffers.
        sync_registers = true,

        -- synchronizes registers when pressing p and P.
        sync_registers_keymap_put = true,

        -- synchronizes registers when pressing (C-r) and ".
        sync_registers_keymap_reg = true,

        -- syncs deletes with tmux clipboard as well, it is adviced to
        -- do so. Nvim does not allow syncing registers 0 and 1 without
        -- overwriting the unnamed register. Thus, ddp would not be possible.
        sync_deletes = true,

        -- syncs the unnamed register with the first buffer entry from tmux.
        sync_unnamed = true,
      },
    })

    -- tmux.nvim only maps these in normal mode; mirror them for terminal
    -- buffers so you can navigate out of a claude/lazygit terminal
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
