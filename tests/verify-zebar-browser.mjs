// Optional integration test: npm install --prefix /tmp/zebar-tests playwright
// ZEBAR_PLAYWRIGHT_MODULE=/tmp/zebar-tests/node_modules/playwright/index.mjs node tests/verify-zebar-browser.mjs
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, extname } from "node:path";
const { chromium } = await import(process.env.ZEBAR_PLAYWRIGHT_MODULE || "playwright");
const root = resolve(import.meta.dirname, "..");
const server = createServer(async (req, res) => {
  try {
    const file = resolve(root, `.${decodeURIComponent(new URL(req.url, "http://localhost").pathname)}`);
    if (!file.startsWith(`${root}/`)) throw new Error("Outside root");
    res.setHeader("Content-Type", extname(file) === ".css" ? "text/css" : extname(file) === ".html" ? "text/html" : "text/javascript");
    res.end(await readFile(file));
  } catch { res.writeHead(404); res.end(); }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 100 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error));
  await page.route("**/dot_glzr/zebar/mirror/index.js", route => route.fulfill({ contentType: "text/javascript", body: `
    import { config } from './config.js';
    import { buildSections } from './render-model.js';
    import { renderSections } from './dom.js';
    import { bindActions } from './actions.js';
    import { weatherData } from './format.js';
    import { fixture, weather, bluetooth } from '/tests/zebar-fixture.mjs';
    const p = fixture();
    const state = { kanataOn: true, bluetooth, weather: weatherData(weather), network: { name: 'Wi-Fi', bytesPerSecond: 12000 } };
    window.test = { p, state, calls: [] };
    p.audio.setMute = async (...args) => window.test.calls.push(['mute', ...args]);
    p.audio.setVolume = async (...args) => window.test.calls.push(['volume', ...args]);
    p.glazewm.runCommand = async command => window.test.calls.push(['workspace', command]);
    const render = () => renderSections(document, buildSections(config, p, state, new Date(2026, 8, 9, 14, 5)));
    window.test.render = render;
    bindActions(document.getElementById('bar'), {
      output: () => p, state, render,
      refreshWeather: () => window.test.calls.push(['weather']),
      shellExec: async (...args) => { window.test.calls.push(['launch', ...args]); return { code: 0 }; },
    });
    render();
  ` }));
  await page.goto(`http://127.0.0.1:${server.address().port}/dot_glzr/zebar/mirror/index.html`);
  await page.locator('[data-action="audio"]').waitFor();
  assert.equal(await page.locator("#bar").evaluate(e => e.getBoundingClientRect().height), 41);
  assert.equal(await page.locator("img").count(), 0);
  for (const width of [1920, 1366]) {
    await page.setViewportSize({ width, height: 100 });
    assert.ok(await page.evaluate(() => [...document.querySelectorAll('section')].every(e => e.scrollWidth <= e.clientWidth)), `Full bar fits at ${width}px`);
  }
  for (const module of ["cpu", "memory", "disk", "weather", "network", "media", "input", "bluetooth", "microphone", "clock"]) {
    assert.ok(await page.locator(`.module.${module}`).getAttribute("title"), module);
  }
  await page.locator(".microphone").hover();
  await page.evaluate(() => { window.hovered = document.querySelector('.microphone'); window.title = window.hovered.title; });
  // Every one-second tick must retain hovered/focused nodes, not rebuild the DOM.
  for (let i = 0; i < 3; i++) {
    await page.waitForTimeout(400);
    await page.evaluate(() => { window.test.p.cpu.usage++; window.test.render(); });
  }
  assert.ok(await page.evaluate(() => window.hovered === document.querySelector('.microphone') && window.title === window.hovered.title));
  await page.locator(".microphone").click();
  await page.waitForFunction(() => document.querySelector('.microphone').title.includes('Status: Muted'));
  await page.locator(".audio").click();
  await page.waitForFunction(() => window.test.p.audio.defaultPlaybackDevice.isMuted);
  await page.locator(".audio").hover();
  await page.mouse.wheel(0, -100);
  await page.waitForFunction(() => window.test.p.audio.defaultPlaybackDevice.volume === 77);
  await page.locator(".clock").focus();
  await page.evaluate(() => window.test.render());
  assert.ok(await page.locator(".clock").evaluate(e => e === document.activeElement));
  await page.keyboard.press("Enter");
  assert.equal(await page.locator(".clock").textContent(), "2026-09-09");
  await page.locator('[data-workspace="w2"]').click();
  await page.locator(".weather").click();
  await page.locator(".cpu").click();
  await page.locator(".network").click();
  const calls = await page.evaluate(() => window.test.calls);
  assert.ok(calls.some(c => c[0] === "workspace" && c[1] === 'focus --workspace "2"'));
  assert.ok(calls.some(c => c[0] === "mute" && c[2].deviceId === "mic"));
  assert.ok(calls.some(c => c[0] === "mute" && c[2].deviceId === "speaker"));
  assert.ok(calls.some(c => c[0] === "weather"));
  assert.ok(calls.some(c => c[0] === "launch" && c[1] === "Taskmgr.exe"));
  assert.ok(calls.some(c => c[0] === "launch" && c[1] === "explorer.exe"));
  await page.evaluate(() => { window.test.state.bluetooth = []; window.test.p.media = null; window.test.render(); });
  assert.equal(await page.locator(".bluetooth").count(), 0);
  assert.equal(await page.locator(".media").count(), 0);
  assert.ok(await page.evaluate(() => window.hovered === document.querySelector('.microphone')));
  await page.evaluate(() => { window.test.state.alternateClock = false; window.test.render(); });
  for (const width of [1920, 1366]) {
    await page.setViewportSize({ width, height: 100 });
    assert.ok(await page.evaluate(() => [...document.querySelectorAll('section')].every(e => e.scrollWidth <= e.clientWidth)), `No clipping at ${width}px`);
  }
  assert.deepEqual(errors, []);
  console.log("Browser DOM stability, escaped tooltips, layout, keyboard, clicks, and volume scroll tests passed.");
} finally {
  await browser.close();
  server.close();
}
