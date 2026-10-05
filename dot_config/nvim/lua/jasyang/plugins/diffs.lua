-- syntax-highlighted diffs in fugitive/gitsigns; github repo goes away 2026-10-31
return {
  "barrettruth/diffs.nvim",
  url = "https://forge.barrettruth.com/barrettruth/diffs.nvim",
  version = "*",
  -- plugin lazy-loads itself; config must exist before load
  init = function()
    vim.g.diffs = {
      integrations = {
        fugitive = true,
        gitsigns = true,
      },
      -- diffview-plus owns merge conflicts
      conflict = { enabled = false },
    }
  end,
  keys = {
    { "<leader>gu", "<Plug>(diffs-diff)", desc = "Diffs: file unified diff" },
    { "<leader>gU", "<Plug>(diffs-diff-vertical)", desc = "Diffs: file unified diff (vsplit)" },
  },
  lazy = false,
}
