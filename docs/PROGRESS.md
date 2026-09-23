# ShiftMate — Build progress

**Next step:** Milestone 4 (engines A: safety core) in progress.

**Autonomy note (2026-09-23):** the user authorised continuing through all milestones without waiting for approval, and approved all needed downloads. Each milestone is still tested, committed, and reported in `docs/reports/milestone-N.md`.

Rules: one milestone at a time. Never start milestone N until the user writes "Proceed to milestone N". Each milestone ends with tests + lint passing, a git commit `milestone N: <summary>`, a milestone report, and an update to this file.

Status values: `not started` · `in progress` · `done` (built, tests pass, waiting for review) · `approved` (the user has approved it).

---

## A. Environment (approved)

| Item | Found | Proposal |
|---|---|---|
| OS / shell | Windows 11 Home, PowerShell 5.1, Git Bash 5.3 | Use as is |
| git | 2.55 | Use as is (repo initialised on `main`) |
| Python | 3.12.10 (python.org install) | Use it through `uv` (no second Python download needed) |
| Anaconda | 25.11.1 at `C:\Users\vgang\anaconda3` (Python 3.13; envs `base`, `capstone`); not on PATH | Leave it alone; not used by the project |
| uv | 0.12.18 (installed with winget) | Installed in milestone 1 |
| Node.js / npm | 24.19 / 11.17 | Use as is (TRD needs 20 or newer) |
| pnpm | 12.5.1 (installed with npm) | Installed in milestone 1 |
| PostgreSQL | 18.4, service running | Not used (TRD uses SQLite + DuckDB) |
| Chrome / Edge | Chrome 154, Edge 153 | Chrome is the demo browser (speech + camera); Playwright uses installed Chrome |
| GPU | RTX 3050 Laptop 4 GB | Not needed; CPU-only PyTorch |
| RAM / disk | 15.7 GB / 308 GB free | Enough |

Approved by the user (2026-09-23): uv (not conda); install uv, pnpm and the milestone 1 packages; jsqr; later downloads (embedding model, MediaPipe model, google-genai) approved in principle but announced first. LLM provider: Google Gemini free tier instead of Anthropic (D-021). All planning decisions are D-005…D-024 in docs/DECISIONS.md.

---

## B. Milestones

### Milestone 1 — Scaffold (CLAUDE Phase 0) · Status: done
Goal: an empty but working project skeleton where every command runs.
- [x] 1. Move `DESIGN.md` → `docs/DESIGN.md`, `tokens.css` → `frontend/packages/ui/src/tokens.css`, `SUMMARY.md` → `docs/DESIGN_SUMMARY.md`
- [x] 2. Repository layout per TRD §3 (folders with placeholders)
- [x] 3. `backend/pyproject.toml` (TRD §2 deps), `uv sync`, `uv.lock`; `shiftmate` typer CLI with placeholder commands
- [x] 4. pnpm workspace: `apps/cab`, `apps/console`, `packages/ui`, `packages/contracts`, `packages/i18n`; `pnpm-lock.yaml`
- [x] 5. Root scripts: `dev:all`, `test:all`, `e2e`, `lint:all`, `contracts:gen`, `contracts:check`, `setup:data`
- [x] 6. Placeholder edge (8100) + fleet (8200) FastAPI apps with `/health`; placeholder cab (5173) + console (5174) Vite apps
- [x] 7. `.env.example`, `.gitignore`, `README.md` skeleton, `docs/DECISIONS.md` with D-001…D-004 + decisions from planning
- [x] 8. `fixtures/sample_rows.csv` (4 rows verbatim)
- [x] 9. ruff, eslint, tsc, pytest, vitest wired; empty suites pass
- [x] 10. Commit `milestone 1: scaffold`
Requirements: groundwork for all. You will see: `pnpm dev:all` starting four servers; two blank pages at localhost:5173 and :5174; `/health` JSON at :8100 and :8200.
Downloads: uv, pnpm, Python packages (~450 MB download, ~1.8 GB installed incl. CPU PyTorch), Node packages (~500 MB).

