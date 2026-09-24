# HANDOFF — pick up here (for the next Claude Code session)

Last updated: 2026-09-23 (after milestone 8).

## Read first
1. `CLAUDE.md` (process rules, golden rules). The repo uses **milestones** (see `docs/PROGRESS.md`), not the "phases" named in CLAUDE.md; PROGRESS.md maps each milestone to its phase.
2. `docs/PROGRESS.md` — milestone list with checkboxes and status.
3. `docs/DECISIONS.md` — D-001…D-093. Log new decisions in the same format (next number: **D-094**).
4. `docs/reports/milestone-N.md` — one report per finished milestone (same format for new ones).
5. `docs/TRD.md` §8 (scenarios), §9 (APIs, sync) for the current milestone.

## Owner's standing instructions
- Work milestone by milestone **without waiting for approval**; downloads are approved.
- End each milestone with: all tests + lint green, `docs/reports/milestone-N.md`, `python scripts/progress_mark.py N "<next step>"`, and a commit `milestone N: <summary>`.
- Never fake results; report misses honestly. Don't weaken tests to pass.
- Decisions already made by the owner are in DECISIONS.md, marked **(user)** (e.g. uv not conda, Gemini free tier for the LLM, jsqr + PIN fallback, features B5 removed).
- **LLM:** Google Gemini free tier via `backend/src/shiftmate/assistant/llm.py` (milestone 14), `google-genai` SDK, JSON mode, immediate offline fallback on 429/timeout/missing key. Everything must run without a key.
- **Secrets:** the owner puts `GEMINI_API_KEY` in the gitignored `.env` themselves. **Never ask for the key in chat, never print it, never commit it.**

## Environment (Windows, Git Bash)
- uv: `/c/Users/vgang/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe/uv.exe` (or `uv` if on PATH). pnpm: `/c/Users/vgang/AppData/Roaming/npm`.
- Set `PYTHONIOENCODING=utf-8`.
- Backend: `uv run --directory backend pytest -q`, `uv run --directory backend ruff check .` and `ruff format .`.
- Everything: `pnpm test:all`, `pnpm lint:all`, `pnpm contracts:gen` (run after any change to `backend/src/shiftmate/schema/`).
- Data (gitignored, regenerate on a new machine): `uv run --directory backend shiftmate sim generate --days 42 --seed 7` (~1 min), then `shiftmate ml train`, then `shiftmate eval all`.
- Bash heredocs sometimes fail on long Python edit scripts: write the script to a file and run it.
- New UI strings: add a YAML batch to `scripts/i18n/` (en/hi/ta; `null` removes a key), then run `uv run --directory backend python ../scripts/i18n_merge.py ../scripts/i18n/<file>.yaml` and `pnpm i18n:review`.

## Status
- Milestones 1–15: **done and committed** (the last is `milestone 15: voice and camera …`). Reports: `docs/reports/milestone-N.md`.
- Next: **milestone 16 (training hub)**. Decisions continue at **D-094**.
- Design system: every component is in `frontend/packages/ui` and on http://localhost:5174/_kitchen-sink. Components take all words through props; the vocabulary is under `ui.*` in the i18n files. `pnpm e2e` checks the kitchen sink for overflow in 3 themes × 3 languages. In Tamil the rail hides the machine segment, so the cab must show the machine ID in the Paused content header (D-068).
- `shiftmate edge headless` plays Ravi's shift at 60× and prints it beat by beat; `tests/test_headless.py` asserts every beat and determinism, and `tests/test_fleet_scale.py` uploads the same shift into a real Fleet Service. Keep both green.
- Fleet Service: `shiftmate fleet` (:8200). Its DuckDB file `data/fleet/fleet.duckdb` is seeded from history on first start (delete `data/fleet/` to reset). Only one process can open it at a time.

### Then milestones 10–18
Follow `docs/PROGRESS.md`. Open items the console milestone (13) should pick up: translations for the fleet suggestion keys (`suggest.add_truck`, `suggest.toolbox_idle`, `suggest.shutdown_briefing`), and which day the supervisor view opens on (see `docs/reports/milestone-9.md`, Observations).

## Known open items (reported, awaiting the owner)
D-051 lists evaluation targets still missed: anomaly precision 67 % and recall 42 % (target 80 %), and estimation p10–p90 coverage 64.5 % (target 75–85 %). The fix options each change TRD-specified behaviour and need the owner's decision. Don't tune on test data.
