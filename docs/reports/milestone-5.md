# Milestone 5 — Engines B: insight core and history pipeline

## What was built
- **Idle reasons.** Every idle stretch of a minute or more is labelled Warm-up, Break, Waiting for truck, Engine on with cab empty, Short stops (habit) or Not sure. Each label comes with a confidence and the evidence used. It works on all three sensor tiers; basic machines use time and the site's dispatch log, with lower confidence.
- **Interval records.** Every quarter hour and at each task change, the engines write a row in the brief's exact format (Engine Hours, Fuel Used, Load Cycles, Idling Time, Seatbelt Status, Safety Alert Triggered) plus about 40 extra columns.
- **Unusual-behaviour features.** Ten features per interval are compared with personal baselines: my own normal over the last 14 days, or my machine type on this site when I have too little history. The comparison uses robust z-scores and gives plain-language explanations ("Fuel per truck was …, your usual is …").
- **Lesson recommender.** It picks up to 3 lessons from the last week's events and offers one only at the start of a long pause.
- **Offline Quick Report parser.** English, Hindi and Tamil keywords turn a spoken sentence into type, severity, people involved and injury. Time, machine, zone, task and weather are filled in automatically.
- **Engine pipeline and history replay.** The same per-machine pipeline the edge will run live now replays the whole 42-day history. It produced 98,309 intervals, 87,964 events and 34,697 classified idle segments in about 3 minutes.

Main files: `backend/src/shiftmate/engines/` (`idle_reason.py`, `intervals.py`, `anomaly.py`, `lessons.py`, `reports.py`, `dispatch_view.py`, `pipeline.py`), `backend/src/shiftmate/edge/replay.py`, `backend/src/shiftmate/util/geo.py` and `backend/src/shiftmate/assistant/keywords/reports.yaml`. Tests: `test_idle_reason.py`, `test_insight_engines.py`, `test_history_replay.py`.

## How to test (PowerShell, repo folder)
```
uv run --directory backend shiftmate sim generate --days 42 --seed 7
```
Expected output is two lines:
- `Generated 3,185,280 ticks …`
- `Replayed through the engines: ~98,000 intervals, ~88,000 events, ~34,700 idle segments in ~200 s`

Open `data\history\SUMMARY.md` and scroll to "Engine replay" for the predicted idle reasons and alert counts.

To see intervals in the brief's format:
```
uv run --directory backend python -c "import pandas as pd; df = pd.read_parquet('../data/history/intervals.parquet'); print(df[df.machine_id=='EXC001'].iloc[:8, :9].to_string())"
```

Run the tests:
```
uv run --directory backend pytest tests/test_idle_reason.py tests/test_insight_engines.py tests/test_history_replay.py -v
pnpm test:all
```
Expected: the three files pass, and the full suite shows 164 backend and 13 frontend tests passing.

## Tests run
All 164 backend tests pass. The new ones cover:
- one test per idle reason on each sensor tier
- intervals closing at the quarter hour with the brief's columns
- features that basic machines lack are dropped, not faked
- personal vs group baselines, and the explanations
- recommender ordering, and offers only during pauses
- the offline parser in English, Hindi and Tamil
- filling in the zone automatically from the machine's position
- the replay checked against the raw ticks: idling ≤ engine on ≤ interval length; engine hours and fuel match the ticks; seatbelt status at the end matches; Safety Alert Triggered is Yes exactly when a P1 or P2 was raised; two runs are identical

Frontend 13/13, contracts check OK, lint clean.

## Decisions
D-043 to D-049:
- one shared engine pipeline for history and live
- interval-building details
- idle-classification details
- anomaly direction and baseline window
- how the recommender scores and offers lessons
- the offline report parser
- simulator realism fixes: ground crew keep clear of machines, and operators slow down earlier

## Downloads
None.

## Known issues
- The IsolationForest part of the anomaly decision, and the estimation models, are trained in milestone 6.
- True "waiting for truck" periods shorter than a minute are not classified, because the TRD sets a 60-second minimum. The evaluation in milestone 6 will report this honestly.
