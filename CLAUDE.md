# CLAUDE.md — How to build ShiftMate

You are building **ShiftMate**, an operator-first in-cab companion for Caterpillar machines, for a Caterpillar hiring hackathon. This file tells you exactly what to build, in what order, how to verify each step, and what never to do. Read it fully before writing code, and re-read the relevant section before each phase.

## 0. Sources of truth

| Question | Read |
|---|---|
| What does the user experience? Why does a feature exist? | `docs/PRD.md` |
| Schemas, algorithms, thresholds, APIs, stack, layout | `docs/TRD.md` |
| Colours, type, spacing, components, motion, icons, copy voice | `docs/DESIGN.md` + `frontend/packages/ui/src/tokens.css` |
| Build order, rules, conventions, done criteria | this file |
| Decisions made during the build | `docs/DECISIONS.md` |

Precedence when documents conflict: this file (process) → TRD (implementation) → PRD (behaviour) → DESIGN (visuals). If a conflict changes user-visible behaviour, stop and ask the user.

## 1. Golden rules

1. **Do not guess.** If the documents specify something, follow it exactly. If they are silent, choose the simplest option that is consistent with the PRD principles (PRD §5), implement it, and append an entry to `docs/DECISIONS.md` (format in §7). If the choice would change what judges see or what the PRD promises, stop and ask the user instead.
2. **Operator first.** When in doubt about UI or behaviour, choose what makes the operator's shift safer and easier with the least attention required.
3. **Config, not code.** Every threshold, weight, distance, time limit, lesson, rule, site and machine profile lives in `config/*.yaml` and is validated by pydantic. Engines never contain magic numbers beyond mathematical constants.
4. **Engines are pure.** No I/O, no clock reads, no randomness inside engines. Time and data come in as arguments. This keeps them testable and deterministic.
5. **Ground truth is sacred.** Engines, the edge runtime, the fleet service and the UI must never read `label_*` fields or operator `personality`. Only `shiftmate.eval` and simulator tests may read them. Enforce with a test that greps imports/field access.
6. **Tier-aware everywhere.** Every feature must check the machine's sensor tier and degrade gracefully (disable, or lower confidence and say so). Never crash or show fake data on a basic machine.
7. **Offline is normal.** Everything except the online LLM path and fleet sync must work with the network toggle off.
8. **No copyrighted manuals, no brand misuse.** Knowledge base content is written by you in plain language; never copy Caterpillar manuals or other copyrighted text. Do not use Caterpillar logos or trade dress. Refer to machines by model name only (e.g. "Cat 320").
9. **Design tokens only.** No hex colours, font names, raw pixel spacing or shadow values in app code. Use tokens from `packages/ui`. If a token you need is missing, add it to `tokens.css` following `DESIGN.md` and log the decision.
10. **Three languages, always.** Every user-facing string exists in `en`, `hi` and `ta`. Hindi and Tamil are real translations in natural, simple language an operator would use, not transliterations. A test enforces key completeness.
11. **Honest numbers.** Evaluation reports actual results, including misses. Never hard-code metrics. Label scale projections as projections.
12. **Understandable code.** The team must defend every line in Q&A. Prefer clear, commented, conventional code over clever code. Each engine module starts with a docstring explaining the algorithm in plain English and citing the TRD section.
13. **Small, verified steps.** Finish each phase's Definition of Done (DoD) before starting the next. Run the tests. Commit at the end of each phase with message `phase N: <summary>`.

## 2. Environment and commands

- OS: Windows (PowerShell) is the primary environment; commands must also work in bash. Do not require Docker, `make` or WSL.
- Python 3.12 via `uv`; Node 20+ via `pnpm`.
- Root `package.json` scripts (create these in Phase 0):
  - `pnpm dev:all` — runs edge (8100), fleet (8200), cab (5173), console (5174) with `concurrently`, coloured prefixes.
  - `pnpm test:all` — backend pytest, frontend vitest, contracts check.
  - `pnpm e2e` — Playwright demo test.
  - `pnpm lint:all` — ruff + eslint + tsc --noEmit.
  - `pnpm contracts:gen` — export JSON Schema from backend and generate TS types.
  - `pnpm setup:data` — `shiftmate sim generate`, `shiftmate ml train`, `shiftmate assistant index`, `shiftmate eval all`.
- Backend CLI (`typer`, entry point `shiftmate`): `edge`, `fleet`, `sim generate|scale`, `bench runtime`, `ml train`, `assistant index`, `eval all|idle|anomaly|estimation|assistant`, `schema export`, `config validate`.

