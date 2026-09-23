# Milestone 8 — Edge Gateway B: live channels, sync, headless demo

## What was built
- **Live WebSocket channels** (`edge/channels.py`, `edge/app.py`):
  - `/ws/cab/{machine_id}` carries everything the cab needs: telemetry, mode, risk, alerts, idle segments, insights, lesson offers, task progress, live estimates, sync and connectivity.
  - `/ws/site/{site_id}` carries the supervisor's map: entities at 5 Hz, the dispatch log and shared site events.
  - Every message uses the TRD §9 envelope `{type, seq, ts, machine_id, site_id, payload}`. A `snapshot` comes first on connect and again after a load or seek.
  - Telemetry is throttled to 1 Hz, whatever the demo speed (D-056).
  - An unknown machine or site closes the socket with code 4404.
- **Outbox sync** (`edge/sync.py`):
  - Intervals, shared events, reports and task summaries go to `/ingest/{intervals,events,reports,tasks}`, but only kinds that `privacy.yaml` allows.
  - After a failure, retries back off on the real clock: 5, 10, 20, 40, then 60 s.
  - The network toggle stops all uploads, so the outbox grows while offline.
- **Estimation model download:**
  - The edge fetches newer models from the fleet into the edge cache and swaps them in while running.
  - At start it uses the cached model first, then the bundled one.
  - `/sync/status` shows the model version and where it came from.
- **Camera proximity:** a camera reading less than 1 s old replaces the machine's own sensor reading. A camera also enables the proximity rules on machines that have no proximity sensor. At the `worker_near` beat, if a camera was active but stops reporting, the person's path is scripted instead (TRD §8).
- **Site issues:** a truck wait appears live on the site map and is recorded as an anonymous shared `site_issue` event (D-057). Equipment problems get their own event type (D-058).
- **Contracts:** the API and WebSocket models are now part of the contracts export (D-059, fixing a milestone 7 gap).
- **Headless runner** (`edge/headless.py`) and the CLI command `shiftmate edge headless [--scenario ravi_shift] [--speed 60]`:
  - It plays the whole Edge Gateway on a fake clock against a fake fleet.
  - It drives Ravi through the real REST API: sign-in, the spoken near-miss report, and an equipment report while offline (D-060).
  - It prints what happened, beat by beat.

### Bugs found and fixed while testing
- **Report uploads were missing their id.** Uploaded reports had no `report_id`, `operator_id` or `machine_id`, so the fleet could not ingest them idempotently. They now carry all three (`edge/store.py`).
- **A broken model download could stop the edge starting.** The downloader wrote the cache's `LATEST` pointer before loading the new model, and the start-up loader only caught missing files. `LATEST` is now written only after the model loads, and any cache error at start-up falls back to the next source (D-061).

## Headless run of Ravi's shift (60×, trained models)
Output of `uv run --directory backend shiftmate edge headless`. It took about 87 s of real time and 4,223 clock steps.
```
07:00:00  ▶ sign_in      · lesson_offered P4 L-SPOTTER-SIGNALS
07:02:00  ▶ cold_start   · idle_segment WARM_UP (07:02:01–07:06:04)
07:15:00  ▶ my_shift     · short normal truck waits ×6 (1–3 min each), each an anonymous site_issue
08:10:00  ▶ truck_delay  · idle_segment WAITING_FOR_TRUCK 08:08:02–08:28:48 (20.8 min) + site_issue
09:30:00  ▶ worker_near  · alert P3 PROXIMITY_CAUTION → P2 PROXIMITY_DANGER → P1 PROXIMITY_CRITICAL
10:20:00  ▶ seatbelt     · alert P1 SEATBELT_MOVING (10:20:01)
10:30:00  ▶ skip_break   · alert P2 HEAT_NO_BREAK, P2 FATIGUE_LIMIT; risk_band_change amber at 10:45 (top: heat)
11:40:00  ▶ step_out     · alert P2 UNATTENDED_RUNNING; idle_segment UNATTENDED_RUNNING 11:40–11:46
12:10:00  ▶ near_miss    · near_miss (shared with the supervisor)
13:00:00  ▶ offline      · connectivity offline; equipment_problem report; outbox 0 → 2
13:08:00  ▶ online       · connectivity online; outbox 2 → 0
14:00:00  ▶ end_shift
fleet received: {'intervals': 31, 'events': 21, 'tasks': 2, 'reports': 2}; final outbox: 0
```

