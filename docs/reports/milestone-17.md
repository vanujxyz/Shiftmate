# Milestone 17: Demo polish and end-to-end

## What was built
- **Ravi's shift end to end** (`e2e/ravi-shift.spec.ts`, D-102):
  - runs against the real gateway, cab and console;
  - Ravi signs in in Tamil with PIN 1001 and does the walkaround;
  - the story then runs at 30×, beat by beat, using pause, speed, seek and play;
  - the near miss is reported by voice through a fake speech recognizer that "hears" a Tamil sentence;
  - it passed twice in a row.
- **Safety beats play at real time** (D-099): `worker_near` and `seatbelt` drop the clock to 1× so the caution → danger → critical escalation and the P1 takeover can be seen at 30×. Catch-up per tick is capped at 1 s of wall time.
- **Voice screens in Working mode** (D-100): a spoken report or question opens its screen over the working strip. Report returns to the strip 3 s after sending.
- **Captions, end of shift, reset** (D-101):
  - beat captions in en/hi/ta show for 10 s in the cab when turned on in Demo control;
  - `end_shift` opens My Day (also when the machine was still working as the story paused, fixed in this milestone's review);
  - `POST /demo/reset` and a Reset demo button;
  - Ask Cat loads when the gateway starts, so the first voice answer is not slow.
- **fleet_tour** in the console: the basic-tier wheel loader at the Pilbara mine and the 10,000-machine scale card linking to Fleet.
- **README**:
  - setup, run and demo guide with troubleshooting;
  - architecture diagram (`docs/architecture.svg`);
  - six screenshots (`docs/screenshots/`, captured by `node scripts/screenshots.mjs`).

## Clean-clone test (2026-09-26)
- `git clone` into an empty folder, then `pnpm install --frozen-lockfile` and `pnpm setup:data`. It exited 0 in about 20 minutes:
  - history: 3,185,280 ticks, 60 machines, 42 days;
  - replay through the engines (541 s);
  - model training;
  - the embedding model downloaded (470 MB) and the Ask Cat index built;
  - `eval all` wrote EVAL.md.
- `pnpm dev:all` in the clone: the edge (8100), fleet (8200), cab (5173) and console (5174) all answered within 10 s.
- The rebuilt data had 7,043 finished tasks, against 7,040 in the main repo's older data and 7,042 in a rebuild of the main repo. Same seed, different worlds: this was traced to a set iterated in hash order in the truck dispatcher, and fixed in milestone 18 (D-103).

## Found and fixed while checking
- At the end-of-shift beat the machine was still on its last task, so the cab showed the working strip instead of My Day. My Day now opens over Working mode when the scenario ends the shift. There is a new vitest for this.

## How to test
```
pnpm setup:data
pnpm dev:all
pnpm e2e
```
Then open the cab at http://localhost:5173 (1280 × 800) and the console Demo page at http://localhost:5174/demo.

## Tests run
- **Backend:** 259 pass.
- **Frontend:** 231 pass (1 new: My Day at end of shift in Working mode).
- **e2e:** 4 pass (smoke, offline, kitchen sink, ravi_shift).
- Lint and typecheck are clean.
