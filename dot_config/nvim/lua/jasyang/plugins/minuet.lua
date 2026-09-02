local function env_file_value(path, name)
  local ok, lines = pcall(vim.fn.readfile, vim.fn.expand(path))
  if not ok then
    return nil
  end

  for _, raw in ipairs(lines) do
    local line = raw:gsub("^%s*export%s+", "")
    local value = line:match("^%s*" .. name .. "%s*=%s*(.-)%s*$")
    if value then
      local quote = value:sub(1, 1)
      if quote == '"' or quote == "'" then
        local closing = value:find(quote, 2, true)
        value = closing and value:sub(2, closing - 1) or value:sub(2)
      else
        value = value:gsub("%s+#.*$", ""):gsub("%s+$", "")
      end
      return value ~= "" and value or nil
    end
  end
end

local function cascade_router_key()
  return env_file_value("~/.config/everpure-foundry/router.env", "CASCADE_ROUTER_KEY")
end

local function minuet_provider()
  if cascade_router_key() then
    return "openai_compatible"
  end
  if vim.env.OPENAI_API_KEY and vim.env.OPENAI_API_KEY ~= "" then
    return "openai"
  end
  if vim.env.ANTHROPIC_API_KEY and vim.env.ANTHROPIC_API_KEY ~= "" then
    return "claude"
  end
  return nil
end

return {
  "milanglacier/minuet-ai.nvim",
  event = "InsertEnter",
  config = function()
    local provider = minuet_provider()
    local has_provider = provider ~= nil

    require("minuet").setup({
      provider = provider or "openai",
      request_timeout = 3,
      throttle = 1500,
      debounce = 500,
      n_completions = 1,
      context_window = 6000,
      enable_predicates = {
        function()
          return has_provider
        end,
      },
      provider_options = {
        openai = {
          api_key = "OPENAI_API_KEY",
          end_point = vim.env.MINUET_OPENAI_ENDPOINT or "https://api.openai.com/v1/chat/completions",
          model = vim.env.MINUET_OPENAI_MODEL or "gpt-4o-mini",
          optional = {
            max_tokens = 96,
          },
        },
        claude = {
          api_key = "ANTHROPIC_API_KEY",
          model = vim.env.MINUET_ANTHROPIC_MODEL or "claude-3-5-haiku-latest",
          optional = {
            max_tokens = 96,
          },
        },
        openai_compatible = {
          name = "Cascade",
          api_key = cascade_router_key,
          end_point = "https://pureroute.dev.purestorage.com/v1/chat/completions",
          model = "gpt-5.6-luna",
          optional = {
            max_tokens = 96,
            reasoning_effort = "none",
          },
          transform = {
            function(request)
              for _, message in ipairs(request.body.messages) do
                if message.role == "system" then
                  message.role = "developer"
                end
              end
              return request
            end,
          },
        },
      },
      virtualtext = {
        auto_trigger_ft = has_provider and { "*" } or {},
        auto_trigger_ignore_ft = { "gitcommit", "help", "markdown" },
        keymap = {
          accept = "<C-y>",
          dismiss = "<C-]>",
        },
      },
    })

    if not has_provider then
      vim.notify(
        "Minuet disabled: set OPENAI_API_KEY or ANTHROPIC_API_KEY for non-work profiles",
        vim.log.levels.WARN,
        { title = "minuet-ai.nvim" }
      )
    end
  end,
}
