// Windows Zebar only. Waybar is configured separately in dot_config/waybar/.
// Apply with chezmoi, then reopen this widget to pick up changes.
export const config = {
  modules: {
    // Mirrors Waybar left: cpu, memory, (disk skipped - no Zebar provider),
    // weather, network, media.
    left: ["cpu", "memory", "weather", "network", "media"],
    center: ["workspaces"],
    // Mirrors Waybar right: input, audio, (microphone skipped), battery, clock.
    right: ["input", "audio", "battery", "clock"],
  },
  icons: {
    cpu: "󰍛",
    memory: "",
    weather: "󰖐",
    keyboard: "󰌌",
    clock: "󰥔",
  },
};