### Milestone 2 — Config and schemas (Phase 1) · Status: done
Goal: every rule, threshold, site, machine and lesson lives in validated config, and backend data types are shared with the frontend.
- [x] 1. `config/` files per TRD §4: 3 machine profiles, sensor tiers, 4 sites, safety rules, risk model, alert policy, idle rules, privacy
- [x] 2. `lessons.yaml` — 12 lessons, en/hi/ta text, cards and quizzes; `checklist.yaml` — 7 items en/hi/ta
- [x] 3. `config_loader.py` with pydantic validation (fails fast with clear messages)
- [x] 4. Pydantic schemas TRD §5 (machines, operators, tasks, SignalTick, IntervalRecord, Event, IdleSegment, training)
- [x] 5. `shiftmate schema export` → JSON Schema → `packages/contracts` TS types; `contracts:check`
- [x] 6. `shiftmate config validate`
- [x] 7. Tests: load all configs; parse `sample_rows.csv` into `IntervalRecord`; lesson/checklist i18n completeness
Requirements: F-FLT-01, F-FLT-02, F-FLT-06, F-START-04 (content), F-LRN-01 (content), P-06.
You will see: `shiftmate config validate` printing a pass summary; generated TS types.

### Milestone 3 — Simulator and history data (Phase 2) · Status: done
Goal: a realistic, deterministic simulated world that generates 42 days of fleet history with ground truth.
- [x] 1. World model: weather (daily cycle, rain Markov chain, Rothfusz heat index), ground, night, visibility
- [x] 2. Trucks + dispatcher + dispatch log + shortage windows; workers
- [x] 3. Machine state machines per task (warm-up, cycles, breaks, travel), fuel, engine hours
- [x] 4. 80 operators with personalities (sim-only), 60 machines, tiers by model year; OP1001/EXC001 and WHL014 fixed
- [x] 5. Tasks and productivity (emergent durations); ground-truth labels
- [x] 6. History generator: chunked, 30 s ticks → Parquet + DuckDB; `shiftmate sim generate --days 42 --seed 7`
- [x] 7. Invariant tests (tick-level ones now; interval-level ones in milestone 5), determinism test, `data/history/SUMMARY.md`
Requirements: supports F-INS-*, F-SHIFT-02, F-FLT-04/05/07 (data).
You will see: the generate command's runtime and the `SUMMARY.md` with row counts and label distributions.

### Milestone 4 — Engines A: safety core (Phase 3, first half) · Status: not started
Goal: the safety brain — safe rule evaluator, machine state, risk level, safety rules and alert discipline.
- [ ] 1. `rule_eval` safe expression evaluator (rejects attribute access, calls, imports)
- [ ] 2. Machine state + Paused/Working mode + continuous operation (TRD §6.1)
- [ ] 3. Risk engine with hysteresis and effective thresholds (§6.3)
- [ ] 4. Safety engine: sustain, cooldown, tier-disabled rules (§6.2)
- [ ] 5. Alert policy: priority queue, single interrupting alert, pre-emption, cooldown, dedupe, paused-only P3/P4, P1 escalation (§6.8)
- [ ] 6. Ground-truth access guard test (golden rule 5)
Requirements: F-SAFE-01, 02, 04, 05, 06, 07, 08, F-INS-04, F-FLT-02.
You will see: pytest output listing each engine test (e.g. hysteresis, pre-emption, cooldown).

### Milestone 5 — Engines B: insight core + history pipeline (Phase 3, second half) · Status: not started
Goal: idle reasons, 15-minute interval records, anomaly features, lesson recommendations and offline report parsing.
- [ ] 1. Idle-reason engine (§6.4) — one test per reason × sensor tier
- [ ] 2. Interval builder (§6.5)
- [ ] 3. Anomaly features + personal baselines (§6.6; model training in milestone 6)
- [ ] 4. Lesson recommender (§6.9)
- [ ] 5. Report parser offline path (§6.10) with en/hi/ta keywords
- [ ] 6. Run the engine pipeline over the history ticks → intervals + events; interval invariants (§7.5)
Requirements: F-INS-01, 02, 03, 05, 06, F-LRN-02, 03, F-REP-01 (offline), F-REP-02, P-04.
You will see: tests passing; history intervals file in the brief's column format.

### Milestone 6 — ML training and evaluation (Phase 4) · Status: not started
Goal: train the anomaly and time-estimation models and write honest results to `docs/EVAL.md`.
- [ ] 1. `shiftmate ml train`: IsolationForest per (type, tier); LightGBM quantile p10/p50/p90 with manifest
- [ ] 2. Estimation explanations (pred_contrib → reason keys) and live remaining-time blend
- [ ] 3. Fleet patterns (condition multipliers with counts)
- [ ] 4. `shiftmate eval idle|anomaly|estimation` → `docs/EVAL.md` (confusion matrix, per tier, coverage)
- [ ] 5. If a target is missed: one investigation, fix genuine bugs only, report honestly, log in DECISIONS.md
Requirements: F-SHIFT-02, 03, F-INS-05, F-FLT-04, 05, PRD §10 metrics.
You will see: `docs/EVAL.md` with real numbers.

