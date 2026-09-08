const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const escape = value => String(value ?? "").replace(/[&<>"']/g, c => entities[c]);
const item = (text, tone = "") => `<span class="module ${tone}">${text}</span>`;

function percent(icon, value, tone) {
  return Number.isFinite(value) ? item(`${escape(icon)} ${Math.round(value)}%`, tone) : "";
}

export function buildSections(config, output = {}, kanataOn = false, storagePct = null, now = new Date()) {
  const p = output;
  const renderers = {
    cpu: () => percent(config.icons.cpu, p.cpu?.usage, "blue"),
    memory: () => percent(config.icons.memory, p.memory?.usage, "red"),
    storage: () => storagePct !== null ? percent(config.icons.storage, storagePct, "yellow") : "",
    weather: () => {
      const w = p.weather;
      if (!w) return "";
      const icon = w.isDaytime ? "󰖐" : "󰖔";
      return item(`${icon} ${Math.round(w.celsiusTemp)}°C`, "blue");
    },
    network: () => {
      const name = p.network?.defaultGateway?.ssid || p.network?.defaultInterface?.friendlyName;
      return name ? item(`󰈀 ${escape(name)}`, "yellow") : "";
    },
    media: () => {
      const title = p.media?.currentSession?.title;
      return title ? item(`󰎈 ${escape(title)}`, "mauve") : "";
    },
    workspaces: () => {
      const workspaces = p.glazewm?.currentWorkspaces;
      if (!workspaces?.length) return "";
      return item(workspaces.map(w => {
        const active = w.name === p.glazewm.displayedWorkspace?.name;
        return `<span class="workspace ${active ? "active" : ""}" title="${escape(w.name)}">●</span>`;
      }).join(""), "workspaces");
    },
    input: () => {
      if (!p.keyboard?.layout) return "";
      const marker = kanataOn ? '<span class="green">󰌌</span>&nbsp;' : "";
      return item(`${marker}${escape(config.icons.keyboard)} ${escape(p.keyboard.layout)}`, "yellow");
    },
    audio: () => {
      const device = p.audio?.defaultPlaybackDevice;
      if (!device) return "";
      return percent(device.isMuted ? "󰝟" : "", device.volume, device.isMuted ? "red" : "blue");
    },
    battery: () => percent("󰁹", p.battery?.chargePercent, "green"),
    clock: () => item(`${escape(config.icons.clock)} ${escape(now.toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit",
    }))}`, "green"),
    date: () => item(`${escape(config.icons.date)} ${escape(now.toLocaleDateString([], {
      month: "short", day: "numeric",
    }))}`, "mauve"),
  };

  return Object.fromEntries(Object.entries(config.modules).map(([group, names]) => [
    group, names.map(name => renderers[name]?.()).filter(Boolean).join(""),
  ]));
}
