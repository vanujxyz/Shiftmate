# Prompt for the next Claude Code session

Paste everything below the line into Claude Code, opened in the cloned repo folder.

---

You are continuing to build **ShiftMate**, an operator-first in-cab companion for Caterpillar machines (a hackathon project). An earlier Claude Code session built milestones 1–7 and half of milestone 8, then ran out of usage. Your job is to pick up exactly where it stopped and continue milestone by milestone to milestone 18.

## 1. Read these first, in this order (do not skip)
1. `HANDOFF.md` (repo root): the exact state, what milestone 8 already contains, and what remains.
2. `CLAUDE.md`: process rules, golden rules and things you must never do. Its "phases" map to the milestones in PROGRESS.md.
3. `docs/PROGRESS.md`: all 18 milestones with checkboxes, goals and requirement IDs.
4. `docs/DECISIONS.md`: decisions D-001…D-070. Entries marked **(user)** are the owner's decisions; never reverse them. Add new entries in the same format, starting at **D-071**.
5. `docs/TRD.md`: implementation spec. Read §8 (scenarios) and §9 (APIs, WebSockets, sync) now; read other sections as each milestone needs them.
6. `docs/PRD.md`: behaviour and requirement IDs (F-…); §9 is the demo story (Ravi's shift).
7. `docs/DESIGN.md` and `frontend/packages/ui/src/tokens.css`: the visual system (from milestone 10 on).
8. `docs/reports/milestone-10.md`: the report format to copy for every milestone.
9. `docs/EVAL.md`: the current evaluation results.

## 2. Owner's standing instructions
- Continue milestone by milestone **without waiting for approval**. The owner has approved all needed downloads.
- Every milestone ends with:
  - all tests and lint green;
  - a report in `docs/reports/milestone-N.md`, with the same sections as milestone 7;
  - `python scripts/progress_mark.py N "<next step text>"`;
  - a git commit `milestone N: <summary>`, pushed to `origin main` (https://github.com/vanujxyz/Shiftmate).
- **Never fake results or hard-code metrics.** Report misses honestly. Never tune on test data. Never weaken or delete a test to make it pass.
- If something would change what the judges see or a PRD "Must" requirement, and the docs don't settle it, stop and ask the owner. Otherwise choose the simplest option and log it in DECISIONS.md.
- **Secrets:** the owner puts `GEMINI_API_KEY` in the gitignored `.env` themselves. Never ask for the key, never print it, and never commit `.env`.
- **LLM (milestone 14):**
  - Use the Google Gemini free tier through a provider layer in `backend/src/shiftmate/assistant/llm.py`, with the `google-genai` SDK and JSON mode.
  - On a 429, a timeout or a missing key, fall back immediately to the offline answer path. Everything must run without a key.
  - In evaluation, pause between calls and cache responses on disk.
  - Env vars: `SHIFTMATE_LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, `SHIFTMATE_LLM_MODEL=<exact AI Studio model name>`.
- **Owner decisions to respect:**
  - uv, not conda.
  - QR sign-in uses jsqr with a PIN fallback; the demo PIN is the operator number.
  - Removed features stay removed: Send a truck, Voice note to Ravi, camera clip, call supervisor by voice, night-shift demo button.
  - The owner installs the speech packs themselves; the README must say speech recognition needs real internet.
  - Keep the names "Ask Cat" and "Cat dealer training centre" in text only, with no logos or trade dress.
  - Translated strings are listed for review in `docs/TRANSLATIONS_REVIEW.md` (regenerate with `pnpm i18n:review`).

## 3. Tech stack
- **Backend:** Python 3.12, managed with **uv**. Package `shiftmate` under `backend/src/`, with the CLI entry point `shiftmate` (typer).
  - Web and schemas: FastAPI, uvicorn, pydantic v2 and pydantic-settings, SQLAlchemy (SQLite, edge store), httpx.
  - Data and ML: pandas, pyarrow, DuckDB, scikit-learn (IsolationForest), LightGBM (quantile models), joblib.
  - Assistant: sentence-transformers (CPU torch) and rank-bm25.
  - Quality: pytest, hypothesis and ruff (line length 100).
- **Frontend:** a **pnpm** workspace under `frontend/`, with apps `apps/cab` (port 5173) and `apps/console` (5174), and packages `packages/ui`, `packages/contracts` and `packages/i18n` (en/hi/ta).
  - Framework and styling: React 19, Vite, Tailwind v4 (`@theme` tokens).
  - Checks: TypeScript ~6.0 (pinned, because typescript-eslint doesn't support 7), vitest, eslint, and Playwright using the installed Chrome (`channel: "chrome"`).
- **Services:** the Edge Gateway on :8100 (the machine side; built) and the Fleet Service on :8200 (milestone 9).
- **Contracts:** pydantic models are exported to JSON Schema, then to TypeScript in `frontend/packages/contracts/src/generated.ts`. Run `pnpm contracts:gen` after any change under `backend/src/shiftmate/schema/`, and never hand-write API types in the frontend.
- **Config:** all thresholds, rules, sites, lessons and timings live in `config/*.yaml`, validated at load (`shiftmate config validate`). No magic numbers in engines.

## 4. Set up a fresh machine (Windows; commands work in Git Bash or PowerShell)
1. Install these tools if they're missing:
   - Git.
   - Python 3.12 (uv can install it with `uv python install 3.12`).
   - **uv**: `winget install astral-sh.uv`, or `pip install uv`.
   - **Node.js 20+** and **pnpm**: `npm install -g pnpm`.
   - Google Chrome, for the Playwright end-to-end test.
2. Clone the repo and install the dependencies:
   ```
   git clone https://github.com/vanujxyz/Shiftmate.git
   cd Shiftmate
   uv sync --directory backend
   pnpm install
   ```
3. Create `.env` from `.env.example`. The owner fills in `GEMINI_API_KEY` later; the app works without it.
4. Generate the data. `data/` and `models/` are gitignored, so they must be rebuilt:
   ```
   uv run --directory backend shiftmate sim generate --days 42 --seed 7
   uv run --directory backend shiftmate ml train
   uv run --directory backend shiftmate eval all
   ```
   History generation takes about 1 minute and the replay a few minutes. The last command rewrites `docs/EVAL.md`; check that the numbers match the committed ones (determinism).
5. Check the setup:
   ```
   uv run --directory backend shiftmate config validate
   pnpm test:all
   pnpm lint:all
   ```
6. Run everything with `pnpm dev:all`. The edge API docs are at http://localhost:8100/docs.

**Windows tips:**
- Set `PYTHONIOENCODING=utf-8`, because the Hindi and Tamil text breaks the default console encoding.
- If uv or pnpm is not on PATH in Git Bash, use their full paths, or PowerShell.
- Long Python edit scripts inside bash heredocs can fail to parse. Write them to a file and run that instead.

**New UI strings** must exist in en, hi and ta (a test enforces this). Add a YAML batch to `scripts/i18n/`, then:
```
uv run --directory backend python ../scripts/i18n_merge.py ../scripts/i18n/<file>.yaml
pnpm i18n:review
```

## 5. Current state and your first tasks
- Milestones 1–10 are done. The last commit is `milestone 10: …`.
- **Step 1:** run the full backend suite, `pnpm test:all` and `pnpm lint:all`, and check they are green before changing anything (the backend suite takes about 3 minutes).
- **Step 2:** carry on with milestones 11 → 18 from `docs/PROGRESS.md`. Build screens from the components in `frontend/packages/ui` (see `/_kitchen-sink` in the console); never style app code with raw values (a test enforces this).
- `uv run --directory backend shiftmate edge headless` prints Ravi's shift beat by beat; the Fleet Service runs with `shiftmate fleet` on :8200.

## 6. Golden rules to remember (full list in CLAUDE.md)
- **Ground truth is sacred.** Only `shiftmate.sim`, `shiftmate.eval` and simulator tests may read `label_*` fields, operator personalities, `data/history/truth/` or `cfg.simulator`. A guard test (`tests/test_ground_truth_guard.py`) enforces this.
- **Engines are pure:** no I/O, no clock reads, no randomness. The simulator uses seeded `numpy` Generators and must stay deterministic.
- **Tier-aware:** basic-tier machines degrade gracefully. Never crash, and never show fake data.
- **Offline is normal:** only the online LLM path and fleet sync may need the network.
- **Design tokens only** in app code: no hex colours, font names or raw pixel values.
- **No copyrighted manuals and no Caterpillar logos.** Refer to machines by model name only ("Cat 320").
- **Each engine module** starts with a plain-English docstring that cites its TRD section. Code should be clear enough for the team to defend in Q&A.