## 3. Build phases

Work strictly in order. Each phase lists what to build (with TRD references) and its Definition of Done.

### Phase 0 — Scaffold
Build: repository layout exactly as TRD §3; `pyproject.toml` with dependencies (TRD §2); pnpm workspace with `apps/cab`, `apps/console`, `packages/ui`, `packages/contracts`, `packages/i18n`; root scripts (§2 above); `.env.example` (TRD §14); `.gitignore` (data/, models/, .env, node_modules, .venv); `docs/DECISIONS.md` with header; `README.md` skeleton; `fixtures/sample_rows.csv` with the brief's four rows verbatim:
```
Timestamp,Machine ID,Operator ID,Engine Hours,Fuel Used (L),Load Cycles,Idling Time (min),Seatbelt Status,Safety Alert Triggered
2025-05-01 08:00:00,EXC001,OP1001,1523.5,5.2,12,30,Fastened,No
2025-05-01 10:00:00,EXC001,OP1001,1524.8,3.8,2,55,Unfastened,Yes
2025-05-01 14:00:00,EXC001,OP1001,1526.5,6.1,10,15,Fastened,No
2025-05-02 09:00:00,EXC001,OP1001,1530.2,2.0,1,60,Unfastened,Yes
```
DoD: `uv sync` and `pnpm install` succeed; `pnpm dev:all` starts four placeholder servers; `pnpm test:all` runs (empty suites pass); lint passes.

### Phase 1 — Config and schemas
Build: all config files in TRD §4 with the given defaults and full content (all four sites, three machine profiles, twelve lessons with en/hi/ta text and quizzes, seven checklist items, intents keywords); `config_loader.py` with pydantic validation; all pydantic schemas in TRD §5; `schema export` → JSON Schema → `packages/contracts` TS types; `config validate` command.
DoD: `shiftmate config validate` passes; a test loads every config; a test parses `fixtures/sample_rows.csv` into `IntervalRecord` (extension fields null); contracts generated and committed; i18n completeness test in place for lessons/checklist text.

### Phase 2 — Simulator (history mode)
Build: `shiftmate.sim` world model per TRD §7 (weather, ground, night, trucks + dispatch log, workers, machine state machines, operators with personalities, tasks, productivity, labels); history generator writing Parquet + DuckDB; deterministic seeding.
DoD: `shiftmate sim generate --days 42 --seed 7` completes in reasonable time on 16 GB RAM (chunked, 30 s ticks); all invariants in TRD §7.5 pass as tests (hypothesis where noted); determinism test passes; a short `data/history/SUMMARY.md` is written with row counts, label distributions and per-site condition stats; OP1001/EXC001 exist with the TRD §7.1 attributes.

### Phase 3 — Engines
Build in this order, each with unit tests before moving on: `rule_eval` (safe evaluator) → machine state (TRD §6.1) → risk (§6.3) → safety (§6.2) → alert policy (§6.8) → idle-reason (§6.4) → interval builder (§6.5) → anomaly features and baselines (§6.6; model training comes in Phase 4) → lesson recommender (§6.9) → report parser offline path (§6.10).
DoD: one test per idle reason × sensor tier; alert pre-emption, cooldown, dedupe and paused-delivery tests; risk hysteresis test; rule evaluator rejects attribute access, calls and imports; ground-truth access guard test (golden rule 5); all engines have plain-English module docstrings.

### Phase 4 — ML training and evaluation
Build: `shiftmate ml train` → anomaly IsolationForests per (type, tier) and estimation quantile models with manifest (TRD §6.6, §6.7); fleet patterns computation; `shiftmate eval idle|anomaly|estimation` writing sections of `docs/EVAL.md` (TRD §12).
DoD: models saved under `models/` with manifests; `EVAL.md` contains real metrics tables, confusion matrix for idle reasons, per-tier breakdown, estimation coverage; if a target is missed, investigate the simulator/engine once, fix genuine bugs only (never tune on test data), then report honestly and log the analysis in `DECISIONS.md`.

### Phase 5 — Edge Gateway
Build: `MachineRuntime` pipeline wiring engines (TRD §1.1); EdgeGateway FastAPI app with all REST endpoints and both WebSockets (TRD §9.1); live mode world clock with speed control; scenario player with seek (TRD §8) and both scenario files; local SQLite store; outbox and sync (TRD §9.3); estimation model loading from fleet with cached fallback; `/proximity/camera` merging camera readings into the proximity signal (source `camera`, overrides sensor when fresher than 1 s).
DoD: API tests for every endpoint; a headless run of `ravi_shift` at 60× produces the expected event sequence (assert beat outcomes: WARM_UP segment, WAITING_FOR_TRUCK segment with supervisor site item, P1 seatbelt, proximity tiers escalating, heat band change to amber, UNATTENDED_RUNNING, network off → outbox grows → on → drains to 0); determinism: two runs produce identical event logs.

