local function cascade_router_key()
  local ok, lines = pcall(vim.fn.readfile, vim.fn.expand("~/.config/everpure-foundry/router.env"))
  if not ok then
    return nil
  end

  for _, raw in ipairs(lines) do
    local line = raw:gsub("^%s*export%s+", "")
    local value = line:match("^%s*CASCADE_ROUTER_KEY%s*=%s*(.-)%s*$")
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

return {
  "milanglacier/minuet-ai.nvim",
  event = "InsertEnter",
  config = function()
    require("minuet").setup({
      provider = "openai_compatible",
      request_timeout = 3,
      throttle = 1500,
      debounce = 500,
      n_completions = 1,
      context_window = 6000,
      provider_options = {
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
        auto_trigger_ft = { "*" },
        auto_trigger_ignore_ft = { "gitcommit", "help", "markdown" },
        keymap = {
          accept = "<C-y>",
          dismiss = "<C-]>",
        },
      },
    })
  end,
}
