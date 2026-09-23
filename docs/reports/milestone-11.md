# Milestone 11: Cab app A (frame, alerts, sign-in, My Shift, Safety)

## What was built
The cab now runs on live edge data at http://localhost:5173. It has sign-in, the frame, the alert layer, My Shift and Safety.

**Cab frame** (`apps/cab/src/shell/`):
- **Status rail** from live data (`railProps.ts`, a pure function): the proximity Reach with its tier and side, risk band with its main reason, seatbelt, machine, the queue pip with the edge's own count, sync state and the machine's clock.
- **Stale mark** once telemetry is older than 30 s or the socket is down.
- **Modes.** Working mode shows only the rail, the active task line (task, zone, progress blocks, time left) and alerts. Paused mode shows the screens and the bottom nav. Switching to Working is immediate, unless a finger is already pressing (D-076).
- **Push-to-talk button** in the same place in both modes. It does nothing yet; voice comes in milestone 15.
- **Connection.** The WebSocket client reconnects with back-off 1, 2, 4, 8, 10 s. A "No contact with the machine" notice appears after 3 s without a connection.

**Alert layer** (`AlertLayer.tsx`, `live/store.ts`, `live/effects.ts`, `live/audio.ts`):
- The cab only draws what the edge's policy engine decided:
  - **P1:** full-screen takeover with the cause drawn big and a single "I've stopped" button, which acknowledges on the edge;
  - **reduced P1:** a red frame that keeps a tone every 5 s;
  - **P2:** banner under the rail with "Seen";
  - **P3:** strip above the nav with "Later" or "Done";
  - **P4:** the Updates feed on My Shift.
- **Sound and speech** follow `alert_policy.yaml` through `/cab/config`:
  - P1 tone every 1 s, spoken line once plus a repeat after 4 s, and a confirming tone on acknowledge;
  - P2 tone once, plus a repeat after 20 s;
  - P3 and P4 silent.
- Speech is in the operator's language (en-IN, hi-IN, ta-IN), with English as the fallback. "Read alerts aloud" is a setting, locked while working.

**Start screen** (`/start`):
- Language first, in each language's own script. The edge's state is shown under it in that language.
- Badge QR by camera via jsQR, with a PIN fallback. The demo PIN is the operator number, e.g. 1001 for OP1001.
- Walkaround checklist from the edge: OK or Problem per item, plus "All OK". Problems are reported to the edge.

**My Shift** (`/`):
- Today's tasks in order. Each shows its quantity, zone and start time, an estimate as a range with the most likely value, and the top reasons (e.g. "Wet ground adds time +17 m"). Live progress and estimates come over the socket.
- Conditions panel with the likely finish as a clock range, heat, ground, and rain or daylight, plus a risk sentence.
- Suggested breaks and the Updates feed.
- The machine ID and operator name in the content header, which covers Tamil (D-068).

**Safety** (`/safety`):
- People near the machine on a 230 px Reach, with a sentence saying where.
- Today's warning distances, noted as wider when risk is raised.
- Time without a break against the break-reminder threshold, which shortens in heat.
- Risk now, as the stack light and word, with contributions per factor.
- Recent alerts, newest first.
- Settings: theme, language, read aloud, and sign out.

**Edge:**
- `GET /cab/config` returns alert timings, the checklist and languages.
- The cab snapshot now carries the risk breakdown (D-072).
- Contracts regenerated.

**Strings:** 104 new keys in en/hi/ta (`scripts/i18n/m11_cab.yaml`). `docs/TRANSLATIONS_REVIEW.md` is regenerated (502 strings per language to review).

## Checked in the browser (1280 × 800 and 1024 × 768, against the running edge and ravi_shift)
- **Sign-in in Tamil.** The camera was blocked in the preview browser, so the PIN pad opened with the note. PIN 1001 led to "வருக, Ravi Kumar", the 7-item Tamil checklist, and then My Shift.
- **Working mode** after the first task started: 176 px rail, task line with load blocks, and "about 1 h 45 m left".
- **Worker beat at 09:30:** rail clear → person near → P2 banner with risk raised → too close → P1 takeover with "1 more alert after this" and the +1 queue pip.
- **Step-out beat:** P2 heat banner, then the queued fatigue P2 after "Seen" (the queue working). Safety showed widened distances, 279 min without a break against an 83 min threshold, and risk from tiredness 48 %, heat 40 %, ground 13 %.
- **Overflow check** (the same rule as the kitchen-sink e2e) on My Shift and Safety in ta/hi/en at both sizes, including the worst rail (stale, raised risk, 48 waiting): nothing overflows.

## Problems found and fixed on the way
- **The Tamil P1 pushed "I've stopped" off the screen.** The button is now always on screen and Tamil/Hindi text is sized to fit. The e2e test now fails if this ever happens again (D-073).
- **The rail was wider than the screen** with stale data, in Tamil at 1024 px and in English at 1280 px. Fixed with the short forms (D-071).
- **A Tamil condition value overlapped its label** in ConditionsSummary. The value now wraps to its own line.
- **Two quick PIN taps could count as one.** Fixed (D-075).
- **Alert history was in filing order.** It is now sorted by when each alert was raised.
- **The smoke e2e still expected the milestone-1 placeholder.** It now checks the Start screen and Tamil switching with the edge down.

## How to test
```
uv run --directory backend shiftmate edge
pnpm --filter cab dev
```
```
curl -X POST localhost:8100/demo/scenario/load -H "content-type: application/json" -d "{\"name\":\"ravi_shift\"}"
```
Open http://localhost:5173 and sign in with PIN 1001. Then:
```
curl -X POST localhost:8100/demo/play
```
```
pnpm test:all
pnpm lint:all
pnpm e2e
```

## Tests run
- **Backend:** 226 pass (1 new, the snapshot risk breakdown).
- **Frontend:** 170 pass:
  - 53 in cab: reducer and alert projection, sound timing with fake timers, socket back-off, rail, mode transition, text helpers, and the app (sign-in flow, Paused, Working, Tamil, P1/P2/P3, operator replaced, Safety);
  - 104 in ui, 6 in console and 7 in i18n.
- **e2e:** 2 of 2 pass. The kitchen sink now also checks P1 vertical fit.
- **Contracts check and lint** (ruff, eslint, tsc) are clean.

## Decisions
D-071 rail short forms · D-072 snapshot risk breakdown · D-073 P1 button always on screen · D-074 P3 Done vs Later · D-075 sign-in flow · D-076 cab session and edge authority.

## Observations (for the owner)
- **A risk alert fires before the shift starts.** The edge raises "Risk level raised" at 06:43, during warm-up before the 06:58 scenario start, and it waits on the strip for the operator. The engine was not changed; "Done" now clears it (D-074).
- **Not tested here:** the badge camera path in a real tablet browser (the preview browser blocks cameras) and spoken alerts (the preview browser has no voices). Both are covered by unit tests of the logic and are checked again in milestone 15.
- **Translations:** the new Hindi and Tamil strings need a native review (`docs/TRANSLATIONS_REVIEW.md`).

## Next (milestone 12)
Report, My Day, offline PWA.

## Downloads
None.
