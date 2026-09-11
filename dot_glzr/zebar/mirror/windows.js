// These command strings are mirrored by the anchored allowlist in zpack.json.
// Never interpolate provider output (device names, workspace names, etc.).
export function windowsQuery(shellExec, query) {
  if (!["kanata", "network", "bluetooth", "weather", "battery"].includes(query)) throw new Error("Unknown Windows query");
  return shellExec("powershell.exe", ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
    `& (Join-Path $env:USERPROFILE '.glzr/zebar/mirror/windows.ps1') -Query ${query}`,
  ]).then(result => {
    if (result.code !== 0) throw new Error(result.stderr || `${query} exited ${result.code}`);
    return JSON.parse(result.stdout.replace(/^\uFEFF/, "").trim());
  });
}

export function windowsAction(shellExec, action) {
  if (action !== "toggle-kanata") throw new Error("Unknown Windows action");
  return shellExec("powershell.exe", ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
    `& (Join-Path $env:USERPROFILE '.glzr/zebar/mirror/windows.ps1') -Action ${action}`,
  ]).then(result => {
    if (result.code !== 0) throw new Error(result.stderr || `${action} exited ${result.code}`);
  });
}

// Completion-driven polling prevents overlapping PowerShell calls. Clicking a
// refresh while a request is running joins it, rather than launching another.
export function poll(task, interval, timers = globalThis) {
  let running = null, timer;
  function refresh() {
    if (running) return running;
    timers.clearTimeout(timer);
    running = Promise.resolve().then(task).catch(error => console.warn("Bar poll failed", error)).finally(() => {
      running = null;
      timer = timers.setTimeout(refresh, interval);
    });
    return running;
  }
  refresh();
  return refresh;
}
