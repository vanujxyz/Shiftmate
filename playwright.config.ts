// End-to-end tests (`pnpm e2e`). Uses the installed Chrome instead of downloading a browser (D-025).
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  use: { baseURL: "http://localhost:5173", channel: "chrome", viewport: { width: 1280, height: 800 } },
  webServer: {
    command: "pnpm --filter cab dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
