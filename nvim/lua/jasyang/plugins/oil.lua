return {
  "stevearc/oil.nvim",
  dependencies = { "nvim-tree/nvim-web-devicons" },
  lazy = false,
  keys = {
    { "-", "<cmd>Oil<cr>", desc = "Oil: open parent directory" },
    { "<leader>o", "<cmd>Oil --float<cr>", desc = "Oil: floating" },
  },
  opts = {
    default_file_explorer = true,
    view_options = {
      show_hidden = true,
    },
  },
}
