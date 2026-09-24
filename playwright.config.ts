// End-to-end tests (`pnpm e2e`). Uses the installed Chrome instead of downloading a browser (D-025).
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: "http://localhost:5173", channel: "chrome", viewport: { width: 1280, height: 800 } },
  webServer: [
    {
      // the edge gateway, for the ravi_shift end-to-end test
      command: "uv run --directory backend shiftmate edge",
      url: "http://127.0.0.1:8100/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "pnpm --filter cab dev",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "pnpm --filter console dev",
      url: "http://localhost:5174",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      // the built cab PWA (service worker included) for the offline test
      command: "pnpm --filter cab build && pnpm --filter cab preview --port 4173 --strictPort",
      url: "http://localhost:4173",
      reuseExistingServer: true,
      timeout: 180_000,
    },
  ],
});
