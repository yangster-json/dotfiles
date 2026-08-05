return {
  'augmentcode/augment.vim',
  branch = "prerelease",
  config = function()
    local keymap = vim.keymap
    vim.g.augment_workspace_folders = { vim.fn.getcwd() }
    -- inline completion only; <leader>a* belongs to claudecode.nvim now
    keymap.set("i", "<C-y>", "<cmd>call augment#Accept()<cr>", { desc = "Accept augment suggestion" })
  end,
}
