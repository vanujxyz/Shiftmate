// The cab app loads in Chrome with the Anek font and translated text; with no session it opens
// the Start screen, whose language choice works even before the machine gateway answers.
// The full ravi_shift end-to-end test replaces this in milestone 17.
import { expect, test } from "@playwright/test";

test("cab app loads and uses the Anek font", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/start$/);
  await expect(page.getByRole("heading", { name: "Start your shift" })).toBeVisible();
  await page.getByRole("button", { name: "தமிழ்" }).click();
  await expect(page.getByRole("heading", { name: "உங்கள் பணியைத் தொடங்குங்கள்" })).toBeVisible();
  const loaded = await page.evaluate(async () => {
    await document.fonts.ready;
    return [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family);
  });
  expect(loaded.join(",")).toContain("Anek Tamil Variable");
});
