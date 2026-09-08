import { createProviderGroup, shellExec } from "zebar";
import { config } from "./config.js";
import { buildSections } from "./render-model.js";

let kanataOn = false;
let storagePct = null;
const providers = createProviderGroup({
  audio: { type: "audio" },
  battery: { type: "battery" },
  cpu: { type: "cpu" },
  memory: { type: "memory" },
  network: { type: "network" },
  media: { type: "media" },
  keyboard: { type: "keyboard", refreshInterval: 2000 },
  glazewm: { type: "glazewm" },
  weather: { type: "weather" },
});

function render() {
  // Read the current map even on errors: failed providers become null.
  const sections = buildSections(config, providers.outputMap, kanataOn, storagePct);
  for (const group of ["left", "center", "right"]) {
    document.getElementById(group).innerHTML = sections[group];
  }
}

providers.onOutput(render);
providers.onError(errors => {
  console.warn("Some Zebar providers are unavailable", errors);
  render();
});

async function checkKanata() {
  try {
    const result = await shellExec("powershell.exe", [
      "-NoProfile", "-Command",
      "Get-Process kanata -ErrorAction SilentlyContinue",
    ]);
    kanataOn = Boolean(result.stdout?.trim());
  } catch {
    kanataOn = false;
  }
  render();
  // Schedule after completion so slow PowerShell calls never overlap.
  setTimeout(checkKanata, 5000);
}

async function checkStorage() {
  try {
    const result = await shellExec("powershell.exe", [
      "-NoProfile", "-Command",
      "$d=Get-PSDrive C; [math]::Round($d.Used/($d.Used+$d.Free)*100)",
    ]);
    const pct = parseInt(result.stdout?.trim(), 10);
    storagePct = Number.isFinite(pct) ? pct : null;
  } catch {
    storagePct = null;
  }
  render();
  setTimeout(checkStorage, 30000);
}

render();
setInterval(render, 1000);
checkKanata();
checkStorage();
