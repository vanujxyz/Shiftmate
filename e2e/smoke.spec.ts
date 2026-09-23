// Milestone 1: the cab app loads in Chrome with the Anek font and translated text.
// The full ravi_shift end-to-end test replaces this in milestone 17.
import { expect, test } from "@playwright/test";

test("cab app loads and uses the Anek font", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "ShiftMate" })).toBeVisible();
  await page.getByRole("button", { name: "தமிழ்" }).click();
  await expect(page.getByText("கேபின் செயலி", { exact: false })).toBeVisible();
  const loaded = await page.evaluate(async () => {
    await document.fonts.ready;
    return [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family);
  });
  expect(loaded.join(",")).toContain("Anek Tamil Variable");
});
