return {
  'augmentcode/augment.vim',
  branch = "prerelease",
  config = function()
    local keymap = vim.keymap
    vim.g.augment_workspace_folders = { vim.fn.getcwd() }
    keymap.set("i", "<C-y>", "<cmd>call augment#Accept()<cr>", { desc = "Accept augment suggestion" })
    keymap.set("n", "<leader>ac", "<cmd>Augment chat<cr>", { desc = "Augment chat" })
    keymap.set("v", "<leader>ay", "<cmd>Augment chat<cr>", { desc = "Augment chat" })
    keymap.set("n", "<leader>an", "<cmd>Augment chat-new<cr>", { desc = "Augment chat-new" })
    keymap.set("n", "<leader>at", "<cmd>Augment chat-toggle<cr>", { desc = "Augment chat-toggle" })
  end,
}
