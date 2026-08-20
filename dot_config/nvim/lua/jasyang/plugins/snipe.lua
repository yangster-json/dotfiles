return {
  "leath-dub/snipe.nvim",
  config = function()
    local snipe = require("snipe")
    snipe.setup({
      ui = {
        max_width = -1,
        position = "cursor",
      },
      hints = {
        dictionary = "asdfjkl;ghnmxcvbziowerutyqp",
      },
    })

    vim.keymap.set("n", "<leader>fb", snipe.open_buffer_menu, { desc = "Snipe buffers" })
  end,
}
