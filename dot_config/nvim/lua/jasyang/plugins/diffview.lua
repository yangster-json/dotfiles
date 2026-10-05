-- maintained fork; sindrets/diffview.nvim unmaintained since 2024
return {
  "dlyongemallo/diffview-plus.nvim",
  version = "*",
  cmd = {
    "DiffviewOpen",
    "DiffviewClose",
    "DiffviewToggle",
    "DiffviewToggleFiles",
    "DiffviewFocusFiles",
    "DiffviewRefresh",
    "DiffviewFileHistory",
    "DiffviewDiffFiles",
    "DiffviewMergeFiles",
  },
  keys = {
    { "<leader>gd", "<cmd>DiffviewOpen<cr>", desc = "Diffview: working tree" },
    {
      "<leader>gD",
      function()
        vim.ui.input({ prompt = "Diffview rev: ", default = "origin/HEAD...HEAD" }, function(rev)
          if rev and rev ~= "" then
            vim.cmd("DiffviewOpen " .. rev)
          end
        end)
      end,
      desc = "Diffview: against rev (PR review)",
    },
    { "<leader>gh", "<cmd>DiffviewFileHistory %<cr>", desc = "Diffview: file history" },
    { "<leader>gh", ":DiffviewFileHistory<cr>", mode = "x", desc = "Diffview: range history" },
    { "<leader>gH", "<cmd>DiffviewFileHistory<cr>", desc = "Diffview: repo history" },
    { "<leader>gc", "<cmd>DiffviewClose<cr>", desc = "Diffview: close" },
  },
  opts = {
    enhanced_diff_hl = true,
    view = {
      merge_tool = { layout = "diff3_mixed" },
    },
  },
}
