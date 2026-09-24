// Ravi's shift end to end (PROGRESS milestone 17; PRD §9 demo story), in the real cab app against
// the real edge gateway, at 30×. Ravi signs in in Tamil with his PIN and does the walkaround;
// the story then plays at 30× from each beat, the way the presenter runs it from the console
// ("Go here"): the cold start with captions on, the worker in the swing zone (P1, acknowledged),
// the seatbelt (P1), stepping out with the engine running (P2), the near miss reported by voice
// (the browser's speech recognizer is replaced by one that "hears" a Tamil sentence), the site
// losing and regaining internet, and the end of the shift opening My Day. The unbroken 7-hour run
// is covered beat by beat by backend/tests/test_headless.py (D-099).
import { readFileSync } from "node:fs";

import { type APIRequestContext, expect, type Page, test } from "@playwright/test";

const EDGE = "http://127.0.0.1:8100";
const ta = JSON.parse(readFileSync(new URL("../frontend/packages/i18n/src/locales/ta.json", import.meta.url), "utf-8"));

/** A Tamil string by its i18n key, with {{name}} filled in. */
function T(key: string, vars: Record<string, string | number> = {}): string {
  const value = key.split(".").reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], ta);
  if (typeof value !== "string") throw new Error(`no Tamil string for ${key}`);
  return value.replace(/{{(\w+)}}/g, (_, v: string) => String(vars[v] ?? ""));
}

type Demo = { waiting_for: string | null; signed_in: string | null; playing: boolean; beats: { id: string; done: boolean; caption: Record<string, string> | null }[] };

async function demo(request: APIRequestContext, path: string, body?: unknown): Promise<Demo> {
  const r = body === undefined && path === "/demo/state" ? await request.get(`${EDGE}${path}`) : await request.post(`${EDGE}${path}`, { data: body ?? {} });
  expect(r.ok(), `${path} → ${r.status()}`).toBeTruthy();
  return (await r.json()) as Demo;
}

async function beatDone(request: APIRequestContext, id: string) {
  await expect.poll(async () => (await demo(request, "/demo/state")).beats.find((b) => b.id === id)?.done, { timeout: 30_000 }).toBe(true);
}

/** Go to a beat and play on at 30× (the console's "Go here" while playing). A beat with a live
 * P1 slows the story to 1× itself so it can be seen (D-099). */
async function goTo(request: APIRequestContext, id: string) {
  // paused first: Play also releases a beat that waits for the cab, so it must come before the beat
  await demo(request, "/demo/pause");
  await demo(request, "/demo/speed", { x: 30 });
  await demo(request, "/demo/seek", { beat_id: id });
  await demo(request, "/demo/play");
  await beatDone(request, id);
}

/** Hold the push-to-talk disc while the fake recognizer "hears" `words`. */
async function say(page: Page, words: string) {
  await page.evaluate((w) => ((window as unknown as { __heard: string }).__heard = w), words);
  // the disc's name changes while listening, so hold on to the element itself
  const disc = await page.getByRole("button", { name: T("ui.ptt.idle") }).elementHandle();
  await disc!.dispatchEvent("pointerdown");
  await page.waitForTimeout(700);
  await disc!.dispatchEvent("pointerup");
}

test.describe.configure({ mode: "serial" });
test.setTimeout(6 * 60_000);

