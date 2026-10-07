-- syntax-highlighted diffs only; github repo goes away 2026-10-31
return {
  "barrettruth/diffs.nvim",
  url = "https://forge.barrettruth.com/barrettruth/diffs.nvim",
  version = "*",
  lazy = false, -- plugin lazy-loads itself
  init = function()
    vim.g.diffs = {
      integrations = { gitsigns = true },
      -- diffview owns merge conflicts
      conflict = { enabled = false },
    }
  end,
  config = function()
    -- keep diffview's own colors in &diff windows
    local runtime = require("diffs.runtime")
    runtime.attach_diff = function() end
    runtime.detach_diff = function() end
  end,
}
