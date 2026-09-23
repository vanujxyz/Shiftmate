# Milestone 7 — Edge Gateway A: runtime, REST, scenario player

## What was built
- **Machine runtime** (`edge/runtime.py`). The focus machine's live pipeline runs the same `MachinePipeline` as the history replay: state, safety, risk, alerts, idle reasons, intervals, anomaly, lessons and estimation. It also merges camera proximity readings and records every event in the local store.
- **Live site** (`edge/live.py`). The scenario's site runs at 1 s ticks, at adjustable speed (1× to 120×; the demo uses up to 60×). Background machines move in the world only: on the map, with trucks and workers (D-052).
- **Scenario player.** It fires beats at their times and supports play, pause, speed and seek. Seek restores a snapshot, or fast-forwards deterministically.
- **Scenarios.** `scenarios/ravi_shift.yaml` covers Ravi's day: tasks, weather script, and beats including the skipped 10:30 break. `scenarios/fleet_tour.yaml` covers the basic-tier loader WHL014 at PIL-MIN-01.
- **Local store** (`edge/store.py`, SQLite): events, reports, lesson completions, drill results, bookings and the outbox table.
- **Every REST endpoint in TRD §9.1** (`edge/app.py`, 33 routes), with request and response models in `schema/api.py`:
  - health and machines;
  - sign in and out: badge, or PIN fallback (D-055);
  - profile, shift with estimates, and task estimate;
  - checklist: a failed item becomes an equipment report;
  - alert acknowledgement;
  - reports: parse, save, list;
  - private insights (My Day);
  - lessons: list, recommended, detail, complete;
  - drills, training slots and bookings;
  - assistant ask and intent: offline stub until milestone 14;
  - camera proximity and sync status;
  - demo control: load, play, pause, speed, seek, network, captions.
- **Services** (`edge/services.py`): shift building, operator profile, My Day insights, and training slots.
- **Keyword intents** (`engines/intents.py`): the offline path for voice commands in en, hi and ta.
- **29 new or changed strings** in all three languages (`scripts/i18n/m07_edge.yaml`, merged with `scripts/i18n_merge.py`).

## Checked by hand (trained models, Ravi's shift)
These were checked with the models from milestone 6:
- The shift shows each task as a time range with reasons, for example "Wet ground adds time: +15 min".
- The heat break suggestion appears at 11:08.
- My Day shows the time split, fuel per load against Ravi's usual, and coaching points.

## How to test (PowerShell, repo folder)
```
uv run --directory backend shiftmate edge
```
Open http://localhost:8100/docs, then:
1. `POST /demo/scenario/load` with `{"name": "ravi_shift"}`, then `POST /demo/play`.
2. `GET /demo/state` shows the clock and the next beat. `POST /demo/speed` takes `{"x": 30}` (above 0, up to 120), and `POST /demo/seek` takes `{"beat_id": "…"}` from the beat list.
3. `POST /session/sign-in` with `{"operator_id": "OP1001", "machine_id": "EXC001", "pin": "1001", "language": "en"}`, then `GET /operators/OP1001/shift`.

```
uv run --directory backend pytest tests/test_edge_api.py -v
pnpm test:all
pnpm lint:all
```

## Tests run
All 185 backend tests pass (14 new edge API tests), along with frontend 13/13 and the contracts check; ruff, eslint and tsc are clean.
- The task-estimate endpoint is tested for its error paths (unknown task, no model). The model path was checked by hand, because tests run without trained models.
- The ML test now expects the new reason key `reason.ground_muddy_slower` instead of `reason.wet_ground_slower`. What it checks is the same: a ground reason that adds time. See D-054.

## Decisions
- D-052: background machines run in the world only.
- D-053: a lesson about the current pause is offered first.
- D-054: estimate reasons are what-if effects on conditions an operator recognises. The model and its evaluation numbers are unchanged.
- D-055: the demo PIN is the operator number (not security).

The live edge code no longer reads simulator settings. Task noise is now drawn by `SiteWorld.task_noise`, which the ground-truth guard test enforces.

## Not in this milestone (milestone 8)
The WebSocket feeds, outbox sync with back-off, estimation model download from fleet, and the headless beat-by-beat run of `ravi_shift` with its determinism check.

## Downloads
None.
