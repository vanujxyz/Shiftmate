// README screenshots (milestone 17). Needs `pnpm dev:all` running. Resets the demo, signs Ravi in
// (English, PIN 1001) and captures the cab and console at 1280 × 800 into docs/screenshots/.
// Usage: node scripts/screenshots.mjs
import { mkdirSync, readFileSync } from "node:fs";

import { chromium } from "@playwright/test";

const EDGE = "http://127.0.0.1:8100";
const CAB = "http://localhost:5173";
const CONSOLE = "http://localhost:5174";
const OUT = new URL("../docs/screenshots/", import.meta.url);
const en = JSON.parse(readFileSync(new URL("../frontend/packages/i18n/src/locales/en.json", import.meta.url), "utf-8"));
const T = (key, vars = {}) =>
  key
    .split(".")
    .reduce((o, k) => o?.[k], en)
    .replace(/{{(\w+)}}/g, (_, v) => String(vars[v] ?? ""));

async function post(path, body = {}) {
  const r = await fetch(`${EDGE}${path}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

async function beatDone(id) {
  for (let i = 0; i < 120; i++) {
    const s = await (await fetch(`${EDGE}/demo/state`)).json();
    if (s.beats.find((b) => b.id === id)?.done) return;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`beat ${id} did not fire`);
}

async function goTo(id) {
  await post("/demo/pause");
  await post("/demo/speed", { x: 30 });
  await post("/demo/seek", { beat_id: id });
  await post("/demo/play");
  await beatDone(id);
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ channel: "chrome" });
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
// the demo readiness checklist asks for no console errors in either app (CLAUDE.md §8)
const errors = [];
context.on("page", (page) => {
  page.on("console", (m) => m.type() === "error" && errors.push(`${new URL(page.url()).port} ${m.text()} (${m.location().url} on ${page.url()})`));
  page.on("response", (r) => r.status() >= 400 && errors.push(`  ↳ ${r.status()} ${r.url()}`));
});
const cab = await context.newPage();
const shot = (page, name) => page.screenshot({ path: new URL(`${name}.png`, OUT).pathname.replace(/^\/([A-Z]:)/, "$1") });

await post("/demo/reset");
await cab.goto(`${CAB}/start`);
await cab.getByRole("button", { name: "English" }).click();
await cab.getByRole("button", { name: T("ui.start.next") }).click();
const usePin = cab.getByRole("button", { name: T("ui.start.use_pin") });
if (await usePin.isVisible().catch(() => false)) await usePin.click();
for (const d of "1001") await cab.getByRole("button", { name: d, exact: true }).click();
await cab.getByRole("button", { name: T("ui.start.all_ok") }).click();
await cab.getByRole("button", { name: T("ui.start.begin") }).click();
await cab.waitForURL(/\/$/);
await cab.waitForTimeout(1500);
await shot(cab, "cab-my-shift");

await goTo("worker_near");
await cab.getByRole("button", { name: T("ui.btn.stopped") }).waitFor({ timeout: 30_000 });
await shot(cab, "cab-p1-alert");

const con = await context.newPage();
await con.goto(`${CONSOLE}/site/CHN-HWY-01`);
await con.waitForTimeout(2500);
await shot(con, "console-site-map");
await cab.getByRole("button", { name: T("ui.btn.stopped") }).click();

await goTo("end_shift");
await cab.waitForURL(/\/insights/, { timeout: 30_000 });
await cab.waitForTimeout(1500);
await shot(cab, "cab-my-day");

await con.goto(`${CONSOLE}/supervisor/CHN-HWY-01`);
await con.waitForTimeout(2500);
await shot(con, "console-supervisor");
await con.goto(`${CONSOLE}/fleet`);
await con.waitForTimeout(2500);
await shot(con, "console-fleet");
await con.goto(`${CONSOLE}/demo`);
await con.waitForTimeout(1500);
await shot(con, "console-demo");

await post("/demo/reset");
await browser.close();
console.log("screenshots written to docs/screenshots/");
console.log(`console errors: ${errors.length}`);
for (const e of errors) console.log(`  ${e}`);
