-- herdr-app on a remote machine: splits-nav can't reach this nvim,
-- so the nav-remote mod forwards ctrl+hjkl; at an edge we tell it via hc label.
local dirs = { h = "left", j = "down", k = "up", l = "right" }
local seq = 0

local function nav(key)
  local win = vim.api.nvim_get_current_win()
  vim.cmd("wincmd " .. key)
  if vim.api.nvim_get_current_win() == win then
    -- pid+seq: every edge hit is a new label value
    seq = seq + 1
    vim.system({ "hc", "label", vim.env.HC_TERMINAL_ID, ("nvim.nav=%s:%d.%d"):format(dirs[key], vim.fn.getpid(), seq) })
  end
end

return {
  dir = vim.fn.stdpath("config"),
  name = "herdr-app-remote-nav",
  virtual = true,
  -- app terminal, and splits-nav's own plugin not linked (it is on the laptop)
  cond = vim.env.HC_TERMINAL_ID ~= nil
    and vim.env.HERDR_ENV ~= "1"
    and vim.uv.fs_stat(vim.fn.stdpath("config") .. "/plugin/herdr-nav.lua") == nil,
  keys = vim.iter({ "h", "j", "k", "l" }):map(function(k)
    return { "<C-" .. k .. ">", function() nav(k) end, mode = { "n", "t" }, desc = "Navigate " .. dirs[k] }
  end):totable(),
}
