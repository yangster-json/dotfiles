return {
  "neovim/nvim-lspconfig",
  event = { "BufReadPre", "BufNewFile" },
  dependencies = {
    "hrsh7th/cmp-nvim-lsp",
    { "antosha417/nvim-lsp-file-operations", config = true },
    { "folke/lazydev.nvim", ft = "lua", opts = {
      library = {
        { path = "${3rd}/luv/library", words = { "vim%.uv" } },
      },
    } },
  },
  config = function()

    local cmp_nvim_lsp = require("cmp_nvim_lsp")

    local keymap = vim.keymap

    vim.api.nvim_create_autocmd("LspAttach", {
      group = vim.api.nvim_create_augroup("UserLspConfig", {}),
      callback = function(ev)

        local opts = { buffer = ev.buf, silent = true }
        local client = vim.lsp.get_client_by_id(ev.data.client_id)

        opts.desc = "Show LSP references"
        keymap.set("n", "gR", "<cmd>Glance references<CR>", opts)

        opts.desc = "Show document symbols"
        keymap.set("n", "gO", vim.lsp.buf.document_symbol, opts)

        opts.desc = "LSP code action"
        keymap.set({ "n", "x" }, "gra", vim.lsp.buf.code_action, opts)

        opts.desc = "LSP rename symbol"
        keymap.set("n", "grn", vim.lsp.buf.rename, opts)

        opts.desc = "LSP references"
        keymap.set("n", "grr", vim.lsp.buf.references, opts)

        opts.desc = "LSP implementations"
        keymap.set("n", "gri", vim.lsp.buf.implementation, opts)

        opts.desc = "LSP type definition"
        keymap.set("n", "grt", vim.lsp.buf.type_definition, opts)

        opts.desc = "Go to declaration"
        keymap.set("n", "gD", vim.lsp.buf.declaration, opts)

        opts.desc = "Show LSP definitions"
        keymap.set("n", "gd", "<cmd>Glance definitions<CR>", opts)

        opts.desc = "Show LSP implementations"
        keymap.set("n", "gi", "<cmd>Glance implementations<CR>", opts)

        opts.desc = "Show LSP type definitions"
        keymap.set("n", "gt", "<cmd>Glance type_definitions<CR>", opts)

        opts.desc = "See available code actions"
        keymap.set({ "n", "v" }, "<leader>ca", vim.lsp.buf.code_action, opts)

        opts.desc = "Smart rename"
        keymap.set("n", "<leader>rn", vim.lsp.buf.rename, opts)

        opts.desc = "Show buffer diagnostics"
        keymap.set("n", "<leader>D", "<cmd>Telescope diagnostics bufnr=0<CR>", opts)

        opts.desc = "Show line diagnostics"
        keymap.set("n", "<leader>d", vim.diagnostic.open_float, opts)

        opts.desc = "Go to previous diagnostic"
        keymap.set("n", "[d", function() vim.diagnostic.jump({ count = -1, float = true }) end, opts)

        opts.desc = "Go to next diagnostic"
        keymap.set("n", "]d", function() vim.diagnostic.jump({ count = 1, float = true }) end, opts)

        opts.desc = "Show documentation for what is under cursor"
        keymap.set("n", "K", vim.lsp.buf.hover, opts)

        opts.desc = "Restart LSP"
        keymap.set("n", "<leader>rs", ":LspRestart<CR>", opts)

        if client and client.name == "svelte" then
          vim.api.nvim_create_autocmd("BufWritePost", {
            pattern = { "*.js", "*.ts" },
            callback = function(ctx)
              client:notify("$/onDidChangeTsOrJsFile", { uri = ctx.match })
            end,
          })
        end
      end,
    })

    local capabilities = cmp_nvim_lsp.default_capabilities()

    vim.diagnostic.config({
      float = { border = "rounded" },
      signs = {
        text = {
          [vim.diagnostic.severity.ERROR] = " ",
          [vim.diagnostic.severity.WARN] = " ",
          [vim.diagnostic.severity.HINT] = "󰠠 ",
          [vim.diagnostic.severity.INFO] = " ",
        },
      },
    })

    vim.lsp.config('*', {
      capabilities = capabilities,
    })

    vim.lsp.config('graphql', {
      filetypes = { "graphql", "gql", "svelte", "typescriptreact", "javascriptreact" },
    })

    vim.lsp.config('emmet_ls', {
      filetypes = { "html", "typescriptreact", "javascriptreact", "css", "sass", "scss", "less", "svelte" },
    })

    vim.lsp.config('clangd', {
      capabilities = { offsetEncoding = { "utf-8" } },
    })

    vim.lsp.config('lua_ls', {
      settings = {
        Lua = {
          completion = {
            callSnippet = "Replace",
          },
        },
      },
    })

    vim.lsp.enable({
      'html',
      'cssls',
      'tailwindcss',
      'svelte',
      'lua_ls',
      'graphql',
      'emmet_ls',
      'prismals',
      'pyright',
      'ruff',
      'ast_grep',
      'clangd',
      'bashls',
      'yamlls',
      'ltex',
    })
  end,
}
