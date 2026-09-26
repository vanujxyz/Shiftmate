# Milestone 18: Final evaluation and review

## What was done
- **Evaluation rebuilt from scratch.** `pnpm setup:data` generated history, replayed it through the engines, trained the models, built the index and ran `shiftmate eval all`, which rewrote `docs/EVAL.md`. The Ask Cat online run used the on-disk response cache: 89 answers came from the cache and no new Gemini calls were made.
- **Determinism bug found and fixed** (D-103):
  - Three builds with seed 7 gave 7,040, 7,042 and 7,043 finished tasks.
  - The truck dispatcher drew a random number per zone while looping over a Python set, whose order changes in every process.
  - It now loops in sorted order.
  - A new test runs the generator in two processes with different `PYTHONHASHSEED` values. It fails without the fix and passes with it.
  - After the fix, a full 42-day rebuild with a different hash seed gave the same four site hashes.
- **Traceability:** `docs/TRACEABILITY.md` maps all 62 PRD requirements (58 Must, 4 Should) to code, tests and the demo beat that shows them.
- **Small fixes found in the final review:**
  - the end-of-shift beat now opens My Day even while the machine is still working (milestone 17 report);
  - the console had no favicon, the only console error left in the full scenario.

## EVAL.md headlines (targets from PRD §10; misses reported as they are)
| Measure | Result | Target | |
|---|---|---|---|
| Idle reason accuracy, advanced sensors | 95.9 % | ≥ 90 % | met |
| Idle reason accuracy, basic sensors | 83.2 % | ≥ 75 % | met |
| Idle reason accuracy, overall | 89.9 % | – | – |
| Unusual behaviour precision / recall | 68.9 % / 42.8 % | ≥ 80 % | **not met** (D-051) |
| Task time median error | 10.3 % | ≤ 12 % | met |
| Task time p10–p90 coverage | 63.2 % | 75–85 % | **not met** (D-051) |
| Ask Cat online: correct citation / refusals | 93.3 % / 100 % | ≥ 85 % / ≥ 90 % | met |
| Ask Cat offline: correct citation / refusals | 66.7 % / 100 % | – | – |
| Camera distance error | 1.85 m (one session, 6 m only) | ≤ 1.0 m | see below |

The rebuilt data moved the numbers a little from the previous EVAL.md, for example coverage from 64.5 % to 63.2 % and anomaly precision from 67.2 % to 68.9 %. The pitch deck quotes 63.9 % coverage, which matches neither; use the EVAL.md value.

**Camera:** `data/eval/camera_protocol.jsonl` holds one session saved on 2026-09-24 at 11:32. It has 20 readings, all labelled 6 m, with estimates around 2.5–4 m. The protocol page was used during the live camera checks that day, and nothing shows that anyone stood at 6 m. So this is probably not a real protocol run. The file and the generated section were left as they are. The owner should either run the full protocol (2–6 m with a helper) or delete the file and re-run `shiftmate eval camera`.

## Demo readiness checklist (CLAUDE.md §8)
- [x] `pnpm setup:data` from a clean state succeeds: done in a fresh clone (milestone 17 report), and again in the main repo.
- [x] `pnpm dev:all` starts all four services; cab at 1280 × 800, console on a second window.
- [x] `ravi_shift` beats all behave as PRD §9:
  - when seeking at 30×: `e2e/ravi-shift.spec.ts` passes twice in a row;
  - the unbroken run: `tests/test_headless.py` checks every beat on time, at 60×;
  - a full live 1× run by a person was not repeated in this milestone.
- [~] Camera proximity after calibration works, and the camera path is unit-tested. The accuracy protocol is still open (see above). The simulated path works without a camera (e2e).
- [x] Network toggle:
  - the offline assistant answer;
  - reports queue;
  - sync drains after reconnect (e2e `offline` and `ravi-shift`, `test_offline_outbox_grows_then_drains`).
- [~] Language switch to Tamil and Hindi shows complete translations (completeness tests, kitchen-sink e2e in 3 languages, Tamil e2e). Spoken alerts use the browser voices and need the speech packs installed, so they were not heard in this check.
- [x] `fleet_tour` loads WHL014, the basic-tier loader at the Pilbara mine. `/scale/stats` shows the 10,000-machine run and the projection.
- [x] `EVAL.md` is current, and the Evaluation page renders it (console tests).
- [x] No console errors in either app during the scenario. `node scripts/screenshots.mjs` walks the story in both apps and reports 0 errors.
- [x] README instructions verified by the clean-clone run.

## How to test
```
pnpm setup:data
pnpm test:all
pnpm lint:all
pnpm e2e
```

## Tests run
- **Backend:** 260 pass (1 new: history is the same in any process).
- **Frontend:** 231 pass (i18n 7, ui 105, cab 100, console 19).
- **e2e:** 4 pass, and `ravi-shift` passed again on a second run.
- Lint, typecheck and the contracts check are clean.

## Still open (for the owner)
- Camera accuracy protocol with a webcam and a helper.
- D-051: anomaly precision and recall and estimation coverage miss their targets. The fixes change TRD-specified behaviour and need the owner's decision.
- The deck's numbers should be updated to the current EVAL.md.
