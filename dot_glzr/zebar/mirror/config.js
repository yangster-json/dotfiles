// Windows Zebar only. Waybar is configured separately in dot_config/waybar/.
// Apply with chezmoi, then reopen this widget to pick up changes.
export const config = {
  modules: {
    left: ["cpu", "memory", "network", "media"],
    center: ["workspaces"],
    right: ["input", "audio", "battery", "clock"],
  },
  icons: {
    cpu: "󰍛",
    memory: "",
    keyboard: "󰌌",
    clock: "󰥔",
  },
};
