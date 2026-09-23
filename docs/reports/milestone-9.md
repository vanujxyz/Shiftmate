# Milestone 9 — Fleet Service

## What was built
- **Fleet store** (`fleet/store.py`, DuckDB at `data/fleet/fleet.duckdb`):
  - It holds intervals, shared events, reports, task summaries, the roster, and an ingest log.
  - Every table has a primary key, and ingest uses `INSERT OR IGNORE`, so a re-sent batch changes nothing.
  - Tasks are upserted forward only: scheduled → active → done.
  - Events that are neither shared nor an incident or near miss are rejected at the door (P-03, P-05).
  - A new store is seeded with what the edges would have uploaded during the simulated history (D-062).
- **Ingest** `POST /ingest/{intervals|events|reports|tasks}` takes `{source, records}`, at most 500 records per request (413 if more). It returns counts of received, inserted, updated, duplicate and rejected records. Records are validated, and timestamps without a time zone are rejected. There is no endpoint for raw ticks.
- **Supervisor views** (`fleet/aggregates.py`: pure functions, per site and local day; the date defaults to the latest day with data):
  - `GET /sites/{id}/summary`: every machine on the site roster with its tasks, progress and on-track, behind or done status (D-063).
  - `GET /sites/{id}/idle-causes`: idle minutes by reason, the lead lost-time reason, and truck waiting by hour. The suggestions are:
    - add a truck (zone, 2-hour window, and a "would likely save" range with its basis in similar days);
    - a toolbox talk on idling;
    - a shutdown briefing.

    Operators are never named in this view (D-064, P-04).
  - `GET /sites/{id}/safety`: P1 and P2 alerts (P2 also counted by code), incidents, near misses, unattended running, anonymous site issues, reports, and each machine's risk band with its amber and red minutes. Operators are named only for the kinds `privacy.yaml` allows (P-03).
  - `GET /sites/{id}/trends?days=`: daily aggregates and groups by operator experience. Any day or group with fewer than 3 operators is suppressed (P-02). This is configurable per site (P-06).
- **Fleet views:**
  - `GET /sites` and `GET /fleet/overview`: sites across four countries; machines by type and sensor tier; how many machines sent data on the latest day; risk bands; the latest conditions; the time of the last upload.
  - `GET /fleet/patterns`: condition multipliers learned across the fleet, with task and machine counts.
- **Model registry:** `GET /models/estimation/latest` returns the version, file list and manifest, and `…/{version}/files/{name}` serves the files. Names are checked against an allow-list, and a path traversal attempt returns 404. The edge's model download (milestone 8) now has a real server.
- **`/ws/fleet`:** a snapshot first, then ingest counters (at most 2 a second) and new P1 alerts, incidents, near misses and site issues as they arrive (without operator ids).
- **Scale** (TRD §7.6):
  - `shiftmate sim scale [--machines 10000] [--sim-minutes 60] [--speed max|N] [--fleet-url …] [--in-process]` streams synthetic machines through the real ingest endpoints. It resamples real summaries rather than inventing numbers (D-066).
  - `shiftmate bench runtime [--machines 200] [--sim-minutes 30]` runs full machine runtimes on live 1 s ticks.
  - Both save their results to `data/fleet/scale.json`, `/scale/stats` and the EVAL.md scale section. The 1.6 M projection is always labelled as a projection.
- **Edge changes:**
  - A task summary is now also sent when a task starts, so today's active task reaches the supervisor (D-065).
  - The headless runner can upload to a real Fleet Service (`fleet_transport`).
- **Config:** `config/fleet.yaml` holds all thresholds (on-track tolerance, suggestion windows, trend groups, scale settings). It is validated by `FleetConfig`.
- **Contracts:** all Fleet Service models (`schema/fleet.py`) are exported to the frontend contracts.

## Measured (on this laptop; full tables in docs/EVAL.md)
- **Scale run:** 10,000 synthetic machines × 60 simulated minutes gave 44,612 records (40,000 intervals and 4,612 events) in 92 requests.
  - Ingest throughput: 4,082 records/s.
  - Latency per batch (up to 500 records): p50 120 ms, p95 147 ms.
  - Upload per machine: 5.7 kB/h.
  - Wall time: 29.7 s.
- **Runtime benchmark:** 200 full runtimes × 30 minutes = 360,000 runtime steps.
  - CPU per machine per tick: 0.185 ms mean, 0.215 ms p95.
  - Upload per machine: 4.8 kB/h, 3.8 records/h.
  - Memory: 0.04 MB per runtime. This counts Python allocations over the first minute, so it is a lower bound.