test("Ravi's shift, end to end at 30×", async ({ page, request }) => {
  // a speech recognizer that hears whatever the test says (Chrome's own needs a microphone)
  await page.addInitScript(() => {
    class HeardSpeech {
      lang = "";
      interimResults = false;
      continuous = false;
      maxAlternatives = 1;
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        setTimeout(() => {
          const transcript = (window as unknown as { __heard?: string }).__heard ?? "";
          this.onresult?.({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript } }] });
        }, 100);
      }
      stop() {
        setTimeout(() => this.onend?.(), 50);
      }
      abort() {}
    }
    const w = window as unknown as { SpeechRecognition: unknown; webkitSpeechRecognition: unknown };
    w.SpeechRecognition = HeardSpeech; // recent Chrome has the unprefixed name, which the cab prefers
    w.webkitSpeechRecognition = HeardSpeech;
  });

  // --- the story from the start, captions on the cab -------------------------------------------
  await demo(request, "/demo/reset");
  await demo(request, "/demo/captions", { on: true });

  // --- sign in: Tamil, PIN 1001 (no badge camera here), walkaround all OK ------------------------
  await page.goto("/start");
  await page.getByRole("button", { name: "தமிழ்" }).click();
  await page.getByRole("button", { name: T("ui.start.next") }).click();
  const usePin = page.getByRole("button", { name: T("ui.start.use_pin") });
  if (await usePin.isVisible().catch(() => false)) await usePin.click();
  for (const d of "1001") await page.getByRole("button", { name: d, exact: true }).click();
  await expect(page.getByRole("heading", { name: T("ui.start.welcome", { name: "Ravi Kumar" }) })).toBeVisible();
  await page.getByRole("button", { name: T("ui.start.all_ok") }).click();
  await page.getByRole("button", { name: T("ui.start.begin") }).click();
  await expect(page).toHaveURL(/\/$/);
  expect((await demo(request, "/demo/state")).signed_in).toBe("OP1001");

  // --- 30×: the cold start, with the story caption in Tamil on the cab --------------------------
  await demo(request, "/demo/speed", { x: 30 });
  await demo(request, "/demo/play");
  await beatDone(request, "cold_start");
  const state = await demo(request, "/demo/state");
  const captions = state.beats.map((b) => b.caption?.ta).filter(Boolean);
  const caption = page.getByTestId("demo-caption");
  await expect(caption).toBeVisible();
  expect(captions).toContain((await caption.textContent())?.trim());

  // --- a worker walks into the swing zone: P1 takeover, acknowledged -----------------------------
  await goTo(request, "worker_near");
  const stopped = page.getByRole("button", { name: T("ui.btn.stopped") });
  await expect(stopped).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("alertdialog", { name: new RegExp(`^${T("ui.p1.command")}`) })).toBeVisible();
  await stopped.click();
  await expect(stopped).toBeHidden({ timeout: 30_000 });

  // --- Ravi unbuckles while working: P1 again --------------------------------------------------
  await goTo(request, "seatbelt");
  await expect(stopped).toBeVisible({ timeout: 30_000 });
  await stopped.click();
  await expect(stopped).toBeHidden({ timeout: 30_000 });

  // --- he steps out with the engine running: P2 banner, seen -----------------------------------
  await goTo(request, "step_out");
  const seen = page.getByRole("button", { name: T("ui.btn.seen") });
  await expect(seen).toBeVisible({ timeout: 60_000 });
  await seen.click();

  // --- the near miss, reported by voice in Tamil; the story waits for it ------------------------
  await goTo(request, "near_miss");
  await expect.poll(async () => (await demo(request, "/demo/state")).waiting_for, { timeout: 30_000 }).toBe("near_miss");
  await say(page, "ஒரு தொழிலாளி பக்கெட் பின்னால் வந்தார், நூலிழையில் தப்பினோம்");
  await expect(page).toHaveURL(/\/report$/, { timeout: 30_000 });
  const send = page.getByRole("button", { name: T("ui.btn.send_report") });
  await expect(send).toBeVisible({ timeout: 30_000 });
  await send.click();
  await expect.poll(async () => (await demo(request, "/demo/state")).waiting_for, { timeout: 30_000 }).toBeNull();

  // --- the site loses internet, then gets it back ------------------------------------------------
  await goTo(request, "offline");
  await demo(request, "/demo/pause"); // hold the moment: at 30× the internet is back 16 s later
  const offline = page.getByRole("img", { name: T("ui.sync.offline") });
  await expect(offline).toBeVisible({ timeout: 30_000 });
  await goTo(request, "online");
  await expect(offline).toHaveCount(0, { timeout: 60_000 });

  // --- the end of the shift opens Ravi's private My Day ----------------------------------------
  await goTo(request, "end_shift");
  await expect(page).toHaveURL(/\/insights$/, { timeout: 30_000 });
  expect((await demo(request, "/demo/state")).playing).toBe(false);
});
