/**
 * CLAUDE.md Phase 7 DoD: the kitchen sink renders every component in 3 themes × 3 languages
 * without overflow. Checked in a real browser (jsdom has no layout): inside each 1280 px cab frame
 * no element may stick out of the frame or have content wider than its own box, and the page
 * itself must not scroll sideways. The push-to-talk listening ring grows on purpose and is skipped.
 */
import { expect, test } from "@playwright/test";

const THEMES = ["day", "sunlight", "night"];
const LANGS = ["en", "hi", "ta"];

test.use({ baseURL: "http://localhost:5174", viewport: { width: 1440, height: 900 } });

test("kitchen sink: no overflow in any theme or language", async ({ page }) => {
  await page.goto("/_kitchen-sink");
  await expect(page.locator("#console")).toBeVisible();
  const problems: string[] = [];
  // the two switches in the header, by position (their labels change with the language)
  const groups = page.locator("header [role=group]");
  for (const [ti, theme] of THEMES.entries()) {
    for (const [li, lang] of LANGS.entries()) {
      await groups.nth(0).locator("button").nth(ti).click();
      await groups.nth(1).locator("button").nth(li).click();
      await expect(page.locator(`[data-theme="${theme}"][lang="${lang}"]`)).toBeVisible();
      const found = await page.evaluate(() => {
        const out: string[] = [];
        for (const frame of document.querySelectorAll('[data-frame="cab"]')) {
          const fr = frame.getBoundingClientRect();
          for (const el of frame.querySelectorAll("*")) {
            if (el.closest(".sr-only") || el instanceof SVGElement) continue;
            if (el.querySelector(".sm-listen-ring") || el.classList.contains("sm-listen-ring")) continue;
            const r = el.getBoundingClientRect();
            if (r.width === 0) continue;
            const text = (el.textContent ?? "").slice(0, 30);
            if (r.right > fr.right + 1 || r.left < fr.left - 1) out.push(`outside frame: ${text}`);
            else if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0) out.push(`overflow: ${text}`);
          }
        }
        if (document.documentElement.scrollWidth > window.innerWidth + 1) out.push("page scrolls sideways");
        return out;
      });
      problems.push(...found.map((f) => `${theme}/${lang}: ${f}`));
    }
  }
  expect(problems).toEqual([]);
});
