
local wezterm = require 'wezterm'

local config = wezterm.config_builder()
config.color_scheme = 'Catppuccin Mocha'
config.font = wezterm.font('JetBrainsMono Nerd Font')
config.font_size = 11
config.default_cursor_style = 'SteadyBar'
config.window_background_opacity = 0.93
config.window_decorations = "INTEGRATED_BUTTONS|RESIZE"
config.enable_tab_bar= false
config.line_height = 0.9
config.window_padding = {
  left = 0,
  right = 0,
  top = 0,
  bottom = 0,
}
config.window_close_confirmation = 'NeverPrompt'
config.front_end = "OpenGL"
config.adjust_window_size_when_changing_font_size = false
config.keys = {

  {
    key = 'PageDown',
    mods = 'CTRL',
    action = wezterm.action.DisableDefaultAssignment
  },

  {
    key = 'PageUp',
    mods = 'CTRL',
    action = wezterm.action.DisableDefaultAssignment
  },
  {
    key = 'w',
    mods = 'CTRL|SHIFT|ALT',
    action = wezterm.action.CloseCurrentPane { confirm = false },
  },
}

return config