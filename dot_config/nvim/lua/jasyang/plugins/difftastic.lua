-- structural diffs; ignores reformatting
return {
  "clabby/difftastic.nvim",
  version = "*",
  dependencies = { "MunifTanjim/nui.nvim", "folke/snacks.nvim" },
  cmd = { "Difft", "DifftPick", "DifftPickRange", "DifftClose", "DifftUpdate" },
  keys = {
    { "<leader>gt", "<cmd>Difft<cr>", desc = "Difftastic: unstaged" },
    { "<leader>gT", "<cmd>Difft --staged<cr>", desc = "Difftastic: staged" },
    { "<leader>gp", "<cmd>DifftPick<cr>", desc = "Difftastic: pick commit" },
  },
  config = function()
    require("difftastic-nvim").setup({
      download = true,
      vcs = "git",
      snacks_picker = { enabled = true },
    })
  end,
}
