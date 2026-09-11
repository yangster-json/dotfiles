import { createProviderGroup, shellExec } from "zebar";
import { config } from "./config.js";
import { buildSections } from "./render-model.js";
import { renderSections } from "./dom.js";
import { bindActions } from "./actions.js";
import { windowsQuery, windowsAction, poll } from "./windows.js";
import { networkSample, weatherData } from "./format.js";

const state = { kanataOn: false, bluetooth: [], weather: null, network: null, updates: null, alternateClock: false,
  battery: null, batterySeen: false };
const providers = createProviderGroup({
  audio: { type: "audio" },
  battery: { type: "battery", refreshInterval: 30000 },
  cpu: { type: "cpu", refreshInterval: 3000 },
  memory: { type: "memory", refreshInterval: 5000 },
  disk: { type: "disk", refreshInterval: 30000 },
  media: { type: "media" },
  keyboard: { type: "keyboard", refreshInterval: 2000 },
  glazewm: { type: "glazewm" },
});
function render() {
  if (Number.isFinite(providers.outputMap.battery?.chargePercent) || state.battery?.present) state.batterySeen = true;
  renderSections(document, buildSections(config, providers.outputMap, state));
}
providers.onOutput(render);
providers.onError(errors => { console.warn("Some Zebar providers are unavailable", errors); render(); });

function queryPoll(query, interval, update, fallback) {
  return poll(async () => {
    try { update(await windowsQuery(shellExec, query)); }
    catch (error) { update(fallback); console.warn(`${query} unavailable`, error); }
    render();
  }, interval);
}
queryPoll("battery", 10000, value => { state.battery = value; }, null);
const refreshKanata = queryPoll("kanata", 5000, value => { state.kanataOn = value === true; }, false);
queryPoll("bluetooth", 10000, value => { state.bluetooth = Array.isArray(value) ? value : []; }, []);
queryPoll("network", 2000, value => { state.network = networkSample(state.network, value); }, null);
queryPoll("updates", 3600000, value => { state.updates = Number.isInteger(value) && value >= 0 ? value : null; }, null);
const refreshWeather = queryPoll("weather", 600000, value => { state.weather = weatherData(value); }, null);
bindActions(document.getElementById("bar"), {
  output: () => providers.outputMap, state, render, refreshWeather, refreshKanata, shellExec, windowsAction,
});
render();
setInterval(render, 1000);
