import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { config } from "../dot_glzr/zebar/mirror/config.js";
import { buildSections } from "../dot_glzr/zebar/mirror/render-model.js";

const root = new URL("../dot_glzr/zebar/mirror/", import.meta.url);
const read = name => readFileSync(new URL(name, root), "utf8");
const manifest = JSON.parse(read("zpack.json"));
const widget = manifest.widgets[0];
assert.equal(manifest.name, "mirror");
assert.equal(widget.name, "bar");
assert.equal(widget.htmlPath, "index.html");
assert.equal(widget.presets[0].height, "41px");
assert.equal(widget.presets[0].offsetX, "0px");
assert.match(read("style.css"), /--height: 41px/);
const html = read("index.html");
assert.match(html, /src="index\.js"/);
assert.match(html, /href="style\.css"/);
assert.doesNotMatch(html, /esm\.sh/);

const output = {
  cpu: { usage: 23 }, memory: { usage: 45 },
  audio: { defaultPlaybackDevice: { volume: 67, isMuted: false } },
  keyboard: { layout: "English" },
  network: { defaultGateway: { ssid: "<unsafe>" } },
  glazewm: { currentWorkspaces: [{ name: "1" }], displayedWorkspace: { name: "1" } },
};
const sections = buildSections(config, output, true);
assert.match(sections.left, /23%/);
assert.match(sections.left, /&lt;unsafe&gt;/);
assert.match(sections.center, /workspace active/);
assert.match(sections.right, /67%/);
assert.match(sections.right, /class="green"/);
assert.ok(sections.right.indexOf("English") < sections.right.indexOf("67%"));
assert.equal(buildSections(config, {}).left, "");
assert.doesNotMatch(buildSections(config, { cpu: {} }).left, /0%/);
const reordered = { ...config, modules: { left: ["memory", "cpu"], center: [], right: [] } };
const left = buildSections(reordered, output).left;
assert.ok(left.indexOf("45%") < left.indexOf("23%"));

// Run the actual entry-point body with mocked browser/Zebar APIs, not a watcher.
// Only imports are substituted; provider callbacks and state handling run intact.
const nodes = Object.fromEntries(["left", "center", "right"].map(k => [k, { innerHTML: "" }]));
let onOutput, onError;
const providers = {
  outputMap: { ...output },
  onOutput: cb => { onOutput = cb; },
  onError: cb => { onError = cb; },
};
vm.runInNewContext(read("index.js").replace(/^import .*;\n/gm, ""), {
  config, buildSections,
  createProviderGroup: () => providers,
  shellExec: async () => { throw new Error("permission unavailable"); },
  document: { getElementById: id => nodes[id] },
  console: { warn() {} }, setInterval() {}, setTimeout() {},
});
onOutput();
assert.match(nodes.right.innerHTML, /67%/);
providers.outputMap = { ...output, audio: null };
onError({ audio: "unavailable" });
assert.doesNotMatch(nodes.right.innerHTML, /67%/);
assert.match(nodes.right.innerHTML, /English/);
assert.match(nodes.left.innerHTML, /23%/);
providers.outputMap = output;
onOutput();
assert.match(nodes.right.innerHTML, /67%/);
await new Promise(resolve => setImmediate(resolve));
assert.doesNotMatch(nodes.right.innerHTML, /class="green"/);
console.log("standalone Zebar fixtures passed");
