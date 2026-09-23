# Milestone 4 — Engines A: safety core

## What was built
The safety brain that will run on every machine:
- **Rule evaluator** — runs the YAML safety rules by walking a checked syntax tree; attribute access, function calls, imports and unknown names are rejected when rules load. Never uses Python `eval`.
- **Machine state** — engine off / idle / working / travelling; Working vs Paused mode for the cab (paused after 30 s idle, back to Working on any movement); continuous operation that only resets after a real 10-minute rest (waiting for a truck does not count).
- **Risk level** — green / amber / red from heat, rain, ground, darkness, visibility, fatigue, people nearby, seatbelt and recent near-misses; goes up at once, comes down only after 2 minutes below the band; wider warning distances and shorter fatigue limits at amber/red and in heat.
- **Safety rules** — sustain timers, cooldowns, rules switched off when the machine lacks the sensor (a camera can switch proximity on), edge-triggered risk-band alerts.
- **Alert policy** — one interrupting alert at a time, P1 over P2, proximity never pushed aside by a same-priority alert, P3/P4 wait for a pause, dedupe, acknowledgement with reaction time, reduced P1 while still true, escalation after 20 s shared with the supervisor, stale queue entries become history.
- **Ground-truth guard** — a test that parses all code outside the simulator and evaluation and fails if anything touches labels, personalities, truth files or the simulator config.

Main files: `backend/src/shiftmate/engines/` (`rule_eval.py`, `machine_state.py`, `risk.py`, `safety.py`, `alerts.py`); tests `test_rule_eval.py`, `test_machine_state.py`, `test_risk.py`, `test_safety.py`, `test_alerts.py`, `test_ground_truth_guard.py`.

## How to test (PowerShell, repo folder)
```
uv run --directory backend pytest tests/test_rule_eval.py tests/test_machine_state.py tests/test_risk.py tests/test_safety.py tests/test_alerts.py tests/test_ground_truth_guard.py -v
```
Expected: 74 passed. Highlights to look for: `test_rejects_unsafe_or_invalid[__import__('os')...]`, `test_demo_heat_beat_is_amber` (heat 45 + 4 h without break + wet = 53, amber), `test_band_goes_up_at_once_and_down_after_hysteresis`, `test_proximity_tiers_escalate_along_the_demo_path`, `test_p1_ack_then_reduced_while_still_true_then_cleared`, `test_never_more_than_one_interrupting_alert` (property test over random alert sequences).

```
pnpm test:all      # backend 111 passed, frontend 13 passed, contracts up to date
pnpm lint:all
```

## Tests run
Backend 111/111 (74 new), frontend 13/13, contracts OK, lint clean.

## Decisions
D-039 rule evaluation semantics · D-040 what counts as rest · D-041 proximity tier for the risk score · D-042 alert policy details. `risk_model.yaml` gained `rest_reset_min: 10` (the TRD's 10 minutes).

## Downloads
None.

## Known issues
The engines are not yet wired to live ticks; that is the MachineRuntime in milestone 7. Idle reasons, intervals and anomaly features come in milestone 5.
