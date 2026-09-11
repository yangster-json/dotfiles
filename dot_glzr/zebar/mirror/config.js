// Windows counterpart of dot_config/waybar/config (no system tray).
export const config = {
  modules: {
    left: [["cpu", "memory", "disk"], ["weather", "network"], ["updates"], ["media"]],
    center: [["workspaces"]],
    right: [["kanata", "input"], ["bluetooth"], ["audio", "microphone", "battery", "clock"]],
  },
  // Windows equivalent of /home; change this if your user files live elsewhere.
  diskMount: "C:\\",
  locale: "en-GB",
  icons: {
    cpu: "󰍛", memory: "", disk: "", keyboard: "󰌌", clock: "󰥔",
  },
};