### Phase 6 — Fleet Service
Build: FastAPI app (TRD §9.2) on DuckDB; idempotent ingest; site summary, idle causes with plain-language suggestions, safety, privacy-respecting trends (`privacy.yaml`); fleet overview and patterns; model registry endpoints; scale stats; `/ws/fleet`; `shiftmate sim scale` and `shiftmate bench runtime` (TRD §7.6) writing the scale section of `EVAL.md`.
DoD: API tests; privacy test (trends never return groups smaller than the minimum; operator detail only for shared event types); scale run of 10,000 machines completes and `/scale/stats` shows totals, ingest rate and the labelled 1.6 M projection.

### Phase 7 — Design system integration (requires `docs/DESIGN.md`)
**If `docs/DESIGN.md` or `frontend/packages/ui/src/tokens.css` does not exist, stop and ask the user to add the Claude Design output before continuing.** Do not invent a visual style.
Build: `packages/ui` — tokens wired into Tailwind v4 `@theme`; day, night and sunlight themes; semantic safety tokens; self-hosted fonts supporting Latin, Devanagari and Tamil; core components listed in `DESIGN.md` (status rail, alert takeover/banner/strip, task row with range bar, reason chip, time-split bar, sparkline, push-to-talk button, large toggle, PIN pad, lesson card, drill canvas frame, map legend, empty/error/offline states); illustrations and machine-state glyphs as SVG components; a `/_kitchen-sink` route in the console showing every component in all themes and all three languages.
DoD: kitchen sink renders every component in 3 themes × 3 languages without overflow; contrast checks meet `DESIGN.md` targets; no hex/font literals outside `packages/ui` (add a lint rule or test).

### Phase 8 — Cab app
Build all routes and persistent elements in TRD §11.2, driven by the Edge Gateway; Working/Paused modes; alert layer behaviour exactly as `alert_policy.yaml`; i18n; PWA with pre-caching and Dexie storage; stale-data and reconnect states.
DoD: vitest for alert layer and mode switching; manual check at 1280×800 and 1024×768; with network toggled off the app remains fully usable except the online-only assistant path; every string translated.

### Phase 9 — Console app
Build: site map, supervisor, fleet, demo control, eval routes (TRD §11.3).
DoD: map ≥ 30 fps with the full Chennai site; demo control can load, play, pause, change speed, seek every beat and toggle network; eval page renders `EVAL.md` metrics.

### Phase 10 — Assistant
Build: knowledge base files (TRD §10.1, written by you, en plus hi/ta for key safety files, sample-content banner), indexing, hybrid retrieval, online answering with validation, offline answering, intents, report parser online path, assistant eval set and runner (TRD §10.6).
DoD: `shiftmate eval assistant` writes results to `EVAL.md` (online and offline modes); a bypass request test always refuses; missing API key → offline mode with a clear UI message.

### Phase 11 — Voice and camera
Build: push-to-talk with live transcript in en-IN/hi-IN/ta-IN; spoken P1/P2 alerts; voice intents wired to actions; voice report flow; camera proximity panel with MediaPipe, calibration, smoothing and posting (TRD §11.2); scenario `worker_near` beat uses camera when active.
DoD: every voice action has a tap equivalent; with the camera enabled and a person walking towards it, tiers escalate caution → danger → critical and the P1 takeover appears; camera protocol results recorded in `EVAL.md`.

### Phase 12 — Training hub
Build: lesson player (narrated cards via speech synthesis, quiz), hazard drill canvas (five hazard scenarios, stop by tap or voice, reaction time scoring), recommendations and pause-only offers, instructor booking, progress view.
DoD: the scenario's truck-delay beat offers a lesson while waiting, and the step-out beat recommends `L-SHUTDOWN`; completing a lesson updates progress; drill results stored and shown over time.

### Phase 13 — Demo polish and end-to-end
Build: Playwright e2e for `ravi_shift` at 30× (TRD §13); `fleet_tour` scenario in the console; captions toggle; a scripted "reset demo" button; README with setup, run and demo instructions; screenshots and a short architecture diagram (SVG) in `docs/` for the slides.
DoD: `pnpm e2e` passes twice in a row; a clean clone + `pnpm setup:data` + `pnpm dev:all` reaches a working demo following only the README.

