return {
  "goolord/alpha-nvim",
  event = "VimEnter",
  config = function()
    local alpha = require("alpha")
    local dashboard = require("alpha.themes.dashboard")

    local function split(source, sep)
      local result, i = {}, 1
      while true do
        local a, b = source:find(sep)
        if not a then
          break
        end
        local candidat = source:sub(1, a - 1)
        if candidat ~= "" then
          result[i] = candidat
        end
        i = i + 1
        source = source:sub(b + 1)
      end
      if source ~= "" then
        result[i] = source
      end
      return result
    end

    -- Set header
    dashboard.section.header.val = {
      "                                                     ",
      "  ███╗   ██╗███████╗ ██████╗ ██╗   ██╗██╗███╗   ███╗ ",
      "  ████╗  ██║██╔════╝██╔═══██╗██║   ██║██║████╗ ████║ ",
      "  ██╔██╗ ██║█████╗  ██║   ██║██║   ██║██║██╔████╔██║ ",
      "  ██║╚██╗██║██╔══╝  ██║   ██║╚██╗ ██╔╝██║██║╚██╔╝██║ ",
      "  ██║ ╚████║███████╗╚██████╔╝ ╚████╔╝ ██║██║ ╚═╝ ██║ ",
      "  ╚═╝  ╚═══╝╚══════╝ ╚═════╝   ╚═══╝  ╚═╝╚═╝     ╚═╝ ",
      "                                                     ",
    }
    dashboard.section.footer.val = "⚡ Total plugins: " .. require("lazy").stats().count
    -- AlphaHeader/AlphaButtons/AlphaShortcut/AlphaFooter come from catppuccin
    dashboard.section.header.opts.hl = "AlphaHeader"
    dashboard.section.footer.opts.hl = "AlphaFooter"
    dashboard.section.buttons.val = {
      dashboard.button("r", "🕘  Open last session", "<cmd>AutoSession restore<CR>"),
      dashboard.button("s", "🔎  Find string", ":Telescope live_grep<CR>"),
      dashboard.button("f", "🔍  Find file", ":Telescope find_files<CR>"),
      dashboard.button("e", "📁  Open file explorer", ":NvimTreeToggle<CR>"),
      dashboard.button("n", "📄  New file", ":enew<CR>"),
      dashboard.button("b", "🔖  Jump to bookmarks", ":Telescope marks<CR>"),
      dashboard.button("p", "🧩  Update plugins", ":Lazy sync<CR>"),
      dashboard.button("q", "👋  Exit", ":qa<CR>"),
    }
    for _, button in ipairs(dashboard.section.buttons.val) do
      button.opts.hl = "AlphaButtons"
      button.opts.hl_shortcut = "AlphaShortcut"
    end

    dashboard.config.layout = {
      { type = "padding", val = 2 },
      dashboard.section.header,
      { type = "padding", val = 2 },
      dashboard.section.buttons,
      { type = "padding", val = 1 },
      dashboard.section.footer,
    }
    alpha.setup(dashboard.config)

    -- update footer once lazy has measured startup time
    vim.api.nvim_create_autocmd("User", {
      pattern = "LazyVimStarted",
      callback = function()
        local stats = require("lazy").stats()
        local ms = math.floor(stats.startuptime * 100 + 0.5) / 100
        dashboard.section.footer.val = "⚡ " .. stats.loaded .. "/" .. stats.count .. " plugins loaded in " .. ms .. "ms"
        pcall(vim.cmd.AlphaRedraw)
      end,
    })

    -- Disable folding on alpha buffer
    vim.cmd([[autocmd FileType alpha setlocal nofoldenable]])

    vim.api.nvim_create_augroup("vimrc_alpha", { clear = true })
    vim.api.nvim_create_autocmd({ "User" }, {
      group = "vimrc_alpha",
      pattern = "AlphaReady",
      callback = function()
        if vim.fn.executable("onefetch") ~= 1 then
          return
        end
        local cmd = [[onefetch 2>/dev/null | sed 's/\x1B[@A-Z\\\]^_]\|\x1B\[[0-9:;<=>?]*[-!"#$%&'"'"'()*+,.\/]*[][\\@A-Z^_`a-z{|}~]//g']]
        vim.system(
          { "sh", "-c", cmd },
          { text = true },
          vim.schedule_wrap(function(obj)
            if obj.code ~= 0 or not obj.stdout or obj.stdout == "" then
              return
            end
            local header = split(obj.stdout, "\n")
            if next(header) ~= nil then
              require("alpha.themes.dashboard").section.header.val = header
              require("alpha").redraw()
            end
          end)
        )
      end,
      once = true,
    })
  end,
}
