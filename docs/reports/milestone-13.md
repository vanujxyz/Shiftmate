# Milestone 13: Console app

## What was built
The supervisor console at http://localhost:5174 has five pages inside one frame. The frame has the sections, the language (en/hi/ta) and the dashed "Demo mode · simulated data" strip on every page.

- **Live map** (`/site/:siteId`, F-SUP-01):
  - the site's plan from the gateway (grid, haul roads, zones with decals);
  - machines with their swing rings, boom, state and ID plate;
  - trucks (open when waiting, filled when moving) and people as dots;
  - the proximity tier sector toward the nearest person, hatched only for critical.
  It updates live from `/ws/site` and glides between the 5 Hz updates at the screen's frame rate: 68 fps measured, against a requirement of 30 or more. Selecting a machine shows its model, sensors, operator, nearby tier, warning rings and its day (engine, working and idle time; tasks and whether they are on track). The side panel also lists the site's events (alerts, reports, truck waits), and a legend, north arrow and 50 m scale are always shown (D-081).
- **Day summary** (`/supervisor/:siteId`, F-SUP-02…05):
  - a day picker;
  - tasks by machine with done, on track or behind;
  - where time was lost: one lead sentence naming the cause, causes with share bars, truck waiting by hour, and the fleet's suggestion with its saving range and basis;
  - safety: critical alerts named with the operator (safety-critical events only), in the site's local time; warnings grouped by kind; reports; hours at raised and high risk per machine;
  - team trends as experience groups, with small groups hidden (D-084).
- **Fleet** (`/fleet`, F-FLT-07, 08):
  - site tiles with local time, machines active and risk split;
  - the fleet by machine type and sensor tier;
  - what the fleet has learned from finished tasks;
  - the scale panel. Measured numbers (live ingest with a sparkline, the 10,000-machine run, the runtime benchmark) are kept apart from the dashed, labelled projection to 1.6 million machines.
- **Demo** (`/demo`): load or restart a scenario, play or pause, choose a speed from 1× to 60×, and jump to any story beat (captions in the chosen language). It also toggles the site's internet and the cab captions, and shows who is signed in on the cab. The removed buttons stay removed.
- **Evaluation** (`/eval`): docs/EVAL.md as written by `shiftmate eval all`, read at build time (D-084).

Supporting changes:
- **Gateway:** new endpoints `GET /site/layout` and `GET /demo/scenarios` (D-082).
- **Contracts generator bug fixed:** it had silently dropped every field named `title`, which affected `Lesson`, `LessonSummary` and `ScenarioInfo` (D-083).
- **Test hygiene:** `test_smoke.py` now builds the fleet app on a temporary database, so the backend suite passes while a fleet service is running.
- **Strings:** 150 new en/hi/ta keys (`scripts/i18n/m13_console.yaml`); the review list is at 731 strings per language.

## Checked in the browser (1440 × 900, live gateway on ravi_shift and fleet service)
- **Live map:**
  - all 12 site machines, 3 trucks and 14 people moving;
  - EXC001 marked as the demo machine;
  - site events arriving;
  - 68 animation frames per second.
- **Day summary for 23 Sep:** 51 of 77 tasks done, 18 behind; the machine table; critical alerts at site-local times with operator names; grouped warnings.
- **Fleet, Demo and Evaluation:** all render against the real services.
- **Overflow check** on all five pages in en, hi and ta: nothing overflows.
- **Old gateway process:** before restarting the gateway, the map got a 404 from the old process and wrongly said "not reachable". The page now tells "no scenario" (409), "not reachable" (no answer) and other errors apart.

## How to test
```
uv run --directory backend shiftmate edge
uv run --directory backend shiftmate fleet
pnpm --filter console dev
```
Open http://localhost:5174 and load Ravi's shift on the Demo page.
```
pnpm test:all
pnpm lint:all
pnpm e2e
```

## Tests run
- **Backend:** 228 pass (new: the layout and scenarios endpoints).
- **Frontend:** 202 pass:
  - 18 in console, 12 of them new: the site reducer and interpolation, the tier-sector bearing, the frame, the live map with a driven socket (selection, detail, events), the day summary, the fleet (measured vs projection), the demo control in Tamil, the evaluation page, and Markdown safety;
  - 67 in cab, 104 in ui and 7 in i18n.
- **e2e:** 3 of 3 pass.
- **Contracts check and lint** are clean.

## Decisions
D-081 console site map · D-082 two gateway endpoints · D-083 contracts generator kept `title` fields · D-084 the console frame, day summary and fleet pages.

## Observations (for the owner)
- **Today's day summary is thin during the live demo.** Only the demo machine (EXC001) uploads to the fleet (D-052, D-067), and the fleet only has what the gateway has synced. Seeking backwards replays the world and resets the gateway's store, so earlier uploads of "today" are not repeated. Earlier days have the full site from history.
- **Fleet tile clocks** show each site's real local time now, not the simulated time.

## Next (milestone 14)
Ask Cat assistant: knowledge files, hybrid index, online answers with Gemini (with offline fallback), intents, the `/ask` screen and its evaluation.

## Downloads
None.
