local keymap = vim.keymap

keymap.set("n", "<leader>nh", ":nohl<CR>", { desc = "Clear search highlights" })

keymap.set("n", "<leader>fi", "<C-g>", { desc = "Show file info" })

for _, click in ipairs({
  "<LeftMouse>",
  "<LeftDrag>",
  "<LeftRelease>",
  "<2-LeftMouse>",
  "<3-LeftMouse>",
  "<4-LeftMouse>",
  "<RightMouse>",
}) do
  keymap.set({ "n", "v", "i" }, click, "<nop>", { desc = "Disable mouse click navigation" })
end

keymap.set({ "n", "v" }, "<leader>y", [["+y]], { desc = "copy to clipboard" })
keymap.set("n", "<leader>Y", [["+Y]], { desc = "copy to clipboard" })

keymap.set({ "n", "v" }, "X", [["_d]], { desc = "Delete to black hole register" })

keymap.set("n", "XX", [["_dd]], { desc = "Delete line to black hole register" })
keymap.set({ "n", "v" }, "x", [["_x]], { desc = "Delete char to black hole register" })
keymap.set("v", "<leader>p", [["_dP]], { desc = "Paste over selection, keep clipboard" })

keymap.set("n", "<leader>+", "<C-a>", { desc = "Increment number" })
keymap.set("n", "<leader>-", "<C-x>", { desc = "Decrement number" })

keymap.set("n", "<leader>sv", "<C-w>v", { desc = "Split window vertically" })
keymap.set("n", "<leader>sh", "<C-w>s", { desc = "Split window horizontally" })
keymap.set("n", "<leader>se", "<C-w>=", { desc = "Make splits equal size" })
keymap.set("n", "<leader>sx", "<cmd>close<CR>", { desc = "Close current split" })

keymap.set("n", "<leader>to", "<cmd>tabnew<CR>", { desc = "Open new tab" })
keymap.set("n", "<leader>tx", "<cmd>tabclose<CR>", { desc = "Close current tab" })
keymap.set("n", "<leader>tn", "<cmd>tabn<CR>", { desc = "Go to next tab" })
keymap.set("n", "<leader>tp", "<cmd>tabp<CR>", { desc = "Go to previous tab" })
keymap.set("n", "<leader>tf", "<cmd>tabnew %<CR>", { desc = "Open current buffer in new tab" })

keymap.set("n", "<leader>bp", function()
  local bufs = vim.fn.getbufinfo({ buflisted = 1 })
  table.sort(bufs, function(a, b) return a.lastused > b.lastused end)

  local keep = {}
  for i = 1, math.min(5, #bufs) do
    keep[bufs[i].bufnr] = true
  end
  for _, b in ipairs(bufs) do
    if b.windows and #b.windows > 0 then
      keep[b.bufnr] = true
    end
  end

  local deleted, skipped = 0, 0
  for _, b in ipairs(bufs) do
    if not keep[b.bufnr] then
      if b.changed == 1 then
        skipped = skipped + 1
      else
        local ok = pcall(vim.api.nvim_buf_delete, b.bufnr, {})
        if ok then deleted = deleted + 1 end
      end
    end
  end
  vim.notify(("Pruned %d buffer(s)%s"):format(deleted, skipped > 0 and (", skipped " .. skipped .. " modified") or ""))
end, { desc = "Prune buffers (keep 5 MRU + visible)" })
