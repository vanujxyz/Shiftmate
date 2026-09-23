# Milestone 12: Cab app B (Report, My Day, offline PWA)

## What was built
**Report** (`/report`):
- **Flow:** tap near miss, incident or machine problem. Type a few words, then answer Yes/No to "people involved" and "anyone hurt". "Check this" returns a draft with time, machine, place, task and weather filled in by the machine gateway.
- **Checking and sending:** type, severity, people and the words can each be changed with big buttons. Send and Delete sit at opposite ends. The draft survives a reload.
- **Recent reports:** each shows whether it is on this tablet, waiting for internet, or sent to the office (D-078).

**Offline:**
- **Gateway unreachable:** a report is built on the tablet, kept in IndexedDB (Dexie), and sent as soon as the cab reconnects. The edge fills the context on arrival, which is why `ReportSaveRequest.context` is now optional (D-077).
- **Last good copy:** the shift, config, insights and report list are kept on the tablet. Screens show the last copy if the gateway can't be reached, but never in place of a real error from it.
- **Privacy:** signing out removes that operator's My Day from the tablet (P-01).

**My Day** (`/insights`, the "My day" tab), private to the signed-in operator:
- how the time went, as a bar with an axis and a sentence;
- stops grouped by cause, each with the evidence in plain words (the cause, never the person), the number of stops and the fuel used;
- truck waits named as a site delay;
- fuel per load against the operator's usual, fuel used while stopped, and fuel used today;
- up to two "went well" notes and up to two ideas, with unit words in the operator's language;
- a week view with one row per earlier day (D-079).

**PWA:**
- The cab builds a service worker that pre-caches the shell, CSS, JS with all strings, and every Anek font subset (15 files, about 2 MB). A manifest and icon make it installable, and every route falls back to the shell (D-080).

**Layout fixes found in the browser:**
- At 1024 px the push-to-talk nav cell is now 220 px, as DESIGN specifies. This fixes Tamil tab labels.
- The Hindi rail drops the risk reason, as Tamil already does (D-071).

**Strings:** 79 new en/hi/ta keys (`scripts/i18n/m12_cab.yaml`). The review list is regenerated (581 strings per language).

## Checked by hand (live edge and ravi_shift at 11:40, 1280 × 800 and 1024 × 768)
- **Filing offline:** site internet off (`/demo/network`), rail showing Offline. Filed a near miss with Tamil text; the draft showed "DIG-A · 11:40", filled in by the edge. After Send the list showed "Waiting for internet".
- **Reload mid-report:** the page was reloaded in the middle of the flow and the draft came back at the check step.
- **Syncing:** internet back on with the fleet service running. Within about 20 s the edge synced (outbox 0), the report showed "Sent to the office", and the rail's sync segment went quiet.
- **My Day:** matches the edge's real numbers. 34 loads at 1.64 L per load against a usual 3.0 L; 3.4 L used while stopped; truck waits grouped with "No truck at the loading point".
- **Overflow** (same rule as the e2e) on My Shift, Safety, Report and My Day (today and week), in ta/hi/en at both sizes: nothing overflows after the two fixes above.
- **Offline PWA:** the preview browser refuses service workers, so this is checked automatically in Chrome instead (below).

## How to test
```
uv run --directory backend shiftmate edge
pnpm --filter cab dev
```
```
uv run --directory backend shiftmate fleet
```
```
curl -X POST localhost:8100/demo/scenario/load -H "content-type: application/json" -d "{\"name\":\"ravi_shift\"}"
```
Sign in with PIN 1001 and play the demo. Toggle the site's internet with:
```
curl -X POST localhost:8100/demo/network -H "content-type: application/json" -d "{\"online\": false}"
```
```
pnpm test:all
pnpm lint:all
pnpm e2e
```
`pnpm e2e` includes the offline PWA test.

## Tests run
- **Backend:** 227 pass (1 new: a report saved without context gets it filled on arrival).
- **Frontend:** 184 pass:
  - 67 in cab, 14 of them new: the tablet store and cache fallback, the pending queue and its flush order, draft persistence, My Day grouping and rendering in en/ta, the week view, the report flow online and with the gateway unreachable, and the tap-over-keyword merge;
  - 104 in ui, 6 in console and 7 in i18n.
- **e2e:** 3 of 3 pass. That's the kitchen sink, the smoke test, and the new offline PWA test in installed Chrome.
- **Contracts check and lint** (ruff, eslint, tsc) are clean.
- **Note:** `tests/test_smoke.py::test_fleet_health` opens the real `data/fleet/fleet.duckdb`. It fails if a fleet service is running at the same time (file lock). It passes with the service stopped.

## Decisions
- D-077: what the tablet keeps, and reports that can't reach the gateway.
- D-078: the typed and tapped report flow.
- D-079: My Day presentation.
- D-080: the cab is an installable PWA, and offline is tested in Chrome.
- D-071 was amended: the nav cell at 1024 px and the Hindi risk reason.

## Observations (for the owner)
- **Voice reports** come in milestone 15, into this same draft.
- **"Learn more" on My Day ideas:** a lesson link from an idea (the edge sends `lesson_id`) will be added with Learn in milestone 16.

## Next (milestone 13)
The console app: live site map, supervisor day summary, fleet, demo control and the evaluation page.

## Downloads
None. vite-plugin-pwa and dexie were already installed.
