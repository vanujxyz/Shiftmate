# ShiftMate — Evaluation results

Measured results, reported as they are, including targets that were not met (golden rule 11).
All numbers come from `shiftmate eval …` on simulated data (see `data/history/SUMMARY.md`);
nothing here is typed in by hand. Test data are history days 36–42, which no model saw during
training, tuning or early stopping.

<!-- BEGIN data -->
## Data

Simulated history, seed 7: 42 days (2026-08-13 to 2026-09-23), 60 machines, 80 operators, 3,185,280 ticks at 30 s, 7,040 completed tasks. Split by day: train 1–32, validation 33–35, test 36–42.
<!-- END data -->

<!-- BEGIN idle -->
## Idle reasons (F-INS-02)

Test days 36–42 (2026-09-17 to 2026-09-23): 5,386 idle segments classified by the engines, each compared with the majority true reason over its ticks.

**Overall accuracy 89.9 %**, macro-average recall 84.8 % (every reason weighted equally, so the common 'Not sure' class cannot hide weak classes).

| sensor tier | segments | accuracy | target | result |
|---|---|---|---|---|
| advanced | 1474 | 95.9 % | 90.0 % | met |
| standard | 1926 | 92.1 % | – | – |
| basic | 1986 | 83.2 % | 75.0 % | met |

### Per reason

| reason | precision | recall | true segments | predicted |
|---|---|---|---|---|
| SCHEDULED_BREAK | 80.7 % | 100.0 % | 394 | 488 |
| WARM_UP | 98.7 % | 90.4 % | 658 | 603 |
| UNATTENDED_RUNNING | 97.6 % | 58.2 % | 141 | 84 |
| WAITING_FOR_TRUCK | 96.4 % | 67.8 % | 994 | 699 |
| HABIT | 73.5 % | 95.1 % | 536 | 694 |
| UNKNOWN | 91.7 % | 97.1 % | 2663 | 2818 |

### Confusion matrix (rows: true reason, columns: predicted)

| true \ predicted | SCHEDULED_BREAK | WARM_UP | UNATTENDED_RUNNING | WAITING_FOR_TRUCK | HABIT | UNKNOWN |
|---|---|---|---|---|---|---|
| SCHEDULED_BREAK | 394 | 0 | 0 | 0 | 0 | 0 |
| WARM_UP | 0 | 595 | 0 | 0 | 63 | 0 |
| UNATTENDED_RUNNING | 2 | 1 | 82 | 0 | 35 | 21 |
| WAITING_FOR_TRUCK | 26 | 4 | 2 | 674 | 76 | 212 |
| HABIT | 21 | 0 | 0 | 5 | 510 | 0 |
| UNKNOWN | 45 | 3 | 0 | 20 | 10 | 2585 |
| NOT_IDLE | 0 | 0 | 0 | 0 | 0 | 0 |

### True idle periods that were never classified

0 of 5,587 true idle periods of at least a minute had no classified segment (they were merged into, or split from, neighbouring states at 30 s resolution).

None.
<!-- END idle -->

<!-- BEGIN anomaly -->
## Unusual behaviour (F-INS-04, F-INS-05)

Test days: 16,723 intervals, 1,702 truly anomalous (10.2 %); 1,056 flagged.

| metric | value | target | result |
|---|---|---|---|
| precision | 68.9 % | 80.0 % | **not met** |
| recall | 42.8 % | 80.0 % | **not met** |
| F1 | 52.8 % | – | – |

Without the P1 hard rule (model and z-score only): precision 71.3 %, recall 35.0 %.