### Milestone 7 — Edge Gateway A: runtime, REST, scenario player (Phase 5, first half) · Status: not started
Goal: the machine-side server runs live simulated machines and plays Ravi's shift.
- [ ] 1. `MachineRuntime` wiring all engines; live world clock (1×–60×)
- [ ] 2. Scenario player with seek; `ravi_shift.yaml` and `fleet_tour.yaml`
- [ ] 3. SQLite local store; all REST endpoints (TRD §9.1) incl. demo control
- [ ] 4. API tests for every endpoint
Requirements: F-START-01, 02, 03, F-SHIFT-01, 04, 05, 06, F-FLT-03.
You will see: interactive API docs at http://localhost:8100/docs; scenario control by HTTP.

### Milestone 8 — Edge Gateway B: live channels, sync, headless demo (Phase 5, second half) · Status: not started
Goal: live WebSocket feeds, offline outbox with sync, camera proximity input, and a verified headless run of Ravi's shift.
- [ ] 1. `/ws/cab/{id}` and `/ws/site/{id}` with all message types
- [ ] 2. Outbox + background sync with back-off; network toggle
- [ ] 3. Estimation model download from fleet with cached fallback
- [ ] 4. `/proximity/camera` merge (camera overrides sensor when fresher than 1 s)
- [ ] 5. Headless `ravi_shift` at 60× asserting every beat; determinism (two identical event logs)
Requirements: F-REP-04, F-CAB-04, F-SAFE-03 (backend), F-FLT-03.
You will see: a test printing the beat-by-beat event sequence.

### Milestone 9 — Fleet Service (Phase 6) · Status: not started
Goal: the cloud side — ingest, supervisor aggregates with privacy, fleet patterns, model registry and the 10,000-machine scale run.
- [ ] 1. FastAPI on DuckDB; idempotent ingest
- [ ] 2. Site summary, idle causes + suggestions, safety, privacy-respecting trends
- [ ] 3. Fleet overview, patterns, model registry, `/ws/fleet`
- [ ] 4. `shiftmate sim scale` and `shiftmate bench runtime` → `/scale/stats` + EVAL.md scale section (projection labelled)
- [ ] 5. API tests, privacy tests
Requirements: F-SUP-02, 03, 04, 05, F-FLT-05, 07, 08, P-01…P-06.
You will see: http://localhost:8200/docs; a 10,000-machine run with ingest rate and 1.6 M projection.

### Milestone 10 — Design system in code (Phase 7) · Status: not started
Goal: all DESIGN.md components built once in `packages/ui`, visible in a kitchen-sink page.
- [ ] 1. Tokens wired into Tailwind v4; Day / Sunlight / Night themes; Anek fonts self-hosted
- [ ] 2. Glyph set (machine state, idle reasons, proximity, belt, sync, sensor, priority shapes, conditions) as SVG components
- [ ] 3. Components: Reach, StatusRail, alerts P1–P4 + queue, TaskRow, RangeBar, ReasonChip, TimeSplit, sparkline, PushToTalk, LargeToggle, SegmentedControl, PIN pad, LessonCard, DrillFrame, map legend, system states, etc.
- [ ] 4. `/_kitchen-sink` in the console: every component × 3 themes × 3 languages
- [ ] 5. Contrast test; lint rule/test banning hex and font literals outside `packages/ui`
Requirements: F-CAB-02, F-CAB-05 (rendering), PRD §10 experience.
You will see: http://localhost:5174/_kitchen-sink with theme and language switches.

### Milestone 11 — Cab app A: frame, alerts, sign-in, My Shift, Safety (Phase 8, first half) · Status: not started
Goal: the operator tablet app connected live to the edge, with Working/Paused modes and correct alert behaviour.
- [ ] 1. App shell: status rail, bottom nav, push-to-talk placeholder, mode transition, WS client with reconnect and stale state
- [ ] 2. Alert layer exactly per `alert_policy.yaml` (vitest)
- [ ] 3. `/start` (PIN, language, checklist), `/` My Shift, `/safety`
- [ ] 4. i18n for every string (en/hi/ta)
Requirements: F-START-01…04, F-SHIFT-01…06, F-SAFE-01, 02, 04…09 (UI), F-CAB-01, 02, 03, 05.
You will see: the cab at http://localhost:5173 following the live scenario.

