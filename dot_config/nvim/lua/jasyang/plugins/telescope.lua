return {
  "nvim-telescope/telescope.nvim",
  branch = "0.1.x",
  dependencies = {
    "nvim-lua/plenary.nvim",
    { "nvim-telescope/telescope-fzf-native.nvim", build = "make" },
    "nvim-tree/nvim-web-devicons",
    "folke/todo-comments.nvim",
  },
  config = function()
    local telescope = require("telescope")
    local actions = require("telescope.actions")

    telescope.setup({
      defaults = {
        path_display = { "smart" },
        borderchars = { "─", "│", "─", "│", "╭", "╮", "╯", "╰" },
        mappings = {
          i = {
            ["<C-k>"] = actions.move_selection_previous, -- move to prev result
            ["<C-j>"] = actions.move_selection_next, -- move to next result
            ["<C-q>"] = actions.send_selected_to_qflist + actions.open_qflist,
          },
        },
      },
    })

    telescope.load_extension("fzf")

    -- set keymaps
    local keymap = vim.keymap -- for conciseness

    keymap.set("n", "<leader>ff", "<cmd>Telescope find_files hidden=true<cr>", { desc = "Fuzzy find files in cwd (incl. hidden)" })
    keymap.set("n", "<leader>fa", "<cmd>Telescope find_files hidden=true no_ignore=true<cr>", { desc = "Find all files (incl. hidden + gitignored)" })
    keymap.set("n", "<leader>fF", "<cmd>Telescope git_files git_command={'git','ls-tree','-r','HEAD','--name-only'}<cr>", { desc = "Find committed files (HEAD)" })
    keymap.set("n", "<leader>fr", "<cmd>Telescope oldfiles<cr>", { desc = "Fuzzy find recent files" })
    keymap.set("n", "<leader>fs", "<cmd>Telescope live_grep<cr>", { desc = "Find string in cwd" })
    keymap.set("n", "<leader>fS", function()
      local root = vim.fn.systemlist({ "git", "rev-parse", "--show-toplevel" })[1]
      if vim.v.shell_error ~= 0 or not root or root == "" then
        vim.notify("Not in a git repository", vim.log.levels.WARN)
        return
      end
      local files = vim.fn.systemlist({ "git", "-C", root, "ls-tree", "-r", "HEAD", "--name-only" })
      if vim.v.shell_error ~= 0 or #files == 0 then
        vim.notify("No committed files on HEAD", vim.log.levels.WARN)
        return
      end
      for i, f in ipairs(files) do
        files[i] = root .. "/" .. f -- absolute so search paths are cwd-independent
      end
      require("telescope.builtin").live_grep({ search_dirs = files, prompt_title = "Live Grep (committed)" })
    end, { desc = "Find string in committed files (HEAD)" })
    keymap.set("n", "<leader>fc", "<cmd>Telescope grep_string<cr>", { desc = "Find string under cursor in cwd" })
    keymap.set("n", "<leader>ft", "<cmd>TodoTelescope<cr>", { desc = "Find todos" })
    keymap.set("n", "<leader>fB", "<cmd>Telescope buffers<cr>", { desc = "Find buffer (Telescope)" })
  end,
}
