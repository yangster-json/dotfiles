import { clamp } from "./format.js";

export function bindActions(bar, { output, state, render, refreshWeather, refreshKanata, shellExec, windowsAction }) {
  let audioQueue = Promise.resolve();
  function report(error) { console.warn("Bar action failed", error); }
  async function launch(program, args = []) {
    const result = await shellExec(program, args);
    if (result.code !== 0) throw new Error(result.stderr || `${program} exited ${result.code}`);
  }
  function audioAction(action, delta) {
    audioQueue = audioQueue.then(async () => {
      const audio = output().audio;
      const device = action === "microphone" ? audio?.defaultRecordingDevice : audio?.defaultPlaybackDevice;
      if (!device) return;
      if (delta !== undefined) {
        const volume = clamp(device.volume + delta);
        await audio.setVolume(volume, { deviceId: device.deviceId });
        device.volume = volume;
      } else {
        const muted = !device.isMuted;
        await audio.setMute(muted, { deviceId: device.deviceId });
        device.isMuted = muted;
      }
      render();
    }).catch(report);
    return audioQueue;
  }
  bar.addEventListener("click", event => {
    const target = event.target.closest("[data-action]");
    if (!target || !bar.contains(target)) return;
    const action = target.dataset.action;
    Promise.resolve().then(async () => {
      if (action === "microphone") return audioAction(action);
      if (action === "clock") { state.alternateClock = !state.alternateClock; render(); }
      if (action === "weather") return refreshWeather();
      if (action === "updates") return launch("explorer.exe", ["ms-settings:windowsupdate"]);
      if (action === "kanata") { await windowsAction(shellExec, "toggle-kanata"); return refreshKanata(); }
      if (action === "task-manager") return launch("Taskmgr.exe");
      if (action === "network") return launch("explorer.exe", ["ms-settings:network-wifi"]);
      if (action === "audio-settings") return launch("explorer.exe", ["ms-settings:apps-volume"]);
      if (action === "workspace") {
        const wm = output().glazewm;
        const workspace = wm?.currentWorkspaces.find(w => w.id === target.dataset.workspace);
        if (workspace) await wm.runCommand(`focus --workspace ${JSON.stringify(workspace.name)}`);
      }
    }).catch(report);
  });
  bar.addEventListener("contextmenu", event => {
    const target = event.target.closest('[data-action="audio-settings"]');
    if (!target || !bar.contains(target)) return;
    event.preventDefault();
    audioAction("audio");
  });
  bar.addEventListener("wheel", event => {
    const target = event.target.closest('[data-action="audio-settings"]');
    if (!target || !bar.contains(target) || event.deltaY === 0) return;
    event.preventDefault();
    audioAction("audio", event.deltaY < 0 ? 10 : -10);
  }, { passive: false });
}
