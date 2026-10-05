local parsers = {
  "json",
  "javascript",
  "typescript",
  "tsx",
  "yaml",
  "html",
  "css",
  "prisma",
  "markdown",
  "markdown_inline",
  "svelte",
  "graphql",
  "bash",
  "lua",
  "vim",
  "dockerfile",
  "gitignore",
  "query",
  "vimdoc",
  "c",
  "cpp",
  "python",
}

-- skip treesitter on files over 1 MiB
local function too_big(buf)
  local stat = vim.uv.fs_stat(vim.api.nvim_buf_get_name(buf))
  return stat and stat.size > 1024 * 1024
end

return {
  {
    "nvim-treesitter/nvim-treesitter",
    branch = "main",
    lazy = false, -- main does not support lazy-loading
    build = ":TSUpdate",
    config = function()
      require("nvim-treesitter").install(parsers)

      vim.api.nvim_create_autocmd("FileType", {
        group = vim.api.nvim_create_augroup("jasyang_treesitter", { clear = true }),
        callback = function(args)
          local buf = args.buf
          local lang = vim.treesitter.language.get_lang(vim.bo[buf].filetype)
          if not lang or too_big(buf) or not vim.treesitter.language.add(lang) then
            return
          end
          vim.treesitter.start(buf, lang)
          if vim.treesitter.query.get(lang, "indents") then
            vim.bo[buf].indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
          end
        end,
      })

      -- incremental selection; nvim 0.12 also has native an/in
      vim.keymap.set("n", "<C-space>", "van", { remap = true, desc = "Start treesitter selection" })
      vim.keymap.set("x", "<C-space>", "an", { remap = true, desc = "Expand treesitter selection" })
      vim.keymap.set("x", "<bs>", "in", { remap = true, desc = "Shrink treesitter selection" })
    end,
  },
  {
    "windwp/nvim-ts-autotag",
    event = { "BufReadPre", "BufNewFile" },
    opts = {},
  },
  {
    "JoosepAlviste/nvim-ts-context-commentstring",
    event = { "BufReadPre", "BufNewFile" },
    init = function()
      vim.g.skip_ts_context_commentstring_module = true
    end,
    config = function()
      require("ts_context_commentstring").setup({ enable_autocmd = false })
      -- make native gc use context-aware commentstring
      local get_option = vim.filetype.get_option
      ---@diagnostic disable-next-line: duplicate-set-field
      vim.filetype.get_option = function(filetype, option)
        return option == "commentstring"
            and require("ts_context_commentstring.internal").calculate_commentstring()
          or get_option(filetype, option)
      end
    end,
  },
}
