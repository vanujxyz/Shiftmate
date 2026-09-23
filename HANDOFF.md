# HANDOFF — pick up here (for the next Claude Code session)

Last updated: 2026-09-23. Written by the previous Claude Code session when the owner ran out of usage.

## Read first
1. `CLAUDE.md` (process rules, golden rules). The repo uses **milestones** (see `docs/PROGRESS.md`), not the "phases" named in CLAUDE.md; PROGRESS.md maps each milestone to its phase.
2. `docs/PROGRESS.md` — milestone list with checkboxes and status.
3. `docs/DECISIONS.md` — D-001…D-055. Log new decisions in the same format (next number: **D-056**).
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
- Milestones 1–7: **done and committed** (the last is `milestone 7: edge gateway runtime, REST API, live site and scenario player`).
- Milestone 8 (Edge Gateway B): **in progress**. Committed as a WIP commit, **not yet a milestone commit**.

### Milestone 8: already written (WIP commit)
- `config/edge.yaml` and `EdgeConfig` in `schema/config.py`, loaded in `config_loader.py`. The camera constants moved here from `runtime.py`.
- `edge/channels.py` — `Hub` (subscribers and a seq number per channel) and `Feeds.pump(wall)`. The pump turns runtime, site and player queues into TRD §9 envelopes:
  - Telemetry is throttled to `telemetry_hz`, and provisional idle segments are coalesced.
  - Site entities go out at 5 Hz, plus dispatch and `site_event` messages.
  - A `snapshot` is sent on connect, and on load or seek.
  - `estimate_update` is sent on task progress, or every `estimate_update_sim_s`.
- `edge/sync.py` — `SyncWorker`:
  - The outbox goes to `/ingest/{intervals,events,reports,tasks}`, with the kinds filtered by `privacy.yaml → fleet_upload`.
  - Retries use exponential back-off (5 s up to 60 s), on wall clock.
  - `check_model()` downloads a newer estimation model from `/models/estimation/latest` and `/models/estimation/{v}/files/{name}` into `data/edge/models`, then hot-swaps it (`EdgeResources.use_estimation_from`). At start it loads the cache first, then the bundled `models/`.
- `edge/app.py`:
  - `EdgeContext.feeds` and `.sync`; the clock pumps the feeds, and a sync task runs.
  - `WS /ws/cab/{machine_id}` and `WS /ws/site/{site_id}` (`_serve_socket`).
  - `/sync/status` now also shows the estimation model version and its source.
  - `/demo/captions` now takes `{on: bool}` (the new `CaptionsRequest`).
  - `create_app(..., cache_dir, fleet_url, fleet_transport)` — pass an `httpx.MockTransport` in tests as a fake fleet.
- `edge/runtime.py`:
  - `site_messages` queue; shared events are forwarded as `site_event`.
  - Live truck-shortage notice (`_truck_shortage_notice`).
  - A closed WAITING_FOR_TRUCK segment records an **anonymous** `site_issue` event (operator_id None, shared; PRD P-04, F-INS-03).
- `edge/live.py`:
  - `dispatch` site messages.
  - `_watch_tasks()` pushes `task_progress` and queues task summaries (`store.add_task_summary`).
  - `player.events` is now a deque with `drain_events()`.
  - Camera fallback for the `worker_near` beat (TRD §8: wait up to `camera.wait_s`, then script the person).
- `schema/enums.py`: new `EventType.SITE_ISSUE` and `EventType.EQUIPMENT_PROBLEM`. Checklist equipment reports used to be mislogged as `incident`; `_save_report` now uses `EventType(draft.type.value)`.
- `schema/api.py`: WebSocket models (`WsEnvelope`, `TaskProgress`, `EstimateUpdate`, `Connectivity`, `SyncUpdate`, `SiteEntities`, `CabMessageType`, `SiteMessageType`), and `Telemetry` extended to match the runtime payload.
- **Fixed M7 gap:** the `schema/api.py` models were never in the contracts export. `schema/__init__.py` now appends every model in `schema/api.py` to `EXPORTED_MODELS`, and the contracts are regenerated.
- The 14 edge API tests pass and ruff is clean. **The full backend suite and `pnpm test:all` have NOT been re-run since these changes. Run them first.**

