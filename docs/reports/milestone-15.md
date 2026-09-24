# Milestone 15: Voice and camera

## What was built
- **Push-to-talk** (`cab/src/voice/`, D-090). This replaces the placeholder disc.
  - Hold to talk, or tap once for a 6 s window, for gloved hands.
  - The transcript sheet shows the words live, in en-IN, hi-IN or ta-IN.
  - The gateway names the intent, and `planAction` turns it into one action:
    - a question opens Ask Cat and reads the answer aloud;
    - "report…" opens a report draft built from the words, for the operator to check;
    - next task, time left, repeat, acknowledge, breaks and help are answered in speech.
  - There is no "call supervisor" intent (D-009).
  - If speech is not available or the microphone is blocked, a calm message says to use the buttons.
- **Checklist by voice** (D-091). "Answer by voice" reads out the next item. Say OK, Problem, or All OK for the rest. The answer words for each language live in `config/checklist.yaml` and reach the cab through `/cab/config`.
- **Spoken alerts:** P1 and P2 alerts are spoken with tones. This was built in milestone 11; this milestone adds a listen tick, an error tick and "repeat" by voice.
- **Rear camera panel** on Safety (`cab/src/camera/`, D-092).
  - MediaPipe EfficientDet-Lite0 is vendored, and the PWA precaches it with its WASM.
  - It shows a live box with a tier-coloured distance tag and the calibration state.
  - Calibrate: the helper stands at 3 m.
  - Readings go to `/proximity/camera` (at most 5 Hz). They are distance, bearing and confidence only, never images.
  - The `worker_near` beat already uses camera readings when present, and falls back to the scripted person if they stop.
- **Camera accuracy protocol** (D-093). "Test accuracy" records 20 readings at each true distance. `POST /eval/camera-protocol` stores them, and `shiftmate eval camera` (part of `eval all`) writes the results to EVAL.md.
- 36 new strings in en, hi and ta (`scripts/i18n/m15_voice_camera.yaml`).

## Results
- **Camera accuracy: not measured.** The protocol needs a webcam and a helper walking towards it; this development machine's browser pane blocks camera access. EVAL.md says "Not measured yet" and gives the steps. Target: MAE ≤ 1.0 m.

## Checked live
- The gateway was restarted, and `/cab/config` returns the camera settings and the checklist voice words. `/assistant/intent` "next task" → `next_task`.
- In the cab (1024 × 768):
  - the badge step falls back to the PIN when the camera is blocked;
  - the checklist shows "Answer by voice" and its hint;
  - Safety shows the Rear camera panel. With the camera blocked it says "The camera is blocked. Allow it in the browser, then turn it on again."
- Fixed while checking:
  - the badge scanner no longer reports "no camera" after it has closed;
  - the camera panel no longer shows its heading twice when there's trouble.

## How to test
```
uv run --directory backend shiftmate edge
pnpm --filter cab dev
```
Load Ravi's shift and sign in with PIN 1001. Then:
- hold the disc and say "next task" or ask a question;
- in the walkaround, tap "Answer by voice";
- on Safety, tap "Turn on camera" (Chrome, with a webcam).
```
pnpm test:all
pnpm lint:all
pnpm e2e
```

## Tests run
- **Backend:** 256 pass (3 new: camera protocol storage and evaluation; the cab config carries the camera and checklist voice settings).
- **Frontend:** 218 pass. New tests:
  - `voice.test.tsx` (9): intent → action, checklist words in three languages, the recognizer's language and partial words, and the hold, spoken-report, tap and no-support flows;
  - `camera.test.ts` (10): distance, calibration, bearing, nearest person, tiers, smoothing, calibration and protocol accumulation, and the blocked and failed camera states.
- **e2e:** 3 pass. Lint and typecheck are clean.
