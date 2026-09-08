// Windows Zebar only. Waybar is configured separately in dot_config/waybar/.
// Apply with chezmoi, then reopen this widget to pick up changes.
export const config = {
  modules: {
    left: [
      ["cpu", "memory", "storage"],
      ["weather", "network", "media"],
    ],
    center: [
      ["workspaces"],
    ],
    right: [
      ["input", "audio", "battery", "clock", "date"],
    ],
  },
  icons: {
    cpu: "󰍛",
    memory: "",
    storage: "󰋊",
    weather: "󰖐",
    keyboard: "󰌌",
    clock: "󰥔",
    date: "󰃭",
  },
};