- **Projection to 1.6 M machines** (linear, 24 h a day as an upper bound; basis: the runtime benchmark):
  - uplink ≈ 183 GB/day;
  - records ≈ 1,700/s;
  - ingest load ≈ 0.4× the single laptop process measured above.

## Seen end to end (Ravi's shift uploaded into the real Fleet Service)
- **Summary for 2026-09-24:** EXC001 (Ravi) shows truck loading 18/18 done, trenching 60/60 done, and backfilling 107/120 active and on track.
- **Where time is lost:** the lead is waiting for trucks, 37 min (a site issue). The suggestion is "LOAD-A, 07:00–09:00, likely save 36–59 min, based on 9 similar days". There are also a toolbox talk on idling (L-IDLE-FUEL) and a shutdown briefing (L-SHUTDOWN).
- **Safety:** two P1 alerts (PROXIMITY_CRITICAL and SEATBELT_MOVING) name Ravi, and so does the near miss. The truck site issue and the equipment report are anonymous. The risk band was amber for 225 minutes.

## How to test (repo folder)
```
uv run --directory backend shiftmate fleet
```
Then open http://localhost:8200/docs and try `/sites/CHN-HWY-01/idle-causes`, `/sites/CHN-HWY-01/safety?date=2026-09-23`, `/fleet/overview` and `/scale/stats`.
```
uv run --directory backend shiftmate sim scale --machines 10000 --sim-minutes 60
uv run --directory backend shiftmate bench runtime
uv run --directory backend pytest tests/test_fleet.py tests/test_fleet_scale.py -v
pnpm test:all
pnpm lint:all
```
- `sim scale` posts to a running Fleet Service. Add `--in-process` to run it inside the command, but stop `shiftmate fleet` first, because DuckDB lets only one process open the file.
- The fleet database is created and seeded on first start. Delete `data/fleet/` to start over.

## Tests run
All 225 backend tests pass (16 new), along with frontend 13/13 and the contracts check. ruff, eslint and tsc are clean.
- `test_fleet.py` (12 tests):
  - **Ingest:** idempotent for intervals, events and reports; tasks move forward only; invalid records, missing time zones and oversized batches are rejected, and there is no tick endpoint.
  - **Privacy:** private events never enter the fleet; the safety view names operators only where allowed; idle causes never name operators; trends hide groups under 3, and a stricter configured minimum hides more (P-06).
  - **Views and services:** on-track versus behind with exact numbers; the truck suggestion's zone, window, range and basis; sites and overview; the model registry (including path traversal); the `/ws/fleet` snapshot, P1 event and counters.
- `test_fleet_scale.py` (4 tests):
  - a scale run of 40 synthetic machines (idempotent, kept out of real site views);
  - projection maths and labelling;
  - a small runtime benchmark;
  - Ravi's whole shift played headless and uploaded into a real Fleet Service, checked through the summary, safety and idle-cause views.

## Decisions
- D-062: the fleet store is seeded with the history the edges uploaded.
- D-063: on-track and behind mean the fleet's usual pace for that task on that machine type.
- D-064: the lead lost-time reason and the add-a-truck suggestion (how its range is computed).
- D-065: task summaries are sent when a task starts and when it ends.
- D-066: scale mode resamples real summaries; throughput counts time inside requests; the projection uses the runtime footprint.
- D-067: today's site views show only the machines that upload today.

## Observations (for the owner)
- **On a live demo day, only EXC001 has data** (D-052, D-067). The other 23 Chennai machines appear in today's summary as "not started". Earlier days have the whole site from history. The console (milestone 13) could default to the latest *complete* day for the supervisor view, and show today for the live map and Ravi's machine.
- **End-of-day summaries show most unfinished tasks as "behind".** Tasks still open at the end of the shift are mostly the slow ones. This is the rule working as defined (D-063), not a bug, but it reads harshly for a past day.
- **The suggestion wording needs translating.** The keys are `suggest.add_truck`, `suggest.toolbox_idle` and `suggest.shutdown_briefing`. They need text in all three languages, which will be added with the console in milestone 13.
- **Test time has grown.** The backend suite now takes about 3 minutes, because the headless shift runs three times: twice for the determinism test and once for the fleet end-to-end test.

## Not in this milestone (milestone 10)
The design system in code: tokens, themes, fonts, glyphs, components and the kitchen-sink page.

## Downloads
None.
