// Frontend lint (the backend uses ruff). Flat config, ESLint 10.
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/node_modules/**", "**/dist/**", "**/dev-dist/**", "backend/**", "data/**", "models/**", "playwright-report/**", "test-results/**", "frontend/packages/contracts/src/generated.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    languageOptions: { globals: { ...globals.browser } },
    rules: { ...reactHooks.configs.recommended.rules },
  },
  {
    files: ["**/*.{js,mjs}", "**/vite.config.ts", "playwright.config.ts"],
    languageOptions: { globals: { ...globals.node } },
  },
);
