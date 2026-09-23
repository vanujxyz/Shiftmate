import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // TRD §11.2 Offline: the app shell, fonts and locale files are pre-cached, so the cab opens and
    // runs with no network at all; data comes from the machine gateway and the tablet's own store
    // (src/offline/db.ts). The manifest and icon are static files in public/.
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "auto",
      manifest: false,
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,woff2,webmanifest}"],
        navigateFallback: "/index.html",
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  // .env lives at the repository root (TRD §14)
  envDir: fileURLToPath(new URL("../../..", import.meta.url)),
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
