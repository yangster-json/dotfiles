import { escape, gib, diskSize, clamp, language, keyboardName, speed, clockText, calendar } from "./format.js";

const icon = (text, tone) => `<span class="${tone}">${escape(text)}</span>`;
function item(key, html, { title, action, tone = "", extra = "" } = {}) {
  const tag = action ? "button" : "span";
  return `<${tag} data-key="${key}" class="module ${key} ${tone}"${action ? ` type="button" data-action="${action}"` : ""}`
    + `${title ? ` title="${escape(title)}"` : ""}${extra}>${html}</${tag}>`;
}
const percent = value => `${Math.round(clamp(value))}%`;
const mount = value => String(value).replace(/[\\/]+$/, "").toLowerCase();

export function buildSections(config, p = {}, state = {}, now = new Date()) {
  const renderers = {
    cpu: () => Number.isFinite(p.cpu?.usage) ? item("cpu", `${icon(config.icons.cpu, "blue")} ${percent(p.cpu.usage)}`,
      { action: "task-manager", title: `CPU: ${percent(p.cpu.usage)}\n${p.cpu.physicalCoreCount ?? "?"} physical / ${p.cpu.logicalCoreCount ?? "?"} logical cores\nClick to open Task Manager` }) : "",
    memory: () => Number.isFinite(p.memory?.usedMemory) ? item("memory", `${icon(config.icons.memory, "red")} ${gib(p.memory.usedMemory)}G`,
      { title: `Memory: ${gib(p.memory.usedMemory)} / ${gib(p.memory.totalMemory)} GiB\nFree: ${gib(p.memory.freeMemory)} GiB` }) : "",
    disk: () => {
      const d = p.disk?.disks?.find(disk => mount(disk.mountPoint) === mount(config.diskMount));
      if (!Number.isFinite(d?.availableSpace?.bytes)) return "";
      return item("disk", `${icon(config.icons.disk, "green")} ${diskSize(d.availableSpace.bytes)}`,
        { title: `${d.mountPoint} (${d.fileSystem})\nFree: ${diskSize(d.availableSpace.bytes)}\nTotal: ${diskSize(d.totalSpace.bytes)}` });
    },
    weather: () => item("weather", escape(state.weather?.text ?? "󰖐 --"),
      { action: "weather", title: state.weather?.tooltip ?? "Weather unavailable" }),
    network: () => item("network", escape(state.network ? `󰤨 ↓ ${speed(state.network.bytesPerSecond)}` : "󰤭 ↓     "),
      { action: "network", tone: "yellow", title: state.network
        ? `${state.network.name}\nDownload: ${speed(state.network.bytesPerSecond).trim()}B/s\nClick to open network settings`
        : "Disconnected\nClick to open network settings" }),
    media: () => {
      const title = p.media?.currentSession?.title;
      if (!title) return "";
      return item("media", `󰎈 ${escape(title)}`, { title, tone: "mauve" });
    },
    workspaces: () => {
      const workspaces = p.glazewm?.currentWorkspaces;
      if (!workspaces?.length) return "";
      return item("workspaces", [...workspaces].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true })).map(w => {
        const active = w.name === p.glazewm.displayedWorkspace?.name;
        return `<button type="button" data-key="${escape(w.id)}" data-action="workspace" data-workspace="${escape(w.id)}"`
          + ` class="workspace${active ? " active" : ""}${w.isDisplayed ? " visible" : ""}" title="${escape(w.name)}" aria-label="Workspace ${escape(w.name)}" aria-pressed="${active}"></button>`;
      }).join(""));
    },
    input: () => {
      const layout = p.keyboard?.layout;
      const marker = state.kanataOn ? `${icon(config.icons.keyboard, "green")} ` : "";
      return item("input", `${marker}${icon(config.icons.keyboard, "yellow")} ${language(layout ?? "")}`,
        { title: `${state.kanataOn ? "Kanata enabled — " : ""}${keyboardName(layout)}` });
    },
    bluetooth: () => {
      const devices = state.bluetooth ?? [];
      if (!devices.length) return "";
      const battery = devices.find(d => Number.isFinite(d.battery))?.battery;
      return item("bluetooth", `${battery === undefined ? "" : ` ${percent(battery)}`}`, { tone: "blue",
        title: devices.map(d => `${d.name}${Number.isFinite(d.battery) ? `: ${percent(d.battery)}` : ""}`).join("\n") });
    },
    audio: () => {
      const d = p.audio?.defaultPlaybackDevice;
      if (!d || !Number.isFinite(d.volume)) return "";
      const glyph = /head(phone|set)/i.test(d.name) ? "" : d.volume < 34 ? "" : d.volume < 67 ? "" : "";
      // Waybar explicitly disables the speaker tooltip.
      return item("audio", d.isMuted ? icon("󰝟", "red") : `${icon(glyph, "green")} ${percent(d.volume)}`,
        { action: "audio", extra: ' aria-label="Toggle speaker mute; scroll to change volume"' });
    },
    microphone: () => {
      const d = p.audio?.defaultRecordingDevice;
      return item("microphone", d && !d.isMuted ? "󰍬" : "󰍭", { action: "microphone", tone: !d || d.isMuted ? "red" : "green",
        title: d ? `Input: ${d.name}\nVolume: ${percent(d.volume)}\nStatus: ${d.isMuted ? "Muted" : "Active"}` : "No microphone available" });
    },
    battery: () => {
      const b = p.battery;
      if (!Number.isFinite(b?.chargePercent)) return "";
      const icons = ["󰁺", "󰁻", "󰁼", "󰁽", "󰁾", "󰁿", "󰂀", "󰂁", "󰂂", "󰁹"];
      const glyph = b.isCharging ? "󰂄" : icons[Math.min(9, Math.floor(clamp(b.chargePercent) / 10))];
      const level = b.chargePercent <= 15 ? "critical" : b.chargePercent <= 30 ? "warning" : "";
      return item("battery", `${icon(glyph, "green")} ${percent(b.chargePercent)}`, { tone: level,
        title: `Battery: ${percent(b.chargePercent)}\n${b.isCharging ? "Charging" : b.state ?? "unknown"}` });
    },
    clock: () => item("clock", `${state.alternateClock ? "" : `${icon(config.icons.clock, "blue")} `}${escape(clockText(now, config.locale, state.alternateClock))}`,
      { action: "clock", title: calendar(now, config.locale) }),
  };
  return Object.fromEntries(Object.entries(config.modules).map(([group, bubbles]) => [group,
    bubbles.map((names, i) => {
      const modules = names.map(name => renderers[name]?.()).filter(Boolean);
      return modules.length ? `<span class="bubble" data-key="${group}-${i}">${modules.join("")}</span>` : "";
    }).join(""),
  ]));
}
