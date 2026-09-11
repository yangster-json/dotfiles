import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { config } from "../dot_glzr/zebar/mirror/config.js";
import { buildSections } from "../dot_glzr/zebar/mirror/render-model.js";
import { networkSample, weatherData, speed, language, keyboardName, clockText, calendar, diskSize, freeGigabytes } from "../dot_glzr/zebar/mirror/format.js";
import { windowsQuery, windowsAction, poll } from "../dot_glzr/zebar/mirror/windows.js";
import { fixture, weather, bluetooth } from "./zebar-fixture.mjs";

const p = fixture();
const now = new Date(2026, 8, 9, 14, 5);
const state = { kanataOn: true, bluetooth, weather: weatherData(weather), network: { name: "Wi-Fi", bytesPerSecond: 12000 }, updates: 2 };
const sections = buildSections(config, p, state, now);
assert.deepEqual(config.modules.left, [["cpu", "memory", "disk"], ["weather", "network"], ["updates"], ["media"]]);
assert.deepEqual(config.modules.right, [["kanata", "input"], ["bluetooth"], ["audio", "microphone", "battery", "clock"]]);
assert.match(sections.left, /8\.5G/);
assert.match(sections.left, /134G/);
assert.match(sections.left, /2 updates available/);
assert.doesNotMatch(sections.left, /45%/);
assert.match(sections.left, /72°F/);
assert.match(sections.left, /Test City, Country/);
assert.match(sections.left, /Feels like 74°F · Humidity 55% · Wind 8 km\/h/);
assert.match(sections.left, /󰤨 ↓  12k/);
assert.doesNotMatch(sections.left, /<img/);
assert.match(sections.left, /&lt;img/);
assert.match(sections.right, /Kanata enabled — click to disable/);
assert.match(sections.right, /eng/);
for (const name of ["cpu", "memory", "disk"]) assert.match(sections.left, new RegExp(`class="module ${name} [^>]*data-action="task-manager"`));
assert.match(sections.right, /Headphones &lt;unsafe&gt; &quot;one&quot;: 75%/);
assert.match(sections.right, /Volume: 80%\nStatus: Active/);
assert.match(sections.right, /14:05 \| Wed 09 Sep/);
assert.match(sections.right, /2026 September/);
assert.ok(sections.center.indexOf('data-workspace="w1"') < sections.center.indexOf('data-workspace="w2"'));
assert.match(sections.center, /workspace active visible/);
assert.match(sections.center, /data-workspace="w1"[^>]*>1<\/button>/);
assert.match(sections.center, /data-workspace="w2"[^>]*>2<\/button>/);
assert.match(sections.right.match(/<button[^>]*data-action="audio-settings"[^>]*>/)[0], /title="Click to open Volume mixer/);
assert.equal(language("Arabic (Saudi Arabia)"), "ara");
assert.equal(language("French"), "---");
for (const value of ["en", "en-US", "en-GB\0", " en_US\0 "]) assert.equal(language(value), "eng");
for (const value of ["ar", "ar-SA", "ar-EG\0", "ar_001"]) assert.equal(language(value), "ara");
assert.equal(language(null), "---");
assert.equal(keyboardName("en-US\0"), "English (United States)");
assert.equal(keyboardName("ar-SA\0"), "Arabic (Saudi Arabia)");
assert.equal(keyboardName("English (United States)"), "English (United States)");
assert.equal(keyboardName(null), "Keyboard unavailable");
assert.ok(!sections.right.includes("\0"));
assert.equal(clockText(now, "en-GB", true), "2026-09-09");
assert.match(calendar(new Date(2024, 1, 29), "en-GB"), /\[29\]/);
assert.equal(diskSize(1024 ** 4), "1.0TiB");
assert.equal(freeGigabytes(125 * 1024 ** 3), " 134G");
assert.equal(speed(12001), " 13k");
assert.equal(speed(999999), "  1M");
assert.equal(speed(0), "  0 ");
const first = networkSample(null, { interfaceId: "a", timestamp: 1000, receivedBytes: 100 });
assert.equal(first.bytesPerSecond, 0);
assert.equal(networkSample(first, { interfaceId: "a", timestamp: 3000, receivedBytes: 30100 }).bytesPerSecond, 15000);
assert.equal(networkSample(first, { interfaceId: "b", timestamp: 3000, receivedBytes: 30100 }).bytesPerSecond, 0);
assert.equal(networkSample(first, { interfaceId: "a", timestamp: 3000, receivedBytes: 1 }).bytesPerSecond, 0);
assert.equal(networkSample(first, null), null);
assert.equal(weatherData(null), null);
const empty = buildSections(config, {}, {}, now);
assert.match(empty.left, /Weather unavailable/);
assert.match(empty.left, /Disconnected/);
assert.match(empty.right, /No microphone available/);
assert.doesNotMatch(empty.right, /class="module bluetooth/);
const pausedMedia = buildSections(config, { media: { currentSession: { isPlaying: false, title: "stale title" } } }, {}, now);
assert.doesNotMatch(pausedMedia.left, /stale title/);
p.audio.defaultPlaybackDevice.isMuted = true;
p.audio.defaultRecordingDevice.isMuted = true;
p.battery.isCharging = true;
const changed = buildSections(config, p, { ...state, alternateClock: true }, now);
assert.match(changed.right, /󰝟/);
assert.match(changed.right, /Status: Muted/);
assert.match(changed.right, /󰂄/);
assert.match(changed.right, /2026-09-09/);

const fallbackBattery = { present: true, chargePercent: 66, isCharging: true, state: "Charging" };
for (const battery of [null, { chargePercent: NaN }, { chargePercent: null }]) {
  const recovered = buildSections(config, { battery }, { battery: fallbackBattery }, now).right;
  assert.match(recovered, /󰂄/);
  assert.match(recovered, /Battery: 66%\nCharging/);
}
assert.match(buildSections(config, {}, { batterySeen: true }, now).right, /Battery status unavailable/);
assert.match(buildSections(config, {}, { battery: { ...fallbackBattery, chargePercent: null } }, now).right, /󰂄.*--/);
assert.doesNotMatch(buildSections(config, {}, { batterySeen: true, battery: { present: false } }, now).right, /class="module battery/);
assert.doesNotMatch(empty.right, /class="module battery/);
assert.match(buildSections(config, p, { battery: fallbackBattery }, now).right, /Battery: 65%/);

const manifest = JSON.parse(readFileSync(new URL("../dot_glzr/zebar/mirror/zpack.json", import.meta.url)));
const permissions = manifest.widgets[0].privileges.shellCommands;
let calls = 0;
for (const query of ["kanata", "network", "bluetooth", "weather", "battery", "updates"]) {
  assert.equal(await windowsQuery(async (program, args) => {
    calls++;
    assert.ok(permissions.some(rule => rule.program === program && new RegExp(rule.argsRegex).test(args.join(" "))));
    return { code: 0, stdout: "\ufefftrue", stderr: "" };
  }, query), true);
}
assert.equal(calls, 6);
assert.throws(() => windowsQuery(() => {}, "injected;command"), /Unknown Windows query/);
assert.throws(() => windowsAction(() => {}, "injected;command"), /Unknown Windows action/);
await assert.rejects(() => windowsQuery(async () => ({ code: 1, stderr: "failure" }), "network"), /failure/);
await windowsAction(async (program, args) => {
  assert.ok(permissions.some(rule => rule.program === program && new RegExp(rule.argsRegex).test(args.join(" "))));
  return { code: 0, stdout: "true", stderr: "" };
}, "toggle-kanata");
for (const [program, args] of [["Taskmgr.exe", ""], ["explorer.exe", "ms-settings:network-wifi"], ["explorer.exe", "ms-settings:apps-volume"], ["explorer.exe", "ms-settings:windowsupdate"]]) {
  assert.ok(permissions.some(rule => rule.program === program && new RegExp(rule.argsRegex).test(args)));
}
assert.ok(!permissions.some(rule => rule.program === "powershell.exe" && new RegExp(rule.argsRegex).test("-Command Remove-Item")));
for (const file of manifest.widgets[0].includeFiles) {
  readFileSync(new URL(`../dot_glzr/zebar/mirror/${file}`, import.meta.url));
}
let finish, pollCalls = 0, schedules = 0;
const refresh = poll(() => { pollCalls++; return new Promise(resolve => { finish = resolve; }); }, 1000,
  { setTimeout() { schedules++; return 1; }, clearTimeout() {} });
await Promise.resolve();
const a = refresh(), b = refresh();
assert.equal(pollCalls, 1);
finish();
await Promise.all([a, b]);
assert.equal(schedules, 1);
const startupTasks = [], intervals = [];
let providerConfig, actionBindings, outputCallback, errorCallback, lastRendered;
const startupProviders = {};
runInNewContext(readFileSync(new URL("../dot_glzr/zebar/mirror/index.js", import.meta.url), "utf8").replace(/^import .*;\n/gm, ""), {
  config, buildSections, weatherData, networkSample, windowsQuery, windowsAction,
  createProviderGroup(value) {
    providerConfig = value;
    return { outputMap: startupProviders, onOutput(fn) { outputCallback = fn; }, onError(fn) { errorCallback = fn; } };
  },
  document: { getElementById: id => ({ id }) }, renderSections(document, sections) { lastRendered = sections; },
  bindActions(bar, bindings) { actionBindings = bindings; assert.equal(bar.id, "bar"); },
  shellExec: async () => ({ code: 0, stdout: "null" }),
  poll(task, interval) { intervals.push(interval); startupTasks.push(task()); return task; },
  setInterval(fn, interval) { assert.equal(interval, 1000); }, console: { warn() {} },
});
await Promise.all(startupTasks);
assert.equal(providerConfig.disk.type, "disk");
assert.equal(providerConfig.audio.type, "audio");
assert.equal(providerConfig.memory.refreshInterval, 5000);
assert.deepEqual(intervals, [10000, 5000, 10000, 2000, 3600000, 600000]);
assert.equal(typeof actionBindings.refreshWeather, "function");
assert.equal(typeof actionBindings.refreshKanata, "function");
outputCallback();
errorCallback({ audio: "Unavailable" });
startupProviders.battery = fixture().battery;
outputCallback();
assert.equal(actionBindings.state.batterySeen, true);
startupProviders.battery = null;
errorCallback({ battery: "Unavailable while charging" });
assert.match(lastRendered.right, /Battery status unavailable/);
actionBindings.state.battery = fallbackBattery;
outputCallback();
assert.match(lastRendered.right, /Battery: 66%\nCharging/);
startupProviders.battery = { chargePercent: 67, isCharging: false, state: "Discharging" };
outputCallback();
assert.match(lastRendered.right, /Battery: 67%\nDischarging/);
console.log("Zebar render, parity, failure-state, permission, polling and startup tests passed.");
