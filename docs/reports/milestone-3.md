# Milestone 3 — Simulator and history data

## What was built
A deterministic simulated world that stands in for real machines and sites. Four sites (Chennai, Pune, Pilbara, Tromsø) have their own weather (daily heat cycle, rain, humidity, heat index, ground getting wet, muddy or frozen, dust and fog, day and night), haul trucks sent by a dispatcher (with delays and shortages), workers walking around, and 60 machines driven by 80 operators with hidden personalities. Every 30 seconds each machine reports what its sensors would see, limited by its sensor tier. Separately, the simulator writes down what really happened (true idle reasons and anomalies), which only the evaluation may read.

`shiftmate sim generate --days 42 --seed 7` produces 42 days of history in about a minute:
3,185,280 ticks, 8,240 tasks (7,068 completed), 47,667 dispatch log entries. See `docs/reports/history-summary.md` (copy of `data/history/SUMMARY.md`).

Main files: `backend/src/shiftmate/sim/` (`weather.py`, `fleet.py`, `trucks.py`, `workers.py`, `tasks.py`, `machine.py`, `site.py`, `history.py`, `params.py`), `backend/src/shiftmate/util/` (`heat_index.py`, `solar.py`, `ids.py`, `clock.py`), `config/simulator.yaml`, `backend/tests/test_sim.py`.

## How to test (PowerShell, repo folder)
```
uv run --directory backend shiftmate sim generate --days 42 --seed 7
```
Expected: `Generated 3,185,280 ticks, 8240 tasks (7068 done) for 60 machines over 42 days in ~60 s`. Then open `data\history\SUMMARY.md`: row counts, fleet per site, EXC001 (Cat 320, 2023, advanced, 1520.0 h), WHL014 (Cat 950 GC, 2013, basic, Pilbara), OP1001 Ravi Kumar (ta, 9 years), true idle reasons, anomaly shares, per-site conditions (Tromsø frozen and dark), task durations.

Run it twice: the numbers are identical (deterministic).

```
uv run --directory backend pytest tests/test_sim.py -v
```
Expected: 13 passed.

## Tests run
Backend 37/37 (13 new simulator tests: fleet facts, tier rule, trait share, tick invariants for engine hours / fuel within 2 % / tier nulls / load counter / truth only on idle ticks, a hypothesis property test over random seeds, determinism of the world and of the generator's file hashes, heat index values used by the demo, polar night, frozen Tromsø). Frontend 13/13, contracts OK, lint clean.

Interval-level invariants (`idling ≤ engine_on ≤ interval`, `safety_alert_triggered` iff P1/P2) need the engines and are added in milestone 5 (D-015).

## Decisions
D-034 task duration excludes breaks · D-035 load cycle counter signal (added to the basic tier) · D-036 ground truth per tick · D-037 simulator scope · D-038 climate tuning.

## Downloads
None.

## Known issues
- No night shifts: the `is_night` estimation feature only varies at Tromsø.
- Live mode (1 s ticks, scenario overrides) uses the same world but is wired up in milestone 7.
