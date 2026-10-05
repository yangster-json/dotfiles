return {
  "tpope/vim-fugitive",
  lazy = false, -- keep :Git available without a keypress
  keys = {
    { "<leader>gg", "<cmd>Git<cr>", desc = "Fugitive: status" },
    { "<leader>gb", "<cmd>Git blame<cr>", desc = "Fugitive: blame" },
    { "<leader>gl", "<cmd>Gclog %<cr>", desc = "Fugitive: file log (qflist)" },
    { "<leader>gL", "<cmd>Git log --oneline --graph --decorate<cr>", desc = "Fugitive: repo log" },
    { "<leader>gw", "<cmd>Gwrite<cr>", desc = "Fugitive: stage file" },
  },
}
