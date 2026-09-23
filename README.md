# ShiftMate

An operator-first, in-cab companion for Caterpillar machines, built for a Caterpillar hiring hackathon ("Smart Operator Assistant for CAT machinery"). It looks out for the operator; it does not watch them.

> **Status:** under construction. See [docs/PROGRESS.md](docs/PROGRESS.md) for what is built so far.

> Sample manual content written for this prototype. A production system would use official Cat Operation & Maintenance Manuals. "Cat" is used only descriptively (for example "Cat 320"); no logos or trade dress.

## What is in the repository

| Folder | What it holds |
|---|---|
| `docs/` | PRD (what and why), TRD (how), DESIGN (visual system), DECISIONS (decision log), PROGRESS (build plan), EVAL (measured results, generated) |
| `config/` | Every threshold, rule, site, machine profile and lesson, as YAML |
| `scenarios/` | Scripted demo scenarios (`ravi_shift`, `fleet_tour`) |
| `knowledge/` | Team-written manual content for the assistant |
| `fixtures/` | The brief's four sample rows, verbatim |
| `backend/` | Python: edge gateway, fleet service, simulator, engines, assistant, evaluation |
| `frontend/` | React: cab app, console app, shared UI, contracts, translations |

## Requirements

- Windows 10/11 (PowerShell) or any bash shell
- Python 3.12 managed by [uv](https://docs.astral.sh/uv/)
- Node.js 20 or newer and [pnpm](https://pnpm.io/)
- Google Chrome (demo browser: speech and camera)

Install the two tools once, if you do not have them:

```powershell
winget install --id astral-sh.uv -e
npm install -g pnpm
```

Open a **new** PowerShell window afterwards so both commands are on the PATH.

## Setup

From the repository folder:

```powershell
uv sync --directory backend
pnpm install
Copy-Item .env.example .env
```

`.env` is optional. Without an LLM key everything still works: the assistant and the report parser run in offline mode, and the app says so.

### Optional: online assistant (Google Gemini free tier)

Edit `.env` and set:

```
SHIFTMATE_LLM_PROVIDER=gemini
GEMINI_API_KEY=<your key from Google AI Studio>
SHIFTMATE_LLM_MODEL=<exact model name from Google AI Studio>
```

The free tier has per-minute and per-day limits. When a limit is hit, the key is missing, or the call times out, ShiftMate immediately uses its offline answer and shows the offline label.

## Run

```powershell
pnpm dev:all
```

This starts four services with coloured prefixes:

| Service | URL |
|---|---|
| Edge gateway (machine side) | http://localhost:8100/health · API docs at http://localhost:8100/docs |
| Fleet service (cloud side) | http://localhost:8200/health · API docs at http://localhost:8200/docs |
| Cab app (operator tablet) | http://localhost:5173 |
| Console app (supervisor) | http://localhost:5174 |

Stop everything with `Ctrl+C`.

## Tests and checks

```powershell
pnpm test:all      # backend pytest, frontend vitest, contracts check
pnpm lint:all      # ruff, eslint, TypeScript
pnpm e2e           # Playwright in the installed Chrome
pnpm i18n:review   # rewrite docs/TRANSLATIONS_REVIEW.md
```

## Demo notes

- **Speech needs real internet.** Chrome's speech recognition sends audio to Google, so voice input needs a working internet connection at the venue. This is separate from the demo's simulated network toggle, which only cuts the edge gateway off from the fleet service and the LLM. Every voice action also has a button.
- For spoken alerts in Tamil and Hindi, install the Windows Tamil and Hindi speech packs (Settings → Time & language → Language & region → add the language → include speech).

Demo instructions are completed in milestone 17.