### Phase 14 — Final evaluation and review
Run `shiftmate eval all`; review `EVAL.md`; run the full test suite and lint; walk through the PRD requirements table and confirm each `F-…` ID is implemented, noting its location in `docs/TRACEABILITY.md` (ID → files → tests → demo beat).
DoD: every Must requirement is traced and demonstrated; all tests green; `DECISIONS.md` complete.

## 4. Conventions

**Python**
- `src/` layout, package `shiftmate`; type hints everywhere; pydantic v2 models for all data crossing module boundaries; `ruff` format and lint.
- Time: use `datetime` with timezone; the simulation clock is injected (`Clock` protocol), never `datetime.now()` in engines or sim.
- Randomness: `numpy.random.Generator` passed in, seeded from config/CLI; no global random state.
- Logging: `logging` with structured messages; no prints outside CLI output.
- Errors: raise specific exceptions; API layer maps them to `{error: {code, message}}`.

**TypeScript / React**
- Strict TS; function components; hooks for data (`useCabSocket`, `useShift`, …); Zustand stores for live state; React Query for REST.
- Types only from `packages/contracts` for API data; never hand-write duplicate API types.
- Components from `packages/ui`; app code composes them. No inline styles except dynamic positions (map, charts).
- Accessibility: semantic elements, labelled controls, visible focus, reduced-motion support.
- Every user-visible string through `t()`.

**Naming**
- IDs: `EXC001`, `WHL014`, `DOZ003`, `OP1001`, sites `CHN-HWY-01`, lessons `L-…`, drills `D-…`, requirements `F-…`.
- Idle reasons and rule IDs are UPPER_SNAKE and identical across backend, contracts, i18n keys (`idle.WAITING_FOR_TRUCK`).

**Copy voice** (details in `DESIGN.md`): plain words, short sentences, active voice, no blame. Say what happened and what to do. Examples: "Truck hasn't arrived. Your waiting time is counted as a site delay." · "Engine was running with the cab empty for 6 minutes. Switch off before stepping out." · "Seatbelt off while working. Fasten it now."

## 5. Things you must not do
- Do not read ground-truth labels or personalities outside `eval` and simulator tests.
- Do not use Python `eval`/`exec` for rules.
- Do not add a chart library, UI kit, or CSS framework beyond those in TRD §2.
- Do not invent a visual style; wait for `DESIGN.md`.
- Do not add login systems, payments, predictive maintenance, parts ordering or real Caterpillar integrations.
- Do not show operator-level detail to the supervisor outside `privacy.yaml` rules.
- Do not block the demo on the network: any online-only feature must have an offline path.
- Do not hard-code metrics, fake results, or tune models on test data.
- Do not copy text from Caterpillar manuals or any copyrighted source.
- Do not remove or weaken a test to make it pass; fix the code or log why the test was wrong.

## 6. When something is ambiguous — decision checklist
1. Is it specified in TRD, then PRD, then DESIGN? Follow it.
2. Does a PRD principle (§5) settle it? Apply it.
3. Is there a simpler option that keeps the demo beats and requirement IDs intact? Choose it and log it.
4. Would it change what the judges see or any Must requirement? Ask the user.

## 7. Decision log format (`docs/DECISIONS.md`)
```
## D-<nnn> — <short title>
Date: <yyyy-mm-dd> · Phase: <n> · Requirement(s): <F-… / TRD §…>
Context: <what was unclear>
Decision: <what you chose>
Why: <reason, referencing principles>
Alternatives: <what else was considered>
```
Seed entries in Phase 0: D-001 load cycle definition (PRD §7), D-002 interval semantics, D-003 safety alert definition, D-004 sample rows are fixtures not calibration.

## 8. Demo readiness checklist (run before handing over)
- [ ] `pnpm setup:data` from a clean state succeeds.
- [ ] `pnpm dev:all` starts all four services; cab at 1280×800, console on a second window.
- [ ] `ravi_shift` beats all behave as PRD §9, at 1× and when seeking.
- [ ] Camera proximity works after calibration; the simulated path works without a camera.
- [ ] Network toggle: offline assistant answer, reports queue, sync drains after reconnect.
- [ ] Language switch to Tamil and Hindi shows complete translations and spoken alerts.
- [ ] `fleet_tour` shows the basic-tier loader and the 10,000-machine scale run with projection.
- [ ] `EVAL.md` is current; eval page shows it.
- [ ] No console errors in either app during the full scenario.
- [ ] README instructions verified.
