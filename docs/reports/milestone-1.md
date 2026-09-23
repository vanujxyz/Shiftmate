# Milestone 1 — Scaffold

## What was built
An empty but working project skeleton: edge (8100) and fleet (8200) FastAPI servers with `/health`, cab (5173) and console (5174) Vite/React placeholder pages with live health status and a language switch, a pnpm workspace (`cab`, `console`, `ui`, `contracts`, `i18n`), root scripts, the `shiftmate` CLI, contracts generation from pydantic, i18n completeness tests and the translations review script. Design files moved into `docs/` and `frontend/packages/ui/src/`.

## How to test (PowerShell, new window, repo folder)
```
pnpm test:all      # backend 7 passed; frontend 7 + 3 + 3 passed; "Contracts are up to date."
pnpm lint:all      # no errors
pnpm dev:all       # then open http://localhost:8100/health, :8200/health, :5173, :5174
pnpm e2e           # with dev:all running: 1 passed
```

## Tests run
Backend pytest 7/7, vitest 13/13, contracts check OK, ruff/eslint/tsc clean, Playwright 1/1 in Chrome.

## Decisions
D-001…D-024 (planning), D-025 TypeScript pinned to 6.0.3 (typescript-eslint support), Playwright uses installed Chrome; D-026 font family names fixed in tokens.css.

## Downloads
uv 0.12.18, pnpm 12.5.1, Python packages (~1 GB incl. CPU PyTorch 2.14), Node packages.

## Known issues
Later-milestone CLI commands exit with "arrives in milestone N". Pages are placeholders until milestone 10.