## How to test (PowerShell or Git Bash, repo folder)
```
uv run --directory backend shiftmate edge headless
uv run --directory backend pytest tests/test_headless.py tests/test_edge_live.py -v
pnpm test:all
pnpm lint:all
```
To watch the live channels, run `uv run --directory backend shiftmate edge`, then connect any WebSocket client to `ws://localhost:8100/ws/cab/EXC001` and `POST /demo/play`.

## Tests run
All 209 backend tests pass (24 new), along with frontend 13/13 and the contracts check. ruff, eslint and tsc are clean.
- `test_headless.py` (12 tests) plays the whole shift twice, on a clean clone with no generated data. It checks each beat's outcome:
  - all 13 beats fire on time;
  - WARM_UP after the cold start;
  - the 18-minute truck delay: a WAITING_FOR_TRUCK segment of at least 15 min, an anonymous shared site issue, the live and closed site events, and the "not you" insight;
  - proximity alerts P3 → P2 → P1 in that order;
  - the P1 seatbelt alert;
  - an amber risk band led by heat;
  - UNATTENDED_RUNNING of at least 5 min;
  - the shared near miss;
  - the outbox grows while offline and drains to 0 afterwards, and every report reaches the fleet;
  - uploads respect privacy;
  - channel order: snapshot first, and `seq` numbers without gaps.

  **Determinism:** two runs produce identical event logs (event id, time, type, code and payload) and identical uploads. The same check was also run by hand with the trained models and generated history: 56 events, identical across two runs.
- `test_edge_live.py` (12 tests):
  - **WebSockets:** snapshot first; ordered `seq` numbers; telemetry arrives after the world advances; unknown machine or site closes with 4404; site entities arrive; the network toggle reaches the cab.
  - **Sync:** the outbox drains; back-off goes 5/10/20/40/60/60 s and recovers; offline, the outbox grows and nothing is sent; the privacy filter keeps intervals on the machine when they are not allowed.
  - **Model download:** the version swaps; an unreadable model, a missing file or a fleet that is down keeps the current model; the next start uses the cache; a cache pointing at a broken model does not stop the edge.
  - **Camera:** a fresh reading overrides the sensor; after 1.6 s the sensor is back; readings during fast-forward are ignored; the REST endpoint feeds the runtime.

## Decisions
- D-056: the edge ingest endpoints, the extra channel message types, and the telemetry throttle.
- D-057: a truck wait is a site issue, anonymous and attributed to the site.
- D-058: equipment problems get their own event type.
- D-059: API models are exported to the frontend contracts.
- D-060: the headless run reports an equipment problem while offline.
- D-061: a downloaded model becomes LATEST only after it loads; report uploads carry their ids.

## Observations (not changed; for the owner)
- **The heat beat's colour change comes early.** The risk band turns amber at 10:45, when the weather script raises the heat index to 43 °C (D-005). At the 11:00 "heat" beat (45 °C) the band is already amber, so nothing new happens at 11:00. PRD §9 says the heat break suggestion appears at 11:08, which milestone 7 confirmed by hand.
- **Events before sign-in are attributed to Ravi.** The world runs silently from the start of the day to the scenario start (06:58). During that time the runtime records a few events, for example an amber risk band at 06:43, under the operator the plan assigns (OP1001), before anyone has signed in. These are not shown in the demo. Making them anonymous would be the cleaner option; this is noted for milestone 11 (cab app).
- **Rebuilt data differs slightly on another machine.** On a second PC, `sim generate --days 42 --seed 7` produced 7,040 completed tasks against the committed 7,039, so the evaluation numbers moved by up to about 1 point (anomaly precision 68.2 % against 67.2 %). On one machine the output is deterministic (see the headless test). The cause of the difference between machines has not been investigated yet. The committed `EVAL.md` was kept.

## Not in this milestone (milestone 9)
The Fleet Service that receives these uploads: `/ingest/intervals|events|reports|tasks` taking `{source, records}`, idempotent by record id, plus `/models/estimation/latest` and `/models/estimation/{version}/files/{name}`.

## Downloads
None.