### Milestone 12 — Cab app B: Report, My Day, offline PWA (Phase 8, second half) · Status: not started
Goal: reporting, private insights and full offline behaviour.
- [ ] 1. `/report` (typed/tap flow now; voice in milestone 15), recent reports
- [ ] 2. `/insights` My Day + week view
- [ ] 3. PWA pre-caching, Dexie storage, sync-state display
- [ ] 4. Manual checks at 1280×800 and 1024×768; offline check
Requirements: F-REP-02…05, F-INS-06, 07, 08, F-CAB-04, P-01.
You will see: My Day screen; the app still working with the network toggled off.

### Milestone 13 — Console app (Phase 9) · Status: not started
Goal: supervisor console — live site map, day summary, fleet view, demo control and evaluation page.
- [ ] 1. `/site/:siteId` SVG live map ≥ 30 fps
- [ ] 2. `/supervisor/:siteId`, `/fleet`, `/demo` (load, play, pause, speed, seek, network, captions), `/eval`
Requirements: F-SUP-01…05, F-FLT-07, 08.
You will see: http://localhost:5174 driving the demo side by side with the cab.

### Milestone 14 — Assistant "Ask Cat" (Phase 10) · Status: not started
Goal: a multilingual assistant answering only from the team-written knowledge base, online and offline.
- [ ] 1. ~15 knowledge files (en; hi/ta for key safety files) with sample-content banner
- [ ] 2. Index: chunking, BM25 + multilingual embeddings; `shiftmate assistant index`
- [ ] 3. Online answering with validation; offline answering; intents; report parser online path
- [ ] 4. `/ask` screen; eval set (40 questions) and `shiftmate eval assistant`
Requirements: F-ASK-01…06, F-REP-01 (online).
Downloads (ask first): `google-genai` SDK, sentence-transformers model (~470 MB). LLM: Gemini via `assistant/llm.py` with offline fallback on missing key / 429 / timeout; eval paces calls and caches responses (D-021).

### Milestone 15 — Voice and camera (Phase 11) · Status: not started
Goal: push-to-talk in three languages, spoken alerts, and live webcam proximity.
- [ ] 1. Push-to-talk + transcript sheet (en-IN / hi-IN / ta-IN); voice intents; voice report flow (no "call supervisor" intent, D-009)
- [ ] 2. Spoken P1/P2 alerts with tones
- [ ] 3. Camera proximity panel: MediaPipe person detection, calibration, smoothing, posting
- [ ] 4. `worker_near` beat uses the camera when active; camera protocol results in EVAL.md
Requirements: F-SAFE-03, 09, F-ASK-01, 04, F-REP-01, F-START-04 (voice).
Downloads: MediaPipe `efficientdet_lite0` model (~7 MB, vendored). You will need: a webcam and a helper to walk towards it.

### Milestone 16 — Training hub (Phase 12) · Status: not started
Goal: lessons, hazard drill, recommendations during pauses, instructor booking and progress.
- [ ] 1. Lesson player (narrated cards + quiz), 12 lessons with illustrations
- [ ] 2. Hazard drill canvas (5 hazards, tap or voice "stop", reaction time)
- [ ] 3. Pause-only lesson offers; instructor booking; progress view
Requirements: F-LRN-01…06.

### Milestone 17 — Demo polish and end-to-end (Phase 13) · Status: not started
Goal: a reliable, repeatable demo anyone can start from the README.
- [ ] 1. Playwright e2e of `ravi_shift` at 30×; passes twice in a row
- [ ] 2. `fleet_tour` in the console; captions toggle; reset-demo button
- [ ] 3. README setup/run/demo; screenshots; architecture SVG
- [ ] 4. Clean-clone test: `pnpm setup:data` + `pnpm dev:all`
Requirements: PRD §9 demo story (all beats).

### Milestone 18 — Final evaluation and review (Phase 14) · Status: not started
Goal: prove everything is done and traceable.
- [ ] 1. `shiftmate eval all`; review EVAL.md
- [ ] 2. Full tests + lint
- [ ] 3. `docs/TRACEABILITY.md`: every F-… ID → files → tests → demo beat
- [ ] 4. CLAUDE.md §8 demo readiness checklist
Requirements: all Must requirements traced.

---

## C. Open questions for the user
None open. All planning questions were answered on 2026-09-23 and logged as D-005…D-024.

## D. Standing notes
- Translations: every hi/ta string is listed in `docs/TRANSLATIONS_REVIEW.md` (`pnpm i18n:review`). The user reviews Hindi; a native speaker checks Tamil.
- Removed from scope (D-009): Send a truck, Voice note to Ravi, camera clip on reports, call supervisor by voice, switch-to-night-shift demo button.
