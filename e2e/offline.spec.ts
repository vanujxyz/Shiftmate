/**
 * F-CAB-04 / TRD §11.2 Offline: once the cab has been opened, it opens again with no network at all.
 * The built PWA's service worker pre-caches the app shell, fonts and strings; data then comes from
 * the machine gateway, and the screen says calmly when that cannot be reached.
 */
import { expect, test } from "@playwright/test";

test.use({ baseURL: "http://localhost:4173" });

test("the cab opens with the network off", async ({ page, context }) => {
  await page.goto("/start");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  // the first visit installs the worker; from the next load on it serves the pages
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Start your shift" })).toBeVisible();
  await page.getByRole("button", { name: "தமிழ்" }).click();
  await expect(page.getByRole("heading", { name: "உங்கள் பணியைத் தொடங்குங்கள்" })).toBeVisible();

  // any cab address opens offline (the shell answers every route)
  await page.goto("/safety");
  await expect(page).toHaveURL(/\/start$/);
  const fonts = await page.evaluate(async () => {
    await document.fonts.ready;
    return [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family);
  });
  expect(fonts.join(",")).toContain("Anek Tamil Variable");
  await context.setOffline(false);
});