Why recall is limited: the TRD rule lets the model flag only intervals in its top 5.0 % (and only those that are also ≥ 3 robust z-scores worse than the operator's own normal), while 10.2 % of test intervals are truly anomalous. Behaviour that is habitual for an operator is part of their own baseline and is not unusual for them, and machines without a proximity or seat sensor cannot see speeding near people or an empty cab.

### Recall per anomaly type

| anomaly type | true intervals | recall |
|---|---|---|
| habit_idle | 974 | 40.6 % |
| unattended | 191 | 63.9 % |
| seatbelt | 278 | 77.3 % |
| speed_near_person | 37 | 27.0 % |
| fuel_abnormal | 128 | 16.4 % |
| low_productivity | 150 | 10.0 % |

### By sensor tier

| sensor tier | intervals | anomalous (truth) | precision | recall | F1 |
|---|---|---|---|---|---|
| advanced | 4463 | 485 | 61.1 % | 47.8 % | 53.6 % |
| standard | 6162 | 576 | 75.4 % | 44.3 % | 55.8 % |
| basic | 6098 | 641 | 71.3 % | 37.6 % | 49.2 % |

### What drives the false alarms

| false alarm driven by | intervals |
|---|---|
| a P1 safety rule (e.g. a person inside the swing radius) | 113 |
| IsolationForest + z-score only | 215 |
<!-- END anomaly -->

<!-- BEGIN estimation -->
## Task time estimation (F-SHIFT-02, F-SHIFT-03, F-FLT-05)

Model `est-20260923-s7` (LightGBM quantile 0.1 / 0.5 / 0.9, trained on days 1–32, early stopping on days 33–35). Test: 1,147 completed tasks on days 36–42.

| metric | model | naive base-rate estimate | target | result |
|---|---|---|---|---|
| median absolute error (% of actual) | 10.3 % | 24.0 % | ≤ 12.0 % | met |
| mean absolute error (% of actual) | 13.7 % | 24.3 % | ≤ 12.0 % (TRD) | **not met** |
| mean absolute error (minutes) | 20.0 | 41.8 | – | – |
| actual inside p10–p90 | 63.2 % | – | 75–85 % | **not met** |

Validation days (used for early stopping): median error 8.7 %, coverage 67.9 %.

### Per task type (test days)

| task type | tasks | MAE (min) | median error | mean error | inside p10–p90 |
|---|---|---|---|---|---|
| backfilling | 228 | 18.50 | 9.7 % | 12.0 % | 68.4 % |
| grading | 67 | 18.70 | 8.9 % | 11.4 % | 67.2 % |
| site_clearing | 405 | 19.40 | 9.4 % | 11.4 % | 60.2 % |
| stockpile_moving | 126 | 18.40 | 7.8 % | 10.5 % | 66.7 % |
| trenching | 162 | 20.40 | 10.7 % | 11.8 % | 64.8 % |
| truck_loading | 159 | 25.00 | 20.6 % | 27.1 % | 57.2 % |

### Fleet-learned patterns (days 1–35, all machines)

| task type | condition | effect | tasks | machines | compared with |
|---|---|---|---|---|---|
| grading | muddy | +34 % | 60 | 11 | dry/rocky |
| backfilling | muddy | +31 % | 218 | 36 | dry/rocky |
| trenching | muddy | +30 % | 145 | 25 | dry/rocky |
| stockpile_moving | muddy | +28 % | 121 | 16 | dry/rocky |
| site_clearing | muddy | +28 % | 325 | 52 | dry/rocky |
| truck_loading | frozen | +23 % | 69 | 7 | dry/rocky |
| backfilling | frozen | +23 % | 157 | 6 | dry/rocky |
| site_clearing | frozen | +21 % | 213 | 8 | dry/rocky |
<!-- END estimation -->

<!-- BEGIN assistant -->
## Ask Cat assistant (F-ASK-01…06)

40 questions in `eval/assistant_eval.yaml` (30 answerable: 10 en, 10 hi, 10 ta; 10 that must be refused). The index holds 46 chunks from 15 team-written files. Online answers use `gemini-3.5-flash-lite`; key facts are graded by the same model with a fixed rubric (`assistant/prompts/judge_system.md`), and every reply is cached by prompt hash.

Citation accuracy counts a refusal as a miss. Targets (TRD §12): citation accuracy and key-fact coverage ≥ 85 %, refusal accuracy ≥ 90 %.

| mode | language | citation accuracy | key-fact coverage | retrieval hit@5 | answered | refusal accuracy |
|---|---|---|---|---|---|---|
| offline | all | 66.7 % | 70.0 % | 93.3 % | 70.0 % | 100.0 % |
| offline | en | 50.0 % | 60.0 % | 100.0 % | 60.0 % | 100.0 % |
| offline | hi | 80.0 % | 80.0 % | 100.0 % | 80.0 % | 100.0 % |
| offline | ta | 70.0 % | 70.0 % | 80.0 % | 70.0 % | 100.0 % |
| online | all | 93.3 % | 93.3 % | 93.3 % | 93.3 % | 100.0 % |
| online | en | 100.0 % | 100.0 % | 100.0 % | 100.0 % | 100.0 % |
| online | hi | 100.0 % | 100.0 % | 100.0 % | 100.0 % | 100.0 % |
| online | ta | 80.0 % | 80.0 % | 80.0 % | 80.0 % | 100.0 % |

| mode | citation ≥ 85 % | key facts ≥ 85 % | refusals ≥ 90 % |
|---|---|---|---|
| offline | not met | not met | met |
| online | met | met | met |

### Questions missed

- offline: answerable without an expected citation: en01, en03, en05, en09, en10, hi08, hi10, ta08, ta09, ta10; unanswerable but answered: none.
- online: answerable without an expected citation: ta09, ta10; unanswerable but answered: none.

Offline answers return the best-matching manual passage as written, and only when it scores at least 0.55 (TRD §10.4), so offline mode refuses more often: it prefers saying it does not know to guessing.
<!-- END assistant -->

<!-- BEGIN camera -->
## Camera proximity (F-SAFE-03)

1 recorded session(s), 1 with a calibrated camera; 20 readings. Overall mean absolute error **1.85 m** (target ≤ 1.0 m: not met).

| true distance | readings | mean absolute error | max error |
|---|---|---|---|
| 6 m | 20 | 1.85 m | 3.47 m |
<!-- END camera -->

<!-- BEGIN scale -->
## Scale (F-FLT-07)

**Scale run** (`shiftmate sim scale`, 2026-09-23): 10,000 synthetic machines, 60 simulated minutes, interval summaries and shared events resampled from the simulated history, posted to the Fleet Service in batches of 500 by one sequential client on the demo laptop.

| Measure | Value |
|---|---|
| Records ingested | 44,612 (40,000 intervals, 4,612 events) in 92 requests |
| Ingest throughput | 4,082 records/s (time inside ingest requests) |
| Request latency per batch | p50 120 ms, p95 147 ms |
| Wall time | 29.7 s |
| Upload per machine | 5.7 kB/h, 4.5 records/h |

**Runtime benchmark** (`shiftmate bench runtime`, 2026-09-23): 200 full machine runtimes (all engines), 30 simulated minutes at 1 s ticks (360,000 runtime steps), on the demo laptop.

| Measure | Value |
|---|---|
| CPU per machine per tick | mean 0.185 ms, p95 0.215 ms |
| Memory per machine runtime | 0.04 MB (Python allocations over the first minute; a lower bound) |
| Upload per machine | 4.8 kB/h, 3.8 records/h |

**Projection to 1,600,000 machines — a linear projection, not a measurement.** Basis: runtime benchmark (200 full machine runtimes); 24 reporting hours a day (upper bound).

| Projected | Value |
|---|---|
| Uplink | 183.5 GB/day |
| Records | 145,920,000/day ≈ 1,689/s |
| Ingest capacity | ≈ 0.4× the single laptop process measured above |
<!-- END scale -->
