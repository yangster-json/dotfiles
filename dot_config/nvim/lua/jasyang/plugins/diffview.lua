-- maintained fork; sindrets/diffview.nvim unmaintained since 2024
return {
  "dlyongemallo/diffview-plus.nvim",
  version = "*",
  cmd = { "DiffviewOpen", "DiffviewClose", "DiffviewFileHistory" },
  keys = {
    { "<leader>gd", "<cmd>DiffviewOpen<cr>", desc = "Diff working tree" },
    {
      "<leader>gD",
      function()
        vim.ui.input({ prompt = "Diff against: ", default = "origin/HEAD...HEAD" }, function(rev)
          if rev and rev ~= "" then
            vim.cmd("DiffviewOpen " .. rev)
          end
        end)
      end,
      desc = "Diff against rev (PR review)",
    },
    { "<leader>gh", "<cmd>DiffviewFileHistory %<cr>", desc = "File history" },
    { "<leader>gh", ":DiffviewFileHistory<cr>", mode = "x", desc = "Line history" },
    { "<leader>gH", "<cmd>DiffviewFileHistory<cr>", desc = "Repo history" },
  },
  opts = function()
    local actions = require("diffview.actions")

    -- T: current file in difftastic (structural diff)
    local function difftastic()
      local view = require("diffview.lib").get_current_view()
      local entry = view and view:infer_cur_file()
      if not (entry and entry.revs) then
        return vim.notify("difftastic: no file under cursor", vim.log.levels.WARN)
      end
      local RevType = require("diffview.vcs.rev").RevType
      local top = entry.adapter.ctx.toplevel
      local dir = vim.fn.tempname()
      vim.fn.mkdir(dir .. "/a", "p")
      vim.fn.mkdir(dir .. "/b", "p")
      -- keep the extension so difft detects the language
      local function side(rev, path, tag)
        if rev.type == RevType.LOCAL then
          return entry.absolute_path
        end
        local out = ("%s/%s/%s"):format(dir, tag, vim.fn.fnamemodify(path, ":t"))
        local obj = rev.type == RevType.STAGE and (":%d:%s"):format(rev.stage, path)
          or (rev:object_name() .. ":" .. path)
        local res = vim.system({ "git", "-C", top, "show", obj }, { text = false }):wait()
        if res.code ~= 0 then
          return "/dev/null" -- added or deleted on this side
        end
        local f = assert(io.open(out, "wb"))
        f:write(res.stdout)
        f:close()
        return out
      end
      local a = side(entry.revs.a, entry.oldpath or entry.path, "a")
      local b = side(entry.revs.b, entry.path, "b")
      local cmd = ("difft --color=always --background=dark --width=%d %s %s . . %s . . | less -R; rm -rf %s")
        :format(
          math.floor(vim.o.columns * 0.95) - 2,
          vim.fn.shellescape(entry.path), -- git-style args so the title shows the real path
          vim.fn.shellescape(a),
          vim.fn.shellescape(b),
          vim.fn.shellescape(dir)
        )
      Snacks.terminal.open({ "sh", "-c", cmd }, { win = { width = 0.95, height = 0.9 } })
    end

    -- ]f/[f pairs with ]c/[c; q closes the tab
    local keys = {
      { "n", "]f", actions.select_next_entry, { desc = "Next file" } },
      { "n", "[f", actions.select_prev_entry, { desc = "Prev file" } },
      { "n", "q", "<cmd>DiffviewClose<cr>", { desc = "Close diffview" } },
      { "n", "T", difftastic, { desc = "Open in difftastic" } },
      -- don't shadow nvim-tree <leader>e* / <leader>bp
      { "n", "<leader>e", false },
      { "n", "<leader>b", false },
    }
    return {
      enhanced_diff_hl = true,
      view = { merge_tool = { layout = "diff3_mixed" } },
      keymaps = {
        view = vim.deepcopy(keys),
        file_panel = vim.deepcopy(keys),
        file_history_panel = vim.deepcopy(keys),
      },
    }
  end,
}
