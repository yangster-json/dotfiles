return {
  "coder/claudecode.nvim",
  dependencies = { "folke/snacks.nvim" },
  opts = {
    -- only nvim-spawned sessions default to sonnet; plain `claude` in a shell
    -- keeps its own default. <leader>am switches model mid-session.
    terminal_cmd = "claude --model sonnet",
    terminal = {
      snacks_win_opts = {
        keys = {
          -- buffer-local, so it only shadows <C-q> inside the claude window.
          -- claudecode patches hide() to keep its own state in sync.
          claude_hide = {
            "<C-q>",
            function(self)
              self:hide()
            end,
            mode = { "n", "t" },
            desc = "Hide Claude",
          },
        },
      },
    },
  },
  -- cmd stubs so :ClaudeCode works before any keymap is pressed
  cmd = {
    "ClaudeCode",
    "ClaudeCodeFocus",
    "ClaudeCodeSelectModel",
    "ClaudeCodeAdd",
    "ClaudeCodeSend",
    "ClaudeCodeTreeAdd",
    "ClaudeCodeStatus",
    "ClaudeCodeStart",
    "ClaudeCodeStop",
    "ClaudeCodeOpen",
    "ClaudeCodeClose",
    "ClaudeCodeDiffAccept",
    "ClaudeCodeDiffDeny",
    "ClaudeCodeCloseAllDiffs",
  },
  -- The terminal opens focused and in insert mode, so <leader>a* keys are typed
  -- into Claude's prompt, not seen by nvim. To get back to nvim, either navigate
  -- out with <C-h/j/k/l> (mapped for terminal mode in tmux.lua) or press
  -- <C-\><C-n> for normal mode, then <leader>ac to hide it.
  keys = {
    { "<leader>a", nil, desc = "AI/Claude Code" },
    { "<leader>ac", "<cmd>ClaudeCode<cr>", desc = "Toggle Claude" },
    { "<leader>af", "<cmd>ClaudeCodeFocus<cr>", desc = "Focus Claude" },
    { "<leader>ar", "<cmd>ClaudeCode --resume<cr>", desc = "Resume Claude" },
    { "<leader>aC", "<cmd>ClaudeCode --continue<cr>", desc = "Continue Claude" },
    { "<leader>am", "<cmd>ClaudeCodeSelectModel<cr>", desc = "Select Claude model" },
    { "<leader>ab", "<cmd>ClaudeCodeAdd %<cr>", desc = "Add current buffer" },
    { "<leader>as", "<cmd>ClaudeCodeSend<cr>", mode = "v", desc = "Send to Claude" },
    -- add file from a tree/explorer buffer
    {
      "<leader>as",
      "<cmd>ClaudeCodeTreeAdd<cr>",
      desc = "Add file",
      ft = { "NvimTree", "oil", "netrw", "snacks_picker_list" },
    },
    { "<leader>aa", "<cmd>ClaudeCodeDiffAccept<cr>", desc = "Accept diff" },
    { "<leader>ad", "<cmd>ClaudeCodeDiffDeny<cr>", desc = "Deny diff" },
  },
}
