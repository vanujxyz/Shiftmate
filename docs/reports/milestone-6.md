# Milestone 6 — ML training and evaluation

## What was built
- **Task time estimation.** Three LightGBM models give each task a range (p10–p90) and a most-likely time. Each estimate comes with its top reasons in minutes, for example "Wet ground adds time: +18 min". A live remaining-time estimate blends the model with the progress actually made.
- **Unusual-behaviour models.** One IsolationForest per machine type and sensor tier works on robust z-scores against each operator's own normal. The latest baselines are exported for the edge.
- **Fleet-learned patterns.** These are condition effects learned across all machines, such as "muddy ground adds about 30 % to backfilling (36 machines)". They are computed from days 1–35 only, and each needs at least 3 machines.
- **Evaluation.** `shiftmate eval all` writes `docs/EVAL.md` with real numbers, tables, a confusion matrix, results per sensor tier, and a naive baseline for comparison.

Main files: `backend/src/shiftmate/fleet/training.py`, `fleet/patterns.py`, `engines/estimation.py`, the vectorised baselines in `engines/anomaly.py`, and `eval/` (`report.py`, `truth.py`, `idle.py`, `anomaly.py`, `estimation.py`). Tests: `tests/test_ml.py`, plus 2 new regression tests in `test_sim.py`.

## Results (test days 36–42, never used for training or tuning)

| What | Result | Target | Verdict |
|---|---|---|---|
| Idle reasons, advanced machines | 96.1 % | ≥ 90 % | met |
| Idle reasons, standard machines | 91.8 % | – | – |
| Idle reasons, basic machines | 83.3 % | ≥ 75 % | met |
| Estimation median error | 10.5 % (naive: 24.0 %) | ≤ 12 % | met |
| Estimation mean error (TRD) | 13.8 % | ≤ 12 % | not met |
| Actual time inside p10–p90 | 64.5 % | 75–85 % | not met |
| Unusual behaviour precision | 67.2 % | ≥ 80 % | not met |
| Unusual behaviour recall | 41.8 % | ≥ 80 % | not met |

The first run found three genuine simulator bugs; fixing them lifted advanced idle accuracy from 89.6 % to 96.1 % (see D-050). No engine setting, threshold or model parameter was changed to reach a target. D-051 explains why the remaining targets are missed and lists options that would need your decision.

## How to test (PowerShell, repo folder)
```
uv run --directory backend shiftmate ml train
uv run --directory backend shiftmate eval all
```
Expected output:
- `ml train`: the estimation model version and best iterations, 9 IsolationForests, and 28 fleet patterns.
- `eval all`: `idle: accuracy 0.899 …`, `anomaly: precision 0.672, recall 0.418`, and `estimation: median error 0.105, coverage 0.645`.

Then open `docs\EVAL.md`.

```
uv run --directory backend pytest tests/test_ml.py -v
pnpm test:all
```

## Tests run
All 171 backend tests pass. The new ones cover:
- estimation ranges are ordered, with reasons and minutes
- the remaining-time blend maths
- the vectorised baselines match the reference implementation
- fleet patterns ignore test days and small groups
- EVAL.md sections are replaced in a fixed order
- two simulator regression tests: warm-up only when cold, and cold engines each morning

Frontend 13/13, contracts check OK, lint clean.

## Decisions
- D-050: three simulator bugs found and fixed during the one allowed investigation.
- D-051: the targets still missed, their causes, and options for you, none applied.
- Ruff now allows `X`/`W` names for matrices (the usual machine-learning convention).

## Downloads
None.

## Known issues and decisions for you
- Estimation ranges are too narrow (64.5 % coverage). One option is to calibrate the range on the validation days, which uses no test data. It isn't applied, because it changes TRD-specified behaviour.
- Unusual-behaviour recall is structurally capped by the TRD's "top 5 %" rule. Options are listed in D-051.