### Milestone 8: still to do
1. **`edge/headless.py`** — a headless runner, plus a CLI `shiftmate edge headless --scenario ravi_shift --speed 60` that prints beat by beat.
   - Build the app with `create_app(autorun=False, fleet_transport=<MockTransport accepting everything>)`.
   - Drive it with a fake wall clock: `player.playing=True; player.speed=60`; loop `wall += 0.1; player.tick_wall(0.1, wall); feeds.pump(wall); await sync.tick(wall)`.
   - Subscribe to both channels with `hub.subscribe(...)` to record messages.
   - Do operator actions through the real REST API with `httpx.AsyncClient(transport=httpx.ASGITransport(app))`:
     - sign in when `player.waiting_for == "sign_in"`;
     - at `near_miss`, POST `/reports/parse`, then `/reports`, with a near-miss transcript.
2. **`tests/test_headless.py`** — assert the CLAUDE.md Phase 5 DoD beat outcomes:
   - WARM_UP idle segment after `cold_start`;
   - WAITING_FOR_TRUCK segment plus the anonymous `site_issue` shared event and the site `site_event`;
   - P1 `SEATBELT_*` alert;
   - proximity alerts escalating caution → danger → critical;
   - a `risk_band_change` to amber around 11:00;
   - UNATTENDED_RUNNING segment at `step_out`;
   - offline at 13:00: the outbox grows (check that intervals or reports really land in 13:00–13:08; if not, file a report while offline in the driver);
   - online at 13:08: the outbox drains to 0.

   **Determinism:** two runs give identical store event logs (`store.list_events()`: event_id, ts, type, code, payload).
3. Tests:
   - WebSocket tests with `TestClient.websocket_connect`: snapshot first; seq numbers increase; unknown machine or site closes with 4404; telemetry arrives after advancing.
   - Sync tests: back-off, the privacy kind filter, drain to 0, and the offline outbox growing.
   - A model-download test: fake fleet serves a model; the version swaps. A failure keeps the cached model.
   - A camera override test: fresh reading wins over the sensor; after 1 s the sensor is back.
4. Log decisions:
   - **D-056:** the `/ingest/reports` and `/ingest/tasks` endpoints (TRD §9.2 lists only intervals and events), the extra cab/site message types (`snapshot`, `demo`, `session`, `alert_queued`, `alert_feed`) and the telemetry throttle.
   - **D-057:** the site_issue event, anonymous and attributed to the site.
   - **D-058:** equipment_problem gets its own event type.
   - **D-059:** the api models are now exported to contracts (the M7 miss).
5. `pnpm contracts:gen`, full tests and lint, `docs/reports/milestone-8.md`, `python scripts/progress_mark.py 8 "Milestone 9 (Fleet Service) in progress."`, then commit `milestone 8: …`.

### Then milestones 9–18
Follow `docs/PROGRESS.md`. Milestone 9 (Fleet Service) must implement the ingest endpoints the edge already calls: `/ingest/intervals`, `/ingest/events`, `/ingest/reports`, `/ingest/tasks`, with body `{source, records: [...]}` and idempotence by record id (interval `record_id`, event `event_id`, report `report_id`, task `task_id`). It must also serve `/models/estimation/latest` → `{version, files: [...]}` and `/models/estimation/{version}/files/{name}`.

## Known open items (reported, awaiting the owner)
D-051 lists evaluation targets still missed: anomaly precision 67 % and recall 42 % (target 80 %), and estimation p10–p90 coverage 64.5 % (target 75–85 %). The fix options each change TRD-specified behaviour and need the owner's decision. Don't tune on test data.
